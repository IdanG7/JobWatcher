"""Degree requirements need candidate context and inclusive alternatives."""
import unittest

from intel import analyze, merge_profile
from intel.eligibility import extract_eligibility


class DegreeContextTests(unittest.TestCase):
    def degree_penalties(self, description):
        result = analyze({"title": "2027 Investment Banking Summer Analyst", "description": description},
                         merge_profile({"education": {"level": "undergraduate"}}))
        return [p for p in result["penalties"] if p["key"] == "degree"]

    def test_inclusive_degree_lists_allow_undergraduates(self):
        for description in ("Open to bachelor, master and PhD students.",
                            "Bachelor's, Master's, and PhD candidates welcome.",
                            "Students pursuing a bachelor's/master's/PhD degree are eligible.",
                            "PhD, master's or bachelor's students welcome."):
            with self.subTest(description=description):
                self.assertEqual([], self.degree_penalties(description))
                self.assertTrue(extract_eligibility(description)["degree_alternatives"])

    def test_unrelated_doctoral_mentions_are_not_requirements(self):
        for description in ("PhD faculty lead our annual speaker series.",
                            "Our speakers include doctoral researchers.",
                            "You will work with PhD scientists on the investment team.",
                            "You will have exposure to PhD scientists on the investment team."):
            with self.subTest(description=description):
                self.assertNotIn("phd", extract_eligibility(description)["degree_required"])
                self.assertEqual([], self.degree_penalties(description))

    def test_exclusive_graduate_programs_still_require_graduate_degrees(self):
        for description in ("Open to PhD candidates only.", "Open to Ph.D. candidates only.",
                            "A PhD degree is required.",
                            "We require a PhD in finance.", "Applicants must hold a PhD.",
                            "Candidates must be pursuing a doctoral degree.",
                            "Excel preferred. This program is for PhD candidates only.",
                            "Master's students only.", "MBA students only."):
            with self.subTest(description=description):
                self.assertTrue(self.degree_penalties(description))

    def test_separate_degree_clauses_do_not_invent_alternatives(self):
        result = extract_eligibility("Bachelor's education is useful. This program is for PhD candidates only.")
        self.assertFalse(result["degree_alternatives"])
        self.assertTrue(self.degree_penalties("Bachelor's education is useful. This program is for PhD candidates only."))


if __name__ == "__main__":
    unittest.main()
