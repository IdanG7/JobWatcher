"""Product: its filters, the words that bring a title to the board, the claims by which it takes titles other
boards place, and what it leaves to Operations, Healthcare and Finance (plans/product-design-board.md, sections 3
and 4; decisions D1 to D6 and D16). Every other board and Finance keep what they place."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile, validate_profile
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()

# Titles per filter (section 3.2), with the employer type where they show up. Plurals land as the singular does.
EXAMPLES = {
    "product_management": [("Senior Product Manager", "big_tech"), ("Product Owner", "defense_tech"),
                           ("Director of Product Management", "semiconductors"), ("Head of Product", "unknown"),
                           ("Product Managers", "unknown"), ("Product Owners", "unknown"),
                           ("Senior Product Manager, Growth", "unknown"), ("Growth Product Manager", "enterprise_saas"),
                           ("Product Lead", "unknown"), ("Senior Product Associate", "bulge_bracket")],
    "technical_pm": [("Technical Program Manager", "semiconductors"), ("Technical Product Manager", "health_tech"),
                     ("Engineering Program Manager", "big_tech"), ("Technical Program Managers", "big_tech"),
                     ("Engineering Program Managers", "unknown"), ("Sr. TPM – Antenna Development, Amazon Leo", "big_tech"),
                     ("Senior PMT-ES, Amazon Aurora", "big_tech"), ("Data Product Manager", "unknown")],
    "apm_programs": [("Associate Product Manager Intern", "unknown"), ("Associate Product Manager", "medtech"),
                     ("Product Management Intern", "big_tech"), ("Product Management Co-op", "unknown"),
                     ("Rotational Product Manager", "unknown"), ("Product Intern", "unknown"),
                     ("Intern, Product Management", "unknown"), ("Associate Product Managers", "unknown"),
                     ("Product Manager, New Grad 2027", "unknown")],
    "product_ops": [("Product Operations Manager", "gaming"), ("Product Operations Specialist", "fintech"),
                    ("Product Operations Intern", "unknown"), ("Head of Product Operations", "robotics_autonomy")],
    "product_analytics": [("Product Analyst", "consumer_tech"), ("Senior Product Analyst", "gaming"),
                          ("Product Analytics Intern", "health_tech"), ("Product Analysts", "unknown")],
}


def cls(title, description="", company_type="unknown", department=""):
    return classify(title, KN, description, department, company_type)


def board(result):
    return "finance" if result["is_finance"] else result["family"]


class FilterTests(unittest.TestCase):
    def test_every_filter_places_its_example_titles(self):
        for sub, titles in EXAMPLES.items():
            for title, ctype in titles:
                with self.subTest(title=title):
                    result = cls(title, company_type=ctype)
                    self.assertEqual(("product", sub), (board(result), result["subcategory"]), result["evidence"])

    def test_the_family_tree_lists_the_five_filters_with_notes(self):
        # D16: growth PMs fold into Product Management; no strategy, delivery or program-management filter.
        tree = {f["key"]: f for f in KN.family_tree()}["product"]
        self.assertEqual(list(EXAMPLES), [s["key"] for s in tree["subcategories"]])
        self.assertTrue(all(s["note"] for s in tree["subcategories"]))
        self.assertEqual("Technical PM & TPM", KN.subcategory_label("product", "technical_pm"))
        self.assertEqual("product_management", cls("Growth PM", company_type="ai_lab")["subcategory"])

    def test_a_product_title_without_a_filter_word_stays_on_the_board(self):
        result = cls("Product Builder")
        self.assertEqual("product", board(result))
        self.assertIn(result["subcategory"], (None, "product_management"))

    def test_the_more_specific_filter_wins_a_tie(self):
        for title, sub in (("Technical Product Management Intern", "apm_programs"),
                           ("Technical Product Manager", "technical_pm"),
                           ("Senior Product Manager, Cloud Networking", "technical_pm"),
                           ("Product Management & Product Operations Intern", "apm_programs")):
            self.assertEqual(sub, cls(title)["subcategory"], title)

    def test_related_filters_earn_the_related_credit(self):
        profile = {"fields": ["product"], "target_roles": ["product.product_management"]}
        self.assertEqual([], validate_profile(merge_profile(profile), KN))

        def role(title):
            result = analyze({"title": title, "company": "Acme", "posted": NOW - 3600}, profile, KN, now=NOW)
            return {s["key"]: s for s in result["subscores"]}["role"]["points"]
        self.assertEqual(35, role("Senior Product Manager"))
        self.assertEqual(24, role("Technical Program Manager"))         # related to Product Management
        self.assertEqual(24, role("Associate Product Manager"))
        self.assertEqual(12, role("Product Operations Manager"))

    def test_product_analytics_also_targets_ai_and_datas_analytics(self):
        # D16: scoring only. 'Data Analyst' stays on AI & Data and counts for a product-analytics target.
        self.assertEqual(["data_ml.analytics"], KN.subcategories["product.product_analytics"].meta["also_targets"])
        job = {"title": "Data Analyst", "company": "Acme", "posted": NOW - 3600}
        target = analyze(job, {"fields": ["product", "data_ml"], "target_roles": ["product.product_analytics"]}, KN,
                         now=NOW)
        self.assertEqual(("data_ml", "analytics"), (target["classification"]["family"],
                                                    target["classification"]["subcategory"]))
        self.assertEqual(35, {s["key"]: s for s in target["subscores"]}["role"]["points"])
        other = analyze(job, {"fields": ["product", "data_ml"], "target_roles": ["product.product_ops"]}, KN, now=NOW)
        self.assertLess({s["key"]: s for s in other["subscores"]}["role"]["points"], 35)


class TitleWordTests(unittest.TestCase):
    """D1, D4 and D5: Product's words, with their exclusions inside the patterns."""

    def assertBoard(self, expected, title, **kw):
        result = cls(title, **kw)
        self.assertEqual(expected, board(result), (title, result["evidence"]))
        return result

    def test_new_words_bring_product_titles_no_board_placed(self):
        for title, kw in (("Product Owner, Laboratory Quality", {"company_type": "diagnostics"}),
                          ("Citi Commerce, Product Lead", {"company_type": "global_bank"}),
                          ("Sr. TPM, AWS EC2", {"company_type": "big_tech"}),
                          ("Sr. PMT, AWS EC2", {"company_type": "big_tech"}),
                          ("Product Intern - Richmond, VA (Summer 2027)", {}),
                          ("Data Intern - Product Analytics - Winter 2027", {}),
                          ("Head of Product - Grid Planning", {}),
                          ("Product Builder", {"company_type": "developer_tools"}),
                          ("Sr Manager, Technical Programs", {"company_type": "fintech"}),
                          ("Lead, Technical Program Management", {"company_type": "defense_tech"})):
            result = self.assertBoard("product", title, **kw)
            self.assertNotIn("rule", result)

    def test_product_ops_leave_operations(self):
        # D4: the filter's whole content.
        for title in ("Product Operations Manager", "Senior Product Operations Manager, Integrations",
                      "2027 Summer Internship - Product Operations"):
            self.assertEqual(("product", "product_ops"), (board(cls(title)), cls(title)["subcategory"]), title)

    def test_heads_and_directors_of_product_marketing_design_and_counsel_stay(self):
        for expected, title in (("sales", "Head of Product Marketing"), ("sales", "Director of Product Marketing"),
                                ("sales", "Director, Head of Product Marketing"), ("sales", "Product Marketing Manager"),
                                ("sales", "Head of Product and Solutions Marketing"),
                                ("design", "Head of Product Design"), ("design", "Director of Product Design"),
                                ("people_legal", "Director of Product Counsel"), ("people_legal", "Product Counsel"),
                                ("people_legal", "Head of Product Engineering, HR Total Rewards"),
                                ("other", "Head of Product Security"), ("other", "Director of Product Strategy")):
            self.assertBoard(expected, title)
        for title in ("VP of Product, Growth and Monetization", "Director of Product, AI Growth", "Growth PM"):
            self.assertBoard("product", title)

    def test_words_left_out_place_nothing(self):
        # No bare pm, apm or cpo, no product strategy, specialist, scrum or release words.
        for expected, title, kw in (("other", "Material Handler I USA (D Crew/PM Shift)", {}),
                                    ("design", "Staff Product Designer, APM", {"company_type": "developer_tools"}),
                                    ("other", "Chief Product Officer", {}),
                                    ("operations", "Executive Assistant to the Chief Product Officer", {}),
                                    ("finance", "Product Strategy Intern", {}),
                                    ("operations", "Product Strategy and Operations Principal", {"company_type": "big_tech"}),
                                    ("other", "Product Specialist", {"company_type": "pharma"}),
                                    ("other", "Scrum Master", {}), ("design", "Product Designer", {"company_type": "big_tech"}),
                                    ("software", "Product Engineer", {}), ("software", "Product Security Engineer", {})):
            self.assertBoard(expected, title, **kw)

    def test_drug_product_and_regulatory_titles_stay_off_product(self):
        self.assertBoard("healthcare", "Senior Manager, Drug Product Analytics", company_type="pharma")
        self.assertBoard("healthcare", "Director - Drug Product Analytics", company_type="pharma")
        self.assertBoard("other", "Onco Drug-Device Combo Products Intern", company_type="pharma")
        self.assertBoard("operations", "Drug Product Operations Technician", company_type="cro_cdmo")
        self.assertEqual("markets", self.assertBoard("finance", "Regulatory Products Intern",
                                                     company_type="market_infrastructure")["category"])
        self.assertEqual("corporate_finance", self.assertBoard(
            "finance", "Tax Technology and Transformation Products Intern - Tax",
            company_type="accounting_advisory")["category"])

    def test_product_analytics_data_scientists_stay_on_ai_and_data(self):
        for title, sub in (("Data Scientist, Product Analytics", "data_science"),
                           ("Data Scientist Intern - Product Analytics", "data_science"),
                           ("Data Engineer, Product Analytics", "data_engineering")):
            result = self.assertBoard("data_ml", title, company_type="big_tech")
            self.assertEqual(sub, result["subcategory"], title)

    def test_tpm_and_pmt_that_mean_something_else_stay(self):
        for expected, title, ctype in (("software", "Total Productive Maintenance (TPM) Engineer", "semiconductors"),
                                       ("other", "MGR,TPM(Total Productive Management) (Taoyuan)", "semiconductors"),
                                       ("operations", "TPM QA Director", "medtech"),
                                       ("operations", "TPM Assessments Operations Expert (/f/m/x)", "global_bank"),
                                       ("operations", "Senior Manager, TPM Manufacturing and Operations", "medtech"),
                                       ("other", "Facilities Technical Project Manager (TPM)", "semiconductors"),
                                       ("software", "Secure Software Architect TPM (Trusted Platform Module) (m/f/d)",
                                        "semiconductors"),
                                       ("other", "PMT Analyst - Weekend Shift", "defense_tech")):
            self.assertBoard(expected, title, company_type=ctype)

    def test_product_builder_is_guarded_against_amazons_application_builders(self):
        self.assertBoard("software", "Application Builder, Ring Software Product Builders", company_type="big_tech")
        self.assertBoard("software", "Application Builder, Device Software Product Builders", company_type="big_tech")
        self.assertBoard("product", "AI Product Builder Intern")

    def test_executive_assistants_go_to_operations(self):
        # D5: Operations' words name executive assistants; Product's words skip them.
        for title in ("Executive Assistant, VP, Product Management (Hybrid)",
                      "Executive Assistant: VP, Customer Experience Product Management (Hybrid)",
                      "Executive Assistant, Product Management", "Executive Assistant to the Head of Product",
                      "Project/ Program Manager (NonTech) Executive Assistant"):
            self.assertBoard("operations", title, company_type="big_tech")
        self.assertBoard("sales", "Program Manager & Executive Assistant to the SVP of Sales",
                         company_type="developer_tools")


