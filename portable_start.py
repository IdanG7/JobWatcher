"""Windows entry point; all recipient data lives outside the app.

The Start menu shortcut (pythonw.exe, no window) or Start Jobwatch.bat runs
this as a short-lived launcher: it starts the server as a windowless
pythonw.exe process (or finds the one already running), opens the browser and
exits. ``--console`` keeps the old run-in-this-window behaviour for
troubleshooting; ``--stop`` stops a running copy (the installer uses it).
"""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import webbrowser
from version import APP_VERSION

LOG_LIMIT = 5_000_000
MISSING = "__missing__"     # tools/source_history.py: a key a release did not ship


def upgrade_sources(app: Path, data: Path) -> None:
    """Upgrade unchanged public defaults while preserving recipient edits."""
    bundled = json.loads((app / "config.json").read_text(encoding="utf-8"))
    destination = data / "config.json"
    existing = json.loads(destination.read_text(encoding="utf-8"))
    version = bundled.get("sources_version", 0)
    if existing.get("sources_version", 0) >= version:
        return
    # Every value any release shipped (board -> key -> values; MISSING = key absent).
    # A setting still equal to one of them was never edited, so it takes the new default.
    history_file = app / "config/source_defaults_history.json"
    if history_file.exists():
        history = json.loads(history_file.read_text(encoding="utf-8"))
    else:
        baseline = json.loads((app / "config/source_defaults_v1.json").read_text(encoding="utf-8"))["boards"]
        history = {name: {k: [v] for k, v in board.items()} for name, board in baseline.items()}
        history["__since__"] = {name: 1 for name in baseline}
    boards = existing.setdefault("boards", {})
    since = history.get("__since__", {})
    installed = existing.get("sources_version", 1)     # configs before versioning held the v1 sources
    identity = {"ats", "tenant", "site", "host", "domain", "token", "repo", "url"}

    def shipped(known: dict, key: str, current: dict) -> bool:
        value = current.get(key, MISSING)
        return value in known.get(key, [MISSING])

    for name, new in bundled.get("boards", {}).items():
        if name not in boards:
            # A source newer than this config is added; one it already had was deleted by the recipient.
            if name not in history or since.get(name, installed + 1) > installed:
                boards[name] = new
            continue
        current, known = boards[name], history.get(name)
        if not isinstance(current, dict) or known is None:
            continue
        if not all(shipped(known, k, current) or current.get(k) == new.get(k) for k in identity):
            continue                        # the recipient pointed this source elsewhere
        for key in known.keys() | new.keys():
            if shipped(known, key, current):
                if key in new:
                    current[key] = new[key]
                else:
                    current.pop(key, None)
    existing["sources_version"] = version
    temporary = destination.with_suffix(".upgrade.tmp")
    temporary.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def initialize_data(app: Path, data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "subscribers.json"):
        destination = data / name
        if not destination.exists():
            # Exclusive creation also protects edits if two starts overlap.
            with destination.open("xb") as output:
                output.write((app / name).read_bytes())
    upgrade_sources(app, data)


def instance_url(path: Path) -> str | None:
    try:
        url = json.loads(path.read_text(encoding="utf-8"))["url"]
        parsed = urlparse(url)
        if (parsed.scheme == "http" and parsed.hostname == "127.0.0.1"
                and parsed.port and not parsed.username and not parsed.password
                and parsed.path in ("", "/") and not parsed.query and not parsed.fragment):
            return url
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def acquire_lock(path: Path):
    import msvcrt
    handle = path.open("a+b")
    if path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        return None
    return handle  # Windows releases the lock on close or process termination.


class RotatingLog(io.TextIOBase):
    """stdout/stderr for the windowless server: jobwatch.log, rolled over at 5 MB."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._file = self._open()

    def _open(self):
        try:
            if self.path.exists() and self.path.stat().st_size > LOG_LIMIT:
                self.path.replace(self.path.with_suffix(".log.1"))
        except OSError:
            pass      # another process has the log open: keep appending, roll over later
        return self.path.open("a", encoding="utf-8", errors="replace")

    def write(self, text):
        # Logging must never take the server down: a failed write or rollover is dropped.
        with self._lock:
            try:
                self._file.write(text)
                self._file.flush()
                if self._file.tell() > LOG_LIMIT:
                    self._file.close()
                    self._file = self._open()
            except (OSError, ValueError):
                try:
                    self._file = self._open()
                except OSError:
                    pass
        return len(text)

    def writable(self):
        return True


def version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in str(version).lstrip("v").split(".") if p.isdigit())


def server_command(data: Path) -> list[str]:
    """The windowless server: pythonw.exe beside this runtime's python.exe."""
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return [str(pythonw if pythonw.exists() else Path(sys.executable)),
            str(Path(__file__).resolve()), "--serve", "--data-dir", str(data)]


