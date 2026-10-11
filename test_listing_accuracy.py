"""Drawer values must come from the listing itself (Capital One FA intern regression)."""
from datetime import datetime, timezone
import unittest
from unittest.mock import MagicMock, patch

import watcher
from intel import build_facts, load_knowledge
from intel.eligibility import extract_eligibility

KN = load_knowledge()

# Condensed from the real Capital One "Intern, Financial Analyst - January 2027 (4 Month)" posting.
CAPITAL_ONE = """Intern, Financial Analyst - January 2027 (4 Month)
Finance: Our Finance team partners with the business on budgets, forecasts and variance analysis.
Accounting: Our Accounting team owns financial reporting, reconciliations and month-end close.
We support a hybrid model – with 3 days in the office per week – that gives room for both collaboration and personal commitments.
Basic Qualifications
• Currently enrolled in an undergraduate degree or higher from an accredited university
Preferred Qualifications
• Previous internship/co-op experience
The expected annual salary range for this position is $45,000 - $75,000.
MUST INCLUDE YOUR RESUME AND UNOFFICIAL TRANSCRIPT IN ONE PDF DOCUMENT IN THE ATTACHMENT SECTION WHEN YOU CREATE YOUR PROFILE TO APPLY.
"""


class CapitalOneListingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.facts = build_facts({"title": "Intern, Financial Analyst - January 2027 (4 Month)",
                                 "company": "Capital One", "location": "Toronto, ON",
                                 "description": CAPITAL_ONE}, KN)

    def test_finance_and_accounting_tracks_classify_as_fpa_with_accounting_secondary(self):
        cls = self.facts["classification"]
        self.assertEqual("corporate_finance", cls["category"])
        self.assertEqual("fpa", cls["subcategory"])
        self.assertIn("accounting", cls["secondary_subcategories"])

    def test_hybrid_work_model_comes_from_the_description(self):
        loc = self.facts["location"]
        self.assertTrue(loc["hybrid"])
        self.assertEqual(3, loc["work_model"]["office_days"])
        self.assertIn("3 days in the office", loc["work_model"]["text"])

    def test_eligibility_quotes_whole_clauses(self):
        elig = self.facts["eligibility"]
        self.assertEqual("Undergraduate or higher", elig["degree"])
        self.assertEqual("Currently enrolled in an undergraduate degree or higher from an accredited university",
                         elig["degree_text"])
        self.assertEqual("Currently enrolled student", elig["enrollment"])
        self.assertEqual(["Transcript"], elig["materials"])
        self.assertIn("UNOFFICIAL TRANSCRIPT", elig["materials_text"])
        self.assertIn("(preferred)", elig["experience"])


class WorkModelTests(unittest.TestCase):
    def location(self, description):
        return build_facts({"title": "Analyst", "location": "New York, NY", "description": description}, KN)["location"]

    def test_product_names_are_not_work_policies(self):
        self.assertFalse(self.location("You will support our hybrid cloud platform.")["hybrid"])

    def test_five_office_days_is_onsite(self):
        loc = self.location("You will be in the office 5 days a week.")
        self.assertFalse(loc["hybrid"])
        self.assertEqual("onsite", loc["work_model"]["model"])


class EligibilityMaterialsTests(unittest.TestCase):
    def test_mentioning_a_transcript_without_asking_for_one_is_not_a_requirement(self):
        self.assertEqual([], extract_eligibility("We review academic transcripts later in the process for some roles")["materials"])

    def test_no_enrollment_statement_stays_unknown(self):
        self.assertIsNone(extract_eligibility("Join our finance team.")["enrollment"])


class WorkdayPostedDateTests(unittest.TestCase):
    NOW = datetime(2026, 10, 10, 15, 30, tzinfo=timezone.utc).timestamp()

    def test_open_ended_bucket_is_unknown_not_invented(self):
        self.assertIsNone(watcher._workday_posted_epoch("Posted 30+ Days Ago", self.NOW))

    def test_relative_days_resolve_to_noon_utc_and_never_the_future(self):
        expected = datetime(2026, 10, 5, 12, tzinfo=timezone.utc).timestamp()
        self.assertEqual(expected, watcher._workday_posted_epoch("Posted 5 Days Ago", self.NOW))
        self.assertEqual(datetime(2026, 10, 10, 12, tzinfo=timezone.utc).timestamp(),
                         watcher._workday_posted_epoch("Posted Today", self.NOW))
        morning = datetime(2026, 10, 10, 9, 45, tzinfo=timezone.utc).timestamp()
        self.assertEqual(datetime(2026, 10, 10, 9, tzinfo=timezone.utc).timestamp(),
                         watcher._workday_posted_epoch("Posted Today", morning))

    def test_detail_record_supplies_exact_start_date(self):
        response = MagicMock()
        response.json.return_value = {"jobPostingInfo": {"jobDescription": "<p>Hi</p>", "jobFamilyGroup": "Finance",
                                                         "startDate": "2026-08-05"}}
        with patch.object(watcher.requests, "get", return_value=response):
            text, dept, meta = watcher.detail_workday({"host": "x.wd1.myworkdayjobs.com", "tenant": "t", "site": "s"}, "/job/1")
        self.assertEqual("Finance", dept)
        self.assertEqual(datetime(2026, 8, 5, 12, tzinfo=timezone.utc).timestamp(), meta["posted"])

    def test_repair_clears_only_estimated_workday_dates(self):
        with patch.object(watcher, "DB_PATH", ":memory:"):
            con = watcher.db_open()
        rows = [("wd", "estimated", 1757500000.123), ("wd", "exact", 1757462400.0), ("gh", "other", 1757500000.5)]
        for board, job_id, posted in rows:
            con.execute("INSERT INTO job_details(board, job_id, posted) VALUES (?,?,?)", (board, job_id, posted))
        config = {"boards": {"wd": {"ats": "workday"}, "gh": {"ats": "greenhouse"}}}
        with patch.object(watcher, "log"):
            self.assertEqual(1, watcher.repair_workday_posted(con, config))
            self.assertEqual(0, watcher.repair_workday_posted(con, config))  # idempotent
        posted = dict(con.execute("SELECT job_id, posted FROM job_details").fetchall())
        self.assertIsNone(posted["estimated"])
        self.assertEqual(1757462400.0, posted["exact"])
        self.assertEqual(1757500000.5, posted["other"])


if __name__ == "__main__":
    unittest.main()
