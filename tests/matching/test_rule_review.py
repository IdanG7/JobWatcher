"""The rule review's fixes (plans/product-design-board.md 14.8, R1 to R20): titles the Product and Design rules
placed on the wrong board, filter or stage, and where each now goes. Every other board keeps what it placed."""
import unittest

from intel import load_knowledge
from intel.seniority import detect_seniority
from intel.taxonomy import classify, specialty

KN = load_knowledge()
TECH = ("Work with engineering teams on the software roadmap, run agile sprints, track releases in Jira and plan "
        "cloud infrastructure.")


def cls(title, description="", company_type="unknown", department=""):
    return classify(title, KN, description, department, company_type)


def board(result):
    return "finance" if result["is_finance"] else result["family"]


def stage(title, family):
    return detect_seniority(title, "", board_rules=KN.stage_rules[family])["stage"]


class ProgramClaimTests(unittest.TestCase):
    """R1: the program claims take technical program managers, not supply-chain, business or facilities ones."""

    def test_non_technical_program_managers_stay_on_operations(self):
        for title, kw in (("Program Manager, Data Center Construction", {"company_type": "big_tech"}),
                          ("Senior Business Program Manager", {"description": TECH}),
                          ("Supply Chain Program Manager",
                           {"department": "Project/Program/Product Management--Technical"}),
                          ("Global Program Manager - Commercial Life Sciences", {"description": TECH}),
                          ("Senior L&D Program Manager - Manager Programs", {"description": TECH}),
                          ("Privacy Program Manager", {"description": TECH})):
            result = cls(title, **kw)
            self.assertEqual("operations", board(result), (title, result["evidence"]))

    def test_a_title_that_names_technical_work_keeps_the_claim(self):
        for title in ("Technology and Facilities Program Manager", "Senior Program Manager I - Laser Communications",
                      "Program Manager, Supply Chain Engineering"):
            result = cls(title, TECH)
            self.assertEqual(("product", "program_tech_evidence"), (board(result), result.get("rule")), title)

    def test_supply_chain_program_managers_a_topic_word_placed_go_to_operations(self):
        for title in ("Program Manager III, Supply Chain Operations, Cloud Networking",
                      "Program Manager III, Hardware NPI, Cloud Supply Chain",
                      "Supply Chain Operations Program Manager, AI Infrastructure"):
            result = cls(title)
            self.assertEqual(("operations", "program_ops_from_tech"), (board(result), result.get("rule")), title)
        # other non-technical program work stays on the board whose topic word placed it, as before this work
        self.assertEqual("software", board(cls("Business Program Manager - AI Infrastructure")))
        result = cls("Technical Program Manager, Cloud Supply Chain")
        self.assertEqual(("product", "technical_pm"), (board(result), result["subcategory"]))

    def test_production_and_training_infrastructure_are_tech_work(self):
        for title, ctype in (("Program Manager, Production Infrastructure", "unknown"),
                             ("Program Manager, Model Training Infrastructure", "ai_lab")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("product", "technical_pm"), (board(result), result["subcategory"]), title)

    def test_student_program_titles_are_apm_and_programs(self):
        """R7: the program claims set their own filter, so a student title has its own claims."""
        for title, kw, rule in (("Technical Program Manager Intern, Cloud Infrastructure", {},
                                 "program_over_topic_student"),
                                ("Program Management Intern", {"description": TECH}, "program_tech_evidence_student")):
            result = cls(title, **kw)
            self.assertEqual(("product", "apm_programs", rule),
                             (board(result), result["subcategory"], result.get("rule")), title)


class DeveloperTeamTests(unittest.TestCase):
    """R2: 'developer' as the team (Developer Experience, Platform, Tools) is no engineer."""

    def test_developer_team_pms_and_tpms_go_to_product(self):
        for title, rule in (("Product Manager, Developer Platform", "pm_over_topic"),
                            ("Staff Product Manager - Developer Productivity", "pm_over_topic"),
                            ("Technical Program Manager, Developer Velocity", "program_over_topic")):
            result = cls(title)
            self.assertEqual(("product", rule), (board(result), result.get("rule")), title)

    def test_a_developer_occupation_stays(self):
        for title in ("Software Developer, Product Management Tools", "Java Developer - Product Management Tools",
                      "Full Stack Developer - Program Management Systems", "Salesforce Developer - Product Owner Team"):
            result = cls(title)
            self.assertEqual("software", board(result), title)
            self.assertNotIn("rule", result, title)


