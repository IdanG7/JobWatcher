"""Product and Design resumes open their own track (plans/product-design-board.md 9.4, D24): a design or HCI degree or a
P&D job title opens it, its signals read the work, and a UX resume no longer adds the Software board. The reader every
board shares reads their degrees, programs and diplomas (9.2, D37, D38) and their headings (9.3, D39). People, schools and employers are invented."""
import unittest

from intel import load_knowledge, merge_profile
from intel import resume_insights as insights
from intel.profile import validate_profile
from intel.resume import extract_text, parse_resume, profile_from_resume
from tests.resume.test_resume_health import word_docx

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


DEGREE = """JORDAN AVERY
jordan.avery@example.com | 555-010-0199 | Toronto, ON
Education
{school}
{degree} Expected: Apr 2027
Experience
Lakeview Analytics Toronto, ON
Operations Assistant May 2025 – Aug 2025
• Kept the team's weekly schedule and supplier records up to date in shared spreadsheets.
"""


def read(text):
    parsed = parse_resume(text, KN)
    return parsed, insights.resume_tracks(parsed["entries"], parsed["education"], KN)


def level(degree, school="Northfield University Toronto, ON"):
    return parse_resume(DEGREE.format(degree=degree, school=school), KN)["education"]["level"]


def program(degree):
    return parse_resume(DEGREE.format(degree=degree, school="Northfield University Toronto, ON"), KN)["education"]["program"]


class DegreeLevelTests(unittest.TestCase):
    def test_design_and_hci_abbreviations_set_the_level(self):
        # 9.2, D37: these set no level on main, so a design graduate's profile kept whatever level it had.
        for degree, expected in (("BDes, Industrial Design", "undergraduate"),
                                 ("B.Des. in Communication Design", "undergraduate"),
                                 ("BDes (Hons), Graphic Design", "undergraduate"),
                                 ("BFA, Graphic Design", "undergraduate"),
                                 ("MDes, Interaction Design", "masters"),
                                 ("MFA, Interaction Design", "masters"),
                                 ("MHCI", "masters"),
                                 ("MHCI, Human-Computer Interaction", "masters"),
                                 ("M.S. in Human-Computer Interaction", "masters"),
                                 ("MS in Human-Computer Interaction", "masters"),
                                 ("MS, Human-Centered Design & Engineering", "masters")):
            with self.subTest(degree=degree):
                self.assertEqual(expected, level(degree))

    def test_a_masters_abbreviation_outranks_the_bachelors_below_it(self):
        self.assertEqual("masters", level("M.S. in Human-Computer Interaction Sep 2024 – Jun 2026\n"
                                          "B.A. in Psychology, Minor in Statistics"))

    def test_an_abbreviated_degree_is_dated_by_the_year_on_its_line(self):
        edu = parse_resume("PAT LEE\npat.lee@example.com\nEducation\nRiverside University Pittsburgh, PA\nMHCI 2026\n"
                           "Experience\nNorthwind Apps Pittsburgh, PA\nUX Research Intern May 2025 – Aug 2025\n", KN)["education"]
        self.assertEqual(("masters", 2026), (edu["level"], edu["graduation_year"]))

    def test_the_abbreviations_are_read_only_where_a_degree_is(self):
        # A state after a city or after "in", Microsoft in coursework, a show's name: the bachelor's below is read.
        for degree in ("B.A. in Psychology\nDelta State University Cleveland, MS, 2024",
                       "B.A. in Psychology\nSouthern University in MS, USA",
                       "B.Sc. in Computer Science\nRelevant Courses: Databases (MS, SQL Server), Algorithms",
                       "B.Com, Finance\nTools: MS in Excel and Access",
                       "B.A. in Studio Arts\nExhibitions: BFA Gallery, MFA Showcase 2023",
                       "Bachelor of Science, Computer Science\nThesis: cut page loads to 200 ms in mobile browsers",
                       "Bachelor of Science, Computer Science\nCapstone: set up mfa, sso and vpn for the lab"):
            with self.subTest(degree=degree):
                self.assertEqual("undergraduate", level(degree))
        self.assertIsNone(level("Exhibited at the BFA Gallery"))
        # "MA," at a line start may be a state; BID and MID are words.
        for degree in ("MA, Communication Design", "BID, Industrial Design", "MID, Industrial Design"):
            with self.subTest(degree=degree):
                self.assertIsNone(level(degree))
        # With no Education heading the whole resume is searched, and there MFA and "MS," are other words.
        text = ("JORDAN AVERY\njordan.avery@example.com\nIT Analyst, Lakeview Analytics, 2019 – Present\n"
                "• Rolled out MFA, SSO and VPN for 2,000 users.\n• MS, Teams and Zoom support for 40 offices.\n")
        self.assertIsNone(parse_resume(text, KN)["education"]["level"])


