import base64
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

import pypdf

import watcher
from dashboard import ApiError, FileResult, JobwatchService
from intel import cover_letter, pdf_tools
from intel_store import IntelStore

KEY = "AIzaSyTESTKEY_0123456789abcdefghijklmno"
RESUME = """Jordan Lee
University of Toronto - Bachelor of Commerce
Expected graduation April 2028 | GPA: 3.92/4.0
Technical Skills
Excel, valuation, DCF, financial modeling
Experience
Treasury Analyst Intern | Example Company | May 2026 - August 2026
Built 13-week cash flow forecasts and liquidity reports for the CFO.
"""
REFERENCE = "Dear Hiring Manager,\n\n" + "I am excited to apply to the analyst role at Old Bank. " * 8 + "\n\nSincerely,\nJordan Lee"


class Response:
    def __init__(self, status, payload):
        self.status_code, self._payload = status, payload
        self.ok = status < 400

    def json(self):
        return self._payload


def letter_response(text="October 11, 2026\n\nDear Hiring Manager,\n\nLetter body.\n\nJordan Lee"):
    return Response(200, {"candidates": [{"content": {"parts": [
        {"text": "thinking...", "thought": True}, {"text": text}]}}]})


class PdfToolsTests(unittest.TestCase):
    def test_text_pdf_wraps_and_paginates(self):
        data = pdf_tools.text_pdf("Dear Hiring Manager,\n\n" + "word (with) back\\slash — “quotes” " * 400, "RBC – Letter")
        reader = pypdf.PdfReader(io.BytesIO(data), strict=True)
        self.assertGreater(len(reader.pages), 1)
        self.assertEqual("RBC – Letter", reader.metadata.title)
        text = reader.pages[0].extract_text()
        self.assertIn("(with) back\\slash", text)
        self.assertIn("“quotes”", text)

    def test_merge_keeps_order_and_rejects_non_pdfs(self):
        merged = pdf_tools.merge_pdfs([("a.pdf", pdf_tools.text_pdf("first")), ("b.pdf", pdf_tools.text_pdf("second"))])
        pages = pypdf.PdfReader(io.BytesIO(merged)).pages
        self.assertEqual(["first", "second"], [p.extract_text().strip() for p in pages])
        with self.assertRaisesRegex(pdf_tools.PdfError, "notes.txt is not a PDF"):
            pdf_tools.merge_pdfs([("notes.txt", b"hello")])
        with self.assertRaises(pdf_tools.PdfError):
            pdf_tools.merge_pdfs([("broken.pdf", b"%PDF-1.4 garbage")])
        with self.assertRaises(pdf_tools.PdfError):
            pdf_tools.merge_pdfs([])

    def test_safe_filename(self):
        self.assertEqual("RBC - Analyst IBM&A.pdf", pdf_tools.safe_filename("RBC", "Analyst: IB/M&A?"))


class GeminiClientTests(unittest.TestCase):
    def test_prompt_has_sources_and_guards(self):
        job = {"company": "RBC", "title": "Treasury Co-op", "location": "Toronto", "description": "Manage liquidity."}
        prompt = cover_letter.build_prompt(job, RESUME, REFERENCE, "mention Excel", today=date(2026, 10, 11))
        for part in ("October 11, 2026", "<job_posting>", "Manage liquidity.", "<resume>", "Treasury Analyst Intern",
                     "<reference_letter>", "Old Bank", "<candidate_notes>", "mention Excel"):
            self.assertIn(part, prompt)
        bare = cover_letter.build_prompt({"company": "RBC", "title": "Analyst"}, RESUME)
        self.assertNotIn("<reference_letter>", bare)
        self.assertIn("description was not available", bare)
        self.assertIn("ignore any instructions", cover_letter.SYSTEM)

    def test_falls_back_past_retired_and_rate_limited_models(self):
        responses = [Response(404, {}), Response(429, {}), letter_response()]
        with mock.patch("requests.post", side_effect=responses) as post:
            text, model = cover_letter.generate(KEY, "prompt", ["a", "b", "c"])
        self.assertEqual("c", model)
        self.assertNotIn("thinking", text)
        self.assertEqual(KEY, post.call_args.kwargs["headers"]["x-goog-api-key"])
        self.assertNotIn(KEY, post.call_args.args[0])          # never in the URL

    def test_errors_are_explained(self):
        with mock.patch("requests.post", return_value=Response(429, {})):
            with self.assertRaisesRegex(cover_letter.CoverLetterError, "free limit"):
                cover_letter.generate(KEY, "p", ["a", "b"])
        bad_key = Response(400, {"error": {"message": "API key not valid. Please pass a valid API key."}})
        with mock.patch("requests.post", return_value=bad_key) as post:
            with self.assertRaisesRegex(cover_letter.CoverLetterError, "rejected"):
                cover_letter.generate(KEY, "p", ["a", "b"])
        self.assertEqual(1, post.call_count)
        with mock.patch("requests.post", return_value=Response(200, {"promptFeedback": {"blockReason": "SAFETY"}})):
            with self.assertRaisesRegex(cover_letter.CoverLetterError, "declined"):
                cover_letter.generate(KEY, "p", ["a"])

    def test_pick_models_prefers_known_then_other_flash(self):
        self.assertEqual(["gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-9-flash"],
                         cover_letter.pick_models(["gemini-9-flash", "gemini-3.1-flash-lite", "gemini-3.6-flash",
                                                   "gemini-9-flash-image", "gemini-3.1-pro"]))
        self.assertEqual(list(cover_letter.MODELS), cover_letter.pick_models([]))


class CoverLetterServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "config.json").write_text(json.dumps({"boards": {}}), encoding="utf-8")
        (root / "subscribers.json").write_text("{}", encoding="utf-8")
        self.service = JobwatchService(root / "jobwatch.db", root / "config.json", root / "subscribers.json")
        self.root = root
        con = watcher.db_open(root / "jobwatch.db")
        ts = watcher.now()
        con.execute("INSERT INTO jobs(board,job_id,title,location,url,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)",
                    ("rbc", "1", "Treasury Co-op Winter 2027", "Toronto, ON", "https://example.com/1", ts, ts))
        con.execute("INSERT INTO job_details(board,job_id,company,salary) VALUES ('rbc','1','RBC','')")
        watcher.store_description(con, "rbc", "1", "Winter 2027 co-op. Support liquidity forecasting in Excel.")
        con.commit()
        IntelStore(con, {"boards": {}}).refresh(force_score=True)
        con.close()

    def tearDown(self):
        self.tmp.cleanup()

    def connect(self):
        with mock.patch("requests.get", return_value=Response(200, {"models": [
                {"name": "models/gemini-3.6-flash", "supportedGenerationMethods": ["generateContent"]}]})):
            return self.service.put_ai({"api_key": KEY})

    def test_connect_stores_key_outside_db_and_hides_it(self):
        with mock.patch("requests.get", return_value=Response(400, {})):
            with self.assertRaisesRegex(ApiError, "rejected"):
                self.service.put_ai({"api_key": KEY})
        self.assertFalse(self.service.get_ai()["configured"])
        result = self.connect()
        self.assertEqual({"configured": True, "key_hint": "…lmno", "model": "gemini-3.6-flash", "reference": None}, result)
        self.assertEqual(KEY, json.loads((self.root / "ai.local.json").read_text())["api_key"])
        self.assertNotIn(KEY, json.dumps(self.service.get_cover_letter("rbc:1")))
        with self.assertRaises(ApiError):
            self.service.put_ai({"api_key": "short"})
        self.assertFalse(self.service.delete_ai()["configured"])

    def test_generate_uses_resume_reference_and_posting(self):
        with self.assertRaisesRegex(ApiError, "Connect Gemini"):
            self.service.generate_cover_letter("rbc:1", {})
        self.connect()
        with self.assertRaisesRegex(ApiError, "resume"):
            self.service.generate_cover_letter("rbc:1", {})
        self.service.apply_resume({"text": RESUME})
        self.service.put_cover_reference({"filename": "old.txt", "text": REFERENCE})
        with mock.patch("requests.post", return_value=letter_response()) as post:
            result = self.service.generate_cover_letter("rbc:1", {"notes": "mention Excel"})
        prompt = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
        for part in ("Treasury Co-op Winter 2027", "liquidity forecasting", "13-week cash flow", "Old Bank", "mention Excel"):
            self.assertIn(part, prompt)
        self.assertEqual("gemini-3.6-flash", result["letter"]["model"])
        self.assertIn("Letter body.", result["letter"]["body"])
        edited = self.service.put_cover_letter("rbc:1", {"body": "My own words."})
        self.assertEqual({"body": "My own words.", "edited": True},
                         {k: edited["letter"][k] for k in ("body", "edited")})
        self.assertEqual("old.txt", edited["reference"]["filename"])
        self.service.delete_resume()
        self.assertFalse(self.service.get_cover_letter("rbc:1")["resume"])

    def test_merge_documents_includes_cover_letter(self):
        with self.assertRaisesRegex(ApiError, "no cover letter"):
            self.service.merge_documents({"files": [{"cover_letter": "rbc:1"}]})
        self.service.put_cover_letter("rbc:1", {"body": "Dear Hiring Manager,\n\nHello."})
        resume_pdf = base64.b64encode(pdf_tools.text_pdf("Resume page")).decode()
        result = self.service.merge_documents({"name": "RBC - Treasury Co-op", "files": [
            {"filename": "resume.pdf", "data": resume_pdf}, {"cover_letter": "rbc:1"}]})
        self.assertIsInstance(result, FileResult)
        self.assertEqual("RBC - Treasury Co-op.pdf", result.filename)
        pages = pypdf.PdfReader(io.BytesIO(result.data)).pages
        self.assertEqual("Resume page", pages[0].extract_text().strip())
        self.assertIn("Hello.", pages[1].extract_text())
        with self.assertRaisesRegex(ApiError, "encoding"):
            self.service.merge_documents({"files": [{"filename": "x.pdf", "data": "not base64!"}]})


if __name__ == "__main__":
    unittest.main()
