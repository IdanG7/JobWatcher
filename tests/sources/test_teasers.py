"""Listing teasers: Oracle's listing carries only ShortDescriptionStr (cut at 1,000 characters), so the
poll stores it as a teaser and its description fetch still reads the posting's own record.
Responses are trimmed from JPMorgan Chase's live Oracle feed (jpmc.fa.oraclecloud.com, CX_1001),
recorded 2026-11-07; the listing's TotalJobsCount (7,115) is cut to the two postings kept."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import watcher
from intel_store import IntelStore, store_description, store_teaser
from tests.app.test_dashboard import ServiceFixture

JPMC = {"ats": "oracle_hcm", "host": "jpmc.fa.oraclecloud.com", "site": "CX_1001", "company_key": "jpmorgan"}
TEASER = "Out of the successful launch of Chase in 2021, we�re a new team, with a new mission"
LISTING = {"items": [{"SearchId": 1, "Offset": 0, "Limit": 25, "SortBy": "POSTING_DATES_DESC", "TotalJobsCount": 2,
                      "SiteNumber": "CX_1001", "requisitionList": [
    {"Id": "210587260", "Title": "Lead Software Engineer - Backend Engineering - Java", "PostedDate": "2026-11-07",
     "PrimaryLocationCountry": "GB", "JobFamily": "Software Engineering", "JobFunction": "Technology",
     "ShortDescriptionStr": TEASER, "PrimaryLocation": "LONDON, LONDON, United Kingdom",
     "ExternalQualificationsStr": None, "ExternalResponsibilitiesStr": None, "secondaryLocations": []},
    {"Id": "210588623", "Title": "Software Engineer III - Backend Engineering - Java", "PostedDate": "2026-11-07",
     "PrimaryLocationCountry": "GB", "JobFamily": "Software Engineering", "JobFunction": "Technology",
     "ShortDescriptionStr": TEASER + ".", "PrimaryLocation": "LONDON, LONDON, United Kingdom",
     "ExternalQualificationsStr": None, "ExternalResponsibilitiesStr": None, "secondaryLocations": []}]}]}
DETAIL = {"items": [{
    "Id": "210587260", "Title": "Lead Software Engineer - Backend Engineering - Java", "Category": "Software Engineering",
    "RequisitionType": "Professional", "ExternalPostedStartDate": "2026-11-07T08:35:41+00:00",
    "ExternalDescriptionStr": (
        '<p style="margin-left: 0in;">Out of the successful launch of Chase in 2021, we�re a new team, with a new '
        "mission. We�re creating products that solve real world problems and put customers at the center -&nbsp; "
        "all in an environment that nurtures skills and helps you realize your potential.&nbsp;</p>\n"
        "<p><strong>Job responsibilities:</strong></p>\n<ul>\n"
        " <li>Use domain modeling techniques to allow us to build best in class business products.</li>\n"
        " <li>Structure software so that it is easy to understand, test and evolve.</li>\n"
        " <li>Make sure our releases happen with zero downtime for our end-users.</li>\n</ul>"),
    "ExternalResponsibilitiesStr": "", "ExternalQualificationsStr": "",
    "CorporateDescriptionStr": "J.P. Morgan is a global leader in financial services.",
    "ShortDescriptionStr": TEASER, "PrimaryLocation": "LONDON, LONDON, United Kingdom",
    "JobFunction": "Technology", "BusinessUnit": "Corporate Sector"}]}
# The same record with its description fields left empty (as Goldman Sachs' campus postings come).
EMPTY_DETAIL = {"items": [{"Id": "210588623", "Category": "Software Engineering", "ExternalDescriptionStr": None,
                           "ExternalResponsibilitiesStr": "", "ExternalQualificationsStr": "",
                           "ShortDescriptionStr": TEASER + "."}]}


def response(payload):
    r = Mock(status_code=200)
    r.raise_for_status.return_value = None
    r.json.return_value = payload
    return r


def oracle_get(url, params=None, **kw):
    """The feed: the listing, and each posting's record by its id."""
    if url.endswith("/recruitingCEJobRequisitions"):
        return response(LISTING)
    assert url.endswith("/recruitingCEJobRequisitionDetails"), url
    return response(DETAIL if 'Id="210587260"' in params["finder"] else EMPTY_DETAIL)


