"""Healthcare resumes: a nursing, a biology co-op and a pharmacy student's resumes propose Healthcare filters,
skills, employer types and education, read the same as text, a PDF or a LaTeX PDF; a biomedical engineering
resume opens Hardware and Healthcare. Finance and tech resumes are read as before (test_resume_tech.py)."""
import importlib.util
import re
import time
import unittest
from xml.sax.saxutils import escape

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.matching import match_resume
from intel.profile import validate_profile
from intel.resume import clean_pdf_text, extract_text, parse_resume, profile_from_resume
from tests.resume.test_resume_documents import docx
from tests.resume.test_resume_tech import pdf

KN = load_knowledge()

# Invented people, schools and employers.
NURSING = """PRIYA NAIR
priya.nair@example.com | 555-010-0142 | Hamilton, ON
Education
Lakeshore University Hamilton, ON
Bachelor of Science in Nursing (BScN) Expected: Apr 2027
Clinical placements: medicine (med-surg), paediatrics, mental health and community health
Clinical Experience
Harbourview General Hospital Hamilton, ON
Nursing Student, Consolidation Placement Jan 2026 – Apr 2026
• Provided patient care for 4–5 patients a shift: head-to-toe assessments, vital signs and charting in the EHR.
• Administered oral, subcutaneous and IV medications under my preceptor and updated care plans with the team.
Bayview Long-Term Care Burlington, ON
Personal Support Worker (Part-Time) May 2024 – Present
• Assisted residents with activities of daily living, mobility and feeding on a 32-bed unit.
• Followed infection control and hand hygiene practices and reported changes in condition to the charge nurse.
Volunteer Experience
Harbourview General Hospital Hamilton, ON
Emergency Department Volunteer Sep 2023 – Apr 2024
Certifications
BLS for Healthcare Providers (CPR Level HCP), 2026
Standard First Aid, 2025
Skills
EHR charting, medication administration, patient education, infection prevention
"""

BIOLOGY = """MARCUS CHEN
marcus.chen@example.com | 555-010-0177 | Vancouver, BC
Education
Pacific Coast University Vancouver, BC
Bachelor of Science, Honours Biology (Co-op) Expected: May 2027
Relevant Coursework: Molecular Biology, Genetics, Biochemistry, Biostatistics
Experience
Northshore Therapeutics Vancouver, BC
Research Assistant Co-op, Discovery Biology Jan 2026 – Aug 2026
• Ran qPCR and ELISA assays on patient-derived cell lines and maintained cell culture with aseptic technique.
• Performed Western blots and flow cytometry for target validation, and wrote SOPs for two assays.
Pacific Coast University, Hartley Genomics Lab Vancouver, BC
Undergraduate Research Student May 2025 – Dec 2025
• Built an RNA-seq pipeline in Python and R (DESeq2) for 48 samples and ran differential expression analyses.
• Analyzed single-cell sequencing data with Scanpy and presented the results at lab meetings.
Projects
Variant Calling Workflow | Python, Snakemake, BWA, GATK 2025
• Built a variant calling workflow on public exome data and compared it with published calls.
Skills
Lab: qPCR, ELISA, Western blot, cell culture, flow cytometry, pipetting
Computational: Python, R, Bash, Snakemake, Git
"""

PHARMACY = """SOFIA ALVAREZ
sofia.alvarez@example.com | 555-010-0163 | Toronto, ON
Education
Lakeshore University, Leslie School of Pharmacy Toronto, ON
Doctor of Pharmacy (PharmD) Expected: May 2028
Experience
Maple Pharmaceuticals Canada Mississauga, ON
Regulatory Affairs Co-op Student May 2026 – Dec 2026
• Prepared Health Canada submissions and eCTD modules for two generic products and tracked labelling updates.
• Reviewed product monographs against the reference product and logged change controls.
Medical Information Summer Student May 2025 – Aug 2025
• Answered medical inquiries from pharmacists and physicians using literature searches and product monographs.
• Logged adverse events for pharmacovigilance review within 24 hours.
Riverside Pharmacy Toronto, ON
Pharmacy Assistant Sep 2023 – Apr 2025
• Entered prescriptions and supported dispensing in a community pharmacy.
Certifications
Standard First Aid and CPR Level C, 2025
"""

