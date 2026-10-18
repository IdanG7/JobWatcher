"""The installed app: stable port, stopping a running copy, windowless errors."""
from http.server import BaseHTTPRequestHandler
import io
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import portable_start
from portable_start import acquire_lock, bind_server, preferred_port, stop_and_wait, wait_for_exit
from dashboard import JobwatchHTTPServer
import updater

ROOT = Path(__file__).resolve().parents[2]

class Quiet(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(os.name == "nt", "Windows locks and sockets")
class InstalledAppTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)          # runs last: after locks and servers close
        self.data = Path(tmp.name)

    def serve(self, server):
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        return server

    def test_bad_remembered_ports_are_ignored(self):
        self.assertEqual(preferred_port(self.data), 0)
        for text in ("abc", "80", "70000", ""):
            (self.data / "port").write_text(text, encoding="utf-8")
            self.assertEqual(preferred_port(self.data), 0, text)
        (self.data / "port").write_text("8790\n", encoding="utf-8")
        self.assertEqual(preferred_port(self.data), 8790)

    def test_restart_reuses_the_same_port(self):
        first = bind_server(JobwatchHTTPServer, Quiet, self.data)
        port = first.server_port
        first.server_close()
        second = bind_server(JobwatchHTTPServer, Quiet, self.data)
        self.addCleanup(second.server_close)
        self.assertEqual(second.server_port, port)

    def test_port_held_by_another_program_is_not_shared(self):
        other = socket.socket()
        self.addCleanup(other.close)
        other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        other.bind(("127.0.0.1", 0))
        other.listen()
        taken = other.getsockname()[1]
        (self.data / "port").write_text(str(taken), encoding="utf-8")
        server = bind_server(JobwatchHTTPServer, Quiet, self.data)
        self.addCleanup(server.server_close)
        self.assertNotEqual(server.server_port, taken)
        self.assertEqual(preferred_port(self.data), server.server_port)

    def test_a_running_jobwatch_port_cannot_be_taken_over(self):
        server = bind_server(JobwatchHTTPServer, Quiet, self.data)
        self.addCleanup(server.server_close)
        intruder = socket.socket()
        self.addCleanup(intruder.close)
        intruder.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with self.assertRaises(OSError):
            intruder.bind(("127.0.0.1", server.server_port))

    def test_stop_asks_the_running_copy_and_waits_for_it_to_exit(self):
        lock = acquire_lock(self.data / "running.lock")
        calls = []

        class Shutdown(Quiet):
            def do_POST(self):
                calls.append(self.path)
                self.send_response(200)
                self.end_headers()
                threading.Timer(0.3, lock.close).start()      # the server exits a moment later

        server = self.serve(JobwatchHTTPServer(("127.0.0.1", 0), Shutdown))
        (self.data / "instance.json").write_text(
            json.dumps({"url": f"http://127.0.0.1:{server.server_port}"}), encoding="utf-8")
        self.assertTrue(stop_and_wait(self.data, seconds=10))
        self.assertEqual(calls, ["/api/shutdown"])

    def test_stop_reports_a_copy_that_does_not_exit(self):
        lock = acquire_lock(self.data / "running.lock")
        self.addCleanup(lock.close)
        self.assertFalse(stop_and_wait(self.data, seconds=0.3))

    def test_waiting_for_exit_ends_a_lingering_server_only_when_allowed(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
        self.addCleanup(child.kill)
        self.assertFalse(wait_for_exit(child.pid, 0.3))
        self.assertIsNone(child.poll())
        self.assertTrue(wait_for_exit(child.pid, 0.3, may_end=True))
        self.assertIsNotNone(child.poll())

    def test_a_reused_process_id_is_neither_waited_for_nor_ended(self):
        child = subprocess.Popen(["ping", "-n", "30", "127.0.0.1"], stdout=subprocess.DEVNULL)
        self.addCleanup(child.kill)
        self.assertTrue(wait_for_exit(child.pid, 5, may_end=True))
        self.assertIsNone(child.poll())

    def test_stop_waits_for_the_recorded_server_process_to_exit(self):
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1.5)"])
        self.addCleanup(child.kill)
        (self.data / "server.pid").write_text(str(child.pid), encoding="utf-8")
        self.assertTrue(stop_and_wait(self.data, seconds=10, ask=False))
        self.assertIsNotNone(child.poll())

    def test_waiting_for_a_finished_process_returns_at_once(self):
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait()
        self.assertTrue(wait_for_exit(child.pid, 5))

    def test_stop_with_nothing_running_succeeds(self):
        self.assertTrue(stop_and_wait(self.data, seconds=1))
        self.assertEqual(portable_start.main(["--stop", "--data-dir", str(self.data)]), 0)


