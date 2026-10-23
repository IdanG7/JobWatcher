import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import watcher
from dashboard import ApiError, JobwatchHandler, JobwatchService
from intel_store import store_description, update_lifecycle
from job_intelligence import analyze_job, board_tags, location_bucket, role_track, seniority


class LegacyFacadeTests(unittest.TestCase):
    """The original job_intelligence API keeps working on top of the new engine."""

    def test_role_families_cover_core_and_broad_searches(self):
        self.assertEqual("quant", role_track("Quantitative Researcher, Systematic Equities"))
        self.assertEqual("software", role_track("Backend Software Engineer — Distributed Systems"))
        self.assertEqual("data_ml", role_track("Machine Learning Engineer"))
        self.assertEqual("product", role_track("Product Manager, Growth"))
        self.assertEqual("design", role_track("Senior Product Designer"))
        self.assertEqual("operations", role_track("Business Operations Associate"))
        self.assertEqual("finance", role_track("Investment Banking Summer Analyst"))

    def test_seniority_and_location_are_independent_facets(self):
        self.assertEqual("internship", seniority("Software Engineer Intern — Summer 2027"))
        self.assertEqual("new_grad", seniority("2027 Graduate Quantitative Trader"))
        self.assertEqual("senior", seniority("Staff Infrastructure Engineer"))
        self.assertEqual("entry", seniority("Investment Banking Analyst"))
        self.assertEqual("us", location_bucket("New York, NY, United States"))
        self.assertEqual("canada", location_bucket("Toronto, ON, Canada"))
        self.assertEqual("remote", location_bucket("Remote — US or Canada"))

    def test_explainable_profile_prioritizes_target_fit(self):
        # Replaces the SWE-default assertion: the profile, not code, sets priorities.
        swe = {"profile": {"target_roles": ["software"], "target_company_types": ["fintech"],
                           "target_locations": ["seattle"], "skills": ["rust", "python"]}}
        target = analyze_job({"title": "Software Engineer Intern - Summer 2027, Rust / Distributed Systems",
                              "location": "Seattle, WA", "posted": time.time() - 3600,
                              "description": "Rust and Python services"}, swe, tags={"fintech"})
        unrelated = analyze_job({"title": "Senior Sales Director", "location": "London, UK",
                                 "posted": time.time() - 3600}, swe)
        self.assertGreaterEqual(target["score"], 90)
        self.assertLess(unrelated["score"], 40)
        self.assertTrue(any("level" in reason for reason in target["reasons"]))
        self.assertEqual(target["score"], target["fit"])

    def test_target_year_and_degree_level_affect_ranking(self):
        base = {"location": "New York, NY", "posted": time.time() - 3600}
        target = analyze_job({**base, "title": "2027 Investment Banking Summer Analyst"})
        old = analyze_job({**base, "title": "2025 Investment Banking Summer Analyst"})
        phd = analyze_job({**base, "title": "2027 Investment Banking Summer Analyst",
                           "description": "Open to PhD candidates only."})
        self.assertGreater(target["score"], old["score"])
        self.assertGreater(target["score"], phd["score"])
        self.assertIn("Summer 2027 target cycle", target["reasons"])

    def test_board_sections_become_company_tags(self):
        config = {"boards": {"_quant_and_trading": "---", "jane": {}, "_ai_and_startups": "---", "linear": {}}}
        tags = board_tags(config)
        self.assertIn("quant", tags["jane"])
        self.assertEqual({"startup"}, tags["linear"] & {"startup", "quant"})


class ServiceFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.db_path = root / "test.db"
        self.config_path = root / "config.json"
        self.subscribers_path = root / "subscribers.json"
        self.config_path.write_text(json.dumps({
            "profile": {"headline": "Test search"},
            "boards": {
                "_canadian_banks": "---",
                "rbc": {"ats": "greenhouse", "token": "rbc"},
                "_quant_and_trading": "---",
                "demo_quant": {"ats": "greenhouse", "token": "quant"},
                "_linkedin": "---",
                "linkedin_ca": {"ats": "linkedin", "location": "Canada"},
            },
        }))
        self.subscribers_path.write_text(json.dumps({"test": {"watchlist": "goldman|rbc", "companies": ["all"]}}))
        con = watcher.db_open(self.db_path)
        now = watcher.now()
        rows = [
            ("rbc", "one", "2027 Investment Banking Summer Analyst", "Toronto, ON", "RBC", time.time() - 3600),
            ("linkedin_ca", "li", "2027 Investment Banking Summer Analyst", "Toronto, Ontario, Canada",
             "RBC Capital Markets", time.time() - 1800),
            ("demo_quant", "two", "Quantitative Researcher", "Chicago, IL", "Demo Capital", time.time() - 7200),
        ]
        for board, job_id, title, location, company, posted in rows:
            con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                        (board, job_id, title, location, f"https://example.com/{job_id}", now, now))
            con.execute("INSERT INTO job_details VALUES (?,?,?,?,?)", (board, job_id, company, "$50/hr", posted))
        store_description(con, "rbc", "one", "Join our M&A team. Financial modeling in Excel. "
                                              "Applications close December 1, 2026.")
        update_lifecycle(con, "rbc", {"one"}, False, now, {"one"}, discovered=True)
        con.execute("INSERT INTO boards(board, seeded, last_ok) VALUES (?,?,?)", ("rbc", 1, now))
        con.commit()
        con.close()
        self.service = JobwatchService(self.db_path, self.config_path, self.subscribers_path)
        self.service.refresh_now()

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()


