"""Cover letters use supplied facts and remain private, per-job drafts."""
import unittest
import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

from dashboard import ApiError, JobwatchHandler, JobwatchService
import test_dashboard as fixtures


BACKGROUND = "I built a valuation model for a student investment fund. I presented our analysis to a team of six."
INPUT = {"candidate_name": "Alex Chen", "background": BACKGROUND,
         "motivation": "I would like to contribute to your M&A team."}


class CoverLetterServiceTests(fixtures.ServiceFixture):
    def test_preview_uses_supplied_facts_without_saving_or_changing_profile(self):
        before = self.service.get_profile()
        result = self.service.generate_cover_letter("rbc:one", INPUT)
        letter = result["cover_letter"]
        for text in ("Alex Chen", "RBC", "2027 Investment Banking Summer Analyst", BACKGROUND, INPUT["motivation"]):
            self.assertIn(text, letter["content"])
        self.assertNotIn("Bloomberg", letter["content"])
        self.assertNotIn("My search", letter["content"])
        self.assertIsNone(self.service.get_cover_letter("rbc:one")["cover_letter"])
        self.assertEqual(before, self.service.get_profile())

    def test_save_edit_reopen_and_isolate_jobs(self):
        draft = self.service.generate_cover_letter("rbc:one", INPUT)["cover_letter"]
        saved = self.service.save_cover_letter("rbc:one", draft)["cover_letter"]
        self.assertTrue(saved["created_at"])
        edited = {**saved, "content": "Dear Hiring Team,\n\nMy edited letter.\n\nAlex"}
        updated = self.service.save_cover_letter("rbc:one", edited)["cover_letter"]
        reopened = JobwatchService(self.db_path, self.config_path, self.subscribers_path)
        self.assertEqual(edited["content"], reopened.get_cover_letter("rbc:one")["cover_letter"]["content"])
        self.assertEqual(saved["created_at"], updated["created_at"])
        self.assertEqual(updated, reopened.job_detail("rbc:one")["cover_letter"])
        self.assertIsNone(reopened.job_detail("demo_quant:two")["cover_letter"])
        # Generating again never replaces the saved edits.
        self.service.generate_cover_letter("rbc:one", {**INPUT, "candidate_name": "Other"})
        self.assertEqual(edited["content"], self.service.get_cover_letter("rbc:one")["cover_letter"]["content"])
        self.assertIsNone(self.service.job_detail("rbc:one")["application"])

    def test_invalid_and_oversized_input_is_rejected(self):
        for payload in ({}, {**INPUT, "candidate_name": " "}, {**INPUT, "background": " "},
                        {**INPUT, "candidate_name": ["Alex"]}, {**INPUT, "background": "a" * 20001},
                        {**INPUT, "motivation": {"text": "x"}}):
            with self.subTest(payload=list(payload)):
                with self.assertRaises(ApiError) as error:
                    self.service.generate_cover_letter("rbc:one", payload)
                self.assertEqual(400, error.exception.status)
        for content in ("", " ", None, ["text"], "a" * 30001):
            with self.subTest(content_type=type(content).__name__):
                with self.assertRaises(ApiError):
                    self.service.save_cover_letter("rbc:one", {**INPUT, "content": content})

    def test_unknown_job_returns_404_for_all_operations(self):
        for action in (lambda: self.service.get_cover_letter("rbc:missing"),
                       lambda: self.service.generate_cover_letter("rbc:missing", INPUT),
                       lambda: self.service.save_cover_letter("rbc:missing", {**INPUT, "content": "Letter"})):
            with self.assertRaises(ApiError) as error:
                action()
            self.assertEqual(404, error.exception.status)

    def test_migration_can_reopen_without_losing_letters(self):
        import watcher
        self.service.save_cover_letter("rbc:one", {**INPUT, "content": "Saved text"})
        con = watcher.db_open(self.db_path)
        con.close()
        self.assertEqual("Saved text", self.service.get_cover_letter("rbc:one")["cover_letter"]["content"])

    def test_private_text_is_absent_from_portable_state_and_csv(self):
        import watcher
        marker = "PRIVATE_COVER_LETTER_123"
        self.service.save_cover_letter("rbc:one", {**INPUT, "content": marker, "background": marker})
        export_path = self.config_path.parent / "state.json"
        with patch.object(watcher, "STATE_JSON", export_path), self.service.db() as con:
            watcher.export_state(con)
        self.assertNotIn(marker, export_path.read_text())
        self.assertNotIn(marker, self.service.csv_export({}))


class CoverLetterHttpTests(fixtures.ServiceFixture):
    def setUp(self):
        super().setUp()
        handler = type("CoverLetterHandler", (JobwatchHandler,), {"service": self.service})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def call(self, method, path, body=None, headers=None):
        request = urllib.request.Request(self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = urllib.request.urlopen(request, timeout=10)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_cover_letter_routes(self):
        path = "/api/jobs/rbc%3Aone/cover-letter"
        self.assertEqual((200, {"cover_letter": None}), self.call("GET", path))
        status, body = self.call("POST", path + "/generate", INPUT)
        self.assertEqual(200, status)
        draft = body["cover_letter"]
        self.assertIn(BACKGROUND, draft["content"])
        self.assertIsNone(self.call("GET", path)[1]["cover_letter"])
        status, body = self.call("PUT", path, {**draft, "content": "Edited via HTTP"})
        self.assertEqual(200, status)
        self.assertEqual("Edited via HTTP", self.call("GET", path)[1]["cover_letter"]["content"])
        self.assertEqual(400, self.call("PUT", path, {"content": ""})[0])
        self.assertEqual(400, self.call("POST", path + "/generate", {})[0])
        self.assertEqual(404, self.call("POST", "/api/jobs/missing/cover-letter/generate", INPUT)[0])
        self.assertEqual(405, self.call("DELETE", path)[0])
        self.assertEqual(403, self.call("PUT", path, {**draft}, {"Origin": "https://evil.example"})[0])


if __name__ == "__main__":
    unittest.main()
