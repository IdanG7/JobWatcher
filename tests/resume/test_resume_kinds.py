"""Resumes outside the usual student layout: a college diploma and no degree, no section headings at all, French
headings, a career changer, and degree-first education lines. The app takes each one and reads it sensibly.
People, schools and employers are invented."""
import unittest

from intel import load_knowledge
from intel.resume import parse_resume
from tests.app import test_dashboard as fixtures

KN = load_knowledge()

IT_TECH = """DEREK BOUCHARD
derek.b@example.com | 555-010-0234 | Hamilton, ON
Summary
IT support technician with 12 years supporting Windows networks for small businesses.
Employment History
Lakeview IT Services Hamilton, ON
Senior IT Support Technician 2017 – Present
• Support 40 client offices: Windows Server, Active Directory, Microsoft 365 and Cisco networking.
• Lead a team of 3 technicians and manage the help desk ticket queue in ServiceNow.
Bramble Computers Hamilton, ON
Computer Technician 2013 – 2017
• Repaired and imaged laptops and desktops and set up small office networks.
Education
Diploma, Computer Systems Technician – Mohawk Valley College 2013
Certifications
CompTIA A+, Network+; Microsoft 365 Certified: Modern Desktop Administrator
"""

NO_HEADINGS = """SOFIA ROSSI
sofia.rossi@example.com | 555-010-0289 | Montreal, QC
Senior Product Manager, Lakeview Software, 2019 – Present
• Own the roadmap for a B2B analytics product with 40,000 users and lead 3 squads.
Product Manager, Fabrikam Apps, 2015 – 2019
• Launched a mobile onboarding flow that lifted activation by 18% across 2 apps.
Master of Business Administration, Riverside University Business School, 2015
"""

FRENCH = """ÉMILIE TREMBLAY
emilie.tremblay@example.com | 555-010-0290 | Montréal, QC
Expérience professionnelle
Banque Laurentienne Fictive Montréal, QC
Analyste financière principale 2017 – Présent
• Préparer les prévisions financières et les analyses de rentabilité pour la haute direction.
Formation
Baccalauréat en administration des affaires (B.A.A.), Finance – Université Riverside 2014
"""

CAREER_CHANGER = """LINDA PARK
linda.park@example.com | 555-010-0223 | Ottawa, ON
Summary
Former high school math teacher moving into data analysis; SQL, Python and Tableau.
Projects
School Attendance Dashboard | SQL, Tableau 2026
• Built a Tableau dashboard from 5 years of attendance data in PostgreSQL to flag at-risk students.
Experience
Ottawa Valley District School Board Ottawa, ON
Mathematics Teacher Sep 2012 – Jun 2025
• Taught grades 9–12 math and statistics to classes of 30 and analyzed test results in Excel.
Education
Data Analytics Certificate - Northgate College, expected Jan 2027
Bachelor of Education - Riverside University 2012
Bachelor of Science, Mathematics - Riverside University 2011
Skills
SQL, Python (pandas), Tableau, Excel, statistics
"""


def titles(parsed):
    return [e["title"] for e in parsed["entries"]]


class ResumeKindTests(unittest.TestCase):
    def test_a_diploma_and_no_degree(self):
        parsed = parse_resume(IT_TECH, KN)
        self.assertEqual("Mohawk Valley College", parsed["education"]["school"])
        self.assertEqual(["Senior IT Support Technician", "Computer Technician"], titles(parsed))
        self.assertEqual(["experienced", "senior"], parsed["career"]["stages"])

    def test_no_section_headings(self):
        parsed = parse_resume(NO_HEADINGS, KN)
        self.assertEqual(["Senior Product Manager, Lakeview Software", "Product Manager, Fabrikam Apps"],
                         titles(parsed))
        self.assertEqual(("masters", "Riverside University Business School", 2015),
                         tuple(parsed["education"][k] for k in ("level", "school", "graduation_year")))
        self.assertIn("senior", parsed["career"]["stages"])

    def test_french_headings(self):
        parsed = parse_resume(FRENCH, KN)
        self.assertEqual(["Analyste financière principale"], titles(parsed))
        self.assertEqual(("undergraduate", "Université Riverside", 2014),
                         tuple(parsed["education"][k] for k in ("level", "school", "graduation_year")))
        self.assertIn("experienced", parsed["career"]["stages"])

    def test_a_career_changer_is_not_senior_in_the_new_field(self):
        # Thirteen years of teaching are no years in a board's work: the old degree makes entry and experienced.
        parsed = parse_resume(CAREER_CHANGER, KN)
        self.assertEqual(["entry", "experienced"], parsed["career"]["stages"])
        # A certificate's "expected Jan 2027" is no graduation, and the school is the part of the line naming it.
        self.assertEqual(("Riverside University", 2012),
                         (parsed["education"]["school"], parsed["education"]["graduation_year"]))

    def test_degree_first_lines_and_dates_after_the_program(self):
        cases = (("Education\nMBA, Riverside University Business School 2010\n",
                  {"school": "Riverside University Business School", "level": "mba"}),
                 ("Education\nBachelor of Science in Nursing - Lakeshore University 2012\n",
                  {"school": "Lakeshore University", "program": "Nursing"}),
                 ("Education\nNorthgate University Waterloo, ON\nBachelor of Mathematics, Statistics Sep 2021 – Apr 2026\n",
                  {"school": "Northgate University", "program": "Statistics", "graduation_year": 2026}))
        for text, expected in cases:
            with self.subTest(text=text.splitlines()[1]):
                edu = parse_resume("PAT LEE\npat.lee@example.com\n" + text, KN)["education"]
                self.assertEqual(expected, {k: edu[k] for k in expected})


class ResumeKindUploadTests(fixtures.ServiceFixture):
    def test_the_app_takes_every_kind(self):
        for name, text in (("diploma", IT_TECH), ("no headings", NO_HEADINGS), ("French", FRENCH),
                           ("career changer", CAREER_CHANGER)):
            with self.subTest(resume=name):
                preview = self.service.parse_resume({"text": text})
                self.assertTrue(preview["profile"]["target_stages"])
                self.assertIsNone(preview["profile"]["graduation_year"])


if __name__ == "__main__":
    unittest.main()
