"""Adapters added for the Architecture, Engineering & Construction board's employers: ConnectID career sites
(AtkinsRéalis) and Cornerstone OnDemand career sites (Turner Construction). Every request is replaced with
small fixtures trimmed from real responses."""
import json
import unittest
from unittest.mock import Mock, call, patch

import watcher
from tests.sources.test_source_coverage import response

API = "atkinsats-prod-api.connectid.cloud"
ATKINS = {"ats": "connectid", "host": API, "site": "careers.atkinsrealis.com"}


def atkins_job(req, title, places, description="<h2>Overview</h2><p>Design bridges.</p>", **extra):
    job = {"id": 14745622, "job_requisition_id": req, "language_code": "en", "job_posting_title": title,
           "job_description": description, "job_overview": None, "job_responsibilities": None,
           "person_requirements": None, "rewards_and_benefits": None, "additional_information": None,
           "job_area": "Engineering", "sub_job_area": "Structural", "countries": "Canada",
           "locations": [{"city": "Rouyn-Noranda", "region": "Quebec", "country": "Canada"}],
           "location_mappings": places, "job_status": "active", "is_cms_job": False,
           "start_date": "2026-11-10T00:00:00.000Z"}
    job.update(extra)
    return job


FRENCH = atkins_job("R-170797", "Ingénieur(e) en structure", ["Rouyn-Noranda, Quebec, Canada"],
                    description="<h2>Aperçu</h2><p></p><p>La division structure est à la recherche d'un(e) "
                                "ingénieur(e).</p><ul><li>Faire la conception.</li></ul>")
GRAD = atkins_job("R-162446", "New Graduate, Structural Engineering (2027)",
                  ["Calgary, Alberta, Canada", "Toronto, Ontario, Canada", "Calgary, Alberta, Canada"],
                  start_date="2026-08-30T00:00:00.000Z")
CMS = atkins_job("gr-236", "Nuclear Safety Graduate Programme\xa0", [], start_date=None, job_area=None,
                 locations=[{"city": "Bristol", "region": "Bristol", "country": "United Kingdom"},
                            {"city": "Derby", "region": "Derbyshire", "country": "United Kingdom"}],
                 description=None, job_overview="<h2>Build a career</h2><p>Graduate scheme.</p>",
                 person_requirements="<h3>What you can bring</h3><ul><li>Curiosity</li></ul>", is_cms_job=True)
EMPTY = atkins_job("R-165929", "Architectural Studio Lead", [], description=None, locations=[], job_area="Architecture")