class NonProductWorkTests(unittest.TestCase):
    """R4: life-science marketing PMs, drug-development product leads, fielded product operations, NPI product
    operations and jobs that only name the PM team leave Product."""

    def test_life_science_marketing_product_managers_go_to_sales(self):
        for title, ctype, rule in (("Product Manager, Trauma Marketing", "medtech", "medtech_marketing_pm"),
                                   ("Field Product Manager - Eastern U.S. (Territory-Based Role)", "medtech",
                                    "medtech_marketing_pm"),
                                   ("Product Manager, HIV Treatment Marketing", "pharma", "life_science_marketing_pm"),
                                   ("Associate Product Manager - Oncology", "pharma", "life_science_marketing_pm")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("sales", rule), (board(result), result.get("rule")), title)

    def test_digital_and_clinical_area_product_managers_stay(self):
        for title, ctype in (("Product Manager, Interventional Cardiology (ICVT)", "medtech"),
                             ("Downstream Product Manager, Digital Solutions (Hybrid)", "medtech"),
                             ("Oncology Data Product Manager", "pharma"),
                             ("Product Manager, Trauma Marketing", "consumer_tech"),
                             # upstream marketing is product work; systems, web, tools and assays are products
                             ("Product Manager, Upstream Marketing – Advanced Imaging", "medtech"),
                             ("Upstream Product Manager, Electrophysiology", "pharma"),
                             ("Product Manager, Marketing Technology", "pharma"),
                             ("Product Owner, Brand Websites", "pharma"),
                             ("Business Product Manager – Territory & Roster Management", "pharma"),
                             ("Product Manager, Oncology Assays", "biotech")):
            self.assertEqual("product", board(cls(title, company_type=ctype)), (title, ctype))

    def test_drug_development_product_leads_go_to_healthcare(self):
        for title, ctype in (("Analytical LCM Product Lead - Biologics", "pharma"),
                             ("Manager, Global Labeling Product Leader", "pharma"),
                             ("Senior Regulatory CMC Drug-Device Combination Product Lead", "pharma"),
                             ("Regulatory Affairs Associate, Product Management", "medtech")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("healthcare", "drug_development_product_lead"), (board(result), result.get("rule")),
                             title)
        self.assertEqual("product", board(cls("Scientific Digital Product Lead, Assay Workflows", company_type="pharma")))

    def test_fielded_and_npi_product_operations_go_to_operations(self):
        for title, kw in (("Product Operations Technical Specialist, Counter Intrusion", {}),
                          ("Product Operations Manager, Maritime",
                           {"department": "Mission Readiness : Customer Support : Product Operations"}),
                          ("New Product Operations Program Manager, Mac", {"company_type": "big_tech"}),
                          ("Staff Program Manager – Product Operations & NPI", {})):
            self.assertEqual("operations", board(cls(title, **kw)), title)
        result = cls("Product Operations Manager", company_type="gaming")
        self.assertEqual(("product", "product_ops"), (board(result), result["subcategory"]))

    def test_jobs_that_name_the_pm_team_leave_product(self):
        for title in ("HR Manager - Product Management", "Forward Deployed Engineer, Agentic Product Management",
                      "Sr. Product Development Engineer - Product Operations"):
            self.assertNotEqual("product", board(cls(title)), title)
        self.assertEqual("people_legal", board(cls("HR Manager - Product Management")))
        # an administrative business partner is on "other", as the other administrative business partners are
        self.assertEqual("other", board(cls("Administrative Business Partner, YouTube Product Management",
                                            company_type="big_tech")))
        self.assertEqual("product", board(cls("Product Operations Engineer Intern")))
        # Cisco's Product Management Engineer is the occupation, with or without a separator after it
        for title in ("Principal Product Management Engineer",
                      "Principal Product Management Engineer | Datacenter, Networking and AI"):
            self.assertEqual("product", board(cls(title, company_type="big_tech")), title)

    def test_design_program_managers_go_to_design(self):
        for title in ("UX Program Manager, Payments Platform", "Staff UX Program Manager, Cloud AI",
                      "Program Manager III, Material Design, Google Design Platform"):
            result = cls(title, company_type="big_tech")
            self.assertEqual(("design", "design_occupation"), (board(result), result.get("rule")), title)


