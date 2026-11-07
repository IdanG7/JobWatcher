"""The Experience a resume shows lists every job title, not only those whose title alone names a role word and a
board: 'Senior QA Test Lead' and 'QA Tester' have no word of the old list, and 'QA Specialist' reads as Operations
until the resume's own experience shows software work. Invented person and employers."""
import unittest

from intel import load_knowledge
from intel.resume import parse_resume

KN = load_knowledge()

SENIOR_QA = """Morgan Ellery
Senior QA Test Lead | Regulated Software
Oakville, ON | 555-010-0199 | morgan.ellery@example.com
Professional Experience
Brightwater Diagnostics Toronto, ON
Senior QA Test Lead Aug 2022 – Present
• Lead QA for 3 software products, directing 6 testers and owning the test strategy for every release.
• Plan functional, integration, regression and UAT testing, and triage defects in Jira with the developers.
Cedar Optics Toronto, ON
Senior Quality Assurance and Support Analyst 2016 – 2022
• Wrote test plans and test cases for the imaging software and ran regression testing before each release.
• Validated results with SQL queries and tested REST APIs with Postman.
QA Specialist 2012 – 2016
• Executed manual and automated test scripts and logged software defects in Quality Center.
Pinegrove Software Mississauga, ON
QA Tester (Contract) 2010 – 2012
• Automated test cases with QTP and tested e-commerce web applications in an agile team.
Harbourline Mobile Ltd. Hamilton, ON
E-Commerce QA Tester (Intern) 2008 – 2009
• Wrote Selenium test scripts and tested mobile checkout flows.
Skills
Testing: Functional, Regression, API, UAT
Tools: Jira, Confluence, SQL, Postman, Quality Center, QTP
Education
B.A., Psychology – Lakeshore University 2004
"""


class ExperienceRolesTests(unittest.TestCase):
    def test_every_qa_job_title_is_listed(self):
        parsed = parse_resume(SENIOR_QA, KN)
        self.assertEqual(["Senior QA Test Lead", "Senior Quality Assurance and Support Analyst", "QA Specialist",
                          "QA Tester (Contract)", "E-Commerce QA Tester (Intern)"],
                         [r["title"] for r in parsed["roles"]])
        for role in parsed["roles"]:
            self.assertEqual(("software", "qa_test"), (role["category"], role["subcategory"]), role["title"])

    def test_a_wrapped_bullet_that_says_lead_stays_one_bullet(self):
        text = SENIOR_QA.replace("• Lead QA for 3 software products, directing 6 testers and owning the test strategy",
                                 "• Built the release checklist with the developers and agreed to\nlead the test "
                                 "strategy")
        parsed = parse_resume(text, KN)
        self.assertTrue(any("agreed to lead the test strategy" in b for b in parsed["bullets"]), parsed["bullets"][:3])
        self.assertNotIn("lead the test strategy for every release.", [r["title"] for r in parsed["roles"]])


if __name__ == "__main__":
    unittest.main()
