"""How far background work is, as /api/status reports it: a poll's sources and a ranking pass's postings,
done of total, so the bars fill instead of sitting gray."""
from contextlib import closing
import sqlite3
import threading
import time
from unittest.mock import patch

from intel_worker import WorkerProcess
from tests.app.test_dashboard import ServiceFixture
from tests.app.test_intel_worker import add_postings, assert_ranking_reports, send_back_for_facts


class RankingProgressTests(ServiceFixture):
    def test_a_pass_in_the_worker_reports_done_of_its_backlog(self):
        self.service._worker_event("indexing", {"on": True})
        self.assertIsNone(self.service.status_info()["ranking"])        # not counted yet: the bar slides
        self.service._worker_event("pending", {"n": 4800})               # the backlog, counted first
        self.assertEqual({"total": 4800, "done": 0}, self.service.status_info()["ranking"])
        self.service._worker_event("pending", {"n": 3600})
        status = self.service.status_info()
        self.assertEqual({"total": 4800, "done": 1200}, status["ranking"])
        self.assertEqual(3600, status["pending"])
        status["ranking"]["done"] = 0                                    # a snapshot, not the live state
        self.assertEqual(1200, self.service.status_info()["ranking"]["done"])
        with patch.object(self.service, "data_changed"):
            self.service._worker_event("done", {"stats": {"facts": 4800, "scored": 4800, "seconds": 9.0}})
        self.assertIsNone(self.service.status_info()["ranking"])

    def test_the_next_pass_counts_from_its_own_backlog(self):
        with patch.object(self.service, "data_changed"):
            for events in ([4800, 0], [84]):
                self.service._worker_event("indexing", {"on": True})
                for n in events:
                    self.service._worker_event("pending", {"n": n})
                if events == [4800, 0]:
                    self.assertEqual({"total": 4800, "done": 4800}, self.service.status_info()["ranking"])
                    self.service._worker_event("done", {"stats": {"facts": 4800, "scored": 4800, "seconds": 9.0}})
        self.assertEqual({"total": 84, "done": 0}, self.service.status_info()["ranking"])

    def test_the_worker_s_total_grows_with_postings_its_pass_takes_on(self):
        self.service._worker_event("indexing", {"on": True})
        for n, total in ((600, 600), (100, 600), (200, 1200)):
            self.service._worker_event("pending", {"n": n, "total": total})
        status = self.service.status_info()
        self.assertEqual({"total": 1200, "done": 1000}, status["ranking"])
        self.assertEqual(200, status["pending"])

    def test_a_failed_or_stopped_pass_leaves_no_bar(self):
        self.service._worker_event("indexing", {"on": True})
        self.service._worker_event("pending", {"n": 50})
        self.service._worker_event("error", {"text": "OperationalError: locked"})
        self.assertIsNone(self.service.status_info()["ranking"])
        self.service._worker_event("indexing", {"on": True})
        self.service._worker_event("pending", {"n": 50})
        self.service._worker_exited(1)
        self.assertIsNone(self.service.status_info()["ranking"])

    def test_a_pass_here_counts_its_backlog_then_each_batch(self):
        send_back_for_facts(self.db_path)
        self.service._pending_cache = None
        seen = []
        record = self.service._ranking_left

        def spy(*args):
            record(*args)
            seen.append(self.service.status_info()["ranking"])
        with patch.object(self.service, "_ranking_left", side_effect=spy):
            stats = self.service.refresh_now()
        total = stats["facts"]
        self.assertGreater(total, 0)
        self.assertEqual({"total": total, "done": 0}, seen[0])           # before any batch lands
        self.assertEqual({"total": total, "done": total}, seen[-1])
        self.assertIsNone(self.service.status_info()["ranking"])

    def test_a_pass_here_reports_postings_a_poll_commits_while_it_runs(self):
        add_postings(self.db_path, 0, 600)
        self.service._pending_cache = None
        seen = []
        record = self.service._ranking_left

        def spy(*args):
            record(*args)
            ranking = self.service.status_info()["ranking"]
            seen.append((ranking["done"], ranking["total"]))
            if len(seen) == 2:                  # the first batch is in, and a poll commits more
                add_postings(self.db_path, 600, 600)
        with patch.object(self.service, "_ranking_left", side_effect=spy):
            stats = self.service.refresh_now()
        self.assertEqual((0, 600), seen[0])
        self.assertEqual(1200, stats["facts"])
        assert_ranking_reports(self, seen, 1200)       # counted again, not from the backlog cached for status

    def test_a_first_scan_reports_collecting_and_ranking_together(self):
        worker = WorkerProcess([], on_event=None, on_exit=None, on_give_up=None)
        worker.send = lambda command: True
        self.service._worker = worker
        self.service.trigger_poll()
        self.service._worker_event("progress", {"event": "start", "data": {"sources": ["rbc", "td", "bmo"], "skipped": 0}})
        self.service._worker_event("progress", {"event": "source_finished",
                                                "data": {"board": "rbc", "outcome": "ok", "jobs": 120, "new": 0}})
        self.service._worker_event("indexing", {"on": True})    # kicked by the finished source
        self.service._worker_event("pending", {"n": 120})
        self.service._worker_event("pending", {"n": 20})
        status = self.service.status_info()
        self.assertTrue(status["poll_running"])
        self.assertEqual(("fetching", 1, 3), (status["progress"]["phase"], status["progress"]["completed"],
                                              status["progress"]["total"]))
        self.assertEqual({"total": 120, "done": 100}, status["ranking"])


