"""tools/resume_record.py: the same code reads the fixture resumes the same way; a changed reading is named."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from tools import resume_record

ROOT = Path(__file__).resolve().parents[2]


class ResumeRecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def compare(self, old, new) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out):
            code = resume_record.compare(old, new)
        return code, out.getvalue()

    def test_every_fixture_and_helper_the_recorder_reads_exists(self):
        # A rename in the tests would otherwise only show as "skipped" in a recording.
        helpers = [("tests.resume.test_resume_tech", n) for n in ("pdf", "CS_LINES")] + \
                  [("tests.resume.test_resume_health", n) for n in ("plain_lines", "latex_lines", "word_docx")]
        for module, attr in [*resume_record.FIXTURES.values(), *helpers]:
            with self.subTest(name=attr):
                self.assertTrue(resume_record._helper(module, attr))

    def test_the_same_code_reads_each_fixture_in_each_form_and_profile_the_same_way(self):
        only = ["finance", "nursing", "pharmacy"]
        a = resume_record.record(ROOT, self.dir / "a.json", only=only)
        resume_record.record(ROOT, self.dir / "b.json", only=only)
        self.assertEqual({f"{n}/{f}{f'@{p}' if p else ''}" for n in only for f in resume_record.FORMS
                          for p in ("", *resume_record.PROFILES)}, set(a["results"]))
        self.assertEqual([], [k for k, e in a["results"].items() if "skipped" in e or "crash" in e["result"]])
        nursing = a["results"]["nursing/text"]["result"]
        self.assertIn("healthcare", nursing["profile"]["fields"])
        self.assertEqual("nursing.pdf", a["results"]["nursing/latex"]["result"]["filename"])
        self.assertEqual(nursing["parsed"]["education"], a["results"]["nursing/docx"]["result"]["parsed"]["education"])
        # The profile a resume proposes starts from the saved one.
        self.assertNotEqual(nursing["changes"], a["results"]["nursing/text@healthcare"]["result"]["changes"])
        # The PharmD sets no education level, and a resume without one is read (987ecc9), not refused.
        pharmacy = a["results"]["pharmacy/text"]["result"]
        self.assertNotIn("error", pharmacy)
        self.assertEqual(["healthcare"], pharmacy["profile"]["fields"])
        self.assertIsNone(pharmacy["parsed"]["education"]["level"])
        self.assertTrue(pharmacy["parsed"]["roles"])
        code, out = self.compare(self.dir / "a.json", self.dir / "b.json")
        self.assertEqual(0, code, out)
        self.assertIn("resumes: passed", out)
        with self.assertRaises(SystemExit):
            resume_record.record(ROOT, self.dir / "a.json", only=["finance"])
        with self.assertRaises(SystemExit):
            resume_record.record(ROOT, self.dir / "x.json", only=["finanse"])

        # A changed reading, a changed document, key order, a missing one and a new skip each fail, by name.
        changed = json.loads((self.dir / "b.json").read_text(encoding="utf-8"))
        results = changed["results"]
        results["nursing/text"]["result"]["parsed"]["education"]["level"] = "phd"
        results["pharmacy/pdf"]["result"]["parsed"]["roles"][0]["title"] = "Pharmacist"
        results["finance/pdf"]["input"] = "0" * 16
        del results["finance/docx"]
        results["finance/text"] = {"skipped": "AttributeError"}
        moved = results["nursing/pdf"]["result"]
        results["nursing/pdf"]["result"] = {"profile": moved.pop("profile"), **moved}
        results["design/text"] = {"input": "1" * 16, "result": {}}
        (self.dir / "c.json").write_text(json.dumps(changed), encoding="utf-8")
        code, out = self.compare(self.dir / "a.json", self.dir / "c.json")
        self.assertEqual(1, code)
        self.assertIn("changed: nursing/text: result.parsed.education.level", out)
        self.assertIn("changed: pharmacy/pdf: result.parsed.roles[0].title", out)
        self.assertIn("changed: nursing/pdf: key order", out)
        self.assertIn("input changed: finance/pdf", out)
        self.assertIn("missing: finance/docx", out)
        self.assertIn("skipped now: finance/text", out)
        self.assertIn("added: design/text", out)
        self.assertIn("resumes: FAILED", out)
        # A fixture the old checkout lacked and the new one has is an addition, not a change.
        older = json.loads((self.dir / "a.json").read_text(encoding="utf-8"))
        older["results"]["finance/text"] = {"skipped": "AttributeError"}
        (self.dir / "d.json").write_text(json.dumps(older), encoding="utf-8")
        code, out = self.compare(self.dir / "d.json", self.dir / "a.json")
        self.assertEqual(0, code, out)
        self.assertIn("now recorded: finance/text", out)
        # Recordings taken with different clocks don't compare.
        older["results"]["finance/text"] = a["results"]["finance/text"]
        older["utc_offset"] += 3600
        (self.dir / "e.json").write_text(json.dumps(older), encoding="utf-8")
        self.assertEqual(1, self.compare(self.dir / "e.json", self.dir / "a.json")[0])


if __name__ == "__main__":
    unittest.main()