BIOMEDICAL = """TAYLOR BROOKS
taylor.brooks@example.com | 555-010-0188 | Kingston, ON
Education
Northfield University Kingston, ON
Bachelor of Applied Science, Biomedical Engineering Expected: Apr 2027
Experience
Cardiosense Medical Toronto, ON
Hardware Engineering Intern May 2026 – Aug 2026
• Designed a PCB for an ECG front end in Altium and wrote STM32 firmware for the biosignal acquisition board.
• Ran verification and validation tests under design controls and ISO 14971 risk management.
Projects
EMG-Controlled Prosthetic Hand | C, STM32 2025
• Built an EMG-driven prosthetic hand controller with embedded firmware and a PID control loop.
"""

RESUMES = {"nursing": NURSING, "biology": BIOLOGY, "pharmacy": PHARMACY}


def latex_lines(text):
    """The resume as pypdf reads a LaTeX PDF of it: ligatures, the en dash and the bullet as font codes."""
    codes = {"ffi": "\x1bi", "fi": "\x1c", "fl": "\x1d", "ff": "\x1b", "–": "\x15", "•": "\x88"}
    lines = text.splitlines()
    for plain, code in codes.items():
        lines = [line.replace(plain, code) for line in lines]
    return lines


def plain_lines(text):
    """The resume in a PDF whose font has no en dash or bullet: hyphens instead."""
    return [line.replace("–", "-").replace("• ", "- ") for line in text.splitlines()]


_RIGHT_SIDE = re.compile(r"^(.*\S)\s+(\w{3} \d{4} – (?:\w{3} \d{4}|Present)|[A-Z][a-z]+, [A-Z]{2})$")


_HEADINGS = {"Education", "Experience", "Clinical Experience", "Volunteer Experience", "Projects", "Certifications", "Skills"}


def word_docx(text, listed=None):
    """The resume as Word saves it: bullets are list numbering, and dates and cities sit at a right tab stop.
    ``listed``: headings, education lines and dated job lines are list items too, and duties have no full stop,
    as many Word resumes are laid out; "nested" puts the duties a level below their job, "flat" beside it."""
    numbering = ('<w:numbering><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/></w:lvl>'
                 '<w:lvl w:ilvl="1"><w:numFmt w:val="bullet"/></w:lvl></w:abstractNum>'
                 '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')
    run = lambda s: f"<w:r><w:t xml:space=\"preserve\">{escape(s)}</w:t></w:r>"
    body, section = [], ""
    for line in text.splitlines():
        section = line if line in _HEADINGS else section
        right = _RIGHT_SIDE.match(line)
        level = None
        if line.startswith("• "):
            line, level = (line[2:].rstrip("."), int(listed == "nested")) if listed else (line[2:], 0)
        elif listed and (line in _HEADINGS or section == "Education" or (right and re.search(r"\d{4}", right[2]))):
            level = 0
        props = (f'<w:numPr><w:ilvl w:val="{level}"/><w:numId w:val="1"/></w:numPr>' if level is not None else "")
        if right and not line.startswith("•"):
            props += '<w:tabs><w:tab w:val="right" w:pos="9360"/></w:tabs>'
            content = f"{run(right[1])}<w:r><w:tab/></w:r>{run(right[2])}"
        else:
            content = run(line)
        body.append(f"<w:p><w:pPr>{props}</w:pPr>{content}</w:p>")
    return docx("".join(body), numbering=numbering)


def keys(parsed):
    return [i["key"] for i in parsed["role_interests"]]


