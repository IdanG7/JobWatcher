"""Regression coverage for resume facts and automatic opportunity matching."""
import copy
import unittest
import time

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.resume import parse_resume, profile_from_resume
from intel.matching import match_resume

KN = load_knowledge()
RESUME = """TEST CANDIDATE
Education
Example University Toronto, ON
Bachelor of Commerce - Finance & Economics Specialist Expected: Apr 2028
cGPA: 3.92/4.00
Experience
Example Properties Toronto, ON
Student Real Estate Finance & Capital Markets Treasury Analyst Jan 2026 - August 2026
Managed liquidity and cash positioning with Excel.
Student Financial Analyst May 2025 - Jan 2026
Built Discounted Cash Flow (DCF) models for C$10M projects and valued C$1BN in assets.
Leadership & Activities
Research & Operations Team Lead Jan 2024 - Jan 2025
Technical Skills & Interests
Languages: English (native), Russian (native), Hebrew (intermediate)
Technical: Bloomberg, Capital IQ, Power BI, SQL
"""


class ParserRegressionTests(unittest.TestCase):
    def test_resume_facts_and_skill_provenance(self):
        parsed = parse_resume(RESUME, KN)
        self.assertEqual((2028, 4, 3.92), tuple(parsed["education"][k] for k in ("graduation_year", "graduation_month", "gpa")))
        self.assertNotIn("cpp", {s["key"] for s in parsed["skills"]})
        self.assertTrue(any(r["subcategory"] == "treasury" for r in parsed["roles"]))
        self.assertTrue(all("2026" not in r["title"] for r in parsed["roles"]))
        self.assertEqual(["English", "Russian", "Hebrew"], parsed["languages"])

    def test_apply_replaces_skills_updates_cycles_and_keeps_targets_and_auth(self):
        before = merge_profile({"target_roles": ["investment_banking"], "skills": ["python", "statistics"]})
        untouched = copy.deepcopy(before)
        profile = profile_from_resume(parse_resume(RESUME, KN), before, KN)
        self.assertEqual(untouched, before)
        self.assertNotIn("python", profile["skills"])
        self.assertNotIn("statistics", profile["skills"])
        self.assertIn("corporate_finance.treasury", profile["target_roles"])
        # The resume decides targets (graded), replacing earlier ones; whole
        # categories are never targeted, so siblings like Accounting don't
        # inherit full role credit.
        self.assertNotIn("investment_banking", profile["target_roles"])
        self.assertTrue(all("." in r for r in profile["target_roles"]))
        self.assertEqual(1.0, max(profile["role_weights"].values()))
        self.assertIn("summer_2027", profile["target_cycles"])
        self.assertIn("new_grad_2028", profile["target_cycles"])
        self.assertEqual(before["work_authorization"], profile["work_authorization"])
        self.assertEqual(before["target_locations"], profile["target_locations"])

    def test_currency_is_not_cpp_but_real_cpp_still_matches(self):
        from intel.skills import extract_skills
        self.assertNotIn("cpp", {s["key"] for s in extract_skills("C$10M, C$1BN, C, C-suite", KN)})
        self.assertIn("cpp", {s["key"] for s in extract_skills("Modern C++ and cpp development", KN)})

    def test_engineering_at_bank_and_explicit_internship_month(self):
        facts = build_facts({"title": "Summer Analyst, Engineering", "company": "Goldman Sachs"}, KN)
        self.assertFalse(facts["classification"]["is_finance"])
        self.assertEqual("software", facts["classification"]["family"])
        affairs = build_facts({"title": "Functions - Enterprise Services and Public Affairs, Summer Analyst, New York - USA, 2027", "company": "Citi"}, KN)
        self.assertFalse(affairs["classification"]["is_finance"])
        facts = build_facts({"title": "Intern, Financial Analyst - January 2027 (4 Month)", "posted": time.time()}, KN)
        self.assertEqual("winter_2027", facts["cycle"]["cycle"])
        self.assertFalse(facts["cycle"]["inferred"])

    def test_authorization_is_country_specific_and_remains_a_preference(self):
        parsed = parse_resume(RESUME + "\nU.S. permanent resident", KN)
        self.assertEqual({"US": "permanent_resident"}, parsed["work_authorization"])
        before = merge_profile({"work_authorization": {"CA": "unknown", "US": "unknown"}})
        self.assertEqual(before["work_authorization"], profile_from_resume(parsed, before, KN)["work_authorization"])