class ProgramManagerTests(unittest.TestCase):
    """D2 (B1): a plain program manager is Operations' word; tech evidence takes it back to Product."""

    def assertBoard(self, expected, title, **kw):
        result = cls(title, **kw)
        self.assertEqual(expected, board(result), (title, result["evidence"]))
        return result

    def test_plain_program_managers_are_operations(self):
        for title, ctype in (("Program Manager", "defense_tech"), ("Program Manager", "hospital"),
                             ("Program Manager", "big_tech"), ("Senior Program Managers", "semiconductors"),
                             ("Material Program Manager", "defense_tech"), ("Supply Chain Program Manager", "unknown"),
                             ("Program Management Mgr - L5", "defense_tech"), ("Program Management Intern", "defense_tech"),
                             ("Global Facilities Senior Program Manager (PMO)", "semiconductors"),
                             ("Program Management Engineer", "semiconductors")):
            self.assertBoard("operations", title, company_type=ctype)
        for title, ctype in (("Program Management Lead Analyst", "global_bank"),
                             ("Program Management Associate", "bulge_bracket")):
            self.assertBoard("operations", title, company_type=ctype)

    def test_other_boards_program_managers_go_to_their_boards(self):
        for expected, title in (("sales", "Sales Enablement Program Manager"), ("sales", "Regional Program Manager, Field Sales"),
                                ("design", "UX Program Manager"), ("design", "Senior Design Program Manager II"),
                                ("operations", "People Program Manager"), ("healthcare", "Clinical Program Manager")):
            self.assertBoard(expected, title)

    def test_technical_and_engineering_program_managers_stay_products_words(self):
        for title in ("Technical Program Manager", "Senior Technical Program Manager", "TPM",
                      "Engineering Program Manager", "Technical Programs Lead", "Tech Program Manager",
                      "Technical Program/Project Manager III"):
            result = self.assertBoard("product", title, company_type="defense_tech")
            self.assertEqual("technical_pm", result["subcategory"], title)
            self.assertNotIn("rule", result)

    def test_tech_evidence_takes_a_program_title_back(self):
        for title, kw in (("IT Program Manager", {}), ("Program Manager, AI", {}), ("Network Program Manager", {}),
                          ("Program Manager, Engineering", {}), ("SoC Program Manager", {"company_type": "semiconductors"}),
                          ("Information Technology Program Manager", {"company_type": "defense_tech"}),
                          ("Lead Technology Program Manager", {"company_type": "bulge_bracket"}),   # yours, 2026-11-07
                          ("Senior Program Manager", {"department": "Project/Program/Product Management--Technical"}),
                          ("Program Manager", {"department": "Technical Program Management"}),
                          ("Program Manager", {"description": "Work with engineering teams on the product roadmap, run "
                                                              "agile sprints and track releases in Jira."})):
            result = self.assertBoard("product", title, **kw)
            self.assertEqual(("program_tech_evidence", "technical_pm"), (result["rule"], result["subcategory"]), title)

    def test_no_tech_evidence_or_an_excluded_word_keeps_operations(self):
        for title, kw in (("Program Manager", {"description": "Manage the contract, its budget and the customer."}),
                          ("Non-Technical Project/Program Management II - NPI Field Readiness Enablement",
                           {"company_type": "semiconductors"}),
                          ("Non-Technical Program Manager", {}), ("NPS Program Manager", {}),
                          ("Program Manager", {"department": "Business Program Management"})):
            self.assertBoard("operations", title, **kw)