class ProductFilterTests(unittest.TestCase):
    """R6 to R8: Technical PM, APM & Programs and Product Management read the forms they missed."""

    def assertFilter(self, expected, title, company_type="unknown"):
        result = cls(title, company_type=company_type)
        self.assertEqual(("product", expected), (board(result), result["subcategory"]), (title, result["evidence"]))

    def test_technical_pm_reads_the_qualifier_after_the_title_and_technical_product_owners(self):
        for title, ctype in (("Product Manager - Technical", "big_tech"), ("Sr. Product Manager - Tech, India Ads", "big_tech"),
                             ("Technical Product Owner", "unknown"), ("Engineering Product Manager", "big_tech")):
            self.assertFilter("technical_pm", title, ctype)
        self.assertFilter("product_management", "Product Manager, Technical Risk", "global_bank")

    def test_student_product_titles_are_apm_and_programs(self):
        for title in ("Product Owner Intern", "AI Product Builder Intern", "Technical Program Manager Intern",
                      "Junior Product Manager", "Product Manager AI Assistant – Stage (6 mois) Janvier 2027 (F/H/NB)"):
            self.assertFilter("apm_programs", title)
        self.assertFilter("product_management", "Senior Associate Product Manager", "commercial_bank")

    def test_one_title_scores_a_filter_once_and_business_networks_are_no_tech(self):
        self.assertFilter("technical_pm", "Director of Product Management, Security")
        self.assertFilter("product_management", "Director, Product Management- Global Payment Network", "fintech")
        self.assertFilter("product_management", "Product Analyst, Salesforce")
        self.assertFilter("product_analytics", "Senior Product Analyst", "gaming")


class ProductStageTests(unittest.TestCase):
    """R9: Product's levels read the forms that fell to the shared rules."""

    def test_stages(self):
        for title, expected in (("Product Operations Manager", "experienced"), ("Product Owner", "experienced"),
                                ("Product Owner I", "entry"), ("Product Builder I", "entry"),
                                ("Assistant Vice President, Product Manager", "experienced"),
                                ("AVP, Product Management", "experienced"),
                                ("Technical Program Manager 5", "senior"), ("Product Manager 4", "senior"),
                                ("Product Manager 2", "experienced"), ("Senior Product Associate", "experienced"),
                                ("Mission Operations Product Manager, Group 5 Mission Autonomy", "experienced"),
                                ("Group Product Manager", "senior"), ("Product Manager-in-Training", "entry"),
                                ("Jr Product Manager", "new_grad"), ("Snr Technical Program Manager", "senior"),
                                ("Dir, Product Management", "senior"), ("CVP, Product Management", "senior"),
                                ("Principle Product Manager", "senior"),
                                ("Working Student (f/m/d) – Quote to Cash Product Management", "internship"),
                                ("Controls Room – Product Owner - Associate", "experienced"),
                                ("Associate Product Manager (starting summer 2027)", "entry"),
                                ("Associate Engineering Product Manager-Robot Data Systems", "entry"),
                                ("Jr Product Owner - 2027 Summer Internship (Chicago Hybrid)", "internship"),
                                ("Associate, Private Equity Product Manager - Data & Technology Solutions",
                                 "experienced"), ("Associate, Product Manager", "experienced"),
                                ("Associate Digital Product Manager", "entry"),
                                ("Product Manager - 6 Month Contract", "experienced"),
                                ("Product Manager - 3 Openings", "experienced"),
                                ("Software Product Manager - Level 4", "senior"),
                                ("Product Manager, Level 5", "senior"),
                                ("Dir, Product Manager", "senior"), ("CVP, Product Manager", "senior"),
                                # PL7: a people manager's form stays Senior
                                ("Manager, Product Management", "senior")):
            self.assertEqual(expected, stage(title, "product"), title)


