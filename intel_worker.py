#!/usr/bin/env python3
"""The background worker: facts, scoring and polls, in a process of their own.

The dashboard's server starts it (JobwatchService.start_background), so this work never holds the
server's GIL while pages are asked for: with a facts pass running in the server, /api/status took
~110 ms and pages ~1.9x their idle time; beside it, in this process, 1.5 ms and 1.1x.

Commands arrive on stdin, one per line: ``kick`` (look for new work now) and ``poll``. End of input
means the server is gone or stopping, and the worker ends at once: its database work is in SQLite
transactions, which roll back cleanly. What it reports goes to stdout as events, lines that start with
EVENT; every other line (watcher.log, a traceback) is log text, which the server writes to its own log.
"""

from __future__ import annotations

import argparse
import ctypes
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

import watcher
from intel_store import IntelStore

EVENT = "\x1efoothold "     # starts every event line; log text never does


def parse_line(line: str):
    """(kind, data) for an event line; None for log text."""
    if not line.startswith(EVENT):
        return None
    try:
        data = json.loads(line[len(EVENT):])
        return data.pop("kind"), data
    except (ValueError, KeyError, AttributeError):
        return None


def count_pending_facts(con) -> int:
    """Postings whose facts or fit are still to be computed."""
    from intel import FACTS_VERSION, config_fingerprint
    return con.execute(
        """SELECT COUNT(*) FROM jobs j LEFT JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
           WHERE j.title != '' AND (i.board IS NULL OR i.input_hash IS NULL OR i.facts_version != ?
                                    OR i.kb_version != ? OR i.fit_detail IS NULL)""",
        (FACTS_VERSION, config_fingerprint())).fetchone()[0]


def refresh_database(db_path, config: dict, force_score: bool = False, backlog=count_pending_facts,
                     on_remaining=None) -> dict:
    """One facts and scoring pass on a connection of its own: what the worker runs, and the server's
    refresh_now() in its place. ``on_remaining(n)`` hears how many postings are left as batches land,
    from ``backlog(con)``, counted first."""
    con = sqlite3.connect(db_path, timeout=30)
    con.execute("PRAGMA busy_timeout=15000")
    con.execute("PRAGMA synchronous=NORMAL")   # WAL: safe, fewer disk flushes
    con.execute(f"PRAGMA mmap_size={watcher.MMAP_SIZE}")
    try:
        progress = None
        if on_remaining is not None:
            pending = backlog(con)
            progress = lambda done: on_remaining(max(0, pending - done))  # noqa: E731
        return IntelStore(con, config).refresh(force_score=force_score, on_progress=progress)
    finally:
        con.close()


# ------------------------------------------------------------ the worker process
class WholeLines(io.TextIOBase):
    """stdout for the worker: written a whole line at a time, so a log line and an event from two
    threads never mix on the pipe (print writes its text and the newline separately)."""

    def __init__(self, stream):
        self._stream = stream
        self._lock = threading.Lock()
        self._local = threading.local()

    def write(self, text):
        *lines, self._local.rest = (getattr(self._local, "rest", "") + text).split("\n")
        if lines:
            with self._lock:
                self._stream.write("".join(line + "\n" for line in lines))
                self._stream.flush()
        return len(text)

    def writable(self):
        return True


def emit(kind: str, **data) -> None:
    print(EVENT + json.dumps({"kind": kind, **data}, default=str), flush=True)


