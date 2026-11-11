"""Private resume preview/apply and SQL filtering integration.

The fixture's resume targets Treasury, Real Estate and FP&A. Its Treasury posting is on the short list (the default
list); the Investment Banking one is a finance role outside those targets: eligible, shown with shortlist=0."""
import base64
import json
import time
import unittest
import threading
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import watcher
from tests.app import test_dashboard as fixtures
from dashboard import ApiError, JobwatchService, JobwatchHandler
from intel import FACTS_VERSION
from tests.resume.test_resume_health import NURSING, word_docx
from tests.resume.test_resume_matching import RESUME


SECOND_RESUME = """TEST CANDIDATE
EDUCATION
Example University - Bachelor of Computer Science
Expected Graduation: May 2028
EXPERIENCE
QA Engineer Intern, Example Software | May 2026 - Aug 2026
- Wrote test plans and test cases, ran regression testing before each release and triaged defects in Jira.
Software Test Co-op, Example Devices | Jan 2025 - Apr 2025
- Automated regression tests in Python and Selenium and reported defects to developers.
SKILLS
Software Testing, Test Automation, Selenium, Python, SQL, Jira
"""


class ResumeFixture(fixtures.ServiceFixture):
    """The service fixture plus one posting in a specialty the resume shows (Treasury): the short list."""
    def setUp(self):
        super().setUp()
        con = watcher.db_open(self.db_path)
        now = watcher.now()
        con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", ("rbc", "treasury", "2027 Treasury Summer Analyst",
                                                                "Toronto, ON", "https://example.com/treasury", now, now))
        con.execute("INSERT INTO job_details VALUES (?,?,?,?,?)", ("rbc", "treasury", "RBC", "", time.time() - 3600))
        con.commit()
        con.close()
        self.service.refresh_now()


