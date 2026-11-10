"""Product and Design fixture resumes (plans/product-design-board.md 9.9): each reads the same as text, as a PDF, as a
LaTeX PDF and in three Word layouts, and as pinned here, read by eye. A design template's layout reads as its
single-column form (9.8), aspiring wording on the finance fixture opens no P&D board (9.6), and the 47 degree lines
of 9.2 read their level. People, schools and employers are invented."""
import importlib.util
import unittest
from xml.sax.saxutils import escape

from intel import load_knowledge, merge_profile
from intel.resume import extract_text, parse_resume, profile_from_resume
from tests.resume.test_resume_documents import docx
from tests.resume.test_resume_health import _RIGHT_SIDE, latex_lines, plain_lines, word_docx
from tests.resume.test_resume_matching import RESUME as FINANCE
from tests.resume.test_resume_tech import CS_TEXT, pdf

KN = load_knowledge()
HAS_PDF = importlib.util.find_spec("pypdf")

PM = """MAYA PATEL
maya.patel@example.com | 555-010-0211 | Toronto, ON
Education
Northfield University Toronto, ON
Honours Business Administration (HBA) Expected: Apr 2027
Experience
Lumenly Waterloo, ON
Product Manager Intern May 2026 – Aug 2026
• Wrote PRDs for a self-serve onboarding flow and prioritized the backlog in Jira with two engineering squads.
• Ran 12 customer interviews and an A/B test on the pricing page that lifted trial starts by 9%.
Harbourline Software Toronto, ON
Product Analyst Co-op Sep 2025 – Dec 2025
• Built Amplitude and Mixpanel dashboards for activation and retention, and wrote SQL queries for weekly product reviews.
• Mapped the checkout funnel with the design team and turned drop-off findings into three roadmap items.
Leadership
Northfield Product Club Toronto, ON
VP Product Sep 2025 – Present
• Organized a product case competition for 80 students with judges from local startups.
Skills
Product: roadmaps, PRDs, user stories, A/B testing, user interviews, prioritization
Tools: Jira, Confluence, Figma, Amplitude, Mixpanel, SQL, Excel
"""

UX_DESIGNER = """LEAH NGUYEN
leah.nguyen@example.com | 555-010-0222 | Vancouver, BC
Portfolio: leahnguyen.design | behance.net/leahnguyen | dribbble.com/leahnguyen
Education
Pacific Coast University Vancouver, BC
Bachelor of Design (BDes), Interaction Design Expected: Apr 2027
Design Experience
Northwind Health Vancouver, BC
Product Design Intern May 2026 – Aug 2026
• Redesigned the appointment booking flow in Figma, from wireframes to a high-fidelity prototype, and cut task time by 30%.
• Ran five moderated usability tests and presented the findings to the product manager and engineers.
Fernwood Studio Vancouver, BC
UX/UI Design Co-op Sep 2025 – Dec 2025
• Built a design system of 40 components with tokens for colour, type and spacing, documented for developers.
• Designed responsive web pages for three client sites and handed off specs in Figma Dev Mode.
Case Studies
Transit Trip Planner | Figma, Maze 2025
• Interviewed 14 riders, synthesized an affinity map and tested two prototypes with a 5-second test.
Skills
Design: user research, wireframing, prototyping, interaction design, design systems, accessibility (WCAG)
Tools: Figma, Sketch, Adobe Creative Cloud, Miro, Maze, HTML, CSS
"""

