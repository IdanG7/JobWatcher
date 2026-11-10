"""Architecture, Engineering & Construction: its six filters, the claims by which it takes titles at AEC employers,
the titles it leaves to other boards, its levels, licences and Calendar dates (plans/aec-board.md sections 2 to 5 and 9;
decisions D1 to D8). Finance keeps its titles apart from the 25 construction postings D1 moves."""
import time
import unittest

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.companies import resolve_company, slug
from intel.programs import program_windows
from intel.seniority import detect_seniority
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()

# Titles per filter, with the employer type where they show up.
EXAMPLES = {
    "architecture": [("Architectural Designer", "architecture_firm"), ("Junior Architect", "engineering_consultancy"),
                     ("Intern Architect", "architecture_firm"), ("Architecture Intern - Summer 2027", "architecture_firm"),
                     ("BIM Coordinator", "unknown"), ("Project Architect", "architecture_firm"),
                     ("Interior Designer", "architecture_firm")],
    "structural": [("Structural EIT", "unknown"), ("Senior Structural Engineer, P.Eng.", "engineering_consultancy"),
                   ("Bridge Engineer", "unknown"), ("Structural Engineer - Buildings", "unknown")],
    "civil": [("Civil Engineering Co-op (Winter 2027)", "unknown"), ("Water Resources Engineer", "unknown"),
              ("Transportation Planner", "unknown"), ("Geotechnical Engineer", "unknown"),
              ("Civil Engineer - Land Development", "unknown"), ("Municipal Engineering Student", "unknown")],
    "building_systems": [("MEP Engineering Intern", "unknown"), ("Mechanical Engineer - Buildings", "engineering_consultancy"),
                         ("Electrical Engineer", "engineering_consultancy"), ("Commissioning Agent", "unknown"),
                         ("Fire Protection Engineering Intern", "defense_tech"), ("Plumbing Designer", "engineering_consultancy"),
                         ("HVAC Applications Engineer", "building_systems")],
    "building_science": [("Building Envelope Consultant", "unknown"), ("Energy Modeller", "unknown"),
                         ("Building Science Co-op", "unknown")],
    "construction": [("Construction Project Manager", "contractor"), ("Superintendent", "contractor"),
                     ("Estimator", "contractor"), ("Field Engineer", "contractor"), ("Project Coordinator", "contractor"),
                     ("Assistant Superintendent", "contractor"), ("Construction Engineering Co-op", "unknown"),
                     ("Data Center Construction Manager", "big_tech"), ("Project Scheduler", "contractor"),
                     ("Cost Estimator", "engineering_consultancy")],
}

# Titles other boards (or none) keep, with the employer type: the guards sections 3 and 4 name.
ELSEWHERE = [
    ("Software Engineer, Construction Tech", "unknown", "software"), ("Solutions Architect", "enterprise_saas", "software"),
    ("Field Engineer", "enterprise_saas", "software"), ("Project Engineer", "medtech", "software"),
    ("Cloud Architect", "engineering_consultancy", "software"), ("Data Engineer", "engineering_consultancy", "data_ml"),
    ("Network Engineer", "contractor", "software"), ("Software Engineer", "building_systems", "software"),
    ("Manufacturing Engineer", "building_systems", "hardware"), ("Graphic Designer", "architecture_firm", "design"),
    ("UX Designer", "engineering_consultancy", "design"), ("Recruiter", "engineering_consultancy", "people_legal"),
    ("Sales Engineer", "building_systems", "sales"), ("Supply Chain Coordinator", "engineering_consultancy", "operations"),
    # D3: power and utility work stays on Hardware.
    ("Electrical Engineer in Training - Substations", "unknown", "hardware"),
    # Not building work: aerospace structures, IT architects in French, trades, security, records, auto body shops.
    ("Structural Analysis Co-op", "defense_tech", "other"), ("Architecture Intern", "semiconductors", "other"),
    ("Architecte de solutions", "big_tech", "other"), ("Architecte logiciel", "unknown", "other"),
    ("HVAC Technician", "building_systems", "other"), ("Line Foreman", "unknown", "other"),
    ("EHS Manager", "owner_developer", "other"), ("Site Security Officer", "owner_developer", "other"),
    ("Civil Registry Associate", "enterprise_saas", "other"), ("Civil Rights Investigator", "unknown", "other"),
    ("Construction Surveillance Technician (CST) I - 24/7", "defense_tech", "other"),
    ("Project Scheduler", "defense_tech", "other"), ("Collision Estimator", "big_tech", "other"),
    ("Auto Damage Estimator-Supplement Writer", "insurance", "other"), ("Cost Estimator (Remote)", "defense_tech", "other"),
    ("Material Estimator, Specialist", "defense_tech", "other"),
    # D8: a bare structural engineer at an unknown or aerospace employer stays where it was.
    ("Structural Engineer", "unknown", "other"), ("Structural Engineer", "defense_tech", "other"),
]


def cls(title, company_type="unknown", description=""):
    return classify(title, KN, description, "", company_type)


def board(result):
    return "finance" if result["is_finance"] else result["family"]