class ResumeServiceTests(ResumeFixture):
    def apply(self, text=RESUME):
        with patch.object(self.service, "kick"):
            result = self.service.apply_resume({"text": text})
        self.service.refresh_now()
        return result

    def keys(self, **query):
        return sorted(j["key"] for j in self.service.jobs(query)["jobs"])

    def age(self, job_id, seen_days=0, posted_days=0, deadline=None):
        """Make a stored posting last seen and posted this many days ago, with this deadline."""
        seen = datetime.fromtimestamp(time.time() - seen_days * 86400, timezone.utc).isoformat(timespec="seconds")
        with self.service.db() as con:
            con.execute("UPDATE jobs SET last_seen=? WHERE job_id=?", (seen, job_id))
            con.execute("UPDATE job_intel SET posted_ref=?, eff_deadline=? WHERE job_id=?",
                        (time.time() - posted_days * 86400, deadline, job_id))

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
        self.assertEqual(["rbc:treasury"], [j["key"] for j in result["jobs"]])      # the short list
        self.assertEqual(["rbc:one", "rbc:treasury"], self.keys(shortlist="0"))     # every eligible role
        self.assertGreater(self.service.jobs({"resume_match": "0"})["total"], len(self.keys(shortlist="0")))
        self.assertTrue(self.service.job_detail("rbc:treasury")["resume_match"]["shortlist"])
        # Eligible and off the list is still a match, and says why it isn't on the list.
        outside = self.service.job_detail("rbc:one")["resume_match"]
        self.assertTrue(outside["matched"])
        self.assertEqual((1, ["Investment Banking is not one of your target roles"]),
                         (outside["tier"], outside["off_list"]))
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
            old_store.score_pass(force=True)
            # A store built before the edit scores with the saved profile, never its own stale copy.
            self.assertEqual(old_con.execute("SELECT version FROM candidate_resume").fetchone()[0], old_store.version)
        self.service.refresh_now()
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertEqual(0, self.service.get_resume()["pending"])
        matching = self.service.jobs({"shortlist": "0"})["resume_matching"]     # the list that counts the ruled out
        self.assertEqual(matching["unfiltered_total"], matching["excluded_total"])
        self.assertEqual(0, matching["pending_filtered"])

    def _change_targets_and_check(self):
        profile = self.service.get_profile()["profile"]
        profile["target_roles"] = ["public_markets.asset_management"]
        profile["target_countries"] = ["US"]
        with patch.object(self.service, "kick"):
            self.service.put_profile({"profile": profile})
        self.assertEqual(0, self.service.jobs({})["total"])
        self.assertGreater(self.service.jobs({})["resume_matching"]["pending_filtered"], 0)
        matching = self.service.jobs({"shortlist": "0"})["resume_matching"]
        self.assertEqual(0, matching["excluded_total"])
        self.assertEqual(matching["unfiltered_total"], matching["pending_filtered"])
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
        self.assertIn("Treasury Summer Analyst", csv)
        self.assertNotIn("Investment Banking", csv)          # eligible, not on the short list
        self.assertNotIn("Quantitative Researcher", csv)
        self.assertNotIn(marker, csv)
        eligible = self.service.csv_export({"shortlist": "0"})
        self.assertIn("Investment Banking", eligible)
        self.assertNotIn("Quantitative Researcher", eligible)
        self.assertIn("Quantitative Researcher", self.service.csv_export({"resume_match": "0"}))

    def test_a_resumes_licences_reach_the_profile(self):
        self.assertEqual(["rn", "bls"], self.service.parse_resume({"text": NURSING})["profile"]["licences"])
        with patch.object(self.service, "kick"):
            self.service.apply_resume({"text": NURSING})
        self.assertEqual(["rn", "bls"], self.service.get_profile()["profile"]["licences"])

    def test_a_docx_upload_proposes_what_its_text_does(self):
        # Word's list paragraphs are whole lines: a duty with no full stop never takes in the next employer.
        data = base64.b64encode(word_docx(NURSING, "flat")).decode()
        self.assertEqual(self.service.parse_resume({"text": NURSING})["profile"],
                         self.service.parse_resume({"filename": "resume.docx", "data": data})["profile"])

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
        for query in ({}, {"resume_match": "1"}, {"resume_match": "1", "shortlist": "0"}, {"resume_match": "0"}):
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

    def test_the_default_list_is_the_short_list(self):
        self.apply()
        default, eligible = self.service.jobs({}), self.service.jobs({"shortlist": "0"})
        self.assertEqual(["rbc:treasury"], [j["key"] for j in default["jobs"]])
        self.assertEqual(default["jobs"], self.service.jobs({"shortlist": "1"})["jobs"])
        self.assertGreaterEqual(eligible["total"], default["total"])
        self.assertLessEqual({j["key"] for j in default["jobs"]}, {j["key"] for j in eligible["jobs"]})
        self.assertEqual(["rbc:one", "rbc:treasury"], self.keys(shortlist="0"))
        # Tiers as stored: short list 2, eligible 1, ruled out 0.
        with self.service.db() as con:
            tiers = {r[0]: r[1] for r in con.execute("SELECT job_id, matched FROM resume_matches").fetchall()}
        self.assertEqual({"treasury": 2, "one": 1, "li": 1, "two": 0}, tiers)

    def test_resume_matching_reports_the_short_list_and_the_eligible_total(self):
        self.apply()
        default = self.service.jobs({})["resume_matching"]
        self.assertTrue(default["shortlist"])
        # The short list is read from the resume's verdicts alone, without a pass over the board, so it
        # has no count of the eligible or the ruled out to give. Nothing is waiting to be read.
        self.assertEqual((None, None, None), (default["eligible_total"], default["unfiltered_total"],
                                              default["excluded_total"]))
        self.assertEqual(0, default["pending_filtered"])
        eligible = self.service.jobs({"shortlist": "0"})["resume_matching"]
        self.assertFalse(eligible["shortlist"])
        self.assertEqual((2, 1), (eligible["eligible_total"], eligible["excluded_total"]))
        off = self.service.jobs({"resume_match": "0"})["resume_matching"]
        self.assertFalse(off["shortlist"])          # no resume match, no short list, whatever is asked
        self.assertFalse(self.service.jobs({"resume_match": "0", "shortlist": "1"})["resume_matching"]["shortlist"])

    def test_a_posting_no_longer_seen_or_long_posted_leaves_the_short_list_and_stays_eligible(self):
        self.apply()
        for name, change in (("last seen 8 days ago", {"seen_days": 8}), ("posted 31 days ago", {"posted_days": 31}),
                             ("posted 31 days ago, deadline passed",
                              {"posted_days": 31, "deadline": (date.today() - timedelta(days=2)).isoformat()})):
            with self.subTest(name):
                self.age("treasury", **change)
                self.assertEqual([], self.keys())
                self.assertEqual(["rbc:one", "rbc:treasury"], self.keys(shortlist="0"))
                self.assertEqual(2, self.service.jobs({"shortlist": "0"})["resume_matching"]["eligible_total"])
        # Within both limits it is back: seen 6 days ago, posted 29 days ago.
        self.age("treasury", seen_days=6, posted_days=29)
        self.assertEqual(["rbc:treasury"], self.keys())

    def test_a_role_its_source_dropped_counts_as_left_out_not_as_unread(self):
        self.apply()
        self.age("treasury", seen_days=8)
        result = self.service.jobs({})
        self.assertEqual((0, 0), (result["total"], result["resume_matching"]["pending_filtered"]))

    def test_a_long_posted_role_counts_as_left_out_not_as_unread(self):
        # With no deadline the age check is NULL for a role posted over 30 days ago; it must read as off
        # the list, never as "the resume hasn't read this yet".
        self.apply()
        self.age("treasury", posted_days=31)
        result = self.service.jobs({})
        self.assertEqual((0, 0), (result["total"], result["resume_matching"]["pending_filtered"]))

    def test_a_deadline_still_ahead_keeps_a_long_posted_role_on_the_short_list(self):
        self.apply()
        self.age("treasury", posted_days=45, deadline=(date.today() + timedelta(days=10)).isoformat())
        self.assertEqual(["rbc:treasury"], self.keys())
        # ...but not one its source stopped listing.
        self.age("treasury", seen_days=8, posted_days=45, deadline=(date.today() + timedelta(days=10)).isoformat())
        self.assertEqual([], self.keys())

    def test_a_second_resume_drops_the_firsts_specialties_and_keeps_a_hand_picked_target(self):
        self.apply()
        first = self.service.get_profile()["profile"]
        self.assertIn("corporate_finance.treasury", first["resume_targets"])
        # Picked by hand in Settings, in a board the person chose.
        picked = {**first, "fields": ["finance", "software"],
                  "target_roles": [*first["target_roles"], "software.security"]}
        with patch.object(self.service, "kick"):
            self.service.put_profile({"profile": picked})
        saved = self.service.get_profile()["profile"]
        self.assertEqual(first["resume_targets"], saved["resume_targets"])      # the note survives a Settings save
        self.apply(SECOND_RESUME)
        second = self.service.get_profile()["profile"]
        self.assertIn("software.qa_test", second["target_roles"])
        self.assertIn("software.qa_test", second["resume_targets"])
        self.assertIn("software.security", second["target_roles"])
        self.assertNotIn("software.security", second["resume_targets"])
        for gone in first["resume_targets"]:
            self.assertNotIn(gone, second["target_roles"])
            self.assertNotIn(gone, second["role_weights"])

    def test_removing_every_resume_target_in_settings_keeps_the_note_empty(self):
        # An empty note still says "none of these came from a resume": a target given a priority by hand
        # afterwards is not mistaken for an earlier resume's and dropped by the next one.
        self.apply()
        first = self.service.get_profile()["profile"]
        edited = {**first, "fields": ["finance", "software"], "target_roles": ["software.security"],
                  "role_weights": {"software.security": 0.5}}
        with patch.object(self.service, "kick"):
            self.service.put_profile({"profile": edited})
        self.assertEqual([], self.service.get_profile()["profile"]["resume_targets"])
        self.apply(SECOND_RESUME)
        second = self.service.get_profile()["profile"]
        self.assertIn("software.security", second["target_roles"])
        self.assertEqual(0.5, second["role_weights"]["software.security"])

    def test_the_pending_count_matches_a_posting_by_posting_count(self):
        # _count_pending reads four index counts; this is the join over every posting it replaced.
        def slow(con, version):
            return con.execute("""SELECT COUNT(*) FROM jobs j LEFT JOIN job_intel i
                ON i.board=j.board AND i.job_id=j.job_id LEFT JOIN resume_matches rm
                ON rm.board=j.board AND rm.job_id=j.job_id WHERE j.title!='' AND
                (i.facts_version IS NOT ? OR rm.profile_version IS NULL OR rm.profile_version!=?
                 OR i.profile_version IS NULL OR i.profile_version!=?)""", (FACTS_VERSION, version, version)).fetchone()[0]

        def both():
            with self.service.db() as con:
                version = con.execute("SELECT version FROM candidate_resume").fetchone()[0]
                return self.service._count_pending(con, version), slow(con, version)

        self.apply()
        self.assertEqual((0, 0), both())
        with self.service.db() as con:      # one posting sent back for scoring, one for its facts
            con.execute("UPDATE job_intel SET profile_version=NULL WHERE job_id='one'")
        self.assertEqual((1, 1), both())
        with self.service.db() as con:
            con.execute("UPDATE job_intel SET facts_version=facts_version-1 WHERE job_id='li'")
        fast, exact = both()
        self.assertEqual(2, exact)
        self.assertGreaterEqual(fast, 1)        # never zero while anything waits; it may undercount an overlap
        with patch.object(self.service, "kick"):    # a new profile: every posting waits
            self.service.put_profile({"profile": {**self.service.get_profile()["profile"], "target_countries": ["US"]}})
        fast, exact = both()
        self.assertEqual(fast, exact)
        self.assertGreater(fast, 2)

    def test_the_short_list_and_the_board_pass_list_the_same_roles(self):
        # The default list starts from the resume's verdicts; ?shortlist=0 passes over the board. With a
        # filter on, each must give what the filter and the verdicts say.
        self.apply()
        self.assertEqual(["rbc:treasury"], self.keys(q="treasury"))
        self.assertEqual([], self.keys(q="quantitative"))
        self.assertEqual(["rbc:treasury"], self.keys(family="finance"))
        short = self.service.jobs({})
        self.assertEqual(1, short["total"])
        self.assertEqual([{"key": "corporate_finance", "count": 1}],
                         [{"key": f["key"], "count": f["count"]} for f in short["facets"]["category"]])
        eligible = self.service.jobs({"shortlist": "0"})
        self.assertEqual(sum(f["count"] for f in eligible["facets"]["category"]), eligible["total"])

    def test_calendar_deadlines_follow_resume_matches(self):
        self.apply()
        with self.service.db() as con:     # a high-fit posting the resume rules out (quant)
            con.execute("UPDATE job_intel SET eff_deadline='2026-12-05', fit=90 WHERE job_id='two'")

        def deadlines():
            items = self.service.calendar({"start": ["2026-11-01"], "end": ["2026-12-31"]})["items"]
            return sorted(i["job_key"] for i in items if i["kind"] == "deadline")

        self.assertEqual(["rbc:one"], deadlines())
        with self.service.db() as con:     # a posting the resume hasn't read yet keeps the fit rule
            con.execute("UPDATE candidate_resume SET version='stale'")
        self.assertIn("demo_quant:two", deadlines())
        with self.service.db() as con:
            self.service._update_resume_version(con)
        self.service.save_application({"key": "demo_quant:two", "status": "applied"})
        self.assertEqual(["demo_quant:two", "rbc:one"], deadlines())     # applied: always shown
        self.service.delete_application("demo_quant:two")
        with patch.object(self.service, "kick"):
            self.service.set_resume_enabled({"enabled": False})
        self.assertIn("demo_quant:two", deadlines())     # no resume: fit decides


class ResumeHttpTests(ResumeFixture):
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
        self.assertEqual(1, self.call("GET", "/api/jobs")[1]["total"])              # the short list
        self.assertEqual(2, self.call("GET", "/api/jobs?shortlist=0")[1]["total"])  # every eligible role
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
