"""Adapters added for the Architecture, Engineering & Construction board's employers (second batch):
Taleo's faceted search (HDR) and SelectMinds (Tetra Tech, Arup).
Every request is replaced with small fixtures trimmed from real responses."""
import unittest
from unittest.mock import patch

import watcher
from tests.sources.test_health_adapters import TALEO_JOBS, pager_reply, taleo_page
from tests.sources.test_source_coverage import response

HDR = {"host": "hdr.taleo.net", "section": "ex"}
FACETED_PAGE = '''<html><script>var require = {config: {'fs/FacetedSearchSettings': {waitSeconds: 15,
    queryString: 'lang=en&amp;portal=101430233', resourcesMapAsJSON: {"a":"b"}}}};</script></html>'''
COUNTRIES = {"id": "LOCATION", "facetValueResults": [
    {"id": "1460483283", "text": "United States", "quantity": "5", "level": 1},
    {"id": "8460483283", "text": "Texas", "quantity": "2", "level": 2},
    {"id": "360483283", "text": "Canada", "quantity": "2", "level": 1},
    {"id": "1360483283", "text": "United Kingdom", "quantity": "1", "level": 1}]}


def row(number, title, place, date="Nov 10, 2026"):
    return {"hotJob": False, "jobId": str(700000 + int(number)), "contestNo": str(number),
            "column": [title, '["%s"]' % place, date], "linkedColumn": 0, "locationsColumns": [1]}


def faceted(rows, total, page_no=1, facets=()):
    return response({"requisitionList": rows, "facetResults": list(facets),
                     "pagingData": {"currentPageNo": page_no, "pageSize": 25, "totalCount": total}})


def country_of(body):
    """The Location facet value the posted search is narrowed to ('' for the whole list)."""
    chosen = body["filterSelectionParam"]["searchFilterSelections"][1]
    assert chosen["id"] == "LOCATION"
    return (chosen["selectedValues"] or [""])[0]


def keyword_of(body):
    return body["fieldData"]["fields"]["KEYWORD"]


def server(lists, hidden=()):
    """A fake searchjobs endpoint: lists maps a country id ('' = everything) to its pages (lists of rows).
    Asking past the last page answers the last page again, as HDR's pager does. A keyword search for a job
    number counts the posting the site knows: one it lists (with its row) or one of `hidden`, which it counts
    but never lists; any other number counts 0."""
    def post(url, params=None, json=None, **kw):
        number = keyword_of(json)
        if number:
            rows = [r for page in lists[""] for r in page if r["contestNo"] == number]
            return faceted(rows, 1 if rows or number in hidden else 0, json["pageNo"])
        pages = lists[country_of(json)]
        n = json["pageNo"]
        rows = pages[min(n, len(pages)) - 1]
        total = sum(len(p) for p in pages)
        return faceted(rows, total + lists.get("_over", {}).get(country_of(json), 0), n, [COUNTRIES] if n == 1 else [])
    return post