class ProgramTests(unittest.TestCase):
    def test_in_and_hyphens_inside_a_program_name_are_part_of_it(self):
        # 9.2, D37: the "In" of "Interaction" was read as the word "in", and a hyphen ended the name.
        for degree, expected in (("Honours Bachelor of Interaction Design", "Interaction Design"),
                                 ("Bachelor of Industrial Design", "Industrial Design"),
                                 ("Master of Human-Computer Interaction (MHCI)", "Human-Computer Interaction"),
                                 ("M.S. in Human-Computer Interaction", "Human-Computer Interaction"),
                                 ("BSc in Human-Computer Interaction", "Human-Computer Interaction"),
                                 ("MS, Human-Centered Design & Engineering", "Human-Centered Design & Engineering"),
                                 ("Majoring in Human-Computer Interaction", "Human-Computer Interaction"),
                                 # other boards' degrees had the same two bugs
                                 ("Bachelor of Information Technology", "Information Technology"),
                                 ("Master of International Affairs", "International Affairs"),
                                 ("Bachelor of Arts, Socio-Cultural Studies", "Socio-Cultural Studies")):
            with self.subTest(degree=degree):
                self.assertEqual(expected, program(degree))

    def test_a_co_op_or_a_school_after_a_spaced_hyphen_is_no_program(self):
        for degree, expected in (("Bachelor of Business Administration - Co-op", "Business Administration"),
                                 ("Bachelor of Science - Computer Science - Co-op", "Computer Science"),
                                 ("Bachelor of Science in Nursing - Lakeshore University 2012", "Nursing"),
                                 ("Bachelor of Computer Science (Co-op)", "Computer Science"),
                                 ("Bachelor of Arts - Co-operative Education", "Arts"),
                                 ("B.Com - Co-op", "Commerce"),
                                 ("BSc, Co-op", None),
                                 ("B.A. - Co-operative Education", None)):
            with self.subTest(degree=degree):
                self.assertEqual(expected, program(degree))


class OtherLevelTests(unittest.TestCase):
    def test_a_diploma_or_certificate_alone_is_the_level_other(self):
        # 9.2, D38: Settings' "Other: Diploma, certificate or other". These set no level before. A high school's
        # diploma too: Settings' "Other" is where a student would put it.
        for degree in ("Advanced Diploma, Graphic Design", "Ontario College Advanced Diploma, Graphic Design",
                       "Diploma, Graphic Design", "Ontario College Graduate Certificate, User Experience Design",
                       "Graduate Certificate, UX Design", "Certificate in UX Design", "UX Design Diploma",
                       "Google UX Design Professional Certificate", "Diplôme d'études collégiales (DEC)",
                       "Ontario Secondary School Diploma (OSSD)"):
            with self.subTest(degree=degree):
                self.assertEqual("other", level(degree, school="Lakeshore College Toronto, ON"))

    def test_a_degree_outranks_a_certificate_and_other_is_read_only_under_education(self):
        self.assertEqual("undergraduate", level("Bachelor of Arts, Psychology\nCertificate in UX Design"))
        self.assertEqual("masters", level("Graduate Certificate, UX Design\nMDes, Interaction Design"))
        text = ("JORDAN AVERY\njordan.avery@example.com\nIT Analyst, Lakeview Analytics, 2019 – Present\n"
                "• Earned the Google Data Analytics certificate and trained 40 staff on the new diploma records.\n")
        self.assertIsNone(parse_resume(text, KN)["education"]["level"])

    def test_the_profile_takes_other(self):
        parsed = parse_resume(DEGREE.format(degree="Advanced Diploma, Graphic Design",
                                            school="Lakeshore College Toronto, ON"), KN)
        profile = profile_from_resume(parsed, merge_profile({}), KN)
        self.assertEqual("other", profile["education"]["level"])
        self.assertEqual([], validate_profile(profile, KN))


