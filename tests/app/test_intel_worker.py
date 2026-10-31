"""The background worker process: facts, scoring and polls run in intel_worker.py, beside the server, and
report back to it; the server stays as it was to every page."""
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch

import dashboard
import intel_worker
from intel_worker import EVENT, Worker, WorkerProcess, parse_line
from tests.app import test_dashboard as fixtures


def wait_until(check, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return True
        time.sleep(0.05)
    return False


def intel_rows(db_path):
    """Every posting's facts and fit, as the boards read them (without when they were computed)."""
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = [{k: r[k] for k in r.keys() if k not in ("facts_at", "scored_at")}
            for r in con.execute("SELECT * FROM job_intel ORDER BY board, job_id")]
    con.close()
    return rows


def send_back_for_facts(db_path):
    con = sqlite3.connect(db_path)
    con.execute("UPDATE job_intel SET input_hash=NULL")
    con.commit()
    con.close()


def add_postings(db_path, start, count):
    """New postings with no facts yet, committed as a poll commits them."""
    con = sqlite3.connect(db_path, timeout=30)
    now = fixtures.watcher.now()
    con.executemany("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                    [("rbc", f"bulk{i}", f"Analyst {i}", "Toronto, ON", f"https://example.com/bulk{i}", now, now)
                     for i in range(start, start + count)])
    con.commit()
    con.close()


def assert_ranking_reports(test, reports, facts):
    """A pass's (done, total) reports: both only grow, and none reads all done while postings are left."""
    test.assertEqual((facts, facts), reports[-1])
    for (done, total), (next_done, next_total) in zip(reports, reports[1:]):
        test.assertLess(done, total)
        test.assertLessEqual(done, next_done)
        test.assertLessEqual(total, next_total)


