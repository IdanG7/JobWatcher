"""Adapters added for the Healthcare board's employers: Dayforce, ADP Workforce Now, BambooHR, Taleo and others.
Every request is replaced with small fixtures trimmed from real responses."""
import json
import unittest
from unittest.mock import patch

import watcher
from tests.sources.test_source_coverage import response


def toronto(name="Mount Sinai Hospital, 600 University Avenue, Toronto, Ontario, Canada"):
    return {"formattedAddress": name, "locationId": 10237, "locationType": 1, "isoCountryCode": "CA",
            "stateCode": "ON", "cityName": "Toronto", "coordinates": "lat:43.6574989;lng:-79.39017249999999"}


def posting(pid, title, locations, start="2026-10-21T10:00:00+00:00", description="Your opportunity"):
    return {"clientNamespace": "sinaihealth", "jobBoardId": 4, "jobPostingId": pid, "jobReqId": 670,
            "jobTitle": title, "jobDescription": description, "hasVirtualLocation": False,
            "postingStartTimestampUTC": start, "postingExpiryTimestampUTC": None, "isEvergreen": False,
            "postingLocations": locations, "searchScore": 0}


def dayforce_page(postings, total, offset=0):
    return response({"jobPostings": postings, "maxCount": total, "offset": offset, "count": len(postings)})


class DayforceTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_search_pages_until_the_total(self, get, post):
        get.return_value = response({"csrfToken": "6e37d681"})
        province = {"formattedAddress": "Michigan, USA", "locationId": 7, "locationType": 2,
                    "isoCountryCode": "US", "stateCode": "MI", "cityName": None}
        country = {"formattedAddress": "United States", "locationId": 1, "locationType": 2,
                   "isoCountryCode": "US", "stateCode": None, "cityName": None}
        post.side_effect = [
            dayforce_page([posting(1705, "Clinical Research Coordinator",
                                 [toronto(), toronto("Sherman Health and Wellness Centre, 9600 Bathurst Street"),
                                  {**toronto("Mississauga"), "cityName": "Mississauga"}],
                                 description="Supporting care&nbsp;\n&nbsp;\nIs this you? That&rsquo;s why we apply."),
                         posting(4963, "Area Vice President - Central", [province, country])], total=3),
            dayforce_page([posting(1657, "Registered Nurse", [toronto()], start="2026-10-22T04:00:00+00:00")],
                        total=3, offset=2),
        ]
        jobs = watcher.fetch_dayforce({"client": "sinaihealth", "site": "sinaihealthcareers", "culture": "en-CA"})
        self.assertEqual(["1705", "4963", "1657"], [j["id"] for j in jobs])
        self.assertEqual("Toronto, ON, CA; Mississauga, ON, CA", jobs[0]["location"])      # the repeat Toronto is dropped
        self.assertEqual("Michigan, USA; United States", jobs[1]["location"])             # no city: the place's own label
        self.assertEqual("https://jobs.dayforcehcm.com/en-CA/sinaihealth/sinaihealthcareers/jobs/1705", jobs[0]["url"])
        self.assertEqual(watcher._iso_epoch("2026-10-21T10:00:00+00:00"), jobs[0]["posted"])
        self.assertIn("Is this you? That’s why we apply.", jobs[0]["description"])        # entities unescaped, as text
        self.assertNotIn("&", jobs[0]["description"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertTrue(get.call_args.args[0].endswith("/api/auth/csrf"))
        first, second = post.call_args_list
        self.assertTrue(first.args[0].endswith("/api/geo/sinaihealth/jobposting/search"))
        self.assertEqual("6e37d681", first.kwargs["headers"]["X-CSRF-TOKEN"])
        self.assertEqual(get.return_value.cookies, first.kwargs["cookies"])
        self.assertEqual(("sinaihealthcareers", "en-CA", 0),
                         tuple(first.kwargs["json"][k] for k in ("jobBoardCode", "cultureCode", "paginationStart")))
        self.assertEqual(2, second.kwargs["json"]["paginationStart"])

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_empty_board_is_complete_and_a_short_read_is_not(self, get, post):
        get.return_value = response({"csrfToken": "6e37d681"})
        post.side_effect = [dayforce_page([], total=0)]
        jobs = watcher.fetch_dayforce({"client": "pp4h663", "site": "CANDIDATEPORTAL"})
        self.assertEqual(([], 0, True), (list(jobs), jobs.total, jobs.complete))
        post.side_effect = [dayforce_page([posting(1, "Nurse", [toronto()])], total=3),
                            dayforce_page([], total=3, offset=1)]
        jobs = watcher.fetch_dayforce({"client": "wch", "site": "CANDIDATEPORTAL"})
        self.assertEqual(["1"], [j["id"] for j in jobs])
        self.assertFalse(jobs.complete)
        self.assertIn("1 of reported total 3", jobs.reason)
        with self.assertRaises(ValueError):
            watcher.fetch_dayforce({"client": "../x", "site": "CANDIDATEPORTAL"})


ADP_CID = "4ed2be93-8bc5-40e2-915f-931884eac404"


def requisition(job_id, title, places=(), posted="2026-10-23T16:11Z"):
    return {"itemID": f"{job_id}_1", "clientRequisitionID": "1235",
            "customFieldGroup": {"dateFields": [{"dateValue": posted, "nameCode": {"codeValue": "PostingDate"}},
                                                {"dateValue": "2026-10-28T00:05Z",
                                                 "nameCode": {"codeValue": "CurrentServerDateTime"}}],
                                 "stringFields": [{"nameCode": {"codeValue": "ExternalJobID"}, "stringValue": job_id},
                                                  {"nameCode": {"codeValue": "HomeDepartment"}, "stringValue": ""}]},
            "postDate": "2026-10-24T01:41:00", "requisitionTitle": title,
            "requisitionLocations": [{"address": {"cityName": city, "countrySubdivisionLevel1": {"codeValue": region},
                                                  "postalCode": ""},
                                      "aliasNames": [], "nameCode": {"shortName": name}}
                                     for city, region, name in places]}


def page(total, *jobs):
    return response({"jobRequisitions": list(jobs), "meta": {"startSequence": 0, "totalNumber": total, "links": []}})


class AdpWorkforceNowTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_requisition_pages_until_the_total(self, get):
        get.side_effect = [
            page(3, requisition("568322", "Senior Office Experience Ambassador ", [("Toronto", "ON", " Toronto, ON, CA")]),
                 requisition("597515", "Data Scientist", [("", "", "Georgia")])),
            page(3, requisition("594080", "Manager, Leadership Giving, Ontario")),   # a tenant with no locations
        ]
        jobs = watcher.fetch_adp_wfn({"cid": ADP_CID, "ccid": "19000101_000001", "lang": "en_CA"})
        self.assertEqual(["568322", "597515", "594080"], [j["id"] for j in jobs])
        self.assertEqual(["Senior Office Experience Ambassador", "Data Scientist", "Manager, Leadership Giving, Ontario"],
                         [j["title"] for j in jobs])
        self.assertEqual(["Toronto, ON, CA", "Georgia", ""], [j["location"] for j in jobs])
        self.assertEqual(f"https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid={ADP_CID}"
                         "&ccId=19000101_000001&jobId=568322&lang=en_CA&source=CC2", jobs[0]["url"])
        self.assertEqual(watcher._iso_epoch("2026-10-23T16:11Z"), jobs[0]["posted"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertEqual([1, 11], [c.kwargs["params"]["$skip"] for c in get.call_args_list])    # 1-based row numbers
        self.assertEqual((ADP_CID, "19000101_000001", 10), tuple(get.call_args_list[0].kwargs["params"][k]
                                                              for k in ("cid", "ccId", "$top")))

    @patch("watcher.requests.get")
    def test_an_employer_with_no_openings_and_a_short_read(self, get):
        get.side_effect = [page(0)]
        jobs = watcher.fetch_adp_wfn({"cid": ADP_CID})
        self.assertEqual(([], 0, True), (list(jobs), jobs.total, jobs.complete))
        get.side_effect = [page(2, requisition("1", "Analyst")), page(2)]       # the feed stops before its total
        jobs = watcher.fetch_adp_wfn({"cid": ADP_CID})
        self.assertFalse(jobs.complete)
        self.assertIn("1 of reported total 2", jobs.reason)
        with self.assertRaises(ValueError):
            watcher.fetch_adp_wfn({"cid": "../x"})

    @patch("watcher.requests.get")
    def test_posting_description_comes_from_the_detail_record(self, get):
        get.return_value = response({"requisitionTitle": "Data Scientist",
                                     "requisitionDescription": "<div><p><strong>Role</strong></p>"
                                                               "<p>Build models&nbsp;for public health.</p></div>"})
        text, department = watcher.detail_adp_wfn({"cid": ADP_CID, "lang": "en_CA"}, "597515")
        self.assertTrue(text.startswith("Role"))
        self.assertIn("Build models", text)
        self.assertNotIn("<", text)
        self.assertEqual("", department)
        self.assertTrue(get.call_args[0][0].endswith("/v1/job-requisitions/597515"))
        get.return_value = response({"postingInstructions": [], "links": [], "organizationalUnits": []})   # closed
        with self.assertRaises(ValueError):
            watcher.detail_adp_wfn({"cid": ADP_CID}, "568086")


def list_row(job_id, name, dept, city, state, kind, ats=None):
    ats = ats or {"country": None, "state": None, "province": None, "city": None}
    return {"id": job_id, "jobOpeningName": name, "departmentId": "18629", "departmentLabel": dept,
            "employmentStatusLabel": "Full-Time", "employmentType": None,
            "location": {"city": city, "state": state}, "atsLocation": ats, "isRemote": None, "locationType": kind}


class BambooHRTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_careers_list_empty_and_short(self, get):
        rows = [list_row("336", "Clinical Research Associate", "Clinical/QARA", "Mississauga", "Ontario", "2"),
                list_row("301", "Field Service Engineer", "Clinical/QARA", None, None, "1",
                         {"country": "United States", "state": "New Jersey", "province": None, "city": "Newark"})]
        get.return_value = response({"meta": {"totalCount": 2}, "result": rows})
        jobs = watcher.fetch_bamboohr({"company": "profoundmedical"})
        self.assertEqual("https://profoundmedical.bamboohr.com/careers/list", get.call_args[0][0])
        self.assertEqual(["336", "301"], [j["id"] for j in jobs])
        self.assertEqual(("Mississauga, Ontario", "Clinical/QARA", "https://profoundmedical.bamboohr.com/careers/336"),
                         (jobs[0]["location"], jobs[0]["department"], jobs[0]["url"]))
        self.assertEqual("Newark, New Jersey, United States (Remote)", jobs[1]["location"])
        self.assertIsNone(jobs[0]["posted"])
        self.assertEqual(2, jobs.total)
        self.assertTrue(jobs.complete)
        get.return_value = response({"meta": {"totalCount": 0}, "result": []})          # Variational AI today
        jobs = watcher.fetch_bamboohr({"company": "variationalai"})
        self.assertEqual((0, 0, True), (len(jobs), jobs.total, jobs.complete))
        get.return_value = response({"meta": {"totalCount": 3}, "result": [   # fewer rows than the reported total
            list_row("464", "Buyer", "Procurement", "MaRS Centre, Toronto  ", "Ontario", "2")]})
        jobs = watcher.fetch_bamboohr({"company": "oicr"})
        self.assertEqual("MaRS Centre, Toronto, Ontario", jobs[0]["location"])
        self.assertFalse(jobs.complete)
        self.assertIn("1 of reported total 3", jobs.reason)
        with self.assertRaises(ValueError):
            watcher.fetch_bamboohr({"company": "oicr.evil.example/x"})
        get.return_value = response({"unexpected": True})
        with self.assertRaises(RuntimeError):
            watcher.fetch_bamboohr({"company": "oicr"})

    @patch("watcher.requests.get")
    def test_posting_detail(self, get):
        get.return_value = response({"meta": {}, "result": {"jobOpening": {
            "jobOpeningName": "Buyer", "departmentLabel": "Procurement", "datePosted": "2026-10-02",
            "description": "<p>About OICR</p><p>Position: Buyer &amp; Procurement</p>"}}})
        text, dept, meta = watcher.detail_bamboohr({"company": "oicr"}, "464")
        self.assertEqual("https://oicr.bamboohr.com/careers/464/detail", get.call_args[0][0])
        self.assertEqual("Procurement", dept)
        self.assertEqual(["About OICR", "Position: Buyer & Procurement"],
                         [line.strip() for line in text.split("\n") if line.strip()])
        self.assertEqual(watcher._date_epoch("2026-10-02"), meta["posted"])
        with self.assertRaises(ValueError):
            watcher.detail_bamboohr({"company": "oicr"}, "../464")


TALEO_LABELS = ["hotjob", "no", "title", "jobschedule", "contestnumber", "basiclocations", "organization", "postingdate"]
TALEO_JOBS = [("false", "769840", "Bio Med Technologist", "Full-time", "127901", "Ontario-Hamilton", "BIOMED", "Oct 26, 2026"),
        ("false", "767737", "Booking Clerk", "Part-time", "127131", "Ontario-Hamilton", "CARDIOVASCULAR GEN", "Oct 26, 2026"),
        ("false", "767195", "Business Clerk", "Part-time", "126966", "Ontario-Hamilton",
         "Neurosciences, Trauma %26 Stroke", "Oct 21, 2026")]


def taleo_page(total, labels=TALEO_LABELS):
    """jobsearch.ftl as the server sends it: the form, the page-size and sort controls, the column labels."""
    hlid = ",".join(f"'reqlistitem.{label}'" for label in labels)
    return f'''<form action="jobsearch.ftl" id="ftlform">
        <input type="hidden" name="csrftoken" id="csrftoken" value="3YHRjs6Pb6HE=" />
        <input type="hidden" name="ftlhistory" id="ftlhistory" value="1793160149773|3.0.7.5" />
        <input type="hidden" name="rlPager.currentPage" id="rlPager.currentPage" value="1" />
        <input type="hidden" name="listRequisition.nbElements" id="listRequisition.nbElements" value="{total}" />
        <input type="checkbox" name="jobfield1" value="8">
        <select id="requisitionListInterface.dropListSize" name="dropListSize" size="1"><option value="5">5</option>
          <option value="10">10</option><option value="100">100</option></select>
        <select id="requisitionListInterface.sortBy" name="dropSortBy" size="1">
          <option value="11">Posting Date (Ascending Order)</option><option value="10">Posting Date (Descending Order)</option>
          <option value="1">Job Title (Ascending Order)</option></select></form>
        <script>requisitionListInterface: {{ _ctls: ['dropListSize','sortBy'], listRequisition: {{
           _size: 10,
           _hles: ['ID3595','ID3619'],
           _hlid: [{hlid}],
           _pars: ['ID3694'] }} }}</script>'''


def pager_reply(*jobs):
    """What jobsearch.ajax answers: callback, pager header, then the rows' cells."""
    cells = "!|!".join(cell for job in jobs for cell in job)
    return response(text="ftlx1!|!ftlPager_processResponse!$!requisitionListInterface!|!rlPager!|!listRequisition"
                         f"!|!1!|!769840!|!5!|!Go to page {{0}}!$!{cells}")


@patch("watcher.time.sleep")
class TaleoTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_pager_calls_page_the_listing_newest_first(self, get, post, sleep):
        get.return_value = response(text=taleo_page(3))
        post.side_effect = [pager_reply(*TALEO_JOBS[:2]), pager_reply(TALEO_JOBS[2])]
        jobs = watcher.fetch_taleo({"host": "hhsc.taleo.net", "section": "2", "page_size": 2})
        self.assertEqual(["127901", "127131", "126966"], [j["id"] for j in jobs])
        self.assertEqual(("Bio Med Technologist", "Ontario-Hamilton", "BIOMED"),
                         (jobs[0]["title"], jobs[0]["location"], jobs[0]["department"]))
        self.assertEqual("https://hhsc.taleo.net/careersection/2/jobdetail.ftl?job=127901&lang=en", jobs[0]["url"])
        self.assertEqual("Neurosciences, Trauma & Stroke", jobs[2]["department"])
        self.assertEqual(watcher._date_epoch("2026-10-26"), jobs[0]["posted"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertEqual("https://hhsc.taleo.net/careersection/2/jobsearch.ftl", get.call_args.args[0])
        first, second = (dict(c.kwargs["data"]) for c in post.call_args_list)
        self.assertTrue(post.call_args_list[0].args[0].endswith("/careersection/2/jobsearch.ajax"))
        self.assertEqual(("1", "2"), (first["rlPager.currentPage"], second["rlPager.currentPage"]))
        self.assertEqual(("10", "2", "PagerComponent", "3YHRjs6Pb6HE="),
                         (first["dropSortBy"], first["dropListSize"], first["ftlcompclass"], first["csrftoken"]))
        self.assertNotIn("jobfield1", first)            # an unticked box is not sent

    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_a_short_read_is_not_complete_and_other_pages_are_not_listings(self, get, post, sleep):
        get.return_value = response(text=taleo_page(3))
        post.side_effect = [pager_reply(*TALEO_JOBS[:2]), pager_reply()]
        jobs = watcher.fetch_taleo({"host": "hhsc.taleo.net", "section": "2", "page_size": 2})
        self.assertEqual(2, len(jobs))
        self.assertFalse(jobs.complete)
        self.assertIn("ended at 2 of reported total 3", jobs.reason)
        get.return_value = response(text=taleo_page(4))                     # a job moved between pages
        post.side_effect = [pager_reply(*TALEO_JOBS[:2]), pager_reply(TALEO_JOBS[2])]
        jobs = watcher.fetch_taleo({"host": "hhsc.taleo.net", "section": "2", "page_size": 2})
        self.assertEqual((3, False), (len(jobs), jobs.complete))
        self.assertIn("ended at 3 of reported total 4", jobs.reason)
        get.return_value = response(text="<html>My Submissions</html>")      # a section that sends you elsewhere
        with self.assertRaises(RuntimeError):
            watcher.fetch_taleo({"host": "kp.taleo.net", "section": "external"})
        with self.assertRaises(ValueError):                                  # Taleo Business Edition
            watcher.fetch_taleo({"host": "phg.tbe.taleo.net", "section": "phg01"})

    @patch("watcher.requests.get")
    def test_posting_page_description_comes_from_the_embedded_row(self, get, sleep):
        rich = "!*!%3Cp style=%22font-family:Arial;%22%3EThe department supports medical devices.%3C/p%3E"
        get.return_value = response(text=f'''<script>descRequisition: {{
           _size: 1,
           _hles: ['ID1273','ID1281'],
           _hlid: ['reqlistitem.no','reqlistitem.contestnumber','reqlistitem.jobfield','reqlistitem.organization',
                   'reqlistitem.description','reqlistitem.description','reqlistitem.qualification','reqlistitem.G14140753286'],
           _pars: [] }}</script>
           <script>api.fillList('requisitionDescriptionInterface', 'descRequisition', ['769840','127901',
             'Technician/Technologist','BIOMED','{rich}','{rich}',
             '!*!%3Cp%3E1. Tool Maker.%3Cbr%3E2. Machine tools.%3C/p%3E','Guidelines for submitting an Application']);</script>''')
        description, department = watcher.detail_taleo({"host": "hhsc.taleo.net", "section": "2"}, "127901")
        self.assertEqual("The department supports medical devices.\n\n1. Tool Maker.\n2. Machine tools.", description)
        self.assertEqual("BIOMED", department)
        self.assertEqual({"job": "127901", "lang": "en"}, get.call_args.kwargs["params"])


TOH = "https://jobposting.ottawahospital.on.ca/psc/jobposting/EMPLOYEE/HRMS/c/HRS_HRAM_FL.HRS_CG_SEARCH_FL.GBL"


def results(rows, total, more=False, state=1):
    """The Fluid search page, trimmed to what the adapter reads: hidden form state, the row count,
    the Search Results grid (one <li> per posting) and the 'more' button."""
    items = "".join(f"""<li class='ps_grid-row psc_rowact psc_disabled' id='HRS_AGNT_RSLT_I$0_row_{n}' >
<span class='ps_box-value'   id='SCH_JOB_TITLE${n}' >{title}</span>
<span class='ps_box-value'   id='HRS_APP_JBSCH_I_HRS_JOB_OPENING_ID${n}' >{jid}</span>
<span class='ps_box-value'   id='LOCATION${n}' >{place}</span>
<span class='ps_box-value'   id='HRS_APP_JBSCH_I_HRS_DEPT_DESCR${n}' >{dept}</span>
<span class='ps_box-value'   id='SCH_OPENED${n}' >{opened}</span></li>"""
                    for n, (jid, title, place, dept, opened) in enumerate(rows))
    button = ("<div class='ps_box-more' onclick=\"submitAction_win0(document.win0,'HRS_AGNT_RSLT_I$hdown$0');\">"
              "<span>more</span></div>") if more else ""
    return f"""<form id='HRS_CG_SEARCH_FL' name='win0' method='post' action="{TOH}">
<input type='hidden' name='ICStateNum' id='ICStateNum' value='{state}' />
<input type='hidden' name='ICSID' id='ICSID' value='abc+/=' />
<input type='hidden' name='ICAction' id='ICAction' value='None' /></form>
<DIV id='win0divHRS_AGNT_RSLT_Irowcnt$0'><span class='ps-text'>{total} rows</span></DIV>
<b>{total}</b> jobs found.<ul class='ps_grid-body'>{items}</ul>{button}"""


ROWS = [("113345", "Administrative Assistant 1", "TOH Cancer Centre - QCH site", "RCP Screening Operations", "10/28/2026"),
        ("113127", "Diagnostic Imag Tech - Nuc Med", "The Ottawa Hospital - Civic Campus", "Nuclear Medicine", "10/27/2026"),
        ("112980", "Pharmacy Technician &amp;&nbsp; Buyer", "The Ottawa Hospital - General Campus", "Pharmacy", "10/26/2026")]


@patch("watcher.time.sleep")
class PeopleSoftTests(unittest.TestCase):
    @patch("watcher.requests.post")
    @patch("watcher.requests.get")
    def test_search_grid_then_more_postback(self, get, post, sleep):
        first = response(text=results(ROWS[:2], 3, more=True))
        first.cookies = {"PSJSESSIONID": "guest"}
        get.return_value = first
        post.return_value = response(text=results(ROWS, 3, state=2))      # every row so far, no 'more'
        jobs = watcher.fetch_peoplesoft({"url": TOH, "site": "2"})
        self.assertEqual(["113345", "113127", "112980"], [j["id"] for j in jobs])
        self.assertEqual(("Administrative Assistant 1", "TOH Cancer Centre - QCH site", "RCP Screening Operations"),
                         (jobs[0]["title"], jobs[0]["location"], jobs[0]["department"]))
        self.assertEqual(watcher._date_epoch("2026-10-28"), jobs[0]["posted"])      # MM/DD/YYYY
        self.assertEqual("Pharmacy Technician & Buyer", jobs[2]["title"])
        self.assertEqual(f"{TOH}?Page=HRS_APP_JBPST_FL&Action=U&FOCUS=Applicant&PostingSeq=1&SiteId=2&JobOpeningId=113345",
                         jobs[0]["url"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertEqual("2", get.call_args.kwargs["params"]["SiteId"])
        sent = post.call_args.kwargs
        self.assertEqual(("HRS_AGNT_RSLT_I$hdown$0", "abc+/=", "1"),
                         (sent["data"]["ICAction"], sent["data"]["ICSID"], sent["data"]["ICStateNum"]))
        self.assertEqual({"PSJSESSIONID": "guest"}, dict(sent["cookies"]))

    @patch("watcher.requests.get")
    def test_other_date_styles_and_a_short_list(self, get, sleep):
        self.assertEqual(watcher._date_epoch("2026-10-26"), watcher._ps_posted("2026-10-26"))      # SickKids
        self.assertEqual(watcher._date_epoch("2026-10-28"), watcher._ps_posted("2026/10/28"))      # LHSC
        self.assertEqual(watcher._date_epoch("2026-11-03"), watcher._ps_posted("03/11/2026", dmy=True))
        self.assertIsNone(watcher._ps_posted(""))
        # the page reports 3 postings but ends at 2 with no 'more': keep them, never call it complete
        get.return_value = response(text=results(ROWS[:2], 3, more=False))
        jobs = watcher.fetch_peoplesoft({"url": TOH, "site": "2", "place": "Ottawa, Ontario"})
        self.assertEqual(2, len(jobs))
        self.assertFalse(jobs.complete)
        self.assertIn("2 of reported total 3", jobs.reason)
        self.assertEqual("TOH Cancer Centre - QCH site, Ottawa, Ontario", jobs[0]["location"])
        with self.assertRaises(ValueError):
            watcher.fetch_peoplesoft({"url": "https://example.com/careers", "site": "2"})
        # a site with no postings renders "No jobs found." and no grid; a page with neither is an error
        get.return_value = response(text="<div class='ps_box-group psc_grid-norows'>No jobs found.</div>")
        none = watcher.fetch_peoplesoft({"url": TOH, "site": "6"})
        self.assertEqual((0, 0, True), (len(none), none.total, none.complete))
        get.return_value = response(text="<html>Sign in to PeopleSoft</html>")
        with self.assertRaises(RuntimeError):
            watcher.fetch_peoplesoft({"url": TOH, "site": "6"})

    @patch("watcher.requests.get")
    def test_posting_page_sections(self, get, sleep):
        get.return_value = response(text="""
<span class='ps-text' id='HRS_SCH_WRK_DESCR100$0lbl'>Position Information</span>
<span class='ps_box-value' id=HRS_SCH_PSTDSC_DESCRLONG$0 > <p>Answers <span style="x">phones</span> and books visits.</p> </span> </DIV>
<span class='ps-text' id='HRS_SCH_WRK_DESCR100$1lbl'>Qualifications</span>
<span class='ps_box-value' id=HRS_SCH_PSTDSC_DESCRLONG$1 ><ul><li>College diploma</li></ul></span> </DIV>""")
        text, dept = watcher.detail_peoplesoft({"url": TOH, "site": "2"}, "113345")
        self.assertEqual("Position Information\nAnswers phones and books visits.\n\nQualifications\n• College diploma", text)
        self.assertEqual("", dept)
        params = get.call_args.kwargs["params"]
        self.assertEqual(("HRS_APP_JBPST_FL", "113345", "1"), (params["Page"], params["JobOpeningId"], params["PostingSeq"]))
        get.return_value = response(text="<html>Job no longer available</html>")
        with self.assertRaises(ValueError):
            watcher.detail_peoplesoft({"url": TOH, "site": "2"}, "1")


def gc_card(poster, title, closing, org, places, path="/psrs-srfp/applicant/page1800"):
    return f'''<li class="searchResult"><div><strong> <a href="{path}?poster={poster}">{title}</a></strong> </div>
        <div class="tableTable"><div class="tableRow"><div class="tableCell">
        Closing date: {closing}
        <br />
        {org}
        <br />
        {places}
        </div><div class="tableCell">English essential<br />$25.17 to $38.38 per hour</div></div></div>
        <hr class="searchJobHrLine" /></li>'''


def gc_results(total, *cards, tail=""):
    return response(text=f'''<div class="searchResults"><ul class="searchResultTab"><li class="searchResultTabSelected">
        <a href="page2440?tab=1&tabKeepCriteria=1" title="Currently selected">Jobs open to the public ({total})</a></li></ul>
        <ol start="1" class="posterInfo list-more-space">{"".join(cards)}</ol>{tail}</div>''')


@patch("watcher.time.sleep")
class GcJobsTests(unittest.TestCase):
    @patch("watcher.requests.Session")
    def test_search_pages_until_the_total(self, session, sleep):
        http = session.return_value
        http.get.side_effect = [
            response(text="<html>start</html>"), response({"hasAccess": [False]}),
            gc_results(3,
                    gc_card(2461512, "Environmental Epigenetics Research Affiliate Program Student", "2026-11-02",
                         "Health Canada\n- Environmental and Radiation Health Sciences Directorate",
                         "Calgary (Alberta), Edmonton (Alberta), Ottawa (Ontario)"),
                    gc_card(2449076, "NU-CHN-03 Occupational Health Nurse Inventory", "2027-03-31", "Health Canada",
                         "Various Locations<br />")),
            gc_results(3, gc_card(1, "ONGOING STUDENT RECRUITMENT", "N/A", "All organizations", "Across Canada",
                            path="/srs-sre/page01.html")),
        ]
        jobs = watcher.fetch_gc_jobs({"departments": [117, 1094]})
        self.assertEqual(["2461512", "2449076", "1"], [j["id"] for j in jobs])
        self.assertEqual(("Environmental Epigenetics Research Affiliate Program Student",
                          "Health Canada - Environmental and Radiation Health Sciences Directorate",
                          "Calgary (Alberta), Edmonton (Alberta), Ottawa (Ontario)",
                          "https://emploisfp-psjobs.cfp-psc.gc.ca/psrs-srfp/applicant/page1800?poster=2461512"),
                         tuple(jobs[0][k] for k in ("title", "department", "location", "url")))
        self.assertEqual(("Various Locations", "$25.17 to $38.38 per hour"), (jobs[1]["location"], jobs[1]["salary"]))
        self.assertIsNone(jobs[0]["posted"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        search = [c.kwargs["params"] for c in http.get.call_args_list[2:]]
        self.assertEqual([("department", 117), ("department", 1094)],
                         [p for p in search[0] if p[0] == "department"])
        self.assertIn(("isSecondPartOfPage", 1), search[0])
        self.assertEqual(("requestedPage", 2), search[1][0])
        self.assertEqual(("fromPage", 1), search[1][1])

    @patch("watcher.requests.Session")
    def test_a_page_without_the_result_count_is_an_error(self, session, sleep):
        session.return_value.get.side_effect = [response(text="x"), response({}),
                                                response(text="<p>The page is being updated. Please wait...</p>")]
        with self.assertRaises(RuntimeError):
            watcher.fetch_gc_jobs({"departments": [117]})
        with self.assertRaises(ValueError):
            watcher.fetch_gc_jobs({"departments": ["117"]})

    @patch("watcher.requests.Session")
    def test_no_jobs_found_is_a_complete_empty_listing(self, session, sleep):
        session.return_value.get.side_effect = [response(text="x"), response({}),
                                                gc_results(0, tail="<p><strong>No jobs found</strong>.</p>")]
        jobs = watcher.fetch_gc_jobs({"departments": [117], "title": "zzz"})
        self.assertEqual((0, 0, True), (len(jobs), jobs.total, jobs.complete))

    @patch("watcher.requests.get")
    def test_posting_page_sections(self, get, sleep):
        get.return_value = response(text='''<h2 class="pst-h2">Health Canada
            - Environmental and Radiation Health Sciences Directorate</h2>
            <div id="aboutPosition"><h2>About the position</h2><div class="bottomSpace"><b>Intent of the process</b><br>
            The immediate need is to staff (1) position.</div></div>
            <div id="youNeed"><h2>You need (essential for the job)</h2><p>Enrolled in a Masters program</p></div>
            <div id="ourCommitment"><h2>Our commitment</h2></div>
            <div id="hiringOrgContact">Name: A Person</div>''')
        text, dept = watcher.detail_gc_jobs({}, "2461512")
        self.assertIn("The immediate need is to staff (1) position.", text)
        self.assertIn("Enrolled in a Masters program", text)
        self.assertNotIn("Our commitment", text)
        self.assertNotIn("A Person", text)
        self.assertEqual("Health Canada - Environmental and Radiation Health Sciences Directorate", dept)
        self.assertEqual({"poster": "2461512"}, get.call_args.kwargs["params"])
        get.return_value = response(text="<h1>You will leave the <abbr>GC</abbr> Jobs Web site</h1>")
        with self.assertRaisesRegex(ValueError, "another site"):
            watcher.detail_gc_jobs({}, "2449076")


def neogov_card(job_id, slug, title, dept, meta, posted):
    return f'''<li class="list-item" data-job-id="{job_id}"><h3 class="job-item-link-container">
        <a aria-label="{title} Link will be opened in a flyout." class="item-details-link"
           data-department-name="{dept}" href="/careers/colorado/jobs/{job_id}/{slug}" rel="">{title}</a></h3>
        <ul class="list-meta">{meta}<li>Department: {dept}</li></ul>
        <div class="list-entry">This posting is only open to current residents of the State of Colorado. ABOUT CDPHE</div>
        <div class="list-published"><span class="list-entry-starts"><span>{posted}</span></span><span class="divider">|</span>
        <span class="list-entry-ends">Closes in 2 weeks</span></div></li>'''


NEOGOV_PAY = '<li>Full Time <span>-</span> $66,024.00 Annually</li>'


def neogov_fragment(total, *cards):
    return response(text=f'''<div class="listing-title"><span id="job-postings-number">{total}</span> Job Postings found</div>
        <ul class="unstyled search-results-listing-container job-listing-container hidden">{"".join(cards)}</ul>''')


class NeogovTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_agency_list_pages_until_the_total(self, get):
        get.side_effect = [
            neogov_fragment(3, neogov_card(5530775, "field-health-compliance-inspector", "Field Health Compliance Inspector",
                             "Department of Public Health &amp; Environment", "<li>Denver Metro, CO</li>" + NEOGOV_PAY,
                             "Posted today"),
                     neogov_card(5530001, "epidemiologist", "Epidemiologist",
                          "Department of Public Health &amp; Environment", "<li>Denver, CO</li>" + NEOGOV_PAY,
                          "Posted more than 30 days ago")),
            neogov_fragment(3, neogov_card(5529000, "nurse", "Nurse Consultant", "Department of Public Health &amp; Environment",
                             NEOGOV_PAY.replace("$66,024.00 Annually", "See Position Description"), "Posted 3 days ago")),
        ]
        jobs = watcher.fetch_neogov({"agency": "colorado", "department": ["Department of Public Health & Environment"],
                                     "place": "Colorado"})
        self.assertEqual(["5530775", "5530001", "5529000"], [j["id"] for j in jobs])
        self.assertEqual(("Field Health Compliance Inspector", "Denver Metro, CO", "$66,024.00 Annually",
                          "Department of Public Health & Environment",
                          "https://www.governmentjobs.com/careers/colorado/jobs/5530775/field-health-compliance-inspector"),
                         tuple(jobs[0][k] for k in ("title", "location", "salary", "department", "url")))
        self.assertEqual(watcher._workday_posted_epoch("Posted today"), jobs[0]["posted"])
        self.assertIsNone(jobs[1]["posted"])                       # "more than 30 days ago" is only a bound
        self.assertEqual(("Colorado", "See Position Description"), (jobs[2]["location"], jobs[2]["salary"]))
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        first, second = (c.kwargs["params"] for c in get.call_args_list)
        self.assertIn(("department", "Department of Public Health & Environment"), first)
        self.assertIn(("agency", "colorado"), first)
        self.assertEqual([("page", 1), ("page", 2)], [next(p for p in q if p[0] == "page") for q in (first, second)])
        self.assertEqual("XMLHttpRequest", get.call_args.kwargs["headers"]["X-Requested-With"])

    @patch("watcher.requests.get")
    def test_missing_count_and_short_paging(self, get):
        get.return_value = response(text="<h1>Cannot load jobs.</h1>")
        with self.assertRaises(RuntimeError):
            watcher.fetch_neogov({"agency": "lacounty"})
        with self.assertRaises(ValueError):
            watcher.fetch_neogov({"agency": "../x"})
        # the list ends before the reported total: kept, but not complete
        get.side_effect = [neogov_fragment(12, neogov_card(1, "a", "A", "PUBLIC HEALTH", NEOGOV_PAY, "Posted today")),
                           response(text="<ul class='job-listing-container'></ul>")]
        jobs = watcher.fetch_neogov({"agency": "lacounty", "department": ["PUBLIC HEALTH"]})
        self.assertEqual((1, 12, False), (len(jobs), jobs.total, jobs.complete))
        self.assertIn("1 of reported total 12", jobs.reason)

    @patch("watcher.requests.get")
    def test_posting_page_job_posting_data(self, get):
        get.return_value = response(text='''<script type="application/ld+json">{"@context": "https://schema.org/",
            "@type": "JobPosting", "title": "EPIDEMIOLOGY ANALYST",
            "description": "&lt;p&gt;Conduct &lt;b&gt;disease surveillance&lt;/b&gt; analyses for the County.&lt;/p&gt;",
            "datePosted": "2026-09-15", "hiringOrganization": {"@type": "Organization", "name": "County of Los Angeles"}}
            </script>''')
        text, dept, meta = watcher.detail_neogov({"agency": "lacounty"}, "4852599")
        self.assertEqual("Conduct disease surveillance analyses for the County.", text)
        self.assertEqual(watcher._date_epoch("2026-09-15"), meta["posted"])
        self.assertTrue(get.call_args[0][0].endswith("/careers/lacounty/jobs/4852599"))


def paradox_site(jobs, total, params=None):
    """A Paradox list page: the jobSearch state is embedded in the HTML."""
    state = {"jobSearch": {"params": params or {"page_size": 20, "filter": {}}, "totalJob": total, "jobs": jobs}}
    return response(text=f"<html><script>window.__PRELOAD_STATE__ = {json.dumps(state)};</script></html>")


def paradox_posting(ref, title, place="Kingston, ON", brand="Loblaws", slug="pharmacist", fields=(), name=""):
    return {"reference": ref, "requisitionID": ref, "title": title, "brandName": brand,
            "locations": [{"cityStateAbbr": place, "locationName": name, "countryAbbr": "CA"}],
            "originalURL": f"{slug}/job/{ref}", "customFields": list(fields)}


@patch("watcher.time.sleep")
class ParadoxTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_filtered_list_pages_until_the_total(self, get, sleep):
        params = {"page_size": 20, "filter": {"category": ["Pharmacy"]}}
        get.side_effect = [
            paradox_site([paradox_posting("R2000715149", "Pharmacist"), paradox_posting("R2000711379", "Pharmacist", "Guelph, ON", "Zehrs")],
                 3, params),
            paradox_site([paradox_posting("R2000708267", "Director, Pharmacy Operations (12 mos contract)", "Vancouver, BC",
                          "Shoppers Drug Mart", "director-pharmacy-operations-12-mos-contract")], 0, params)]
        jobs = watcher.fetch_paradox({"host": "careers.loblaw.ca", "filter": {"category": ["Pharmacy"]}})
        self.assertEqual(["R2000715149", "R2000711379", "R2000708267"], [j["id"] for j in jobs])
        self.assertEqual(("Kingston, ON", "Loblaws", "https://careers.loblaw.ca/pharmacist/job/R2000715149"),
                         tuple(jobs[0][k] for k in ("location", "department", "url")))
        self.assertIsNone(jobs[0]["posted"])
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertEqual("https://careers.loblaw.ca/jobs", get.call_args_list[0][0][0])
        self.assertEqual("https://careers.loblaw.ca/jobs/page/2", get.call_args_list[1][0][0])
        self.assertEqual({"page_size": 20, "filter[category][0]": "Pharmacy"}, get.call_args_list[0].kwargs["params"])

    @patch("watcher.requests.get")
    def test_landing_page_posted_date_and_accented_link(self, get, sleep):
        get.return_value = paradox_site([
            paradox_posting("8C378A15918B92900FE7DEA853137CE1", "Testing Specialist - 141968", "", "", "testing-specialist-141968",
                    [{"cfKey": "cf_date_posted", "value": "2026-10-27"}], name="La Jolla"),
            paradox_posting("R2000707405", "Adjoint(e) en pharmacie", "Saint-Felicien, QC", "Pharmaprix",
                    "adjoint-e-en-pharmacie-rémunéré-e")], 2)
        jobs = watcher.fetch_paradox({"host": "employment.ucsd.edu", "path": "uc-san-diego-health"})
        self.assertEqual("https://employment.ucsd.edu/uc-san-diego-health", get.call_args[0][0])
        self.assertEqual(watcher._date_epoch("2026-10-27"), jobs[0]["posted"])
        self.assertEqual("La Jolla", jobs[0]["location"])
        self.assertEqual("https://employment.ucsd.edu/adjoint-e-en-pharmacie-r%C3%A9mun%C3%A9r%C3%A9-e/job/R2000707405",
                         jobs[1]["url"])
        self.assertTrue(jobs.complete)

    @patch("watcher.requests.get")
    def test_refuses_an_ignored_filter_and_marks_a_short_list_partial(self, get, sleep):
        get.return_value = paradox_site([paradox_posting("R1", "Pharmacist")], 1)          # the site echoed no filter
        with self.assertRaises(RuntimeError):
            watcher.fetch_paradox({"host": "careers.loblaw.ca", "filter": {"category": ["Pharmacy"]}})
        get.side_effect = [paradox_site([paradox_posting("R1", "Pharmacist"), paradox_posting("R2", "Pharmacist")], 5), paradox_site([], 0)]
        jobs = watcher.fetch_paradox({"host": "careers.loblaw.ca"})
        self.assertFalse(jobs.complete)
        self.assertIn("2 of reported total 5", jobs.reason)
        with self.assertRaises(ValueError):
            watcher.fetch_paradox({"host": "careers.loblaw.ca/../x"})


def toronto_tile(jid, title, slug, date="Oct 28, 2026", site="jobsatcity", stream="Administrative"):
    href = f"/{site}/job/{slug}/{jid}/"
    section = lambda name, label, value: (   # noqa: E731
        f'<div id="job-{jid}-desktop-section-{name}" class="section-field {name}">'
        f'<span id="job-{jid}-desktop-section-{name}-label" aria-describedby="job-{jid}-desktop-section-{name}-value">{label}</span>'
        f'<div id="job-{jid}-desktop-section-{name}-value">\n{value}\n</div></div>')
    return (f'<li class="job-tile job-id-{jid} job-row-index-1" data-url="{href}"><div class="job-tile-cell">'
            f'<div class="sub-section-desktop"><span class="title"><a class="jobTitle-link fontcolorb6a533a1" '
            f'data-focus-tile=".job-id-{jid}" href="{href}">\n{title}\n</a></span>'
            + section("department", "Job Stream", stream) + section("shifttype", "Position Type", "Full-time")
            + section("date", "Posting Date", date) + '</div><div class="sub-section-mobile"><span class="title">'
            f'<a class="jobTitle-link" href="{href}">{title}</a></span></div></div></li>')


def toronto_page(total, *tiles):
    return response(text='<span id="tile-search-results-label">Showing 1 to 2 of %d Jobs</span>'
                         '<ul id="job-tile-list" data-per-page="2">%s</ul>'
                         '<script>j2w.SearchResults.init({jobRecordsPerPage: parseInt("2"), '
                         'jobRecordsFound: parseInt("%d")});</script>' % (total, "".join(tiles), total))


A = toronto_tile(606586117, "SUPERVISOR CONTRACT SERVICES", "Toronto-SUPERVISOR-CONTRACT-SERVICES-ON-M3J-2E1")
B = toronto_tile(605549117, "Skate Program Instructor - North York District",
                 "Toronto-Skate-Program-Instructor-North-York-District-ON", "Oct 27, 2026", "recreation", "Recreation")
C = toronto_tile(607222817, "EVALUATOR PROGRAMS", "Toronto-EVALUATOR-PROGRAMS-ON-M5V-0C4", "Oct 26, 2026")
D = toronto_tile(607235517, "ELECTRICIAN", "Toronto-ELECTRICIAN-ON-M9V-3T1", "Oct 26, 2026")


@patch("watcher.time.sleep")
class SuccessFactorsPortalTests(unittest.TestCase):
    @patch("watcher.requests.get")
    def test_tile_layout_pages_by_startrow(self, get, sleep):
        get.side_effect = [toronto_page(3, A, B), toronto_page(3, C)]
        jobs = watcher.fetch_successfactors_portal({"url": "https://jobs.toronto.ca/search/", "location": "Toronto, ON"})
        self.assertEqual(["606586117", "605549117", "607222817"], [j["id"] for j in jobs])
        first, recreation = jobs[0], jobs[1]
        self.assertEqual("SUPERVISOR CONTRACT SERVICES", first["title"])
        self.assertEqual("https://jobs.toronto.ca/jobsatcity/job/Toronto-SUPERVISOR-CONTRACT-SERVICES-ON-M3J-2E1/606586117/",
                         first["url"])
        self.assertEqual(("Toronto, ON", "Administrative", "Position Type: Full-time."),
                         (first["location"], first["department"], first["listing_note"]))
        self.assertEqual(watcher._date_epoch("2026-10-28"), first["posted"])
        self.assertTrue(recreation["url"].startswith("https://jobs.toronto.ca/recreation/job/"))
        self.assertEqual(3, jobs.total)
        self.assertTrue(jobs.complete)
        self.assertNotIn("startrow", get.call_args_list[0].kwargs["params"])
        self.assertEqual(2, get.call_args_list[1].kwargs["params"]["startrow"])

    @patch("watcher.requests.get")
    def test_tile_layout_survives_nodes_that_disagree(self, get, sleep):
        # One node reports 4 postings, a stale one 3 and repeats a posting: the first pass is short,
        # the second adds the missing one, and only then is the listing complete.
        get.side_effect = [toronto_page(4, A, B), toronto_page(3, B, C), toronto_page(3),
                           toronto_page(4, A, B), toronto_page(4, C, D)]
        jobs = watcher.fetch_successfactors_portal({"url": "https://jobs.toronto.ca/search/"})
        self.assertEqual(["606586117", "605549117", "607222817", "607235517"], [j["id"] for j in jobs])
        self.assertEqual(4, jobs.total)
        self.assertTrue(jobs.complete)
        get.side_effect = [toronto_page(4, A, B), toronto_page(3, B, C), toronto_page(3)] * 3
        short = watcher.fetch_successfactors_portal({"url": "https://jobs.toronto.ca/search/", "passes": 2})
        self.assertEqual(3, len(short))
        self.assertFalse(short.complete)
        self.assertIn("3 of reported total 4", short.reason)

    @patch("watcher.requests.get")
    def test_table_with_en_gb_dates_and_facility_as_department(self, get, sleep):
        get.return_value = response(text='''<span class="paginationLabel">Results <b>1 – 100</b> of <b>1</b></span>
            <table id="searchresults"><tr class="data-row"><td class="colTitle" headers="hdrTitle">
            <span class="jobTitle hidden-phone"><a href="/job/Koriyama-HS-Professional%2C-Koriyama-Factory-Fuku/1431730133/"
            class="jobTitle-link">HS Professional, Koriyama Factory</a></span></td>
            <td class="colLocation hidden-phone"><span class="jobLocation">\nKoriyama, Fukushima, JP\n</span></td>
            <td class="colFacility hidden-phone"><span class="jobFacility">Human Resource Management</span></td>
            <td class="colDate hidden-phone" nowrap="nowrap"><span class="jobDate">28 Oct 2026\n</span></td></tr></table>''')
        jobs = watcher.fetch_successfactors_portal({"url": "https://careers.novonordisk.com/search", "facility": "department"})
        self.assertEqual(("1431730133", "Koriyama, Fukushima, JP", "Human Resource Management"),
                         (jobs[0]["id"], jobs[0]["location"], jobs[0]["department"]))
        self.assertEqual(watcher._date_epoch("2026-10-28"), jobs[0]["posted"])
        self.assertEqual("https://careers.novonordisk.com/job/Koriyama-HS-Professional%2C-Koriyama-Factory-Fuku/1431730133/",
                         jobs[0]["url"])
        self.assertTrue(jobs.complete)
        # without the cfg key the Facility column (a plant number on Olympus) is not taken for a department
        self.assertNotIn("department", watcher.fetch_successfactors_portal({"url": "https://careers.novonordisk.com/search/"})[0])


if __name__ == "__main__":
    unittest.main()