UX_RESEARCHER = """SAMIR HADDAD
samir.haddad@example.com | 555-010-0233 | Seattle, WA
Education
Northfield University Seattle, WA
M.S. in Human-Computer Interaction Expected: Jun 2027
B.A. in Psychology, Minor in Statistics Jun 2024
Research Experience
Cobalt Cloud Seattle, WA
UX Research Intern Jun 2026 – Sep 2026
• Planned and ran 18 moderated interviews and a diary study on admin workflows, and synthesized findings into personas.
• Designed a 1,200-response survey in Qualtrics and analyzed it in R with the data science team.
Northfield University, Human Factors Lab Seattle, WA
Graduate Research Assistant Sep 2025 – Jun 2026
• Ran usability studies with eye tracking on a voice assistant prototype and coded transcripts in Dovetail.
Publications
Haddad, S. et al. Trust in voice assistants. CHI Late-Breaking Work, 2026.
Skills
Methods: user interviews, usability testing, survey design, diary studies, card sorting, journey mapping
Tools: Qualtrics, Dovetail, UserTesting, Figma, R, SQL
"""

VISUAL = """CHLOE MARTIN
chloe.martin@example.com | 555-010-0244 | Toronto, ON
chloemartin.ca | behance.net/chloemartin
Education
Lakeshore College Toronto, ON
Advanced Diploma, Graphic Design Apr 2025
Experience
Maple & Finch Creative Toronto, ON
Junior Graphic Designer May 2025 – Present
• Designed brand identities, packaging and social campaigns for six retail clients in Illustrator, Photoshop and InDesign.
• Prepared print-ready files and managed proofs with printers for a 40-store in-store campaign.
Riverside Coffee Co. Toronto, ON
Brand Design Intern Jan 2025 – Apr 2025
• Refreshed the logo, colour palette and type system, and wrote the brand guidelines used across 12 cafes.
Selected Work
Harbour Film Festival identity | Illustrator, After Effects 2024
• Created the festival's identity, posters and motion graphics for screens and social media.
Awards
Applied Arts Student Award, Packaging, 2024
Skills
Branding, typography, layout, illustration, motion graphics, print production
Tools: Adobe Creative Cloud (Illustrator, Photoshop, InDesign, After Effects), Figma, Canva
"""

INDUSTRIAL = """OWEN BRADLEY
owen.bradley@example.com | 555-010-0255 | Montreal, QC
Portfolio: owenbradley.design
Education
Northfield University Montreal, QC
Bachelor of Industrial Design Expected: May 2027
Experience
Arbor Home Products Montreal, QC
Industrial Design Intern May 2026 – Aug 2026
• Developed concepts for a countertop appliance from sketches to SolidWorks models and appearance prototypes.
• Specified CMF options with suppliers and prepared design-for-manufacturing notes for injection-moulded parts.
Kestrel Outdoor Gear Montreal, QC
Product Design Co-op Sep 2025 – Dec 2025
• Built foam and 3D-printed prototypes for a hydration pack and ran fit tests with 20 hikers.
Projects
Modular Desk Lamp | SolidWorks, KeyShot 2025
• Designed and prototyped a modular lamp with a snap-fit aluminium arm and rendered it in KeyShot.
Skills
Sketching, 3D modelling, prototyping, CMF, design for manufacturing, user research
Tools: SolidWorks, Rhino, KeyShot, Fusion 360, Adobe Illustrator, Photoshop
"""

CS_PM = """ETHAN KIM
ethan.kim@example.com | 555-010-0266 | Waterloo, ON
Education
Northfield University Waterloo, ON
Bachelor of Computer Science (Co-op) Expected: Apr 2027
Experience
Lumenly Waterloo, ON
Product Manager Intern Jan 2026 – Apr 2026
• Owned the roadmap for the notifications team, wrote specs and ran sprint planning with five engineers in Jira.
• Defined success metrics and analyzed an A/B test in SQL and Amplitude that raised weekly active users by 6%.
Harbourline Software Toronto, ON
Software Engineer Intern May 2025 – Aug 2025
• Built REST APIs in Python and Django for the billing service and added integration tests to the CI pipeline.
• Shipped a React and TypeScript settings page used by 20,000 customers.
Projects
Course Planner | React, Node.js, PostgreSQL 2025
• Built a web app that plans degree requirements for 3,000 students, from user interviews to launch.
Skills
Languages: Python, Java, TypeScript, SQL
Product: roadmaps, user stories, A/B testing, Figma, Jira, Amplitude
"""