class TopicClaimTests(unittest.TestCase):
    """D3: a PM or program occupation beats the topic word that put the title on Software, AI & Data or Hardware."""

    def test_pm_titles_leave_topic_boards(self):
        for title, before in (("Product Manager, API Platform", "software"),
                              ("Confluent - Senior Product Manager, Cloud Networking", "software"),
                              ("Senior Product Manager, Mobile", "software"),
                              ("Software Product Management Intern", "software"),
                              ("Staff Product Manager, ML Foundations and GenAI", "data_ml"),
                              ("Technical Product Manager, AI/ML Products", "data_ml"),
                              ("Product Manager, Hardware", "hardware"), ("Senior Hardware Product Manager", "hardware"),
                              ("Lead Principal Product Manager - Robotics", "hardware")):
            result = cls(title)
            self.assertEqual(("product", "pm_over_topic"), (board(result), result.get("rule")), (title, before))

    def test_program_titles_leave_topic_boards(self):
        for title in ("Technical Program Manager, Infrastructure", "Software Development Program Manager",
                      "Senior Program Manager - AI Infrastructure Services", "Hardware Technical Program Manager",
                      "Technical Program Manager-Post Silicon Development", "Technical Program Manager, ASIC",
                      "Technical Program/Project Manager (Software)"):
            result = cls(title)
            self.assertEqual(("product", "program_over_topic", "technical_pm"),
                             (board(result), result.get("rule"), result["subcategory"]), title)

    def test_engineers_and_the_two_known_false_moves_stay(self):
        for expected, title, ctype in (("data_ml", "AI Intern, Office of CEO & Head of Product", "unknown"),
                                       ("data_ml", "AI Intern - Office of CEO & Head of Product", "unknown"),
                                       ("data_ml", "Vice President Product Delivery Manager - Data Analytics Platform",
                                        "bulge_bracket"),
                                       ("software", "Senior Software Engineer - Product Lead", "defense_tech"),
                                       ("data_ml", "Consultant Machine Learning Engineer & AI Product Lead", "unknown"),
                                       ("software", "Software Engineer – Product Analytics Platform", "unknown"),
                                       ("hardware", "Firmware Engineer, Product Development", "unknown")):
            result = cls(title, company_type=ctype)
            self.assertEqual(expected, board(result), title)
            self.assertNotIn("rule", result)