class ProductTitleVariantTests(unittest.TestCase):
    """R3 and R5: product titles no word read come to Product from "other" and the boards other than Finance;
    Finance keeps its own."""

    def test_variants_come_to_product_with_a_filter(self):
        for title, ctype, expected in (("Product Line Manager", "unknown", "product_management"),
                                       ("Director, Product", "unknown", "product_management"),
                                       ("Product Director", "consumer_tech", "product_management"),
                                       ("Member of Product Staff", "ai_lab", "product_management"),
                                       ("Product & Programme Manager", "unknown", "product_management"),
                                       ("Product Sr Manager", "medtech", "product_management"),
                                       ("Senior Manager, Digital Product Delivery", "canadian_bank",
                                        "product_management"),
                                       ("Senior Product Associate, Growth Product", "bulge_bracket",
                                        "product_management"),
                                       ("Technical Programme Manager", "unknown", "technical_pm"),
                                       ("Technical Product Line Manager", "semiconductors", "technical_pm"),
                                       ("Senior Product Manger tech", "big_tech", "technical_pm"),
                                       ("Product Mgr Intern", "unknown", "apm_programs"),
                                       # group 1's full student list ('Graduate', 'Trainee', 'Alternance')
                                       ("Technology Graduate Scheme - Tech Product and Programme Management",
                                        "unknown", "apm_programs"),
                                       ("Product Line Manager Trainee", "unknown", "apm_programs"),
                                       # 'Campus Networking' names no student
                                       ("Lead Product Line Manager - Campus Networking Solutions", "big_tech",
                                        "product_management")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("product", expected, "product_title_variants"),
                             (board(result), result["subcategory"], result.get("rule")), title)

    def test_a_title_product_already_reads_keeps_its_filter(self):
        """The variants score a filter only when Product's own PM word doesn't read the title (R8)."""
        for title, ctype, expected in (("Technical Product Manager - Aladdin Product Managment, ASO", "asset_manager",
                                        "technical_pm"),
                                       ("Manager, Digital Product Operations", "fintech", "product_ops")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("product", expected), (board(result), result["subcategory"]), title)

    def test_other_work_and_finance_titles_stay(self):
        for title, ctype, expected in (("Product Line Manager - Quality", "unknown", "other"),
                                       ("Product Line Manager, Debt Products", "global_bank", "other"),
                                       ("Chief of Staff - Product Line Management", "unknown", "operations"),
                                       ("Consumer Products Senior Manager, Supply Chain", "unknown", "operations")):
            self.assertEqual(expected, board(cls(title, company_type=ctype)), title)
        self.assertEqual("design", board(cls("Art Director, Product")))
        self.assertEqual("finance", board(cls("Product Mgr, Payments", company_type="fintech")))

    def test_hw_sw_and_autonomy_program_managers_are_technical(self):
        for title, ctype in (("Senior HW Program Manager", "semiconductors"),
                             ("Compute Chipset SW Program Manager", "semiconductors"),
                             ("Senior Autonomy Program Manager", "robotics_autonomy")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("product", "technical_pm"), (board(result), result["subcategory"]), title)
        for title in ("Program Manager, SW Region", "Program Manager - SW Florida", "Program Manager, Youth Autonomy",
                      "Program Manager, HW Retail"):
            self.assertEqual("operations", board(cls(title)), title)

    def test_finance_keeps_its_product_associates_and_product_takes_visas_interns(self):
        """R5."""
        for title, ctype in (("Total Rewards Product Associate", "fintech"),
                             ("Product Associate - Business Finance Control", "bulge_bracket"),
                             ("Treasury Product Associate", "bulge_bracket")):
            self.assertEqual("finance", board(cls(title, company_type=ctype)), title)
        result = cls("Technical Product/Project Management Intern", company_type="fintech")
        self.assertEqual(("product", "apm_programs"), (board(result), result["subcategory"]))