class DashboardServiceTests(ServiceFixture):
    def test_search_filters_and_overview(self):
        results = self.service.jobs({"category": ["investment_banking"], "location": ["toronto"]})
        self.assertEqual(1, results["total"])        # LinkedIn twin is merged, not duplicated
        job = results["jobs"][0]
        self.assertEqual("rbc:one", job["key"])
        self.assertEqual(["LinkedIn · Canada", "RBC Careers"], job["discovered_from"])
        self.assertEqual("Investment Banking", job["category_label"])
        overview = self.service.overview()
        self.assertEqual("Test search", overview["profile"]["headline"])
        self.assertGreaterEqual(overview["stats"]["new_today"], 1)
        self.assertTrue(overview["top"])
        self.assertTrue(any(a["kind"] == "fresh_high_fit" for a in overview["attention"]))

    def test_full_text_search_covers_description_and_skills(self):
        self.assertEqual(1, self.service.jobs({"q": ["modeling"]})["total"])
        self.assertEqual(1, self.service.jobs({"q": ["financial modeling"]})["total"])
        self.assertEqual(0, self.service.jobs({"q": ["astrophysics"]})["total"])

    def test_job_detail_explains_score(self):
        job = self.service.job_detail("rbc:one")
        self.assertEqual("ma", job["subcategory"])
        self.assertEqual(7, len(job["fit_detail"]["subscores"]))
        self.assertTrue(job["description"].startswith("Join our M&A team"))
        self.assertEqual(2, len(job["sources"]))
        self.assertTrue(any(s["canonical"] for s in job["sources"]))
        with self.assertRaises(ApiError):
            self.service.job_detail("rbc:missing")

    def test_application_status_transitions_record_history(self):
        result = self.service.save_application({"key": "rbc:one", "status": "saved"})
        self.assertTrue(result["ok"])
        self.service.patch_application("rbc:one", {"status": "applied"})
        self.service.patch_application("rbc:one", {"status": "first_round", "interview_date": "2026-12-01",
                                                   "next_step": "Prepare technicals"})
        apps = self.service.applications()
        app = apps["grouped"]["first_round"][0]
        self.assertEqual("Prepare technicals", app["next_step"])
        self.assertTrue(app["applied_date"])          # set automatically on 'applied'
        self.assertEqual(["saved", "applied", "first_round"], [e["to_status"] for e in app["events"]])
        self.assertEqual(1, len(self.service.pipeline()["pipeline"]["first_round"]))
        self.service.delete_application("rbc:one")
        self.assertEqual(0, self.service.applications()["total"])

    def test_invalid_status_and_dates_are_rejected(self):
        with self.assertRaises(ApiError):
            self.service.save_application({"key": "rbc:one", "status": "ghosted"})
        with self.assertRaises(ApiError):
            self.service.save_application({"key": "rbc:one", "status": "saved", "deadline": "next week"})
        legacy = self.service.save_application({"key": "rbc:one", "status": "interview"})
        self.assertEqual("first_round", legacy["status"])

    def test_contacts_and_follow_ups(self):
        created = self.service.create_contact({"name": "John Smith", "position": "Investment Banking Analyst",
                                               "company": "RBC Capital Markets", "relationship": "alumni",
                                               "linkedin_url": "https://www.linkedin.com/in/example",
                                               "next_follow_up": "2020-01-01"})
        contacts = self.service.contacts({})["contacts"]
        self.assertEqual("rbc", contacts[0]["company_key"])
        self.assertEqual(1, self.service.overview()["stats"]["follow_ups"])
        logged = self.service.log_contact(created["id"], {"note": "coffee chat", "follow_up_days": 7})
        self.assertTrue(logged["next_follow_up"] > "2020-01-01")
        with self.assertRaises(ApiError):
            self.service.create_contact({"name": "X", "relationship": "best friend"})
        with self.assertRaises(ApiError):
            self.service.create_contact({"name": "X", "linkedin_url": "javascript:alert(1)"})

    def test_watchlist_boosts_and_company_pages(self):
        before = self.service.job_detail("demo_quant:two")["fit"]
        self.service.watch_company("demo_capital", {"watched": True, "name": "Demo Capital"})
        after = self.service.job_detail("demo_quant:two")["fit"]
        self.assertGreater(after, before)
        company = self.service.company_detail("rbc")
        self.assertTrue(company["watched"])       # seeded from the subscriber watchlist regex
        self.assertEqual(1, company["stats"]["active"])
        self.assertEqual(13, len(company["weekly"]))

    def test_calendar_saved_searches_and_profile(self):
        self.service.save_application({"key": "rbc:one", "status": "saved", "deadline": "2026-12-01"})
        items = self.service.calendar({"start": ["2026-11-01"], "end": ["2026-12-31"]})["items"]
        self.assertEqual(1, sum(1 for i in items if i["kind"] == "deadline"))   # manual wins, no duplicate
        search = self.service.create_saved_search({"name": "Toronto IB 2027",
                                                   "query": {"category": "investment_banking",
                                                             "location": "toronto", "cycle": "2027"}})
        listed = self.service.saved_searches()["saved_searches"][0]
        self.assertEqual((search["id"], 1), (listed["id"], listed["total"]))
        with self.assertRaises(ApiError):
            self.service.put_profile({"target_roles": ["astrology"]})
        self.assertFalse(self.service.get_profile()["saved"])     # first run: the browser offers onboarding
        saved = self.service.put_profile({"target_locations": ["chicago"]})
        self.assertEqual(["chicago"], saved["profile"]["target_locations"])
        self.assertEqual(["chicago"], self.service.get_profile()["profile"]["target_locations"])
        self.assertTrue(self.service.get_profile()["saved"])

    def test_profile_fields_choose_what_settings_show(self):
        saved = self.service.put_profile({"fields": ["finance", "software"], "target_roles": ["software"],
                                          "role_weights": {"software": 0.75}})
        self.assertEqual(["finance", "software"], saved["profile"]["fields"])
        self.assertEqual({"software": 0.75}, saved["profile"]["role_weights"])
        with self.assertRaises(ApiError):
            self.service.put_profile({"fields": ["astrology"]})
        meta = self.service.meta()
        self.assertIn("CA", {c["key"] for c in meta["countries"]})
        self.assertIn("English", meta["languages"])

    def test_choices_this_version_dropped_are_pruned_at_start(self):
        # A profile saved by 0.3.0, whose specialties, employer types and skills this version
        # renamed or doesn't offer (software.backend and the Kubernetes skill are offered again and stay).
        from intel_store import save_profile
        with self.service.db() as con:
            save_profile(con, {"fields": ["software"],
                               "target_roles": ["software.embedded", "data_ml.research", "software.backend", "investment_banking.ma"],
                               "role_weights": {"software.embedded": 0.75, "investment_banking.ma": 1.0},
                               "target_company_types": ["established_tech", "bulge_bracket"],
                               "skills": ["kubernetes", "python", "retired_skill"]})
        profile = JobwatchService(self.db_path, self.config_path, self.subscribers_path).get_profile()["profile"]
        self.assertEqual(["software", "data_ml", "software.backend", "investment_banking.ma"], profile["target_roles"])
        self.assertEqual({"software": 0.75, "investment_banking.ma": 1.0}, profile["role_weights"])
        self.assertEqual((["bulge_bracket"], ["kubernetes", "python"]), (profile["target_company_types"], profile["skills"]))
        self.service.put_profile(profile)       # Settings can save it again

    def test_sources_name_their_pack_and_whether_your_boards_poll_them(self):
        from intel_store import save_profile
        result = self.service.sources()
        rows = {s["name"]: s for s in result["sources"]}
        self.assertEqual(("finance/canadian_banks", True), (rows["rbc"]["pack"], rows["rbc"]["polled"]))
        self.assertEqual(("", True), (rows["demo_quant"]["pack"], rows["demo_quant"]["polled"]))   # your own
        packs = {p["key"]: p for p in result["packs"]}
        self.assertEqual(["Finance"], packs["finance/canadian_banks"]["boards"])
        self.assertEqual(["Software"], packs["tech/gaming"]["boards"])
        self.assertEqual(["Finance", "Software", "AI & Data"], packs["shared/ai_labs"]["boards"])
        self.assertIn("Sales & Growth", result["every_pack"])
        with self.service.db() as con:
            save_profile(con, {"fields": ["software"], "target_roles": ["software"]})
        rows = {s["name"]: s for s in self.service.sources()["sources"]}
        self.assertEqual((False, True), (rows["rbc"]["polled"], rows["demo_quant"]["polled"]))

    def test_analytics_activity_sources(self):
        evidence = {"fetched": 1, "reported_total": 300, "complete": False,
                    "detects_removals": False, "reason": "Configured cap reached"}
        with self.service.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k,v) VALUES (?,?)",
                        ("source_coverage:rbc", json.dumps(evidence)))
        analytics = self.service.analytics({"window": ["30"]})
        self.assertIn("funnel", analytics)
        self.assertEqual(7, len(analytics["heatmap"]))
        self.assertTrue(any(c["key"] == "investment_banking" for c in analytics["by_category"]))
        # flow counts by posting date, so freshly seeded boards still show a market picture
        self.assertEqual(2, analytics["flow"][30])
        self.assertEqual(2, sum(d["count"] for d in analytics["daily"]))
        self.assertEqual({"rbc", "demo_capital"}, {c["key"] for c in analytics["companies"]})
        self.assertTrue(self.service.activity({})["items"])
        sources = self.service.sources()["sources"]
        rbc = next(s for s in sources if s["name"] == "rbc")
        self.assertEqual("Canadian Banks", rbc["group"])
        self.assertTrue(rbc["complete_listing"])
        self.assertEqual(evidence, rbc["coverage"])