def stage(title, company_type="unknown"):
    c = cls(title, company_type)
    return detect_seniority(title, "", c["associate_stage"], c["category"], KN.stage_rules.get(board(c)))["stage"]


class FilterTests(unittest.TestCase):
    def test_the_board_has_six_filters_in_order(self):
        tree = {f["key"]: f for f in KN.family_tree()}["aec"]
        self.assertEqual("Architecture, Engineering & Construction", tree["label"])
        self.assertEqual(["architecture", "structural", "civil", "building_systems", "building_science", "construction"],
                         [s["key"] for s in tree["subcategories"]])

    def test_every_filter_places_its_example_titles(self):
        for sub, titles in EXAMPLES.items():
            for title, company_type in titles:
                with self.subTest(title=title, company_type=company_type):
                    result = cls(title, company_type)
                    self.assertEqual(("aec", sub), (board(result), result["subcategory"]), result["evidence"])

    def test_a_structural_co_op_needs_a_building_employer_or_building_work(self):
        # Aerospace structures co-ops are common (RTX), so the title alone stays where it was.
        self.assertEqual("other", board(cls("Structural Engineering Co-op")))
        self.assertEqual(("aec", "structural"), (board(r := cls("Structural Engineering Co-op", "engineering_consultancy")),
                                                 r["subcategory"]))
        work = "Design concrete and steel framing in ETABS and Revit, review shop drawings and RFIs, to the building code."
        self.assertEqual("aec", board(cls("Structural Engineering Co-op", description=work)))


class ClaimTests(unittest.TestCase):
    def test_plain_titles_at_aec_employers_come_to_the_board(self):
        for title, company_type, rule in (("Engineer I", "engineering_consultancy", "engineer_at_aec_firm"),
                                          ("Project Manager", "contractor", "aec_role_at_firm"),
                                          ("Associate", "architecture_firm", "aec_role_at_firm"),
                                          ("Designer", "architecture_firm", "designer_at_aec_firm"),
                                          ("Controls Project Engineer", "building_systems", "building_systems_maker")):
            with self.subTest(title=title):
                result = cls(title, company_type)
                self.assertEqual(("aec", rule), (board(result), result["rule"]))

    def test_process_work_at_an_aec_firm_is_on_the_board_without_a_filter(self):
        # D4: process, mining and power-plant engineering at AEC firms.
        result = cls("Process Engineer", "engineering_consultancy")
        self.assertEqual(("aec", None), (board(result), result["subcategory"]))

    def test_other_boards_keep_their_titles(self):
        for title, company_type, expected in ELSEWHERE:
            with self.subTest(title=title, company_type=company_type):
                self.assertEqual(expected, board(cls(title, company_type)))


class FinanceTests(unittest.TestCase):
    def test_construction_work_finance_placed_moves_to_the_board(self):
        # D1: 25 sample postings, all construction management at banks, tech and research employers.
        for title, company_type in (("Project Controls, Vice President, Construction Management", "bulge_bracket"),
                                    ("Construction Quality Manager", "big_tech"),
                                    ("Senior Construction Project Manager", "unknown")):
            with self.subTest(title=title):
                self.assertEqual(("aec", "construction"), (board(r := cls(title, company_type)), r["subcategory"]))

    def test_finance_keeps_lending_real_estate_infrastructure_and_accounting(self):
        for title, company_type in (("Construction Loan Officer", "commercial_bank"), ("Real Estate Analyst", "private_equity"),
                                    ("Infrastructure Investment Associate", "asset_manager"),
                                    ("Project Finance Analyst", "engineering_consultancy"), ("Accountant", "contractor"),
                                    ("Construction Accountant", "contractor")):
            with self.subTest(title=title):
                self.assertEqual("finance", board(cls(title, company_type)))


class LevelTests(unittest.TestCase):
    def test_the_boards_own_levels(self):
        for title, company_type, expected in (
                ("Architecture Intern - Summer 2027", "architecture_firm", "internship"),
                ("Civil Engineering Co-op (Winter 2027)", "unknown", "internship"),
                ("Intern Architect", "architecture_firm", "entry"), ("Structural EIT", "unknown", "entry"),
                ("Engineer I", "engineering_consultancy", "entry"), ("Field Engineer", "contractor", "entry"),
                ("Project Coordinator", "contractor", "entry"),
                ("Assistant Superintendent", "contractor", "experienced"), ("Superintendent", "contractor", "experienced"),
                ("Construction Project Manager", "contractor", "experienced"), ("Estimator", "contractor", "experienced"),
                ("Associate", "architecture_firm", "senior"), ("Senior Structural Engineer, P.Eng.", "engineering_consultancy", "senior"),
                ("Senior Construction Project Manager", "unknown", "senior")):
            with self.subTest(title=title):
                self.assertEqual(expected, stage(title, company_type))


def facts(title, description="", company="Example Engineering Ltd."):
    return build_facts({"title": title, "description": description, "company": company, "posted": NOW}, KN)