# Each fixture and its headings (the listed Word layouts make each heading a list item).
FIXTURES = {
    "pm": (PM, {"Education", "Experience", "Leadership", "Skills"}),
    "ux_designer": (UX_DESIGNER, {"Education", "Design Experience", "Case Studies", "Skills"}),
    "ux_researcher": (UX_RESEARCHER, {"Education", "Research Experience", "Publications", "Skills"}),
    "visual": (VISUAL, {"Education", "Experience", "Selected Work", "Awards", "Skills"}),
    "industrial": (INDUSTRIAL, {"Education", "Experience", "Projects", "Skills"}),
    "cs_pm": (CS_PM, {"Education", "Experience", "Projects", "Skills"}),
}


def forms(text, headings):
    """The resume as text, as a PDF and a LaTeX PDF, and in the three Word layouts."""
    yield "text", parse_resume(text, KN)
    if HAS_PDF:
        yield "pdf", parse_resume(extract_text("resume.pdf", pdf(plain_lines(text))), KN)
        yield "latex", parse_resume(extract_text("resume.pdf", pdf(latex_lines(text))), KN)
    for listed in (None, "nested", "flat"):
        data = word_docx(text, listed, headings)
        yield f"docx {listed}", parse_resume(extract_text("resume.docx", data), KN, wrapped=False)


def reading(parsed):
    """What a form must read as the text does."""
    edu = parsed["education"]
    profile = profile_from_resume(parsed, merge_profile({}), KN)
    return {"education": tuple(edu[k] for k in ("level", "program", "school", "graduation_year", "graduation_month")),
            "entries": [(e["block"], e["company"], e["title"]) for e in parsed["entries"]],
            "roles": [(r["title"], r["category"], r["subcategory"]) for r in parsed["roles"]],
            "interests": [(i["key"], i["strength"]) for i in parsed["role_interests"]],
            "skills": [s["key"] for s in parsed["skills"]],
            "fields": profile.get("fields"), "target_roles": profile.get("target_roles")}


def read(name):
    return reading(parse_resume(FIXTURES[name][0], KN))


class FormTests(unittest.TestCase):
    def test_each_form_reads_as_the_text(self):
        for name, (text, headings) in FIXTURES.items():
            want = reading(parse_resume(text, KN))
            for form, parsed in forms(text, headings):
                with self.subTest(fixture=name, form=form):
                    self.assertEqual(want, reading(parsed))


