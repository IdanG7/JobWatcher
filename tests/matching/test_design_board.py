"""Design: its filters, the words that bring a title to the board, the claims by which it takes titles other
boards place, and the engineering design it leaves to Hardware (plans/product-design-board.md, sections 4.2 and 4.3;
decisions D6, D8 to D14 and D16). Finance keeps every title it places, in the same filter."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile, validate_profile
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()

# Titles per filter (D16), with the employer type where they show up. Plurals land as the singular does (D14).
EXAMPLES = {
    "product_design": [("Senior Product Designer", "fintech"), ("Staff Product Designer", "unknown"),
                       ("Product Designers", "unknown"), ("Senior Product Designers", "enterprise_saas"),
                       ("UI/UX Design Intern", "unknown"), ("UI Designer", "unknown"), ("Lead UX Designer", "unknown"),
                       ("UX Designers", "unknown"), ("Interaction Designer", "big_tech"),
                       ("Product Design Manager", "commercial_bank"), ("Head of Product Design", "unknown"),
                       ("Director, Design", "unknown"), ("Design Systems Designer", "unknown"),
                       ("Senior Design Program Manager II", "unknown"), ("UX Program Manager", "unknown"),
                       ("Experience Design Vice President", "bulge_bracket")],
    "ux_research": [("UX Researcher", "unknown"), ("UX Researchers", "unknown"), ("User Researchers", "unknown"),
                    ("Senior UX Researcher, Qualitative", "unknown"), ("Staff User Researcher", "fintech"),
                    ("User Experience Research Intern, PhD, Summer 2027", "big_tech"),
                    ("Director, UX Research", "unknown"), ("Senior User Researcher", "pharma")],
    "visual_brand": [("Graphic Designer", "defense_tech"), ("Graphic Designers", "unknown"),
                     ("Senior Brand Designer", "unknown"), ("Motion Designer, CX", "big_tech"),
                     ("Creative Director", "unknown"), ("Head of Creative", "unknown"), ("Illustrator", "unknown"),
                     ("Illustrators", "unknown"), ("Multimedia Design Intern", "robotics_autonomy"),
                     ("Editorial Design Intern, Wirecutter", "consumer_tech"), ("Packaging Designer", "unknown"),
                     ("Motion Graphics Specialist", "enterprise_saas")],
    "content_design": [("Senior Content Designer", "fintech"), ("Content Designers", "unknown"),
                       ("Staff UX Writer, AI", "unknown"), ("Conversation Designer", "unknown"),
                       ("Content Strategist, Product", "unknown"), ("UX Content Strategist", "unknown")],
    "design_engineering": [("UX Engineer", "unknown"), ("Design Technologist", "unknown"),
                           ("Creative Technologist", "high_growth_startup"),
                           ("User Experience Engineer Intern", "big_tech"), ("UX Design Engineer", "unknown"),
                           ("UI Design Engineer", "unknown"), ("Web Design Engineer", "unknown")],
    "industrial_design": [("Industrial Designer", "big_tech"), ("Industrial Designers", "unknown"),
                          ("Industrial Design Intern", "unknown"), ("Head of Industrial Design", "unknown"),
                          ("CMF Designer - Color, Material, and Finish (Starlink)", "unknown"),
                          ("CMF Designer", "hardware_devices")],
    "game_design": [("Senior Game Designer", "gaming"), ("Game Designers", "gaming"), ("Level Design Intern", "gaming"),
                    ("Principal Narrative Designer", "gaming"), ("Gameplay Designer - EA SPORTS FC", "gaming"),
                    ("Level Designer, Missions", "consumer_tech")],
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
                    self.assertEqual(("design", sub), (board(result), result["subcategory"]), result["evidence"])

    def test_the_family_tree_lists_the_seven_filters_with_notes(self):
        # D16: no accessibility or human-factors filter.
        tree = {f["key"]: f for f in KN.family_tree()}["design"]
        self.assertEqual(list(EXAMPLES), [s["key"] for s in tree["subcategories"]])
        self.assertTrue(all(s["note"] for s in tree["subcategories"]))
        self.assertEqual("Product & UX Design", KN.subcategory_label("design", "product_design"))
        self.assertEqual("Game Design", KN.subcategory_label("design", "game_design"))

    def test_a_design_title_without_a_filter_word_stays_on_the_board(self):
        for title, ctype in (("Designer", "unknown"), ("Index Design R&D Team Manager, Director", "market_infrastructure"),
                             ("Entry Level Designer", "defense_tech")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("design", None), (board(result), result["subcategory"]), title)

    def test_game_systems_and_technical_designers_need_a_game_description(self):
        # D12: 'Systems Designer' and 'Technical Designer' also name controls and clinical-data work, so the filter
        # reads them from a game description, not from the title.
        game = "Design combat systems, player progression and the game economy for a live ops game in Unreal Engine."
        for title in ("Senior Systems Designer", "Technical Designer"):
            self.assertEqual(("design", "game_design"), (board(cls(title, game, "gaming")),
                                                         cls(title, game, "gaming")["subcategory"]), title)
            # R17 (14.8): a game studio leans Game Design; elsewhere the title alone names no filter.
            self.assertEqual(("design", "game_design"), (board(cls(title, company_type="gaming")),
                                                         cls(title, company_type="gaming")["subcategory"]), title)
            self.assertNotEqual("game_design", cls(title, company_type="medtech")["subcategory"], title)
        # 'Entry Level Design' is not level design.
        result = cls("Entry Level Design and Analysis Engineer (Support Equipt Design - Elect)", company_type="defense_tech")
        self.assertNotEqual("design", board(result))

    def test_design_engineering_also_targets_softwares_frontend(self):
        # D16: scoring only. 'UI Engineer' stays on Software and counts for a design-engineering target.
        self.assertEqual(["software.frontend"], KN.subcategories["design.design_engineering"].meta["also_targets"])
        profile = {"fields": ["design", "software"], "target_roles": ["design.design_engineering"]}
        self.assertEqual([], validate_profile(merge_profile(profile), KN))

        def role(title, target):
            result = analyze({"title": title, "company": "Acme", "posted": NOW - 3600},
                             {"fields": ["design", "software"], "target_roles": [target]}, KN, now=NOW)
            return result["classification"], {s["key"]: s for s in result["subscores"]}["role"]["points"]
        classification, points = role("UI Engineer", "design.design_engineering")
        self.assertEqual(("software", "frontend"), (classification["family"], classification["subcategory"]))
        self.assertEqual(35, points)
        self.assertLess(role("UI Engineer", "design.product_design")[1], 35)
        self.assertEqual(35, role("UX Engineer", "design.design_engineering")[1])

    def test_related_filters_earn_the_related_credit(self):
        profile = {"fields": ["design"], "target_roles": ["design.product_design"]}

        def role(title):
            result = analyze({"title": title, "company": "Acme", "posted": NOW - 3600}, profile, KN, now=NOW)
            return {s["key"]: s for s in result["subscores"]}["role"]["points"]
        self.assertEqual(35, role("Product Designer"))
        self.assertEqual(24, role("UX Researcher"))           # related to Product & UX Design
        self.assertEqual(24, role("UX Engineer"))
        self.assertEqual(12, role("Graphic Designer"))


class EngineeringDesignTests(unittest.TestCase):
    """D8: an engineer's 'design' is Hardware's; a plain 'Design Engineer' at a software employer stays on Design."""

    def assertPlaced(self, expected, title, **kw):
        result = cls(title, **kw)
        self.assertEqual(expected, (board(result), result["subcategory"], result.get("rule")), (title, result["evidence"]))
        return result

    def test_chip_and_mechanical_design_engineers_go_to_hardware(self):
        for title, ctype, sub, rule in (("Design Engineer", "semiconductors", None, "engineering_design"),
                                        ("Design Engineer", "defense_tech", None, "engineering_design"),
                                        ("Product Design Engineer", "big_tech", None, "engineering_design"),
                                        ("Senior Design Engineer, Structures", "unknown", None, "engineering_design"),
                                        ("Design and Analysis Engineer", "defense_tech", None, "engineering_design"),
                                        ("Mechanical Design Engineer", "robotics_autonomy", None, None),
                                        ("Digital Design Engineer", "semiconductors", "chip_design", None),
                                        ("Design Verification Engineer", "semiconductors", "chip_design", None),
                                        ("Principal Engineer - Digital Design", "semiconductors", "chip_design", None),
                                        ("ASIC Design Engineer", "unknown", "chip_design", None),
                                        ("RF Design Engineer", "telecom", "electrical", None),
                                        ("Memory Design Engineer", "semiconductors", None, None),
                                        ("Mask Layout Designer", "semiconductors", "chip_design", None),
                                        ("IC Layout Designer", "semiconductors", "chip_design", None),
                                        ("Analog Designer", "semiconductors", "electrical", None)):
            self.assertPlaced(("hardware", sub, rule), title, company_type=ctype)

    def test_hardware_takes_engineering_design_that_softwares_words_placed(self):
        # The design's 14 Software -> Hardware moves: a topic word put them on Software.
        for title, ctype in (("Electrical Design Engineer (Starlink Mobile)", "unknown"),
                             ("Mobile Radar Mechanical Design Engineer", "defense_tech"),
                             ("Platform Hardware Design Engineer", "unknown")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("hardware", "engineering_design"), (board(result), result.get("rule")), title)

    def test_digital_design_that_is_not_chip_design_stays_off_hardware(self):
        self.assertPlaced(("design", "visual_brand", None), "Associate Creative Director, Digital Design")
        self.assertEqual("other", board(cls("Digital Design Specialist")))

    def test_chip_board_rf_and_substation_designers_go_to_hardware(self):
        # Design's 'designer' words placed these: a chip, board, RF, photonics or substation word in the title
        # makes them Hardware's at any employer.
        for title, ctype in (("Memory System Designer and Place and Route Engineer", "semiconductors"),
                             ("DRAM PHY Designer, up to Staff", "semiconductors"), ("SoC Physical Designer", "unknown"),
                             ("Senior DFT Designer", "semiconductors"), ("Senior Designer , IC Layout", "unknown"),
                             ("Physical Designer Engineer, Synthesis/PnR", "robotics_autonomy"),
                             ("E-core CPU Design Manager", "unknown"), ("Test Chip Design Lead", "unknown"),
                             ("Senior Standard Cell Library Design Manager", "unknown"),
                             ("HW IP designer - Qualcomm - Guyancourt or Sophia, France", "semiconductors"),
                             ("Principal HW/SW Co-Design", "semiconductors"), ("Staff Board Designer", "defense_tech"),
                             ("Senior Printed Circuit Board (PCB) Designer", "big_tech"),
                             ("Sr Designer, Printed Wiring Board", "diagnostics"),
                             ("Printed Circuit Board Designer for Electronic/Photonics Product Design", "hardware_devices"),
                             ("Senior Technical Staff-Design (Signal and Power Integrity)", "semiconductors"),
                             ("RF/ Millimeter Wave Design Intern", "hardware_devices"),
                             ("mm-Wave/RF System & Design Intern", "semiconductors"), ("Senior RF Antenna Designer", "unknown"),
                             ("High Speed Analog I/O designer", "semiconductors"), ("FBAR Filter Designer", "unknown"),
                             ("Senior Laser Designer", "unknown"), ("Senior Laser and SOA Designer", "unknown"),
                             ("Photonic Design Manager", "semiconductors"), ("Optical System Designer", "defense_tech"),
                             ("Media SoC Designer", "unknown"), ("Video SoC Designer", "big_tech"),
                             ("Level III RF Antenna Designer", "unknown"),
                             ("SOI Design Intern", "semiconductors"), ("CryoCMOS Design Director, Quantum", "semiconductors"),
                             ("Senior Staff Advance Packaging Designer", "semiconductors"),
                             ("IC Packaging Design Intern", "semiconductors"),
                             ("引线框架结构设计师/Lead Frame Designer", "semiconductors"),
                             ("Substation Physical Designer", "defense_tech"),
                             ("Substation Protection & Control Designer - Remote", "health_consulting")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("hardware", "hardware_designer"), (board(result), result.get("rule")), (title, ctype))

    def test_digital_memory_layout_and_packaging_designers_are_chip_roles_only_at_a_chipmaker(self):
        for title in ("Sr. Principal Digital Designer", "Memory Designer", "Senior Memory Designer", "Designer, Layout",
                      "Level II Memory Designer",
                      "Lead Designer, Layout", "Filter Design Intern (m/f/d)", "System Design Leader or Architect",
                      "Packaging Design Integration Engineer (2026 New College Graduate)"):
            result = cls(title, company_type="semiconductors")
            self.assertEqual(("hardware", "designer_at_chipmaker"), (board(result), result.get("rule")), title)
        for title, ctype in (("Digital Designer", "consumer_tech"), ("Associate Digital Designer", "unknown"),
                             ("Packaging Designer", "consumer_products"), ("Digital Designer, CNN", "consumer_tech")):
            self.assertEqual("design", board(cls(title, company_type=ctype)), (title, ctype))

    def test_design_occupations_that_name_a_hardware_word_stay_on_design(self):
        # 'IC' is an individual contributor in parentheses; a UX, visual, industrial or game word names design work.
        for title, ctype in (("Senior Manager (IC), Product Designer", "commercial_bank"),
                             ("Spring 2027: HW UX/UI Design Co-op (January through June)", "consumer_products"),
                             ("Senior Industrial Designer, Packaging Experience", "hardware_devices"),
                             ("Team Lead Level Designer [Splinter Cell Remake]", "gaming"),
                             ("UX/UI Designer", "semiconductors"), ("Senior Multimedia Designer", "semiconductors"),
                             ("Manager Multimedia Design, Motion Design", "semiconductors"),
                             ("Web Marketing Program - User Experience Design", "semiconductors"),
                             ("Senior Digital Designer, Design Systems", "semiconductors"),
                             ("Digital Product Design Intern", "semiconductors"), ("Laser Show Designer", "unknown")):
            self.assertEqual("design", board(cls(title, company_type=ctype)), (title, ctype))

    def test_a_plain_design_engineer_at_a_software_employer_is_design(self):
        for title, ctype in (("Design Engineer", "developer_tools"), ("Design Engineer, III", "developer_tools"),
                             ("Design Engineer", "fintech"), ("Staff Design Engineer", "consumer_tech"),
                             ("Senior Design Engineer", "enterprise_saas"), ("Design Engineer, Brand Studio", "fintech")):
            self.assertPlaced(("design", "design_engineering", "design_engineer_at_software"), title, company_type=ctype)

    def test_other_design_engineers_at_software_employers_stay_engineers(self):
        for expected, title, ctype in (("software", "Design Engineer, iOS", "big_tech"),
                                       ("software", "Wireless MAC Design Engineer", "big_tech"),
                                       ("software", "Software Design Engineer", "unknown"),
                                       ("software", "Design Engineer", "unknown"),
                                       ("hardware", "Design Engineer", "robotics_autonomy")):
            self.assertEqual(expected, board(cls(title, company_type=ctype)), (title, ctype))

    def test_ui_engineers_and_programmers_go_to_software(self):
        # D10: no bare 'ui'.
        for title, ctype, sub in (("UI Engineer", "unknown", "frontend"), ("Senior UI Engineer", "big_tech", "frontend"),
                                  ("UI Developer", "unknown", "frontend"), ("UI Programmer", "gaming", None)):
            result = cls(title, company_type=ctype)
            self.assertEqual(("software", sub), (board(result), result["subcategory"]), title)
        self.assertEqual("other", board(cls("Game UI Artist", company_type="gaming")))

    def test_network_solution_and_data_center_design_leave_design(self):
        # D11: network and solution designers are released.
        for title, ctype in (("Network Design Engineer", "telecom"), ("Solutions Design Architect", "enterprise_saas"),
                             ("Data Center Design Engineer", "big_tech"),
                             ("Design Engineer - Access (Network Designer III) (Government)", "telecom")):
            self.assertEqual("software", board(cls(title, company_type=ctype)), title)
        for title, ctype in (("Network Designer", "canadian_tech"), ("Senior Network Designer", "defense_tech"),
                             ("Network Site Design Intern", "defense_tech"), ("Solutions Design IT Specialist", "unknown")):
            self.assertEqual("other", board(cls(title, company_type=ctype)), title)


class TitleWordTests(unittest.TestCase):
    """D10, D11 and D14: Design's words, with their exclusions inside the patterns."""

    def test_marketing_creative_roles_leave_design(self):
        for expected, title in (("sales", "Creative Strategist, Brand Partnerships"), ("other", "Creative Producer"),
                                ("other", "Copywriter"), ("other", "Senior Creative Project Manager"),
                                ("operations", "Creative Operations Manager")):
            self.assertEqual(expected, board(cls(title)), title)

    def test_the_kept_creative_words_stay(self):
        for title, sub in (("Creative Director", "visual_brand"), ("Head of Creative", "visual_brand"),
                           ("Brand Creative Lead", "visual_brand"), ("Creative Technologist", "design_engineering")):
            result = cls(title)
            self.assertEqual(("design", sub), (board(result), result["subcategory"]), title)

    def test_instructional_cad_and_interior_designers_leave_design(self):
        for title, ctype in (("Instructional Designer", "unknown"), ("Instructional Designer", "hospital"),
                             ("Senior Instructional Designer", "enterprise_saas"),
                             ("Learning Experience Designer", "unknown"), ("eLearning Designer", "unknown"),
                             ("Curriculum Designer", "unknown"), ("CAD Designer", "unknown"),
                             ("Interior Designer", "unknown"), ("Intermediate Interior Designer", "unknown")):
            self.assertEqual("other", board(cls(title, company_type=ctype)), title)

    def test_vehicle_interior_designers_are_industrial_design(self):
        result = cls("Senior Interior Designer", company_type="robotics_autonomy")
        self.assertEqual(("design", "industrial_design", "vehicle_interior_designer"),
                         (board(result), result["subcategory"], result.get("rule")))

    def test_recruiters_leave_design(self):
        for title in ("Design Recruiter", "Technical Recruiter, Design", "Recruiter - Design"):
            self.assertEqual("people_legal", board(cls(title)), title)

    def test_a_plain_designer_at_an_engineering_employer_stays(self):
        # D11: 31 open postings; no licences block.
        for ctype in ("semiconductors", "defense_tech", "unknown"):
            self.assertEqual(("design", None), (board(cls("Designer", company_type=ctype)),
                                                cls("Designer", company_type=ctype)["subcategory"]), ctype)
        self.assertEqual("design", board(cls("Designer II", company_type="defense_tech")))

    def test_technical_and_tooling_words_stay_excluded_from_the_plurals(self):
        # D13 and D14: RTX's and Blue Origin's titles do not move in.
        for title, ctype in (("Aerospace Technical Writer & Illustrator", "defense_tech"),
                             ("Technical Illustrator", "unknown"),
                             ("Senior Lunar Manufacturing Tooling Designers", "defense_tech"),
                             ("Tooling Designer", "unknown")):
            self.assertEqual("other", board(cls(title, company_type=ctype)), title)

    def test_cmf_counts_only_as_cmf_design(self):
        self.assertEqual("software", board(cls("CMF Engineer", company_type="hardware_devices")))


