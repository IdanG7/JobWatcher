"""How far background work is, as /api/status reports it: a poll's sources and a ranking pass's postings,
done of total, so the bars fill instead of sitting gray."""
from contextlib import closing
import sqlite3
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
    def test_an_empty_list_says_whether_anything_is_ranked_yet(self):
        self.assertTrue(self.service.jobs({})["ranked_any"])
        none = self.service.jobs({"q": ["zzzz no such role"]})
        self.assertEqual(0, none["total"])
        self.assertTrue(none["ranked_any"])                 # postings are ranked; none match this search
        with closing(sqlite3.connect(self.db_path)) as con:
            con.execute("DELETE FROM job_intel")
            con.commit()
        self.assertFalse(self.service.jobs({})["ranked_any"])