class FixtureTests(unittest.TestCase):
    def test_pm(self):
        r = read("pm")
        self.assertEqual(("undergraduate", "Business Administration", "Northfield University", 2027, 4), r["education"])
        # "VP Product" under Leadership is no role.
        self.assertEqual([("Product Manager Intern", "product", "apm_programs"),
                          ("Product Analyst Co-op", "product", "product_analytics")], r["roles"])
        self.assertEqual(["product.product_analytics", "product.product_management", "product.apm_programs"],
                         [k for k, _ in r["interests"]])
        self.assertEqual(["product"], r["fields"])
        self.assertLessEqual({"figma", "product_analytics_tools", "ab_testing", "prds", "jira", "sql", "excel"},
                             set(r["skills"]))

    def test_ux_designer(self):
        # "Design Experience" and "Case Studies" (D39), BDes (D37). Known limit: the program reads "Design", the word
        # after "of", not "Interaction Design".
        r = read("ux_designer")
        self.assertEqual(("undergraduate", "Pacific Coast University", 2027, 4),
                         tuple(r["education"][i] for i in (0, 2, 3, 4)))
        self.assertEqual([("experience", "Northwind Health", "Product Design Intern"),
                          ("experience", "Fernwood Studio", "UX/UI Design Co-op"),
                          ("projects", "", "Transit Trip Planner | Figma, Maze")], r["entries"])
        self.assertEqual([("Product Design Intern", "design", "product_design"),
                          ("UX/UI Design Co-op", "design", "product_design")], r["roles"])
        self.assertEqual(["design.product_design"], [k for k, _ in r["interests"]])
        self.assertEqual(["design"], r["fields"])
        self.assertLessEqual({"figma", "sketch_xd", "adobe_cc", "prototyping", "wireframing", "user_research",
                              "usability_testing", "design_systems", "accessibility", "html_css"}, set(r["skills"]))

    def test_ux_researcher(self):
        # "M.S. in" above a B.A. (D37), "Research Experience" (D39).
        r = read("ux_researcher")
        self.assertEqual(("masters", "Human-Computer Interaction", "Northfield University", 2027, 6), r["education"])
        self.assertEqual([("UX Research Intern", "design", "ux_research")], r["roles"])
        # No AI & Data: the R and statistics are research methods here.
        self.assertEqual(["design.ux_research"], [k for k, _ in r["interests"]])
        self.assertEqual(["design"], r["fields"])
        self.assertLessEqual({"r", "sql", "statistics", "user_research", "usability_testing", "survey_design", "figma"},
                             set(r["skills"]))

    def test_visual_designer(self):
        # An Advanced Diploma (D38) and "Selected Work" (D39). Known limits: the diploma's program and its lone date
        # are unread, and "Illustrator" after " | " on the project line reads as a role.
        r = read("visual")
        self.assertEqual(("other", "Lakeshore College"), (r["education"][0], r["education"][2]))
        self.assertEqual([("Junior Graphic Designer", "design", "visual_brand"),
                          ("Brand Design Intern", "design", "visual_brand")], r["roles"][:2])
        self.assertEqual([("projects", "", "Harbour Film Festival identity | Illustrator, After Effects")],
                         [e for e in r["entries"] if e[0] == "projects"])
        self.assertEqual(["design.visual_brand"], [k for k, _ in r["interests"]])
        self.assertEqual(["design"], r["fields"])
        self.assertLessEqual({"adobe_cc", "adobe_design_apps", "after_effects", "typography", "motion_graphics",
                              "figma"}, set(r["skills"]))

    def test_industrial_designer(self):
        # Known limits: "Product Design Co-op" reads product_design whatever its bullets say, and Finance's `options`
        # skill matches "CMF options" (D40).
        r = read("industrial")
        self.assertEqual(("undergraduate", "Industrial Design", "Northfield University", 2027, 5), r["education"])
        self.assertEqual(("Industrial Design Intern", "design", "industrial_design"), r["roles"][0])
        self.assertEqual("design.industrial_design", r["interests"][0][0])
        self.assertEqual(["design"], r["fields"])
        self.assertLessEqual({"solidworks", "rhino", "keyshot", "cad", "cmf", "dfm"}, set(r["skills"]))

    def test_cs_with_pm_internships_keeps_both_boards(self):
        r = read("cs_pm")
        self.assertEqual(("undergraduate", "Computer Science"), r["education"][:2])
        self.assertEqual([("Product Manager Intern", "product", "apm_programs"),
                          ("Software Engineer Intern", "software", None)], r["roles"])
        self.assertEqual(["software.backend", "software.frontend", "product.apm_programs", "software"],
                         [k for k, _ in r["interests"]])
        self.assertEqual(["software", "product"], r["fields"])


# 9.8: the UX designer with known headings, as a design template lays it out (D): the name and contact in a Word text
# box (Word writes it twice, the drawing and its VML fallback) above a two-column table, Education and Skills in the
# sidebar cell and the experience in the main one.
UX_KNOWN = UX_DESIGNER.replace("Design Experience\n", "Experience\n").replace("Case Studies\n", "Projects\n")
NUMBERING = ('<w:numbering><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl>'
             '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')


