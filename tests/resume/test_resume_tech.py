"""Tech and mixed resumes: a CS resume proposes tech fields, filters, skills and its education,
and a finance resume is read exactly as before."""
import importlib.util
import io
import time
import unittest

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel import resume_insights as insights
from intel.matching import match_resume
from intel.profile import validate_profile
from intel.resume import clean_pdf_text, extract_text, parse_resume, profile_from_resume
from tests.resume.test_resume_matching import RESUME as FINANCE_RESUME

KN = load_knowledge()
TECH = {"software", "data_ml", "hardware", "product", "design"}

# A one-page LaTeX resume in the layout CS students use, with invented details, as pypdf reads
# it: the fonts carry no Unicode map, so "fi" comes out as \x1c, "fl" as \x1d, "ff" as \x1b,
# the en dash as \x15 and the bullet as \x88, and kerning splits "T oronto" and "NA TS".
CS_LINES = [
    "Jordan Rivera",
    "555-010-0199 | jordan.rivera@example.com | LinkedIn |GitHub |jordanrivera.dev",
    "Professional Experience",
    "Northwind Semiconductors (NWS) Ottawa, ON",
    "Embedded Firmware Engineer Intern May 2026 \x15 Aug 2026",
    "\x88 Built pre-silicon test benches for power-management \x1crmware features from speci\x1ccations and",
    "existing \x1crmware, enabling feature veri\x1ccation and low-level debugging while uncovering 6 defects.",
    "\x88 Automated \x1crmware validation in Python on Linux and integrated the tests into GitHub Actions CI.",
    "Fabrikam Sensors Inc. Toronto, ON",
    "Junior Software Developer Jan 2025 \x15 Present",
    "\x88 Developed a C++ camera driver and REST API for a lidar sensor, with error handling and unit tests.",
    "\x88 Administered 40+ Jenkins projects and post-commit hook work\x1dows between SVN, JIRA and Jenkins.",
    "Software Co-op Student May 2024 \x15 Dec 2024",
    "\x88 Wrote Python tools to triage and reproduce defects with QA engineers across 3 products.",
    "Selected Projects",
    "Robotic Rover Autonomy Stack | C++20, ROS2, STM32, UART 2026",
    "\x88 Implemented a 100 Hz PID control loop with Kalman-\x1clter sensor fusion on an STM32 microcontroller.",
    "\x88 Built a ROS2 node for motion planning and a real-time telemetry dashboard showing state di\x1berences.",
    "Event Streaming Service | C++17, Python, Docker, NATS, K8s 2025",
    "\x88 Designed event-driven backend microservices using NA TS messaging and Redis, deployed with Docker.",
    "Technical Skills",
    "Embedded & Robotics: STM32, FreeRTOS, ROS2, UART/I2C/SPI, PID Control",
    "Languages: C/C++ (C++17/20), Python, Bash, Java, SQL",
    "Infrastructure: Linux, Git, Jenkins, GitHub Actions, Docker, Kubernetes",
    "T ools & Platforms: Visual Studio, JIRA, SVN",
    "Education",
    "T oronto Lakeshore University Toronto, ON",
    "Bachelor of Computer Science Expected April 2027",
    "Relevant Coursework: Embedded Systems, Operating Systems, Data Structures, Computer Networks",
]
CS_TEXT = clean_pdf_text("\n".join(CS_LINES))

MIXED_RESUME = """ALEX MORGAN
Education
Example University Toronto, ON
Bachelor of Commerce and Computer Science (Double Degree) Expected: Apr 2028
Experience
Maple Capital Partners Toronto, ON
Investment Banking Summer Analyst May 2026 - Aug 2026
- Built DCF and precedent transactions analyses for two sell-side M&A mandates.
- Drafted pitch books and supported due diligence for a C$400M acquisition.
Lakeside Labs Toronto, ON
Software Engineer Intern May 2025 - Aug 2025
- Built React and TypeScript front-end pages for a customer dashboard.
- Added REST APIs and PostgreSQL schemas behind the web app; wrote unit tests.
Technical Skills & Interests
Technical: Excel, Capital IQ, Python, JavaScript, React, SQL, Git
"""


