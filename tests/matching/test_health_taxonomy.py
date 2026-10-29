"""Healthcare & Science: its filters, how a title reaches the board, its career levels, employer types and skills
(plans/healthcare-board.md, sections 3 and 4). Finance and the other boards keep what they place."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile, score_job, validate_profile
from intel.facts import build_facts
from intel.seniority import detect_seniority
from intel.skills import extract_skills
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()
RULES = KN.stage_rules["healthcare"]

# Three titles per filter (section 3.1), with the employer type where the title alone doesn't place it.
EXAMPLES = {
    "clinical_care": [("Registered Nurse, Medical-Surgical", "unknown"), ("Pharmacy Intern", "unknown"),
                      ("Physiotherapy Assistant (Summer Student)", "unknown")],
    "clinical_research": [("Clinical Research Coordinator", "unknown"), ("Clinical Research Associate II", "unknown"),
                          ("Clinical Trial Assistant (Co-op)", "unknown")],
    "lab_research": [("Research Associate, Cell Biology", "unknown"), ("Laboratory Technician", "biotech"),
                     ("Co-op Student, Analytical Chemistry", "pharma")],
    "bioinformatics": [("Bioinformatics Scientist", "unknown"), ("Computational Biologist", "unknown"),
                       ("Biostatistician", "unknown")],
    "regulatory_quality": [("Regulatory Affairs Co-op", "pharma"), ("Quality Assurance Specialist, GMP", "unknown"),
                           ("Pharmacovigilance Associate", "unknown")],
    "medical_devices": [("Biomedical Engineering Intern", "unknown"), ("R&D Engineer, Medical Devices", "unknown"),
                        ("Field Clinical Engineer", "unknown")],
    "public_health": [("Epidemiologist", "unknown"), ("Health Promotion Specialist", "unknown"),
                      ("Health Policy Analyst", "unknown")],
    "health_admin": [("Patient Access Representative", "unknown"), ("Health Information Management Co-op", "unknown"),
                     ("Hospital Administration Intern", "unknown")],
    "medical_affairs": [("Medical Science Liaison", "unknown"), ("Market Access Analyst", "unknown"),
                        ("Pharmaceutical Sales Representative", "unknown")],
}
LAB = ("You will run qPCR and ELISA assays, maintain cell culture and record results in the laboratory notebook.")


def cls(title, description="", company_type="unknown", department=""):
    return classify(title, KN, description, department, company_type)


def board(result):
    return "finance" if result["is_finance"] else result["family"]


def level(title, description="", rules=RULES):
    return detect_seniority(title, description, board_rules=rules)


class FilterTests(unittest.TestCase):
    def test_every_filter_places_its_example_titles(self):
        for sub, titles in EXAMPLES.items():
            for title, ctype in titles:
                result = cls(title, company_type=ctype)
                self.assertEqual(("healthcare", sub), (board(result), result["subcategory"]), (title, result["evidence"]))

    def test_the_family_tree_lists_the_nine_filters_with_notes(self):
        tree = {f["key"]: f for f in KN.family_tree()}["healthcare"]
        self.assertEqual(list(EXAMPLES), [s["key"] for s in tree["subcategories"]])
        self.assertTrue(all(s["note"] for s in tree["subcategories"]))
        self.assertEqual("healthcare", tree["track"])
        self.assertEqual("Lab Research", KN.subcategory_label("healthcare", "lab_research"))

    def test_related_filters_earn_the_related_credit(self):
        profile = {"fields": ["healthcare"], "target_roles": ["healthcare.clinical_research", "healthcare.lab_research"]}
        self.assertEqual([], validate_profile(merge_profile(profile), KN))

        def role(title):
            result = analyze({"title": title, "company": "Acme", "posted": NOW - 3600}, profile, KN, now=NOW)
            return {s["key"]: s for s in result["subscores"]}["role"]["points"]
        self.assertEqual(25, role("Clinical Research Coordinator"))
        self.assertEqual(14, role("Regulatory Affairs Specialist, Medical Devices"))   # related to Clinical Research
        self.assertEqual(14, role("Bioinformatics Scientist"))                         # related to Lab Research
        self.assertEqual(9, role("Medical Science Liaison"))


class PlacementTests(unittest.TestCase):
    def assertBoard(self, expected, title, **kw):
        result = cls(title, **kw)
        self.assertEqual(expected, board(result), (title, result["evidence"]))
        return result

    def test_tier_one_titles_stay_on_the_board_they_had(self):
        self.assertBoard("healthcare", "Software Engineer, Medical Imaging")
        self.assertBoard("data_ml", "Data Scientist, Genomics")
        self.assertBoard("software", "Statistical Programmer")
        self.assertBoard("data_ml", "Research Scientist")

    def test_fallback_words_place_only_titles_no_board_placed(self):
        for title in ("Registered Nurse", "RPN - Long Term Care, Nights", "Phlebotomist", "Epidemiologist",
                      "Patient Access Representative", "Dental Hygienist"):
            result = self.assertBoard("healthcare", title)
            self.assertNotIn("rule", result)
        for expected, title in (("people_legal", "Nurse Recruiter"), ("software", "Software Engineer, Nurse Scheduling"),
                                ("other", "AI Scientist"), ("other", "Account Director, Life Sciences"),
                                ("other", "Health and Safety Coordinator"),
                                ("other", "Health, Safety and Environment (HSE) Manager"),
                                ("other", "Industrial Hygienist"), ("other", "Radiological Control Technician"),
                                ("other", "Vice President, Regulatory Affairs"), ("other", "Admissions Counselor")):
            self.assertBoard(expected, title)

    def test_lab_and_science_words_need_life_science_evidence(self):
        for title in ("Laboratory Technician", "Scientist", "Postdoctoral Researcher - Quantum Devices", "Chemist",
                      "Research Assistant"):
            self.assertBoard("other", title)
            self.assertBoard("other", title, company_type="semiconductors")
        self.assertBoard("healthcare", "Laboratory Technician", company_type="diagnostics")
        self.assertBoard("healthcare", "Research Assistant", description=LAB)
        self.assertBoard("healthcare", "Scientist I, Analytical Development")
        self.assertBoard("healthcare", "Regulatory Affairs Specialist", company_type="medtech")
        self.assertBoard("other", "PhD Research Intern, Quantum and AI for Chemistry", company_type="university")

    def test_finance_is_decided_first(self):
        for title, category in (("Healthcare Investment Banking Analyst", "investment_banking"),
                                ("Actuarial Analyst, Health Insurance", "insurance"),
                                ("Biostatistician, Quantitative Epidemiology", "quant"),
                                ("Summer 2027 AHN Physician Org Undergraduate Finance Intern", "corporate_finance"),
                                ("Equity Research Associate - Biotechnology", "public_markets"),
                                ("Research Associate, Healthcare Equity Research", "public_markets"),
                                ("Research Associate I", "public_markets")):
            self.assertEqual(category, self.assertBoard("finance", title)["category"], title)

    def test_a_pay_line_in_the_title_is_no_finance_word(self):
        # Vanderbilt and Boston Medical Center name the pay in the title; 'Rates' there isn't Fixed Income.
        for title in ("Licensed Practical Nurse - Adult Urology - Cool Springs (**New Rates**)",
                      "Licensed Practical Nurse PRN - Neurology Clinic - (!!New Rates!!)"):
            self.assertBoard("healthcare", title, company_type="hospital")
        for title in ("CT Technologist (24 Hours, Evenings/Nights) Enhanced Rates and 15k Sign-On Bonus!",
                      "MRI Tech-Per Diem, Enhanced Pay Rates",
                      "Lead Cat Scan Technologist $15K sign-on bonus and new higher rates"):
            self.assertFalse(cls(title, company_type="hospital")["is_finance"], title)
        self.assertFalse(cls("Heat Treat Operator – 1st Shift – Pay Rate: $21.00/hour")["is_finance"])
        for title in ("Rates Trader", "Associate, Rates Structuring", "Summer Analyst - Rates",
                      "Interest Rates Sales - Vice President", "Emerging Markets Rates Strategist"):
            self.assertEqual("fixed_income", self.assertBoard("finance", title)["subcategory"], title)

    def test_life_science_research_titles_leave_equity_research(self):
        # D1: 'research associate' is Equity Research's title word too.
        for title, kw in (("Research Associate, Cell Biology", {}), ("Clinical Research Associate II", {}),
                          ("Postdoctoral Research Associate - Oncology", {}),
                          ("Research Associate I", {"company_type": "health_tech"}),
                          ("Research Associate", {"description": LAB})):
            result = self.assertBoard("healthcare", title, **kw)
            self.assertEqual("life_science_research", result["rule"])
            self.assertEqual([], result["secondary"])
        # A posting that reads as finance keeps Finance, even with lab words in its prose.
        self.assertBoard("finance", "Research Associate", description=LAB + " Build earnings models and write research "
                         "reports that initiate coverage of the sector.")
        self.assertBoard("finance", "Research Associate I", company_type="hedge_fund")
        # Words that also name materials and physics work are no evidence: an aerospace inspection posting.
        self.assertBoard("finance", "Research Associate – Non-Destructive Evaluation (NDE)", company_type="defense_tech",
                         description="Inspect spacecraft parts by acoustic microscopy and thermography. Record results "
                                     "for materials and specimens. Physical Sciences Laboratories supports the mission.")

    def test_clinical_occupations_and_lab_quality_leave_topic_boards(self):
        # D2: the occupation beats a topic word ('Backend' is the back-end pharmacy, 'Mobile' the city).
        for title, rule, sub in (("Pharmacy Technician Backend-PT", "clinical_occupation", "clinical_care"),
                                 ("Registered Nurse- AL Hospice Care Mobile", "clinical_occupation", "clinical_care"),
                                 ("Personal Support Worker - Casual", "clinical_occupation", "clinical_care"),
                                 ("Quality Control Microbiologist", "lab_quality", "regulatory_quality"),
                                 ("Health Policy Analyst", "health_policy", "public_health")):
            result = self.assertBoard("healthcare", title)
            self.assertEqual((rule, sub), (result["rule"], result["subcategory"]), title)
        self.assertBoard("operations", "Quality Assurance Intern")
        self.assertBoard("operations", "Quality Assurance Lab Manager")
        self.assertBoard("software", "QA Engineer")
        self.assertBoard("people_legal", "Policy Analyst")

    def test_healthcare_employer_types_never_make_a_role_finance(self):
        for ctype in ("hospital", "pharma", "biotech", "medtech", "cro_cdmo", "payer", "university"):
            self.assertFalse(cls("Summer Analyst", company_type=ctype)["is_finance"], ctype)
            self.assertTrue(cls("Investment Banking Summer Analyst", company_type=ctype)["is_finance"], ctype)

    def test_an_employer_type_leans_a_filter_but_names_none_alone(self):
        trials = "Support our clinical trials and the informed consent process."
        self.assertIsNone(cls("Clinical Coordinator", trials)["subcategory"])
        result = cls("Clinical Coordinator", trials, company_type="cro_cdmo")
        self.assertEqual("clinical_research", result["subcategory"])
        self.assertIn("employer type: cro_cdmo", result["evidence"])
        self.assertIsNone(cls("Clinical Coordinator", company_type="cro_cdmo")["subcategory"])


class LevelTests(unittest.TestCase):
    def test_healthcare_levels_map_onto_the_five_stages(self):
        for title, lvl, stage, label in (
                ("Summer 2027 Nurse Extern Program", "extern", "internship", "Extern"),
                ("Summer Student, Research", "summer_student", "internship", "Summer Student"),
                ("Nursing Student - Undergraduate Nursing Employee (UNE)", "student_worker", "internship", "Student Worker"),
                ("New Grad RN Residency Program", "new_grad_program", "new_grad", "New Grad Program"),
                ("Graduate Nurse - ICU", "new_grad_program", "new_grad", "New Grad Program"),
                ("PGY1 Pharmacy Resident", "residency", "new_grad", "Residency"),
                ("Dietetic Internship", "residency", "new_grad", "Residency"),
                ("Post-PharmD Industry Fellowship, Regulatory", "fellowship", "new_grad", "Fellowship"),
                ("Postdoctoral Fellow, Immunology", "postdoc", "new_grad", "Postdoc")):
            result = level(title)
            self.assertEqual((lvl, stage, label, True),
                             (result["level"], result["stage"], result["level_label"], result.get("board_level")), title)

    def test_words_with_other_meanings_are_not_levels(self):
        self.assertNotEqual("residency", level("Resident Care Aide")["level"])
        self.assertNotEqual("residency", level("Resident Assistant, Long-Term Care")["level"])
        self.assertEqual("senior", level("Senior Research Fellow")["stage"])
        self.assertNotIn(level("Registered Nurse - 12 Hour Rotating Shifts")["level"], ("rotational", "residency"))
        rotations = level("Registered Nurse", "Supervise students on clinical rotations; preceptor experience preferred.")
        self.assertEqual("entry_to_practice", rotations["level"])
        self.assertNotEqual("extern", level("External Relations Coordinator")["level"])

    def test_board_levels_are_read_only_on_their_board(self):
        for title in ("Summer Student, Research", "Postdoctoral Fellow", "Registered Nurse"):
            self.assertNotIn("board_level", detect_seniority(title))
        self.assertEqual(("unspecified", "experienced"),
                         (detect_seniority("Registered Nurse")["level"], detect_seniority("Registered Nurse")["stage"]))
        ai = build_facts({"title": "AI Resident", "company": "Acme"}, KN)
        self.assertEqual(("data_ml", None), (ai["classification"]["family"], ai["seniority"].get("board_level")))
        finance = build_facts({"title": "Research Associate I", "company": "Acme Capital"}, KN)
        self.assertNotIn("board_level", finance["seniority"])

    def test_licensed_entry_to_practice_roles_read_as_entry(self):
        # D14: the licence is the level; years asked still decide.
        for title in ("Registered Nurse", "RPN - Long Term Care", "Pharmacist", "Pharmacy Technician",
                      "Respiratory Therapist", "Personal Support Worker", "Medical Laboratory Technologist"):
            result = level(title)
            self.assertEqual(("entry", "entry_to_practice", "Entry to practice"),
                             (result["stage"], result["level"], result["level_label"]), title)
        self.assertEqual("experienced", level("Registered Nurse", "Requires 3+ years of experience in acute care.")["stage"])
        self.assertEqual("senior", level("Pharmacist", "Minimum 5 years of experience as a pharmacist.")["stage"])
        for title in ("Nurse Practitioner", "Physician", "Charge Nurse, ICU", "Clinical Nurse Specialist",
                      "Registered Nurse II", "Nurse Manager", "RN Case Manager"):
            self.assertNotEqual("entry_to_practice", level(title)["level"], title)

    def test_an_entry_to_practice_posting_scores_as_entry_level_for_a_student(self):
        profile = merge_profile({"fields": ["healthcare"], "target_roles": ["healthcare.clinical_care"],
                                 "target_stages": ["new_grad", "entry"]})
        result = analyze({"title": "Registered Nurse", "company": "Acme", "posted": NOW - 3600}, profile, KN, now=NOW)
        stage = {s["key"]: s for s in result["subscores"]}["stage"]
        self.assertEqual((20, "Entry to practice — target career stage"), (stage["points"], stage["detail"]))
        self.assertNotIn("experienced", {p["key"] for p in result["penalties"]})
        intern = merge_profile({"fields": ["healthcare"], "target_stages": ["internship", "new_grad"]})
        stage = {s["key"]: s for s in analyze({"title": "Registered Nurse", "company": "Acme"}, intern, KN,
                                              now=NOW)["subscores"]}["stage"]
        self.assertEqual((16, "Entry to practice — entry level"), (stage["points"], stage["detail"]))

    def test_healthcare_levels_carry_their_badge(self):
        facts = build_facts({"title": "PGY1 Pharmacy Resident", "company": "Acme"}, KN)
        self.assertIn("RESIDENCY", score_job(facts, merge_profile({"fields": ["healthcare"]}), KN, {}, NOW)["badges"])
        facts = build_facts({"title": "Software Engineer Intern", "company": "Acme"}, KN)
        self.assertNotIn("INTERN", score_job(facts, merge_profile({"fields": ["software"]}), KN, {}, NOW)["badges"])


class EmployerAndSkillTests(unittest.TestCase):
    def test_healthcare_types_are_on_the_healthcare_track_only(self):
        for ctype in ("hospital", "pharma", "biotech", "medtech", "cro_cdmo", "diagnostics", "payer",
                      "public_health_agency", "health_consulting", "university", "pharmacy_consumer"):
            self.assertEqual(["healthcare"], KN.type_tracks(ctype), ctype)
        self.assertEqual(["tech", "healthcare"], KN.type_tracks("research_lab"))
        self.assertEqual(["tech", "healthcare"], KN.type_tracks("health_tech"))
        self.assertEqual(["finance"], KN.type_tracks("insurance"))                        # D5: payer is apart
        for ctype, priors in KN.company_priors.items():
            if ctype in KN.board_employer_types["healthcare"]:
                self.assertTrue(all(k.startswith("healthcare.") for k in priors), ctype)
        for key in KN.board_employer_types["healthcare"]:
            self.assertIn(key, KN.company_types)

    def test_a_health_tech_employer_counts_for_healthcare_profiles(self):
        # D4: 7 points for a profile with Healthcare; Finance-only and tech profiles score as before.
        facts = build_facts({"title": "Registered Nurse", "company": "Acme"}, KN)
        facts["company"] = {**facts["company"], "type": "health_tech", "type_label": "Health Tech", "known": True}

        def company(profile):
            subs = {s["key"]: s for s in score_job(facts, merge_profile(profile), KN, {}, NOW)["subscores"]}
            return subs["company"]["points"], subs["company"]["detail"]
        self.assertEqual((7, "Health Tech — recognized healthcare and science employer"), company({"fields": ["healthcare"]}))
        self.assertEqual((7, "Health Tech — recognized healthcare and science employer"),
                         company({"fields": ["finance", "healthcare"]}))
        self.assertEqual((7, "Health Tech — recognized tech employer"), company({"fields": ["software", "healthcare"]}))
        self.assertEqual((4, "Health Tech — outside finance"), company({"fields": ["finance"]}))
        facts["company"] = {**facts["company"], "type": "hospital", "type_label": "Hospital & Health System"}
        self.assertEqual((4, "Hospital & Health System — outside finance"), company({"fields": ["software"]}))

    def test_healthcare_skills_are_read_only_on_the_healthcare_board(self):
        # D9: tech skills are read from Healthcare postings as before; healthcare skills only there.
        text = "Run qPCR and ELISA assays under GMP. Python and SQL for analysis."
        health = {s["key"] for s in extract_skills(text, KN, tracks=KN.skill_tracks("healthcare"))}
        self.assertTrue({"pcr", "elisa", "gmp", "python"} <= health, health)
        for placed in ("finance", "software", "other"):
            skills = {s["key"] for s in extract_skills(text, KN, tracks=KN.skill_tracks(placed))}
            self.assertFalse({"pcr", "elisa", "gmp"} & skills, placed)
        self.assertEqual(frozenset({"tech", "healthcare"}), KN.skill_tracks("healthcare"))
        self.assertEqual(frozenset({"tech"}), KN.skill_tracks("software"))

    def test_the_healthcare_board_offers_its_skill_groups(self):
        groups = {f["key"]: f["skill_groups"] for f in KN.family_tree()}["healthcare"]
        self.assertTrue({"clinical", "lab", "regulatory", "health_data"} <= set(groups))
        self.assertTrue(set(groups) <= set(KN.skill_groups))


if __name__ == "__main__":
    unittest.main()