@patch("watcher.time.sleep")
class TaleoFacetedTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_search_json_is_read_and_multi_location_rows_are_placed_by_country(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        everything = [[row(103, "Project Manager", "Canada-Alberta-Calgary"),
                       row(102, "Transmission Line Engineer", "Multiple Locations"),
                       row(101, "Structural Co-op (Winter 2027)", "Canada-British Columbia-Vancouver")],
                      [row(100, "Roadway Designer", "United States-Texas-Dallas"),
                       row(99, "Water Engineer", "Multiple Locations")]]
        post.side_effect = server({"": everything, "360483283": [[row(103, "Project Manager", "Canada-Alberta-Calgary"),
                                                                 row(102, "Transmission Line Engineer", "Multiple Locations")]],
                                   "1360483283": [[row(101, "Structural Co-op (Winter 2027)", "Multiple Locations")]]})
        # the first page holds 3 rows: that is the page size, so the 2 on the second page end the list
        jobs = watcher.fetch_taleo(HDR)
        self.assertEqual(["103", "102", "101", "100", "99"], [j["id"] for j in jobs])
        self.assertEqual(["Calgary, Alberta, Canada", "Canada", "Vancouver, British Columbia, Canada",
                          "Dallas, Texas, United States", "United States"], [j["location"] for j in jobs])
        self.assertEqual("https://hdr.taleo.net/careersection/ex/jobdetail.ftl?job=103&lang=en", jobs[0]["url"])
        self.assertEqual(watcher._date_epoch("2026-11-10"), jobs[0]["posted"])
        self.assertEqual((5, True, 5), (len(jobs), jobs.complete, jobs.total))
        self.assertEqual(("https://hdr.taleo.net/careersection/rest/jobboard/searchjobs",
                          {"lang": "en", "portal": "101430233"}), (post.call_args.args[0], post.call_args.kwargs["params"]))
        first = post.call_args_list[0].kwargs
        self.assertEqual(("3", "false", 1), (first["json"]["sortingSelection"]["sortBySelectionParam"],
                                              first["json"]["sortingSelection"]["ascendingSortingOrder"], first["json"]["pageNo"]))
        self.assertEqual("America/Toronto", first["headers"]["tzname"])
        asked = [(country_of(c.kwargs["json"]), c.kwargs["json"]["pageNo"]) for c in post.call_args_list]
        self.assertEqual([("", 1), ("", 2), ("360483283", 1), ("1360483283", 1)], asked)      # not the largest country

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_read_short_of_the_total_is_incomplete_but_still_places_its_rows(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        page = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (5, 4, 3, 2)] + [row(1, "Engineer 1", "Multiple Locations")]
        # the total counts 3 postings the pager never lists (HDR: 2331 reported, 2328 listed, last page repeated):
        # never the whole list, so it closes nothing, but its multi-location row still gets its countries
        post.side_effect = server({"": [page[:3], page[3:]], "_over": {"": 3}, "360483283": [[page[4]]],
                                   "1360483283": [[row(9, "Other", "United Kingdom-London")]]})
        jobs = watcher.fetch_taleo(HDR)
        self.assertEqual(([5, 4, 3, 2, 1], 8, False), ([int(j["id"]) for j in jobs], jobs.total, jobs.complete))
        self.assertIn("ended at 5 of reported total 8", jobs.reason)
        self.assertEqual("Canada", jobs[4]["location"])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_stored_postings_missing_from_a_short_read_are_looked_up_by_job_number(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        page = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (5, 4, 3)]
        # the site counts 3 postings its pager never lists; 7 is one of them (stored, still open), 8 and 9 closed
        post.side_effect = server({"": [page], "_over": {"": 3}}, hidden={"7"})
        jobs = watcher.fetch_taleo({**HDR, "_open_ids": {"5", "4", "7", "8", "9", "x-1"}})
        self.assertEqual((frozenset({"8", "9"}), False, 6), (jobs.gone, jobs.complete, jobs.total))
        asked = [keyword_of(c.kwargs["json"]) for c in post.call_args_list if keyword_of(c.kwargs["json"])]
        # a posting this read listed comes first (the lookup must find it, or no zero is trusted); an id that
        # is not a job number is never looked up, since a keyword search for other text proves nothing
        self.assertEqual(["5", "7", "8", "9"], asked)
        self.assertIn("ended at 3 of reported total 6", jobs.reason)
        self.assertIn("2 of 3 missing postings looked up by job number are gone", jobs.reason)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_job_number_lookups_are_capped_and_only_trusted_when_they_find_a_listed_posting(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        page = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (5, 4, 3)]
        post.side_effect = server({"": [page], "_over": {"": 3}})
        with patch.object(watcher, "TALEO_LOOKUPS", 2):
            jobs = watcher.fetch_taleo({**HDR, "_open_ids": {"7", "8", "9"}})
        self.assertEqual(frozenset({"7", "8"}), jobs.gone)
        self.assertIn("2 of 2 missing postings looked up by job number are gone (1 more not looked up)", jobs.reason)
        listed_only = server({"": [page], "_over": {"": 3}})
        post.side_effect = lambda url, json=None, **kw: (faceted([], 0, 1) if keyword_of(json)
                                                          else listed_only(url, json=json, **kw))
        post.reset_mock()
        jobs = watcher.fetch_taleo({**HDR, "_open_ids": {"5", "8"}})
        # the lookup did not find posting 5, which the read just listed: its zeros say nothing
        self.assertEqual((None, False), (jobs.gone, jobs.complete))
        self.assertEqual(["5"], [keyword_of(c.kwargs["json"]) for c in post.call_args_list if keyword_of(c.kwargs["json"])])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_whole_capped_and_unasked_reads_look_nothing_up(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        page = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (5, 4, 3)]
        post.side_effect = server({"": [page]})
        whole = watcher.fetch_taleo({**HDR, "_open_ids": {"5", "8"}})          # the read itself closes 8
        capped = watcher.fetch_taleo({**HDR, "max": 2, "_open_ids": {"5", "8"}})
        post.side_effect = server({"": [page], "_over": {"": 3}})
        unasked = watcher.fetch_taleo(HDR)                                      # no stored postings given
        nothing_missing = watcher.fetch_taleo({**HDR, "_open_ids": {"5", "4"}})
        post.side_effect = server({"": [[]], "_over": {"": 2}})
        empty = watcher.fetch_taleo({**HDR, "_open_ids": {"5", "8"}})         # no listed posting to check a lookup by
        self.assertEqual([None, None, None, frozenset(), None],
                         [j.gone for j in (whole, capped, unasked, nothing_missing, empty)])
        self.assertTrue(whole.complete)
        self.assertFalse(any(keyword_of(c.kwargs["json"]) for c in post.call_args_list))

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_posting_added_mid_read_repeats_a_row_and_is_not_a_reason_to_drop_the_list(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        rows = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (4, 3, 2, 1)]
        post.side_effect = [faceted(rows[:2], 4, 1), faceted(rows[1:3], 4, 2), faceted(rows[3:], 4, 3)]
        jobs = watcher.fetch_taleo(HDR)
        self.assertEqual(["4", "3", "2", "1"], [j["id"] for j in jobs])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_capped_read_is_incomplete_and_unplaced_rows_keep_their_text(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        rows = [row(n, f"Engineer {n}", "Multiple Locations") for n in (3, 2, 1)]
        post.side_effect = server({"": [rows]})
        jobs = watcher.fetch_taleo({**HDR, "max": 2})
        self.assertEqual((2, False), (len(jobs), jobs.complete))
        self.assertIn("source limit 2", jobs.reason)
        self.assertEqual(["Multiple Locations"] * 2, [j["location"] for j in jobs])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_odd_answers_are_errors(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        post.return_value = response({"requisitionList": [{"contestNo": "1", "column": ["x"]}],
                                      "pagingData": {"currentPageNo": 1, "totalCount": 1}})
        with self.assertRaises(RuntimeError):                                # a row of another shape
            watcher.fetch_taleo(HDR)
        post.return_value = response({"errors": ["tz"]})
        with self.assertRaises(RuntimeError):
            watcher.fetch_taleo(HDR)
        get.return_value = response(text="<html>FacetedSearchSettings, no portal</html>")
        with self.assertRaises(RuntimeError):                                # never guess the portal id
            watcher.fetch_taleo(HDR)

    def test_place_names(self, sleep):
        self.assertEqual("Toronto, Ontario, Canada", watcher._taleo_place('["Canada-Ontario-Toronto"]'))
        self.assertEqual("Saint-Laurent, Quebec, Canada", watcher._taleo_place('["Canada-Quebec-Saint-Laurent"]'))
        self.assertEqual("Hagatna, Guam", watcher._taleo_place('["Guam-Hagatna"]'))
        self.assertEqual("", watcher._taleo_place('["Multiple Locations"]'))

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_the_classic_section_still_reads_as_before(self, get, post, sleep):
        get.return_value = response(text=taleo_page(3))
        post.side_effect = [pager_reply(*TALEO_JOBS[:2]), pager_reply(TALEO_JOBS[2])]
        jobs = watcher.fetch_taleo({"host": "hhsc.taleo.net", "section": "2", "page_size": 2})
        self.assertEqual(["127901", "127131", "126966"], [j["id"] for j in jobs])
        self.assertEqual((True, "Ontario-Hamilton"), (jobs.complete, jobs[0]["location"]))
        self.assertTrue(all(c.args[0].endswith("/careersection/2/jobsearch.ajax") for c in post.call_args_list))
        self.assertNotIn("json", post.call_args.kwargs)

    @patch("watcher.requests.get")
    def test_a_faceted_posting_page_gives_its_description(self, get, sleep):
        rich = "!*!%3Cp%3EDesign roadways in Calgary.%3C/p%3E"
        get.return_value = response(text=f'''<script>descRequisition: {{ _size: 1, _hles: ['a'],
           _hlid: ['reqlistitem.no','reqlistitem.contestnumber','reqlistitem.jobfield','reqlistitem.description'],
           _pars: [] }}</script>
           <script>api.fillList('requisitionDescriptionInterface', 'descRequisition', ['793393','197562',
             'Highway + Road','{rich}']);</script>''')
        description, department = watcher.fetch_description({"ats": "taleo", **HDR}, "197562")
        self.assertEqual(("Design roadways in Calgary.", "Highway + Road"), (description, department))
        self.assertEqual("https://hdr.taleo.net/careersection/ex/jobdetail.ftl", get.call_args.args[0])


def sm_row(jid, title, place, category="Ground Engineering", teaser="We are looking for someone who is passionate about", slug="engineer"):
    return f'''<div id="job_list_{jid}" class="job_list_row jlr_Odd ">
        <div class="jlr_right_hldr "><div class="jlr_title"><div class="flg_hldr"><span class="job_flg font_header_bold new_flg">New</span></div>
          <p><a href="https://jobs.example.com/jobs/{slug}-{jid}" class="job_link font_bold">{title}</a></p>
          <p class="jlr_company">Europe Region</p>
          <p class="jlr_cat_loc"><span class="font_bold">Location:</span>
            <span class="location">
              {place}
            </span></p>
          <p class="jlr_cat_loc"><span class="font_bold">Category:</span> <span class="category">{category}</span></p></div>
        <div class="jlr_content"><div class="jlr_content_full"><p class="jlr_description">{teaser}...</p></div></div></div></div>'''


def sm_results(rows, page=1, pages=2, total=None, search=22443397):
    return (f'<div class="results_content jResultsContent" data-jsid="{search}" data-keywords="">'
            f'<div class="number_of_results"><span class="total_results">{total if total is not None else len(rows)}</span> results</div>'
            + "".join(rows) + f'<div id="jPaginateNumPages" class="ghost">{pages}.0</div>'
            f'<div id="jPaginateCurrPage" class="ghost">{page}</div></div>')


def sm_search_page(rows, **kw):
    text = ('<html><script>var TVAPP = { property: { site: { short_name: "default657" } } };</script>'
            '<input type = "hidden" name="tsstoken" id = "tsstoken" value ="pniGI+NcIU78lXkB/w+Y1qdkZgveMi61EQzhdTOKqpg="/>'
            + sm_results(rows, **kw) + "</html>")
    r = response(text=text)
    r.history, r.cookies, r.url = [], {}, "https://jobs.example.com/jobs/search/22443397"
    return r


def sm_pager(rows, page, pages=2, total=None):
    return response({"Status": "OK", "UserMessage": "", "Result": sm_results(rows, page=page, pages=pages, total=total)})


SM = {"host": "jobs.example.com"}


@patch("watcher.time.sleep")
class SelectMindsTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_search_pages_are_read_through_the_sites_pager(self, get, post, sleep):
        first = [sm_row(36157, "Senior Geotechnical Engineer", "Copenhagen, -, Denmark"),
                 sm_row(36154, "Ing&eacute;nieur structure", "Montr&eacute;al, Quebec, Canada", category="Structural", teaser="Un poste")]
        hop = response(text="")
        hop.cookies = {"JSESSIONID": "abc"}
        get.return_value = sm_search_page(first, total=3)
        get.return_value.history = [hop]
        post.return_value = sm_pager([sm_row(36034, "Cost Consultant", "Vancouver, British Columbia, Canada and 1 additional location")],
                                     page=2, total=3)
        jobs = watcher.fetch_selectminds(SM)
        self.assertEqual(["36157", "36154", "36034"], [j["id"] for j in jobs])
        self.assertEqual(["Copenhagen, Denmark", "Montréal, Quebec, Canada", "Vancouver, British Columbia, Canada"],
                         [j["location"] for j in jobs])
        self.assertEqual("Ingénieur structure", jobs[1]["title"])
        self.assertEqual(("Structural", "https://jobs.example.com/jobs/engineer-36154"), (jobs[1]["department"], jobs[1]["url"]))
        self.assertEqual(("Un poste...", True), (jobs[1]["description"], jobs[1]["teaser"]))      # the list holds a teaser only
        self.assertEqual((3, True, 3), (len(jobs), jobs.complete, jobs.total))
        self.assertEqual("https://jobs.example.com/jobs/search?all", get.call_args.args[0])
        self.assertEqual("utf-8", get.return_value.encoding)
        call = post.call_args
        self.assertEqual("https://jobs.example.com/ajax/content/job_results", call.args[0])
        self.assertEqual({"JobSearch.id": "22443397", "page_index": 2, "site-name": "default657", "include_site": "true"},
                         call.kwargs["params"])
        self.assertEqual("pniGI+NcIU78lXkB/w+Y1qdkZgveMi61EQzhdTOKqpg=", call.kwargs["headers"]["tss-token"])
        self.assertEqual("abc", call.kwargs["cookies"].get("JSESSIONID"))           # the session the redirect set

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_short_read_capped_read_and_odd_answers_are_not_complete(self, get, post, sleep):
        rows = [sm_row(i, f"Engineer {i}", "Toronto, Ontario, Canada") for i in (3, 2)]
        get.return_value = sm_search_page(rows, total=5, pages=2)
        post.return_value = sm_pager([sm_row(1, "Engineer 1", "Toronto, Ontario, Canada")], page=2, total=5)
        jobs = watcher.fetch_selectminds(SM)
        self.assertEqual((3, False), (len(jobs), jobs.complete))              # the pager ran out of pages at 3 of 5
        self.assertIn("ended at 3 of reported total 5", jobs.reason)
        jobs = watcher.fetch_selectminds({**SM, "max": 2})
        self.assertEqual((2, False), (len(jobs), jobs.complete))
        self.assertIn("source limit 2", jobs.reason)
        post.return_value = response({"Status": "ERROR", "Result": ""})
        with self.assertRaises(RuntimeError):
            watcher.fetch_selectminds(SM)
        post.return_value = sm_pager(rows, page=2, total=5)                   # the same page again
        with self.assertRaises(RuntimeError):
            watcher.fetch_selectminds(SM)
        get.return_value = response(text="<html>Page not found</html>")
        get.return_value.history, get.return_value.url = [], "https://jobs.example.com/"
        with self.assertRaises(RuntimeError):
            watcher.fetch_selectminds(SM)

    @patch("watcher.requests.get")
    def test_config_is_validated(self, get, sleep):
        for bad in ({"host": "jobs.example.com/x"}, {"host": "localhost"}, {"host": "jobs.example.com", "site": "../x"}):
            with self.assertRaises(ValueError):
                watcher.fetch_selectminds(bad)
        with self.assertRaises(ValueError):
            watcher.detail_selectminds({"host": "jobs.example.com"}, "12/../3")
        get.assert_not_called()

    @patch("watcher.requests.get")
    def test_posting_page_description_is_the_job_description_block(self, get, sleep):
        get.return_value = response(text='''<html><dl class="field_category"><dt><a href="/x"><span class="job_icon">&#128193;</span></a></dt>
            <dd><a href="/x"><span class="field_value font_header_light">Ground Engineering</span></a></dd></dl>
            <div class="job_description"><p><strong>Shape a future with purpose.</strong></p>
              <div><p>Design and deliver geotechnical solutions.</p><ul><li>Site investigation</li></ul></div>
              <p>Arup&rsquo;s office opened in 2012.</p></div>
            <div id="jJobInsideInfo">Employees only</div></html>''')
        description, department = watcher.fetch_description({"ats": "selectminds", "host": "jobs.example.com", "site": "surge2"},
                                                            "36157", "https://jobs.example.com/jobs/engineer-36157")
        self.assertEqual("https://jobs.example.com/surge2/jobs/36157", get.call_args.args[0])
        self.assertEqual("utf-8", get.return_value.encoding)
        self.assertEqual("Ground Engineering", department)
        self.assertIn("Design and deliver geotechnical solutions.", description)
        self.assertIn("• Site investigation", description)
        self.assertIn("Arup’s office opened in 2012.", description)
        self.assertNotIn("Employees only", description)
        get.return_value = response(text="<html>no description here</html>")
        with self.assertRaises(ValueError):
            watcher.detail_selectminds(SM, "36157")
