"""Product and Design resumes open their own track (plans/product-design-board.md 9.4, D24): a design or HCI degree or a
P&D job title opens it, its signals read the work, and a UX resume no longer adds the Software board. People, schools
and employers are invented."""
import unittest

from intel import load_knowledge, merge_profile
from intel import resume_insights as insights
from intel.resume import parse_resume, profile_from_resume

KN = load_knowledge()
PD_TYPES = ["big_tech", "consumer_tech", "enterprise_saas", "high_growth_startup"]

UX = """LEAH NGUYEN
leah.nguyen@example.com | 555-010-0301 | Toronto, ON
Education
Lakeshore University Toronto, ON
Bachelor of Design, Interaction Design Sep 2022 – Apr 2026
Experience
Northwind Apps Toronto, ON
UX Designer Intern May 2025 – Aug 2025
• Ran usability testing with 12 participants and turned the findings into wireframes in Figma.
• Built a design system of 40 components and documented user interfaces with HTML and CSS specs.
Fabrikam Studio Toronto, ON
Visual Designer Co-op Jan 2025 – Apr 2025
• Designed brand identity refreshes and typography guidelines in Illustrator and Photoshop.
Skills
Figma, Sketch, Adobe Creative Cloud, user research, accessibility (WCAG)
"""

PM = """SAM OKAFOR
sam.okafor@example.com | 555-010-0302 | Waterloo, ON
Education
Northgate University Waterloo, ON
Bachelor of Arts, Cognitive Science Sep 2022 – Apr 2026
Experience
Contoso Cloud Toronto, ON
Product Manager Intern May 2025 – Aug 2025
• Wrote PRDs and user stories for an onboarding flow and ran an A/B test that lifted activation 9%.
• Built retention and funnel dashboards in Amplitude and Mixpanel with SQL.
Lakeview Software Waterloo, ON
Associate Product Manager Intern Sep 2024 – Dec 2024
• Owned the roadmap for the mobile app's settings and prioritized the backlog with engineering in Jira.
"""

CS_PM = """RIYA SHAH
riya.shah@example.com | 555-010-0303 | Toronto, ON
Education
Lakeshore University Toronto, ON
Bachelor of Computer Science Sep 2022 – Apr 2026
Experience
Contoso Cloud Toronto, ON
Product Manager Intern May 2025 – Aug 2025
• Wrote PRDs and user stories for the billing page and prioritized the backlog.
Northwind Apps Toronto, ON
Software Engineer Intern Jan 2025 – Apr 2025
• Built REST APIs in Python and Django and a React front end with TypeScript.
"""

HCI = """ALEX KIM
alex.kim@example.com | 555-010-0305 | Pittsburgh, PA
Education
Riverside University Pittsburgh, PA
Master of Human-Computer Interaction Sep 2024 – Dec 2025
Bachelor of Arts, Psychology Sep 2020 – Apr 2024
Experience
Riverside HCI Lab Pittsburgh, PA
Research Assistant Jan 2025 – Dec 2025
• Ran user interviews and diary studies with 30 participants and coded them in Dovetail.
"""

ROLE = """JO PARK
jo.park@example.com | 555-010-0306 | Toronto, ON
Education
Lakeshore University Toronto, ON
Bachelor of Design, Communication Design Sep 2021 – Apr 2025
Experience
Northwind Apps Toronto, ON
{title} May 2025 – Present
• Wrote onboarding and error messages for the mobile app with the product design
lead.
• Ran weekly critiques and wrote the guidelines the team reviews every quarter.
"""


def read(text):
    parsed = parse_resume(text, KN)
    return parsed, insights.resume_tracks(parsed["entries"], parsed["education"], KN)


