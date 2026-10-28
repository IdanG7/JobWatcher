"""Adapters for tech employers' career sites; all HTTP is replaced with fixtures."""
import json
import unittest
from unittest.mock import patch

import watcher
from tests.sources.test_source_coverage import response


@patch("watcher.time.sleep")
class EightfoldTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_pcsx_search_pages_until_the_count(self, get, sleep):
        def page(*ids, count=3):
            return response({"status": 200, "data": {"count": count, "positions": [
                {"id": i, "name": f"Engineer {i}", "locations": ["San Diego, California, United States",
                                                                  "Toronto, Ontario, Canada"],
                 "postedTs": 1784592000, "positionUrl": f"/careers/job/{i}"} for i in ids]}})
        get.side_effect = [page(446719881658, 446719881659), page(446719881660)]
        jobs = watcher.fetch_eightfold({"host": "careers.qualcomm.com", "domain": "qualcomm.com", "api": "pcsx"})
        self.assertEqual(["446719881658", "446719881659", "446719881660"], [j["id"] for j in jobs])
        self.assertEqual("https://careers.qualcomm.com/careers/job/446719881658", jobs[0]["url"])
        self.assertEqual("San Diego, California, United States; Toronto, Ontario, Canada", jobs[0]["location"])
        self.assertEqual(1784592000, jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        self.assertTrue(get.call_args_list[0][0][0].endswith("/api/pcsx/search"))
        self.assertEqual(2, get.call_args_list[1].kwargs["params"]["start"])
        self.assertEqual("", get.call_args_list[0].kwargs["params"]["query"])
        get.side_effect = [page(1, count=1)]
        watcher.fetch_eightfold({"host": "apply.careers.microsoft.com", "domain": "microsoft.com", "api": "pcsx",
                                 "query": "finance"})
        self.assertEqual("finance", get.call_args.kwargs["params"]["query"])

    @patch("watcher.requests.get")
    def test_pcsx_waits_out_a_429(self, get, sleep):
        busy = response({})
        busy.status_code = 429
        get.side_effect = [busy, response({"status": 200, "data": {"count": 1, "positions": [
            {"id": 5, "name": "Engineer", "locations": [], "positionUrl": "/careers/job/5"}]}})]
        jobs = watcher.fetch_eightfold({"host": "careers.lamresearch.com", "domain": "lamresearch.com", "api": "pcsx"})
        self.assertEqual(["5"], [j["id"] for j in jobs])
        sleep.assert_called_once_with(watcher.EIGHTFOLD_BACKOFF[0])

    @patch("watcher.requests.get")
    def test_pcsx_keeps_what_it_read_when_rate_limited(self, get, sleep):
        busy = response({})
        busy.status_code = 429
        busy.raise_for_status.side_effect = watcher.requests.HTTPError(response=busy)
        get.side_effect = [response({"status": 200, "data": {"count": 30, "positions": [
            {"id": 1, "name": "Engineer", "locations": ["US-CA-Fremont (1003)"],
             "standardizedLocations": ["Fremont, CA, US"]}]}})] + [busy] * 4
        jobs = watcher.fetch_eightfold({"host": "careers.lamresearch.com", "domain": "lamresearch.com", "api": "pcsx"})
        self.assertEqual([("1", "Fremont, CA, US")], [(j["id"], j["location"]) for j in jobs])
        self.assertFalse(jobs.complete)
        self.assertIn("rate-limited", jobs.reason)

    @patch("watcher.requests.get")
    def test_older_sites_keep_the_apply_api(self, get, sleep):
        get.return_value = response({"count": 1, "positions": [{"id": 7, "name": "Engineer", "location": "Los Gatos"}]})
        jobs = watcher.fetch_eightfold({"host": "explore.jobs.netflix.net", "domain": "netflix.com"})
        self.assertEqual(["7"], [j["id"] for j in jobs])
        self.assertTrue(get.call_args[0][0].endswith("/api/apply/v2/jobs"))

    @patch("watcher.requests.get")
    def test_pcsx_description(self, get, sleep):
        get.return_value = response({"status": 200, "data": {"jobDescription": "<p>Design <b>codecs</b></p>",
                                                             "department": "ASICS Engineering"}})
        text, dept = watcher.detail_eightfold({"host": "careers.qualcomm.com", "domain": "qualcomm.com",
                                               "api": "pcsx"}, "446719881658")
        self.assertEqual(("Design codecs", "ASICS Engineering"), (text, dept))
        self.assertEqual("446719881658", get.call_args.kwargs["params"]["position_id"])


class SuccessFactorsSearchTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_a_search_page_pages_by_startrow_and_a_category_page_by_path(self, get):
        def page(*ids):
            rows = "".join(f'<tr class="data-row"><td><a class="jobTitle-link" href="/job/Toronto-Engineer-ON/{i}/">Engineer</a>'
                           f'</td></tr>' for i in ids)
            return response(text=f'<span class="paginationLabel">Results <b>1</b> of <b>3</b></span>'
                                 f'<table id="searchresults">{rows}</table>')
        get.side_effect = [page("1", "2"), page("3")]
        jobs = watcher.fetch_successfactors({"url": "https://jobs.rogers.com/search/"})
        self.assertEqual(["1", "2", "3"], [j["id"] for j in jobs])
        self.assertTrue(jobs.complete)
        self.assertEqual("https://jobs.rogers.com/search/", get.call_args.args[0])
        self.assertEqual(2, get.call_args.kwargs["params"]["startrow"])
        get.side_effect = [page("1", "2"), page("3")]
        watcher.fetch_successfactors({"url": "https://jobs.scotiabank.com/go/IT-Jobs/2298017/"})
        self.assertEqual("https://jobs.scotiabank.com/go/IT-Jobs/2298017/2/", get.call_args.args[0])
        self.assertNotIn("startrow", get.call_args.kwargs["params"])


class PhenomCategoryTests(unittest.TestCase):
    @patch("watcher.requests.post")
    def test_categories_narrow_the_search_and_no_categories_selects_everything(self, post):
        post.return_value = response({"refineSearch": {"status": 200, "totalHits": 1, "data": {"jobs": [
            {"jobId": "J1", "title": "Software Engineer", "location": "Charlotte, NC"}]}}})
        jobs = watcher.fetch_phenom({"host": "talent.lowes.com", "categories": ["Technology", "Corporate"]})
        self.assertEqual(["J1"], [j["id"] for j in jobs])
        self.assertEqual({"category": ["Technology", "Corporate"]}, post.call_args.kwargs["json"]["selected_fields"])
        watcher.fetch_phenom({"host": "jobs.rbc.com"})
        self.assertEqual({}, post.call_args.kwargs["json"]["selected_fields"])


class LeverRegionTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_an_eu_board_is_read_from_levers_eu_api(self, get):
        get.return_value = response([{"id": "a1", "text": "Quantum Engineer", "hostedUrl": "https://jobs.eu.lever.co/q/a1"}])
        self.assertEqual(["a1"], [j["id"] for j in watcher.fetch_lever({"token": "quantinuum", "region": "eu"})])
        self.assertEqual("https://api.eu.lever.co/v0/postings/quantinuum?mode=json", get.call_args.args[0])
        watcher.fetch_lever({"token": "belvedere"})
        self.assertEqual("https://api.lever.co/v0/postings/belvedere?mode=json", get.call_args.args[0])


class LinkedInCompanyTests(unittest.TestCase):
    @patch("watcher._linkedin_get")
    def test_company_ids_narrow_the_search(self, get):
        card = ('<li><div data-entity-urn="urn:li:jobPosting:4480023552"><h3 class="base-search-card__title">Software Engineer</h3>'
                '<h4 class="base-search-card__subtitle"><a href="#">Meta</a></h4></div></li>')
        get.return_value = response(text=card)
        get.return_value.status_code = 200
        jobs = watcher.fetch_linkedin({"queries": [""], "companies": [10667, 15564], "pages": 1})
        self.assertEqual([("4480023552", "Meta")], [(j["id"], j["company"]) for j in jobs])
        self.assertEqual("10667,15564", get.call_args[0][1]["f_C"])
        watcher.fetch_linkedin({"query": "software engineer intern", "pages": 1})
        self.assertNotIn("f_C", get.call_args[0][1])


class LayoutTests(unittest.TestCase):
    """Other layouts of adapters finance sources use; their own layouts are tested in test_source_coverage."""

    @patch("watcher.requests.get")
    def test_radancy_cards_with_h3_titles_or_bare_links(self, get):
        arm = '''<li class="job-card"><a class="job-card__title" href="/en/job/austin/theorem-proving-engineer/33099/97584421536"
            data-job-id="97584421536">Theorem Proving&#xA0;Engineer</a> <span class="location">Austin, Texas</span></li>'''
        netapp = '''<li><a href="/en/job/raleigh/sre/27600/98418896160" data-job-id="98418896160"> <h3>Site Reliability Engineer</h3>
            <span class="job-location job-default">Raleigh, North Carolina</span> </a></li>'''
        get.return_value = response({"results": f'<section data-total-results="2"><ul>{arm}{netapp}</ul></section>'})
        jobs = watcher.fetch_radancy({"host": "careers.arm.com"})
        self.assertEqual([("Theorem Proving Engineer", "Austin, Texas"), ("Site Reliability Engineer", "Raleigh, North Carolina")],
                         [(j["title"], j["location"]) for j in jobs])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_avature_result_cards(self, get):
        def page(jid, title, more=""):
            return response(text=f'''<div class="list-controls__text__legend" aria-label="2 results">1-1 of 2 results</div>
                <article class="article article--result"><div class="article__header"><h3 class="article__header__text__title">
                <a class="link" href="https://bloomberg.avature.net/careers/JobDetail/Software-Engineer/{jid}"> {title} </a></h3>
                <span class="list-item-location">New York, NY</span></div></article>{more}''')
        get.side_effect = [page(45796, "Software Engineer",
                                '<a class="paginationLink" href="https://bloomberg.avature.net/careers/SearchJobs/?jobRecordsPerPage=12&amp;jobOffset=12">2</a>'),
                           page(45800, "Data Engineer &amp; Analyst")]
        jobs = watcher.fetch_avature({"url": "https://bloomberg.avature.net/careers/SearchJobs/"})
        self.assertEqual(["45796", "45800"], [j["id"] for j in jobs])
        self.assertEqual(("Data Engineer & Analyst", "New York, NY"), (jobs[1]["title"], jobs[1]["location"]))
        self.assertEqual("https://bloomberg.avature.net/careers/JobDetail/Software-Engineer/45796", jobs[0]["url"])
        self.assertEqual(12, get.call_args_list[1].kwargs["params"]["jobOffset"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_avature_location_search_and_next_links(self, get):
        siemens = '''<article class="article article--result"><h3 class="title"><a class="link"
            href="https://jobs.siemens.com/en_US/externaljobs/JobDetail/{jid}">{title}</a></h3>
            <div class="article__header__text__subtitle"><span class="list-item-location">{loc}</span>
            <span class="separator"> &#8226; </span></div></article>'''
        nested = ('<span class="list-item-jobCity">Kitchener</span><span class="separator">, </span>'
                  '<span class="list-item-jobState">Ontario</span><span class="separator">, </span>'
                  '<span class="list-item-jobCountry">Canada</span> ')
        get.side_effect = [
            response(text=siemens.format(jid=526944, title="Platform Engineer", loc=nested)
                     + '<li class="list-controls__pagination__item paginationNextLink"><a href="https://jobs.siemens.com/'
                       'en_US/externaljobs/SearchJobs/?folderRecordsPerPage=6&amp;folderOffset=6">Next</a></li>'),
            response(text=siemens.format(jid=526950, title="Data Engineer", loc="Multiple Locations"))]
        jobs = watcher.fetch_avature({"url": "https://jobs.siemens.com/en_US/externaljobs/SearchJobs", "location": "Canada"})
        self.assertEqual(["Kitchener, Ontario, Canada", "Multiple Locations, Canada"], [j["location"] for j in jobs])
        first, second = (c.kwargs["params"] for c in get.call_args_list)
        self.assertEqual(("Canada", 1, 0), (first["search"], first["listFilterMode"], first["jobOffset"]))
        self.assertEqual((6, "Canada"), (second["folderOffset"], second["search"]))
        self.assertTrue(jobs.complete)
        lenovo = '''<article class="article article--result"><h3><a href="https://jobs.lenovo.com/en_US/careers/JobDetail/
            AI-Engineer/83002"> AI Engineer </a></h3><span class="paragraph">Development</span>
            <div class="article__header__text__subtitle">
            <span> United States of America, North Carolina, Morrisville </span><br><span>Req #: WD1</span></div></article>'''
        get.side_effect = [response(text=lenovo)]
        jobs = watcher.fetch_avature({"url": "https://jobs.lenovo.com/en_US/careers/SearchJobs", "location": "United States"})
        self.assertEqual("United States of America, North Carolina, Morrisville", jobs[0]["location"])
        get.side_effect = [response(text=siemens.format(jid=1, title="Controller", loc="Multiple Locations"))]
        jobs = watcher.fetch_avature({"url": "https://jobs.siemens.com/en_US/externaljobs/SearchJobs",
                                      "query": "finance", "location": "United States"})
        self.assertEqual("finance United States", get.call_args.kwargs["params"]["search"])
        self.assertEqual("Multiple Locations, United States", jobs[0]["location"])

    @patch("watcher.requests.get")
    def test_avature_folder_list(self, get):
        def item(slug, title, jid):
            return (f'<li role="listitem" class="jobResultItem itemJob"><h3 class="jobTitleMain"><a href="https://'
                    f'epic.avature.net/Careers/FolderDetail/{slug}/{jid}" class="color1">{title}</a></h3></li>')
        get.side_effect = [
            response(text=item("Verona-Wisconsin-United-States-Software-Developer", "Software Developer", 740)
                     + '<a class="paginationItem paginationLink" href="https://epic.avature.net/Careers/SearchJobs/?folderOffset=10">2</a>'),
            response(text=item("Verona-Wisconsin-United-States-Senior-In-House-Counsel", "Senior In-House Counsel", 10455))]
        jobs = watcher.fetch_avature({"url": "https://epic.avature.net/Careers/SearchJobs"})
        self.assertEqual([("740", "Software Developer", "Verona Wisconsin United States"),
                          ("10455", "Senior In-House Counsel", "Verona Wisconsin United States")],
                         [(j["id"], j["title"], j["location"]) for j in jobs])
        self.assertEqual(10, get.call_args_list[1].kwargs["params"]["folderOffset"])
        self.assertTrue(jobs.complete)


class NewAdapterTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_jibe_pages_with_descriptions(self, get):
        def page(*jobs):
            return response({"totalCount": 3, "jobs": [{"data": {
                "req_id": jid, "title": title, "full_location": loc, "country": country, "country_code": code,
                "posted_date": "2026-10-21T16:44:00+0000", "description": "<p>Build <b>firmware</b></p>",
                "qualifications": "<p>C++</p>", "category": [" Engineering"],
                "meta_data": {"canonical_url": f"https://careers.garmin.com/jobs/{jid}?lang=en-us"}}}
                for jid, title, loc, country, code in jobs]})
        get.side_effect = [page(("20396", "Embedded Engineer", "Salem, Oregon", "United States", "US"),
                                ("20184", "Mechanical Engineer", "Taipei, Taiwan", "Taiwan", "TW")),
                           page(("19975", "Trade Compliance Intern", "Olathe, Kansas", "United States", "US"))]
        jobs = watcher.fetch_jibe({"host": "careers.garmin.com"})
        self.assertEqual(["20396", "20184", "19975"], [j["id"] for j in jobs])
        self.assertEqual(["Salem, Oregon, US", "Taipei, Taiwan"], [j["location"] for j in jobs[:2]])
        self.assertEqual("https://careers.garmin.com/jobs/20396?lang=en-us", jobs[0]["url"])
        self.assertEqual("Build firmware\n\nC++", jobs[0]["description"])
        self.assertEqual("Engineering", jobs[0]["department"])
        self.assertEqual(watcher._iso_epoch("2026-10-21T16:44:00+00:00"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        self.assertEqual(2, get.call_args_list[1].kwargs["params"]["page"])
        with self.assertRaises(ValueError):
            watcher.fetch_jibe({"host": "evil.example/x"})

    @patch("watcher.requests.get")
    def test_atlassian_reads_the_page_gallery(self, get):
        gallery = [{"sys": {"id": "a"}, "fields": {"id": "27641", "title": "Principal  Engineer - Canada",
                    "locations": ["Canada -     Canada", "Remote - Remote"]}},
                   {"sys": {"id": "b"}, "fields": {"id": "27636", "title": "Sales Specialist",
                    "locations": ["Salt Lake City - United States -   Salt Lake City, Utah 84044 United States"]}}]
        get.return_value = response(text='<script>window.x={"slots":{"component":[{"type":"careersGallery","parameters":'
                                         '{"data":{"type":"json","value":' + json.dumps(gallery) + '}}}]}};</script>')
        jobs = watcher.fetch_atlassian({})
        self.assertEqual(["27641", "27636"], [j["id"] for j in jobs])
        self.assertEqual(("Principal Engineer - Canada", "Canada; Remote"), (jobs[0]["title"], jobs[0]["location"]))
        self.assertEqual("Salt Lake City, Utah 84044 United States", jobs[1]["location"])
        self.assertEqual("https://www.atlassian.com/company/careers/details/27641", jobs[0]["url"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_workable_widget_and_detail(self, get):
        get.return_value = response({"jobs": [{"shortcode": "81B46579FE", "title": "ML Engineer",
                                               "url": "https://apply.workable.com/j/81B46579FE", "published_on": "2026-10-16",
                                               "locations": [{"city": "Montreal", "region": "Quebec", "country": "Canada"}]}]})
        jobs = watcher.fetch_workable({"account": "mila-2"})
        self.assertEqual(("81B46579FE", "Montreal, Quebec, Canada"), (jobs[0]["id"], jobs[0]["location"]))
        self.assertEqual(watcher._date_epoch("2026-10-16"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)
        get.return_value = response({"description": "<p>Train models</p>", "requirements": "<p>PyTorch</p>",
                                     "benefits": "", "department": ["Research"]})
        self.assertEqual(("Train models\n\nPyTorch", "Research"), watcher.detail_workable({"account": "mila-2"}, "81B46579FE"))
        with self.assertRaises(ValueError):
            watcher.fetch_workable({"account": "../x"})

    @patch("watcher.requests.post")
    def test_ukg_pages_newest_first(self, post):
        def page(*ids):
            return response({"totalCount": 3, "opportunities": [{
                "Id": i, "Title": f"Engineer {i}", "PostedDate": "2026-10-22T22:08:22.905Z",
                "Locations": [{"Address": {"City": "Brampton", "State": {"Code": "ON"}, "Country": {"Name": "Canada"}}}]}
                for i in ids]})
        post.side_effect = [page("a1", "a2"), page("a3")]
        cfg = {"host": "recruiting.ultipro.ca", "tenant": "MAC5000MCDW", "board": "664818ff"}
        jobs = watcher.fetch_ukg(cfg)
        self.assertEqual(["a1", "a2", "a3"], [j["id"] for j in jobs])
        self.assertEqual("Brampton, ON, Canada", jobs[0]["location"])
        self.assertEqual("https://recruiting.ultipro.ca/MAC5000MCDW/JobBoard/664818ff/OpportunityDetail?opportunityId=a1",
                         jobs[0]["url"])
        self.assertEqual(2, post.call_args_list[1].kwargs["json"]["opportunitySearch"]["Skip"])
        self.assertTrue(jobs.complete)
        with self.assertRaises(ValueError):
            watcher.fetch_ukg({**cfg, "host": "evil.example"})

    @patch("watcher.requests.get")
    def test_ukg_detail_reads_the_posting_data(self, get):
        get.return_value = response(text='<script>new US.Opportunity.CandidateOpportunityDetail({"Description":'
                                         '"\\u003cp\\u003eBuild satellites\\u003c/p\\u003e","JobCategoryName":"Engineering"});</script>')
        self.assertEqual(("Build satellites", "Engineering"), watcher.detail_ukg(
            {"host": "recruiting.ultipro.ca", "tenant": "MAC5000MCDW", "board": "664818ff"}, "a1"))

    @patch("watcher.requests.get")
    def test_xml_job_feed(self, get):
        get.return_value = response()
        get.return_value.content = '''<?xml version="1.0" encoding="utf-8"?><source><publisher>Nutanix</publisher>
            <job><title><![CDATA[Software Engineer]]></title><date><![CDATA[2026-10-21T23:27:59.6170000Z]]></date>
            <apijobid><![CDATA[32932]]></apijobid><url><![CDATA[https://careers.nutanix.com/en/jobs/32932/software-engineer/]]></url>
            <city>San Jose</city><state>CA</state><country>United States</country>
            <description><![CDATA[<p>Build <b>HCI</b></p>]]></description><category>Engineering</category></job></source>'''.encode()
        jobs = watcher.fetch_xml_feed({"url": "https://careers.nutanix.com/en/jobs/xml/?rss=true"})
        self.assertEqual(("32932", "San Jose, CA, United States", "Build HCI"),
                         (jobs[0]["id"], jobs[0]["location"], jobs[0]["description"]))
        self.assertTrue(jobs.complete)
        with self.assertRaises(ValueError):
            watcher.fetch_xml_feed({"url": "http://careers.nutanix.com/feed"})

    @patch("watcher.requests.get")
    def test_kula_board_data(self, get):
        jobs = [{"id": 33797, "title": "Head of Hardware", "listed": True, "launch_at": "2026-04-28T19:43:17Z",
                 "ats_job": {"offices": [{"location": "Vancouver, British Columbia, Canada"}]}},
                {"id": 34567, "title": "Unlisted", "listed": False}]
        get.return_value = response(text='0:["$","div"]\n1d:{"company":{"name":"Sanctuary AI"},"jobs":' + json.dumps(jobs) + '}\n')
        out = watcher.fetch_kula({"account": "sanctuary-ai"})
        self.assertEqual([("33797", "Vancouver, British Columbia, Canada")], [(j["id"], j["location"]) for j in out])
        self.assertEqual("https://careers.kula.ai/sanctuary-ai/33797", out[0]["url"])
        self.assertEqual("1", get.call_args.kwargs["headers"]["RSC"])

    @patch("watcher.requests.get")
    def test_kula_titles_keep_their_non_ascii_text(self, get):
        # The payload is UTF-8 with a bare text/x-component type: read as Latin-1, 10x Genomics' Japanese
        # titles came out as mojibake.
        raw = watcher.requests.models.Response()
        raw.status_code, raw.headers["Content-Type"] = 200, "text/x-component"
        raw._content = ('1d:{"jobs":' + json.dumps([{"id": 1, "title": "フィールドサービスエンジニア", "listed": True}],
                                                  ensure_ascii=False) + '}\n').encode("utf-8")
        raw.encoding = watcher.requests.utils.get_encoding_from_headers(raw.headers)    # as requests' adapter sets it
        get.return_value = raw
        self.assertEqual("フィールドサービスエンジニア", watcher.fetch_kula({"account": "10xgenomics"})[0]["title"])

    @patch("watcher.time.sleep")
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_apple_asks_again_for_a_page_it_answered_empty(self, get, post, sleep):
        get.return_value = response()
        get.return_value.headers = {}
        empty = response({"res": {"totalRecords": 0, "searchResults": []}})
        post.side_effect = [empty, response({"res": {"totalRecords": 1, "searchResults": [{"positionId": "7"}]}})]
        self.assertEqual(["7"], [j["id"] for j in watcher.fetch_apple({})])
        sleep.assert_any_call(watcher.APPLE_BACKOFF[0])
        post.side_effect = [empty] * 3
        with self.assertRaises(RuntimeError):
            watcher.fetch_apple({})

    @patch("watcher.time.sleep")
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_apple_search_uses_the_sites_csrf_token(self, get, post, sleep):
        get.return_value = response()
        get.return_value.headers = {"X-Apple-CSRF-Token": "tok"}
        get.return_value.cookies = {"jssid": "s"}

        def page(*ids):
            return response({"res": {"totalRecords": 3, "searchResults": [{
                "positionId": i, "postingTitle": f"Engineer {i}", "postDateInGMT": "2026-10-23T04:25:53Z",
                "jobSummary": "Design silicon.", "team": {"teamName": "Hardware"},
                "locations": [{"city": "Cupertino", "stateProvince": "California", "countryName": "United States of America"}]}
                for i in ids]}})
        post.side_effect = [page("200596966", "200596967"), page("200596968")]
        jobs = watcher.fetch_apple({})
        self.assertEqual(["200596966", "200596967", "200596968"], [j["id"] for j in jobs])
        self.assertEqual("Cupertino, California, United States of America", jobs[0]["location"])
        self.assertEqual("https://jobs.apple.com/en-us/details/200596966", jobs[0]["url"])
        self.assertEqual(("Design silicon.", "Hardware"), (jobs[0]["description"], jobs[0]["department"]))
        self.assertEqual("tok", post.call_args.kwargs["headers"]["X-Apple-CSRF-Token"])
        self.assertEqual({"jssid": "s"}, post.call_args.kwargs["cookies"])
        self.assertEqual(2, post.call_args_list[1].kwargs["json"]["page"])
        self.assertEqual("", post.call_args.kwargs["json"]["query"])
        self.assertTrue(jobs.complete)
        post.side_effect = [page("200596966", "200596967"), page("200596968")]
        watcher.fetch_apple({"query": "finance"})
        self.assertEqual("finance", post.call_args.kwargs["json"]["query"])

    @patch("watcher.requests.get")
    def test_google_results_page_data(self, get):
        def job(i, company="Google"):
            return [str(i), f"Engineer {i}", "https://www.google.com/about/careers/applications/signin?jobId=x",
                    [None, "<ul><li>Ship code</li></ul>"], [None, "<p>BS degree</p>"], None, None, company, "en-US",
                    [["Mountain View, CA, USA", ["Mountain View, CA 94043"], None, "94043", "CA", "US"]],
                    [None, "<p>Join Search</p>"], [2], [1792478321, 533000000]]

        def page(*jobs):
            return response(text="<script>AF_initDataCallback({key: 'ds:1', hash: '2', data:" + json.dumps(
                [list(jobs), None, 3, 20]) + ", sideChannel: {}});</script>")
        get.side_effect = [page(job(1), job(2, "YouTube")), page(job(3))]
        jobs = watcher.fetch_google({})
        self.assertEqual(["1", "2", "3"], [j["id"] for j in jobs])
        self.assertEqual(("Mountain View, CA, USA", "YouTube"), (jobs[0]["location"], jobs[1]["company"]))
        self.assertEqual("https://www.google.com/about/careers/applications/jobs/results/1", jobs[0]["url"])
        self.assertEqual("Join Search\n\n• Ship code\n\nBS degree", jobs[0]["description"])
        self.assertEqual(1792478321, jobs[0]["posted"])
        self.assertIn(("location", "Canada"), get.call_args_list[0].kwargs["params"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_jobs_api_search_pages(self, get):
        def page(*ids):
            return response({"totalJobs": 3, "jobs": [{
                "Id": i, "Title": f"Engineer {i}", "DisplayDate": "2026-10-23T01:33:28Z", "Description": "<p>Scale</p>",
                "Teams": ["Engineering"], "Urls": [{"Url": f"/en/jobs/{i}/", "IsDefault": True}],
                "Locations": [{"City": "Toronto", "Region": "Ontario", "Country": "Canada"}]} for i in ids]})
        get.side_effect = [page(303157, 303158), page(303159)]
        jobs = watcher.fetch_jobs_api({"host": "jobs.uber.com"})
        self.assertEqual(["303157", "303158", "303159"], [j["id"] for j in jobs])
        self.assertEqual(("Toronto, Ontario, Canada", "https://jobs.uber.com/en/jobs/303157/"),
                         (jobs[0]["location"], jobs[0]["url"]))
        self.assertEqual("https://jobs.uber.com/api/jobs/search/", get.call_args_list[0][0][0])
        self.assertEqual({"page": 2, "pagesize": 1000}, get.call_args_list[1].kwargs["params"])
        self.assertTrue(jobs.complete)
        with self.assertRaises(ValueError):
            watcher.fetch_jobs_api({"host": "evil.example"})

    @patch("watcher.requests.get")
    def test_gem_job_board_api(self, get):
        get.return_value = response([{
            "id": "am9icG9zdDpb", "title": "Senior Payroll Specialist ", "absolute_url": "https://jobs.gem.com/freshbooks/am9icG9zdDpb",
            "first_published_at": "2026-10-06T18:24:59.272Z", "content_plain": "Run payroll", "content": "<p>Run payroll</p>",
            "location": {"name": "Canada - Remote"}, "offices": [{"name": "Toronto"}], "departments": [{"name": "Finance"}]}])
        jobs = watcher.fetch_gem({"account": "freshbooks"})
        self.assertEqual(("am9icG9zdDpb", "Senior Payroll Specialist", "Canada - Remote", "Run payroll", "Finance"),
                         tuple(jobs[0][k] for k in ("id", "title", "location", "description", "department")))
        self.assertEqual("https://api.gem.com/job_board/v0/freshbooks/job_posts/", get.call_args[0][0])
        self.assertTrue(jobs.complete)
        with self.assertRaises(ValueError):
            watcher.fetch_gem({"account": "../x"})

    @patch("watcher.requests.get")
    def test_jobvite_company_feed(self, get):
        get.return_value = response()
        get.return_value.content = '''<?xml version="1.0" encoding="UTF-8"?><result><job><id>oQjXAfwq</id>
            <title>Principal Architect</title><category>Cloud, Engineering and R&amp;D</category>
            <location>Broomfield, Colorado</location><date>10/13/2026</date>
            <detail-url><![CDATA[http://app.jobvite.com/CompanyJobs/Job.aspx?c=q31bVfwU&j=oQjXAfwq]]></detail-url>
            <description>&lt;p&gt;Design &lt;b&gt;SIEM&lt;/b&gt;&lt;/p&gt;</description></job></result>'''.encode()
        jobs = watcher.fetch_jobvite({"account": "q31bVfwU"})
        self.assertEqual(("oQjXAfwq", "Broomfield, Colorado", "Design SIEM", "Cloud, Engineering and R&D"),
                         tuple(jobs[0][k] for k in ("id", "location", "description", "department")))
        self.assertEqual("https://app.jobvite.com/CompanyJobs/Job.aspx?c=q31bVfwU&j=oQjXAfwq", jobs[0]["url"])
        self.assertEqual(watcher._us_date_epoch("10/13/2026"), jobs[0]["posted"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_adp_result_cards(self, get):
        def page(jid, title, last):
            return response(text=f'''<div class="card card-job" data-id="{jid}"><div class="job-meta">
                <p><time datetime="2026-10-22">10/22/2026</time></p><p>Technology</p></div>
                <h2 class="card-title"><a class="stretched-link js-view-job" href="/en/jobs/{jid}/x/">{title}</a></h2>
                <span class="job-meta-location">Roseland, New Jersey, United States + 2 other locations</span></div>
                <a href="https://jobs.adp.com/en/jobs/?page=2#results">2</a>{last}''')
        get.side_effect = [page(281472, "Software Engineer", ""), page(281125, "Data Engineer", "")]
        jobs = watcher.fetch_adp({})
        self.assertEqual(["281472", "281125"], [j["id"] for j in jobs])
        self.assertEqual(("Roseland, New Jersey, United States + 2 other locations", "Technology",
                          "https://jobs.adp.com/en/jobs/281472/x/"),
                         (jobs[0]["location"], jobs[0]["department"], jobs[0]["url"]))
        self.assertEqual(watcher._date_epoch("2026-10-22"), jobs[0]["posted"])
        self.assertEqual(2, get.call_args_list[1].kwargs["params"]["page"])
        self.assertTrue(jobs.complete)


if __name__ == "__main__":
    unittest.main()