def para(line):
    run = lambda s: f'<w:r><w:t xml:space="preserve">{escape(s)}</w:t></w:r>'
    if line.startswith("• "):
        return f'<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr>{run(line[2:])}</w:p>'
    right = _RIGHT_SIDE.match(line)
    if right:
        return (f'<w:p><w:pPr><w:tabs><w:tab w:val="right" w:pos="6000"/></w:tabs></w:pPr>{run(right[1])}'
                f'<w:r><w:tab/></w:r>{run(right[2])}</w:p>')
    return f"<w:p>{run(line)}</w:p>"


def layout_d(text):
    lines = text.splitlines()
    cut = lambda heading: lines.index(heading)
    header, education = lines[:cut("Education")], lines[cut("Education"):cut("Experience")]
    main, skills = lines[cut("Experience"):cut("Skills")], lines[cut("Skills"):]
    inner = "".join(para(l) for l in header)
    box = ('<w:p><w:r><mc:AlternateContent xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006">'
           '<mc:Choice Requires="wps"><w:drawing><wp:anchor xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/'
           'wordprocessingDrawing"><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
           '<a:graphicData><wps:wsp xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">'
           f'<wps:txbx><w:txbxContent>{inner}</w:txbxContent></wps:txbx></wps:wsp></a:graphicData></a:graphic>'
           '</wp:anchor></w:drawing></mc:Choice><mc:Fallback><w:pict><v:shape xmlns:v="urn:schemas-microsoft-com:vml">'
           f'<v:textbox><w:txbxContent>{inner}</w:txbxContent></v:textbox></v:shape></w:pict></mc:Fallback>'
           '</mc:AlternateContent></w:r></w:p>')
    cell = lambda ls, w: f'<w:tc><w:tcPr><w:tcW w:w="{w}" w:type="dxa"/></w:tcPr>{"".join(para(l) for l in ls)}</w:tc>'
    table = ('<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr><w:tblGrid><w:gridCol w:w="3000"/>'
             f'<w:gridCol w:w="6360"/></w:tblGrid><w:tr>{cell(education + skills, 3000)}{cell(main, 6360)}</w:tr>'
             '</w:tbl>')
    return docx(box + table, numbering=NUMBERING)


class LayoutTests(unittest.TestCase):
    def test_a_text_box_header_over_a_sidebar_table_reads_as_one_column(self):
        # 9.8, D41. Recorded, not pinned as right: a table with one row per entry (B), the experience in a text box
        # (F, read 3 times) and a PDF written row by row across two columns.
        one_column = reading(parse_resume(extract_text("resume.docx", word_docx(UX_KNOWN)), KN, wrapped=False))
        layout = reading(parse_resume(extract_text("resume.docx", layout_d(UX_KNOWN)), KN, wrapped=False))
        for part in ("education", "roles", "interests", "fields", "target_roles"):
            with self.subTest(part=part):
                self.assertEqual(one_column[part], layout[part])
        self.assertEqual(set(one_column["skills"]), set(layout["skills"]))