def should_repoint_autostart(current: str | None, command: str, data: Path) -> bool:
    """Move the sign-in start to this copy only when it already starts Jobwatch
    for this same data folder (a test copy or second data folder never takes it).
    JOBWATCH_NO_AUTOSTART=1 (the bundle verifier) leaves it alone."""
    if not current or current == command or "portable_start.py" not in current:
        return False
    if os.environ.get("JOBWATCH_NO_AUTOSTART"):
        return False
    found = re.search(r'--data-dir\s+(?:"([^"]+)"|(\S+))', current)
    if not found:
        return False
    try:
        return Path(found.group(1) or found.group(2)).resolve() == data.resolve()
    except OSError:
        return False


def stop_running(url: str) -> bool:
    """Ask a running copy (v0.1.11 or newer) to shut down."""
    request = Request(url + "/api/shutdown", data=b"{}", method="POST",
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return response.status == 200
    except OSError:
        return False


def wait_for_exit(pid: int, seconds: float) -> bool:
    """Wait for a stopped server's process to end (its files stay in use until it
    does); one still alive after ``seconds`` is ended. Only Python processes are
    touched, so a reused process id never ends an unrelated program."""
    import ctypes
    from ctypes import wintypes
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    synchronize, terminate, query = 0x00100000, 0x0001, 0x1000
    handle = kernel32.OpenProcess(synchronize | terminate | query, False, pid)
    if not handle:
        return True           # already gone
    try:
        if kernel32.WaitForSingleObject(handle, int(seconds * 1000)) == 0:
            return True
        size = wintypes.DWORD(1024)
        name = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, name, ctypes.byref(size)):
            return False
        if Path(name.value).name.lower() not in ("pythonw.exe", "python.exe"):
            return False
        kernel32.TerminateProcess(handle, 1)
        return kernel32.WaitForSingleObject(handle, 5000) == 0
    finally:
        kernel32.CloseHandle(handle)


def stop_and_wait(data: Path, seconds: float = 30) -> bool:
    """Stop the copy serving this data folder and wait until its process has exited."""
    state = data / "instance.json"
    url = instance_url(state)
    pid = None
    if url:
        try:
            pid = int(json.loads(state.read_text(encoding="utf-8")).get("pid"))
        except (OSError, ValueError, TypeError):
            pass
        if not stop_running(url):
            pid = None        # nothing answered: the recorded process id may be stale
    deadline = time.monotonic() + seconds
    while True:
        lock = acquire_lock(data / "running.lock")
        if lock is not None:
            lock.close()
            break
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)
    return wait_for_exit(pid, max(5.0, deadline - time.monotonic())) if pid else True


