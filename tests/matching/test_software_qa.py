"""QA and test titles that don't say "software": Software's software_qa rule takes them from Operations, or from no
board, when the title, department or description shows software work. Manufacturing, food, call-centre and
finance-operations QA stay where they were, and Finance keeps every posting it places. All postings are invented."""
import unittest

from intel import load_knowledge
from intel.taxonomy import classify

KN = load_knowledge()

SOFTWARE = ("Join the team that ships our patient-scheduling web application. You will write test plans and test "
            "cases, run regression testing before each release, log defects in Jira, check REST APIs with Postman, "
            "query the database with SQL and grow our Selenium test automation suite in an agile team.")
DEVICE_SOFTWARE = ("Lead verification of the software for our infusion pump. Plan system testing under IEC 62304, "
                   "review test scripts and test cases, triage defects and report on each software release.")
MANUFACTURING = ("Inspect incoming parts against drawings, keep ISO 9001 records, lead CAPA and root cause analysis, "
                 "audit suppliers and release finished goods on the production floor.")
FOOD = ("Monitor HACCP and SQF programs, verify sanitation and allergen control, check GMP on the plant floor and "
        "hold product that fails specification.")
CALL_CENTRE = ("Listen to and score agent calls, coach agents on customer interactions, calibrate scorecards with "
               "team leads and report CSAT trends to the contact centre manager.")
FINANCE_OPS = ("Review closed loan files for completeness, check KYC documents and disclosures, sample transactions "
               "for policy exceptions and report findings to the operations manager.")
# A SaaS employer's boilerplate is no evidence that its support-quality role is software QA.
SAAS_BOILERPLATE = ("We build cloud platforms for retailers. Our software products help 2,000 brands. "
                    "In this role you will listen to support calls and score agent tickets for tone and accuracy.")


def cls(title, description="", department="", company_type="unknown"):
    return classify(title, KN, description, department, company_type)


def placement(result):
    return ("finance" if result["is_finance"] else result["family"]), result["subcategory"]