class ProtocolTests(unittest.TestCase):
    def test_event_lines_and_log_lines_are_told_apart(self):
        self.assertEqual(("pending", {"n": 3}), parse_line(EVENT + json.dumps({"kind": "pending", "n": 3})))
        self.assertIsNone(parse_line("2026-10-28T12:00:00+00:00 ! rbc: HTTPError"))
        self.assertIsNone(parse_line(EVENT + "{not json"))        # never an event the server can't read

    def test_lines_from_two_threads_never_mix(self):
        out = io.StringIO()
        lines = intel_worker.WholeLines(out)
        start = threading.Barrier(2)

        def write(text):
            start.wait()
            for _ in range(200):
                print(text, file=lines)         # print writes the text and the newline separately

        threads = [threading.Thread(target=write, args=(t,)) for t in ("a" * 50, "b" * 50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual({"a" * 50, "b" * 50}, set(out.getvalue().splitlines()))


class WorkerTests(fixtures.ServiceFixture):
    """The worker's side, run here: what it does and reports."""

    def setUp(self):
        super().setUp()
        self.events = []
        self.worker = Worker(self.db_path, self.service.config,
                             emit=lambda kind, **data: self.events.append((kind, data)))

    def test_a_pass_builds_the_same_facts_and_fits_as_the_server_did(self):
        before = intel_rows(self.db_path)
        send_back_for_facts(self.db_path)
        self.worker.refresh()
        self.assertEqual(before, intel_rows(self.db_path))
        kinds = [kind for kind, _ in self.events]
        self.assertEqual("indexing", kinds[0])
        self.assertEqual(("pending", {"n": len(before), "total": len(before)}), self.events[1])   # counted first
        self.assertEqual("done", kinds[-1])
        self.assertEqual(len(before), self.events[-1][1]["stats"]["facts"])
        self.assertFalse(self.worker.indexing)

    def test_a_pass_that_takes_on_postings_a_poll_commits_reports_them(self):
        add_postings(self.db_path, 0, 600)
        reports = []

        def emit(kind, **data):
            self.events.append((kind, data))
            if kind == "pending":
                reports.append((data["total"] - data["n"], data["total"]))
                if len(reports) == 2:           # the first batch is in, and a poll commits more
                    add_postings(self.db_path, 600, 600)
        self.worker.emit = emit
        self.worker.refresh()
        self.assertEqual((0, 600), reports[0])
        self.assertEqual(1200, self.events[-1][1]["stats"]["facts"])
        assert_ranking_reports(self, reports, 1200)

    def test_a_pass_with_nothing_to_do_counts_once(self):
        with patch.object(intel_worker, "count_pending_facts", wraps=intel_worker.count_pending_facts) as count:
            stats = intel_worker.refresh_database(self.db_path, self.service.config, backlog=count,
                                                  on_remaining=lambda *_: None)
        self.assertEqual(0, stats["facts"])
        self.assertEqual(1, count.call_count)

    def test_a_failed_pass_is_reported(self):
        with patch.object(intel_worker, "refresh_database", side_effect=sqlite3.OperationalError("locked")):
            self.worker.refresh()
        self.assertEqual(("error", {"text": "OperationalError: locked"}), self.events[-1])
        self.assertFalse(self.worker.indexing)

    def test_commands_reach_the_worker_and_end_of_input_stops_it(self):
        stopped = []
        with patch.object(self.worker, "start_poll") as poll:
            self.worker.read_commands(io.StringIO("kick\npoll\nnonsense\n"), on_end=lambda: stopped.append(1))
        self.assertTrue(self.worker._wake.is_set())
        poll.assert_called_once()
        self.assertEqual([1], stopped)

    def test_a_poll_reports_its_progress_and_end(self):
        self.worker.config = {**self.worker.config, "boards": {}, "description_budget": 0,
                              "linkedin_description_budget": 0}       # nothing to fetch: no network
        with patch.object(fixtures.watcher, "SUBSCRIBERS", self.subscribers_path):
            self.worker.poll()
        progress = [data["event"] for kind, data in self.events if kind == "progress"]
        self.assertEqual("start", progress[0])
        self.assertIn("phase", progress)
        self.assertEqual(("poll_end", {"error": None}), self.events[-1])
        self.assertTrue(self.worker._wake.is_set())         # the new postings get ranked next


class ServerSideTests(fixtures.ServiceFixture):
    """What the server does with the worker's events: the state refresh_now and polls set before."""

    def test_events_set_what_refresh_now_set(self):
        with patch.object(self.service, "data_changed") as changed:
            self.service._worker_event("indexing", {"on": True})
            self.assertTrue(self.service.status["indexing"])
            self.service._worker_event("pending", {"n": 40})
            self.assertEqual(40, self.service.status_info()["pending"])
            self.service._worker_event("done", {"stats": {"facts": 40, "scored": 40, "seconds": 1.0}})
            changed.assert_called_once()
        status = self.service.status_info()
        self.assertFalse(status["indexing"])
        self.assertEqual({"facts": 40, "scored": 40, "seconds": 1.0}, status["last_stats"])
        self.assertIsNotNone(status["last_refresh"])
        self.assertIsNone(self.service._pending_cache)      # counted again when next asked

    def test_a_pass_with_nothing_new_leaves_the_pages_alone(self):
        with patch.object(self.service, "data_changed") as changed:
            self.service._worker_event("done", {"stats": {"facts": 0, "scored": 0, "seconds": 0.1}})
        changed.assert_not_called()

    def test_a_failed_pass_shows_in_status(self):
        self.service._worker_event("indexing", {"on": True})
        self.service._worker_event("error", {"text": "OperationalError: locked"})
        self.assertEqual("OperationalError: locked", self.service.status["error"])
        self.assertFalse(self.service.status["indexing"])

    def worker_that_takes_commands(self):
        sent = []
        worker = WorkerProcess([], on_event=None, on_exit=None, on_give_up=None)
        worker.send = lambda command: sent.append(command) or True
        self.service._worker = worker
        return sent

    def test_kicks_and_polls_go_to_the_worker(self):
        sent = self.worker_that_takes_commands()
        self.service.kick()
        self.assertFalse(self.service._wake.is_set())
        self.assertEqual({"ok": True, "started": True}, self.service.trigger_poll())
        self.assertEqual({"ok": True, "started": False, "message": "a poll is already running"},
                         self.service.trigger_poll())
        self.assertEqual(["kick", "poll"], sent)
        self.assertTrue(self.service.status["poll_running"])

    def test_a_poll_in_the_worker_shows_its_progress_and_end(self):
        self.worker_that_takes_commands()
        self.service.trigger_poll()
        self.service._worker_event("progress", {"event": "start", "data": {"sources": ["rbc"], "skipped": 2}})
        self.service._worker_event("progress", {"event": "source_finished",
                                                "data": {"board": "rbc", "outcome": "ok", "jobs": 5, "new": 1}})
        progress = self.service.status_info()["progress"]
        self.assertEqual((1, 5, 1, 2), (progress["completed"], progress["jobs"], progress["new"], progress["skipped"]))
        with patch.object(self.service, "data_changed") as changed:
            self.service._worker_event("poll_end", {"error": None})
        changed.assert_called_once()
        status = self.service.status_info()
        self.assertFalse(status["poll_running"])
        self.assertEqual("complete", status["progress"]["phase"])
        self.assertIsNotNone(status["last_poll"])
        self.assertTrue(self.service.trigger_poll()["started"])          # the next one may start

    def test_a_worker_that_stops_mid_poll_fails_the_poll_and_frees_it(self):
        self.worker_that_takes_commands()
        self.service._worker_event("indexing", {"on": True})
        self.service.trigger_poll()
        self.service._worker_exited(1)
        status = self.service.status_info()
        self.assertFalse(status["indexing"])
        self.assertFalse(status["poll_running"])
        self.assertEqual("failed", status["progress"]["phase"])
        self.assertIn("background process stopped", status["error"])
        self.assertTrue(self.service.trigger_poll()["started"])

    def test_without_the_worker_the_threads_in_the_server_do_the_work(self):
        with patch.object(intel_worker.subprocess, "Popen", side_effect=OSError("blocked")):
            self.service.start_background()
            self.assertTrue(wait_until(lambda: self.service._worker is None, 10))
        self.assertTrue(wait_until(lambda: any(t.name == "jobwatch-intel" for t in threading.enumerate()), 5))
        send_back_for_facts(self.db_path)
        self.service.kick()
        self.assertTrue(wait_until(lambda: (self.service.status["last_stats"] or {}).get("facts"), 30))
        self.service.stop_background()      # the kick may have started another pass: let it finish
        self.assertTrue(wait_until(lambda: not any(t.name == "jobwatch-intel" for t in threading.enumerate()), 30))


class WorkerProcessTests(fixtures.ServiceFixture):
    """The real worker process, started by the server."""

    def tearDown(self):
        self.service.stop_background()
        super().tearDown()

    def started(self):
        """Started, and its first pass reported."""
        self.service.status["last_refresh"] = None
        self.service.start_background()
        self.assertTrue(wait_until(lambda: self.service.status["last_refresh"] is not None))
        return self.service._worker

    def test_the_worker_ranks_postings_and_the_server_hears_it(self):
        before = intel_rows(self.db_path)
        send_back_for_facts(self.db_path)
        worker = self.started()
        self.assertTrue(worker.alive)
        self.assertNotIn("jobwatch-intel", [t.name for t in threading.enumerate()])
        self.assertEqual(len(before), self.service.status["last_stats"]["facts"])
        self.assertEqual(before, intel_rows(self.db_path))
        self.assertFalse(self.service.status["indexing"])

    def test_a_kick_starts_a_pass_at_once(self):
        self.started()
        send_back_for_facts(self.db_path)
        self.service.status["last_stats"] = None
        self.service.kick()
        self.assertTrue(wait_until(lambda: (self.service.status["last_stats"] or {}).get("facts")))

    def test_stopping_waits_for_the_worker_which_ends_by_itself(self):
        worker = self.started()
        process = worker._proc
        self.assertTrue(worker.stop())                 # ended on end of input, not killed
        self.assertIsNotNone(process.poll())

    def test_a_worker_that_dies_is_started_again(self):
        worker = self.started()
        worker.restart_delay = 0.1
        first = worker._proc
        first.kill()
        self.assertTrue(wait_until(lambda: worker._proc is not first and worker.alive))
        self.assertIs(worker, self.service._worker)

    def test_polls_run_in_the_worker(self):
        config = json.loads(self.config_path.read_text())
        self.config_path.write_text(json.dumps({**config, "boards": {}, "description_budget": 0,
                                                "linkedin_description_budget": 0}))   # no network
        self.started()
        self.assertTrue(self.service.trigger_poll()["started"])
        self.assertTrue(wait_until(lambda: not self.service.status["poll_running"]))
        status = self.service.status_info()
        self.assertEqual("complete", status["progress"]["phase"])
        self.assertIsNotNone(status["last_poll"])
        self.assertNotIn("jobwatch-poll", [t.name for t in threading.enumerate()])


class SupervisionTests(unittest.TestCase):
    def test_a_worker_that_keeps_dying_hands_the_work_back(self):
        exits, gave_up = [], threading.Event()
        worker = WorkerProcess([sys.executable, "-c", "raise SystemExit(3)"], on_event=None,
                               on_exit=exits.append, on_give_up=gave_up.set, restart_delay=0.01)
        worker.start()
        self.assertTrue(gave_up.wait(20))
        self.assertEqual([3, 3, 3], exits)
        self.assertFalse(worker.alive)

    @unittest.skipUnless(os.name == "nt", "Windows job objects; elsewhere the worker ends on end of input")
    def test_the_worker_ends_with_the_process_that_started_it(self):
        # The real interpreter, not a virtual environment's launcher, so the job holds the process itself.
        worker = WorkerProcess([getattr(sys, "_base_executable", sys.executable), "-c",
                                "import time; time.sleep(60)"], on_event=None, on_exit=None, on_give_up=None)
        worker.start()
        self.assertTrue(wait_until(lambda: worker.alive, 10))
        process = worker._proc
        worker._stopping.set()
        intel_worker.close_job(worker._job)          # what Windows does when the server's process ends
        worker._job = None
        self.assertTrue(wait_until(lambda: process.poll() is not None, 10))


if __name__ == "__main__":
    unittest.main()