class HealthcareTests(unittest.TestCase):
    def test_nurse_np_and_pharmacist_program_managers_go_to_healthcare(self):
        # D5: Healthcare's claim; the 7 clinical program managers.
        for title in ("RN Program Manager Abdominal Transplant", "Program Manager (RN), Cancer Destination Service Line",
                      "(RN) Heart Transplant Program Manager - 141034", "(RN) Lung Transplant Program Manager - 140105",
                      "RN Program Manager, Women's Health, Part Time, Varies, Morristown NJ",
                      "Bilingual Senior Program Manager - Nurse Practitioner Team Lead", "Pharmacist Program Manager"):
            result = cls(title, company_type="hospital")
            self.assertEqual(("healthcare", "clinical_program_manager"), (board(result), result.get("rule")), title)

    def test_the_claim_stays_narrow(self):
        self.assertEqual("operations", board(cls("Senior Specialist, Health Plan Quality Program Management & "
                                                 "Performance (RN) - Remote", company_type="payer")))
        self.assertEqual("operations", board(cls("NPS Program Manager")))
        # D5's two other titles stay on Product, as on main.
        self.assertEqual("product", board(cls("Pharmacy Compliance & Sterile Product Coordinator", company_type="hospital")))
        self.assertEqual("product", board(cls("Associate Legal Paralegal/Product Manager", company_type="asset_manager")))

    def test_healthcares_title_words_and_claims_keep_their_titles(self):
        self.assertEqual("healthcare", board(cls("Clinical Product Manager", company_type="medtech")))
        self.assertEqual("product", board(cls("Quality Product Manager", company_type="pharma")))
        self.assertEqual("healthcare", board(cls("Registered Nurse", company_type="hospital")))


