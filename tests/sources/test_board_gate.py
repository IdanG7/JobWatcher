"""tools/board_gate.py: the same code gives the same boards; a moved posting or a label change is named."""

import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path

import watcher
from tools import board_gate

ROOT = Path(__file__).resolve().parents[2]
EPOCH = 1793070000          # 2026-10-27 03:00 UTC
POSTINGS = [
    ("rbc", "1", "Summer Analyst, Investment Banking", "Toronto, ON", "RBC Capital Markets"),
    ("rbc", "2", "Software Engineer Intern, Backend", "Toronto, ON", "RBC"),
    ("acme", "3", "Clinical Research Coordinator Co-op", "Toronto, ON", "Acme Health"),
    ("acme", "4", "Data Scientist Intern", "New York, NY", "Acme Health"),
    ("acme", "5", "Marketing Coordinator", "Toronto, ON", "Acme Health"),
]


class GateCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def compare(self, old, new, expect=()) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = board_gate.compare(old, new, expect)
        return code, out.getvalue()


class SnapshotTests(GateCase):
    def test_the_same_code_on_the_same_copy_gives_the_same_boards(self):
        db = self.dir / "jobwatch.db"
        con = watcher.db_open(db)
        for board, job_id, title, location, company in POSTINGS:
            con.execute("INSERT INTO jobs(board,job_id,title,location,url,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)",
                        (board, job_id, title, location, f"https://example.com/{job_id}",
                         "2026-10-20T12:00:00+00:00", "2026-10-26T12:00:00+00:00"))
            con.execute("INSERT INTO job_details(board,job_id,company,salary,posted) VALUES (?,?,?,?,?)",
                        (board, job_id, company, "", EPOCH - 5 * 86400))
        con.commit()
        con.close()
        config = self.dir / "config.json"
        config.write_text(json.dumps({"boards": {"rbc": {"ats": "workday"}, "acme": {"ats": "greenhouse"}}}),
                          encoding="utf-8")
        logs = []
        for name, workers in (("a", 2), ("b", 1)):
            board_gate.snapshot(ROOT, db, config, EPOCH, self.dir / f"{name}.db", workers=workers, log=logs.append)
        views = board_gate.board_views(self.dir / "a.db")
        self.assertEqual({"default", "finance", "user", *board_gate.BOARDS, *("+".join(m) for m in board_gate.MIXES)},
                         set(views["profiles"]))
        self.assertEqual(len(POSTINGS), len(views["facts"]))
        self.assertIn(("rbc", "1"), views["profiles"]["finance"]["rows"])
        self.assertIn(("rbc", "2"), views["profiles"]["software"]["rows"])
        code, out = self.compare(self.dir / "a.db", self.dir / "b.db")
        self.assertEqual(0, code, out)
        self.assertIn("gate: passed", out)
        # The database given is never written.
        with closing(sqlite3.connect(db)) as con:
            self.assertEqual(len(POSTINGS), con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            self.assertEqual(0, con.execute("SELECT COUNT(*) FROM job_intel").fetchone()[0])


def fake_snapshot(path: Path, postings: dict, fits: dict) -> Path:
    """A snapshot by hand: postings {key: (is_finance, family, company_type)}, fits {(profile, key): fit}."""
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE facts (board TEXT, job_id TEXT, title TEXT, is_canonical INT, is_finance INT, family TEXT,
          category TEXT, subcategory TEXT, company_key TEXT, company_name TEXT, company_type TEXT, cluster_key TEXT,
          city TEXT, country TEXT, stage TEXT, level TEXT, cycle TEXT, skills TEXT, status TEXT, hidden INT,
          facts_hash TEXT);
        CREATE TABLE scores (profile TEXT, board TEXT, job_id TEXT, fit REAL, urgency REAL, window_status TEXT,
          badges TEXT, deadline TEXT, posted_ref REAL, detail_hash TEXT, matched INT, match_hash TEXT);""")
    con.executemany("INSERT INTO meta VALUES (?,?)", [("boards:finance", '["finance"]'), ("boards:software", '["software"]'),
                                                      ("boards:healthcare", '["healthcare"]')])
    for (board, job_id), (is_finance, family, ctype) in postings.items():
        con.execute("INSERT INTO facts VALUES (?,?,'Title',1,?,?,?,NULL,'acme','Acme',?,'c','','','','','','','active',0,?)",
                    (board, job_id, is_finance, family, "ib" if is_finance else family, ctype, f"{family}{ctype}"))
        for profile in ("finance", "software", "healthcare"):
            fit = fits.get((profile, (board, job_id)), 50.0)
            con.execute("INSERT INTO scores VALUES (?,?,?,?,0,'open','[]',NULL,0,?,0,NULL)",
                        (profile, board, job_id, fit, f"why {ctype} {fit}"))
    con.commit()
    con.close()
    return path


class CompareTests(GateCase):
    BASE = {("a", "1"): (1, "other", "bulge_bracket"), ("a", "2"): (0, "software", "big_tech"),
            ("a", "3"): (0, "other", "unknown")}

    def test_a_posting_that_moves_board_is_named_and_fails_the_gate(self):
        old = fake_snapshot(self.dir / "old.db", self.BASE, {})
        new = fake_snapshot(self.dir / "new.db", {**self.BASE, ("a", "3"): (0, "healthcare", "unknown"),
                                                  ("a", "2"): (0, "healthcare", "big_tech")}, {})
        code, out = self.compare(old, new)
        self.assertEqual(1, code)
        self.assertIn("software", out)
        self.assertIn("- a:2", out)
        # Counted by move, and each posting that leaves a board listed with its title and employer.
        self.assertIn("software -> healthcare: 1", out)
        self.assertIn("other -> healthcare: 1", out)
        self.assertIn("software -> healthcare  a:2  'Title' @ Acme", out)
        self.assertNotIn("a:3  'Title'", out)
        self.assertIn("gate: FAILED", out)
        # Allowed when the profile that changes is expected to.
        self.assertEqual(0, self.compare(old, new, expect=("software", "healthcare"))[0])

    def test_a_known_employer_in_place_of_an_unclassified_one_is_a_label_change(self):
        base = {**self.BASE, ("a", "3"): (0, "software", "unknown")}
        old = fake_snapshot(self.dir / "old.db", base, {})
        new = fake_snapshot(self.dir / "new.db", {**base, ("a", "3"): (0, "software", "pharma")}, {})
        code, out = self.compare(old, new)
        self.assertEqual(0, code, out)
        self.assertIn("label changes 1", out)

    def test_a_fit_change_fails_unless_its_profile_is_expected(self):
        old = fake_snapshot(self.dir / "old.db", self.BASE, {})
        new = fake_snapshot(self.dir / "new.db", self.BASE, {("finance", ("a", "1")): 61.0})
        code, out = self.compare(old, new)
        self.assertEqual(1, code)
        self.assertIn("'fit': 1", out)
        self.assertEqual(0, self.compare(old, new, expect=("finance",))[0])



if __name__ == "__main__":
    unittest.main()
