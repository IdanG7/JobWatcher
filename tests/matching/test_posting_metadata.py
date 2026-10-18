"""Posting dates and pay need explicit recruiting / compensation evidence."""
from datetime import datetime, timezone
import unittest

from intel.compensation import comp_from_description, parse_compensation
from intel.cycle import extract_deadline


class PostingDeadlineTests(unittest.TestCase):
    REF = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def test_explicit_source_deadlines_and_posting_close_labels(self):
        for text, expected in (
            ("Application Deadline:\n2026-11-01", "2026-11-01"),
            ("Application Deadline: 2026-11-01T23:59:59Z", "2026-11-01"),
            ("Posting End Date:\n2026/11/02", "2026-11-02"),
            ("Job Posting Closing Date: 03-Nov-2026", "2026-11-03"),
            ("Applications will be accepted until 14/11/2026.", "2026-11-14"),
            ("Submit your application no later than November 15, 2026.", "2026-11-15"),
        ):
            with self.subTest(text=text):
                deadline = extract_deadline(text, self.REF)
                self.assertEqual(expected, deadline.get("date"))
                self.assertEqual("high", deadline.get("confidence"))
                self.assertIn(expected[:4], deadline["text"])

    def test_unrelated_term_and_project_dates_do_not_close_a_posting(self):
        for text in (
            "The internship runs until August 31, 2027.",
            "You must remain enrolled until May 1, 2027.",
            "Benefits are available until December 31, 2026.",
            "Employment End Date: November 1, 2026",
            "Project deadline: November 1, 2026",
            "Application deadline: not yet announced. Start date: November 1, 2026.",
            "Application deadline: not yet announced. Graduation: November 1, 2026.",
        ):
            with self.subTest(text=text):
                self.assertEqual({}, extract_deadline(text, self.REF))


class PostingCompensationTests(unittest.TestCase):
    def test_bank_annual_and_hourly_pay_and_source_metadata(self):
        for text, period, low, high in (
            ("Base salary:\nCAD 58,000 - 76,000 YEAR", "year", 58000, 76000),
            ("The hourly pay range is $24.50–$32.75 per hour.", "hour", 50960, 68120),
            ("Base salary: CAD 25.50 - 32.00 HOUR", "hour", 53040, 66560),
            ("Base salary: CAD 1,000 - 1,500 WEEK", "week", 52000, 78000),
            ("The annual base salary range for this role is CAD $90–105k.", "year", 90000, 105000),
            ("Salary range: $90,000 CAD - $105,000 CAD per year.", "year", 90000, 105000),
        ):
            with self.subTest(text=text):
                comp = comp_from_description(text, "CA")
                self.assertEqual((period, low, high),
                                 (comp.get("period"), comp.get("annual_min"), comp.get("annual_max")))
                self.assertEqual("CAD", comp["currency"])
                self.assertEqual("description", comp["source"])
                self.assertTrue(comp["original"])

    def test_shorthand_scales_both_range_endpoints(self):
        comp = parse_compensation("CAD $90–105k per year", "CA")
        self.assertEqual((90000, 105000), (comp.get("annual_min"), comp.get("annual_max")))

    def test_benefits_and_business_amounts_are_not_candidate_pay(self):
        for text in (
            "We pay attention to our $150 billion assets under management.",
            "Our compensation team supports $120 million in annual revenue.",
            "Compensation and benefits include $5,000 annual tuition reimbursement.",
            "We offer a $1,000 monthly wellness benefit.",
            "Pay benefits include a $5,000 signing bonus.",
            "The salary team manages a $100,000 operating budget.",
        ):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "CA"))

    def test_base_pay_survives_separate_benefit_amounts(self):
        comp = comp_from_description(
            "We offer a $5,000 tuition allowance. Base salary: CAD $65,000–$75,000 per year. "
            "Benefits include $1,000 for wellness.", "CA")
        self.assertEqual((65000, 75000), (comp.get("annual_min"), comp.get("annual_max")))


if __name__ == "__main__":
    unittest.main()