def atkins_page(jobs, total, number=1, per_page=1000):
    return response({"jobs": jobs, "facets": {}, "meta": {"totalCount": total, "perPage": per_page,
                                                          "totalPages": -(-total // per_page), "currentPage": number}})


@patch("watcher.time.sleep")
class ConnectIdTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_search_takes_a_token_and_pages_until_the_total(self, get, post, sleep):
        get.return_value = response({"token": "tok-1"})
        post.side_effect = [atkins_page([FRENCH, GRAD], 3), atkins_page([CMS], 3, number=2)]
        jobs = watcher.fetch_connectid({**ATKINS, "page_size": 2})
        self.assertEqual(["R-170797", "R-162446", "gr-236"], [j["id"] for j in jobs])
        self.assertEqual((3, True, ""), (jobs.total, jobs.complete, jobs.reason))
        self.assertEqual(f"https://{API}/api/jobs/token", get.call_args.args[0])
        first, second = post.call_args_list
        self.assertEqual(f"https://{API}/api/jobs/jobs", first.args[0])
        self.assertEqual("Bearer tok-1", first.kwargs["headers"]["Authorization"])
        self.assertEqual({"limit": 2, "page": 1, "language": "en"}, first.kwargs["json"])
        self.assertEqual(2, second.kwargs["json"]["page"])
        sleep.assert_called_with(watcher.CONNECTID_PAUSE)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_posting_fields(self, get, post, sleep):
        get.return_value = response({"token": "tok-1"})
        post.side_effect = [atkins_page([FRENCH, GRAD, CMS, EMPTY], 4)]
        french, grad, cms, empty = watcher.fetch_connectid(ATKINS)
        self.assertEqual("Ingénieur(e) en structure", french["title"])
        self.assertEqual("Rouyn-Noranda, Quebec, Canada", french["location"])
        # the careers page's own link: slugified title, then the requisition number
        self.assertEqual("https://careers.atkinsrealis.com/en/jobs/ing%C3%A9nieur-e-en-structure-r-170797", french["url"])
        self.assertEqual(watcher._iso_epoch("2026-11-10T00:00:00Z"), french["posted"])
        self.assertEqual("Engineering", french["department"])
        self.assertTrue(french["description"].startswith("Aperçu\n"))
        self.assertIn("La division structure est à la recherche", french["description"])
        self.assertIn("• Faire la conception.", french["description"])
        self.assertNotIn("<", french["description"])
        self.assertEqual("Calgary, Alberta, Canada; Toronto, Ontario, Canada", grad["location"])   # a repeat is dropped
        self.assertEqual("https://careers.atkinsrealis.com/en/jobs/new-graduate-structural-engineering-2027-r-162446",
                         grad["url"])
        # a posting without dates, area or mapped places: the places and the sections come from its other fields
        self.assertEqual("Nuclear Safety Graduate Programme", cms["title"])
        self.assertEqual("Bristol, Bristol, United Kingdom; Derby, Derbyshire, United Kingdom", cms["location"])
        self.assertEqual((None, ""), (cms["posted"], cms["department"]))
        self.assertEqual(["Build a career", "Graduate scheme.", "What you can bring", "• Curiosity"],
                         [p.strip() for p in cms["description"].split("\n") if p.strip()])
        # no text anywhere: no description key, so the detail fetch is tried
        self.assertNotIn("description", empty)
        self.assertEqual("", empty["location"])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_short_read_a_repeat_and_a_cap_are_never_complete(self, get, post, sleep):
        get.return_value = response({"token": "tok-1"})
        post.side_effect = [atkins_page([FRENCH], 3), atkins_page([], 3, number=2)]
        jobs = watcher.fetch_connectid({**ATKINS, "page_size": 1})
        self.assertEqual(["R-170797"], [j["id"] for j in jobs])
        self.assertFalse(jobs.complete)
        self.assertIn("1 of reported total 3", jobs.reason)
        post.side_effect = [atkins_page([FRENCH], 3), atkins_page([FRENCH], 3, number=2)]
        with self.assertRaisesRegex(RuntimeError, "repeated a page"):
            watcher.fetch_connectid({**ATKINS, "page_size": 1})
        post.side_effect = [atkins_page([FRENCH, FRENCH], 2), atkins_page([], 2, number=2)]   # listed twice: total unmet
        jobs = watcher.fetch_connectid(ATKINS)
        self.assertEqual((1, False), (len(jobs), jobs.complete))
        post.side_effect = [atkins_page([FRENCH, GRAD], 2)]
        jobs = watcher.fetch_connectid({**ATKINS, "max": 1})
        self.assertEqual((1, False), (len(jobs), jobs.complete))
        self.assertIn("source limit 1", jobs.reason)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_posting_without_an_id_or_an_answer_without_a_total_is_an_error(self, get, post, sleep):
        get.return_value = response({"token": "tok-1"})
        post.side_effect = [atkins_page([atkins_job("", "No number", [])], 1)]
        with self.assertRaisesRegex(RuntimeError, "without an id"):
            watcher.fetch_connectid(ATKINS)
        post.side_effect = [response({"jobs": [FRENCH]})]
        with self.assertRaisesRegex(RuntimeError, "totalCount"):
            watcher.fetch_connectid(ATKINS)
        get.return_value = response({})
        with self.assertRaisesRegex(RuntimeError, "no token"):
            watcher.fetch_connectid(ATKINS)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_refused_token_is_renewed_once(self, get, post, sleep):
        get.side_effect = [response({"token": "old"}), response({"token": "new"})]
        refused = Mock(status_code=401)
        post.side_effect = [refused, atkins_page([FRENCH], 1)]
        jobs = watcher.fetch_connectid(ATKINS)
        self.assertTrue(jobs.complete)
        self.assertEqual(["Bearer old", "Bearer new"], [c.kwargs["headers"]["Authorization"] for c in post.call_args_list])
        refused.raise_for_status.assert_not_called()
        post.side_effect = [Mock(status_code=403, **{"raise_for_status.side_effect": watcher.requests.HTTPError("403")})] * 2
        get.side_effect = [response({"token": "old"}), response({"token": "new"})]
        with self.assertRaises(watcher.requests.HTTPError):
            watcher.fetch_connectid(ATKINS)

    def test_config_is_validated(self, sleep):
        for bad in ({"host": "evil.example.com"}, {"host": "../x.connectid.cloud"}, {"site": "https://x.com/"},
                    {"site": "localhost"}, {"lang": "de"}, {"page_size": 0}, {"page_size": True}, {"max": 0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                watcher.fetch_connectid({**ATKINS, **bad})
        with self.assertRaises(KeyError):
            watcher.fetch_connectid({"ats": "connectid", "host": API})

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_posting_description_comes_from_the_search_by_its_number(self, get, post, sleep):
        get.return_value = response({"token": "tok-1"})
        post.return_value = atkins_page([GRAD, FRENCH], 2)
        text, dept, meta = watcher.fetch_description(ATKINS, "R-170797", "https://careers.atkinsrealis.com/x")
        self.assertTrue(text.startswith("Aperçu"))
        self.assertEqual("Engineering", dept)
        self.assertEqual({"posted": watcher._iso_epoch("2026-11-10T00:00:00Z")}, meta)
        self.assertEqual("R-170797", post.call_args.kwargs["json"]["job_profile"])
        post.return_value = atkins_page([GRAD], 1)         # the search no longer lists it
        with self.assertRaisesRegex(ValueError, "does not list"):
            watcher.fetch_description(ATKINS, "R-170797")
        post.return_value = atkins_page([CMS], 1)
        text, dept, meta = watcher.fetch_description(ATKINS, "gr-236")
        self.assertIn("Graduate scheme.", text)
        self.assertEqual({}, meta)

    def test_connectid_is_registered(self, sleep):
        self.assertIs(watcher.fetch_connectid, watcher.ADAPTERS["connectid"])
        self.assertTrue(watcher.describable(ATKINS))


CORP = "turnerconstruction"
HOST = f"{CORP}.csod.com"
CLOUD = "https://us.api.csod.com/"
TURNER = {"ats": "csod", "host": HOST, "site": 1}


def career_site(token="tok-1", cloud=CLOUD, corp=CORP, culture="en-US"):
    context = {"corp": corp, "user": -101, "cultureID": 1, "cultureName": culture, "package": "career-site",
               "page": "home", "basePath": "/player-career-site/1.25.6/", "serviceBase": "/",
               "endpoints": {"cloud": cloud, "api": "/"}, "token": token, "theme": "{x};y"}
    page = Mock(status_code=200, text="<html><script>csod.context=" + json.dumps(context) + ";\nvar x = 1;</script></html>")
    page.raise_for_status.return_value = None
    return page


def req(rid, title, locations, date="11/9/2026", description=" Position Description: Build it. "):
    return {"requisitionId": rid, "postingEffectiveDate": date, "postingExpirationDate": "-",
            "displayJobTitle": title, "locations": locations, "externalDescription": description}


AUSTIN = req(22250, "Senior Project Manager (Austin)", [{"city": "Austin", "state": "TX", "country": "US"}],
             description=" Position Description: Leads the team. Reports to: Project Executive. ")
TORONTO = req(22146, "January 2027 - Co-Op - Operational Finance – Toronto & Ottawa",
              [{"city": "Toronto", "state": "ON", "country": "CA"}, {"city": "Toronto", "state": "ON", "country": "CA"},
               {"state": "CA", "country": "US"}, {"country": "US"}], date="10/30/2026",
              description="BUILD YOUR FUTURE WITH TURNER\nOver 16,000 employees.")
SHARED = req(21714, "Rodman, National SPO - Monroe, LA", [{"city": "Monroe", "state": "LA", "country": "US"}])
BARE = req(17012, "Traveling Surveyor", [{"city": "Monroe", "state": "LA", "country": "US"}], description="")


def csod_page(rows, total, status=200):
    r = response({"status": "Success", "timestamp": "2026-11-10T18:55:32Z", "data": {"totalCount": total, "requisitions": rows,
                                                                                    "filters": [], "customFieldFilters": []}})
    r.status_code = status
    return r


@patch("watcher.time.sleep")
class CsodTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_session_token_comes_from_the_page_and_search_pages_until_the_total(self, get, post, sleep):
        get.return_value = career_site()
        post.side_effect = [csod_page([AUSTIN, TORONTO], 3), csod_page([SHARED], 3)]
        jobs = watcher.fetch_csod({**TURNER, "page_size": 2})
        self.assertEqual(["22250", "22146", "21714"], [j["id"] for j in jobs])
        self.assertEqual((3, True, ""), (jobs.total, jobs.complete, jobs.reason))
        self.assertEqual(f"https://{HOST}/ux/ats/careersite/1/home", get.call_args.args[0])
        self.assertEqual({"c": CORP}, get.call_args.kwargs["params"])
        first, second = post.call_args_list
        self.assertEqual(CLOUD + "rec-job-search/external/jobs", first.args[0])
        self.assertEqual("Bearer tok-1", first.kwargs["headers"]["Authorization"])
        body = first.kwargs["json"]
        self.assertEqual((1, 1, 1, 2, 1, "en-US"), tuple(body[k] for k in (
            "careerSiteId", "careerSitePageId", "pageNumber", "pageSize", "cultureId", "cultureName")))
        self.assertEqual(2, second.kwargs["json"]["pageNumber"])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_the_crawl_delay_is_kept_between_every_request(self, get, post, sleep):
        calls = []
        get.side_effect = lambda *a, **k: calls.append("get") or career_site()
        post.side_effect = lambda *a, **k: calls.append("post") or csod_page([AUSTIN], 1)
        sleep.side_effect = lambda s: calls.append(("sleep", s))
        watcher.fetch_csod({**TURNER, "site": [1, 2]})
        self.assertEqual(10.0, watcher.CSOD_PAUSE)
        self.assertEqual(["get", ("sleep", 10.0), "post", ("sleep", 10.0), "post"], calls)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_posting_fields(self, get, post, sleep):
        get.return_value = career_site()
        post.side_effect = [csod_page([AUSTIN, TORONTO, BARE], 3)]
        austin, toronto, bare = watcher.fetch_csod(TURNER)
        self.assertEqual("Austin, TX, United States", austin["location"])
        self.assertEqual(f"https://{HOST}/ux/ats/careersite/1/home/requisition/22250?c={CORP}", austin["url"])
        self.assertEqual(watcher._date_epoch("2026-11-09"), austin["posted"])
        self.assertEqual("Position Description: Leads the team. Reports to: Project Executive.", austin["description"])
        # a real place per entry, a repeat dropped, a state with no city and a bare country kept readable
        self.assertEqual("Toronto, ON, Canada; CA, United States; United States", toronto["location"])
        self.assertEqual("January 2027 - Co-Op - Operational Finance – Toronto & Ottawa", toronto["title"])
        self.assertEqual(watcher._date_epoch("2026-10-30"), toronto["posted"])
        self.assertEqual("BUILD YOUR FUTURE WITH TURNER\nOver 16,000 employees.", toronto["description"])
        self.assertNotIn("description", bare)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_several_career_sites_are_merged_and_a_requisition_on_two_is_kept_once(self, get, post, sleep):
        get.return_value = career_site()
        post.side_effect = [csod_page([AUSTIN, SHARED], 2), csod_page([SHARED, TORONTO], 2)]
        jobs = watcher.fetch_csod({**TURNER, "site": [1, 3]})
        self.assertEqual(["22250", "21714", "22146"], [j["id"] for j in jobs])
        self.assertIn("/careersite/1/home/requisition/21714", jobs[1]["url"])      # the first site that lists it
        self.assertIn("/careersite/3/home/requisition/22146", jobs[2]["url"])
        self.assertEqual((3, True), (jobs.total, jobs.complete))
        self.assertEqual([1, 3], [c.kwargs["json"]["careerSiteId"] for c in post.call_args_list])
        self.assertEqual(1, get.call_count)                                         # one token serves the employer's sites

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_short_read_a_repeat_and_a_cap_are_never_complete(self, get, post, sleep):
        get.return_value = career_site()
        post.side_effect = [csod_page([AUSTIN], 3), csod_page([], 3)]
        jobs = watcher.fetch_csod({**TURNER, "page_size": 1})
        self.assertEqual(["22250"], [j["id"] for j in jobs])
        self.assertFalse(jobs.complete)
        self.assertIn("ended at 1 of reported total 3", jobs.reason)
        # a short site stays incomplete even when another site reads fully
        post.side_effect = [csod_page([AUSTIN], 2), csod_page([], 2), csod_page([TORONTO], 1)]
        jobs = watcher.fetch_csod({**TURNER, "site": [1, 2], "page_size": 1})
        self.assertEqual(["22250", "22146"], [j["id"] for j in jobs])
        self.assertFalse(jobs.complete)
        post.side_effect = [csod_page([AUSTIN], 3), csod_page([AUSTIN], 3)]
        with self.assertRaisesRegex(RuntimeError, "repeated a page"):
            watcher.fetch_csod({**TURNER, "page_size": 1})
        post.side_effect = [csod_page([AUSTIN, AUSTIN], 2), csod_page([], 2)]        # listed twice
        jobs = watcher.fetch_csod(TURNER)
        self.assertEqual((1, False), (len(jobs), jobs.complete))
        self.assertIn("twice", jobs.reason)
        post.side_effect = [csod_page([AUSTIN, TORONTO], 2)]
        jobs = watcher.fetch_csod({**TURNER, "max": 1})
        self.assertEqual((1, False), (len(jobs), jobs.complete))
        self.assertIn("source limit 1", jobs.reason)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_an_empty_career_site_is_complete_and_odd_answers_are_errors(self, get, post, sleep):
        get.return_value = career_site()
        post.side_effect = [csod_page([], 0)]
        jobs = watcher.fetch_csod(TURNER)
        self.assertEqual(([], 0, True), (list(jobs), jobs.total, jobs.complete))
        post.side_effect = [response({"status": "Success", "data": {"requisitions": [AUSTIN]}})]
        with self.assertRaisesRegex(RuntimeError, "totalCount"):
            watcher.fetch_csod(TURNER)
        post.side_effect = [csod_page([req(0, "No id", [])], 1)]
        with self.assertRaisesRegex(RuntimeError, "without an id"):
            watcher.fetch_csod(TURNER)

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_dates_are_read_only_in_the_culture_that_writes_them_month_first(self, get, post, sleep):
        get.return_value = career_site(culture="fr-CA")
        post.side_effect = [csod_page([AUSTIN], 1)]
        self.assertIsNone(watcher.fetch_csod(TURNER)[0]["posted"])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_an_expired_session_token_is_taken_again_from_the_page(self, get, post, sleep):
        get.side_effect = [career_site("old"), career_site("new")]
        post.side_effect = [csod_page([], 0, status=401), csod_page([AUSTIN], 1)]
        jobs = watcher.fetch_csod(TURNER)
        self.assertTrue(jobs.complete)
        self.assertEqual(["Bearer old", "Bearer new"], [c.kwargs["headers"]["Authorization"] for c in post.call_args_list])

    @patch("watcher.requests.get")
    def test_a_page_without_a_session_or_naming_a_foreign_api_is_refused(self, get, sleep):
        for page in (Mock(status_code=200, text="<html>sign in</html>", **{"raise_for_status.return_value": None}),
                     career_site(token=""), career_site(corp="someoneelse"),
                     career_site(cloud="https://evil.example.com/"), career_site(cloud="http://us.api.csod.com/"),
                     Mock(status_code=200, text="csod.context={oops", **{"raise_for_status.return_value": None})):
            get.return_value = page
            with self.subTest(text=page.text[:40]), self.assertRaises(RuntimeError):
                watcher.fetch_csod(TURNER)

    def test_config_is_validated(self, sleep):
        for bad in ({"host": "evil.example.com"}, {"host": "x.csod.com.evil.io"}, {"host": "../x.csod.com"},
                    {"site": 0}, {"site": "1"}, {"site": True}, {"site": []}, {"site": [1, 1]}, {"site": [1, "2"]},
                    {"page_size": 0}, {"page_size": 5000}, {"max": 0}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                watcher.fetch_csod({**TURNER, **bad})
        with self.assertRaises(KeyError):
            watcher.fetch_csod({"ats": "csod", "site": 1})

    @patch("watcher.requests.get")
    def test_posting_description_comes_from_the_requisition_record(self, get, sleep):
        detail = response({"status": 0, "timestamp": "2026-11-10T18:59:11Z", "data": {
            "displayTitle": "Senior Engineer (Austin)", "openDate": "2026-10-15T14:13:19",
            "externalDescription": "<p>Position Description: Resource for Operations staff.\n</p><p>Essential Duties "
                                   "&amp; Responsibilities*:\n</p><ul><li>Review constructability.\n</li></ul>"}})
        get.side_effect = [career_site(), detail]
        text, dept, meta = watcher.fetch_description(TURNER, "22002", "https://x/y")
        self.assertEqual("Position Description: Resource for Operations staff.\n\n Essential Duties & Responsibilities*:"
                         "\n\n• Review constructability.", text)
        self.assertEqual("", dept)
        self.assertEqual({"posted": watcher._date_epoch("2026-10-15")}, meta)
        self.assertEqual(call(f"https://{HOST}/services/x/job-requisition/v2/requisitions/22002/jobDetails",
                              params={"cultureId": 1}, timeout=watcher.TIMEOUT,
                              headers={"User-Agent": watcher.UA, "Accept": "application/json",
                                       "Authorization": "Bearer tok-1"}), get.call_args)
        sleep.assert_called_with(watcher.CSOD_PAUSE)
        get.side_effect = [career_site(), response({"status": 0, "data": None})]
        with self.assertRaisesRegex(ValueError, "no posting data"):
            watcher.fetch_description(TURNER, "22002")
        with self.assertRaises(ValueError):
            watcher.fetch_description(TURNER, "22002/../x")

    def test_csod_is_registered(self, sleep):
        self.assertIs(watcher.fetch_csod, watcher.ADAPTERS["csod"])
        self.assertTrue(watcher.describable(TURNER))


if __name__ == "__main__":
    unittest.main()