class FinanceTests(unittest.TestCase):
    """D6: claim V3's Product half. Finance keeps every other title, in the same filter."""

    def test_product_occupations_leave_finance(self):
        for title, sub in (("Product Owner, Wealth", "product_management"),
                           ("Head of Product, Lending", "product_management"),
                           ("Senior Product Associate - Small Business Lending", "product_management"),
                           ("Wealth - Account Opening Product Owner - VP", "product_management"),
                           ("Technical Program Manager, Payments Risk", "technical_pm"),
                           ("Lead Technical Program Manager - Risk Technology", "technical_pm"),
                           ("Product Manager, Quantitative Trading", "product_management")):
            result = cls(title, company_type="bulge_bracket")
            self.assertEqual(("product", "product_occupation_from_finance", sub),
                             (board(result), result.get("rule"), result["subcategory"]), title)

    def test_finance_titles_keep_their_filter(self):
        for title, ctype, category, sub in (
                ("Product Controller", "bulge_bracket", "corporate_finance", "accounting"),
                ("Product Control Analyst", "bulge_bracket", "investment_banking", None),
                ("Product Analyst, Credit Risk", "unknown", "risk", "credit_risk"),
                ("Risk Product Analyst", "quant_firm", "risk", None),
                ("Treasury Product Analyst - Payments", "bulge_bracket", "corporate_finance", "treasury"),
                ("Program Manager, Risk", "unknown", "risk", None),
                ("Program Manager, Compliance", "unknown", "risk", "operational_risk"),
                ("Product Strategy Intern", "unknown", "strategy", None),
                ("Head of Product Development & Strategy, BMO Global Asset Management (U.S.)", "canadian_bank",
                 "public_markets", "asset_management"),
                ("UX Researcher, Wealth Management", "unknown", "wealth", "wealth_management"),
                ("Investment Banking Summer Analyst", "bulge_bracket", "investment_banking", None),
                ("Equity Research Associate", "unknown", "public_markets", "equity_research")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("finance", category, sub), (board(result), result["category"], result["subcategory"]),
                             title)

    def test_a_technical_occupation_still_beats_finance_words(self):
        for title in ("Product Manager, Credit Risk", "Product Manager, Payments", "Senior Product Manager, Lending"):
            result = cls(title, company_type="bulge_bracket")
            self.assertEqual("product", board(result), title)
            self.assertNotIn("rule", result)


if __name__ == "__main__":
    unittest.main()
