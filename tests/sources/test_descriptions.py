"""Descriptions for postings whose listing has none: page reading, ATS links, on-demand fetches."""
import json
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import watcher
from intel.page_text import html_text, posting_description
from intel_store import IntelStore
from tests.app.test_dashboard import ServiceFixture

DUTIES = ("Build three-statement models for live deals, prepare pitch books and client materials, "
          "and support senior bankers through diligence and execution. ")
BOILERPLATE = ("We are an equal opportunity employer and value diversity at our company. We do not discriminate "
               "on the basis of race, religion, color, national origin, gender, sexual orientation, age, marital "
               "status, veteran status, or disability status. Information you submit is handled under our "
               "applicant privacy notice and kept for as long as the law requires. ") * 3


LINKEDIN_PAGE = (
    '<section class="show-more-less-html"><div class="show-more-less-html__markup relative overflow-hidden">'
    f'<strong>About us<br><br></strong>{DUTIES}<ul><li>Excel</li></ul></div>'
    '<button class="show-more-less-html__button">Show more</button></section>'
    '<ul class="description__job-criteria-list"><li><h3 class="description__job-criteria-subheader">Seniority level'
    '</h3><span class="description__job-criteria-text">Internship</span></li><li>'
    '<h3 class="description__job-criteria-subheader"> Job function </h3>'
    '<span class="description__job-criteria-text"> Finance &amp; Accounting </span></li></ul>')


def page(body, head=""):
    return f"<!doctype html><html><head><title>Careers</title>{head}</head><body>{body}</body></html>"


def response(url, text="", status=200, content_type="text/html; charset=utf-8", payload=None):
    r = MagicMock()
    r.url, r.status_code, r.text = url, status, text
    r.content = text.encode("utf-8")
    r.headers = {"content-type": content_type}
    r.json.return_value = payload
    r.__enter__.return_value = r
    r.__exit__.return_value = False
    r.raise_for_status.side_effect = None if status < 400 else watcher.requests.HTTPError(str(status))
    return r


class PageTextTests(unittest.TestCase):
    def test_json_ld_job_posting_description_is_unescaped(self):
        data = {"@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "name": "Bank"},
            {"@type": "JobPosting", "title": "Analyst",
             "description": "&lt;p&gt;" + DUTIES + "&lt;/p&gt;&lt;ul&gt;&lt;li&gt;Excel&lt;/li&gt;&lt;/ul&gt;"}]}
        text = posting_description(page("<p>Shell</p>",
                                        f'<script type="application/ld+json">{json.dumps(data)}</script>'))
        self.assertTrue(text.startswith("Build three-statement models"))
        self.assertIn("• Excel", text)

    def test_microdata_description(self):
        body = f'<div itemscope itemtype="http://schema.org/JobPosting"><span itemprop="description"><p>{DUTIES * 2}</p></span></div>'
        self.assertIn("pitch books", posting_description(page(f"<nav>Menu</nav>{body}")))

    def test_main_text_prefers_the_sectioned_posting_over_dense_boilerplate(self):
        posting = (f"<div class='job'><div><h3>About the job</h3><p>{DUTIES}</p></div>"
                   f"<div><h3>Responsibilities</h3><ul><li>{DUTIES}</li><li>Own the deal model.</li></ul></div>"
                   f"<div><h3>Minimum qualifications</h3><ul><li>Bachelor's degree in finance or economics.</li></ul></div></div>")
        footer = f"<div class='legal'><p>{BOILERPLATE}</p></div>"
        text = posting_description(page(f"<header>Site</header><main>{posting}{footer}</main>"
                                        "<script>var x = 'never shown';</script>"))
        self.assertTrue(text.startswith("About the job"), text[:80])
        self.assertIn("Own the deal model.", text)
        self.assertNotIn("never shown", text)
        self.assertNotIn("Site", text)

    def test_cookie_banner_and_hidden_text_are_dropped(self):
        body = (f"<div class='cookie-consent'><p>{BOILERPLATE}</p></div><div hidden><p>{BOILERPLATE}</p></div>"
                f"<article><p>{DUTIES * 2}</p></article>")
        self.assertTrue(posting_description(page(body)).startswith("Build three-statement"))

    def test_page_without_a_description_gives_nothing(self):
        self.assertEqual("", posting_description(page("<div id='app'></div><p>Loading…</p>")))

    def test_html_text_keeps_lists_and_breaks(self):
        self.assertEqual("Role\n• One\n• Two\nEnd", html_text("Role<ul><li>One</li><li>Two</li></ul>End"))
        self.assertEqual("P&L owner", html_text("P&amp;L owner"))


