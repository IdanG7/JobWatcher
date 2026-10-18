"""Domain evidence must distinguish financial assurance from technical QA."""
import unittest

from intel import build_facts, load_knowledge
from intel.taxonomy import classify


KN = load_knowledge()


class ClassificationContextTests(unittest.TestCase):
    def test_screenshot_technical_and_clinical_assurance_roles_are_not_finance(self):
        cases = (
            ("Software Engineering Intern - Software Tools and Assurance", "Aerospace Corporation", "software"),
            ("Quality Assurance Research Clinical Quality, Analytics & AI Co-op", "Merck", "healthcare"),
            ("Data and Intelligence Delivery Intern - Assurance", "EY", "data_ml"),
        )
        for title, company, family in cases:
            with self.subTest(title=title):
                result = build_facts({"title": title, "company": company}, KN)["classification"]
                self.assertFalse(result["is_finance"], result)
                self.assertEqual(family, result["family"])

    def test_generic_accounting_words_cannot_override_a_technical_title(self):
        for title in ("Software Engineering Intern - Audit", "Data Analytics Intern - Assurance",
                      "Quality Assurance Intern", "QA Intern", "Clinical Research Intern"):
            for employer_type in ("unknown", "accounting_advisory", "bulge_bracket"):
                with self.subTest(title=title, employer_type=employer_type):
                    result = classify(title, KN, "Our teams perform accounting, audit and financial reporting.",
                                      company_type=employer_type)
                    self.assertFalse(result["is_finance"], result)

    def test_accounting_employer_prior_cannot_claim_data_analytics(self):
        result = build_facts({"title": "Data Analytics Intern", "company": "BDO"}, KN)["classification"]
        self.assertFalse(result["is_finance"], result)
        self.assertEqual("data_ml", result["family"])

    def test_financial_audit_and_assurance_roles_remain_accounting(self):
        for title in ("Audit Intern", "Assurance Intern", "Financial Audit Associate",
                      "Accounting Intern", "Audit and Assurance Co-op"):
            with self.subTest(title=title):
                result = classify(title, KN, company_type="accounting_advisory")
                self.assertTrue(result["is_finance"], result)
                self.assertEqual(("corporate_finance", "accounting"),
                                 (result["category"], result["subcategory"]))

    def test_employer_or_programming_language_does_not_turn_software_into_finance(self):
        for title, company in (("Software Developer Intern", "DRW"),
                               ("Software Engineer Intern", "Jane Street"),
                               ("Data Scientist Intern", "Citadel"),
                               ("Research Scientist Intern", "Example Research Lab"),
                               ("C++ Developer Intern", "Example Software"),
                               ("FPGA Engineer Intern", "Example Hardware")):
            with self.subTest(title=title, company=company):
                result = build_facts({"title": title, "company": company}, KN)["classification"]
                self.assertFalse(result["is_finance"], result)

    def test_finance_specific_analysis_and_quant_research_roles_stay_finance(self):
        for title, company, category, sub in (
            ("ALM Data Analyst Intern", "Manulife", "corporate_finance", "treasury"),
            ("Quantitative Researcher Intern", "Jane Street", "quant", "quant_research"),
            ("Quantitative Trader Intern", "Jane Street", "quant", "quant_trading"),
        ):
            with self.subTest(title=title):
                result = build_facts({"title": title, "company": company}, KN)["classification"]
                self.assertTrue(result["is_finance"], result)
                self.assertEqual((category, sub), (result["category"], result["subcategory"]))

    def test_technical_occupation_trumps_banking_or_risk_department(self):
        for title, company, department in (
            ("Commercial Lending AI Engineer Intern", "Equitable Bank", "Commercial Lending"),
            ("Retail Lending AI Engineer Intern", "Equitable Bank", "Retail Lending"),
            ("GenAI and Digital Workplace Intern", "Manulife", "Insurance"),
            ("AI/ML Research Intern", "DRW", "Quant"),
            ("Quantum Technologies Intern", "RBC", "Quant"),
            ("Applied Research Intern, Proactive Intelligence & Customer World Models (PhD / Graduate Co-op)",
             "Block", "Fintech"),
            ("Technology Enablement Analyst Co-op", "Manulife", "Insurance"),
            ("Product Management & Risk Technology Intern", "Manulife", "Risk"),
            ("Software Engineer Intern, Treasury", "RBC", "Treasury"),
            ("Data & Analytics Co-op Intern", "BDO", "Accounting"),
            ("Clinical Risk Data Scientist Intern", "Merck", "Risk"),
            ("Medical Risk Software Engineer Intern", "Merck", "Risk"),
        ):
            with self.subTest(title=title):
                result = build_facts({"title": title, "company": company, "department": department}, KN)["classification"]
                self.assertFalse(result["is_finance"], result)
                self.assertNotEqual("other", result["family"])

    def test_financial_analysis_occupations_survive_technical_family_keywords(self):
        for title, expected in (
            ("ALM Data Analyst Intern", "corporate_finance"),
            ("Treasury Data Analyst Intern", "corporate_finance"),
            ("Model Risk Analyst - Machine Learning", "risk"),
            ("Credit Risk Analyst Intern", "risk"),
            ("Quantitative Analyst Intern", "quant"),
        ):
            with self.subTest(title=title):
                result = build_facts({"title": title, "company": "RBC"}, KN)["classification"]
                self.assertTrue(result["is_finance"], result)
                self.assertEqual(expected, result["category"])

    def test_quant_label_does_not_turn_engineering_into_finance(self):
        result = classify("Commercial Lending Quantitative Software Engineer Intern", KN,
                          "Corporate banking, lending decisions and commercial clients. Business banking and commercial banking.",
                          department="Lending", company_type="canadian_bank")
        self.assertEqual("software", result["category"])
        self.assertFalse(result["is_finance"])

    def test_quant_development_and_trading_systems_engineering_are_not_finance(self):
        for title in ("Quant Developer Intern", "Quantitative Developer Intern", "Trading Systems Engineer Intern",
                      "Quantitative Software Engineer Intern", "Quantitative Data Engineer Intern",
                      "Quantitative Data Scientist Intern", "Quantitative Research Data Scientist Intern"):
            with self.subTest(title=title):
                result = classify(title, KN, company_type="quant_firm", department="Quant")
                self.assertFalse(result["is_finance"], result)

    def test_bank_support_security_and_technology_consulting_are_not_finance(self):
        for title in ("Trade Floor Technology Consultant Intern", "Corporate Security Intern",
                      "Workplace Coordinator Intern", "Administrative Support Intern",
                      "Finance Administrative Assistant Intern", "Office Assistant Intern",
                      "Technology Business Administration Co-op Intern"):
            with self.subTest(title=title):
                result = classify(title, KN, company_type="canadian_bank", department="Finance")
                self.assertFalse(result["is_finance"], result)

    def test_economists_and_economic_research_are_financial_strategy_roles(self):
        for title in ("Economist Intern", "Economic Research Analyst Intern", "Energy Analyst Intern - Economics"):
            with self.subTest(title=title):
                result = classify(title, KN)
                self.assertTrue(result["is_finance"], result)
                self.assertEqual("strategy", result["category"])

    def test_programming_skills_do_not_change_a_financial_research_occupation(self):
        for title in ("Quantitative Researcher Intern", "Quantitative Analyst Intern", "Quantitative Trader Intern"):
            with self.subTest(title=title):
                result = classify(title, KN, "Use Python, C++ and SQL for statistical analysis and financial research.",
                                  company_type="quant_firm")
                self.assertTrue(result["is_finance"], result)
                self.assertEqual("quant", result["category"])

    def test_marketing_research_and_product_coordination_are_not_finance(self):
        for title, company, expected in (
            ("Analyst Co-op Intern - Consumer Insights & Market Research", "Definity", "sales"),
            ("Product Coordinator Intern, Driver Compliance", "Geotab", "product"),
        ):
            with self.subTest(title=title):
                result = build_facts({"title": title, "company": company}, KN)["classification"]
                self.assertFalse(result["is_finance"], result)
                self.assertEqual(expected, result["family"])


if __name__ == "__main__":
    unittest.main()