class ClaimTests(unittest.TestCase):
    """D13: a design occupation that another board's word placed; art directors outside game studios."""

    def assertClaimed(self, title, sub, rule, **kw):
        result = cls(title, **kw)
        self.assertEqual(("design", sub, rule), (board(result), result["subcategory"], result.get("rule")),
                         (title, result["evidence"]))

    def test_designers_leave_softwares_topic_words(self):
        for title, ctype, sub in (("Mobile Product Designer", "big_tech", "product_design"),
                                  ("Senior Product Designer, Platform", "enterprise_saas", "product_design"),
                                  ("Product Designer, Cloud", "big_tech", "product_design"),
                                  ("Staff Content Designer, UX Platform", "consumer_tech", "content_design"),
                                  ("Senior UX Engineer, Cloud Learning Services", "big_tech", "design_engineering")):
            self.assertClaimed(title, sub, "design_occupation", company_type=ctype)

    def test_a_design_department_is_evidence(self):
        self.assertClaimed("Senior UI Designer (f/m/d) for medical software products", "product_design",
                           "design_occupation", company_type="medtech", department="Experience Design")

    def test_without_evidence_the_topic_board_keeps_the_title(self):
        self.assertEqual(("software", "mobile"), (board(cls("Mobile Product Designer")),
                                                  cls("Mobile Product Designer")["subcategory"]))
        self.assertEqual("healthcare", board(cls("Senior UI Designer (f/m/d) for medical software products",
                                                 company_type="medtech")))

    def test_art_directors_join_design_except_at_game_studios(self):
        for title, ctype in (("Art Director", "consumer_tech"), ("Lead Art Director", "enterprise_saas"),
                             ("Art Directors", "unknown"), ("Senior Art Director (Contract)", "fintech"),
                             ("Senior Art Director - Social", "design_studio"), ("Art Director", "consumer_products")):
            self.assertClaimed(title, "visual_brand", "art_direction", company_type=ctype)
        for title in ("Art Director", "Senior Art Director"):
            self.assertEqual("other", board(cls(title, company_type="gaming")), title)

    def test_no_hardware_title_moves_to_design(self):
        result = cls("Associate Packaging Designer, Amazon Robotics", company_type="big_tech")
        self.assertEqual(("hardware", "robotics_autonomy"), (board(result), result["subcategory"]))
        self.assertEqual("hardware", board(cls("Mechanical Product Designer", company_type="hardware_devices")))