class WindowlessTests(unittest.TestCase):
    def test_startup_failure_without_a_console_shows_a_message_box(self):
        shown = []
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None), \
                patch.object(portable_start, "main", side_effect=RuntimeError("disk full")), \
                patch.object(portable_start, "show_error", shown.append):
            self.assertEqual(portable_start.run([]), 1)
        self.assertEqual(len(shown), 1)
        self.assertIn("disk full", shown[0])

    def test_success_without_a_console_shows_nothing(self):
        shown = []
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None), \
                patch.object(portable_start, "main", return_value=0), \
                patch.object(portable_start, "show_error", shown.append):
            self.assertEqual(portable_start.run([]), 0)
        self.assertEqual(shown, [])

    def test_stop_failures_never_show_a_message_box(self):
        shown = []
        with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None), \
                patch.object(portable_start, "main", return_value=1), \
                patch.object(portable_start, "show_error", shown.append):
            self.assertEqual(portable_start.run(["--stop"]), 1)
        self.assertEqual(shown, [])

    def test_console_runs_never_show_a_message_box(self):
        shown = []
        with patch.object(sys, "stdout", io.StringIO()), \
                patch.object(portable_start, "main", return_value=1), \
                patch.object(portable_start, "show_error", shown.append):
            self.assertEqual(portable_start.run([]), 1)
        self.assertEqual(shown, [])


class InstallerScriptTests(unittest.TestCase):
    """The installer shows Foothold; what installed Jobwatch copies rely on stays."""
    script = (ROOT / "tools/jobwatch.iss").read_text(encoding="utf-8")
    setup = dict(line.split("=", 1) for line in script.split("[Setup]")[1].split("\n[")[0].splitlines()
                 if "=" in line and not line.startswith(";"))

    def test_upgrades_replace_the_installed_copy(self):
        self.assertEqual(self.setup["AppId"], "{{1AE8ADC1-F27E-4DCC-AA4E-691280798458}")

    def test_installed_copies_still_accept_the_setup_file_as_an_update(self):
        name = self.setup["OutputBaseFilename"].replace("{#AppVersion}", "1.2.3") + ".exe"
        shipped = re.compile(r"Jobwatch-Setup-\d+(?:\.\d+){1,3}\.exe")    # updater.py up to 0.2.5
        self.assertTrue(shipped.fullmatch(name), name)
        self.assertTrue(updater.INSTALLER_NAME.fullmatch(name), name)

    def test_the_app_and_its_shortcuts_are_named_foothold(self):
        for key in ("AppName", "AppPublisher", "UninstallDisplayName"):
            self.assertEqual(self.setup[key], "Foothold", key)
        self.assertIn('Name: "{autoprograms}\\Foothold"', self.script)
        self.assertIn('Name: "{autoprograms}\\Jobwatch.lnk"', self.script.split("[InstallDelete]")[1])

    def test_icons_point_at_the_foothold_icon(self):
        icons = set(re.findall(r"\\app\\web\\([\w.]+\.ico)", self.script))
        self.assertEqual(icons, {"foothold.ico"})
        self.assertTrue((ROOT / "web/foothold.ico").is_file())

    def test_the_data_folder_is_unchanged(self):
        self.assertIn("{localappdata}\\Jobwatch", self.script)


if __name__ == "__main__":
    unittest.main()
