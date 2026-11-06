"""tools/board_gate.py: the same code gives the same boards; a moved posting or a label change is named."""

import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing, redirect_stdout
from pathlib import Path
from unittest import mock

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

    def place_compare(self, old, new, **kw) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = board_gate.place_compare(old, new, **kw)
        return code, out.getvalue()

    def database(self) -> tuple[Path, Path]:
        """POSTINGS in a database the app opened, and a config.json listing their sources."""
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
        return db, config


class SnapshotTests(GateCase):
    def test_the_same_code_on_the_same_copy_gives_the_same_boards(self):
        db, config = self.database()
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


class PolledTests(GateCase):
    def test_each_sample_profile_polls_what_the_app_selects_and_a_change_is_named(self):
        from intel import load_knowledge
        from intel.profile import DEFAULT_PROFILE, merge_profile
        from intel.sources import load_config, load_packs, polled_sources
        lists = board_gate.polled(ROOT, ROOT / "config.json", self.dir / "a.json")
        board_gate.polled(ROOT, ROOT / "config.json", self.dir / "b.json")
        self.assertEqual({"default", "finance", *board_gate.BOARDS, *("+".join(m) for m in board_gate.MIXES)}, set(lists))
        kn, config = load_knowledge(), load_config(ROOT / "config.json")
        layer = board_gate.first_run(["product", "design"], DEFAULT_PROFILE, {s.key: s.group for s in kn.skills})
        self.assertEqual(sorted(polled_sources(config, merge_profile(config.get("profile"), layer), kn, load_packs())),
                         lists["product+design"]["sources"])
        self.assertEqual({"finance", "shared"}, set(lists["finance"]["folders"]))
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(0, board_gate.polled_compare(self.dir / "a.json", self.dir / "b.json"))
        self.assertIn("polled: passed", out.getvalue())

        changed = json.loads((self.dir / "b.json").read_text(encoding="utf-8"))
        product = changed["profiles"]["product"]
        product["sources"].append("new_studio")
        product["count"] += 1
        product["hash"] = "0" * 16
        (self.dir / "c.json").write_text(json.dumps(changed), encoding="utf-8")
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(1, board_gate.polled_compare(self.dir / "a.json", self.dir / "c.json"))
            self.assertEqual(0, board_gate.polled_compare(self.dir / "a.json", self.dir / "c.json", expect=["product"]))
        self.assertIn("+1: new_studio", out.getvalue())
        self.assertIn("polled: FAILED", out.getvalue())