class Worker:
    """Today's background loop (a pass, then a kick or a minute) and polls, reporting as it goes."""

    def __init__(self, db_path, config: dict, interval: int = 60, emit=emit):
        self.db_path = db_path
        self.config = config
        self.interval = interval
        self.emit = emit
        self.indexing = False
        self._wake = threading.Event()
        self._poll_lock = threading.Lock()

    def kick(self) -> None:
        self._wake.set()

    def _backlog(self, con) -> int:
        n = count_pending_facts(con)
        self.emit("pending", n=n)
        return n

    def refresh(self) -> None:
        self.indexing = True
        self.emit("indexing", on=True)
        try:
            stats = refresh_database(self.db_path, self.config, backlog=self._backlog,
                                     on_remaining=lambda n: self.emit("pending", n=n))
        except Exception as exc:    # reported, and tried again on the next pass
            self.indexing = False
            self.emit("error", text=f"{type(exc).__name__}: {exc}")
        else:
            self.indexing = False
            self.emit("done", stats=stats)

    def _progress(self, event, **data):
        self.emit("progress", event=event, data=data)

    def poll(self) -> None:
        if not self._poll_lock.acquire(blocking=False):     # the server never asks twice; just in case
            return
        error = None
        try:
            con = watcher.db_open(self.db_path)
            try:
                watcher.cycle(self.config, con, progress=self._progress, ranking=lambda: self.indexing)
            finally:
                con.close()
        except Exception as exc:
            error = f"poll failed: {type(exc).__name__}: {exc}"
        finally:
            self._poll_lock.release()
            self.emit("poll_end", error=error)
            self.kick()

    def start_poll(self) -> None:
        threading.Thread(target=self.poll, name="jobwatch-poll", daemon=True).start()

    def read_commands(self, stream, on_end=lambda: os._exit(0)) -> None:
        for line in stream:
            command = line.strip()
            if command == "kick":
                self.kick()
            elif command == "poll":
                self.start_poll()
        on_end()

    def run(self) -> None:
        while True:
            self.refresh()
            self._wake.wait(self.interval)
            self._wake.clear()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Foothold's background worker (started by the server)")
    parser.add_argument("--db", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--subscribers", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--dashboard-url", default="")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args(argv)
    sys.stdout = sys.stderr = WholeLines(sys.__stdout__)
    watcher.DB_PATH = Path(args.db)
    watcher.CONFIG = Path(args.config)
    watcher.SUBSCRIBERS = Path(args.subscribers)
    watcher.STATE_JSON = Path(args.state)
    from intel.sources import load_config
    config = load_config(args.config)
    if args.dashboard_url:
        config["dashboard_url"] = args.dashboard_url      # alert links
    worker = Worker(watcher.DB_PATH, config, args.interval)
    threading.Thread(target=worker.read_commands, args=(sys.stdin,), name="worker-commands", daemon=True).start()
    worker.run()
    return 0


# ------------------------------------------------------------ the server's side
if os.name == "nt":
    from ctypes import wintypes
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    _kernel32.CreateJobObjectW.argtypes = [wintypes.LPVOID, wintypes.LPCWSTR]
    _kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    _kernel32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.POINTER(wintypes.FILETIME)] * 4
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    class _BasicLimits(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _BasicLimits), ("IoInfo", ctypes.c_uint64 * 6),
                    ("ProcessMemoryLimit", ctypes.c_size_t), ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t), ("PeakJobMemoryUsed", ctypes.c_size_t)]


def process_created(pid: int) -> int | None:
    """When a process started (Windows FILETIME): with its id, it names that one process, even after
    the id is reused."""
    if os.name != "nt":
        return None
    handle = _kernel32.OpenProcess(0x1000, False, pid)        # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        return None
    try:
        times = [wintypes.FILETIME() for _ in range(4)]
        if not _kernel32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            return None
        return times[0].dwHighDateTime << 32 | times[0].dwLowDateTime
    finally:
        _kernel32.CloseHandle(handle)


def tie_to_this_process(pid: int):
    """A job that ends the process when this one ends, however it ends (its handle closes with it).
    None where that isn't possible: the worker still ends on end of input."""
    if os.name != "nt":
        return None
    job = _kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    limits = _ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = 0x2000      # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    handle = _kernel32.OpenProcess(0x0101, False, pid)       # PROCESS_SET_QUOTA | PROCESS_TERMINATE
    try:
        if handle and _kernel32.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)) \
                and _kernel32.AssignProcessToJobObject(job, handle):
            return job
    finally:
        if handle:
            _kernel32.CloseHandle(handle)
    _kernel32.CloseHandle(job)
    return None


def close_job(job) -> None:
    if job:
        _kernel32.CloseHandle(job)