class LicenceTests(unittest.TestCase):
    def test_a_posting_asks_for_a_licence_by_title_or_registration(self):
        for title, description, expected in (
                ("Structural Engineer, P.Eng.", "Design buildings and bridges.", {"required": ["peng"]}),
                ("Senior Civil Engineer, PE", "Design buildings and bridges.", {"required": ["peng"]}),
                ("Mechanical Engineer - Buildings", "Professional Engineer (PE) license required.", {"required": ["peng"]}),
                ("Mechanical Engineer - Buildings", "Registered with PEO as a P.Eng.", {"required": ["peng"]}),
                ("Structural Engineer in Training (EIT)", "Eligible for registration as an EIT with PEO.",
                 {"required": ["eit"], "pending_ok": True}),
                ("Project Architect", "Licensed architect (OAA) required. LEED AP an asset.",
                 {"required": ["architect"], "certifications": ["leed"]}),
                ("Construction Project Manager", "PMP certification required. Gold Seal certification an asset.",
                 {"certifications": ["pmp", "gold_seal"]})):
            with self.subTest(title=title, description=description):
                self.assertEqual(expected, facts(title, description)["licences"])

    def test_a_preferred_licence_or_a_student_role_asks_for_none(self):
        self.assertEqual({}, facts("Mechanical Engineer - Buildings", "Professional Engineer (PE) license preferred.")["licences"])
        self.assertEqual({}, facts("Civil Engineering Co-op, Winter 2027", "Enrolled in civil engineering.")["licences"])

    def test_other_boards_postings_read_no_aec_licence(self):
        self.assertNotIn("licences", facts("Software Engineer", "PMP certification required."))

    def test_a_licence_the_profile_does_not_hold_costs_fit(self):
        posting = facts("Structural Engineer, P.Eng.", "Design buildings and bridges. P.Eng. designation required.")
        profile = merge_profile({"fields": ["aec"], "target_roles": ["aec.structural"]})
        penalty = lambda p: next((x for x in score_job(posting, p, KN)["penalties"] if x["key"] == "licence"), None)
        self.assertIsNotNone(penalty(profile))
        self.assertIsNone(penalty({**profile, "licences": ["peng"]}))


class ProgramWindowTests(unittest.TestCase):
    def windows(self, profile):
        return [(i["date"], i["key"]) for i in program_windows(merge_profile(profile), KN, "2026-09-01", "2027-08-31")]

    def test_the_board_sees_its_co_op_internship_and_new_grad_dates(self):
        self.assertEqual([("2026-09-15", "coop_winter"), ("2027-01-10", "coop_summer"), ("2027-05-15", "coop_fall"),
                          ("2026-09-01", "us_summer_internships"), ("2026-09-15", "new_grad"), ("2027-05-01", "eit_application")],
                         self.windows({"fields": ["aec"], "target_roles": ["aec"]}))
        self.assertTrue(all("typically" in i["title"] for i in program_windows(
            merge_profile({"fields": ["aec"]}), KN, "2026-09-01", "2027-08-31")))

    def test_the_eit_application_follows_graduation_for_an_eit_profile(self):
        student = {"fields": ["aec"], "target_roles": ["aec.structural"], "graduation_year": 2027, "graduation_month": 4}
        self.assertNotIn("eit_application", [k for _, k in self.windows(student)])
        self.assertIn(("2027-04-01", "eit_application"), self.windows({**student, "licences": ["eit"]}))

    def test_other_boards_see_none_of_them(self):
        self.assertEqual([], self.windows({"fields": ["software"], "target_roles": ["software"]}))


class EmployerTests(unittest.TestCase):
    def test_aec_employers_carry_the_boards_types(self):
        for key, kind in (("stantec", "engineering_consultancy"), ("pcl_construction", "contractor"), ("turner_construction", "contractor"),
                          ("atkinsr_alis", "engineering_consultancy"), ("arup", "engineering_consultancy")):
            with self.subTest(key):
                self.assertEqual(kind, KN.companies[key].type)
                self.assertEqual(["aec"], KN.type_tracks(kind))

    def test_a_new_employer_keeps_the_key_its_postings_had(self):
        # Keyed by the slug stored postings resolve to, so no company or cluster key moves: "AtkinsRéalis" slugs to
        # atkinsr_alis, and each spelling of Carrier, GFT, JLL and WSP that postings use has its own entry.
        for name, key in (("AtkinsRéalis", "atkinsr_alis"), ("Carrier Global", "carrier_global"), ("Carrier", "carrier"),
                          ("Gannett Fleming", "gannett_fleming"), ("Jones Lang LaSalle", "jones_lang_lasalle"),
                          ("JLL", "jll"), ("WSP in Canada", "wsp_in_canada"), ("WSP", "wsp"),
                          ("Syska Hennessy Group", "syska_hennessy_group")):
            with self.subTest(name):
                self.assertEqual(key, resolve_company(name, KN)["key"])
                self.assertEqual(key, slug(name))

    def test_the_boards_six_types_belong_to_its_track_only(self):
        types = {k for k in KN.company_types if k != "unknown" and KN.type_tracks(k) == ["aec"]}
        self.assertEqual({"engineering_consultancy", "architecture_firm", "contractor", "owner_developer",
                          "building_systems", "public_infrastructure"}, types)


if __name__ == "__main__":
    unittest.main()
