from contextlib import closing
import sqlite3
import threading
import time
from unittest.mock import patch

import watcher
from test_dashboard import ServiceFixture


class PollProgressTests(ServiceFixture):
    def test_status_is_available_without_database_access(self):
        with patch.object(self.service, "connect", side_effect=AssertionError("status must not wait for SQLite")):
            self.assertFalse(self.service.status_info()["poll_running"])

    def test_live_progress_failure_and_duplicate_poll(self):
        entered, release = threading.Event(), threading.Event()

        def cycle(config, con, progress=None):
            progress("start", sources=["rbc", "demo_quant"], skipped=1)
            progress("source_started", board="rbc")
            progress("source_finished", board="rbc", outcome="ok", jobs=12, new=4)
            progress("source_started", board="demo_quant")
            entered.set()
            release.wait(5)
            progress("source_finished", board="demo_quant", outcome="failed", error="Timeout")
            progress("phase", phase="indexing")

        with patch.object(watcher, "cycle", side_effect=cycle):
            try:
                self.assertTrue(self.service.trigger_poll()["started"])
                self.assertTrue(entered.wait(2))
                self.assertFalse(self.service.trigger_poll()["started"])
                status = self.service.status_info()
                self.assertTrue(status["poll_running"])
                progress = status["progress"]
                self.assertEqual((2, 1, 12, 4), (progress["total"], progress["completed"], progress["jobs"], progress["new"]))
                self.assertEqual("running", progress["sources"]["demo_quant"]["state"])
                # Returned snapshots must not expose mutable state to callers.
                progress["sources"]["rbc"]["state"] = "corrupted"
                self.assertEqual("ok", self.service.status_info()["progress"]["sources"]["rbc"]["state"])
            finally:
                release.set()
                self.assertTrue(self.service._poll_lock.acquire(timeout=5))
                self.service._poll_lock.release()
        status = self.service.status_info()
        self.assertFalse(status["poll_running"])
        self.assertEqual("complete", status["progress"]["phase"])
        self.assertEqual(1, status["progress"]["failed"])
        self.assertEqual("Timeout", status["progress"]["sources"]["demo_quant"]["error"])

    def test_cycle_reports_source_outcomes_and_skips(self):
        events = []
        self.service.config["description_budget"] = 0
        self.service.config["boards"]["linkedin_ca"]["min_interval"] = 3600
        with self.service.db() as con:
            con.execute("INSERT OR REPLACE INTO boards(board, seeded, last_ok, failures, last_poll) VALUES (?,?,?,?,?)",
                        ("linkedin_ca", 1, watcher.now(), 0, time.time()))

        def fetch(name, cfg):
            if name == "demo_quant":
                raise TimeoutError("fixture timeout")
            return name, [{"id": "new", "title": "Investment Banking Analyst", "location": "Toronto", "url": "https://example.com/new"}]

        with patch.object(watcher, "fetch_board", side_effect=fetch), patch.object(watcher, "load_subscribers", return_value=[]):
            con = watcher.db_open(self.db_path)
            try:
                watcher.cycle(self.service.config, con, progress=lambda event, **data: events.append((event, data)))
            finally:
                con.close()
        start = next(data for event, data in events if event == "start")
        self.assertEqual(1, start["skipped"])
        finished = {data["board"]: data for event, data in events if event == "source_finished"}
        self.assertEqual("ok", finished["rbc"]["outcome"])
        self.assertEqual("failed", finished["demo_quant"]["outcome"])
        self.assertTrue(any(event == "phase" and data["phase"] == "indexing" for event, data in events))

    def test_new_source_is_added_after_a_concurrent_commit(self):
        # Workday date repair has nothing to clear here. It must not leave a
        # deferred transaction open: the source scan would then pin a read
        # snapshot, and adding a source row after the background refresh
        # commits fails at once with "database is locked", ignoring busy_timeout.
        self.service.config["boards"]["demo_workday"] = {"ats": "workday"}
        self.service.config["description_budget"] = 0
        real_backoff = watcher.failure_backoff
        refreshed = []

        def backoff(failures):
            if not refreshed:   # the background refresh commits mid-scan
                with closing(sqlite3.connect(self.db_path)) as other:
                    other.execute("INSERT OR REPLACE INTO kv VALUES ('refresh_probe', 'done')")
                    other.commit()
                refreshed.append(True)
            return real_backoff(failures)

        def fetch(name, cfg):
            raise TimeoutError("offline fixture")

        with patch.object(watcher, "failure_backoff", side_effect=backoff), \
                patch.object(watcher, "fetch_board", side_effect=fetch), \
                patch.object(watcher, "load_subscribers", return_value=[]):
            con = watcher.db_open(self.db_path)
            try:
                watcher.cycle(self.service.config, con)
            finally:
                con.close()
        self.assertTrue(refreshed)
        with self.service.db() as con:
            added = {r[0] for r in con.execute("SELECT board FROM boards")}
        self.assertLessEqual({"demo_quant", "linkedin_ca", "demo_workday"}, added)

    def test_fatal_poll_error_remains_visible(self):
        with patch.object(watcher, "cycle", side_effect=RuntimeError("fixture error")):
            self.service.trigger_poll()
            self.assertTrue(self.service._poll_lock.acquire(timeout=5))
            self.service._poll_lock.release()
        status = self.service.status_info()
        self.assertFalse(status["poll_running"])
        self.assertEqual("failed", status["progress"]["phase"])
        self.assertIn("fixture error", status["error"])
        self.service.refresh_now()
        status = self.service.status_info()
        self.assertIsNone(status["error"])
        self.assertIn("fixture error", status["progress"]["error"])

    def test_overview_carries_its_saved_fit_threshold_without_boot_profile(self):
        profile = self.service.get_profile()["profile"]
        profile["alerts"]["high_fit"] = 90
        self.service.put_profile({"profile": profile})
        self.assertEqual(90, self.service.overview()["profile"]["alerts"]["high_fit"])