def text_row(con, job_id):
    return con.execute("SELECT description, source, attempts, fetched_at IS NULL, last_error FROM job_text "
                       "WHERE board='jpmorgan' AND job_id=?", (job_id,)).fetchone()


class OracleTeaserTests(unittest.TestCase):
    def test_the_listing_marks_its_text_a_teaser(self):
        with patch.object(watcher.requests, "get", side_effect=oracle_get):
            jobs = watcher.fetch_oracle_hcm(JPMC)
        self.assertEqual(["210587260", "210588623"], [j["id"] for j in jobs])
        self.assertEqual([TEASER, TEASER + "."], [j["description"] for j in jobs])
        self.assertTrue(all(j["teaser"] for j in jobs))
        self.assertTrue(jobs.complete)

    def test_the_poll_reads_the_posting_behind_a_teaser_once_and_keeps_it(self):
        config = {"boards": {"jpmorgan": JPMC}, "filters": {}, "profile": {}}
        enrich = watcher.enrich_descriptions                # the poll's own call is patched out below
        with tempfile.TemporaryDirectory() as tmp:
            subs = Path(tmp) / "subs.json"
            subs.write_text("{}")
            with patch.object(watcher, "SUBSCRIBERS", subs), patch.object(watcher, "EPHEMERAL", False), \
                    patch.object(watcher.requests, "get", side_effect=oracle_get) as get, \
                    patch("watcher.enrich_descriptions", return_value=0):
                con = watcher.db_open(":memory:")
                watcher.cycle(config, con)
                # stored as a teaser: no attempt used, no back-off
                self.assertEqual((TEASER, "teaser", 0, 1, ""), text_row(con, "210587260"))
                get.reset_mock()
                self.assertEqual(1, enrich(config, con))
                self.assertEqual(2, get.call_count)          # both records were read
                full, source, attempts, unfetched, error = text_row(con, "210587260")
                self.assertTrue(full.startswith(TEASER + ". We�re creating products"))
                self.assertIn("• Make sure our releases happen with zero downtime", full)
                self.assertEqual(("detail", 1, 0, ""), (source, attempts, unfetched, error))
                self.assertEqual("Software Engineering", con.execute(
                    "SELECT department FROM job_text WHERE job_id='210587260'").fetchone()[0])
                # the empty record keeps the teaser and counts as a failed attempt
                self.assertEqual((TEASER + ".", "teaser", 1, 0), text_row(con, "210588623")[:4])
                self.assertIn("no description", text_row(con, "210588623")[4])
                # the next poll keeps the posting's own text, and the full text arriving is not an edit
                watcher.cycle(config, con)
                self.assertEqual((full, "detail"), text_row(con, "210587260")[:2])
                self.assertEqual([], con.execute("SELECT * FROM job_changes WHERE kind='description_changed'")
                                 .fetchall())
                get.reset_mock()
                self.assertEqual(0, enrich(config, con))     # read once; the failed one backs off for six hours
                get.assert_not_called()

    def test_a_record_that_is_its_teaser_is_read_once(self):
        con = watcher.db_open(":memory:")
        board(con, "jpmorgan", ["1"])
        config = {"boards": {"jpmorgan": {"ats": "fake"}}, "profile": {}}
        IntelStore(con, config).refresh()
        store_teaser(con, "jpmorgan", "1", "A short posting.")
        detail = Mock(return_value=("A short posting.", ""))
        with patch.dict(watcher.DETAIL_FETCHERS, {"fake": detail}):
            self.assertEqual(1, watcher.enrich_descriptions(config, con))
            self.assertEqual(0, watcher.enrich_descriptions(config, con))
        self.assertEqual(1, detail.call_count)
        self.assertEqual(("A short posting.", "detail"), text_row(con, "1")[:2])


