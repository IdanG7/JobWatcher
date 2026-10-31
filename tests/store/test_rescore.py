"""Re-scoring when what a posting shows can change (rescore_at), not every hour: nothing shown changes before it,
and every change of input sends the postings it reaches back for a score."""

import itertools
import json
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import intel_store
import watcher
from intel import build_facts, load_knowledge, merge_profile, score_job
from intel_store import IntelStore
from tests.store.test_store import CONFIG, add_job, iso

HOUR, DAY = 3600, 86400
T0 = datetime(2026, 10, 30, 13, 17, 41, tzinfo=timezone.utc).timestamp()
POSTINGS = [
    {"board": "rbc", "id": "1", "title": "2027 Investment Banking Summer Analyst", "location": "Toronto, ON",
     "company": "RBC", "description": "Rolling applications. Join our M&A team."},
    {"board": "rbc", "id": "2", "title": "Senior Software Engineer", "location": "Toronto, ON", "company": "RBC",
     "description": "Build trading systems."},
    {"board": "rbc", "id": "3", "title": "Registered Nurse - New Grad", "location": "Toronto, ON", "company": "UHN",
     "description": "Current registered nurse registration with the CNO."},
]


def shown(result: dict) -> dict:
    return {k: v for k, v in result.items() if k not in ("posting_age_hours", "rescore_at")}


class RescoreAtTests(unittest.TestCase):
    def test_nothing_shown_changes_before_rescore_at(self):
        kn = load_knowledge()
        profile = merge_profile(None)
        facts = [build_facts(job, kn) for job in POSTINGS]
        posted = [None, 0.4 * HOUR, 5.5 * HOUR, 23.9 * HOUR, 47.5 * HOUR, 3 * DAY, 44.9 * DAY, 80 * DAY]
        deadlines = [None, -3, 0, 2, 6.5, 13.5, 30]
        statuses = ["active", "possibly_closed", "closed"]
        checked = 0
        for n, (f, age, ahead, status, discovered) in enumerate(itertools.product(
                facts, posted, deadlines, statuses, (False, True))):
            if n % 3:       # a third of the combinations, every kind of each
                continue
            dyn = {"posted": None if age is None else T0 - age, "first_seen": T0 - (age or 2 * HOUR) / 2,
                   "discovered": discovered, "status": status, "watched": False, "recent_change": False,
                   "deadline_override": None if ahead is None else
                   datetime.fromtimestamp(T0 + ahead * DAY, timezone.utc).date().isoformat()}
            for start in (T0, T0 + 17 * 60, T0 + 11.3 * HOUR, T0 + 2.6 * DAY, T0 + 40 * DAY):
                first = score_job(f, profile, kn, dyn, start)
                until = first["rescore_at"]
                self.assertTrue(until is None or until > start, (n, start, until))
                # rescore_at falls 10 ms after the boundary it waits for
                end = min(until - 0.01 if until else start + 70 * DAY, start + 70 * DAY)
                for t in [start + (end - start) * k / 12 for k in range(1, 12)] + [end - 0.001] * (end - 0.001 > start):
                    with self.subTest(posting=n, start=start - T0, at=t - T0):
                        self.assertEqual(shown(first), shown(score_job(f, profile, kn, dyn, t)))
                    checked += 1
        self.assertGreater(checked, 5000)

    def test_a_posting_with_nothing_left_to_change_has_no_rescore_time(self):
        kn = load_knowledge()
        f = build_facts(POSTINGS[1], kn)
        result = score_job(f, merge_profile(None), kn, {"posted": None, "status": "active"}, T0)
        self.assertIsNone(result["rescore_at"])


class RescorePassTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        now = time.time()           # dates between the boundaries, so nothing is due again at once
        add_job(self.con, "linkedin_ca", "9", "2027 Investment Banking Summer Analyst",
                "Toronto, Ontario, Canada", "RBC Capital Markets", now - 3.5 * HOUR, first_seen=iso(1))
        add_job(self.con, "rbc", "1", "2027 Investment Banking Summer Analyst", "Toronto, ON", "RBC",
                now - 2.5 * HOUR, first_seen=iso(2))
        add_job(self.con, "rbc", "2", "Senior Software Engineer", "Toronto, ON", "RBC", now - 50.5 * DAY)
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()

    def at(self, epoch):
        return patch.object(intel_store.time, "time", return_value=epoch)

    def rescore_at(self, board, job_id):
        return self.con.execute("SELECT rescore_at FROM job_intel WHERE board=? AND job_id=?",
                                (board, job_id)).fetchone()[0]

    def test_a_pass_scores_only_postings_whose_shown_values_moved(self):
        now = time.time()
        self.assertEqual(0, IntelStore(self.con, CONFIG).score_pass())
        due = {k: self.rescore_at(*k) for k in (("rbc", "1"), ("linkedin_ca", "9"), ("rbc", "2"))}
        for key, when in due.items():
            self.assertLessEqual(when, now + DAY + 60, key)      # at least daily
        first = min(due.values())
        with self.at(first - 1):
            self.assertEqual(0, IntelStore(self.con, CONFIG).score_pass())
        with self.at(first + 1):
            self.assertEqual(sum(1 for when in due.values() if when <= first + 1),
                             IntelStore(self.con, CONFIG).score_pass())

    def test_scores_from_before_rescore_at_are_scored_once(self):
        self.con.execute("UPDATE job_intel SET rescore_at=NULL")
        self.assertEqual(3, IntelStore(self.con, CONFIG).score_pass())
        self.assertEqual(0, IntelStore(self.con, CONFIG).score_pass())

    def test_a_changed_posting_date_rescores_its_cluster(self):
        self.con.execute("UPDATE job_details SET posted=posted-3600 WHERE board='rbc' AND job_id='1'")
        self.assertEqual(2, IntelStore(self.con, CONFIG).score_pass())

    def test_an_application_deadline_rescores_the_posting(self):
        day = (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat()
        self.con.execute("INSERT INTO applications(job_key, board, job_id, deadline) VALUES ('rbc:2','rbc','2',?)",
                         (day,))
        self.assertEqual(1, IntelStore(self.con, CONFIG).score_pass())
        self.assertEqual(day, self.con.execute("SELECT eff_deadline FROM job_intel WHERE job_id='2'").fetchone()[0])
        self.con.execute("UPDATE applications SET deadline='' WHERE job_key='rbc:2'")
        self.assertEqual(1, IntelStore(self.con, CONFIG).score_pass())
        self.con.execute("DELETE FROM applications WHERE job_key='rbc:2'")
        self.assertEqual(1, IntelStore(self.con, CONFIG).score_pass())

    def test_facts_rebuilt_for_one_duplicate_rescore_the_others(self):
        self.con.execute("UPDATE job_intel SET input_hash=NULL WHERE board='rbc' AND job_id='1'")
        stats = IntelStore(self.con, CONFIG).refresh()
        self.assertEqual((1, 2), (stats["facts"], stats["scored"]))

    def test_the_updated_badge_goes_when_its_change_is_two_days_old(self):
        changed = time.time() - 47 * HOUR
        self.con.execute("INSERT INTO job_changes(board, job_id, ts, kind, field, old, new) VALUES "
                         "('rbc','2',?,'title_changed','title','Engineer','Senior Software Engineer')",
                         (datetime.fromtimestamp(changed, timezone.utc).isoformat(timespec="seconds"),))
        self.con.execute("UPDATE job_intel SET profile_version=NULL WHERE board='rbc' AND job_id='2'")
        IntelStore(self.con, CONFIG).score_pass()
        self.assertIn("UPDATED", self.con.execute("SELECT badges FROM job_intel WHERE job_id='2'").fetchone()[0])
        when = self.rescore_at("rbc", "2")
        self.assertLessEqual(when, changed + 48 * HOUR + 1)
        with self.at(when + 1):
            IntelStore(self.con, CONFIG).score_pass()
        self.assertGreater(self.rescore_at("rbc", "2"), when + 1)
        self.assertNotIn("UPDATED", self.con.execute("SELECT badges FROM job_intel WHERE job_id='2'").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