class SoftwareQaTests(unittest.TestCase):
    def test_qa_and_test_titles_of_software_postings_land_in_qa_and_test(self):
        for title in ("Senior QA Test Lead", "QA Lead", "QA Specialist", "Senior QA Analyst",
                      "Quality Assurance Analyst", "Quality Assurance Engineer", "Test Manager", "Test Lead",
                      "Quality Analyst", "Automation Tester", "UAT Analyst"):
            for description in (SOFTWARE, DEVICE_SOFTWARE):
                with self.subTest(title=title, description=description[:20]):
                    result = cls(title, description)
                    self.assertEqual(("software", "qa_test"), placement(result), result["evidence"])
                    self.assertEqual("software_qa", result["rule"])
                    self.assertEqual("QA & Test", result["subcategory_label"])

    def test_titles_that_already_name_software_keep_their_placement(self):
        for title in ("QA Engineer", "Software QA Analyst", "Software Test Lead", "QA Automation Engineer"):
            with self.subTest(title=title):
                result = cls(title)
                self.assertEqual(("software", "qa_test"), placement(result))
                self.assertNotIn("rule", result)

    def test_software_words_in_the_title_or_department_are_evidence_alone(self):
        for title in ("Senior QA Test Lead", "IT QA Analyst", "QA Analyst, Web Applications", "Web App Tester",
                      "Quality Assurance Specialist - SaaS Platform", "IT Test Analyst", "Game QA Tester"):
            with self.subTest(title=title):
                self.assertEqual(("software", "qa_test"), placement(cls(title)))
        for department in ("Information Technology", "Software Development", "IT", "Technology", "Digital and Technology"):
            with self.subTest(department=department):
                self.assertEqual(("software", "qa_test"), placement(cls("QA Specialist", department=department)))
        # 'it' that isn't the IT acronym, and an engineering division's 'Technology', are no evidence.
        for department in ("Make it Right", "Engineering / Technology"):
            with self.subTest(department=department):
                self.assertEqual(("operations", None), placement(cls("QA Specialist", department=department)))

    def test_qa_without_software_evidence_stays_where_it_was(self):
        for title, description, expected in (
                ("QA Lead", "", "operations"), ("QA Specialist", "", "operations"),
                ("Quality Assurance Analyst", "", "operations"), ("Test Manager", "", "other"),
                ("Test Lead", "", "other"), ("Quality Assurance Intern", "", "operations"),
                ("QA Lead", MANUFACTURING, "operations"), ("Quality Assurance Engineer", MANUFACTURING, "operations"),
                ("QA Inspector", MANUFACTURING, "operations"), ("Test Manager", MANUFACTURING, "other"),
                ("QA Specialist", FOOD, "operations"), ("Quality Assurance Technician", FOOD, "operations"),
                ("Quality Assurance Analyst", CALL_CENTRE, "operations"), ("Quality Analyst", CALL_CENTRE, "other"),
                ("Quality Assurance Specialist", SAAS_BOILERPLATE, "operations"),
                ("QA Analyst", FINANCE_OPS, "operations"), ("Quality Assurance Specialist", FINANCE_OPS, "operations")):
            with self.subTest(title=title, description=description[:20]):
                result = cls(title, description)
                self.assertEqual((expected, None), placement(result), result["evidence"])
                self.assertNotIn("rule", result)

    def test_non_software_qa_titles_stay_even_with_software_words_in_the_posting(self):
        # Call-centre, compliance, coding and data-quality reviews use SQL and Jira too.
        for title, expected in (("Quality Assurance Analyst - Call Centre", "operations"),
                                ("Quality Assurance, Monitoring & Testing Analyst", "operations"),
                                ("Controls Testing Lead", "other"),
                                ("Coding Quality Analyst", "other"),
                                ("Data Quality Analyst", "other")):
            with self.subTest(title=title):
                self.assertNotEqual("software", cls(title, SOFTWARE)["family"])
                self.assertEqual(expected, cls(title)["family"])

    def test_hardware_and_aerospace_test_roles_stay_off_software(self):
        # Their postings name Python, Jira and automated tests too.
        hardware = ("Run automated test stations written in Python, track issues in Jira, keep the test execution "
                    "logs and improve test coverage of every unit we build.")
        for title, department in (("Propulsion Test Engineer", ""), ("Manufacturing Test Lead", ""),
                                  ("Test Specialist, Avionics", ""), ("Flight Test Coordinator", ""),
                                  ("Test Specialist", "Satellite Production"), ("QA Test Lead", "Hardware"),
                                  ("NAND QA Test Engineer", ""), ("PCBA Aerospace Test Engineer", ""),
                                  ("Optical Test Automation Intern", ""), ("Test Specialist, Factory Automation", "")):
            with self.subTest(title=title):
                self.assertNotEqual("software", cls(title, hardware, department)["family"])

    def test_audit_and_risk_qa_stay_off_software(self):
        for title in ("Audit Manager, Quality Assurance - IT Audit", "Consultant, ORM QA",
                      "Quality Assurance Manager, Operational Risk"):
            with self.subTest(title=title):
                self.assertNotEqual("software", cls(title, SOFTWARE)["family"])

    def test_lab_quality_keeps_gmp_qa_on_healthcare(self):
        for title in ("Quality Assurance Specialist, GMP", "Quality Control Microbiologist"):
            with self.subTest(title=title):
                result = cls(title, SOFTWARE)
                self.assertEqual("healthcare", result["family"])
                self.assertEqual("lab_quality", result["rule"])

    def test_finance_keeps_the_test_and_qa_titles_it_places(self):
        # 'Test Analyst' at a bank names no division: Finance places it today, and the rule takes nothing from Finance.
        for title, company_type in (("Test Analyst", "canadian_bank"), ("Stress Testing Analyst", "global_bank"),
                                    ("Model Validation Analyst", "unknown")):
            with self.subTest(title=title):
                before = cls(title, company_type=company_type)
                after = cls(title, SOFTWARE, company_type=company_type)
                self.assertTrue(before["is_finance"], before)
                self.assertTrue(after["is_finance"], after)
                self.assertNotEqual("software_qa", after.get("rule"))

    def test_tech_words_in_an_unplaced_title_stay_closed_to_other_boards(self):
        # Only a Tech board's rule may take an unplaced title that names tech work.
        result = cls("Laboratory Analyst, IT", "You will run qPCR and ELISA assays and maintain cell culture.")
        self.assertNotEqual("healthcare", result["family"])


if __name__ == "__main__":
    unittest.main()