def board(con, name, ids, title="Investment Banking Analyst", posted=None):
    now = watcher.now()
    for i, job_id in enumerate(ids):
        con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)", (name, job_id, title, "New York, NY", f"https://x/{job_id}",
                                                                 now, now))
        con.execute("INSERT INTO job_details VALUES (?,?,?,?,?)",
                    (name, job_id, "Acme Advisors", "", (posted or 1_790_000_000) + i))


class TeaserStorageTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        board(self.con, "jpmorgan", ["1", "2"])
        IntelStore(self.con, {"boards": {"jpmorgan": JPMC}, "profile": {}}).refresh()

    def row(self, job_id):
        return self.con.execute("SELECT description, department, source, attempts, fetched_at, content_hash != '' "
                                "FROM job_text WHERE job_id=?", (job_id,)).fetchone()

    def test_text_an_older_poll_kept_as_the_listing_starts_over_as_a_teaser(self):
        store_description(self.con, "jpmorgan", "1", TEASER, source="listing")
        store_description(self.con, "jpmorgan", "1", TEASER + ".", source="listing")   # each change was an "attempt"
        self.con.execute("UPDATE job_intel SET input_hash='kept'")
        self.assertFalse(store_teaser(self.con, "jpmorgan", "1", TEASER + "."))
        self.assertEqual((TEASER + ".", "", "teaser", 0, None, 1), self.row("1"))
        self.assertEqual("kept", self.con.execute("SELECT input_hash FROM job_intel WHERE job_id='1'").fetchone()[0])
        self.assertEqual(1, len(self.con.execute("SELECT * FROM job_changes").fetchall()))   # only the old edit

    def test_a_teaser_never_replaces_the_posting_s_own_text(self):
        store_description(self.con, "jpmorgan", "1", "The posting's own text.", source="detail")
        self.assertFalse(store_teaser(self.con, "jpmorgan", "1", TEASER))
        self.assertTrue(store_teaser(self.con, "jpmorgan", "1", TEASER, "Markets"))     # an empty department fills
        self.assertEqual(("The posting's own text.", "Markets", "detail"), self.row("1")[:3])

    def test_a_teaser_fills_a_posting_whose_fetches_found_nothing_and_keeps_their_count(self):
        for _ in range(3):
            watcher.record_description_error(self.con, "jpmorgan", "2", ValueError("no description"))
        self.assertTrue(store_teaser(self.con, "jpmorgan", "2", TEASER))
        description, _, source, attempts, fetched_at, _ = self.row("2")
        self.assertEqual((TEASER, "teaser", 3), (description, source, attempts))
        self.assertIsNotNone(fetched_at)
        self.assertIsNone(self.con.execute("SELECT input_hash FROM job_intel WHERE job_id='2'").fetchone()[0])

    def test_an_edited_teaser_is_an_edit(self):
        store_teaser(self.con, "jpmorgan", "1", TEASER)
        self.assertTrue(store_teaser(self.con, "jpmorgan", "1", TEASER + " in London."))
        self.assertEqual(["description_changed"], [r[0] for r in self.con.execute("SELECT kind FROM job_changes")])
        self.assertEqual((TEASER + " in London.", "teaser", 0, None), self.row("1")[:1] + self.row("1")[2:5])