class PlaceTests(GateCase):
    def test_the_same_code_places_the_picked_postings_the_same_way_as_the_app_stored_them(self):
        import db_migrations
        db, config = self.database()
        # A copy from an install that lags behind: schema 6 had no job_notes, which the facts worker reads.
        with closing(sqlite3.connect(db)) as con:
            con.executescript("DROP TABLE job_notes; PRAGMA user_version=6;")
        logs = []
        # The words alone, no random picks: Software's title words and "marketing", as whole words.
        exact = self.dir / "words.json"
        board_gate.sample(db, exact, cap=0, words=[ROOT], boards=["software"], titles=["marketing"], log=logs.append)
        self.assertEqual([["acme", "5"], ["rbc", "2"]], json.loads(exact.read_text(encoding="utf-8"))["ids"])
        ids = self.dir / "ids.json"
        counts = board_gate.sample(db, ids, cap=2, words=[ROOT], boards=["software"], titles=["marketing"],
                                   log=logs.append)
        picked = json.loads(ids.read_text(encoding="utf-8"))
        # Two from each source at random, and every title the words name.
        self.assertEqual({"sources": 2, "postings": 5, "title_matches": 2, "picked": 4}, counts)
        self.assertLessEqual({("rbc", "1"), ("rbc", "2"), ("acme", "5")}, set(map(tuple, picked["ids"])))
        self.assertIn(r"(?<![a-z0-9])(?:marketing)(?![a-z0-9])", picked["patterns"])    # a whole word
        for wrong in ({}, {"words": [ROOT]}, {"boards": ["software"]}):
            with self.assertRaises(SystemExit):
                board_gate.sample(db, self.dir / "x.json" if wrong else ids, log=logs.append, **wrong)

        for name, workers in (("a", 2), ("b", 1)):
            board_gate.place(ROOT, db, config, ids, self.dir / f"{name}.db", workers=workers, log=logs.append)
        placed, meta = board_gate.placements(self.dir / "a.db")
        self.assertEqual(4, len(placed))
        self.assertEqual(str(picked["epoch"]), meta["epoch"].removesuffix(".0"))
        self.assertEqual("finance", placed["rbc", "1"]["field"])
        self.assertEqual("software", placed["rbc", "2"]["field"])
        self.assertEqual("US", placed["acme", "4"]["countries"])
        code, out = self.place_compare(self.dir / "a.db", self.dir / "b.db")
        self.assertEqual(0, code, out)
        self.assertIn("place: passed", out)
        self.assertEqual([], [p.name for p in self.dir.glob("*.facts*.db")])
        with self.assertRaises(SystemExit):
            board_gate.place(ROOT, db, config, ids, self.dir / "a.db", log=logs.append)
        # A checkout's config.json lists no sources, so the postings would read with no source settings.
        with self.assertRaises(SystemExit):
            board_gate.place(ROOT, db, ROOT / "config.json", ids, self.dir / "c.db", log=logs.append)
        self.assertFalse((self.dir / "c.db").exists())

        # The copy keeps its postings after the checkout's migrations, and the app's own facts pass places
        # them where the check does.
        import intel_store
        with closing(sqlite3.connect(db)) as con:
            self.assertEqual(db_migrations.SCHEMA_VERSION, con.execute("PRAGMA user_version").fetchone()[0])
            self.assertEqual(len(POSTINGS), con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0])
            store = intel_store.IntelStore(con, json.loads(config.read_text(encoding="utf-8")))
            store.facts_workers = 1
            store.facts_pass()
            con.commit()
        board_gate.place(None, db, None, ids, self.dir / "stored.db", stored=True, log=logs.append)
        code, out = self.place_compare(self.dir / "stored.db", self.dir / "a.db")
        self.assertEqual(0, code, out)

    def test_the_installed_database_is_never_placed(self):
        installed = self.dir / "Jobwatch" / "jobwatch.db"
        installed.parent.mkdir()
        installed.touch()
        (self.dir / "ids.json").write_text('{"epoch": 0, "ids": []}', encoding="utf-8")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(self.dir)}):
            for stored in (False, True):
                with self.assertRaises(SystemExit):
                    board_gate.place(ROOT, installed, None, self.dir / "ids.json", self.dir / f"{stored}.db",
                                     stored=stored, log=lambda line: None)
        # With LOCALAPPDATA unset, the data folder is still found under the home folder.
        home = self.dir / "home"
        (home / "AppData" / "Local" / "Jobwatch").mkdir(parents=True)
        (home / "AppData" / "Local" / "Jobwatch" / "jobwatch.db").touch()
        env = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with mock.patch.dict(os.environ, env, clear=True), mock.patch.object(Path, "home", return_value=home):
            with self.assertRaises(SystemExit):
                board_gate.place(ROOT, home / "AppData" / "Local" / "Jobwatch" / "jobwatch.db", None,
                                 self.dir / "ids.json", self.dir / "home.db", stored=True, log=lambda line: None)
        self.assertEqual(0, installed.stat().st_size)

    @unittest.skipUnless(os.name == "nt", "a directory junction")
    def test_the_installed_database_is_never_placed_through_a_junction(self):
        real, local = self.dir / "real", self.dir / "local"
        real.mkdir()
        local.mkdir()
        (real / "jobwatch.db").touch()
        subprocess.run(["cmd", "/c", "mklink", "/J", str(local / "Jobwatch"), str(real)], check=True,
                       capture_output=True)
        (self.dir / "ids.json").write_text('{"epoch": 0, "ids": []}', encoding="utf-8")
        with mock.patch.dict(os.environ, {"LOCALAPPDATA": str(local)}), self.assertRaises(SystemExit):
            board_gate.place(ROOT, real / "jobwatch.db", None, self.dir / "ids.json", self.dir / "j.db", stored=True,
                             log=lambda line: None)
        os.rmdir(local / "Jobwatch")    # the junction itself, before the folder is cleaned up

    def test_a_failed_worker_leaves_no_placement_and_no_worker_running(self):
        db, config = self.database()
        ids = self.dir / "ids.json"
        board_gate.sample(db, ids, cap=5, log=lambda line: None)
        started, popen = [], subprocess.Popen

        def worker(args, **kw):     # facts worker 0 fails at once; everything else runs as usual
            if "_facts" not in args:
                return popen(args, **kw)
            started.append(popen([sys.executable, "-c", "raise SystemExit(1)"] if args[-4] == "0" else args, **kw))
            return started[-1]

        with mock.patch.object(board_gate.subprocess, "Popen", worker), self.assertRaises(SystemExit):
            board_gate.place(ROOT, db, config, ids, self.dir / "a.db", workers=3, log=lambda line: None)
        self.assertEqual(3, len(started))
        self.assertTrue(all(p.poll() is not None for p in started))
        with self.assertRaises(SystemExit):     # the shards it would write must not exist either
            (self.dir / "b.facts0.db").touch()
            board_gate.place(ROOT, db, config, ids, self.dir / "b.db", workers=2, log=lambda line: None)
        (self.dir / "b.facts0.db").unlink()
        self.assertEqual([], sorted(p.name for p in self.dir.iterdir() if p.suffix == ".db" and p.name != "jobwatch.db"))

    def test_a_title_file_is_a_list_of_words_or_lists_under_keys(self):
        path = self.dir / "words.json"
        for words, expected in ((["ux", "designers?"], ["ux", "designers?"]),
                                ({"_note": "x", "product": ["pms?"], "design": ["ui"]}, ["pms?", "ui"])):
            path.write_text(json.dumps(words), encoding="utf-8")
            self.assertEqual(expected, board_gate._title_file(path))
        for wrong in ({"product": "product manager"}, ["ux", 3], {"design": [""]}, "ux"):
            path.write_text(json.dumps(wrong), encoding="utf-8")
            with self.assertRaises(SystemExit):
                board_gate._title_file(path)