class DesignWorkTests(unittest.TestCase):
    """R12 to R15: building, business and apparel titles leave Design; design work held elsewhere comes to it."""

    def test_building_business_apparel_and_assistant_titles_leave_design(self):
        for title, ctype in (("Data Center Design Manager", "big_tech"), ("Store Designer", "unknown"),
                             ("Study Design Lead", "pharma"), ("Compensation Design Manager", "unknown"),
                             ("Designer, Knits", "unknown"), ("Associate Designer, Home", "unknown"),
                             ("Category Associate – Design, Construction, CQV", "pharma")):
            self.assertEqual("other", board(cls(title, company_type=ctype)), title)
        self.assertEqual("operations", board(cls("Executive Assistant, Design")))
        # R14: Wells Fargo's and Apple's engineers, whom Design's claim took on the UX or interaction word
        for title, ctype in (("UI/UX Lead Software Engineer", "commercial_bank"),
                             ("Robot Interaction Engineer", "big_tech")):
            self.assertEqual("software", board(cls(title, company_type=ctype)), title)

    def test_product_designers_keep_design_whatever_their_product(self):
        for title, ctype in (("Senior Product Designer, Home", "big_tech"),
                             ("Product Designer - Contract - Design Systems", "unknown"),
                             ("Product Designer, Plan Design Tools", "unknown"),
                             ("Product Designer, Robotics", "big_tech"), ("UX Designer, Robotics", "robotics_autonomy")):
            self.assertEqual("design", board(cls(title, company_type=ctype)), title)

    def test_design_work_comes_to_design(self):
        for title, ctype, expected in (("Industrial Design Engineer", "unknown", "industrial_design"),
                                       ("DesignOps Manager", "unknown", "product_design"),
                                       ("Senior Illustration Lead", "unknown", "visual_brand"),
                                       ("VP, Human Centered Design", "canadian_bank", "product_design"),
                                       ("Senior Manager, Human-centered Design", "unknown", "product_design"),
                                       ("Software Signature Interface Designer", "big_tech", "product_design"),
                                       ("Game Designer (Mobile)", "gaming", "game_design"),
                                       ("Technical Interface Designer - EA SPORTS FC", "gaming", "game_design"),
                                       ("Product Researcher", "big_tech", "ux_research"),
                                       ("Researcher, Figma Design", "enterprise_saas", "ux_research")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("design", expected), (board(result), result["subcategory"]), title)
        result = cls("Design Engineer", department="Design")
        self.assertEqual(("design", "design_engineering"), (board(result), result["subcategory"]))

    def test_not_design_work(self):
        self.assertNotEqual("design", board(cls("Policy Illustration Lead")))
        self.assertNotEqual("design", board(cls("Design Engineer", department="Mechanical Design")))
        for title, ctype in (("Illustration Analyst", "insurance"), ("Illustration Systems Analyst", "insurance")):
            self.assertEqual("finance", board(cls(title, company_type=ctype)), title)
        for title, ctype in (("Researcher, Chip Design", "semiconductors"), ("Researcher, Protein Design", "ai_lab")):
            self.assertNotEqual("design", board(cls(title, company_type=ctype)), title)


class MagnaTests(unittest.TestCase):
    """R14, your yes: Magna is a vehicle and robotics supplier, so its design engineers are Hardware's."""

    def test_magna_is_typed_robotics_autonomy(self):
        from intel.companies import resolve_company
        resolved = resolve_company("Magna", KN)
        self.assertEqual(("magna", "robotics_autonomy"), (resolved["key"], resolved["type"]))

    def test_its_design_engineers_go_to_hardware(self):
        for title in ("Engineer, Design", "Senior Design Engineer"):
            self.assertEqual("hardware", board(cls(title, company_type="robotics_autonomy")), title)


class EngineeringDesignerTests(unittest.TestCase):
    """R11 and R20: engineering designers are Hardware's; business and building titles are not."""

    def test_engineering_designers_and_design_leads_go_to_hardware(self):
        for title, ctype in (("Electronics Designer, Space", "unknown"), ("HVAC Designer", "hardware_devices"),
                             ("Engineer - Design Lead", "pharma"), ("Manufacturing Tool Designer", "defense_tech"),
                             ("F135 Base High-Pressure Compressor Design Intern (Summer 2027) (Onsite)", "defense_tech"),
                             ("iPhone Product Design Lab Manager", "big_tech"),
                             ("Building Automation Controls Designer", "unknown")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("hardware", "hardware_designer"), (board(result), result.get("rule")), title)

    def test_building_and_ux_titles_stay_off_hardware(self):
        self.assertEqual("design", board(cls("UX Designer, Controls")))
        # R12: building design is no board's until the AEC board takes it
        self.assertEqual("other", board(cls("Construction Engineering Design Manager", company_type="semiconductors")))
        for title in ("Interior Design Architect", "Lab IT Compute Architect / Solution Designer",
                      "Technical Architect – Application Design & AI Engineering"):
            self.assertNotEqual("hardware", board(cls(title)), title)
        self.assertEqual("hardware", board(cls("RF Application Design Engineer", company_type="semiconductors")))


class DesignFilterTests(unittest.TestCase):
    """R17: Design's filters read reversed visual words, vehicle studios, research orders and game studios."""

    def assertFilter(self, expected, title, company_type="unknown"):
        result = cls(title, company_type=company_type)
        self.assertEqual(("design", expected), (board(result), result["subcategory"]), (title, result["evidence"]))

    def test_filters(self):
        for expected, title, ctype in (("visual_brand", "Senior Designer, Brand Marketing", "unknown"),
                                       ("visual_brand", "Production Designer", "unknown"),
                                       ("product_design", "Senior Product Designer, Marketing Tools", "unknown"),
                                       ("industrial_design", "Class A - Surface Designer", "robotics_autonomy"),
                                       ("industrial_design", "Transportation Design Intern", "unknown"),
                                       ("ux_research", "CX Researcher & Information Designer", "unknown"),
                                       ("game_design", "Lead Systems Designer", "gaming")):
            self.assertFilter(expected, title, ctype)

    def test_a_game_studios_quality_designers_are_qa(self):
        result = cls("Quality Designer II", company_type="gaming")
        self.assertEqual(("software", "qa_test"), (board(result), result["subcategory"]))