class TeaserBudgetTests(unittest.TestCase):
    def test_teasers_share_the_budget_and_per_source_cap_with_postings_with_no_text(self):
        con = watcher.db_open(":memory:")
        board(con, "a", ["t1", "t2", "t3", "t4", "empty"], posted=1_790_000_000)
        board(con, "b", ["t1", "t2", "t3"], posted=1_780_000_000)
        config = {"boards": {"a": {"ats": "fake"}, "b": {"ats": "fake"}}, "profile": {}, "description_per_board": 2}
        IntelStore(con, config).refresh()
        for name, ids in (("a", ["t1", "t2", "t3", "t4"]), ("b", ["t1", "t2", "t3"])):
            for job_id in ids:
                store_teaser(con, name, job_id, TEASER)
        con.execute("UPDATE job_details SET posted=1700000000 WHERE board='a' AND job_id='empty'")   # the oldest
        detail = Mock(side_effect=lambda cfg, job_id: (f"Posting {job_id}. Financial modeling in Excel.", ""))
        count = lambda keys: {s: sum(b == s for b, _ in keys) for s in "ab"}  # noqa: E731
        with patch.dict(watcher.DETAIL_FETCHERS, {"fake": detail}):
            fetched = []
            self.assertEqual(3, watcher.enrich_descriptions(config, con, budget=3, fetched=fetched))
            self.assertEqual(3, detail.call_count)                               # the budget
            self.assertEqual(({"a": 2, "b": 1}, {("a", "t4"), ("a", "t3"), ("b", "t3")}),
                             (count(fetched), set(fetched)))                     # the cap, newest first
            fetched.clear()
            self.assertEqual(4, watcher.enrich_descriptions(config, con, budget=10, fetched=fetched))
            self.assertEqual({"a": 2, "b": 2}, count(fetched))
            fetched.clear()
            self.assertEqual(1, watcher.enrich_descriptions(config, con, budget=10, fetched=fetched))
            self.assertEqual([("a", "empty")], fetched)     # a teaser counts as no text: the oldest comes last
            self.assertEqual(0, watcher.enrich_descriptions(config, con, budget=10))
        self.assertEqual(0, con.execute("SELECT COUNT(*) FROM job_text WHERE source='teaser'").fetchone()[0])

    def test_a_source_with_thousands_due_leaves_the_rest_of_the_budget_to_the_others(self):
        """JPMorgan's teasers are finance roles at a finance firm, ranked above everything else: capping
        each source only after taking the budget's best candidates left most of the budget unused."""
        con = watcher.db_open(":memory:")
        board(con, "jpm", [str(i) for i in range(10)])
        board(con, "hospital", ["1"], title="Office Coordinator")
        config = {"boards": {"jpm": {"ats": "fake"}, "hospital": {"ats": "fake"}}, "profile": {},
                  "description_per_board": 1}
        IntelStore(con, config).refresh()
        for i in range(10):
            store_teaser(con, "jpm", str(i), TEASER)
        fetched = []
        with patch.dict(watcher.DETAIL_FETCHERS, {"fake": Mock(return_value=("The posting's own text.", ""))}):
            self.assertEqual(2, watcher.enrich_descriptions(config, con, budget=2, fetched=fetched))
        self.assertEqual(["hospital", "jpm"], sorted(b for b, _ in fetched))

    def test_failed_teaser_fetches_back_off_and_stop_after_three_attempts(self):
        con = watcher.db_open(":memory:")
        board(con, "a", ["1"])
        config = {"boards": {"a": {"ats": "fake"}}, "profile": {}}
        IntelStore(con, config).refresh()
        store_teaser(con, "a", "1", TEASER)
        detail = Mock(side_effect=watcher.requests.HTTPError("503"))
        with patch.dict(watcher.DETAIL_FETCHERS, {"fake": detail}):
            for _ in range(4):
                watcher.enrich_descriptions(config, con)
                con.execute("UPDATE job_text SET fetched_at='2000-01-01T00:00:00+00:00'")   # past the back-off
        self.assertEqual(3, detail.call_count)
        self.assertEqual((TEASER, "teaser", 3), con.execute("SELECT description, source, attempts FROM job_text")
                         .fetchone())


class OpenTeaserTests(ServiceFixture):
    def test_opening_a_posting_that_holds_its_teaser_fetches_the_posting(self):
        self.service.fetch_on_open = True
        with self.service.db() as con:
            store_teaser(con, "demo_quant", "two", "Join our research team.")
        with patch.object(watcher, "fetch_description",
                          return_value=("Join our research team. Build pricing models in Python.", "Research")):
            job = self.service.job_detail("demo_quant:two")
            self.assertEqual(("Join our research team.", "teaser", True),
                             (job["description"], job["description_source"], job["description_pending"]))
            for thread in threading.enumerate():
                if thread.name == "jobwatch-describe":
                    thread.join(5)
        job = self.service.job_detail("demo_quant:two")
        self.assertEqual(("detail", False), (job["description_source"], job["description_pending"]))
        self.assertIn("pricing models", job["description"])


if __name__ == "__main__":
    unittest.main()