class PostingLinkTests(unittest.TestCase):
    def test_ats_links_route_to_their_apis(self):
        cases = {
            "https://wf.wd1.myworkdayjobs.com/en-US/wellsfargojobs/wellsfargojobs/job/KENNESAW-GA/Teller_R-580450":
                (watcher.detail_workday, {"host": "wf.wd1.myworkdayjobs.com", "tenant": "wf", "site": "wellsfargojobs"},
                 "/job/KENNESAW-GA/Teller_R-580450"),
            "https://rbc.wd3.myworkdayjobs.com/RBCGLOBAL1/job/OTTAWA-Ontario-Canada/Client-Advisor_R-1/apply":
                (watcher.detail_workday, {"host": "rbc.wd3.myworkdayjobs.com", "tenant": "rbc", "site": "RBCGLOBAL1"},
                 "/job/OTTAWA-Ontario-Canada/Client-Advisor_R-1"),
            "https://wd3.myworkdaysite.com/en-US/recruiting/acme/External/job/Toronto/Analyst_R9":
                (watcher.detail_workday, {"host": "wd3.myworkdaysite.com", "tenant": "acme", "site": "External"},
                 "/job/Toronto/Analyst_R9"),
            "https://job-boards.eu.greenhouse.io/imc/jobs/4979079101": (watcher.detail_greenhouse, {"token": "imc"}, "4979079101"),
            "https://boards.greenhouse.io/embed/job_app?for=acme&token=123": (watcher.detail_greenhouse, {"token": "acme"}, "123"),
            "https://jobs.lever.co/belvedere/337314ee-4de5/apply":
                (watcher.detail_lever, {"token": "belvedere", "region": ""}, "337314ee-4de5"),
            "https://jobs.smartrecruiters.com/RedBull/744000156093986-finance-intern":
                (watcher.detail_smartrecruiters, {"token": "RedBull"}, "744000156093986"),
            "https://jpmc.fa.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1001/job/210800228":
                (watcher.detail_oracle_hcm, {"host": "jpmc.fa.oraclecloud.com", "site": "CX_1001"}, "210800228"),
        }
        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(expected, watcher._posting_api(url))
        for url in ("https://www.janestreet.com/join-jane-street/position/123/", "https://zapply.jobs/l/d/x",
                    "https://acme.wd1.myworkdayjobs.com/en-US/External"):
            self.assertIsNone(watcher._posting_api(url))

    def test_redirecting_link_uses_the_workday_api(self):
        landing = "https://wf.wd1.myworkdayjobs.com/en-US/wellsfargojobs/job/Charlotte-NC/Analyst_R-1"
        calls = []

        def get(url, **kw):
            calls.append(url)
            if url.startswith("https://zapply.jobs/"):
                return response(landing, "<html>app shell</html>")
            self.assertEqual("https://wf.wd1.myworkdayjobs.com/wday/cxs/wf/wellsfargojobs/job/Charlotte-NC/Analyst_R-1", url)
            return response(url, payload={"jobPostingInfo": {"jobDescription": f"<p>{DUTIES}</p>",
                                                             "jobFamilyGroup": "Finance", "startDate": "2026-10-01"}})

        with patch.object(watcher.requests, "get", side_effect=get):
            text, dept, meta = watcher.fetch_description({"ats": "github_md"}, "abc",
                                                         "https://zapply.jobs/l/d/workday-wf-wellsfargojobs-R-1?s=x")
        self.assertTrue(text.startswith("Build three-statement"))
        self.assertEqual(("Finance", 2), (dept, len(calls)))
        self.assertTrue(meta["posted"])

    def test_dead_redirects_and_community_links_to_linkedin_are_errors(self):
        with patch.object(watcher.requests, "get", return_value=response("https://zapply.jobs/jobs/", page(f"<p>{DUTIES * 3}</p>"))):
            with self.assertRaisesRegex(ValueError, "no longer leads"):
                watcher.detail_page("https://zapply.jobs/l/d/greenhouse-gone-1")
        error_page = response("https://careers.bankofamerica.com/en-us/errors/404", page(f"<p>{DUTIES * 3}</p>"))
        with patch.object(watcher.requests, "get", return_value=error_page):
            with self.assertRaisesRegex(ValueError, "gone"):
                watcher.fetch_description({"ats": "bofa"}, "1", "https://careers.bankofamerica.com/en-us/students/job-detail/1/x")
        with patch.object(watcher.requests, "get") as get:
            with self.assertRaisesRegex(ValueError, "LinkedIn"):
                watcher.fetch_description({"ats": "github_md"}, "1", "https://www.linkedin.com/jobs/view/123")
            get.assert_not_called()

    def test_page_sources_read_the_posting_page(self):
        ld = json.dumps({"@type": "JobPosting", "description": f"<p>{DUTIES}</p>"})
        html_page = page("<div id='root'></div>", f'<script type="application/ld+json">{ld}</script>')
        with patch.object(watcher.requests, "get", return_value=response("u", html_page)) as get:
            text, dept = watcher.fetch_description({"ats": "icims", "host": "careers-acme.icims.com"}, "3437",
                                                   "https://careers-acme.icims.com/jobs/3437/analyst/job")
        self.assertEqual("https://careers-acme.icims.com/jobs/3437/job?in_iframe=1", get.call_args[0][0])
        self.assertTrue(text.startswith("Build three-statement"))
        with patch.object(watcher.requests, "get", return_value=response("u", page("<div id='root'></div>"))):
            with self.assertRaisesRegex(ValueError, "no readable description"):
                watcher.fetch_description({"ats": "bofa"}, "1", "https://careers.bankofamerica.com/en-us/job-detail/1/x")

    def test_page_charset_comes_from_the_page_when_the_header_has_none(self):
        body = page(f"<p>Café {DUTIES}</p>", '<meta charset="windows-1252">').encode("cp1252")
        r = response("u", content_type="text/html")
        r.content = body
        self.assertIn("Café", watcher._page_html(r))

    def test_oracle_campus_postings_use_program_and_division_text(self):
        item = {"ExternalDescriptionStr": "<br>", "ShortDescriptionStr": " ", "Category": "Seasonal",
                "CorporateDescriptionStr": "<p>About the program</p>", "OrganizationDescriptionStr": "<p>About the division</p>"}
        with patch.object(watcher.requests, "get", return_value=response("u", payload={"items": [item]})):
            text, dept = watcher.detail_oracle_hcm({"host": "h", "site": "s"}, "1")
        self.assertEqual(("About the program\n\nAbout the division", "Seasonal"), (text, dept))


