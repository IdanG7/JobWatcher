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


def server(lists):
    """A fake searchjobs endpoint: lists maps a country id ('' = everything) to its pages (lists of rows).
    Asking past the last page answers the last page again, as HDR's pager does."""
    def post(url, params=None, json=None, **kw):
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
    def test_the_pagers_padding_past_the_end_still_completes_but_a_real_gap_does_not(self, get, post, sleep):
        get.return_value = response(text=FACETED_PAGE)
        page = [row(n, f"Engineer {n}", "Canada-Ontario-Toronto") for n in (5, 4, 3, 2, 1)]
        # the total counts 3 postings the pager never lists (HDR: 2331 reported, 2328 listed, last page repeated)
        post.side_effect = server({"": [page[:3], page[3:]], "_over": {"": 3}})
        jobs = watcher.fetch_taleo(HDR)
        self.assertEqual(([5, 4, 3, 2, 1], 8, True), ([int(j["id"]) for j in jobs], jobs.total, jobs.complete))
        post.side_effect = server({"": [page[:3], page[3:]], "_over": {"": 40}})
        jobs = watcher.fetch_taleo(HDR)
        self.assertEqual((5, 45, False), (len(jobs), jobs.total, jobs.complete))
        self.assertIn("ended at 5 of reported total 45", jobs.reason)

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
