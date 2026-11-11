"""A posting in both a targeted specialty and a targeted whole board earns the stronger of the two weights. A
resume's QA & Test (x1.0) beats a Software board kept at x0.78 from an earlier resume, so QA work isn't scored like
any other software role, and a board picked at full weight is never cut to a specialty's lower one. A posting in
another of the board's specialties is marked down once, for not being a specialty picked, and the board's weight is
not taken off as well. Invented postings."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile

KN = load_knowledge()
NOW = time.time()
QA = ("Senior QA Test Lead", "We build clinical scheduling software used in 300 hospitals. You will lead five testers, "
      "own the test strategy, write test plans and test cases, run regression testing before each release and triage "
      "defects in Jira. Requirements: 8+ years of software QA experience and SQL.")
BACKEND = ("Senior Backend Software Engineer", "Design and build backend services and REST APIs in Java and Python "
           "for our scheduling platform. Requirements: 6+ years building distributed backend systems.")
PROFILE = {"fields": ["software", "hardware"], "target_stages": ["experienced", "senior"], "target_cycles": [],
           "graduation_year": None, "target_locations": ["toronto"], "target_company_types": [], "skills": ["sql"]}


def role(posting, targets, weights):
    title, description = posting
    profile = merge_profile({**PROFILE, "target_roles": targets, "role_weights": weights})
    job = {"board": "example", "id": title, "title": title, "company": "Example Health Software",
           "location": "Toronto, ON", "description": description, "posted": NOW - 86400}
    result = analyze(job, profile, KN, now=NOW)
    return result["classification"]["subcategory"], next(s for s in result["subscores"] if s["key"] == "role")


class RoleWeightTests(unittest.TestCase):
    def test_a_resume_specialty_outweighs_a_lower_weighted_board(self):
        targets, weights = ["software.qa_test", "software", "hardware"], {"software.qa_test": 1.0, "software": 0.78}
        sub, qa = role(QA, targets, weights)
        self.assertEqual("qa_test", sub)
        self.assertEqual(35, qa["points"], qa)
        self.assertNotIn("weighted", qa["detail"])
        sub, backend = role(BACKEND, targets, weights)
        self.assertEqual("backend", sub)
        # In the board, not a specialty picked: 12 of 35, and the board's x0.78 is not taken off again.
        self.assertEqual(12, backend["points"], backend)
        self.assertIn("in your Software board, not one of your specialties", backend["detail"])
        self.assertNotIn("weighted", backend["detail"])

    def test_a_board_alone_keeps_its_own_weight(self):
        # With no specialty picked beside it, the board is the target: 35 x 0.78 = 27.
        sub, backend = role(BACKEND, ["software", "hardware"], {"software": 0.78})
        self.assertEqual("backend", sub)
        self.assertEqual(27, backend["points"], backend)
        self.assertIn("weighted ×0.78", backend["detail"])

    def test_a_full_weight_board_is_not_cut_to_a_weaker_specialty(self):
        _, qa = role(QA, ["software", "software.qa_test"], {"software.qa_test": 0.6})
        self.assertEqual(35, qa["points"], qa)

    def test_a_specialty_alone_keeps_its_own_weight(self):
        _, qa = role(QA, ["software.qa_test"], {"software.qa_test": 0.6})
        self.assertEqual(21, qa["points"], qa)       # 35 x 0.6


if __name__ == "__main__":
    unittest.main()