class PageEnrichmentTests(unittest.TestCase):
    def test_poll_fetches_page_sources_and_backs_off_failures(self):
        con = watcher.db_open(":memory:")
        now = watcher.now()
        for job_id in ("1", "2"):
            con.execute("INSERT INTO jobs VALUES ('bofa',?,?,?,?,?,?)", (job_id, "Investment Banking Analyst",
                        "New York", f"https://careers.bankofamerica.com/en-us/job-detail/{job_id}/x", now, now))
            con.execute("INSERT INTO job_details VALUES ('bofa',?,?,?,?)", (job_id, "Bank of America", "", None))
        config = {"boards": {"bofa": {"ats": "bofa"}, "li": {"ats": "linkedin"}}, "profile": {}}
        IntelStore(con, config).refresh()
        ld = json.dumps({"@type": "JobPosting", "description": DUTIES * 2})

        def get(url, **kw):
            if "/1/" in url:
                return response(url, page("", f'<script type="application/ld+json">{ld}</script>'))
            return response(url, status=503)

        with patch.object(watcher.requests, "get", side_effect=get):
            self.assertEqual(1, watcher.enrich_descriptions(config, con, budget=5))
            self.assertEqual(0, watcher.enrich_descriptions(config, con, budget=5))      # job 2 backs off
        rows = dict(con.execute("SELECT job_id, source || ':' || attempts || ':' || (description != '') FROM job_text"))
        self.assertEqual({"1": "detail:1:1", "2": ":1:0"}, rows)