# 9.6: P&D wording a finance student might have. The finance fixture stays Finance-only in each.
FIN_DEGREE = "Bachelor of Commerce - Finance & Economics Specialist Expected: Apr 2028"
NAME = "TEST CANDIDATE\n"
ASPIRING = {
    "summary: aspiring PM": (NAME, NAME + "Summary\nAspiring product manager with a finance background.\n"),
    "headline: aspiring product manager": (NAME, NAME + "Aspiring Product Manager | Finance student\n"),
    "summary: interested in UX": (NAME, NAME + "Summary\nInterested in UX design and user research.\n"),
    "minor in design": (FIN_DEGREE, FIN_DEGREE.replace(" Expected", ", Minor in Design Expected")),
    "minor in computer science": (FIN_DEGREE, FIN_DEGREE.replace(" Expected", ", Minor in Computer Science Expected")),
    "coursework: HCI": ("cGPA: 3.92/4.00\n",
                        "cGPA: 3.92/4.00\nRelevant Coursework: Human-Computer Interaction, Corporate Finance\n"),
    "certification: Google UX": ("Technical Skills & Interests\n",
                                 "Certifications\nGoogle UX Design Certificate, 2025\nTechnical Skills & Interests\n"),
    "leadership: product club": ("Research & Operations Team Lead Jan 2024 - Jan 2025\n",
                                 "Research & Operations Team Lead Jan 2024 - Jan 2025\n"
                                 "Product Management Club Member Sep 2024 - Present\n"),
    "bullet: shadowed the PM": ("Managed liquidity and cash positioning with Excel.\n",
                                "Managed liquidity and cash positioning with Excel.\n"
                                "• Shadowed the product manager on two launches and wrote the release notes.\n"),
}


class AspiringTests(unittest.TestCase):
    def test_aspiring_wording_opens_no_pd_board_on_the_finance_fixture(self):
        # A single "UX Design Course Project" adds Design at 0.33 through its title, as main reads it (D41): recorded,
        # not pinned.
        base = reading(parse_resume(FINANCE, KN))
        for name, (old, new) in ASPIRING.items():
            self.assertEqual(1, FINANCE.count(old), name)
            with self.subTest(variant=name):
                r = reading(parse_resume(FINANCE.replace(old, new), KN))
                self.assertEqual(base["fields"], r["fields"])
                self.assertEqual([], [k for k, _ in r["interests"] if k.split(".")[0] in ("product", "design")])
                self.assertEqual([], [t for t in r["roles"] if t[1] in ("product", "design")])

    def test_aspiring_wording_changes_nothing_on_the_cs_fixture(self):
        base = reading(parse_resume(CS_TEXT, KN))
        project = ("\nProjects\nProduct Management Course Project | Figma 2025\n"
                   "• Wrote a PRD and a roadmap for a campus app in a one-term course.\nSkills")
        summary = "\nSummary\nAspiring product manager who loves building for users.\n"
        for name, text in (("project: PM course", CS_TEXT.replace("\nSkills", project, 1)),
                           ("summary: aspiring PM", CS_TEXT.replace("\n", summary, 1))):
            with self.subTest(variant=name):
                r = reading(parse_resume(text, KN))
                self.assertEqual((base["interests"], base["fields"]), (r["interests"], r["fields"]))


