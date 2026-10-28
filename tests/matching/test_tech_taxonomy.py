"""Tech boards' filters (specialties), tech employer types and how they score.
Finance classification and a Finance-only profile's scores must not move."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile, score_job, validate_profile
from intel.companies import resolve_company, slug
from intel.facts import build_facts
from intel.sources import load_packs
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()

# Three titles per filter (plans/cs-tech-sources.md, section 6).
EXAMPLES = {
    "software": {
        "backend": ["Backend Engineer, Payments", "Software Engineer, API Platform", "Java Developer"],
        "frontend": ["Frontend Engineer", "UI Engineer, Design Systems", "React Developer Intern"],
        "full_stack": ["Full-Stack Engineer", "Software Engineer, Full Stack (New Grad)", "Full Stack Developer Co-op"],
        "mobile": ["iOS Engineer", "Android Developer Intern", "Mobile Engineer, React Native"],
        "infrastructure": ["Site Reliability Engineer", "DevOps Engineer", "Cloud Platform Engineer"],
        "systems": ["Distributed Systems Engineer", "Compiler Engineer", "Database Kernel Engineer"],
        "security": ["Security Engineer, Application Security", "Detection & Response Engineer", "Penetration Tester"],
        "game_dev": ["Gameplay Programmer", "Game Engine Developer", "Graphics Engineer, Rendering"],
        "quant_dev": ["Quantitative Developer", "Software Engineer, Low-Latency Trading", "Trading Systems Developer"],
        "qa_test": ["Software Engineer in Test", "QA Automation Engineer", "Test Developer Co-op"],
    },
    "data_ml": {
        "ml_engineering": ["Machine Learning Engineer", "ML Infrastructure Engineer", "Applied AI Engineer, LLMs"],
        "ai_research": ["Research Scientist, Reinforcement Learning", "Research Engineer, Pretraining", "AI Resident"],
        "data_science": ["Data Scientist, Product", "Decision Scientist", "Data Science Intern, Experimentation"],
        "data_engineering": ["Data Engineer", "Analytics Engineer", "Big Data Developer (Spark)"],
        # 'Analytics Co-op' alone stays unplaced: at a bank it is a finance posting today.
        "analytics": ["Data Analyst", "Business Intelligence Developer", "Data Analytics Co-op, Tableau"],
    },
    "hardware": {
        "embedded_firmware": ["Embedded Software Engineer", "Firmware Engineer Intern", "Embedded Systems Developer (RTOS)"],
        "chip_design": ["ASIC Design Engineer", "Design Verification Engineer", "FPGA Engineer"],
        "electrical": ["Electrical Engineer, Power Electronics", "Hardware Engineer, PCB Design", "Analog Circuit Design Intern"],
        "robotics_autonomy": ["Robotics Software Engineer", "Perception Engineer", "Motion Planning Engineer"],
    },
}


def cls(title, description="", company_type="unknown", department=""):
    return classify(title, KN, description, department, company_type)


class SpecialtyTests(unittest.TestCase):
    def assertSpecialty(self, title, family, sub, **kw):
        result = cls(title, **kw)
        self.assertEqual((family, sub, False), (result["family"], result["subcategory"], result["is_finance"]),
                         (title, result["evidence"]))
        return result

    def test_every_filter_places_its_example_titles(self):
        for family, filters in EXAMPLES.items():
            for sub, titles in filters.items():
                for title in titles:
                    with self.subTest(title=title):
                        self.assertSpecialty(title, family, sub)

    def test_the_family_tree_lists_each_boards_filters_and_the_manifest_polls_for_them(self):
        tree = {f["key"]: f["subcategories"] for f in KN.family_tree()}
        manifest = load_packs().fields
        for family, filters in EXAMPLES.items():
            self.assertEqual(list(filters), [s["key"] for s in tree[family]])
            self.assertTrue(all(s["note"] for s in tree[family]))
            self.assertEqual(set(filters), set(manifest[family]["filters"]), family)
        self.assertEqual([], tree["sales"])
        self.assertEqual("Backend", KN.subcategory_label("software", "backend"))
        self.assertNotIn("backend", {s["key"] for c in KN.taxonomy_tree() for s in c["subcategories"]})

    def test_a_title_without_a_specialty_stays_on_its_board(self):
        self.assertSpecialty("Software Engineer Intern", "software", None)
        self.assertSpecialty("Mechanical Engineering Intern", "hardware", None)

    def test_the_occupation_before_the_comma_outranks_the_team_after_it(self):
        result = self.assertSpecialty("Backend Engineer, Payments Infrastructure", "software", "backend")
        self.assertIn("infrastructure", result["secondary_subcategories"])
        self.assertEqual("Backend", result["subcategory_label"])
        self.assertSpecialty("Backend Engineer - Data Platform", "software", "backend",
                             description="Kubernetes, Terraform, CI/CD and observability for our platform.")

    def test_a_specialty_from_the_description_alone_needs_clear_evidence(self):
        frontend = "You will build React components in TypeScript with CSS and HTML5, and own our design system."
        result = self.assertSpecialty("Software Engineer", "software", "frontend", description=frontend)
        self.assertIn("description: CSS", result["evidence"])
        self.assertSpecialty("Software Development Engineer", "software", None,
                             description="Our teams run on AWS. Experience with Docker and Python is a plus.")

    def test_hardware_occupations_come_before_software(self):
        for title in ("Embedded Software Engineer", "Firmware Engineer", "Robotics Software Engineer", "RTL Design Engineer"):
            self.assertEqual("hardware", cls(title)["family"], title)
        self.assertSpecialty("Machine Learning Engineer, Robotics", "data_ml", "ml_engineering")
        self.assertEqual("software", cls("Robotics Process Automation Developer")["family"])
        self.assertEqual("software", cls("Product Manager, Embedded Payments")["family"])     # a business title: as before

    def test_an_employer_type_leans_a_specialty_but_names_none_alone(self):
        unreal = "Build gameplay systems in Unreal Engine."
        self.assertSpecialty("Software Engineer", "software", None, description=unreal)
        result = self.assertSpecialty("Software Engineer", "software", "game_dev", description=unreal, company_type="gaming")
        self.assertIn("employer type: gaming", result["evidence"])
        self.assertSpecialty("Software Engineer", "software", None, company_type="gaming")

    def test_a_subject_word_does_not_take_a_quant_research_role_off_the_finance_board(self):
        # The Finance board gate caught this one: 'reinforcement learning' must not decide the family.
        result = cls("Member of Research Staff, Reinforcement Learning", company_type="quant_firm",
                     description="Our quantitative research team builds systematic trading strategies with "
                                 "statistical arbitrage and time series models.")
        self.assertEqual((True, "quant", "quant_research"), (result["is_finance"], result["category"], result["subcategory"]))

    def test_tech_employer_types_never_make_a_role_finance(self):
        for ctype in ("gaming", "big_tech", "ai_lab", "semiconductors"):
            self.assertFalse(cls("Summer Analyst", company_type=ctype)["is_finance"], ctype)
        self.assertTrue(cls("Summer Analyst", company_type="canadian_bank")["is_finance"])
        self.assertTrue(cls("2027 Investment Banking Summer Analyst", company_type="big_tech")["is_finance"])


class TechFitTests(unittest.TestCase):
    PROFILE = {"fields": ["software"], "target_roles": ["software.backend", "data_ml.ml_engineering"],
               "target_locations": ["new_york"], "target_countries": ["US"], "target_company_types": []}
    FINANCE = {"fields": ["finance"], "target_roles": ["investment_banking"], "target_countries": ["US"],
               "target_company_types": []}

    def score(self, title, profile=None, **extra):
        job = {"title": title, "company": "Acme Robotics", "location": "New York, NY", "posted": NOW - 3600, **extra}
        result = analyze(job, profile or self.PROFILE, KN, now=NOW)
        return result, {s["key"]: s for s in result["subscores"]}

    def test_specialty_targets_validate(self):
        self.assertEqual([], validate_profile(merge_profile(self.PROFILE), KN))
        problems = validate_profile(merge_profile({"target_roles": ["software.nope"], "target_company_types": ["big_tech", "moonbase"]}), KN)
        self.assertEqual(2, len(problems), problems)

    def test_specialties_rank_exact_then_related_then_siblings(self):
        points = {title: self.score(title)[1]["role"]["points"] for title in (
            "Backend Engineer Intern", "Full Stack Engineer Intern", "Software Engineer Intern",
            "Frontend Engineer Intern", "Machine Learning Engineer Intern", "Research Scientist Intern")}
        self.assertEqual(25, points["Backend Engineer Intern"])
        self.assertEqual(25, points["Machine Learning Engineer Intern"])
        self.assertEqual(14, points["Full Stack Engineer Intern"])           # related to Backend
        self.assertEqual(14, points["Research Scientist Intern"])            # related to ML Engineering
        self.assertEqual(14, points["Software Engineer Intern"])             # no specialty named
        self.assertEqual(9, points["Frontend Engineer Intern"])
        self.assertIn("related to your Backend target", self.score("Full Stack Engineer Intern")[1]["role"]["detail"])

    def test_specialty_targets_are_not_a_finance_mismatch(self):
        for title in ("Frontend Engineer Intern", "Account Executive"):
            self.assertNotIn("role_mismatch", {p["key"] for p in self.score(title)[0]["penalties"]}, title)

    def test_quant_development_also_targets_finance_quant_developers(self):
        job = {"title": "Technology Co-op", "company": "Jane Street",
               "description": "Low-latency trading systems, market data feeds and order management."}
        quant_dev = analyze(job, {"fields": ["software"], "target_roles": ["software.quant_dev"]}, KN, now=NOW)
        self.assertEqual(("quant", "quant_developer", True), (quant_dev["classification"]["category"],
                         quant_dev["classification"]["subcategory"], quant_dev["classification"]["is_finance"]))
        self.assertEqual(25, {s["key"]: s for s in quant_dev["subscores"]}["role"]["points"])
        backend = analyze(job, {"fields": ["software"], "target_roles": ["software.backend"]}, KN, now=NOW)
        self.assertLess({s["key"]: s for s in backend["subscores"]}["role"]["points"], 25)

    def test_a_tech_employer_counts_only_for_a_profile_with_a_tech_board(self):
        facts = build_facts({"title": "Backend Engineer", "company": "Acme", "location": "New York, NY"}, KN)
        facts["company"] = {**facts["company"], "type": "big_tech", "type_label": "Big Tech", "known": True}

        def company(profile, facts=facts):
            return {s["key"]: s for s in score_job(facts, merge_profile(profile), KN, {}, NOW)["subscores"]}["company"]
        self.assertEqual((7, "Big Tech — recognized tech employer"), (company(self.PROFILE)["points"], company(self.PROFILE)["detail"]))
        self.assertEqual(7, company({"fields": ["finance", "data_ml"], "target_roles": []})["points"])
        self.assertEqual(4, company(self.FINANCE)["points"])
        self.assertEqual(4, company({})["points"])                          # no profile: the Finance board
        unknown = {**facts, "company": {**facts["company"], "type": "unknown", "type_label": "Unclassified"}}
        self.assertEqual(4, company(self.FINANCE, unknown)["points"])
        bank = {**facts, "company": {**facts["company"], "type": "canadian_bank", "type_label": "Canadian Bank"}}
        self.assertEqual(7, company(self.PROFILE, bank)["points"])

    def test_every_employer_type_has_a_track_and_finance_ones_are_unchanged(self):
        tracks = {key: tuple(KN.type_tracks(key)) for key in KN.company_types if key != "unknown"}
        # Healthcare has its own types and shares Research Lab and Health Tech with tech (healthcare-board D4, D10).
        self.assertTrue(set(tracks.values()) <= {("finance",), ("tech",), ("finance", "tech"), ("healthcare",),
                                                 ("tech", "healthcare")})
        self.assertEqual({"fintech", "quant_firm"}, {k for k, t in tracks.items() if t == ("finance", "tech")})
        self.assertIn("ai_lab", {k for k, t in tracks.items() if t == ("tech",)})
        self.assertEqual(20, sum("tech" in t and "finance" not in t for t in tracks.values()))  # 3 since: climate, quantum, telecom


class TechEmployerTests(unittest.TestCase):
    def test_a_tech_employers_key_is_the_one_its_postings_had_before_it_was_known(self):
        # Unknown employers key on the slug of their name, and cluster keys start with it.
        tech = [c for c in KN.companies.values() if KN.type_tracks(c.type) == ["tech"]]
        self.assertGreater(len(tech), 100)
        for company in tech:
            self.assertEqual(slug(company.name), company.key, company.name)

    def test_a_tech_employers_hq_never_stands_in_for_a_postings_location(self):
        okta = resolve_company("Okta", KN)
        self.assertEqual(("okta", "Cybersecurity", ""), (okta["key"], okta["type_label"], okta["country"]))
        self.assertEqual("US", KN.companies["okta"].country)               # still shown in the Companies view
        self.assertEqual("CA", resolve_company("RBC", KN)["country"])       # finance employers as before
        self.assertEqual("US", resolve_company("Visa", KN)["country"])      # and fintech

    def test_names_near_a_new_employer_keep_the_employer_they_had(self):
        # The Finance board gate: these postings resolved this way before tech employers were added.
        for name, key, ctype in (("HPE (University)", "hpe", "unknown"), ("Micron Technology", "micron_technology", "semiconductors"),
                                 ("Lightspeed Venture Partners", "lightspeed", "venture_capital")):
            resolved = resolve_company(name, KN)
            self.assertEqual((key, ctype), (resolved["key"], resolved["type"]), name)
        self.assertEqual("Micron Technology", resolve_company("Micron Technology", KN)["name"])


if __name__ == "__main__":
    unittest.main()
