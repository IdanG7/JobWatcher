"""A profile in the workforce (only entry, experienced or senior targets) is scored and matched without the campus
parts: no recruiting cycle to miss, no graduation date to check. Student profiles keep both. Postings are invented."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile
from intel.matching import match_resume

KN = load_knowledge()
NOW = time.time()
DESCRIPTION = ("We build clinical scheduling software used in 300 hospitals. You will lead a team of five testers, "
               "own the test strategy, write test plans and test cases, run regression testing before each release, "
               "triage defects in Jira and grow our Selenium test automation. Requirements: 8+ years of software QA "
               "experience, 3+ years leading testers, SQL, and experience with IEC 62304.")
EXPERIENCED = {"fields": ["software"], "target_roles": ["software.qa_test"], "target_stages": ["experienced", "senior"],
               "target_cycles": [], "graduation_year": None, "graduation_month": None, "target_company_types": [],
               "target_locations": ["toronto"], "skills": ["sql", "jira", "selenium"]}


def run(title, layer):
    profile = merge_profile(layer)
    job = {"board": "example", "id": title, "title": title, "company": "Example Health Software",
           "location": "Toronto, ON", "description": DESCRIPTION, "posted": NOW - 86400}
    result = analyze(job, profile, KN, now=NOW)
    return result, match_resume(result, profile, result, KN), {s["key"]: s for s in result["subscores"]}


class WorkforceProfileTests(unittest.TestCase):
    def test_senior_qa_postings_match_an_experienced_qa_profile(self):
        for title, stage in (("Senior QA Test Lead", "senior"), ("QA Manager", "senior"), ("Test Manager", "senior"),
                             ("Director, IT Quality Assurance", "senior"), ("Quality Assurance Analyst II", "experienced")):
            with self.subTest(title=title):
                result, match, _ = run(title, EXPERIENCED)
                self.assertEqual(("software", "qa_test"), (result["classification"]["family"],
                                                           result["classification"]["subcategory"]))
                self.assertEqual(stage, result["seniority"]["stage"])
                self.assertTrue(match["matched"], match["exclusions"])
                self.assertEqual([], result["penalties"])

    def test_a_workforce_profile_has_no_cycle_to_miss_or_graduation_to_check(self):
        result, match, subscores = run("Senior QA Test Lead", EXPERIENCED)
        self.assertEqual(10, subscores["cycle"]["points"], subscores["cycle"])
        self.assertIn("year-round", subscores["cycle"]["detail"])
        self.assertNotIn("Graduation requirement is not stated", match["review"])

    def test_student_and_mixed_profiles_keep_the_campus_checks(self):
        for name, layer in (("default student", {}),
                            ("student on Software", {**EXPERIENCED, "target_stages": ["internship", "new_grad"]}),
                            ("career changer", {**EXPERIENCED, "target_stages": ["new_grad", "experienced"]})):
            with self.subTest(profile=name):
                _, match, subscores = run("QA Analyst", layer)
                self.assertNotIn("year-round", subscores["cycle"]["detail"])
                self.assertLessEqual(subscores["cycle"]["points"], 5)
                self.assertIn("Graduation requirement is not stated", match["review"])


if __name__ == "__main__":
    unittest.main()
