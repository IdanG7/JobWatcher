"""The backlog, pending-count and score-selection queries find their postings through indexes: the same postings as
comparing every row, in every state a posting can be in."""

import random
import re
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import watcher
from intel import FACTS_VERSION, knowledge
from intel.knowledge import config_fingerprint
from intel_store import IntelStore
from intel_worker import count_pending_facts
from tests.store.test_store import CONFIG, add_job

LEGACY = "0ldbytes0000"


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def day(days_ahead: float) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_ahead)).date().isoformat()


class IndexedQueryTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(knowledge.LEGACY_FINGERPRINTS, {LEGACY: config_fingerprint()}, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        rng = random.Random(7)
        titles = ["2027 Investment Banking Summer Analyst", "Senior Software Engineer", "Registered Nurse",
                  "Equity Research Associate", "Data Scientist Intern", ""]
        now = time.time()
        for n in range(240):
            add_job(self.con, rng.choice(["rbc", "linkedin_ca"]), str(n), rng.choice(titles) or "x",
                    posted=rng.choice([None, now - 3 * 3600, now - 10 * 86400, now - 50 * 86400, now - 90 * 86400]),
                    first_seen=iso(rng.choice([0.1, 5, 40, 80])))
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()
        version = IntelStore(self.con, CONFIG).version
        states = {
            "title": [None, ""],
            "input_hash": [None, "NULL"],
            "facts_version": [None, FACTS_VERSION - 1, FACTS_VERSION + 1, "NULL"],
            "kb_version": [None, LEGACY, "0ther0000000", "zzzz", "NULL"],
            "fit_detail": [None, "NULL"],
            "profile_version": [None, "NULL", "0ld", version + "z"],
            "rescore_at": [None, 0, now - 60, now + 3600, "NULL"],
            "deadline": [None, day(5), day(-5)],
        }
        for n in range(240):
            key = ("rbc" if self.con.execute("SELECT 1 FROM jobs WHERE board='rbc' AND job_id=?", (str(n),))
                   .fetchone() else "linkedin_ca", str(n))
            if rng.random() < 0.08:
                self.con.execute("DELETE FROM job_intel WHERE board=? AND job_id=?", key)
                continue
            for column, values in states.items():
                value = rng.choice(values) if rng.random() < 0.3 else None
                if value is None:
                    continue
                if column == "title":
                    self.con.execute("UPDATE jobs SET title='' WHERE board=? AND job_id=?", key)
                    continue
                self.con.execute(f"UPDATE job_intel SET {column}=? WHERE board=? AND job_id=?",
                                 (None if value == "NULL" else value, *key))
            if rng.random() < 0.1:
                self.con.execute("INSERT INTO applications(job_key, board, job_id, deadline) VALUES (?,?,?,?)",
                                 (f"{key[0]}:{key[1]}", *key, rng.choice([day(3), day(-3)])))
            if rng.random() < 0.1:
                self.con.execute("INSERT INTO job_overrides(job_key, deadline) VALUES (?,?)",
                                 (f"{key[0]}:{key[1]}", rng.choice([day(3), day(-3), ""])))
        # postings that left jobs keep a job_intel row until a prune
        self.con.execute("DELETE FROM jobs WHERE job_id IN ('3', '4')")
        self.con.commit()
        self.store = IntelStore(self.con, CONFIG)

    def every_row(self, fits: bool) -> list:
        """The postings the conditions pick when every posting is compared."""
        current = self.store.kb_current
        return self.con.execute(
            f"""SELECT j.board, j.job_id, COALESCE(i.is_finance,0), COALESCE(d.posted, 0)
                FROM jobs j LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
                LEFT JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
                WHERE j.title != '' AND (i.board IS NULL OR i.input_hash IS NULL OR i.facts_version != ?
                      OR i.kb_version NOT IN ({','.join('?' * len(current))}){' OR i.fit_detail IS NULL' if fits else ''})""",
            (FACTS_VERSION, *current)).fetchall()

    def test_the_backlog_is_every_posting_due_in_order(self):
        expected = self.every_row(fits=False)
        self.assertGreater(len(expected), 40)
        rows = self.store._backlog()
        self.assertEqual(sorted((b, j) for b, j, *_ in expected), sorted((r[0], r[1]) for r in rows))
        order = {(b, j): (fin, posted) for b, j, fin, posted in expected}
        keys = [order[(r[0], r[1])] for r in rows]
        self.assertEqual(sorted(keys, reverse=True), keys)
        first = [order[(r[0], r[1])] for r in self.store._backlog(limit=9)]
        self.assertEqual(keys[:9], first)

    def test_the_pending_counts_are_every_posting_due(self):
        for fits in (True, False):
            with self.subTest(fits=fits):
                self.assertEqual(len(self.every_row(fits)), count_pending_facts(self.con, fits=fits))

    def test_the_score_selection_is_every_posting_due(self):
        now = time.time()
        expected = self.con.execute(
            """SELECT i.board, i.job_id FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
               WHERE i.facts IS NOT NULL AND i.facts_version=? AND (
                   i.profile_version IS NULL OR i.profile_version != ? OR i.rescore_at IS NULL OR i.rescore_at <= ?)""",
            (FACTS_VERSION, self.store.version, now)).fetchall()
        self.assertGreater(len(expected), 20)
        self.assertEqual(sorted(expected), sorted((r[0], r[1]) for r in self.store._score_rows(now)))
        everything = self.con.execute("SELECT board, job_id FROM job_intel WHERE facts IS NOT NULL AND "
                                      "facts_version=?", (FACTS_VERSION,)).fetchall()
        forced = [(r[0], r[1]) for r in self.store._score_rows(now, force=True)]
        self.assertEqual(sorted(k for k in everything if k[1] not in ("3", "4")), sorted(forced))

    def test_the_queries_use_the_indexes(self):
        plans = {
            "backlog": self.store._backlog_sql(None, None),
            "score selection": self.store._score_sql(time.time(), False, None),
        }
        for name, (sql, args) in plans.items():
            with self.subTest(name):
                plan = " | ".join(r[3] for r in self.con.execute(f"EXPLAIN QUERY PLAN {sql}", args))
                self.assertIsNone(re.search(r"SCAN (i|i1|job_intel)\b", plan), plan)
                self.assertIsNotNone(re.search(r"USING (COVERING )?INDEX intel_", plan), plan)


if __name__ == "__main__":
    unittest.main()