class LinkedInPostingTests(unittest.TestCase):
    def setUp(self):
        watcher._linkedin_next = watcher._linkedin_blocked_until = 0.0
        self.addCleanup(setattr, watcher, "_linkedin_next", 0.0)
        self.addCleanup(setattr, watcher, "_linkedin_blocked_until", 0.0)
        self.sleeps = []
        sleep = patch.object(watcher.time, "sleep", side_effect=self.sleeps.append)
        sleep.start()
        self.addCleanup(sleep.stop)

    def test_posting_text_and_job_function_come_from_the_guest_page(self):
        with patch.object(watcher.requests, "get", return_value=response("u", LINKEDIN_PAGE)) as get:
            text, dept = watcher.fetch_description({"ats": "linkedin"}, "4464612654",
                                                   "https://www.linkedin.com/jobs/view/4464612654")
        self.assertEqual("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/4464612654", get.call_args[0][0])
        self.assertTrue(text.startswith("About us\n\nBuild three-statement"), text[:60])
        self.assertIn("• Excel", text)
        self.assertNotIn("Show more", text)
        self.assertEqual("Finance & Accounting", dept)
        with patch.object(watcher.requests, "get", return_value=response("u", "<section></section>")):
            with self.assertRaisesRegex(ValueError, "no description"):
                watcher.detail_linkedin({}, "1")

    def test_posting_fetches_share_the_search_spacing_and_pause(self):
        with patch.object(watcher.requests, "get", return_value=response("u", LINKEDIN_PAGE)):
            watcher.detail_linkedin({}, "1")
            self.assertGreater(watcher._linkedin_next, time.monotonic())     # the search waits its turn
            watcher.fetch_linkedin({"queries": ["analyst"], "pages": 1})
        self.assertTrue(self.sleeps and self.sleeps[0] > 0, self.sleeps)
        watcher._linkedin_blocked_until = time.monotonic() + 60
        with patch.object(watcher.requests, "get") as get:
            with self.assertRaises(watcher.LinkedInRateLimited):
                watcher.detail_linkedin({}, "1")
            get.assert_not_called()          # while LinkedIn is paused a fetch fails at once

    def test_linkedin_is_fetched_on_open_never_by_the_poll(self):
        self.assertFalse(watcher.describable({"ats": "linkedin"}))
        self.assertTrue(watcher.describable({"ats": "linkedin"}, on_open=True))
        con = watcher.db_open(":memory:")
        now = watcher.now()
        con.execute("INSERT INTO jobs VALUES ('li','4464612654','Intern - Treasury Analyst','Toronto, ON',?,?,?)",
                    ("https://www.linkedin.com/jobs/view/4464612654", now, now))
        con.execute("INSERT INTO job_details VALUES ('li','4464612654','EQ Bank','',NULL)")
        config = {"boards": {"li": {"ats": "linkedin"}}, "profile": {}}
        IntelStore(con, config).refresh()
        with patch.object(watcher.requests, "get") as get:
            self.assertEqual(0, watcher.enrich_descriptions(config, con, budget=5))
        get.assert_not_called()

    def test_best_fitting_linkedin_listings_get_their_description_a_few_at_a_time(self):
        con = watcher.db_open(":memory:")
        now = watcher.now()
        for job_id in ("1", "2", "3"):
            con.execute("INSERT INTO jobs VALUES ('li',?,'Intern - Treasury Analyst','Toronto, ON',?,?,?)",
                        (job_id, f"https://www.linkedin.com/jobs/view/{job_id}", now, now))
            con.execute("INSERT INTO job_details VALUES ('li',?,'EQ Bank','',NULL)", (job_id,))
        config = {"boards": {"li": {"ats": "linkedin"}}, "profile": {}}
        IntelStore(con, config).refresh()
        con.execute("UPDATE job_intel SET fit=CAST(job_id AS INTEGER) * 10, is_canonical=1")
        fetched = []
        with patch.object(watcher, "_linkedin_enriched_at", float("-inf")), \
                patch.object(watcher, "fetch_description",
                             side_effect=[(DUTIES, ""), watcher.LinkedInRateLimited("429")]) as fetch:
            self.assertEqual(1, watcher.enrich_linkedin(config, con, budget=3, fetched=fetched))
            self.assertEqual([("li", "3")], fetched)                          # the best fit first
            self.assertEqual(["3", "2"], [call.args[1] for call in fetch.call_args_list])   # until LinkedIn says wait
            self.assertIsNone(con.execute("SELECT 1 FROM job_text WHERE job_id='2'").fetchone())   # not held against it
            fetch.reset_mock()
            self.assertEqual(0, watcher.enrich_linkedin(config, con, budget=3))
            fetch.assert_not_called()                                         # ten minutes between batches
        with patch.object(watcher, "_linkedin_enriched_at", float("-inf")), \
                patch.object(watcher, "fetch_description", return_value=(DUTIES, "")) as fetch:
            self.assertEqual(2, watcher.enrich_linkedin(config, con, budget=3))
        self.assertEqual(["2", "1"], [call.args[1] for call in fetch.call_args_list])


