"""Public-source coverage regressions; all HTTP is replaced with fixtures."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import watcher


def response(payload=None, text=""):
    r = Mock(status_code=200, text=text)
    r.raise_for_status.return_value = None
    r.json.return_value = payload
    return r


def workday_page(start, count, total=None):
    data = {"jobPostings": [{"externalPath": f"/job/{i}", "title": f"Intern {i}",
                              "locationsText": "Toronto, ON"}
                             for i in range(start, start + count)]}
    if total is not None:
        data["total"] = total
    return response(data)


class SourcePaginationTests(unittest.TestCase):
    @patch("watcher.requests.post")
    def test_workday_repeated_tail_retains_usable_postings_without_closures(self, post):
        # HP returns page one when an offset runs beyond a listing that shrank
        # during the fetch. Keep what we fetched, but don't infer any removals.
        post.side_effect = [workday_page(0, 20, 23), workday_page(20, 2, 0), workday_page(0, 20, 23)]
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})
        self.assertEqual(22, len(jobs))
        self.assertFalse(jobs.complete)
        self.assertIn("repeated", jobs.reason)
        self.assertEqual(3, post.call_count)

    @patch("watcher.requests.post")
    def test_workday_duplicate_rows_at_reported_end_are_not_complete(self, post):
        post.side_effect = [workday_page(0, 2, 4), workday_page(1, 2, 0)]
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})
        self.assertEqual(3, len(jobs))
        self.assertFalse(jobs.complete)
        self.assertIn("3 of 4", jobs.reason)

    @patch("watcher.requests.get")
    def test_oracle_small_ordering_gap_cannot_enable_closure_detection(self, get):
        get.side_effect = [response({"items": [{"TotalJobsCount": 4, "requisitionList": [
            {"Id": str(i), "Title": "Analyst"} for i in range(3)]}]}),
            response({"items": [{"TotalJobsCount": 4, "requisitionList": []}]})]
        jobs = watcher.fetch_oracle_hcm({"host": "x", "site": "x"})
        self.assertEqual(3, len(jobs))
        self.assertFalse(jobs.complete)
        self.assertIn("3 of reported total 4", jobs.reason)

    @patch("watcher.requests.post")
    def test_workday_cap_warning_survives_malformed_summary_warning(self, post):
        post.return_value = response({"total": 2000, "facets": [
            {"facetParameter": "country", "values": [{"id": "us", "count": 14000}]}],
            "jobPostings": [{"externalPath": "/job/valid", "title": "Intern"},
                            {"bulletFields": ["Rmissing"]}]})
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x", "max": 2})
        self.assertFalse(jobs.complete)
        self.assertIn("14,000", jobs.reason)
        self.assertIn("malformed", jobs.reason)

    @patch("watcher.requests.post")
    def test_workday_retains_valid_summaries_but_marks_malformed_listing_partial(self, post):
        post.return_value = response({"total": 3, "jobPostings": [
            {"externalPath": "/job/valid", "title": "Finance Intern", "locationsText": "Toronto"},
            {"bulletFields": ["R0000476666"]},
            {"externalPath": "/job/no-title", "bulletFields": ["R0000000002"]},
        ]})
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})
        self.assertEqual(["/job/valid"], [j["id"] for j in jobs])
        self.assertEqual(3, jobs.total)
        self.assertFalse(jobs.complete)
        self.assertIn("2 malformed", jobs.reason)

    @patch("watcher.requests.post")
    def test_workday_all_malformed_pages_advance_raw_offset_and_stop_at_cap(self, post):
        post.side_effect = [response({"total": 100, "jobPostings": [
            {"bulletFields": [f"R{i:010d}"]} for i in range(start, start + 20)]})
            for start in (0, 20)]
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x", "max": 40})
        self.assertEqual([], jobs)
        self.assertFalse(jobs.complete)
        self.assertEqual(100, jobs.total)
        self.assertEqual(20, post.call_args_list[1].kwargs["json"]["offset"])
        self.assertIn("40 malformed", jobs.reason)
        self.assertIn("limit 40", jobs.reason)

    @patch("watcher.requests.post")
    def test_workday_repeated_malformed_page_is_failure(self, post):
        post.return_value = response({"total": 3, "jobPostings": [{"bulletFields": ["R1"]}]})
        with self.assertRaisesRegex(RuntimeError, "pagination repeated"):
            watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x", "max": 40})
        self.assertEqual(2, post.call_count)

    @patch("watcher.requests.post")
    def test_workday_includes_postings_beyond_first_300(self, post):
        post.side_effect = [workday_page(i, min(20, 321 - i), 321 if i == 0 else None)
                            for i in range(0, 321, 20)]
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})
        self.assertEqual(321, len(jobs))
        self.assertEqual("/job/320", jobs[-1]["id"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.post")
    def test_missing_workday_total_does_not_stop_after_first_page(self, post):
        post.side_effect = [workday_page(0, 20), workday_page(20, 1), workday_page(21, 0)]
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})
        self.assertEqual(21, len(jobs))
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.post")
    def test_workday_repeat_or_early_empty_is_failure(self, post):
        for second in (workday_page(0, 20), workday_page(20, 0)):
            with self.subTest(second=second):
                post.side_effect = [workday_page(0, 20, 40), second]
                with self.assertRaisesRegex(RuntimeError, "pagination"):
                    watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})

    @patch("watcher.requests.post")
    def test_workday_explicit_limit_preserves_partial_metadata(self, post):
        post.return_value = workday_page(0, 20, 40)
        jobs = watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x", "max": 20})
        self.assertEqual(20, len(jobs))
        self.assertFalse(jobs.complete)

    @patch("watcher.requests.post")
    def test_inconsistent_zero_total_is_not_authoritative(self, post):
        post.return_value = workday_page(0, 1, 0)
        with self.assertRaisesRegex(RuntimeError, "pagination"):
            watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})

    @patch("watcher.requests.post")
    def test_second_page_http_failure_does_not_return_first_page_as_complete(self, post):
        post.side_effect = [workday_page(0, 20, 40), watcher.requests.HTTPError("fixture outage")]
        with self.assertRaises(watcher.requests.HTTPError):
            watcher.fetch_workday({"host": "x", "tenant": "x", "site": "x"})

    @patch("watcher.requests.post")
    def test_phenom_reads_second_page_using_actual_page_size(self, post):
        def page(start, count):
            return response({"refineSearch": {"status": 200, "totalHits": 3, "hits": count,
                "data": {"jobs": [{"jobId": str(i), "title": "Finance Co-op",
                                   "cityStateCountry": "Toronto, Ontario, Canada"}
                                  for i in range(start, start + count)]}}})
        post.side_effect = [page(0, 2), page(2, 1)]
        jobs = watcher.fetch_phenom({"host": "jobs.rbc.com", "size": 2})
        self.assertEqual(["0", "1", "2"], [j["id"] for j in jobs])
        self.assertEqual(2, post.call_args_list[1].kwargs["json"]["from"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_oracle_cap_cannot_be_used_as_complete_listing(self, get):
        get.return_value = response({"items": [{"TotalJobsCount": 40, "requisitionList": [
            {"Id": str(i), "Title": "Summer Analyst", "PrimaryLocation": "Toronto"}
            for i in range(25)]}]})
        jobs = watcher.fetch_oracle_hcm({"host": "x", "site": "x", "max": 25})
        self.assertEqual(25, len(jobs))
        self.assertFalse(jobs.complete)


def li_card(jid, title="Investment Banking Intern"):
    return (f'<li><div data-entity-urn="urn:li:jobPosting:{jid}">'
            f'<h3 class="base-search-card__title">{title}</h3>'
            '<h4 class="base-search-card__subtitle"><a>RBC</a></h4>'
            '<span class="job-search-card__location">Toronto, ON</span>'
            '<time datetime="2026-09-20"></time></div></li>')


class LinkedInCoverageTests(unittest.TestCase):
    @patch("watcher.time.sleep")
    @patch("watcher.requests.get")
    def test_initial_seed_uses_configured_longer_lookback(self, get, sleep):
        get.return_value = response(text=li_card("20000000"))
        watcher.fetch_linkedin({"_initial_seed": True, "recency": "r86400", "seed_recency": "r7776000",
                                "pages": 1, "seed_pages": 1})
        self.assertEqual("r7776000", get.call_args.kwargs["params"]["f_TPR"])

    @patch("watcher.time.sleep")
    @patch("watcher.requests.get")
    def test_legitimate_older_ids_survive_wider_lookback(self, get, sleep):
        get.return_value = response(text=li_card("10000000") + li_card("20000000"))
        jobs = watcher.fetch_linkedin({"pages": 1, "recency": "r2592000"})
        self.assertEqual({"10000000", "20000000"}, {j["id"] for j in jobs})
        self.assertFalse(jobs.complete)

    @patch("watcher.time.sleep")
    @patch("watcher.requests.get")
    def test_repeated_linkedin_page_stops_without_duplicate_rows(self, get, sleep):
        get.return_value = response(text=li_card("20000000"))
        jobs = watcher.fetch_linkedin({"pages": 8})
        self.assertEqual(1, len(jobs))
        self.assertEqual(2, get.call_count)

    def test_canada_queries_include_finance_coop_and_analyst(self):
        cfg = json.loads(watcher.CONFIG.read_text(encoding="utf-8"))["boards"]["linkedin_canada"]
        queries = " ".join(cfg["queries"]).lower()
        self.assertIn("banking", queries)
        self.assertIn("co-op", queries)
        self.assertIn("summer analyst", queries)


class LifecycleCoverageTests(unittest.TestCase):
    @patch("watcher.requests.post")
    def test_workday_repeated_tail_stores_results_without_closing_missing_jobs(self, post):
        post.side_effect = [workday_page(0, 20, 23), workday_page(20, 2, 0), workday_page(0, 20, 23)]
        con = watcher.db_open(":memory:")
        stamp = watcher.now()
        old = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(timespec="seconds")
        con.execute("INSERT INTO jobs VALUES ('sample','missing','Intern','Toronto','u',?,?)", (stamp, old))
        con.execute("INSERT INTO job_state(board,job_id,status,missing_count) VALUES ('sample','missing','possibly_closed',2)")
        cfg = {"boards": {"sample": {"ats": "workday", "host": "x", "tenant": "x", "site": "x", "complete_listing": True}},
               "filters": {}, "profile": {}}
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), patch("watcher.enrich_descriptions", return_value=0):
                watcher.cycle(cfg, con)
        self.assertEqual(("possibly_closed", 2), con.execute(
            "SELECT status,missing_count FROM job_state WHERE job_id='missing'").fetchone())
        self.assertEqual(22, con.execute("SELECT COUNT(*) FROM jobs WHERE job_id LIKE '/job/%'").fetchone()[0])
        self.assertEqual(0, con.execute("SELECT failures FROM boards WHERE board='sample'").fetchone()[0])
        coverage = json.loads(con.execute("SELECT v FROM kv WHERE k='source_coverage:sample'").fetchone()[0])
        self.assertFalse(coverage["detects_removals"])
        self.assertIn("repeated", coverage["reason"])
        con.close()

    @patch("watcher.requests.post")
    def test_malformed_workday_summary_cannot_close_missing_posting(self, post):
        post.return_value = response({"total": 2, "jobPostings": [
            {"externalPath": "/job/present", "title": "Finance Intern", "locationsText": "Toronto"},
            {"bulletFields": ["R0000476666"]}]})
        con = watcher.db_open(":memory:")
        stamp = watcher.now()
        con.execute("INSERT INTO jobs VALUES ('sample','missing','Intern','Toronto','u',?,?)", (stamp, stamp))
        cfg = {"boards": {"sample": {"ats": "workday", "host": "x", "tenant": "x", "site": "x", "complete_listing": True}},
               "filters": {}, "profile": {}}
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), patch("watcher.enrich_descriptions", return_value=0):
                watcher.cycle(cfg, con)
        state = con.execute("SELECT status FROM job_state WHERE job_id='missing'").fetchone()
        self.assertTrue(state is None or state[0] == "active")
        self.assertIsNotNone(con.execute("SELECT job_id FROM jobs WHERE job_id='/job/present'").fetchone())
        coverage = json.loads(con.execute("SELECT v FROM kv WHERE k='source_coverage:sample'").fetchone()[0])
        self.assertEqual(1, coverage["fetched"])
        self.assertEqual(2, coverage["reported_total"])
        self.assertFalse(coverage["complete"])
        self.assertIn("malformed", coverage["reason"])
        con.close()

    def test_partial_listing_override_cannot_mark_missing_posting_closed(self):
        con = watcher.db_open(":memory:")
        stamp = watcher.now()
        con.execute("INSERT INTO jobs VALUES ('sample','missing','Intern','Toronto','u',?,?)", (stamp, stamp))
        cfg = {"boards": {"sample": {"ats": "fake", "complete_listing": True}}, "filters": {}, "profile": {}}
        listing = watcher.SourceListing([{"id": "present", "title": "Intern", "location": "Toronto", "url": "v"}],
                                        complete=False, reason="source limit reached")
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": lambda cfg: listing}), \
                    patch("watcher.enrich_descriptions", return_value=0):
                watcher.cycle(cfg, con)
        state = con.execute("SELECT status FROM job_state WHERE job_id='missing'").fetchone()
        self.assertTrue(state is None or state[0] == "active")
        coverage = json.loads(con.execute("SELECT v FROM kv WHERE k='source_coverage:sample'").fetchone()[0])
        self.assertEqual(1, coverage["fetched"])
        self.assertFalse(coverage["complete"])
        self.assertEqual("source limit reached", coverage["reason"])
        con.close()


class OfficialHtmlTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_html_result_page_cannot_overrun_explicit_limit(self, get):
        get.return_value = response(text='''<span class="paginationLabel">Results <b>1 – 2</b> of <b>2</b></span>
            <table id="searchresults"><tr class="data-row"><td><a class="jobTitle-link" href="/job/Intern/1/">Intern</a></td></tr>
            <tr class="data-row"><td><a class="jobTitle-link" href="/job/Intern/2/">Intern</a></td></tr></table>''')
        jobs = watcher.fetch_successfactors({"url": "https://jobs.scotiabank.com/go/Students/2298417/", "max": 1})
        self.assertEqual(1, len(jobs))
        self.assertFalse(jobs.complete)

    @patch("watcher.requests.get")
    def test_scotiabank_student_table_preserves_location_and_id(self, get):
        get.return_value = response(text='''<span class="paginationLabel">Results <b>1 – 1</b> of <b>1</b></span>
            <table id="searchresults"><tr class="data-row"><td class="colTitle">
            <a href="/job/Toronto-Finance-Intern/12345/" class="jobTitle-link">Finance Internship/Co-op</a></td>
            <td class="colDate"><span class="jobDate">Oct 7, 2026</span></td>
            <td class="colLocation"><span class="jobLocation">Toronto, ON, CA</span></td></tr></table>''')
        jobs = watcher.fetch_successfactors({"url": "https://jobs.scotiabank.com/go/Students/2298417/"})
        self.assertEqual("12345", jobs[0]["id"])
        self.assertEqual("Toronto, ON, CA", jobs[0]["location"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_national_bank_follows_verified_avature_offset_links(self, get):
        def page(jid, next_link=""):
            return response(text=f'''<table><tbody><tr><th scope="row"><a class="link fw--500"
                data-map="job-detail-link" href="https://emplois.bnc.ca/en_CA/careers/JobDetail/Intern/{jid}">Finance Intern</a></th>
                <td>Montreal, Quebec</td><td>Hybrid</td></tr></tbody></table>{next_link}''')
        get.side_effect = [page(1, '<a class="paginationLink" href="?jobOffset=20&amp;jobRecordsPerPage=20">2</a>'), page(2)]
        jobs = watcher.fetch_avature({"url": "https://emplois.bnc.ca/en_CA/careers/searchjobs/"})
        self.assertEqual(["1", "2"], [j["id"] for j in jobs])
        self.assertEqual("Montreal, Quebec, Canada", jobs[1]["location"])
        self.assertTrue(jobs.complete)


class NewEmployerSourceTests(unittest.TestCase):
    """Adapters added for employers that were listed as coverage gaps."""

    @patch("watcher.requests.get")
    def test_oracle_link_template_points_at_the_employers_own_site(self, get):
        get.return_value = response({"items": [{"TotalJobsCount": 1, "requisitionList": [
            {"Id": "183732", "Title": "2027 | Americas | Chicago | Investment Banking | Summer Associate",
             "PrimaryLocation": "Chicago, IL", "PostedDate": "2026-10-15"}]}]})
        jobs = watcher.fetch_oracle_hcm({"host": "hdpc.fa.us2.oraclecloud.com", "site": "LateralHiring",
                                         "url": "https://higher.gs.com/roles/{id}"})
        self.assertEqual("https://higher.gs.com/roles/183732", jobs[0]["url"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_bank_of_america_pages_the_search_service(self, get):
        def job(rid, title, city, state, country):
            return {"jobRequisitionId": rid, "postingTitle": title, "city": city, "state": state, "country": country,
                    "postedDate": "10/14/2026", "lob": "Global Corporate & Investment Banking",
                    "jcrURL": f"/en-us/students/job-detail/{rid}/slug"}
        get.side_effect = [
            response({"totalMatches": 3, "jobsList": [job("15196", "Investment Banking 2027 Analyst", "Paris", "", "France"),
                                                      job("14913", "Credit Operations CO-OP", "Toronto", "", "Canada")]}),
            response({"totalMatches": 3, "jobsList": [job("15183", "Corporate Banking Analyst", "Charlotte",
                                                          "North Carolina", "United States")]})]
        jobs = watcher.fetch_bofa({"servlet": "campusjobssearchservlet"})
        self.assertEqual(["15196", "14913", "15183"], [j["id"] for j in jobs])
        self.assertEqual("Toronto, Canada", jobs[1]["location"])
        self.assertEqual("Charlotte, North Carolina, United States", jobs[2]["location"])
        self.assertEqual("https://careers.bankofamerica.com/en-us/students/job-detail/15196/slug", jobs[0]["url"])
        self.assertEqual(watcher._date_epoch("2026-10-14"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        self.assertIn("campusjobssearchservlet", get.call_args_list[0].args[0])
        # "rows" is an end index, not a page size: start=2, rows=102 is the next 100.
        self.assertEqual({"start": 0, "rows": 100}, {k: get.call_args_list[0].kwargs["params"][k] for k in ("start", "rows")})
        self.assertEqual({"start": 2, "rows": 102}, {k: get.call_args_list[1].kwargs["params"][k] for k in ("start", "rows")})
        with self.assertRaises(ValueError):
            watcher.fetch_bofa({"servlet": "../admin"})

    @patch("watcher.requests.get")
    def test_bank_of_america_end_of_listing_returns_no_list(self, get):
        get.side_effect = [response({"totalMatches": 5, "jobsList": [
            {"jobRequisitionId": "1", "postingTitle": "Analyst", "jcrURL": "/en-us/job-detail/1/a"}]}),
            response({"totalMatches": 5, "jobsList": None})]
        jobs = watcher.fetch_bofa({})
        self.assertEqual(1, len(jobs))
        self.assertFalse(jobs.complete)               # 1 of 5: never infer closures
        self.assertIn("1 of reported total 5", jobs.reason)

    @patch("watcher.requests.get")
    def test_oleeo_atom_feed(self, get):
        base = "https://evercore.tal.net/vx/mobile-0/appcentre-ext/brand-4/candidate/so/pm/1/pl/2/opp"
        get.return_value = Mock(status_code=200, content=f'''<?xml version="1.0" encoding="UTF-8"?>
            <feed xmlns="http://www.w3.org/2005/Atom"><title>Students and Graduates</title>
            <entry><id>{base}/3420-2027-Graduate-Programme-RESA-Frankfurt/en-GB</id>
              <link rel="alternate" href="{base}/3420-2027-Graduate-Programme-RESA-Frankfurt/en-GB?instant=apply" type="text/html"/>
              <title>2027 Graduate Programme - Real Estate Strategic Advisory (RESA), Frankfurt</title>
              <published>2026-10-09T16:30:00Z</published>
              <content type="xhtml"><div xmlns="http://www.w3.org/1999/xhtml">Title:2027 Graduate Programme<br/>
              Application Deadline:13 Nov 2026 05:30 PM GMT<br/></div></content></entry>
            <entry><id>{base}/3419-Paris-Off-Cycle-Internship/en-GB</id>
              <title>2027 Paris Off-Cycle Internship &amp; Industrials</title>
              <updated>2026-10-09T14:30:00Z</updated></entry></feed>'''.encode())
        get.return_value.raise_for_status.return_value = None
        feed = "https://evercore.tal.net/vx/lang-en-GB/mobile-0/channel-1/appcentre-ext/brand-6/candidate/jobboard/vacancy/2/feed/rss"
        jobs = watcher.fetch_oleeo({"feed": feed})
        self.assertEqual(["3420", "3419"], [j["id"] for j in jobs])
        self.assertEqual(f"{base}/3420-2027-Graduate-Programme-RESA-Frankfurt/en-GB", jobs[0]["url"])
        self.assertEqual("2027 Paris Off-Cycle Internship & Industrials", jobs[1]["title"])
        self.assertIn("Application Deadline:13 Nov 2026", jobs[0]["description"])
        self.assertEqual(watcher._iso_epoch("2026-10-09T16:30:00Z"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        for bad in ("http://evercore.tal.net/feed", "https://evil.example/vacancy/2/feed/rss"):
            with self.subTest(feed=bad), self.assertRaises(ValueError):
                watcher.fetch_oleeo({"feed": bad})

    @patch("watcher.requests.get")
    def test_radancy_results_pages(self, get):
        def page(*jobs, total=3):
            cards = "".join(f'''<li><a href="/en/job/{city.lower()}/{slug}/49841/{jid}" data-job-id="{jid}">
                <h2>{title}</h2><span class="job-location">{loc}</span><span class="job-date-posted">10/14/2026</span></a></li>'''
                            for jid, slug, title, city, loc in jobs)
            return response({"results": f'<section id="search-results" data-total-results="{total}" data-total-pages="2"><ul>{cards}</ul></section>',
                             "hasJobs": True})
        get.side_effect = [page(("99515739872", "avp-sourcing", "AVP-Sourcing", "New-York", "New York, NY"),
                                ("100093032528", "data-analyst", "Data Analyst &amp; Insights", "Heredia", "Heredia, Provincia de Heredia")),
                           page(("101946200240", "economic-research-summer-intern", "Economic Research Summer Intern",
                                 "New-York", "New York, NY"))]
        jobs = watcher.fetch_radancy({"host": "careers.moodys.com", "size": 2})
        self.assertEqual(["99515739872", "100093032528", "101946200240"], [j["id"] for j in jobs])
        self.assertEqual("Data Analyst & Insights", jobs[1]["title"])
        self.assertEqual("New York, NY", jobs[0]["location"])
        self.assertEqual("https://careers.moodys.com/en/job/new-york/avp-sourcing/49841/99515739872", jobs[0]["url"])
        self.assertTrue(jobs.complete)
        self.assertEqual(2, get.call_args_list[1].kwargs["params"]["CurrentPage"])

    @patch("watcher.requests.get")
    def test_icims_portal_pages(self, get):
        def card(jid, title, loc, posted):
            return f'''<li class="iCIMS_JobCardItem"><div class="row"><div class="col-xs-6 header right">
                <span title="{posted} 11:08 PM"> 3 days ago</span></div><div class="col-xs-12 title">
                <a href="https://globalcareers-msci.icims.com/jobs/{jid}/slug/job?in_iframe=1" class="iCIMS_Anchor" title="{jid} - {title}">
                <span class="sr-only field-label">Job Posting Title</span><h3 > {title}</h3></a></div>
                <dl class="iCIMS_JobHeaderGroup"><div class="iCIMS_JobHeaderTag"><dt class="iCIMS_JobHeaderField">
                <span class="glyphicons glyphicons-map-marker" aria-hidden="true"></span> <span class="sr-only field-label">Job Locations</span>
                </dt><dd class="iCIMS_JobHeaderData"><span > {loc}</span></dd></div></dl></div></li>'''

        def page(n, *cards):
            return response(text=f'<div>Page {n} of 2</div><ul class="container-fluid iCIMS_JobsTable">{"".join(cards)}</ul>')
        get.side_effect = [page(1, card(5993, "Senior Associate, Events, APAC", "HK-Hong Kong", "10/11/2026"),
                                card(5968, "Client Consultant Real Assets", "US-NY-New York | UK-London", "10/9/2026")),
                           page(2, card(5967, "Run Rate Auditor", "IN-Mumbai", "10/1/2026"))]
        jobs = watcher.fetch_icims({"host": "globalcareers-msci.icims.com"})
        self.assertEqual(["5993", "5968", "5967"], [j["id"] for j in jobs])
        self.assertEqual("Senior Associate, Events, APAC", jobs[0]["title"])
        self.assertEqual("Hong Kong, HK", jobs[0]["location"])
        self.assertEqual("New York, NY, US; London, UK", jobs[1]["location"])
        self.assertEqual("https://globalcareers-msci.icims.com/jobs/5993/slug/job", jobs[0]["url"])
        self.assertEqual(watcher._date_epoch("2026-10-11"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        self.assertEqual(1, get.call_args_list[1].kwargs["params"]["pr"])
        with self.assertRaises(ValueError):
            watcher.fetch_icims({"host": "evil.example"})

    @patch("watcher.requests.get")
    def test_icims_cards_without_location_keep_the_description(self, get):
        # Susquehanna's portal lists a description snippet instead of location and date.
        get.return_value = response(text='''<ul class="iCIMS_JobsTable"><li class="iCIMS_JobCardItem"><div class="row">
            <div class="col-xs-12 title"><a href="https://careers-sig.icims.com/jobs/10966/accounting-internship/job?in_iframe=1"
            class="iCIMS_Anchor"><h3 > Accounting Internship: Summer 2027</h3></a></div>
            <div class="col-xs-12 description"> As an intern you&rsquo;ll reconcile ledgers...</div></div></li></ul>''')
        jobs = watcher.fetch_icims({"host": "careers-sig.icims.com"})
        self.assertEqual(("10966", ""), (jobs[0]["id"], jobs[0]["location"]))
        self.assertEqual("As an intern you’ll reconcile ledgers...", jobs[0]["description"])
        self.assertTrue(jobs.complete)


if __name__ == "__main__":
    unittest.main()