def preferred_port(data: Path) -> int:
    """The port used last time, so open tabs and bookmarks survive a restart or update."""
    try:
        port = int((data / "port").read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return 0
    return port if 1024 <= port <= 65535 else 0


def bind_server(server_class, handler, data: Path):
    """Listen on the remembered port, or any free one if another program has it."""
    port = preferred_port(data)
    if port:
        try:
            return server_class(("127.0.0.1", port), handler)
        except OSError:
            pass
    server = server_class(("127.0.0.1", 0), handler)
    try:
        (data / "port").write_text(str(server.server_port), encoding="utf-8")
    except OSError:
        pass
    return server


def show_error(text: str) -> None:
    """No console under pythonw.exe: a startup problem is shown in a message box."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text[-1800:], "Jobwatch", 0x10)    # MB_ICONERROR
    except (ImportError, AttributeError, OSError):
        pass


def log_tail(path: Path, lines: int = 15) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError:
        return ""


def responds(url: str, wait: float = 0.0) -> bool:
    """The server answers /api/status (retrying for up to ``wait`` seconds)."""
    deadline = time.monotonic() + wait
    while True:
        try:
            with urlopen(url + "/api/status", timeout=3):
                return True
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                return False
        time.sleep(0.3)


def wait_for_running(args, data: Path, seconds: float = 90) -> int:
    """Another start is under way: wait for its server instead of racing it."""
    state = data / "instance.json"
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        url = instance_url(state)
        if url and responds(url):
            print(f"Jobwatch is running: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        time.sleep(0.2)
    print(f"Jobwatch is taking long to start; see {data / 'jobwatch.log'}", flush=True)
    return 1


def launch(args, data: Path) -> int:
    """Start the hidden server (or find the running one), open the browser, exit."""
    # Double-clicking Start runs two launchers: only one may start a server.
    launching = acquire_lock(data / "launching.lock")
    if launching is None:
        return wait_for_running(args, data)
    try:
        return _launch(args, data)
    finally:
        launching.close()


def _launch(args, data: Path) -> int:
    state = data / "instance.json"
    lock = acquire_lock(data / "running.lock")
    if lock is None:
        for _ in range(50):
            url = instance_url(state)
            if url:
                break
            time.sleep(0.1)
        else:
            print("Jobwatch is still starting. Please wait a moment and try again.", flush=True)
            return 0
        running = json.loads(state.read_text(encoding="utf-8")).get("version", "0")
        if version_key(running) >= version_key(APP_VERSION):
            # The lock says a server process exists; make sure it actually answers.
            if not responds(url, wait=10):
                print(f"Jobwatch is running but not responding at {url}.", flush=True)
                print(f"See {data / 'jobwatch.log'}; restarting Windows stops it.", flush=True)
                return 1
            print(f"Jobwatch is already running: {url}", flush=True)
            if not args.no_browser:
                webbrowser.open(url)
            return 0
        print(f"Replacing the older Jobwatch {running} that is running...", flush=True)
        if stop_running(url):
            for _ in range(150):
                lock = acquire_lock(data / "running.lock")
                if lock:
                    break
                time.sleep(0.1)
        if lock is None:
            print(f"An older Jobwatch copy is still running: {url}", flush=True)
            print("Close its console window, then start this updated copy again.", flush=True)
            return 1
    lock.close()          # the server takes the lock itself
    state.unlink(missing_ok=True)
    command = server_command(data) + (["--no-poll"] if args.no_poll else [])
    flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    quiet = {"cwd": str(data), "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
             "stderr": subprocess.DEVNULL, "close_fds": True}
    try:      # leave the console's job object so closing the window never stops Jobwatch
        child = subprocess.Popen(command, creationflags=flags | subprocess.CREATE_BREAKAWAY_FROM_JOB, **quiet)
    except OSError:
        child = subprocess.Popen(command, creationflags=flags, **quiet)
    print("Starting Jobwatch in the background...", flush=True)
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if child.poll() is not None:
            if child.returncode == 0:      # another server (e.g. the sign-in start) took the lock first
                return wait_for_running(args, data)
            print("Jobwatch could not start:", flush=True)
            print(log_tail(data / "jobwatch.log") or f"(exit code {child.returncode})", flush=True)
            return 1
        url = instance_url(state)
        try:
            if url and json.loads(state.read_text(encoding="utf-8")).get("pid") == child.pid:
                with urlopen(url + "/api/status", timeout=2):
                    break
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    else:
        print(f"Jobwatch is taking long to start; see {data / 'jobwatch.log'}", flush=True)
        return 1
    print(f"\nJobwatch is running in the background: {url}", flush=True)
    print("This window closes by itself; Jobwatch keeps running without a window.", flush=True)
    print("Open Start Jobwatch.bat again any time to reopen the dashboard.", flush=True)
    print("To stop it, or to start it when you sign in to Windows: Settings > Background.\n", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Start the portable Jobwatch dashboard")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jobwatch")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-poll", action="store_true", help="offline diagnostics only")
    parser.add_argument("--console", action="store_true", help="run in this window instead of the background")
    parser.add_argument("--stop", action="store_true", help="stop the running copy and wait for it to exit")
    parser.add_argument("--serve", action="store_true", help=argparse.SUPPRESS)   # the hidden server itself
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("This package runs on Windows 10/11 (64-bit).")
    data = args.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    if args.stop:
        return 0 if stop_and_wait(data) else 1
    lock = None
    if args.serve:
        # Lock first: a second server (e.g. the sign-in start while one runs) exits
        # without touching the log, so it can never block the log's rollover.
        lock = acquire_lock(data / "running.lock")
        if lock is None:
            return 0
        sys.stdout = sys.stderr = RotatingLog(data / "jobwatch.log")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if not (args.serve or args.console):
        return launch(args, data)
    app = Path(__file__).resolve().parent
    lock = lock or acquire_lock(data / "running.lock")
    state = data / "instance.json"
    if lock is None:
        for _ in range(20):
            url = instance_url(state)
            if url:
                running = json.loads(state.read_text(encoding="utf-8"))
                if running.get("version") != APP_VERSION:
                    print(f"An older Jobwatch copy is still running: {url}", flush=True)
                    print("Stop it in Settings > Background, then start this updated copy again.", flush=True)
                    return 1
                print(f"Jobwatch is already running: {url}", flush=True)
                if not args.no_browser:
                    webbrowser.open(url)
                return 0
            time.sleep(0.1)
        print("Jobwatch is starting in another window. Please wait a moment.")
        return 0
    try:
        initialize_data(app, data)
        # Imported after paths are ready. Never use the developer's local DB.
        import watcher
        from dashboard import JobwatchHandler, JobwatchService, JobwatchHTTPServer, autostart_value, set_autostart

        watcher.CONFIG = data / "config.json"
        watcher.SUBSCRIBERS = data / "subscribers.json"
        watcher.DB_PATH = data / "jobwatch.db"
        watcher.STATE_JSON = data / "state.json"
        service = JobwatchService(watcher.DB_PATH, watcher.CONFIG, watcher.SUBSCRIBERS)
        handler = type("PortableHandler", (JobwatchHandler,), {"service": service})
        # The last port again (a free one if taken): conflicts with other apps are avoided
        # and open tabs reconnect after a restart or update.
        server = bind_server(JobwatchHTTPServer, handler, data)
        url = f"http://127.0.0.1:{server.server_port}"
        service.config["dashboard_url"] = url
        service.on_shutdown = server.shutdown
        service.autostart_command = subprocess.list2cmdline(server_command(data))
        service.log_path = data / "jobwatch.log" if args.serve else None
        current = autostart_value()
        if args.serve and should_repoint_autostart(current, service.autostart_command, data):
            try:      # the sign-in start follows the newest copy opened for the same data
                set_autostart(service.autostart_command)
            except Exception as exc:
                print(f"Could not update the sign-in start: {exc}", flush=True)
        temporary = state.with_suffix(".tmp")
        temporary.write_text(json.dumps({"url": url, "pid": os.getpid(), "version": APP_VERSION}), encoding="utf-8")
        temporary.replace(state)
        print(f"\nJobwatch is ready: {url}", flush=True)
        print(f"Version: {APP_VERSION}", flush=True)
        print(f"Your private data: {data}", flush=True)
        if args.console:
            print("Keep this window open. Close it or press Ctrl+C to stop Jobwatch.", flush=True)
            print("Open Settings to choose your targets and upload your own resume.\n", flush=True)
        service.start_background()
        if not args.no_poll:
            def poll():
                while not service._stop.is_set():
                    service.trigger_poll()
                    if service._stop.wait(max(60, service.config.get("interval_seconds", 300))):
                        break
            threading.Thread(target=poll, name="jobwatch-auto-poll", daemon=True).start()
            print("Fetching jobs in the background; the first fetch can take several minutes.", flush=True)
        if args.console and not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            print("\nJobwatch stopped.", flush=True)
            service._stop.set()
            service._wake.set()
            server.server_close()
            state.unlink(missing_ok=True)
    finally:
        lock.close()
    return 0


def run(argv=None) -> int:
    """main(), but under pythonw.exe (no console) failures are shown in a message box."""
    windowless = sys.stdout is None and "--serve" not in (argv or sys.argv[1:])
    if windowless:
        sys.stdout = sys.stderr = captured = io.StringIO()
    try:
        code = main(argv)
    except SystemExit as exc:          # argparse errors
        code = exc.code if isinstance(exc.code, int) else 1
    except Exception as exc:
        print(f"Jobwatch could not start: {type(exc).__name__}: {exc}", file=sys.stderr)
        code = 1
    if windowless and code:
        show_error(captured.getvalue().strip() or "Jobwatch could not start.")
    return code


if __name__ == "__main__":
    raise SystemExit(run())