class OpenDrawerFetchTests(ServiceFixture):
    def wait(self):
        for thread in threading.enumerate():
            if thread.name == "jobwatch-describe":
                thread.join(5)

    def test_opening_a_posting_without_text_fetches_it_once(self):
        self.service.fetch_on_open = True
        release = threading.Event()

        def fetch(cfg, job_id, url):
            release.wait(5)
            return f"{DUTIES} Applications close December 1, 2026.", "Quant Research"

        with patch.object(watcher, "fetch_description", side_effect=fetch) as fetcher:
            first = self.service.job_detail("demo_quant:two")
            again = self.service.job_detail("demo_quant:two")
            release.set()
            self.wait()
        self.assertEqual((True, True, 1), (first["description_pending"], again["description_pending"], fetcher.call_count))
        self.assertEqual(({"ats": "greenhouse", "token": "quant"}, "two", "https://example.com/two"), fetcher.call_args[0])
        job = self.service.job_detail("demo_quant:two")
        self.assertFalse(job["description_pending"])
        self.assertIn("three-statement", job["description"])
        self.assertEqual(("detail", "Quant Research"), (job["description_source"], job["department"]))
        self.assertEqual("2026-12-01", job["facts"]["deadline"]["date"])

    def test_drawer_keeps_checking_until_the_posting_is_rescored(self):
        self.service.fetch_on_open = True
        scoring, release = threading.Event(), threading.Event()
        facts_pass = IntelStore.facts_pass

        def slow_facts_pass(store, *args, **kwargs):
            scoring.set()
            release.wait(5)
            return facts_pass(store, *args, **kwargs)

        with patch.object(watcher, "fetch_description", return_value=(DUTIES * 2, "")), \
                patch.object(IntelStore, "facts_pass", slow_facts_pass):
            self.service.job_detail("demo_quant:two")
            self.assertTrue(scoring.wait(5))
            saved = self.service.job_detail("demo_quant:two")
            release.set()
            self.wait()
        self.assertTrue(saved["description"].startswith("Build three-statement"))
        self.assertTrue(saved["description_pending"])          # facts and fit are not updated yet
        self.assertFalse(self.service.job_detail("demo_quant:two")["description_pending"])

    def test_failures_back_off_and_stop_after_three_attempts(self):
        self.service.fetch_on_open = True
        with patch.object(watcher, "fetch_description", side_effect=watcher.requests.HTTPError("503")) as fetcher:
            self.assertTrue(self.service.job_detail("demo_quant:two")["description_pending"])
            self.wait()
            job = self.service.job_detail("demo_quant:two")
            self.assertEqual(1, fetcher.call_count)           # inside the six-hour back-off
            self.assertFalse(job["description_pending"])
            with self.service.db() as con:
                con.execute("UPDATE job_text SET fetched_at='2000-01-01T00:00:00+00:00'")
            self.assertTrue(self.service.job_detail("demo_quant:two")["description_pending"])
            self.wait()
            with self.service.db() as con:
                con.execute("UPDATE job_text SET fetched_at='2000-01-01T00:00:00+00:00', attempts=3")
            self.assertFalse(self.service.job_detail("demo_quant:two")["description_pending"])
            self.assertEqual(2, fetcher.call_count)
        with self.service.db() as con:
            self.assertIn("503", con.execute("SELECT last_error FROM job_text WHERE job_id='two'").fetchone()[0])

    def test_a_failed_fetch_says_why_and_try_again_skips_the_back_off(self):
        self.service.fetch_on_open = True
        with patch.object(watcher, "fetch_description", side_effect=watcher.requests.HTTPError("503 Server Error")):
            self.service.job_detail("demo_quant:two")
            self.wait()
            job = self.service.job_detail("demo_quant:two")
        self.assertEqual((False, "the site didn't answer"), (job["description_pending"], job["description_failed"]))
        with patch.object(watcher, "fetch_description", return_value=(DUTIES * 2, "")) as fetcher:
            self.assertEqual({"pending": True}, self.service.retry_description("demo_quant:two"))
            self.wait()
        job = self.service.job_detail("demo_quant:two")
        self.assertEqual((1, ""), (fetcher.call_count, job["description_failed"]))
        self.assertTrue(job["description"].startswith("Build three-statement"))
        self.assertEqual({"pending": False}, self.service.retry_description("demo_quant:two"))   # nothing to fetch

    def test_linkedin_listing_is_fetched_when_opened(self):
        self.service.fetch_on_open = True
        with patch.object(watcher, "fetch_description", return_value=(DUTIES * 2, "Finance")) as fetcher:
            self.assertTrue(self.service.job_detail("linkedin_ca:li")["description_pending"])
            self.wait()
        self.assertEqual("linkedin", fetcher.call_args[0][0]["ats"])
        job = self.service.job_detail("linkedin_ca:li")
        self.assertEqual((False, "detail"), (job["description_pending"], job["description_source"]))
        self.assertTrue(job["description"].startswith("Build three-statement"))

    def test_no_fetch_for_postings_with_text_or_without_background_work(self):
        with patch.object(watcher, "fetch_description") as fetcher:
            self.assertFalse(self.service.job_detail("demo_quant:two")["description_pending"])   # tests, tools
            self.service.fetch_on_open = True
            self.assertFalse(self.service.job_detail("rbc:one")["description_pending"])
            time.sleep(0.05)
            fetcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