class FirstScanListTests(ServiceFixture):
    search = {"q": ["zzzz no such role"]}

    def finished_poll(self):
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("INSERT INTO runs VALUES ('2026-10-30T09:00:00+00:00', '2026-10-30T09:04:00+00:00', 3, 0, 0, 120, 0, 0, 240.0)")
            con.commit()

    def taken_on(self, sources):
        """As a poll does as it starts: a row for each source it polls."""
        with closing(sqlite3.connect(self.db_path)) as con:
            con.executemany("INSERT OR IGNORE INTO boards(board) VALUES (?)", [(source,) for source in sources])
            con.commit()

    def pick_rbc(self):
        """Every source polled once, then setup or Settings picks the board rbc is in: a save, with rbc untried."""
        with self.service.db() as con:
            self.taken_on(self.service.untried_sources(con))
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM boards WHERE board='rbc'")
            con.commit()
        self.service.put_profile({"profile": self.service.get_profile()["profile"]})

    def first_scan(self):
        return self.service.jobs(self.search)["first_scan"]

    def test_an_empty_list_says_whether_the_first_scan_is_still_under_way(self):
        self.assertFalse(self.service.jobs({})["first_scan"])          # roles to list
        none = self.service.jobs(self.search)
        self.assertEqual(0, none["total"])
        self.assertTrue(none["first_scan"])          # some postings ranked, none match, and no poll has finished
        self.finished_poll()
        self.assertFalse(self.first_scan())          # after a finished poll: "no roles match"
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM job_intel")
            con.commit()
        self.assertTrue(self.service.jobs({})["first_scan"])           # nothing ranked at all

    def test_a_board_picked_later_is_polled_at_once_and_a_first_scan_until_that_poll_ends(self):
        self.finished_poll()
        with self.service.db() as con:
            self.taken_on(self.service.untried_sources(con))
        self.service.put_profile({"profile": self.service.get_profile()["profile"]})
        self.assertFalse(self.service._poll_soon.is_set())             # an ordinary save: the next poll is on time
        self.assertFalse(self.first_scan())
        self.pick_rbc()
        self.assertTrue(self.service._poll_soon.is_set())              # polled once the poll under way ends
        self.assertTrue(self.first_scan())                             # its roles may be on their way
        self.finished_poll()                                           # the poll that took it on
        self.assertFalse(self.first_scan())

    def test_the_poll_under_way_at_the_pick_does_not_end_its_first_scan(self):
        self.finished_poll()
        self.service.status["poll_running"] = True      # the launch poll, which read the profile before setup
        self.pick_rbc()
        self.service.status["poll_running"] = False
        self.finished_poll()                            # that poll ends
        self.assertTrue(self.first_scan())
        self.finished_poll()                            # the next one, which took the board on
        self.assertFalse(self.first_scan())

    def test_a_board_picked_then_removed_before_any_poll_is_no_first_scan(self):
        self.finished_poll()
        self.pick_rbc()
        self.assertTrue(self.first_scan())
        profile = self.service.get_profile()["profile"]
        with patch.object(self.service, "untried_sources", return_value=set()):
            self.service.put_profile({"profile": profile})              # rbc's board removed again: none untried
        self.assertFalse(self.first_scan())                            # nothing new is on its way

    def test_a_board_a_poll_has_taken_on_stays_a_first_scan_until_that_poll_ends(self):
        self.finished_poll()
        self.pick_rbc()
        self.taken_on(["rbc"])                                         # the poll for it has started
        self.service.put_profile({"profile": self.service.get_profile()["profile"]})
        self.assertTrue(self.first_scan())
        self.finished_poll()
        self.assertFalse(self.first_scan())

    def run_auto_poll(self, **untried):
        """auto_poll with a poll under way when setup saves; the polls it starts, after that poll ends."""
        calls = []

        def trigger():
            calls.append(time.time())
            self.service.status["poll_running"] = len(calls) == 1     # the first poll is still running at setup
            return {"ok": True, "started": True}

        def wait_for(n, seconds=6):
            deadline = time.time() + seconds
            while len(calls) < n and time.time() < deadline:
                time.sleep(0.05)
            return len(calls)

        with patch.object(self.service, "trigger_poll", side_effect=trigger), \
                patch.object(self.service, "untried_sources", **untried):
            thread = threading.Thread(target=self.service.auto_poll, daemon=True)
            thread.start()
            try:
                self.assertEqual(1, wait_for(1))
                self.service._poll_soon.set()                          # setup saved a board no poll had started on
                time.sleep(0.3)
                self.assertEqual(1, len(calls), "not while a poll runs")
                self.service.status["poll_running"] = False
                wait_for(2, seconds=4)                                 # the check runs every 2 s; the interval is 300 s
            finally:
                self.service.stop_background()
                thread.join(5)
        self.assertFalse(thread.is_alive())
        return len(calls)

    def test_auto_poll_polls_a_new_board_once_the_poll_under_way_ends(self):
        self.assertEqual(2, self.run_auto_poll(return_value={"rbc"}))

    def test_auto_poll_waits_for_the_interval_when_the_poll_under_way_took_the_board_on(self):
        self.assertEqual(1, self.run_auto_poll(return_value=set()))

    def test_auto_poll_polls_on_when_it_cannot_tell(self):
        # A locked database must not end the loop, which would stop polling until the app restarts.
        self.assertEqual(2, self.run_auto_poll(side_effect=sqlite3.OperationalError("database is locked")))
