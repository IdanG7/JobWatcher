"""Experienced and senior resumes: education listed last under "Certifications & Education", a degree from
decades ago, an in-progress certification with an "expected" date and roles from the 1990s. They propose
experienced and senior roles, not internships, and a student's resume is still read as a student's."""
import unittest
from datetime import date

from intel import load_knowledge, merge_profile
from intel.profile import validate_profile
from intel.resume import parse_resume, profile_from_resume

KN = load_knowledge()

# Invented person, schools and employers, laid out as pypdf reads a one-page PDF resume (the
# space before an en dash is lost: "Social Sciences– Riverside University").
SENIOR = """Dana Kowalski
Senior QA Test Lead | Test Manager | Medical Device Software
Mississauga, ON | 555-010-0163 | dana.kowalski@example.com | linkedin.com/in/dana-kowalski
Professional Summary
Senior QA Test Lead with 25+ years in software and hardware quality assurance, including 10+ years in regulated
medical imaging. Leads QA teams from test strategy through UAT and go/no-go release decisions.
Professional Experience
Lakeview Imaging Toronto, ON
Senior QA Test Lead Aug 2023 – Present
• Lead QA strategy across 3 concurrent initiatives, directing 8 QA analysts and driving defect triage to closure.
• Own test strategies and plans for functional, integration, regression and UAT testing across 12 releases.
Harbour Sonics Toronto, ON
Senior Quality Assurance Analyst 2014 – 2023
• Tested high-frequency ultrasound hardware and software, writing test plans and cases for regression testing.
• Validated data with SQL and used Postman to test REST APIs with the developers.
Bramble Commerce Ltd. Mississauga, ON
QA Tester (Contract) 2004 – 2013
• Automated test cases with QTP/VBScript and tested e-commerce web apps, including the payment gateway.
Northline Systems Ottawa, ON
Software Tester 1997 – 2003
• Ran manual functional and regression tests on billing software and logged defects in the tracker.
Skills
Testing: Functional, SIT, E2E, Regression, API, UAT
Tools: Jira (admin), Confluence, SQL, Postman, Quality Center, QTP
Certifications & Education
ISTQB Advanced Level Test Manager (CTAL-TM) – in progress expected Jun 2027
ISTQB Certified Tester, Foundation Level (CTFL) 2016
B.Sc., Social Sciences– Riverside University, Poland 1996
"""


def student(grad_year: int, exam_year: int) -> str:
    """A student with a long part-time job and a CFA exam listed before the degree."""
    return f"""SAM ORTEGA
sam.ortega@example.com | 555-010-0128 | Toronto, ON
Education & Certifications
CFA Level I Candidate – expected Feb {exam_year}
Lakeshore University Toronto, ON
Bachelor of Commerce, Finance Expected: Apr {grad_year}
Experience
Maple Grocers Toronto, ON
Cashier {grad_year - 7} – Present
• Handled cash and returns for 200 customers a shift and trained four new cashiers on the till.
Skills
Excel, financial modeling, valuation
"""


class SeniorResumeTests(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_resume(SENIOR, KN)

    def test_education_comes_from_the_combined_heading(self):
        edu = self.parsed["education"]
        self.assertEqual(("undergraduate", "Riverside University, Poland", "Social Sciences"),
                         (edu["level"], edu["school"], edu["program"]))
        # The degree year, not the certification's "expected Jun 2027" or a job's end year.
        self.assertEqual(1996, edu["graduation_year"])

    def test_roles_from_the_1990s_are_read(self):
        self.assertIn(("Software Tester", 2003), [(e["title"], e["end"]) for e in self.parsed["entries"]])

    def test_career_stage_comes_from_years_of_experience(self):
        career = self.parsed["career"]
        self.assertEqual(["experienced", "senior"], career["stages"])
        self.assertEqual([], career["cycles"])
        self.assertGreaterEqual(career["work_years"], 20)
        self.assertIn("years of experience", career["note"])

    def test_profile_targets_experienced_and_senior_roles(self):
        profile = profile_from_resume(self.parsed, merge_profile({}), KN)
        self.assertEqual(["experienced", "senior"], profile["target_stages"])
        # No student graduation date or recruiting cycles are left behind.
        self.assertEqual((None, None, []), (profile["graduation_year"], profile["graduation_month"],
                                            profile["target_cycles"]))
        self.assertEqual([], validate_profile(profile, KN))

    def test_qa_skills_without_false_finance_hits(self):
        skills = {s["key"] for s in self.parsed["skills"]}
        self.assertLessEqual({"software_testing", "sql", "jira", "confluence", "api_testing", "test_management", "uft"},
                             skills)
        # "high-frequency ultrasound" is not low-latency trading, and regression testing is not statistics.
        self.assertFalse({"low_latency", "statistics"} & skills)


class StudentResumeTests(unittest.TestCase):
    def test_a_student_is_still_read_as_a_student(self):
        year = date.today().year
        parsed = parse_resume(student(year + 2, year + 1), KN)
        edu = parsed["education"]
        # The degree's date, not the CFA exam's; "e-commerce"-style words don't set the program.
        self.assertEqual((year + 2, 4, "Finance"), (edu["graduation_year"], edu["graduation_month"], edu["program"]))
        # Seven years at a part-time job while studying don't make a student an experienced hire.
        self.assertNotIn("experienced", parsed["career"]["stages"])
        self.assertIn("internship", parsed["career"]["stages"])

    def test_statistics_still_reads_regression_analysis(self):
        parsed = parse_resume(student(date.today().year + 2, date.today().year + 1)
                              + "Built linear regression models and ran regression analysis in Excel.\n", KN)
        self.assertIn("statistics", {s["key"] for s in parsed["skills"]})


if __name__ == "__main__":
    unittest.main()
