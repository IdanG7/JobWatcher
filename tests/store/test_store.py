"""Migrations, lifecycle (changes / closures), clustering and incremental scoring."""

import json
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import watcher
from db_migrations import SCHEMA_VERSION, migrate
from intel_store import IntelStore, ensure_fts, record_changes, store_description, update_lifecycle

CONFIG = {
    "profile": {},
    "boards": {
        "_canadian_banks": "---",
        "rbc": {"ats": "greenhouse", "token": "rbc"},
        "_linkedin": "---",
        "linkedin_ca": {"ats": "linkedin", "location": "Canada"},
    },
}


def iso(hours_ago=0.0):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def add_job(con, board, job_id, title, location="Toronto, ON", company="RBC", posted=None,
            first_seen=None, url=None):
    ts = first_seen or iso()
    con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                (board, job_id, title, location, url or f"https://example.com/{board}/{job_id}", ts, ts))
    con.execute("INSERT INTO job_details VALUES (?,?,?,?,?)", (board, job_id, company, "", posted))


class MigrationTests(unittest.TestCase):
    LEGACY_SCHEMA = """
        CREATE TABLE jobs(board TEXT, job_id TEXT, title TEXT, location TEXT, url TEXT,
                          first_seen TEXT, last_seen TEXT, PRIMARY KEY(board, job_id));
        CREATE TABLE job_details(board TEXT, job_id TEXT, company TEXT DEFAULT '',
                                 salary TEXT DEFAULT '', posted REAL, PRIMARY KEY(board, job_id));
        CREATE TABLE applications(job_key TEXT PRIMARY KEY, board TEXT, job_id TEXT, company TEXT,
            title TEXT, location TEXT DEFAULT '', url TEXT, salary TEXT DEFAULT '', posted REAL,
            status TEXT DEFAULT 'saved', priority INTEGER DEFAULT 0, notes TEXT DEFAULT '',
            next_step TEXT DEFAULT '', due_date TEXT DEFAULT '', created_at TEXT, updated_at TEXT);
    """

    def test_legacy_database_is_upgraded_without_losing_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legacy.db"
            con = sqlite3.connect(path)
            con.executescript(self.LEGACY_SCHEMA)
            con.execute("INSERT INTO jobs VALUES ('rbc','1','Analyst','Toronto','u','t','t')")
            con.execute("INSERT INTO applications(job_key, board, job_id, company, title, status, due_date, "
                        "created_at, updated_at) VALUES ('rbc:1','rbc','1','RBC','Analyst','interview',"
                        "'2026-10-20','t','t')")
            con.commit()
            con.close()

            con = watcher.db_open(path)
            self.assertEqual(SCHEMA_VERSION, con.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(1, con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            status, deadline = con.execute("SELECT status, deadline FROM applications").fetchone()
            self.assertEqual(("first_round", "2026-10-20"), (status, deadline))
            for table in ("job_intel", "job_state", "job_text", "job_changes", "contacts", "events",
                          "saved_searches", "company_prefs", "application_events", "user_profile"):
                con.execute(f"SELECT * FROM {table}")
            # Positional inserts used by older code and state imports still work.
            con.execute("INSERT INTO jobs VALUES ('rbc','2','Associate','NY','u2','t','t')")
            con.execute("INSERT INTO job_details VALUES ('rbc','2','RBC','',NULL)")
            con.close()

    def test_migration_is_idempotent(self):
        con = watcher.db_open(":memory:")
        self.assertEqual(SCHEMA_VERSION, migrate(con))
        self.assertEqual(SCHEMA_VERSION, con.execute("PRAGMA user_version").fetchone()[0])


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")

    def test_changes_are_recorded_but_blank_history_is_ignored(self):
        add_job(self.con, "rbc", "1", "Analyst", location="Toronto")
        self.con.execute("INSERT INTO jobs VALUES ('rbc','2','','','','t','t')")  # imported id-only row
        changes = record_changes(self.con, "rbc", [
            {"id": "1", "title": "Analyst", "location": "Montreal", "url": "https://example.com/rbc/1"},
            {"id": "2", "title": "Associate", "location": "Toronto", "url": "u"},
        ], iso())
        self.assertEqual([("location_changed", "Toronto", "Montreal")], [(c[3], c[5], c[6]) for c in changes])

    def test_description_change_is_an_event(self):
        add_job(self.con, "rbc", "1", "Analyst")
        self.assertTrue(store_description(self.con, "rbc", "1", "first version"))
        self.assertFalse(store_description(self.con, "rbc", "1", "first version"))
        self.assertTrue(store_description(self.con, "rbc", "1", "second version"))
        kinds = [r[0] for r in self.con.execute("SELECT kind FROM job_changes")]
        self.assertEqual(["description_changed"], kinds)

    def test_complete_listing_closure_and_reopen(self):
        add_job(self.con, "rbc", "1", "Analyst", first_seen=iso(48))
        self.con.execute("UPDATE jobs SET last_seen=? WHERE job_id='1'", (iso(30),))
        update_lifecycle(self.con, "rbc", set(), True, iso())
        status = lambda: self.con.execute("SELECT status, missing_count FROM job_state").fetchone()  # noqa: E731
        self.assertEqual(("possibly_closed", 1), status())
        update_lifecycle(self.con, "rbc", set(), True, iso())
        stats = update_lifecycle(self.con, "rbc", set(), True, iso())
        self.assertEqual(1, stats["closed"])
        self.assertEqual(("closed", 3), status())
        update_lifecycle(self.con, "rbc", {"1"}, True, iso())
        self.assertEqual(("active", 0), status())
        kinds = [r[0] for r in self.con.execute("SELECT kind FROM job_changes ORDER BY id")]
        self.assertEqual(["possibly_closed", "removed", "reopened"], kinds)

    def test_windowed_sources_never_close_jobs(self):
        add_job(self.con, "rbc", "1", "Analyst", first_seen=iso(100))
        self.con.execute("UPDATE jobs SET last_seen=? WHERE job_id='1'", (iso(90),))
        for _ in range(5):
            update_lifecycle(self.con, "rbc", set(), False, iso())
        self.assertIsNone(self.con.execute("SELECT status FROM job_state").fetchone())


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        now = time.time()
        add_job(self.con, "linkedin_ca", "9", "2027 Investment Banking Summer Analyst",
                "Toronto, Ontario, Canada", "RBC Capital Markets", now - 3600, first_seen=iso(1))
        add_job(self.con, "rbc", "1", "2027 Investment Banking Summer Analyst", "Toronto, ON", "RBC",
                now - 7200, first_seen=iso(2))
        add_job(self.con, "rbc", "2", "Senior Software Engineer", "Toronto, ON", "RBC", now - 86400)
        self.con.commit()
        self.store = IntelStore(self.con, CONFIG)

    def intel(self, board, job_id, column):
        return self.con.execute(f"SELECT {column} FROM job_intel WHERE board=? AND job_id=?",
                                (board, job_id)).fetchone()[0]

    def test_refresh_classifies_scores_and_clusters(self):
        stats = self.store.refresh()
        self.assertEqual(3, stats["facts"])
        self.assertEqual(3, stats["scored"])
        self.assertEqual("investment_banking", self.intel("rbc", "1", "category"))
        self.assertEqual(self.intel("rbc", "1", "cluster_key"), self.intel("linkedin_ca", "9", "cluster_key"))
        # Direct careers site beats LinkedIn as the canonical record.
        self.assertEqual(1, self.intel("rbc", "1", "is_canonical"))
        self.assertEqual(0, self.intel("linkedin_ca", "9", "is_canonical"))
        detail = json.loads(self.intel("rbc", "1", "fit_detail"))
        self.assertEqual(self.intel("rbc", "1", "fit"),
                         max(0, min(100, detail["raw_total"])))
        self.assertGreater(self.intel("rbc", "1", "fit"), self.intel("rbc", "2", "fit"))

    def test_refresh_is_incremental(self):
        self.store.refresh()
        again = self.store.refresh()
        self.assertEqual((0, 0), (again["facts"], again["scored"]))
        store_description(self.con, "rbc", "1", "Applications close October 30, 2026. Join our M&A team.")
        again = self.store.refresh()
        self.assertEqual(1, again["facts"])
        self.assertEqual("ma", self.intel("rbc", "1", "subcategory"))
        self.assertEqual("2026-10-30", self.intel("rbc", "1", "deadline"))

    def test_profile_change_rescores_everything(self):
        self.store.refresh()
        before = self.intel("rbc", "2", "fit")
        self.con.execute("INSERT INTO user_profile VALUES ('profile', ?)", (json.dumps({
            "target_roles": ["software"], "target_stages": ["senior", "experienced"]}),))
        store = IntelStore(self.con, CONFIG)
        stats = store.refresh()
        self.assertEqual(3, stats["scored"])
        self.assertGreater(self.intel("rbc", "2", "fit"), before)

    def test_targeted_facts_for_new_jobs(self):
        n = self.store.facts_pass(keys=[("rbc", "1")])
        self.assertEqual(1, n)
        self.assertEqual(1, self.con.execute("SELECT COUNT(*) FROM job_intel").fetchone()[0])

    def test_a_refresh_reports_how_many_postings_it_has_done(self):
        seen = []
        done = self.store.refresh(on_progress=seen.append)["facts"]
        self.assertGreater(done, 0)
        self.assertEqual([done], seen)      # one call per committed batch of 500

    def test_search_index(self):
        self.store.refresh()
        if not self.store.fts:
            self.skipTest("SQLite built without FTS5")
        search = """SELECT i.job_id FROM job_intel i
                    WHERE i.rowid IN (SELECT rowid FROM job_fts WHERE job_fts MATCH ?)"""
        self.assertEqual({"1", "9"}, {h[0] for h in self.con.execute(search, ('"summer"*',))})
        # Re-classifying a job replaces its index row instead of duplicating it.
        self.con.execute("UPDATE job_intel SET input_hash=NULL WHERE job_id='1'")
        self.store.facts_pass()
        self.assertEqual(self.con.execute("SELECT COUNT(*) FROM job_intel").fetchone()[0],
                         self.con.execute("SELECT COUNT(*) FROM job_fts").fetchone()[0])
        self.assertEqual({"1", "9"}, {h[0] for h in self.con.execute(search, ('"summer"*',))})

    def test_legacy_fts_layout_is_rebuilt(self):
        self.store.refresh()
        if not self.store.fts:
            self.skipTest("SQLite built without FTS5")
        self.con.execute("DROP TABLE job_fts")
        self.con.execute("CREATE VIRTUAL TABLE job_fts USING fts5(board UNINDEXED, job_id UNINDEXED, body)")
        self.assertTrue(ensure_fts(self.con))
        sql = self.con.execute("SELECT sql FROM sqlite_master WHERE name='job_fts'").fetchone()[0]
        self.assertNotIn("job_id", sql)
        hits = self.con.execute("SELECT rowid FROM job_fts WHERE job_fts MATCH ?", ('"summer"*',)).fetchall()
        self.assertEqual(2, len(hits))


if __name__ == "__main__":
    unittest.main()
