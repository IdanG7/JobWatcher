"""A posting goes back for facts whenever an input its facts read changes, blank or not. Before, a poll sent it
back only when a title, location or salary changed from one value to another, so a salary or a place that came
or went, a new company name or posting day left facts built from inputs the posting no longer had."""

import unittest
from unittest.mock import patch

import intel_store
import watcher
from intel_store import IntelStore
from tests.store.test_store import CONFIG, add_job

DAY = 86400
POSTED = 20752 * DAY + 3 * 3600         # 03:00 UTC: a minute either way is the same day


class PollTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        self.config = {**CONFIG, "description_budget": 0}
        self.con.execute("INSERT INTO boards(board, seeded, last_ok, failures, last_poll) VALUES ('rbc',1,?,0,0)",
                         (watcher.now(),))
        self.con.commit()

    def poll(self, **listing):
        job = {"id": "7", "title": "Investment Banking Analyst", "url": "https://example.com/rbc/7", **listing}
        self.con.execute("UPDATE boards SET last_poll=0")
        with patch.object(watcher, "fetch_board", side_effect=lambda name, cfg: (name, [job] if name == "rbc" else [])), \
                patch.object(watcher, "load_subscribers", return_value=[]):
            watcher.cycle(self.config, self.con)
        IntelStore(self.con, self.config).refresh()
        return self.con.execute("SELECT comp_annual_min, city FROM job_intel WHERE board='rbc' AND job_id='7'").fetchone()

    def test_a_salary_that_goes_and_a_place_that_comes_reach_the_facts(self):
        self.assertEqual((116000, None), self.poll(location="", salary="$116K – $174K"))
        self.assertEqual((None, "toronto"), self.poll(location="Toronto, ON", salary=""))
        # still not news: the change log keeps its rule for blank values
        self.assertEqual(0, self.con.execute("SELECT COUNT(*) FROM job_changes").fetchone()[0])

    def test_an_unchanged_listing_is_not_read_again(self):
        self.poll(location="Toronto, ON", salary="$116K – $174K")
        with patch.object(intel_store, "build_facts", side_effect=intel_store.build_facts) as build:
            self.poll(location="Toronto, ON", salary="$116K – $174K")
        self.assertEqual(0, build.call_count)


class TriggerTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        add_job(self.con, "rbc", "1", "Investment Banking Analyst", posted=POSTED)
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()

    def sent_back(self) -> bool:
        return self.con.execute("SELECT input_hash IS NULL FROM job_intel WHERE board='rbc' AND job_id='1'"
                                ).fetchone()[0] == 1

    def test_each_input_facts_read_sends_the_posting_back(self):
        for change in ("jobs SET location=''", "jobs SET location='Montreal, QC'", "jobs SET title='Equity Analyst'",
                       "job_details SET salary='$90,000'", "job_details SET salary=''",
                       "job_details SET company='RBC Capital Markets'", "job_details SET posted=posted+86400",
                       "job_details SET posted=NULL"):
            with self.subTest(change):
                self.con.execute(f"UPDATE {change} WHERE board='rbc' AND job_id='1'")
                self.assertTrue(self.sent_back())
                IntelStore(self.con, CONFIG).refresh()
                self.assertFalse(self.sent_back())

    def test_what_facts_dont_read_leaves_them(self):
        for change in ("jobs SET url='https://example.com/moved', last_seen='2026-10-31T00:00:00+00:00'",
                       "jobs SET title=title, location=location", "job_details SET salary=salary, company=company",
                       "job_details SET posted=posted+60"):
            with self.subTest(change):
                self.con.execute(f"UPDATE {change} WHERE board='rbc' AND job_id='1'")
                self.assertFalse(self.sent_back())


class OneTimeCheckTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        for n in range(5):
            add_job(self.con, "rbc", str(n), "Investment Banking Analyst", posted=POSTED)
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()

    def leave_stale(self, *job_ids):
        """What an older poll left: the stored inputs moved on, the facts and their hash didn't."""
        for job_id in job_ids:
            self.con.execute("UPDATE job_intel SET input_hash='0ld0inputs0000' WHERE board='rbc' AND job_id=?",
                             (job_id,))

    def test_facts_from_inputs_a_posting_no_longer_has_are_read_again_once(self):
        self.leave_stale("1", "4")
        self.con.execute("DELETE FROM kv WHERE k='inputs_rechecked'")
        with patch.object(intel_store, "RECHECK_CHUNK", 2):
            self.assertEqual(2, IntelStore(self.con, CONFIG).refresh()["facts"])
        self.assertEqual(0, IntelStore(self.con, CONFIG).refresh()["facts"])
        # once: from then on the triggers send postings back
        self.leave_stale("2")
        self.assertEqual(0, IntelStore(self.con, CONFIG).refresh()["facts"])


if __name__ == "__main__":
    unittest.main()
