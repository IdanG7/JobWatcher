import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import dashboard
import portable_start
from dashboard import ApiError, JobwatchService


class BackgroundTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "config.json").write_text(json.dumps({"boards": {}}), encoding="utf-8")
        (root / "subscribers.json").write_text("{}", encoding="utf-8")
        self.service = JobwatchService(root / "jobwatch.db", root / "config.json", root / "subscribers.json")
        self.root = root

    def tearDown(self):
        self.tmp.cleanup()

    def test_dev_server_cannot_be_stopped_or_autostarted_remotely(self):
        from version import APP_VERSION
        self.assertEqual({"can_stop": False, "version": APP_VERSION, "updates": False, "installed": False,
                          "autostart_supported": False, "autostart": False, "log": ""},
                         self.service.background_info())
        with self.assertRaises(ApiError):
            self.service.shutdown()
        with self.assertRaises(ApiError):
            self.service.put_background({"autostart": True})

    def test_autostart_writes_the_launcher_command(self):
        self.service.autostart_command = '"C:\\J\\runtime\\pythonw.exe" "C:\\J\\app\\portable_start.py" --serve'
        stored = {}
        with mock.patch.object(dashboard, "set_autostart", side_effect=lambda c: stored.update(v=c)), \
                mock.patch.object(dashboard, "autostart_value", side_effect=lambda: stored.get("v")):
            self.assertTrue(self.service.put_background({"autostart": True})["autostart"])
            self.assertEqual(self.service.autostart_command, stored["v"])
            self.assertFalse(self.service.put_background({"autostart": False})["autostart"])
            self.assertIsNone(stored["v"])
            with self.assertRaises(ApiError):
                self.service.put_background({"autostart": "yes"})

    def test_background_identifies_installed_and_zip_copies(self):
        self.service.app_root = self.root
        self.assertFalse(self.service.background_info()["installed"])
        (self.root / "unins000.exe").write_bytes(b"uninstaller")
        self.assertTrue(self.service.background_info()["installed"])

    def test_shutdown_answers_before_stopping(self):
        stopped = threading.Event()
        self.service.on_shutdown = stopped.set
        self.assertEqual({"ok": True}, self.service.shutdown())
        self.assertTrue(stopped.wait(3))


class OutdatedResumeTests(BackgroundTests):
    def test_resume_from_older_parser_is_flagged(self):
        from tests.letters.test_cover_letters import RESUME
        self.service.apply_resume({"text": RESUME})
        self.assertFalse(self.service.get_resume()["outdated"])
        with self.service.db() as con:
            parsed = json.loads(con.execute("SELECT parsed FROM candidate_resume").fetchone()[0])
            parsed.pop("role_interests")
            con.execute("UPDATE candidate_resume SET parsed=?", (json.dumps(parsed),))
        self.assertTrue(self.service.get_resume()["outdated"])


class LauncherHelpersTests(unittest.TestCase):
    def test_version_key_orders_numerically(self):
        self.assertGreater(portable_start.version_key("0.1.10"), portable_start.version_key("v0.1.9"))

    def test_server_command_uses_windowless_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            runtime = Path(tmp)
            (runtime / "pythonw.exe").write_bytes(b"")
            with mock.patch.object(portable_start.sys, "executable", str(runtime / "python.exe")):
                command = portable_start.server_command(Path("D:/data"))
        self.assertTrue(command[0].endswith("pythonw.exe"))
        self.assertEqual(["--serve", "--data-dir"], command[2:4])

    def test_log_rolls_over(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "jobwatch.log"
            with mock.patch.object(portable_start, "LOG_LIMIT", 100):
                log = portable_start.RotatingLog(path)
                for _ in range(30):
                    print("a line of log output", file=log)
                log._file.close()
            self.assertTrue(path.with_suffix(".log.1").exists())
            self.assertLessEqual(path.stat().st_size, 130)


if __name__ == "__main__":
    unittest.main()