class TrackGateTests(unittest.TestCase):
    def test_a_ux_resume_opens_only_its_own_track_and_no_longer_adds_software(self):
        # On tech, "user interfaces", HTML and CSS read as software.frontend and applying added Software (6.1).
        parsed, tracks = read(UX)
        self.assertEqual(frozenset({"product_design"}), tracks)
        keys = [i["key"] for i in parsed["role_interests"]]
        self.assertEqual(["design.product_design", "design.visual_brand"], keys)
        self.assertLessEqual({"figma", "wireframing", "design_systems", "usability_testing", "user_research",
                              "adobe_cc", "accessibility"}, {s["key"] for s in parsed["skills"]})
        profile = profile_from_resume(parsed, merge_profile({}), KN)
        self.assertEqual(["design"], profile["fields"])
        self.assertEqual(PD_TYPES, profile["target_company_types"])

    def test_a_pm_resume_reads_its_work_with_product_signals(self):
        parsed, tracks = read(PM)
        self.assertEqual(frozenset({"product_design"}), tracks)
        keys = [i["key"] for i in parsed["role_interests"]]
        self.assertEqual("product.apm_programs", keys[0])               # PM internships and the APM title
        self.assertLessEqual({"product.product_management", "product.product_analytics"}, set(keys))
        self.assertFalse([k for k in keys if k.split(".")[0] in {"software", "data_ml"}], keys)
        self.assertLessEqual({"prds", "ab_testing", "product_analytics_tools", "sql"}, {s["key"] for s in parsed["skills"]})
        profile = profile_from_resume(parsed, merge_profile({}), KN)
        self.assertEqual(["product"], profile["fields"])
        self.assertEqual(PD_TYPES, profile["target_company_types"])

    def test_a_cs_degree_with_a_pm_internship_keeps_both_boards(self):
        parsed, tracks = read(CS_PM)
        self.assertEqual(frozenset({"tech", "product_design"}), tracks)
        keys = [i["key"] for i in parsed["role_interests"]]
        self.assertIn("software", keys)
        self.assertTrue(any(k.startswith("product.") for k in keys), keys)
        profile = profile_from_resume(parsed, merge_profile({}), KN)
        self.assertEqual({"product", "software"}, set(profile["fields"]))

    def test_a_design_or_hci_degree_opens_the_track_and_a_minor_does_not(self):
        parsed, tracks = read(HCI)
        self.assertEqual(frozenset({"product_design"}), tracks)       # no titled role: the degree opens it
        self.assertEqual("design.ux_research", parsed["role_interests"][0]["key"])
        degree = KN.tracks["product_design"].degree
        for line in ("Bachelor of Design, Industrial Design", "Bachelor of Fine Arts in Graphic Design",
                     "BDes, Communication Design", "MS in Human Computer Interaction", "Master of HCI"):
            self.assertTrue(degree.search(line), line)
        for line in ("Bachelor of Commerce, Minor in Interaction Design", "BA Economics, Minor: Graphic Design",
                     "Bachelor of Design", "Bachelor of Science, Computer Science", "Industrial Engineering"):
            self.assertFalse(degree.search(line), line)
        # A tech degree opens tech only.
        self.assertNotIn("product_design", read(CS_PM.replace("Product Manager Intern", "Data Analyst Intern"))[1])

    def test_a_pd_resume_also_reads_tech_skills_as_pd_postings_do(self):
        # P&D postings read tech's skills (tech.skills_from names both boards); so a resume that opens only the P&D
        # track reads them too: Jira and Agile on the PM resume, HTML & CSS on the UX resume. No other track does.
        self.assertEqual({"tech": frozenset(), "healthcare": frozenset(), "product_design": frozenset({"tech"})},
                         {key: track.skills_also for key, track in KN.tracks.items()})
        self.assertLessEqual({"product", "design"}, KN.tracks["tech"].skills_from)
        for text, expected in ((PM, {"jira", "agile"}), (UX, {"html_css"})):
            parsed, tracks = read(text)
            self.assertEqual(frozenset({"product_design"}), tracks)
            self.assertLessEqual(expected, {s["key"] for s in parsed["skills"]})


class RoleWordTests(unittest.TestCase):
    def test_pd_titles_without_a_common_role_word_are_roles_on_the_track(self):
        for title, sub in (("UX Writer", "content_design"), ("Creative Director", "visual_brand"),
                           ("Art Director", "visual_brand"), ("Design Technologist", "design_engineering"),
                           ("Illustrator", "visual_brand"), ("Product Owner", "product_management")):
            with self.subTest(title=title):
                parsed, tracks = read(ROLE.format(title=title))
                self.assertIn("product_design", tracks)
                self.assertEqual([(title, sub)], [(r["title"], r["subcategory"]) for r in parsed["roles"]])

    def test_a_wrapped_bullet_ending_on_a_role_word_stays_one_bullet(self):
        parsed, _ = read(ROLE.format(title="UX Writer"))
        self.assertEqual(["Wrote onboarding and error messages for the mobile app with the product design lead.",
                          "Ran weekly critiques and wrote the guidelines the team reviews every quarter."], parsed["bullets"])
        self.assertEqual(1, len(parsed["roles"]))


if __name__ == "__main__":
    unittest.main()