class HealthResumeTests(unittest.TestCase):
    def test_nursing_student_targets_clinical_care(self):
        parsed = parse_resume(NURSING, KN)
        edu = parsed["education"]
        self.assertEqual(("undergraduate", "Nursing", 2027, 4),
                         tuple(edu[k] for k in ("level", "program", "graduation_year", "graduation_month")))
        self.assertEqual(["healthcare.clinical_care"], keys(parsed))
        self.assertEqual(["Nursing Student", "Personal Support Worker (Part-Time)"], [r["title"] for r in parsed["roles"]])
        self.assertLessEqual({"vital_signs", "medication_administration", "patient_care", "bls", "ehr", "infection_control"},
                             {s["key"] for s in parsed["skills"]})
        self.assertEqual(["hospital", "pharmacy_consumer"], parsed["company_types"])

    def test_biology_co_op_targets_lab_research_and_bioinformatics(self):
        parsed = parse_resume(BIOLOGY, KN)
        self.assertEqual(["healthcare.lab_research", "healthcare.bioinformatics"], keys(parsed))
        self.assertIn("title: Research Assistant Co-op, Discovery Biology", parsed["role_interests"][0]["evidence"])
        self.assertLessEqual({"pcr", "elisa", "western_blot", "cell_culture", "flow_cytometry", "python", "r"},
                             {s["key"] for s in parsed["skills"]})
        # Python and statistics in a biology resume don't point at Quant Research or Software.
        self.assertTrue(all(k.startswith("healthcare.") for k in keys(parsed)))

    def test_pharmacy_co_op_targets_regulatory_and_medical_affairs(self):
        parsed = parse_resume(PHARMACY, KN)
        self.assertEqual(["healthcare.regulatory_quality", "healthcare.medical_affairs"], keys(parsed)[:2])
        # A PharmD is neither a PhD nor a master's: no level is guessed.
        self.assertEqual((None, "Pharmacy"), (parsed["education"]["level"], parsed["education"]["program"]))
        self.assertEqual("pharma", parsed["company_types"][0])

    def test_healthcare_degrees(self):
        cases = {"BScN, Lakeshore University": "undergraduate", "Honours BHSc, Health Sciences": "undergraduate",
                 "BKin, Kinesiology": "undergraduate", "Master of Public Health (MPH)": "masters",
                 "MSN, Family Nurse Practitioner": "masters", "Doctor of Medicine (MD)": None,
                 "PhD, Immunology": "phd"}
        for line, level in cases.items():
            with self.subTest(line=line):
                text = f"ALEX DOE\nEducation\nLakeshore University Toronto, ON\n{line} Expected: Apr 2027\n"
                self.assertEqual(level, parse_resume(text, KN)["education"]["level"])

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "install requirements.txt for PDF support")
    def test_pdf_and_latex_pdf_read_as_the_text_does(self):
        for name, text in RESUMES.items():
            want = parse_resume(text, KN)
            for kind, lines in (("pdf", plain_lines(text)), ("latex", latex_lines(text))):
                with self.subTest(resume=name, kind=kind):
                    read = parse_resume(extract_text("resume.pdf", pdf(lines)), KN)
                    self.assertEqual(keys(want), keys(read))
                    self.assertEqual(want["education"]["program"], read["education"]["program"])
                    self.assertEqual({s["key"] for s in want["skills"]}, {s["key"] for s in read["skills"]})

    def test_a_word_docx_reads_as_the_text_does(self):
        for name, text in RESUMES.items():
            want = parse_resume(text, KN)
            for listed in (None, "nested", "flat"):
                with self.subTest(resume=name, listed=listed):
                    read = parse_resume(extract_text("resume.docx", word_docx(text, listed)), KN, wrapped=False)
                    self.assertEqual(want["role_interests"], read["role_interests"])
                    self.assertEqual([(r["title"], r["label"]) for r in want["roles"]],
                                     [(r["title"], r["label"]) for r in read["roles"]])
                    self.assertEqual([(e["company"], e["title"]) for e in want["entries"]],
                                     [(e["company"], e["title"]) for e in read["entries"]])
                    self.assertEqual(want["education"], read["education"])
                    self.assertEqual(want.get("licences"), read.get("licences"))

    def test_a_wrapped_bullet_line_is_no_role(self):
        # A PDF wraps a long bullet; its last line ("nurse.") is the bullet's end, not a job title.
        for end in ("the charge\nnurse.", "the\nICU charge nurse."):
            wrapped = parse_resume(NURSING.replace("the charge nurse.", end), KN)
            self.assertEqual(["Nursing Student", "Personal Support Worker (Part-Time)"], [r["title"] for r in wrapped["roles"]])
        # A title on its own line after an unfinished bullet is still a role.
        titled = parse_resume(NURSING.replace("the charge nurse.", "the charge nurse\nRegistered Nurse"), KN)
        self.assertIn("Registered Nurse", [r["title"] for r in titled["roles"]])

    def test_a_typed_bullet_is_a_duty_or_a_skill(self):
        # Dates don't make a typed bullet a job, nor a heading word a heading.
        want = parse_resume(NURSING, KN)
        for change in (("on a 32-bed unit.\n", "on a 32-bed unit.\n• Shadowed a registered nurse, Jun 2025 – Aug 2025\n"),
                       ("Skills\n", "Skills\n• Leadership\n• Projects\n")):
            with self.subTest(line=change[1].split("\n")[1]):
                read = parse_resume(NURSING.replace(*change), KN)
                self.assertEqual([(e["company"], e["title"]) for e in want["entries"]],
                                 [(e["company"], e["title"]) for e in read["entries"]])
                self.assertEqual(want["licences"], read["licences"])
                self.assertEqual(want["role_interests"], read["role_interests"])

    def test_the_rest_of_a_bullet_or_a_title(self):
        from intel.resume import _goes_on
        nurse = [KN.tracks["healthcare"].role_words]
        for line, rest in [("nurse.", True), ("and charted in Epic.", True), ("the ICU charge nurse.", True),
                           ("lululemon  Data Analyst Intern", False), ("backend developer co-op", False),
                           ("e-Commerce Data Analyst", False), ("iOS Developer", False), ("Acme Inc.", False),
                           ("Registered Nurse", False), ("staff nurse", False)]:
            with self.subTest(line=line):
                self.assertEqual(rest, _goes_on(line, nurse))

    def test_latex_codes_become_text(self):
        text = clean_pdf_text("\n".join(latex_lines(BIOLOGY)))
        for phrase in ("flow cytometry", "differential expression", "Jan 2026 – Aug 2026", "• Ran qPCR"):
            self.assertIn(phrase, text)

    def test_biomedical_engineering_opens_hardware_and_healthcare(self):
        parsed = parse_resume(BIOMEDICAL, KN)
        fields = {k.split(".")[0] for k in keys(parsed)}
        self.assertEqual({"healthcare", "hardware"}, fields)
        self.assertEqual("healthcare.medical_devices", keys(parsed)[0])
        profile = profile_from_resume(parsed, merge_profile(), KN)
        self.assertEqual([], validate_profile(profile, KN))
        self.assertEqual({"healthcare", "hardware"}, set(profile["fields"]))
        self.assertIn("medtech", profile["target_company_types"])