class ResumeMatchTests(unittest.TestCase):
    def setUp(self):
        self.profile = profile_from_resume(parse_resume(RESUME, KN), merge_profile(), KN)

    def match(self, title, description="", location="Toronto, ON"):
        facts = build_facts({"title": title, "description": description, "location": location,
                             "company": "RBC", "posted": time.time()}, KN)
        return match_resume(facts, self.profile, score_job(facts, self.profile, KN))

    def test_compatible_roles_match_and_explicit_graduation_conflict_does_not(self):
        self.assertTrue(self.match("2027 Investment Banking Summer Analyst", "Graduating between December 2027 and June 2028.")["matched"])
        result = self.match("2027 Investment Banking Graduate Analyst", "Graduating between January 2027 and December 2027.")
        self.assertFalse(result["matched"])
        self.assertTrue(any("graduat" in s.lower() for s in result["exclusions"]))
        self.assertTrue(self.match("2028 Investment Banking Graduate Analyst", "Graduating between January 2028 and December 2028.")["matched"])

    def test_unrelated_senior_and_outside_target_geography_are_excluded(self):
        for title, location in (("Summer Analyst, Engineering", "Toronto, ON"),
                                ("Functions - Enterprise Services and Public Affairs, Summer Analyst, 2027", "New York, NY"),
                                ("Senior Treasury Manager", "Toronto, ON"),
                                ("2027 Investment Banking Summer Analyst", "Singapore")):
            with self.subTest(title=title):
                self.assertFalse(self.match(title, location=location)["matched"])

    def test_unknown_requirements_are_kept_with_review_notes(self):
        result = self.match("2027 Investment Banking Summer Analyst")
        self.assertTrue(result["matched"])
        self.assertTrue(result["review"])

    def test_known_degree_and_gpa_conflicts_are_excluded(self):
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "Open to PhD candidates only.")["matched"])
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "Minimum GPA: 4.0.")["matched"])

    def test_work_authorization_unknown_does_not_invent_a_conflict(self):
        self.profile["work_authorization"] = {"CA": "unknown"}
        result = self.match("2027 Investment Banking Summer Analyst", "Canadian citizenship required.")
        self.assertTrue(result["matched"])
        self.assertTrue(any("authoriz" in s.lower() or "citizen" in s.lower() for s in result["review"]))

    def test_optional_languages_and_alternative_degrees_do_not_exclude(self):
        for description in ("French is an asset.", "Fluency in French preferred.", "Preferred: fluency in French.",
                            "Bachelor, Master or PhD candidates welcome."):
            with self.subTest(description=description):
                self.assertTrue(self.match("2027 Investment Banking Summer Analyst", description)["matched"])
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "Fluency in French is required.")["matched"])
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "French is an asset. Fluency in French is required.")["matched"])

    def test_preferred_gpa_is_not_a_minimum(self):
        self.profile["education"]["gpa"] = 3.5
        self.assertTrue(self.match("2027 Investment Banking Summer Analyst", "GPA of 3.8 preferred.")["matched"])
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "Minimum GPA: 3.8.")["matched"])

    def test_explicit_wrong_recruiting_year_is_excluded(self):
        self.assertFalse(self.match("2025 Investment Banking Summer Analyst")["matched"])

    def test_generic_citizenship_restriction_is_checked_for_known_location(self):
        self.profile["work_authorization"]["US"] = "needs_sponsorship"
        self.assertFalse(self.match("2027 Investment Banking Summer Analyst", "Permanent residents or citizens only.", "New York, NY")["matched"])


if __name__ == "__main__":
    unittest.main()