class WorkerProcess:
    """The worker as the server runs it: started, given commands, heard, started again if it stops,
    and stopped with the server. After three quick deaths in a row it gives up (``on_give_up``), and the
    server does the work in its own threads again."""

    def __init__(self, args: list[str], on_event, on_exit, on_give_up, pid_path: Path | None = None,
                 restart_delay: float = 2.0):
        self.args = args
        self.on_event, self.on_exit, self.on_give_up = on_event, on_exit, on_give_up
        self.pid_path = pid_path
        self.restart_delay = restart_delay
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._job = None
        self._send_lock = threading.Lock()
        self._life_lock = threading.Lock()      # no worker is started once stop() has begun
        self._stopping = threading.Event()

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> bool:
        """Start the worker, here, so the first poll already finds it; False if it can't be started."""
        with self._life_lock:
            try:
                self._spawn()
            except OSError as exc:
                watcher.log(f"! the background process could not start ({exc}); working in the server instead")
                return False
        self._thread = threading.Thread(target=self._supervise, name="jobwatch-worker", daemon=True)
        self._thread.start()
        return True

    def _spawn(self) -> None:
        self._proc = subprocess.Popen(
            self.args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        close_job(self._job)
        self._job = tie_to_this_process(self._proc.pid)
        if self.pid_path is not None:
            try:      # for --stop (Setup), which waits for this process too
                self.pid_path.write_text(f"{self._proc.pid} {process_created(self._proc.pid)}", encoding="utf-8")
            except OSError:
                pass

    def _read(self) -> None:
        for line in self._proc.stdout:
            line = line.rstrip("\r\n")
            event = parse_line(line)
            if event is None:
                try:      # the worker's log, into the server's; reading on matters more than one line
                    if line:
                        print(line, flush=True)
                except (AttributeError, OSError, ValueError):
                    pass
                continue
            try:
                self.on_event(*event)
            except Exception as exc:      # one bad event never stops the reports
                watcher.log(f"! background event {event[0]}: {type(exc).__name__}: {exc}")

    def _supervise(self) -> None:
        """Hear the worker until it ends; start it again unless it is being stopped."""
        delay, quick, started = self.restart_delay, 0, time.monotonic()
        while True:
            self._read()
            code = self._proc.wait()
            for pipe in (self._proc.stdin, self._proc.stdout):
                with self._send_lock:
                    pipe.close()
            if self._stopping.is_set():
                return
            lived = time.monotonic() - started
            quick = quick + 1 if lived < 60 else 0
            delay = self.restart_delay if lived > 600 else delay
            self.on_exit(code)
            if quick >= 3:
                watcher.log(f"! the background process keeps stopping (exit code {code}); working in the server instead")
                self.on_give_up()
                return
            watcher.log(f"! the background process stopped (exit code {code}); starting it again in {delay:g} s")
            if self._stopping.wait(delay):
                return
            delay = min(delay * 2, 60)
            started = time.monotonic()
            with self._life_lock:
                if self._stopping.is_set():
                    return
                try:
                    self._spawn()
                    error = None
                except OSError as exc:
                    error = exc
            if error is not None:
                watcher.log(f"! the background process could not start ({error}); working in the server instead")
                self.on_give_up()
                return

    def send(self, command: str) -> bool:
        """False when the worker isn't there to hear it (stopped, or being started again)."""
        with self._send_lock:
            if not self.alive or self._stopping.is_set():
                return False
            try:
                self._proc.stdin.write(command + "\n")
                self._proc.stdin.flush()
                return True
            except (OSError, ValueError):
                return False

    def stop(self, timeout: float = 3.0) -> bool:
        """End the worker and wait until it has: True if it ended by itself on end of input."""
        with self._life_lock:
            self._stopping.set()
            proc = self._proc
        if proc is None:
            return True
        with self._send_lock:
            try:
                proc.stdin.close()
            except OSError:
                pass
        try:
            proc.wait(timeout)
            ended = True
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            ended = False
        if self._thread is not threading.current_thread():
            self._thread.join(5)          # it has heard the last of the worker
        close_job(self._job)
        self._job = None
        if self.pid_path is not None:
            try:
                self.pid_path.unlink(missing_ok=True)
            except OSError:
                pass
        return ended


if __name__ == "__main__":
    raise SystemExit(main())
