"""Windows portable entry point; all recipient data lives outside the app."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
from urllib.parse import urlparse
import webbrowser


def initialize_data(app: Path, data: Path) -> None:
    data.mkdir(parents=True, exist_ok=True)
    for name in ("config.json", "subscribers.json"):
        destination = data / name
        if not destination.exists():
            # Exclusive creation also protects edits if two starts overlap.
            with destination.open("xb") as output:
                output.write((app / name).read_bytes())


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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Start the portable Jobwatch dashboard")
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Jobwatch")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--no-poll", action="store_true", help="offline diagnostics only")
    args = parser.parse_args(argv)
    if os.name != "nt":
        parser.error("This package runs on Windows 10/11 (64-bit).")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    app = Path(__file__).resolve().parent
    data = args.data_dir.resolve()
    data.mkdir(parents=True, exist_ok=True)
    lock = acquire_lock(data / "running.lock")
    state = data / "instance.json"
    if lock is None:
        for _ in range(20):
            url = instance_url(state)
            if url:
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
        from dashboard import JobwatchHandler, JobwatchService
        from http.server import ThreadingHTTPServer

        watcher.CONFIG = data / "config.json"
        watcher.SUBSCRIBERS = data / "subscribers.json"
        watcher.DB_PATH = data / "jobwatch.db"
        watcher.STATE_JSON = data / "state.json"
        service = JobwatchService(watcher.DB_PATH, watcher.CONFIG, watcher.SUBSCRIBERS)
        handler = type("PortableHandler", (JobwatchHandler,), {"service": service})
        # A free loopback port avoids conflicts with other apps or installations.
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        url = f"http://127.0.0.1:{server.server_port}"
        service.config["dashboard_url"] = url
        temporary = state.with_suffix(".tmp")
        temporary.write_text(json.dumps({"url": url, "pid": os.getpid()}), encoding="utf-8")
        temporary.replace(state)
        print(f"\nJobwatch is ready: {url}", flush=True)
        print(f"Your private data: {data}", flush=True)
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
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nJobwatch stopped.")
        finally:
            service._stop.set()
            service._wake.set()
            server.server_close()
            state.unlink(missing_ok=True)
    finally:
        lock.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Jobwatch could not start: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
