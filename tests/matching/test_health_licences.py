"""Licences and certifications (plans/healthcare-board.md, D16): what a Healthcare posting asks for, what a resume
shows, and the fit cost of a licence the profile doesn't hold. Other boards' postings and resumes read none."""
import time
import unittest

from intel import build_facts, load_knowledge, merge_profile, score_job, validate_profile
from intel.resume import parse_resume, profile_from_resume, profile_suggestions
from tests.resume.test_resume_health import BIOLOGY, NURSING, PHARMACY
from tests.resume.test_resume_matching import RESUME as FINANCE_RESUME
from tests.resume.test_resume_tech import MIXED_RESUME

KN = load_knowledge()
NOW = time.time()


def facts(title, description=""):
    return build_facts({"title": title, "description": description, "company": "Example Health", "posted": NOW}, KN)


def licence_penalty(f, profile):
    return next((p for p in score_job(f, profile, KN)["penalties"] if p["key"] == "licence"), None)


class PostingLicenceTests(unittest.TestCase):
    def test_the_title_or_the_registration_asks_for_a_licence(self):
        for title, description, required in [
                ("Registered Nurse - Medicine, Full Time", "Current registration with the College of Nurses of Ontario.", ["rn"]),
                ("Registered Practical Nurse - Long Term Care", "Current RPN registration with CNO.", ["rpn"]),
                ("Staff Pharmacist", "Registered with the Ontario College of Pharmacists (Part A pharmacist).", ["pharmacist"]),
                ("Medical Laboratory Technologist - Microbiology", "CSMLS certification and CMLTO registration.", ["mlt"]),
                ("Respiratory Therapist", "Registered with the CRTO.", ["respiratory_therapist"])]:
            with self.subTest(title):
                self.assertEqual(facts(title, description)["licences"].get("required"), required)

    def test_certifications_are_listed_apart(self):
        f = facts("Registered Nurse - Medicine", "Current CNO registration. BLS required.")
        self.assertEqual(f["licences"], {"required": ["rn"], "certifications": ["bls"]})
        f = facts("Clinical Research Coordinator", "ACRP CP or SOCRA (CCRP) certification an asset.")
        self.assertEqual(f["licences"], {"certifications": ["clinical_research_certification"]})

    def test_a_student_role_needs_no_licence(self):
        f = facts("Nursing Student Extern, Summer 2027", "Enrolled in a BScN program. Current BLS for healthcare providers.")
        self.assertEqual(f["licences"], {"certifications": ["bls"]})

    def test_pending_registration_is_noted(self):
        f = facts("New Grad RN Residency 2027", "Graduate nurses eligible for registration with the CNO are welcome.")
        self.assertEqual(f["licences"], {"required": ["rn"], "pending_ok": True})

    def test_a_preferred_licence_or_a_billing_term_is_not_required(self):
        self.assertEqual(facts("Pharmacy Technician", "Registered Pharmacy Technician preferred.")["licences"], {})
        self.assertEqual(facts("Patient Access Representative", "Verify Medicare Part A and Part B coverage.")["licences"], {})

    def test_a_job_family_line_asks_for_nothing(self):
        # Elevance's pharmacy technician postings end with their family's name, which names pharmacists.
        family = "\nJob Level:\nNon-Management Non-Exempt\nJob Family:\nMED > Licensed/Registered Pharmacist/Pharmacy Technician"
        self.assertEqual(facts("Pharmacy Technician I", "Inputs data for the pharmacists." + family)["licences"], {})
        self.assertEqual(facts("Pharmacy Technician I", "Job Family: MED > Licensed/Registered Pharmacist")["licences"], {})
        self.assertEqual(facts("Pharmacy Technician", "Requirements:\nCertified Pharmacy Technician (CPhT)." + family)["licences"],
                         {"required": ["pharmacy_technician"]})

    def test_a_bonus_or_a_licence_for_some_cases_is_not_required(self):
        # Oscar's NP and PA postings: "Bonus Points:" lists a compact RN licence for APRNs only.
        bonus = "Requirements:\n• Licensed in a minimum of 2 core Oscar States\n\nBonus Points:\n• Compact RN license\n• Remote monitoring"
        self.assertNotIn("rn", facts("Physician Assistant - Virtual Health Assessment", bonus)["licences"].get("required", []))
        self.assertNotIn("rn", facts("Physician Assistant", "Requirements:\n• Compact RN license (if an APRN)")["licences"].get("required", []))
        required = "Requirements:\n• Compact RN license\n\nBonus Points:\n• Spanish"
        self.assertIn("rn", facts("Physician Assistant", required)["licences"]["required"])

    def test_an_emt_title_asks_for_the_paramedic_or_emt_licence(self):
        self.assertEqual(facts("Firefighter EMT")["licences"], {"required": ["paramedic"]})
        self.assertEqual(KN.licence_by_key["paramedic"].label, "Paramedic or EMT")

    def test_other_boards_read_no_licences(self):
        self.assertNotIn("licences", facts("Investment Banking Analyst", "Registered nurse experience a plus."))
        self.assertNotIn("licences", facts("Software Engineer Intern", "BLS certification is a plus."))