class DesignStageTests(unittest.TestCase):
    """R18: Design's levels."""

    def test_stages(self):
        for title, expected in (("Senior Associate, Art Director", "experienced"),
                                ("Returning New Grad Graphic Designer I (For current/previous HNTB interns ONLY)",
                                 "new_grad"),
                                ("Jr. Designer (Design Engineering)", "new_grad"), ("Assoc Designer", "entry"),
                                ("Ausbildung zum Technical Product Designer (m/w/d)", "new_grad")):
            self.assertEqual(expected, stage(title, "design"), title)


class SharedStageTests(unittest.TestCase):
    """R10: the shared stage words (every board's, Finance's too), and the student words in Product's and Design's
    own levels only, so Finance's Working Student postings keep their stage."""

    def test_shared_rules(self):
        for title, expected in (("Research Internships", "internship"),
                                ("New College Grad - DRAM Design Engineer", "new_grad"),
                                ("Software Engineer (NCG)", "new_grad"),
                                ("Career Accelerator Program - Product Marketing Engineer", "new_grad"),
                                # real programs stay new-grad programs (a Finance title among them)
                                ("Leadership Development Program", "new_grad"),
                                ("Finance Development Program Analyst", "new_grad"),
                                ("Analyst Development Program", "new_grad"),
                                # Finance stays identical: its analyst-program titles read as on main
                                ("Oracle Health Federal Risk Analyst Program Manager", "new_grad"),
                                # a program's manager is a manager
                                ("Director Development Program Management (Hematology)", "senior"),
                                ("IC Development Program Manager", "senior"),
                                ("Leadership Development Program Manager", "senior"),
                                ("Analyst Development Program Manager", "senior"),
                                ("Rotational Development Program Manager", "senior"),
                                ("Career Accelerator Program Manager", "senior")):
            with self.subTest(title=title):
                self.assertEqual(expected, detect_seniority(title)["stage"])

    def test_product_and_design_levels_let_the_new_grad_words_through(self):
        for title, family, expected in (("New College Grad - Product Manager, HBM", "product", "new_grad"),
                                        ("Technical Program Manager New College Grad - MS/PHD Degree", "product",
                                         "new_grad"),
                                        ("Engineering Program Management Undergrad Internships", "product",
                                         "internship"),
                                        ("Designer I, New College Grad", "design", "new_grad")):
            with self.subTest(title=title):
                self.assertEqual(expected, stage(title, family))

    def test_student_words_in_product_and_design_levels(self):
        for title, family in (("Engineering Student - Product Management", "product"),
                              ("Working Student (f/m/d) – Quote to Cash Product Management", "product"),
                              ("Working Student UX Design (m/f/d)", "design"),
                              ("Engineering Student - Industrial Design", "design")):
            with self.subTest(title=title):
                self.assertEqual("internship", stage(title, family))
        # the staff of student programs are no students
        for title, family in (("Program Manager, Engineering Student Programs", "product"),
                              ("Engineering Student Recruiter", "product"), ("Working Student Coordinator", "design")):
            with self.subTest(title=title):
                self.assertNotEqual("internship", stage(title, family))
        # the shared rules don't read them, so Finance's Working Student postings keep their stage
        self.assertNotEqual("internship", detect_seniority("Working Student - Finance (m/w/d)")["stage"])


class HardwareFilterTests(unittest.TestCase):
    """R19: Hardware's filters read the chip and board designers; titles Hardware held before keep their filter."""

    def test_filters(self):
        for expected, title in (("chip_design", "Memory Designer"), ("chip_design", "Mask Layout Designer"),
                                ("chip_design", "Senior Designer , IC Layout"), ("electrical", "PCB Layout Designer"),
                                ("electrical", "Substation Physical Designer"), ("electrical", "Staff Board Designer"),
                                ("electrical", "Principal Analog IC Designer"),
                                ("electrical", "Analog IC Layout Designer"), (None, "Hardware Designer 2")):
            self.assertEqual(expected, specialty(title, KN, "hardware")[0], title)


if __name__ == "__main__":
    unittest.main()