def pdf(lines):
    """A text PDF whose Helvetica font passes the control codes through, as LaTeX's fonts do."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    escape = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    body = b" ".join(f"({escape(line)}) Tj 0 -12 Td".encode("latin-1") for line in lines)
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 9 Tf 40 760 Td " + body + b" ET")
    page[NameObject("/Contents")] = writer._add_object(stream.flate_encode())
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject(
        {NameObject("/F1"): writer._add_object(font)})})
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def field_of(role):
    top = role.split(".")[0]
    return "finance" if top in KN.categories else top


class PdfTextTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "install requirements.txt for PDF support")
    def test_latex_font_codes_and_kerning_splits_are_read_as_text(self):
        text = extract_text("resume.pdf", pdf(CS_LINES))
        self.assertFalse(any(ch in text for ch in "\x15\x1b\x1c\x1d\x88"))
        for phrase in ("power-management firmware features from specifications", "May 2026 – Aug 2026",
                       "• Implemented", "Kalman-filter", "workflows", "differences", "NATS messaging",
                       "Toronto Lakeshore University"):
            self.assertIn(phrase, text)

    def test_a_split_is_rejoined_only_when_the_whole_word_appears_elsewhere(self):
        self.assertEqual("Toronto, ON\nToronto Lakeshore", clean_pdf_text("Toronto, ON\nT oronto Lakeshore"))
        for text in ("I am a T eam lead", "A team of 4", "AI and ML work"):
            self.assertEqual(text, clean_pdf_text(text))


class CsResumeTests(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_resume(CS_TEXT, KN)

    def test_education_graduation_and_tech_roles(self):
        edu = self.parsed["education"]
        self.assertEqual(("Toronto Lakeshore University", "undergraduate", "Computer Science", 2027, 4),
                         tuple(edu[k] for k in ("school", "level", "program", "graduation_year", "graduation_month")))
        self.assertEqual(["Embedded Firmware Engineer Intern", "Junior Software Developer", "Software Co-op Student"],
                         [r["title"] for r in self.parsed["roles"]])
        self.assertEqual([2026, 2026, 2024], [e["end"] for e in self.parsed["entries"][:3]])

    def test_interests_are_tech_specialties_not_quant_research(self):
        keys = [i["key"] for i in self.parsed["role_interests"]]
        self.assertEqual("hardware.embedded_firmware", keys[0])
        self.assertIn("hardware.robotics_autonomy", keys)
        self.assertTrue(all(field_of(k) in TECH for k in keys), keys)

    def test_generic_software_job_titles_target_software(self):
        # "Junior Software Developer" and "Software Co-op Student" name no specialty; a stronger
        # specialty (Infrastructure) must not make them count for nothing.
        interest = {i["key"]: i for i in self.parsed["role_interests"]}
        self.assertIn("software", interest)
        self.assertIn("title: Junior Software Developer", interest["software"]["evidence"])

    def test_tech_skills(self):
        skills = {s["key"] for s in self.parsed["skills"]}
        self.assertLessEqual({"cpp", "c_lang", "python", "bash", "embedded_systems", "microcontrollers",
                              "serial_protocols", "control_systems", "robotics", "docker", "kubernetes",
                              "ci_cd", "git", "linux"}, skills)
        self.assertFalse(skills & {"dcf", "valuation", "financial_modeling"})

    def test_profile_gets_tech_fields_targets_employers_and_education(self):
        before = merge_profile({"education": {"school": "Example Business School", "program": "Commerce", "gpa": 3.9}})
        profile = profile_from_resume(self.parsed, before, KN)
        self.assertEqual([], validate_profile(profile, KN))
        # The default profile's Finance targets were implied, not chosen: the resume's fields replace them.
        self.assertEqual({"hardware", "software"}, set(profile["fields"]))
        self.assertEqual("hardware.embedded_firmware", profile["target_roles"][0])
        self.assertTrue(all(field_of(r) in {"hardware", "software"} for r in profile["target_roles"]))
        self.assertEqual(1.0, max(profile["role_weights"].values()))
        self.assertTrue(profile["target_company_types"])
        self.assertTrue(all(KN.company_types[t].get("track") == "tech" for t in profile["target_company_types"]))
        self.assertIn("embedded_systems", profile["skills"])
        # Another school: the old program and GPA don't carry over.
        self.assertEqual({"level": "undergraduate", "school": "Toronto Lakeshore University", "program": "Computer Science",
                          "gpa": None}, profile["education"])
        self.assertEqual((2027, 4), (profile["graduation_year"], profile["graduation_month"]))

    def test_chosen_tech_fields_stay_as_they_are(self):
        before = merge_profile({"fields": ["software", "hardware"], "role_weights": {"software.backend": 0.5},
                                "target_roles": ["software.backend", "hardware.embedded_firmware"]})
        profile = profile_from_resume(self.parsed, before, KN)
        self.assertEqual(["software", "hardware"], profile["fields"])
        self.assertTrue(all(field_of(r) in {"hardware", "software"} for r in profile["target_roles"]))
        # Targets picked in a chosen board stay, with the priority given them.
        self.assertIn("software.backend", profile["target_roles"])
        self.assertEqual(0.5, profile["role_weights"]["software.backend"])
        self.assertEqual(len(profile["target_roles"]), len(set(profile["target_roles"])))


class TechMatchTests(unittest.TestCase):
    def setUp(self):
        before = merge_profile({"fields": ["software", "hardware"], "target_roles": ["hardware.embedded_firmware"]})
        self.profile = profile_from_resume(parse_resume(CS_TEXT, KN), before, KN)

    def match(self, title, company="Example Corp"):
        facts = build_facts({"title": title, "location": "Toronto, ON", "company": company, "posted": time.time()}, KN)
        return match_resume(facts, self.profile, score_job(facts, self.profile, KN), KN)

    def test_finance_and_other_fields_are_outside_a_tech_profile(self):
        result = self.match("2027 Investment Banking Summer Analyst", "RBC")
        self.assertFalse(result["matched"])
        self.assertIn("Finance role is outside the fields you recruit in", result["exclusions"])
        self.assertFalse(self.match("Data Scientist Intern")["matched"])

    def test_roles_nothing_places_in_a_field_are_not_matches(self):
        # "Illustrator, Intern" and "Revenue Management" internships matched a CS resume on a real install.
        for title in ("Illustrator, Intern", "2027 Summer Internship - Business Technology"):
            with self.subTest(title=title):
                result = self.match(title)
                self.assertFalse(result["matched"])
                self.assertIn("Role doesn't name a field you recruit in", result["exclusions"])
        # A finance profile still reviews them: vague titles are common in finance.
        finance = profile_from_resume(parse_resume(FINANCE_RESUME, KN), merge_profile(), KN)
        facts = build_facts({"title": "2027 Summer Internship - Business Technology", "location": "Toronto, ON",
                             "posted": time.time()}, KN)
        result = match_resume(facts, finance, score_job(facts, finance, KN), KN)
        self.assertNotIn("Role doesn't name a field you recruit in", result["exclusions"])
        self.assertIn("Role relevance needs review", result["review"])

    def test_tech_roles_in_its_fields_stay(self):
        self.assertTrue(self.match("Firmware Engineer Intern")["matched"])
        # Generic software jobs target all of Software, so a frontend role is within the targets.
        frontend = self.match("Frontend Software Engineer Intern")
        self.assertTrue(frontend["matched"])
        self.assertFalse(any("outside your specialties" in r for r in frontend["reasons"]))
        chip = self.match("ASIC Design Verification Engineer Intern")
        self.assertTrue(chip["matched"])
        self.assertTrue(any("outside your specialties" in r for r in chip["reasons"]))

    def test_finance_only_profile_keeps_its_messages(self):
        finance = profile_from_resume(parse_resume(FINANCE_RESUME, KN), merge_profile(), KN)
        facts = build_facts({"title": "Frontend Software Engineer Intern", "location": "Toronto, ON",
                             "posted": time.time()}, KN)
        for kn in (None, KN):
            result = match_resume(facts, finance, score_job(facts, finance, KN), kn)
            self.assertEqual(["Role is outside finance and your selected career targets"], result["exclusions"][:1])


class MixedResumeTests(unittest.TestCase):
    def test_finance_and_software_targets_fields_and_skills(self):
        parsed = parse_resume(MIXED_RESUME, KN)
        fields = {field_of(i["key"]) for i in parsed["role_interests"]}
        self.assertEqual({"finance", "software"}, fields)
        self.assertLessEqual({"dcf", "capital_iq", "react", "javascript", "typescript", "apis"},
                             {s["key"] for s in parsed["skills"]})
        profile = profile_from_resume(parsed, merge_profile({"fields": ["finance"]}), KN)
        self.assertEqual([], validate_profile(profile, KN))
        self.assertEqual(["finance", "software"], profile["fields"])
        self.assertTrue(any(r.startswith("investment_banking.") for r in profile["target_roles"]))
        self.assertTrue(any(r.startswith("software") for r in profile["target_roles"]))
        for title, company in (("2027 Investment Banking Summer Analyst", "RBC"), ("Software Engineer Intern", "Example Corp")):
            facts = build_facts({"title": title, "location": "Toronto, ON", "company": company, "posted": time.time()}, KN)
            with self.subTest(title=title):
                self.assertTrue(match_resume(facts, profile, score_job(facts, profile, KN), KN)["matched"])


class FinanceUnchangedTests(unittest.TestCase):
    def test_finance_resume_is_read_with_the_finance_vocabulary(self):
        parsed = parse_resume(FINANCE_RESUME, KN)
        sections = {"experience": FINANCE_RESUME.splitlines()}
        self.assertFalse(insights.tech_resume(insights.experience_entries(sections), parsed["education"], KN))
        self.assertFalse({s["key"] for s in parsed["skills"]} & {s.key for s in KN.skills if s.tech})
        profile = profile_from_resume(parsed, merge_profile(), KN)
        self.assertNotIn("fields", {k for k in profile if profile[k] != merge_profile().get(k)})

    def test_python_and_machine_learning_still_point_finance_resumes_at_quant(self):
        text = FINANCE_RESUME.replace("Managed liquidity", "Built Python machine learning backtests and managed liquidity")
        self.assertIn("quant.quant_research", parse_resume(text, KN)["role_categories"])

    def test_postings_read_tech_skills_only_outside_finance(self):
        description = "Excel, DCF models, Python, Git, Docker, Jira and Kubernetes."
        finance = build_facts({"title": "Investment Banking Analyst", "company": "RBC", "description": description}, KN)
        tech = build_facts({"title": "Backend Software Engineer", "description": description}, KN)
        self.assertTrue(finance["classification"]["is_finance"])
        self.assertEqual({"excel", "dcf", "python"}, {s["key"] for s in finance["skills"]})
        self.assertLessEqual({"python", "git", "docker", "agile", "kubernetes"}, {s["key"] for s in tech["skills"]})


if __name__ == "__main__":
    unittest.main()
