"""The knowledge fingerprint: postings' facts are re-read when, and only when, what they read changes."""

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import watcher
from intel import knowledge
from intel.facts import build_facts
from intel.knowledge import CONFIG_DIR, FILES, Knowledge, config_fingerprint, current_fingerprints
from intel_store import IntelStore
from intel_worker import count_pending_facts
from tests.store.test_store import CONFIG, add_job

ROOT = Path(__file__).resolve().parents[2]

POSTINGS = [
    {"board": "rbc", "id": "1", "title": "2027 Investment Banking Summer Analyst", "location": "Toronto, ON",
     "company": "RBC", "description": "Join our M&A team. Strong Excel and financial modelling skills."},
    {"board": "uhn", "id": "2", "title": "Registered Nurse (RN) - New Grad", "location": "Toronto, ON",
     "company": "University Health Network",
     "description": "Current registered nurse registration with the CNO. BScN required. NCLEX-RN passed."},
    {"board": "shopify", "id": "3", "title": "Software Engineer Intern", "location": "Remote - Canada",
     "company": "Shopify", "description": "Build React front-ends and REST APIs in a Computer Science program."},
    {"board": "pharmacy", "id": "4", "title": "Pharmacist", "location": "Vancouver, BC", "company": "London Drugs",
     "description": "Registered pharmacist licensed with the College of Pharmacists. PharmD preferred."},
]


def copy_config(tmp: str, name: str) -> Path:
    out = Path(tmp) / name
    out.mkdir()
    for f in FILES:
        shutil.copyfile(CONFIG_DIR / f, out / f)
    return out


def edit(root: Path, name: str, change) -> None:
    path = root / name
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def facts(root: Path) -> list[dict]:
    kn = Knowledge(root)
    return [build_facts(job, kn) for job in POSTINGS]


class FingerprintTests(unittest.TestCase):
    def test_layout_and_line_endings_do_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = copy_config(tmp, "crlf")
            for f in FILES:
                data = json.loads((root / f).read_text(encoding="utf-8"))
                (root / f).write_bytes(json.dumps(data, indent=4, ensure_ascii=True).replace("\n", "\r\n").encode())
            self.assertEqual(config_fingerprint(CONFIG_DIR), config_fingerprint(root))

    def test_parts_no_posting_reads_leave_the_fingerprint_and_facts_alone(self):
        def healthcare(data):
            return data["non_finance_families"]["healthcare"]

        def licences(data):
            for item in healthcare(data)["licences"]["items"].values():
                item["resume"], item["degree"] = ["nurse", "pharmac", "analyst"], ["science", "commerce"]

        def tracks(data):
            for track in data["tracks"].values():
                if isinstance(track, dict):
                    track["resume"] = {"degree": "computer science|nursing|commerce", "signals": []}

        def readmes(data):
            data["_readme"] = "changed"
            data["version"] = 999
            healthcare(data)["licences"]["_readme"] = "changed"

        changes = {
            "a licence's resume and degree patterns": ("taxonomy.json", licences),
            "a track's resume reading": ("taxonomy.json", tracks),
            "a board's program windows": ("taxonomy.json", lambda d: healthcare(d)["program_windows"].update(items=[])),
            "readmes and versions": ("taxonomy.json", readmes),
            "another file's readme and version": ("companies.json", lambda d: d.update(_readme="x", version=999)),
        }
        with tempfile.TemporaryDirectory() as tmp:
            expected = facts(CONFIG_DIR)
            for n, (what, (name, change)) in enumerate(changes.items()):
                with self.subTest(what):
                    root = copy_config(tmp, str(n))
                    edit(root, name, change)
                    self.assertEqual(config_fingerprint(CONFIG_DIR), config_fingerprint(root))
                    self.assertEqual(expected, facts(root))

    def test_what_postings_read_changes_the_fingerprint(self):
        def healthcare(data):
            return data["non_finance_families"]["healthcare"]

        changes = {
            "a licence's posting pattern": ("taxonomy.json", lambda d: healthcare(d)["licences"]["items"]["rn"]
                                            ["description"].append("rn permit")),
            "a licence's label": ("taxonomy.json", lambda d: healthcare(d)["licences"]["items"]["rn"]
                                  .update(label="RN")),
            "pending registration phrases": ("taxonomy.json", lambda d: healthcare(d)["licences"].update(pending=[])),
            "a track's employer noun": ("taxonomy.json", lambda d: d["tracks"]["tech"].update(employer_noun="x")),
            "a company": ("companies.json", lambda d: d["companies"].pop(0)),
            "a city": ("locations.json", lambda d: d["cities"].pop(0)),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for n, (what, (name, change)) in enumerate(changes.items()):
                with self.subTest(what):
                    root = copy_config(tmp, str(n))
                    edit(root, name, change)
                    self.assertNotEqual(config_fingerprint(CONFIG_DIR), config_fingerprint(root))

    @unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "needs the git checkout")
    def test_legacy_fingerprints_are_the_releases(self):
        """Each LEGACY_FINGERPRINTS entry is a release's byte fingerprint (CRLF and LF) beside config_fingerprint()
        of the same files."""
        found = {}
        for tag in ("v0.3.12", "v0.3.13"):
            try:
                raw = {f: subprocess.run(["git", "show", f"{tag}:config/{f}"], capture_output=True, cwd=ROOT,
                                         check=True).stdout.replace(b"\r\n", b"\n") for f in FILES}
            except subprocess.CalledProcessError:
                self.skipTest(f"{tag} is not in this checkout")
            with tempfile.TemporaryDirectory() as tmp:
                for f, data in raw.items():
                    (Path(tmp) / f).write_bytes(data)
                new = config_fingerprint(tmp)
            for crlf in (True, False):
                digest = hashlib.sha1()
                for f in FILES:
                    digest.update(raw[f].replace(b"\n", b"\r\n") if crlf else raw[f])
                found[digest.hexdigest()[:12]] = new
        self.assertEqual(found, knowledge.LEGACY_FINGERPRINTS)


class StoreFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        for job_id in ("1", "2", "3"):
            add_job(self.con, "rbc", job_id, f"2027 Investment Banking Summer Analyst {job_id}")
        add_job(self.con, "linkedin_ca", "9", "2027 Investment Banking Summer Analyst",
                "Toronto, Ontario, Canada", "RBC Capital Markets")
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()

    def kb(self, job_id, value):
        self.con.execute("UPDATE job_intel SET kb_version=? WHERE board='rbc' AND job_id=?", (value, job_id))
        self.con.commit()

    def test_facts_from_an_older_release_that_read_the_same_stay_current(self):
        current = config_fingerprint()
        with mock.patch.dict(knowledge.LEGACY_FINGERPRINTS, {"0ldbytes0000": current, "0therold0000": "elsewhere"},
                             clear=True):
            self.assertEqual((current, "0ldbytes0000"), current_fingerprints())
            self.kb("1", "0ldbytes0000")
            self.kb("2", "0therold0000")
            self.kb("3", "5tale0000000")
            self.assertEqual(2, count_pending_facts(self.con, fits=False))
            self.assertEqual(2, IntelStore(self.con, CONFIG).facts_pass())
        rows = dict(self.con.execute("SELECT job_id, kb_version FROM job_intel WHERE board='rbc'"))
        self.assertEqual({"1": "0ldbytes0000", "2": current, "3": current}, rows)

    def test_a_source_whose_fact_settings_change_is_read_again(self):
        changed = json.loads(json.dumps(CONFIG))
        changed["boards"]["rbc"]["company_key"] = "td"
        self.assertEqual(3, IntelStore(self.con, changed).refresh()["facts"])
        self.assertEqual(0, IntelStore(self.con, changed).refresh()["facts"])
        moved = {"profile": {}, "boards": {"_us_banks": "---", **{k: v for k, v in changed["boards"].items()
                                                                     if not k.startswith("_")}}}
        self.assertEqual(4, IntelStore(self.con, moved).refresh()["facts"])
        renamed = json.loads(json.dumps(moved))
        renamed["boards"]["rbc"]["token"] = "royal"     # facts don't read it
        self.assertEqual(0, IntelStore(self.con, renamed).refresh()["facts"])

    def test_the_first_run_records_source_settings_without_reading_again(self):
        self.con.execute("DELETE FROM kv WHERE k='source_fact_settings'")
        self.con.commit()
        changed = json.loads(json.dumps(CONFIG))
        changed["boards"]["rbc"]["company_type"] = "big_bank"
        self.assertEqual(0, IntelStore(self.con, changed).refresh()["facts"])
        self.assertIsNotNone(self.con.execute("SELECT v FROM kv WHERE k='source_fact_settings'").fetchone())
        self.assertEqual(0, IntelStore(self.con, changed).refresh()["facts"])


if __name__ == "__main__":
    unittest.main()