class HttpApiTests(ServiceFixture):
    def setUp(self):
        super().setUp()
        handler = type("H", (JobwatchHandler,), {"service": self.service})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def test_endpoints(self):
        for path in ("/api/overview", "/api/jobs?sort=newest", "/api/jobs/rbc%3Aone", "/api/companies",
                     "/api/companies/rbc", "/api/applications", "/api/contacts", "/api/calendar",
                     "/api/analytics", "/api/activity", "/api/sources", "/api/profile", "/api/meta",
                     "/api/status", "/api/saved-searches", "/api/pipeline"):
            status, body = self.call("GET", path)
            self.assertEqual(200, status, (path, body))
        status, body = self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"})
        self.assertEqual((200, True), (status, body["ok"]))
        status, body = self.call("PATCH", "/api/applications/rbc%3Aone", {"status": "applied"})
        self.assertEqual("applied", body["status"])
        status, body = self.call("POST", "/api/contacts", {"name": "Jane Doe", "relationship": "recruiter"})
        self.assertEqual(200, status)
        status, _ = self.call("POST", f"/api/contacts/{body['id']}/log", {"note": "emailed"})
        self.assertEqual(200, status)
        self.assertEqual(400, self.call("POST", "/api/applications", {"key": "rbc:one", "status": "nope"})[0])
        self.assertEqual(404, self.call("GET", "/api/nothing")[0])
        self.assertEqual(405, self.call("DELETE", "/api/overview")[0])
        self.assertEqual(200, self.call("DELETE", "/api/applications/rbc%3Aone")[0])

    def test_csv_export(self):
        with urllib.request.urlopen(self.base + "/api/export.csv", timeout=10) as response:
            text = response.read().decode()
        self.assertTrue(text.startswith("fit,company,title"))

    def test_cross_site_writes_are_refused(self):
        request = urllib.request.Request(self.base + "/api/applications", method="POST",
                                         data=b'{"key":"rbc:one","status":"saved"}',
                                         headers={"Content-Type": "text/plain"})
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(request, timeout=10)
        self.assertEqual(415, ctx.exception.code)
        status, _ = self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"},
                              {"Origin": "https://evil.example"})
        self.assertEqual(403, status)
        status, _ = self.call("GET", "/api/overview", headers={"Host": "evil.example"})
        self.assertEqual(403, status)

    def test_static_files_and_traversal(self):
        with urllib.request.urlopen(self.base + "/", timeout=10) as response:
            self.assertIn(b"<!doctype html>", response.read().lower())
        for path in ("/../config.json", "/%2e%2e/config.json", "/dashboard.py"):
            with self.assertRaises(urllib.error.HTTPError):
                urllib.request.urlopen(self.base + path, timeout=10)


if __name__ == "__main__":
    unittest.main()