class HealthProfileTests(unittest.TestCase):
    def test_applying_adds_healthcare_and_keeps_chosen_boards(self):
        parsed = parse_resume(NURSING, KN)
        profile = profile_from_resume(parsed, merge_profile(), KN)
        self.assertEqual([], validate_profile(profile, KN))
        # The default profile's Finance targets were implied, not chosen: Healthcare replaces them.
        self.assertEqual(["healthcare"], profile["fields"])
        self.assertEqual(["healthcare.clinical_care"], profile["target_roles"])
        self.assertTrue(all("healthcare" in KN.type_tracks(t) for t in profile["target_company_types"]))
        chosen = profile_from_resume(parsed, merge_profile({"fields": ["finance", "software"]}), KN)
        self.assertEqual(["finance", "software", "healthcare"], chosen["fields"])


class HealthMatchTests(unittest.TestCase):
    def setUp(self):
        self.profile = profile_from_resume(parse_resume(NURSING, KN), merge_profile(), KN)

    def match(self, title, company="Example Health"):
        facts = build_facts({"title": title, "location": "Hamilton, ON", "company": company, "posted": time.time()}, KN)
        return match_resume(facts, self.profile, score_job(facts, self.profile, KN), KN)

    def test_nursing_roles_match_and_other_boards_dont(self):
        # Placed by the board's fallback words (tier 2), not by a filter's: they stay matches.
        for title in ("Registered Nurse - Medicine", "Nursing Student Extern, Summer 2027", "New Grad RN Residency"):
            with self.subTest(title=title):
                self.assertTrue(self.match(title)["matched"], self.match(title))
        result = self.match("2027 Investment Banking Summer Analyst", "RBC")
        self.assertFalse(result["matched"])
        self.assertIn("Finance role is outside the fields you recruit in", result["exclusions"])
        self.assertFalse(self.match("Software Engineer Intern")["matched"])
        self.assertIn("Role doesn't name a field you recruit in", self.match("2027 Summer Internship")["exclusions"])


if __name__ == "__main__":
    unittest.main()
