"""Private resume preview/apply and SQL filtering integration."""
import base64
import json
import unittest
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import test_dashboard as fixtures
from dashboard import ApiError, JobwatchService, JobwatchHandler
from test_resume_matching import RESUME


class ResumeServiceTests(fixtures.ServiceFixture):
    def apply(self):
        with patch.object(self.service, "kick"):
            result = self.service.apply_resume({"text": RESUME})
        self.service.refresh_now()
        return result

    def test_preview_is_non_mutating_and_apply_persists_only_matching_facts(self):
        before = self.service.get_profile()
        preview = self.service.parse_resume({"text": RESUME})
        self.assertEqual(2028, preview["profile"]["graduation_year"])
        self.assertEqual(before, self.service.get_profile())
        self.assertFalse(self.service.get_resume()["available"])
        self.apply()
        reopened = JobwatchService(self.db_path, self.config_path, self.subscribers_path)
        saved = reopened.get_resume()
        self.assertTrue(saved["enabled"])
        self.assertEqual(2028, reopened.get_profile()["profile"]["graduation_year"])
        self.assertNotIn("name", saved["parsed"])
        self.assertNotIn("bullets", saved["parsed"])
        self.assertEqual(0, saved["pending"])

    def test_automatic_filter_can_be_disabled_and_removed_without_losing_profile(self):
        self.apply()
        result = self.service.jobs({})
        self.assertTrue(result["resume_matching"]["active"])
        self.assertEqual(["rbc:one"], [j["key"] for j in result["jobs"]])
        self.assertGreater(self.service.jobs({"resume_match": "0"})["total"], result["total"])
        self.assertTrue(self.service.job_detail("rbc:one")["resume_match"]["matched"])
        self.assertFalse(self.service.job_detail("demo_quant:two")["resume_match"]["matched"])
        self.service.set_resume_enabled({"enabled": False})
        self.assertFalse(self.service.jobs({})["resume_matching"]["active"])
        self.service.delete_resume()
        self.assertFalse(self.service.get_resume()["available"])
        self.assertIsNone(self.service.job_detail("rbc:one")["resume_match"])
        self.assertEqual(2028, self.service.get_profile()["profile"]["graduation_year"])

    def test_profile_changes_never_return_stale_matches(self):
        from intel_store import IntelStore
        self.apply()
        with self.service.db() as old_con:
            old_store = IntelStore(old_con, self.service.config)
            self._change_targets_and_check()
            self.assertEqual(0, old_store.score_pass(force=True))
        self.service.refresh_now()
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertEqual(0, self.service.get_resume()["pending"])

    def _change_targets_and_check(self):
        profile = self.service.get_profile()["profile"]
        profile["target_roles"] = ["public_markets.asset_management"]
        with patch.object(self.service, "kick"):
            self.service.put_profile({"profile": profile})
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertGreater(self.service.get_resume()["pending"], 0)
        self.assertIsNone(self.service.job_detail("rbc:one")["resume_match"])

    def test_input_validation_and_base64_file(self):
        payload = {"filename": "resume.txt", "data": base64.b64encode(RESUME.encode()).decode()}
        self.assertEqual(2028, self.service.parse_resume(payload)["parsed"]["education"]["graduation_year"])
        for bad in ({}, {"text": "short"}, {"text": ["bad"]}, {"text": "a" * 60001},
                    {"filename": "x.pdf", "data": "???"}, {"filename": "x.exe", "data": payload["data"]},
                    {"filename": "x.txt", "data": base64.b64encode(b"x" * 5000001).decode()}):
            with self.subTest(keys=list(bad)), self.assertRaises(ApiError):
                self.service.parse_resume(bad)
        with self.assertRaises(ApiError):
            self.service.set_resume_enabled({"enabled": True})

    def test_private_resume_absent_from_exports_and_csv_uses_same_filter(self):
        import watcher
        self.apply()
        with self.service.db() as con:
            marker = "PRIVATE_RESUME_MARKER"
            con.execute("UPDATE candidate_resume SET filename=?", (marker,))
            export = self.config_path.parent / "state.json"
            with patch.object(watcher, "STATE_JSON", export):
                watcher.export_state(con)
        self.assertNotIn(marker, export.read_text())
        csv = self.service.csv_export({})
        self.assertIn("Investment Banking", csv)
        self.assertNotIn("Quantitative Researcher", csv)
        self.assertNotIn(marker, csv)
        self.assertIn("Quantitative Researcher", self.service.csv_export({"resume_match": "0"}))

    def test_incomplete_or_invalid_replacement_preserves_saved_facts(self):
        self.apply()
        before = self.service.get_resume()
        for payload in ({"text": "SKILLS\nExcel\nThis is just a fragment of a skills section."},
                        {"filename": "broken.pdf", "data": "aW52YWxpZA=="}):
            with self.assertRaises(ApiError):
                self.service.apply_resume(payload)
        self.assertEqual(before, self.service.get_resume())

    def test_profile_edit_during_scoring_cannot_revive_old_matches(self):
        from intel_store import IntelStore, score_job
        self.apply()
        changed = False
        def score_with_intervening_edit(*args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                profile = self.service.get_profile()["profile"]
                profile["target_roles"] = ["public_markets.asset_management"]
                with patch.object(self.service, "kick"):
                    self.service.put_profile({"profile": profile})
            return score_job(*args, **kwargs)
        with self.service.db() as con:
            old = IntelStore(con, self.service.config)
            with patch('intel_store.score_job', side_effect=score_with_intervening_edit):
                old.score_pass(force=True)
            self.assertNotEqual(old.version, con.execute("SELECT version FROM candidate_resume").fetchone()[0])
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertIsNone(self.service.job_detail('rbc:one')["resume_match"])

    def test_reindex_publishes_fresh_batches_and_counts_unindexed_jobs(self):
        from intel import FACTS_VERSION
        from intel_store import IntelStore
        self.apply()
        with self.service.db() as con:
            con.execute("UPDATE job_intel SET facts_version=0")
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertIsNone(self.service.job_detail('rbc:one')["resume_match"])
        with self.service.db() as con:
            stats = IntelStore(con, self.service.config).refresh(max_facts=1)
            self.assertEqual(1, stats['facts'])
            self.assertEqual(1, stats['scored'])
            con.execute("INSERT INTO jobs VALUES ('new','unindexed','Investment Banking Intern','','https://example.com/new','','')")
        self.assertGreater(self.service.get_resume()["pending"], 0)
        self.service.refresh_now()
        self.assertEqual(0, self.service.get_resume()["pending"])

    def test_saved_view_counts_and_notification_queries_share_resume_defaults(self):
        import watcher
        from intel_store import IntelStore
        self.apply()
        for query in ({}, {"resume_match": "1"}, {"resume_match": "0"}):
            with self.service.db() as con:
                con.execute("DELETE FROM saved_searches")
                con.execute("INSERT INTO saved_searches(name,query,notify,created_at) VALUES ('Test',?,1,'2020-01-01')", (json.dumps(query),))
            for enabled in (True, False):
                with patch.object(self.service, "kick"):
                    self.service.set_resume_enabled({"enabled": enabled})
                expected = self.service.saved_searches()["saved_searches"][0]["total"]
                with self.service.db() as con, patch.object(watcher, "send_discord_note") as send:
                    con.execute("UPDATE saved_searches SET last_notified_at=NULL")
                    count = watcher.notify_saved_searches({}, con, [{"saved_search_alerts": True, "discord": "test"}], IntelStore(con, self.service.config))
                    self.assertEqual(expected, count)
                    self.assertTrue(send.called)


class ResumeHttpTests(fixtures.ServiceFixture):
    def setUp(self):
        super().setUp()
        handler = type("ResumeTestHandler", (JobwatchHandler,), {"service": self.service})
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

    def test_resume_routes_and_upload_request_bounds(self):
        self.assertFalse(self.call("GET", "/api/resume")[1]["available"])
        # A legitimate upload can exceed the normal 200KB JSON cap.
        text = RESUME + "\n" + "✨" * 52000
        payload = {"filename": "resume.txt", "data": base64.b64encode(text.encode()).decode()}
        self.assertGreater(len(json.dumps(payload)), 200000)
        self.assertEqual(200, self.call("POST", "/api/resume/parse", payload)[0])
        self.assertEqual(200, self.call("POST", "/api/resume", {"text": RESUME})[0])
        self.service.refresh_now()
        self.assertEqual(1, self.call("GET", "/api/jobs")[1]["total"])
        self.assertEqual(200, self.call("PATCH", "/api/resume", {"enabled": False})[0])
        self.assertFalse(self.call("GET", "/api/jobs")[1]["resume_matching"]["active"])
        self.assertEqual(200, self.call("DELETE", "/api/resume")[0])
        self.assertFalse(self.call("GET", "/api/resume")[1]["available"])
        self.assertEqual(400, self.call("POST", "/api/resume/parse", {"text": "bad"})[0])
        self.assertEqual(405, self.call("PUT", "/api/resume", {})[0])
        self.assertEqual(403, self.call("POST", "/api/resume", {"text": RESUME}, {"Origin":"https://evil.example"})[0])
        self.assertEqual(415, self.call("POST", "/api/resume", {"text": RESUME}, {"Content-Type":"text/plain"})[0])
        # Repeat real oversized bodies: closing with unread data used to reset
        # the Windows connection intermittently instead of delivering HTTP 413.
        for _ in range(6):
            self.assertEqual(413, self.call("POST", "/api/profile", payload)[0])
        self.assertEqual(413, self.call("POST", "/api/resume", {}, {"Content-Length":"6700001"})[0])
        for length in ("invalid", "-1"):
            self.assertEqual(400, self.call("POST", "/api/resume", {}, {"Content-Length":length})[0])


if __name__ == "__main__":
    unittest.main()
