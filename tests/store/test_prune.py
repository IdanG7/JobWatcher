"""A poll's prune: postings past PRUNE_AFTER_DAYS go with their rows in every other table, found by key; a sweep
of every table for rows left without a posting runs once a day."""

import sqlite3
import time
import unittest
from datetime import datetime, timedelta, timezone

import watcher
from intel_store import IntelStore
from tests.store.test_store import CONFIG, add_job

CHILDREN = ("job_details", "job_text", "job_notes", "job_intel", "job_state")


def iso(days_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat(timespec="seconds")


def tables(con) -> dict:
    out = {t: sorted(con.execute(f"SELECT board, job_id FROM {t}").fetchall()) for t in ("jobs", *CHILDREN)}
    out["job_fts"] = sorted(r[0] for r in con.execute("SELECT rowid FROM job_fts"))
    return out


def sweep_every_table(con) -> None:
    """The prune as it was: every child table and the search index compared with jobs."""
    con.execute("""DELETE FROM jobs WHERE last_seen < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)
                   AND (board || ':' || job_id) NOT IN (SELECT job_key FROM applications)""",
                (f"-{watcher.PRUNE_AFTER_DAYS} days",))
    for table in CHILDREN:
        con.execute(f"DELETE FROM {table} WHERE NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.board={table}.board "
                    f"AND jobs.job_id={table}.job_id)")
    con.execute("DELETE FROM job_fts WHERE rowid NOT IN (SELECT rowid FROM job_intel)")


class PruneTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        now = time.time()
        for n in range(12):
            add_job(self.con, "rbc", str(n), f"2027 Investment Banking Summer Analyst {n}", posted=now - 86400,
                    first_seen=iso(120 if n < 6 else 3))
            self.con.execute("INSERT INTO job_text(board, job_id, description) VALUES ('rbc', ?, 'M&A team')",
                             (str(n),))
            self.con.execute("INSERT INTO job_notes(board, job_id, note) VALUES ('rbc', ?, 'Summer 2027')",
                             (str(n),))
        self.con.execute("INSERT INTO applications(job_key, board, job_id) VALUES ('rbc:0', 'rbc', '0')")
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()
        self.con.execute("INSERT INTO job_state(board, job_id, status) SELECT board, job_id, 'closed' FROM jobs")
        self.con.commit()

    def clone(self):
        other = sqlite3.connect(":memory:")
        self.addCleanup(other.close)
        self.con.commit()       # a backup waits for an open write
        self.con.backup(other)
        return other

    def test_aged_postings_go_with_their_rows_everywhere(self):
        expected = self.clone()
        sweep_every_table(expected)
        self.con.execute("INSERT INTO kv(k, v) VALUES ('orphan_sweep', ?)", (iso(0),))    # by key alone
        self.assertEqual(5, watcher.prune(self.con, IntelStore(self.con, CONFIG)))
        self.assertEqual(tables(expected), tables(self.con))
        self.assertEqual(sorted([("rbc", "0")] + [("rbc", str(n)) for n in range(6, 12)]),
                         sorted(self.con.execute("SELECT board, job_id FROM jobs")))

    def test_rows_left_without_a_posting_are_swept_once_a_day(self):
        self.con.execute("DELETE FROM jobs WHERE job_id='7'")      # left behind some other way
        expected = self.clone()
        sweep_every_table(expected)
        watcher.prune(self.con, IntelStore(self.con, CONFIG))
        self.assertEqual(tables(expected), tables(self.con))
        self.con.execute("DELETE FROM jobs WHERE job_id='8'")
        watcher.prune(self.con, IntelStore(self.con, CONFIG))
        self.assertIn(("rbc", "8"), tables(self.con)["job_intel"])  # swept within the day, not at every poll
        self.con.execute("UPDATE kv SET v=? WHERE k='orphan_sweep'", (iso(1.1),))
        watcher.prune(self.con, IntelStore(self.con, CONFIG))
        self.assertNotIn(("rbc", "8"), tables(self.con)["job_intel"])


if __name__ == "__main__":
    unittest.main()
