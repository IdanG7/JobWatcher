"""Healthcare resumes: a nursing, a biology co-op and a pharmacy student's resumes propose Healthcare filters,
skills, employer types and education, read the same as text, a PDF or a LaTeX PDF; a biomedical engineering
resume opens Hardware and Healthcare. Finance and tech resumes are read as before (test_resume_tech.py)."""
import importlib.util
import time
import unittest

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.matching import match_resume
from intel.profile import validate_profile
from intel.resume import clean_pdf_text, extract_text, parse_resume, profile_from_resume
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


def keys(parsed):
    return [i["key"] for i in parsed["role_interests"]]


class HealthResumeTests(unittest.TestCase):
    def test_nursing_student_targets_clinical_care(self):
        parsed = parse_resume(NURSING, KN)
        edu = parsed["education"]
        self.assertEqual(("undergraduate", "Nursing", 2027, 4),
                         tuple(edu[k] for k in ("level", "program", "graduation_year", "graduation_month")))
        self.assertEqual(["healthcare.clinical_care"], keys(parsed))
        self.assertEqual(["Nursing Student", "Personal Support Worker (Part-Time"], [r["title"] for r in parsed["roles"]])
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
