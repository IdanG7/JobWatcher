"""Regression tests for the 2026-10 reliability audit (batch 4): polling and
background behaviour behind the UI."""
import json
import time
from unittest.mock import patch

import watcher
from tests.app.test_dashboard import ServiceFixture


class CycleTests(ServiceFixture):
    def run_cycle(self, fetch, record_changes=None):
        events = []
        self.service.config["description_budget"] = 0
        patches = [patch.object(watcher, "fetch_board", side_effect=fetch),
                   patch.object(watcher, "load_subscribers", return_value=[])]
        if record_changes:
            patches.append(patch.object(watcher, "record_changes", side_effect=record_changes))
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        con = watcher.db_open(self.db_path)
        try:
            watcher.cycle(self.service.config, con, progress=lambda event, **data: events.append((event, data)))
        finally:
            con.close()
        return {data["board"]: data for event, data in events if event == "source_finished"}

    def test_one_boards_bad_data_does_not_stop_the_cycle(self):
        def fetch(name, cfg):
            return name, [{"id": "x1", "title": "Investment Banking Analyst", "location": "Toronto", "url": "https://e/x1"}]

        real = watcher.record_changes

        def record_changes(con, name, jobs, ts):
            if name == "rbc":
                raise ValueError("bad row")
            return real(con, name, jobs, ts)

        finished = self.run_cycle(fetch, record_changes)
        self.assertEqual("failed", finished["rbc"]["outcome"])
        self.assertTrue(any(f["outcome"] == "ok" for b, f in finished.items() if b != "rbc"))

    def test_a_reader_given_its_open_postings_closes_the_ones_it_found_gone(self):
        self.service.config["boards"]["rbc"] = {"ats": "taleo", "host": "rbc.taleo.net", "section": "ex"}
        given = {}

        def fetch(listing):
            def f(name, cfg):
                given[name] = cfg.get("_open_ids")
                return name, listing if name == "rbc" else []
            return f
        rows = [{"id": i, "title": f"Analyst {i}", "location": "Toronto", "url": f"https://e/{i}"} for i in ("one", "t1", "t2")]
        self.run_cycle(fetch(watcher.SourceListing(rows, complete=True, total=3)))
        short = watcher.SourceListing(rows[:1], reason="Taleo pagination ended at 1 of reported total 4", total=4)
        short.gone = frozenset({"t1"})        # t2 is missing too, but the site still counts it
        self.run_cycle(fetch(short))
        self.assertEqual(frozenset({"one", "t1", "t2"}), given["rbc"])      # what was stored and open
        self.assertIsNone(given["demo_quant"])                              # only Taleo readers look postings up
        with self.service.db() as con:
            state = dict(con.execute("SELECT job_id, status FROM job_state WHERE board='rbc'").fetchall())
            coverage = json.loads(con.execute("SELECT v FROM kv WHERE k='source_coverage:rbc'").fetchone()[0])
        self.assertEqual(("possibly_closed", "active"), (state["t1"], state.get("t2", "active")))
        self.assertEqual((False, True), (coverage["complete"], coverage["detects_removals"]))

    def test_estimated_dates_never_move_later(self):
        self.service.config["boards"]["rbc"]["ats"] = "workday"
        day = 86400
        first = int(time.time()) - 5 * day      # Workday dates are whole seconds

        def fetch(posted):
            return lambda name, cfg: (name, [{"id": "w1", "title": "Analyst", "location": "Toronto",
                                             "url": "https://e/w1", "posted": posted}])
        self.run_cycle(fetch(first))
        self.run_cycle(fetch(int(time.time())))          # a stale listing says "Posted Today" again
        with self.service.db() as con:
            posted = con.execute("SELECT posted FROM job_details WHERE board='rbc' AND job_id='w1'").fetchone()[0]
        self.assertAlmostEqual(first, posted, delta=1)


class BackoffTests(ServiceFixture):
    def test_failing_sources_back_off(self):
        self.assertEqual(0, watcher.failure_backoff(2))
        self.assertEqual(300, watcher.failure_backoff(3))
        self.assertEqual(7200, watcher.failure_backoff(40))
        self.assertEqual(0, watcher.failure_backoff("2026-10-12"))


class DigestWindowTests(ServiceFixture):
    def test_recent_window_is_twenty_four_hours(self):
        con = watcher.db_open(self.db_path)
        try:
            self._check(con)
        finally:
            con.close()

    def _check(self, con):
        old = (watcher.datetime.now(watcher.timezone.utc) - watcher.timedelta(hours=30)).isoformat(timespec="seconds")
        con.execute("INSERT INTO recent VALUES (?,?,?,?,?,?)", (old, "Old Co", "Analyst", "https://e/1", "", ""))
        con.execute("INSERT INTO recent VALUES (?,?,?,?,?,?)", (watcher.now(), "New Co", "Analyst", "https://e/2", "", ""))
        rows = con.execute("SELECT company FROM recent WHERE ts > strftime('%Y-%m-%dT%H:%M:%S', 'now','-1 day')").fetchall()
        self.assertEqual([("New Co",)], rows)


class FreshnessTests(ServiceFixture):
    def test_jobs_older_than_a_month_keep_rescoring_daily(self):
        from intel_store import IntelStore
        posted = time.time() - 45 * 86400
        with self.service.db() as con:
            con.execute("UPDATE job_details SET posted=? WHERE board='rbc' AND job_id='one'", (posted,))
            con.execute("UPDATE job_intel SET scored_at=? WHERE board='rbc' AND job_id='one'", (time.time() - 2 * 86400,))
            store = IntelStore(con, self.service.config)
            self.assertGreaterEqual(store.score_pass(), 1)
            detail = json.loads(con.execute("SELECT fit_detail FROM job_intel WHERE board='rbc' AND job_id='one'").fetchone()[0])
        self.assertTrue(any(s["key"] == "freshness" for s in detail["subscores"]))