DEGREE_TEXT = """JORDAN AVERY
jordan.avery@example.com | 555-010-0199 | Toronto, ON
Education
{school}
{degree} Expected: Apr 2027
Experience
Lakeview Analytics Toronto, ON
Operations Assistant May 2025 – Aug 2025
• Kept the team's weekly schedule and supplier records up to date in shared spreadsheets.
Skills
Excel, PowerPoint, teamwork, attention to detail
"""
NORTHFIELD, LAKESHORE = "Northfield University Toronto, ON", "Lakeshore College Toronto, ON"
DESIGN_SCHOOL = "Lakeshore School of Design Toronto, ON"
# 9.2's degree lines, their school lines and the level each reads. BID, MID and "MA," at a line's start stay unread:
# "bid", "mid" and the state MA (D37).
DEGREE_LINES = [
    ("Bachelor of Design (BDes), Interaction Design", NORTHFIELD, "undergraduate"),
    ("BDes, Industrial Design", NORTHFIELD, "undergraduate"),
    ("B.Des. in Communication Design", NORTHFIELD, "undergraduate"),
    ("BDes (Hons), Graphic Design", NORTHFIELD, "undergraduate"),
    ("BFA, Graphic Design", DESIGN_SCHOOL, "undergraduate"),
    ("Bachelor of Fine Arts, Graphic Design", DESIGN_SCHOOL, "undergraduate"),
    ("BA in Design", NORTHFIELD, "undergraduate"),
    ("BA, Design", NORTHFIELD, "undergraduate"),
    ("Bachelor of Arts, Communication Design", NORTHFIELD, "undergraduate"),
    ("Honours Bachelor of Interaction Design", "Lakeshore College Oakville, ON", "undergraduate"),
    ("Bachelor of Industrial Design", LAKESHORE, "undergraduate"),
    ("BID, Industrial Design", LAKESHORE, None),
    ("BSc in Human-Computer Interaction", NORTHFIELD, "undergraduate"),
    ("B.S. in Human-Computer Interaction", NORTHFIELD, "undergraduate"),
    ("Bachelor of Science, Cognitive Science", NORTHFIELD, "undergraduate"),
    ("BSc, Cognitive Science", NORTHFIELD, "undergraduate"),
    ("BA, Psychology", NORTHFIELD, "undergraduate"),
    ("Bachelor of Arts, Psychology", NORTHFIELD, "undergraduate"),
    ("BCom, Marketing", NORTHFIELD, "undergraduate"),
    ("Bachelor of Commerce, Marketing", NORTHFIELD, "undergraduate"),
    ("BSc Computer Science", NORTHFIELD, "undergraduate"),
    ("Bachelor of Computer Science", NORTHFIELD, "undergraduate"),
    ("MDes, Interaction Design", NORTHFIELD, "masters"),
    ("Master of Design (MDes)", NORTHFIELD, "masters"),
    ("MFA, Interaction Design", "Lakeshore School of Design New York, NY", "masters"),
    ("Master of Fine Arts, Design", "Lakeshore School of Design New York, NY", "masters"),
    ("MHCI", "Northfield University Pittsburgh, PA", "masters"),
    ("MHCI, Human-Computer Interaction", "Northfield University Pittsburgh, PA", "masters"),
    ("Master of Human-Computer Interaction", "Northfield University Pittsburgh, PA", "masters"),
    ("Master of Human-Computer Interaction (MHCI)", "Northfield University Pittsburgh, PA", "masters"),
    ("MSc in Human-Computer Interaction", NORTHFIELD, "masters"),
    ("M.S. in Human-Computer Interaction", "Northfield University Seattle, WA", "masters"),
    ("MS, Human-Centered Design & Engineering", "Northfield University Seattle, WA", "masters"),
    ("MA in Interaction Design", NORTHFIELD, "masters"),
    ("MA, Communication Design", NORTHFIELD, None),
    ("MID, Industrial Design", "Lakeshore Institute New York, NY", None),
    ("MBA", NORTHFIELD, "mba"),
    ("Master of Business Administration (MBA)", NORTHFIELD, "mba"),
    ("PhD, Human-Computer Interaction", NORTHFIELD, "phd"),
    ("Advanced Diploma, Graphic Design", LAKESHORE, "other"),
    ("Ontario College Advanced Diploma, Graphic Design", "Lakeshore Polytechnic Toronto, ON", "other"),
    ("Diploma, Graphic Design", LAKESHORE, "other"),
    ("Ontario College Graduate Certificate, User Experience Design", "Lakeshore Polytechnic Toronto, ON", "other"),
    ("Graduate Certificate, UX Design", LAKESHORE, "other"),
    ("Certificate in UX Design", LAKESHORE, "other"),
    ("UX Design Diploma", "Lakeshore Design Academy Toronto, ON", "other"),
    ("Google UX Design Professional Certificate", "Coursera", "other"),
]


class DegreeLineTests(unittest.TestCase):
    def test_each_degree_line_reads_its_level(self):
        self.assertEqual(47, len(DEGREE_LINES))
        for degree, school, level in DEGREE_LINES:
            with self.subTest(degree=degree):
                text = DEGREE_TEXT.format(degree=degree, school=school)
                self.assertEqual(level, parse_resume(text, KN)["education"]["level"])
