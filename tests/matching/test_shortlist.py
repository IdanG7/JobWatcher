"""The short list: an eligible posting is on it only when its role is a specialty the person picked or the resume
shows (not merely somewhere in a board) and its location is known to be somewhere they can work. Everything else
stays eligible and searchable. What time decides (still listed, how old) is the list query's, tested in
tests/store. Invented postings."""
import time
import unittest

from intel import build_facts, load_knowledge, merge_profile
from intel.matching import ELIGIBLE, EXCLUDED, SHORTLIST, match_resume
from intel.scoring import score_job

KN = load_knowledge()
NOW = time.time()
QA = ("Senior QA Test Lead", "You will lead five testers, own the test strategy, write test plans and test cases, "
      "run regression testing before each release and triage defects in Jira. Requirements: 8+ years of software QA "
      "experience and SQL.")
BACKEND = ("Senior Backend Software Engineer", "Design and build backend services and REST APIs in Java and Python "
           "for our scheduling platform. Requirements: 6+ years building distributed backend systems.")
GENERIC = ("Senior Software Engineer", "")
GENERIC_QA_SKILLS = ("Senior Software Engineer", "You will work in an Agile team, track work in Jira, write SQL "
                     "against our reporting database and own software testing for your features.")
SENIOR = {"fields": ["software"], "target_stages": ["experienced", "senior"], "target_cycles": [],
          "graduation_year": None, "target_locations": ["toronto"], "target_countries": ["CA", "US"],
          "target_company_types": [], "skills": ["sql", "software_testing", "agile", "jira"]}


def verdict(posting, targets, location="Toronto, ON", **profile):
    title, description = posting
    profile = merge_profile({**SENIOR, "target_roles": targets, "role_weights": {}, **profile})
    job = {"board": "example", "id": title, "title": title, "company": "Example Health Software",
           "location": location, "description": description, "posted": NOW - 86400}
    facts = build_facts(job, KN, None, "")
    scored = score_job(facts, profile, KN, {"posted": NOW - 86400}, NOW)
    return match_resume(facts, profile, scored, KN)


class SpecialtyTests(unittest.TestCase):
    def test_a_targeted_specialty_is_on_the_list(self):
        match = verdict(QA, ["software.qa_test", "software"])
        self.assertTrue(match["shortlist"], match)
        self.assertEqual(SHORTLIST, match["tier"])
        self.assertEqual([], match["off_list"])

    def test_another_specialty_in_the_board_is_eligible_but_off_the_list(self):
        match = verdict(BACKEND, ["software.qa_test", "software"])
        self.assertTrue(match["matched"], match)
        self.assertFalse(match["shortlist"], match)
        self.assertEqual(ELIGIBLE, match["tier"])
        self.assertIn("not one of your specialties", match["off_list"][0])

    def test_a_posting_that_names_no_specialty_waits_for_evidence(self):
        match = verdict(GENERIC, ["software.qa_test", "software"])
        self.assertEqual(ELIGIBLE, match["tier"], match)
        self.assertIn("hasn't been read yet", match["off_list"][0])

    def test_skills_from_the_resume_put_a_posting_with_no_specialty_on_the_list(self):
        match = verdict(GENERIC_QA_SKILLS, ["software.qa_test", "software"])
        self.assertGreaterEqual(len(match["matched_skills"]), 3, match)
        self.assertEqual(SHORTLIST, match["tier"], match)

    def test_a_board_picked_with_no_specialty_is_the_persons_own_breadth(self):
        for posting in (QA, BACKEND, GENERIC):
            with self.subTest(title=posting[0]):
                self.assertEqual(SHORTLIST, verdict(posting, ["software"])["tier"])

    def test_a_related_specialty_is_on_the_list(self):
        full_stack = ("Senior Full-Stack Developer", "Build React front ends and Node.js services for our platform.")
        match = verdict(full_stack, ["software.backend"])
        self.assertEqual(SHORTLIST, match["tier"], match)

    def test_a_finance_area_is_specific_without_a_group(self):
        profile = {"fields": ["finance"], "target_stages": ["internship", "new_grad"], "graduation_year": 2027,
                   "target_cycles": ["summer_2027"], "skills": []}
        title = ("2027 Investment Banking Summer Analyst", "")
        self.assertEqual(SHORTLIST, verdict(title, ["investment_banking"], **profile)["tier"])
        # A finance role outside the targets stays eligible, as before, and off the list.
        other = verdict(("2027 Internal Audit Summer Intern", ""), ["investment_banking"], **profile)
        self.assertEqual(ELIGIBLE, other["tier"], other)
        self.assertIn("not one of your target roles", other["off_list"][0])

    def test_no_targets_means_nothing_to_narrow_by(self):
        self.assertEqual(SHORTLIST, verdict(BACKEND, [])["tier"])


class LocationTests(unittest.TestCase):
    def test_a_posting_that_names_no_place_is_off_the_list(self):
        match = verdict(QA, ["software.qa_test"], location="")
        self.assertTrue(match["matched"], match)
        self.assertEqual(ELIGIBLE, match["tier"])
        self.assertEqual(["The posting doesn't say where the role is"], match["off_list"])

    def test_remote_with_no_country_is_on_the_list_for_someone_open_to_remote(self):
        self.assertEqual(SHORTLIST, verdict(QA, ["software.qa_test"], location="Remote")["tier"])
        self.assertEqual(ELIGIBLE, verdict(QA, ["software.qa_test"], location="Remote", open_to_remote=False)["tier"])

    def test_a_place_outside_the_target_countries_is_excluded_as_before(self):
        match = verdict(QA, ["software.qa_test"], location="Berlin, Germany")
        self.assertEqual(EXCLUDED, match["tier"], match)
        self.assertEqual([], match["off_list"])        # ruled out: the short list has nothing to add

    def test_no_target_countries_means_any_place(self):
        self.assertEqual(SHORTLIST, verdict(QA, ["software.qa_test"], location="", target_countries=[],
                                            target_locations=[])["tier"])


if __name__ == "__main__":
    unittest.main()
