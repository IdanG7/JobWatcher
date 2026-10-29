"""Test requisitions ("DO NOT APPLY - TEST REQ"): no opening, so they leave every board like a passed deadline."""
import time
import unittest

from intel import load_knowledge, merge_profile, score_job
from intel.facts import build_facts

KN = load_knowledge()
NOW = time.time()


def facts(title, company="Example"):
    return build_facts({"title": title, "company": company, "posted": NOW - 3600}, KN)


class TestPostingTests(unittest.TestCase):
    def test_only_titles_the_employer_marks_as_a_test(self):
        for title in ("DO NOT APPLY - TEST REQ - CRG - Assistant CRA - Lima Peru",     # Thermo Fisher, 37 of them
                      "DO NOT APPLY- TEST 4", "Test Position - do not apply",          # Autodesk
                      "Test job", "TEST REQUISITION"):                                # OpenText
            self.assertTrue(facts(title).get("test_posting"), title)
        for title in ("Test Engineer", "Software Development Engineer in Test", "Engineer III, Software Test",
                      "Production Scheduler (Test)", "Test Job Coordinator", "Test Requisition Analyst",
                      "Investment Banking Analyst", "Registered Nurse - Casual, Nights"):
            self.assertNotIn("test_posting", facts(title), title)

    def test_a_test_posting_is_closed_on_every_board(self):
        profile = merge_profile({"fields": ["finance", "software", "healthcare"]})
        for title in ("DO NOT APPLY - TEST REQ - Scientist I, Protein Biology - Bangalore India", "Test job"):
            scored = score_job(facts(title), profile, KN, now=NOW)
            self.assertEqual("closed", scored["window_status"], title)
            self.assertEqual(0, scored["urgency"], title)
            self.assertIn(("test_posting", -40), [(p["key"], p["points"]) for p in scored["penalties"]])
        real = score_job(facts("Test Engineer"), profile, KN, now=NOW)
        self.assertNotEqual("closed", real["window_status"])
        self.assertNotIn("test_posting", [p["key"] for p in real["penalties"]])


if __name__ == "__main__":
    unittest.main()
