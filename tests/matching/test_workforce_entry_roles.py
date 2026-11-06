"""A profile in the workforce still sees postings whose title names no level: a "Registered Nurse" or a "QA Analyst"
reads as entry level, and an experienced nurse or tester applies to them. They rank below the target stages;
campus programs stay out. Postings are invented."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile
from intel.matching import match_resume

KN = load_knowledge()
NOW = time.time()
QA = ("Test our clinical scheduling software: write test plans and test cases, run regression testing before each "
      "release and triage defects in Jira.")
NURSING = "Provide patient care on a 36-bed medicine unit; current CNO registration required."
SENIOR_QA = {"fields": ["software"], "target_roles": ["software.qa_test"], "target_stages": ["experienced", "senior"],
             "target_cycles": [], "graduation_year": None, "graduation_month": None, "target_company_types": [],
             "target_locations": ["toronto"]}
EXPERIENCED_RN = {**SENIOR_QA, "fields": ["healthcare"], "target_roles": ["healthcare.clinical_care"], "licences": ["rn"]}


def run(title, description, layer):
    profile = merge_profile(layer)
    job = {"board": "example", "id": title, "title": title, "company": "Example Health", "location": "Toronto, ON",
           "description": description, "posted": NOW - 86400}
    result = analyze(job, profile, KN, now=NOW)
    return result, match_resume(result, profile, result, KN), {s["key"]: s for s in result["subscores"]}


class WorkforceEntryRoleTests(unittest.TestCase):
    def test_an_unlevelled_title_is_not_ruled_out(self):
        for title, description, layer in (("QA Analyst", QA, SENIOR_QA), ("Registered Nurse", NURSING, EXPERIENCED_RN)):
            with self.subTest(title=title):
                result, match, _ = run(title, description, layer)
                self.assertEqual("entry", result["seniority"]["stage"])
                self.assertTrue(match["matched"], match["exclusions"])

    def test_it_ranks_below_the_target_stages(self):
        _, _, entry = run("QA Analyst", QA, SENIOR_QA)
        _, _, senior = run("Senior QA Analyst", QA, SENIOR_QA)
        self.assertLess(entry["stage"]["points"], senior["stage"]["points"])
        # A licensed role with no level named is open to experienced staff: close to a target stage.
        _, _, nurse = run("Registered Nurse", NURSING, EXPERIENCED_RN)
        self.assertEqual(16, nurse["stage"]["points"], nurse["stage"])

    def test_campus_programs_stay_out(self):
        _, match, _ = run("QA Analyst Intern", QA, SENIOR_QA)
        self.assertFalse(match["matched"])
        self.assertIn("Career stage internship is outside your targets", match["exclusions"])

    def test_a_student_profile_still_rules_out_senior_roles(self):
        _, match, _ = run("Senior QA Analyst", QA, {**SENIOR_QA, "target_stages": ["internship", "new_grad"]})
        self.assertFalse(match["matched"])


if __name__ == "__main__":
    unittest.main()