class LicenceFitTests(unittest.TestCase):
    RN = ("Registered Nurse - Medicine", "Current CNO registration. BLS required.")

    def test_a_required_licence_the_profile_lacks_costs_fit(self):
        p = licence_penalty(facts(*self.RN), merge_profile())
        self.assertEqual((p["points"], p["detail"]), (-20, "Registered Nurse (RN) required"))
        p = licence_penalty(facts("New Grad RN Residency 2027", "Graduate nurses eligible for registration."), merge_profile())
        self.assertIn("registration is pending", p["detail"])

    def test_held_or_expected_licences_and_certifications_cost_nothing(self):
        self.assertIsNone(licence_penalty(facts(*self.RN), merge_profile({"licences": ["rn"]})))
        f = facts("Nursing Student Extern, Summer 2027", "Current BLS for healthcare providers.")
        self.assertIsNone(licence_penalty(f, merge_profile()))

    def test_any_one_of_several_licences_is_enough(self):
        f = facts("CORE Clinical (LPN or RN) Coordinator", "")
        self.assertEqual(f["licences"]["required"], ["rn", "rpn"])
        self.assertIsNone(licence_penalty(f, merge_profile({"licences": ["rpn"]})))
        self.assertEqual(licence_penalty(f, merge_profile())["detail"],
                         "Registered Nurse (RN) or Registered Practical Nurse (RPN/LPN) required")

    def test_profile_licences_are_validated(self):
        self.assertEqual(validate_profile(merge_profile({"licences": ["rn", "bls"]}), KN), [])
        self.assertIn("unknown licences: cpa", validate_profile(merge_profile({"licences": ["cpa"]}), KN))
        self.assertIn("licences must be a list", validate_profile(merge_profile({"licences": "rn"}), KN))


class ResumeLicenceTests(unittest.TestCase):
    def found(self, text):
        return [(l["key"], l["status"]) for l in parse_resume(text, KN).get("licences", [])]

    def test_a_program_expects_its_licence_and_a_certification_is_held(self):
        self.assertEqual(self.found(NURSING), [("rn", "expected"), ("bls", "held")])
        self.assertEqual(self.found(PHARMACY), [("pharmacist", "expected"), ("bls", "held")])
        self.assertEqual(self.found(BIOLOGY), [])

    def test_a_licensed_job_title_is_held(self):
        text = NURSING.replace("Personal Support Worker (Part-Time)", "Registered Nurse (Casual)")
        self.assertIn(("rn", "held"), self.found(text))

    def test_applying_the_resume_adds_its_licences(self):
        parsed = parse_resume(NURSING, KN)
        self.assertEqual(profile_suggestions(parsed, merge_profile(), KN)["licences"], ["rn", "bls"])
        self.assertNotIn("licences", profile_suggestions(parsed, merge_profile({"licences": ["rn", "bls"]}), KN))
        profile = profile_from_resume(parsed, merge_profile({"licences": ["acls"]}), KN)
        self.assertEqual(profile["licences"], ["acls", "rn", "bls"])
        self.assertIsNone(licence_penalty(facts(*LicenceFitTests.RN), profile))

    def test_finance_and_tech_resumes_read_no_licences(self):
        for text in (FINANCE_RESUME, MIXED_RESUME):
            self.assertNotIn("licences", parse_resume(text, KN))


if __name__ == "__main__":
    unittest.main()