def fake_placed(path: Path, rows: dict) -> Path:
    """A placement by hand: rows {key: columns that differ from a Software posting at Acme in Toronto}."""
    con = sqlite3.connect(path)
    con.executescript(f"""CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE placed (board TEXT, job_id TEXT, {", ".join(board_gate.PLACED)});
        INSERT INTO meta VALUES ('ids_sha1', 'same');""")
    for (board, job_id), columns in rows.items():
        row = {"title": "Title", "field": "software", "family": "software", "category": "software",
               "subcategory": None, "is_finance": 0, "company_key": "acme", "company_name": "Acme",
               "company_type": "unknown", "country": "CA", "countries": "CA", "city": "toronto", "cities": "toronto",
               "location_bucket": "toronto", "rule": None, "stage": "internship", "level": "intern", **columns}
        con.execute(f"INSERT INTO placed VALUES (?,?,{','.join('?' * len(board_gate.PLACED))})",
                    (board, job_id, *(row[c] for c in board_gate.PLACED)))
    con.commit()
    con.close()
    return path


class PlaceCompareTests(GateCase):
    PRODUCT = {"field": "product", "family": "product", "category": "product"}
    BASE = {("a", "1"): {}, ("a", "2"): {"field": "finance", "family": "other", "category": "ib", "is_finance": 1},
            ("a", "3"): PRODUCT}

    def compared(self, new: dict, **kw) -> tuple[int, str]:
        run = Path(tempfile.mkdtemp(dir=self.dir))
        old = fake_placed(run / "old.db", self.BASE)
        return self.place_compare(old, fake_placed(run / "new.db", {**self.BASE, **new}), **kw)

    def test_a_posting_that_changes_board_fails_unless_that_move_is_allowed(self):
        code, out = self.compared({("a", "1"): self.PRODUCT})
        self.assertEqual(1, code)
        self.assertIn("moved (not allowed):", out)
        self.assertIn("software -> product: 1", out)
        self.assertIn("a:1  'Title' @ Acme  field: 'software' -> 'product'", out)
        self.assertIn("place: FAILED", out)
        for allow in (["software:product"], ["*:product"], ["software:*"]):
            code, out = self.compared({("a", "1"): self.PRODUCT}, allow=allow)
            self.assertEqual(0, code, out)
            self.assertIn("moved (allowed):", out)
        self.assertEqual(1, self.compared({("a", "1"): self.PRODUCT}, allow=["data_ml:product"])[0])
        # An allowed move must still keep its company and location, every country included.
        code, out = self.compared({("a", "1"): {**self.PRODUCT, "city": "ottawa"}}, allow=["*:*"])
        self.assertEqual(1, code)
        self.assertIn("also moved {('software', 'product'): 1}", out)
        self.assertEqual(1, self.compared({("a", "1"): {**self.PRODUCT, "countries": "CA US"}}, allow=["*:*"])[0])
        for wrong in (["product"], ["software:"], ["a:b:c"]):
            with self.assertRaises(SystemExit):
                self.compared({("a", "1"): self.PRODUCT}, allow=wrong)

    def test_a_move_from_or_to_finance_or_other_is_marked_and_must_be_named(self):
        code, out = self.compared({("a", "2"): self.PRODUCT}, allow=["finance:product"])
        self.assertEqual(0, code, out)
        self.assertIn("finance -> product: 1  (changes what Finance shows)", out)
        self.assertIn("(+1 allowed, 1 of them change what Finance shows)", out)
        other = {"field": "other", "family": "other", "category": "other"}
        code, out = self.compared({("a", "1"): other, ("a", "3"): {**other, "field": "software", "family": "software"}})
        self.assertIn("software -> other: 1  (changes what Finance shows)", out)
        self.assertIn("product -> software: 1\n", out)
        # * stands for any board but Finance and "other".
        self.assertEqual(1, self.compared({("a", "2"): self.PRODUCT}, allow=["*:product"])[0])
        self.assertEqual(1, self.compared({("a", "1"): other}, allow=["software:*"])[0])
        self.assertEqual(0, self.compared({("a", "1"): other}, allow=["software:other"])[0])

    def test_a_career_stage_change_off_the_boards_is_listed_without_blocking(self):
        code, out = self.compared({("a", "2"): {**self.BASE["a", "2"], "stage": "senior", "level": "vp"},
                                   ("a", "3"): {**self.PRODUCT, "stage": "new_grad"}}, boards=["product"])
        self.assertEqual(0, code, out)
        self.assertIn("stage changes off the boards (not blocking): {'finance': 1}; internship->senior 1", out)

    def test_filter_changes_pass_only_on_the_boards_named(self):
        change = {("a", "3"): {**self.PRODUCT, "subcategory": "product.growth"}}
        code, out = self.compared(change)
        self.assertEqual(1, code)
        self.assertIn("filter: {'subcategory': 1}", out)
        code, out = self.compared(change, boards=["product"])
        self.assertEqual(0, code, out)
        self.assertIn("inside product 1", out)
        # Another board's filter never may.
        self.assertEqual(1, self.compared({("a", "2"): {**self.BASE["a", "2"], "category": "st"}}, boards=["product"])[0])

    def test_a_known_employer_type_in_place_of_unknown_is_a_label_change(self):
        code, out = self.compared({("a", "1"): {"company_name": "ACME Corp", "company_type": "big_tech"},
                                   ("a", "2"): {**self.BASE["a", "2"], "company_type": "fintech"}})
        self.assertEqual(0, code, out)
        self.assertIn("label changes 2", out)
        self.assertIn("label changes: {'software': 1, 'finance': 1}; renamed 1", out)
        self.assertIn("by board and new type: software big_tech 1, finance fintech 1", out)
        # Another company, or one known type for another, is a change.
        self.assertEqual(1, self.compared({("a", "1"): {"company_key": "acme_corp", "company_type": "big_tech"}})[0])
        old = fake_placed(self.dir / "known.db", {("a", "1"): {"company_type": "big_tech"}})
        new = fake_placed(self.dir / "other.db", {("a", "1"): {"company_type": "startup"}})
        self.assertEqual(1, self.place_compare(old, new)[0])

    def test_postings_missing_or_added_and_location_changes_fail_and_every_change_can_be_written(self):
        old = fake_placed(self.dir / "old.db", self.BASE)
        new = fake_placed(self.dir / "new.db", {("a", "1"): {"location_bucket": "remote"}, ("a", "2"): self.BASE["a", "2"],
                                                ("a", "4"): {}})
        changes = self.dir / "changes.json"
        code, out = self.place_compare(old, new, json_out=changes)
        self.assertEqual(1, code)
        self.assertIn("missing 1, added 1", out)
        self.assertIn("location: {'location_bucket': 1}", out)
        written = json.loads(changes.read_text(encoding="utf-8"))
        self.assertEqual([["a", "3"]], [e["key"] for e in written["missing"]])
        self.assertEqual([["a", "4"]], [e["key"] for e in written["added"]])
        self.assertEqual({"location_bucket": ["toronto", "remote"]}, written["changed"][0]["changes"])


if __name__ == "__main__":
    unittest.main()