class FinanceTests(unittest.TestCase):
    """D6 and D9: V3's Design half leaves Finance; every other Finance title keeps its filter."""

    def assertClaimed(self, title, sub, **kw):
        result = cls(title, **kw)
        self.assertEqual(("design", sub, "design_occupation"),
                         (board(result), result["subcategory"], result.get("rule")), (title, result["evidence"]))

    def test_quantitative_ux_researchers_leave_quant(self):
        for title, ctype in (("UX Researcher, Quantitative", "big_tech"),
                             ("Quantitative UX Researcher, Customer Engagement", "big_tech"),
                             ("Staff Quantitative UX Researcher", "consumer_tech")):
            self.assertClaimed(title, "ux_research", company_type=ctype)
        self.assertClaimed("Quantitative User Researcher", "ux_research", company_type="big_tech", department="Hardware")
        self.assertClaimed("2027 Summer Intern, MS/PhD, Quantitative UX Researcher, Growth/International Expansion",
                           "ux_research", description="Run surveys and A/B experiments on user behavior, with "
                                                      "usability studies, user interviews and mixed methods research.")

    def test_bank_design_roles_leave_finance(self):
        for title, ctype in (("Experience Design Vice President- Business Banking", "bulge_bracket"),
                             ("Product Design Director - Risk Design", "commercial_bank"),
                             ("Risk UX Specialist", "fintech")):
            self.assertClaimed(title, "product_design", company_type=ctype)
        self.assertClaimed("Sr. Manager, Product Design, IT Asset Management", "product_design",
                           department="User Experience Design")

    def test_without_evidence_quant_keeps_the_title(self):
        result = cls("Quantitative UX Researcher")
        self.assertEqual(("finance", "quant"), (board(result), result["category"]))

    def test_main_design_words_keep_their_titles_off_finance(self):
        # D9: Design's claim on main's bare words keeps these on Design, so Finance stays identical.
        for title, ctype in (("Learning Experience Designer - Talent Enablement (Instructional Designer) (Commercial & "
                              "Investment Bank)", "bulge_bracket"),
                             ("Principal Associate, Learning Experience Designer", "commercial_bank"),
                             ("Assessment & Design Sr. Lead Analyst - C14 - SINGAPORE", "bulge_bracket"),
                             ("Senior Associate Solutions Designer, Automation", "fintech")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("design", "design_words_from_finance"), (board(result), result.get("rule")), title)
        for title in ("Payments-Digital & Design-Senior Product Associate",
                      "Payments Digital & Design Business Manager – Senior Associate"):
            self.assertEqual("design", board(cls(title, company_type="bulge_bracket")), title)

    def test_sp_index_design(self):
        result = cls("Equities & Digital Assets R&D Associate Director, Index Design", company_type="market_infrastructure")
        self.assertEqual(("finance", "markets", "equities"), (board(result), result["category"], result["subcategory"]))
        result = cls("Index Design R&D Team Manager, Director", company_type="market_infrastructure")
        self.assertEqual(("design", None), (board(result), result["subcategory"]))

    def test_finance_titles_naming_design_or_creative_keep_their_filter(self):
        for title, ctype, category, sub in (
                ("Market Risk Stress Testing and Scenario Design", "asset_manager", "risk", "market_risk"),
                ("Manager, Insurance Product and Benefit Design", "unknown", "insurance", None),
                ("Asset & Wealth Management, Head of Creative / Integrated Marketing, Senior Vice President",
                 "bulge_bracket", "wealth", "wealth_management"),
                ("Asset & Wealth Management, PWM, Brand Marketing and Creative Strategy, Vice President  - New York - "
                 "2027", "bulge_bracket", "wealth", "wealth_management"),
                ("J.P. Morgan Wealth Management - Senior Associate, Client Pricing Strategy & Design Lead",
                 "bulge_bracket", "wealth", "wealth_management"),
                ("Senior Design Manager - Business Banking & Investments", "fintech", "banking", "commercial_banking"),
                ("Client Segment Risk Conduct, Controls & Governance - Control Design - Vice President", "bulge_bracket",
                 "risk", None),
                ("Operations Risk Control Architecture Design", "bulge_bracket", "risk", None),
                ("Senior Financial Analyst, Store Design & Renewal", "canadian_tech", "corporate_finance", "fpa"),
                ("Senior Treasury Manager, Creative Media & Technology", "canadian_bank", "corporate_finance", "treasury"),
                ("UX Quantitative Research Intern (USA)", "unknown", "quant", "quant_research"),
                ("UX Researcher, Wealth Management", "unknown", "wealth", "wealth_management")):
            result = cls(title, company_type=ctype)
            self.assertEqual(("finance", category, sub), (board(result), result["category"], result["subcategory"]),
                             title)


if __name__ == "__main__":
    unittest.main()