UX_TOP = """LEAH NGUYEN
leah.nguyen@example.com | 555-010-0301 | Toronto, ON
Education
Lakeshore University Toronto, ON
Bachelor of Design, Interaction Design Sep 2022 – Apr 2026
"""
UX_JOB = """Northwind Apps Toronto, ON
Product Design Intern May 2025 – Aug 2025
• Ran usability testing with 12 participants and turned the findings into wireframes in Figma.
"""
UX_PROJECT = """Transit Trip Planner | Figma 2025
• Redesigned a trip planner's booking flow and cut the steps from 7 to 4.
"""


def forms(*sections):
    """A UX resume with these (heading, lines) sections after Education, as text and as each Word layout."""
    text = UX_TOP + "".join(f"{heading}\n{lines}" for heading, lines in sections) + "Skills\nFigma, Sketch, user research\n"
    yield "text", parse_resume(text, KN)
    headings = {"Education", "Skills", *(heading for heading, _ in sections)}
    for listed in (None, "nested", "flat"):
        data = word_docx(text, listed, headings)
        yield f"docx {listed}", parse_resume(extract_text("resume.docx", data), KN, wrapped=False)


def block(parsed, name):
    return [(e["company"], e["title"]) for e in parsed["entries"] if e["block"] == name]


class HeadingTests(unittest.TestCase):
    def test_design_research_product_and_ux_experience_are_experience(self):
        # 9.3, D39: right after Education, the job under these headings read as education.
        for heading in ("Design Experience", "Research Experience", "Product Experience", "UX Experience"):
            for form, parsed in forms((heading, UX_JOB), ("Case Studies", UX_PROJECT)):
                with self.subTest(heading=heading, form=form):
                    self.assertEqual([("Northwind Apps", "Product Design Intern")], block(parsed, "experience"))
                    self.assertEqual(["Product Design Intern"], [r["title"] for r in parsed["roles"]])

    def test_portfolio_selected_work_and_case_studies_are_projects(self):
        # After an Experience entry the heading read as the next project's employer.
        for heading in ("Portfolio", "Selected Work", "Case Studies"):
            for form, parsed in forms(("Experience", UX_JOB), (heading, UX_PROJECT)):
                with self.subTest(heading=heading, form=form):
                    self.assertEqual([("", "Transit Trip Planner | Figma")], block(parsed, "projects"))

    def test_a_portfolio_heading_is_no_asset_management_interest(self):
        # Right after Education, "Portfolio" was education text, which the finance signal "portfolios?" reads.
        barista = "Bean Co Toronto, ON\nBarista May 2025 – Aug 2025\n• Served 200 customers a day.\n"
        for form, parsed in forms(("Portfolio", UX_PROJECT), ("Experience", barista)):
            with self.subTest(form=form):
                self.assertNotIn("public_markets.asset_management", [i["key"] for i in parsed["role_interests"]])

    def test_research_experience_on_another_board_and_lines_that_stay_no_heading(self):
        top = "ALEX DOE\nalex.doe@example.com | 555-010-0101 | Toronto, ON\n"
        education = "Education\nLakeshore University Toronto, ON\nBachelor of Science, Biology Expected: Apr 2027\n"
        lab = ("Research Experience\nLakeshore University, Cell Biology Lab Toronto, ON\n"
               "Research Assistant May 2026 – Aug 2026\n• Ran PCR and western blots on patient samples.\n")
        self.assertEqual([("Lakeshore University, Cell Biology Lab", "Research Assistant")],
                         block(parse_resume(top + education + lab + "Skills\nPCR, cell culture\n", KN), "experience"))
        # A heading is a line on its own: "Portfolio Management" and a "Portfolio: <link>" line are no projects.
        fund = ("Experience\nNorthwind Capital Toronto, ON\nInvestment Analyst Intern May 2026 – Aug 2026\n"
                "• Built DCF models.\nPortfolio Management\nStudent Investment Fund Toronto, ON\n"
                "Analyst Sep 2025 – Apr 2026\n• Pitched two equities.\n")
        self.assertEqual([], block(parse_resume(top + education + fund, KN), "projects"))
        link = top + "Portfolio: alexdoe.design\n" + education + "Experience\n" + UX_JOB
        self.assertEqual([], block(parse_resume(link, KN), "projects"))


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
