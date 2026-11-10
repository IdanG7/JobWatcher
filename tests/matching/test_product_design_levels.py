"""Product's and Design's own career levels: their stage rules, labels and badges (plans/product-design-board.md,
section 5.4 and decisions D17 to D22). Each board's levels are read only on its own postings, so Finance and every
other board read their titles as they did."""
import time
import unittest

from intel import analyze, load_knowledge, merge_profile, score_job
from intel.facts import build_facts
from intel.seniority import detect_seniority

KN = load_knowledge()
NOW = time.time()
PRODUCT = KN.stage_rules["product"]
DESIGN = KN.stage_rules["design"]


def level(title, rules, description=""):
    return detect_seniority(title, description, board_rules=rules)


def reading(result):
    return result["level"], result["stage"], result["level_label"]


class ProductLevelTests(unittest.TestCase):
    def assertLevels(self, cases, rules=PRODUCT):
        for title, expected in cases:
            result = level(title, rules)
            self.assertEqual(expected, reading(result), title)
            self.assertTrue(result.get("board_level"), title)

    def test_a_bare_product_program_or_project_manager_is_experienced(self):
        # D17 (PL7): the occupation's 'manager' is no level word. Main reads each of these Senior.
        self.assertLevels([(t, ("pm", "experienced", "Experienced")) for t in (
            "Enterprise AI Product Manager", "Product Manager-Global Merchandising", "Technical Program Manager II, ICON",
            "SEO Product Manager", "Program Manager, Go-to-Market Experience and Productivity", "Project Manager",
            "Technical Product Managers")])
        for title in ("Enterprise AI Product Manager", "Technical Program Manager II, ICON"):
            self.assertEqual(("senior_ic", "senior"), reading(detect_seniority(title))[:2], title)

    def test_a_senior_word_or_a_people_manager_stays_senior(self):
        for title in ("Senior Product Manager", "Sr. Technical Program Manager", "Lead Product Manager",
                      "Staff Product Manager", "Group Product Manager", "Manager, Product Management",
                      "Product Manager III"):
            self.assertEqual("senior", level(title, PRODUCT)["stage"], title)
        self.assertEqual(("vp", "senior", "Vice President"), reading(level("Product Manager - Vice President", PRODUCT)))

    def test_development_program_managers_are_program_managers_not_a_development_program(self):
        # D17: main's 'development program' reads them Rotational Analyst, at new_grad.
        self.assertLevels([(t, ("pm", "experienced", "Experienced")) for t in (
            "Development Program Manager", "New Product Development Program Manager", "IC Development Program Manager")])
        # D17's optional rule: the 6 with a senior word, which PL7 skips, read Senior.
        self.assertLevels([(t, ("senior_ic", "senior", "Senior")) for t in (
            "Sr. Certification Development Program Manager", "Senior Learning & Development Program Manager",
            "Customer Service Development Program Manager IV - ETCH (E4)",
            "Senior Exam Development Program Manager, NetSuite Certification")])
        # A development program that is a cohort keeps main's reading.
        for title, expected in (("Management Development Program - Forward Deployed Product Analyst",
                                 ("rotational", "new_grad", "Rotational Analyst")),
                                ("Product Management Development Program (PMDP) Intern", ("intern", "internship", "Intern"))):
            self.assertEqual(expected, reading(level(title, PRODUCT)), title)
            self.assertNotIn("board_level", level(title, PRODUCT), title)
        self.assertEqual("principal", level("Principal Development Program Manager", PRODUCT)["level"])

    def test_early_career_pm_levels(self):
        # D18: Associate PM and PM I are Entry; APM and rotational programs and dated titles are New grad.
        self.assertLevels([
            ("Associate Product Manager", ("associate_pm", "entry", "Associate PM")),
            ("Associate Product Manager - Battery Energy Storage Systems", ("associate_pm", "entry", "Associate PM")),
            ("Associate Product Manager, BMO Global Asset Management", ("associate_pm", "entry", "Associate PM")),
            ("Associate Program Manager", ("associate_pm", "entry", "Associate PM")),
            ("Program Manager 1", ("pm_one", "entry", "Level I")),
            ("Supply Chain Program Manager I", ("pm_one", "entry", "Level I")),
            ("Treasury Product Manager I", ("pm_one", "entry", "Level I")),
            ("Associate Product Manager Program", ("new_grad_program", "new_grad", "APM Program")),
            ("Associate Product Manager - APM Program", ("new_grad_program", "new_grad", "APM Program")),
            ("New Grad 2026: Associate Product Manager (APM)", ("new_grad_program", "new_grad", "APM Program")),
            ("Rotational Product Manager", ("new_grad_program", "new_grad", "APM Program")),
            ("2027 Amazon Leadership Accelerator (ALA) - Product Manager Full Time", ("new_grad", "new_grad", "New Grad")),
            ("Product Manager Technical (PMT) - 2027", ("new_grad", "new_grad", "New Grad")),
            ("Product Management Apprentice", ("new_grad_program", "new_grad", "Apprenticeship")),
            ("Apprentice Product Manager", ("new_grad_program", "new_grad", "Apprenticeship")),
            ("PM Apprentice", ("new_grad_program", "new_grad", "Apprenticeship"))])
        # Junior stays New Grad (the shared reading), and the shared intern and new-grad words still win.
        for title, expected in (("Junior Product Manager", ("new_grad", "new_grad", "New Grad")),
                                ("Associate Product Manager Intern (APM)", ("intern", "internship", "Intern")),
                                ("Product Manager Intern", ("intern", "internship", "Intern")),
                                ("[2027] Associate Product Manager, Early Career", ("new_grad", "new_grad", "New Grad")),
                                ("Senior Program Manager, Apprenticeships", ("senior_ic", "senior", "Senior"))):
            result = level(title, PRODUCT)
            self.assertEqual(expected, reading(result), title)
            self.assertNotIn("board_level", result, title)

    def test_the_years_rule_still_wins_over_an_early_level(self):
        for title in ("Associate Product Manager", "Rotational Product Manager", "Program Manager I"):
            self.assertEqual("experienced", level(title, PRODUCT, "Requires 3+ years of experience.")["stage"], title)
            self.assertNotEqual("experienced", level(title, PRODUCT, "Requires 2+ years of experience.")["stage"], title)

    def test_campus_is_a_campus_hire(self):
        # D20: 'campus' left PL3's unless.
        self.assertLevels([("Campus - Full Time - Product Manager - 2027 (UK - London)", ("new_grad", "new_grad", "New Grad")),
                           ("Campus - Full Time - Product Manager - 2027 (UK - Burgess Hill)",
                            ("new_grad", "new_grad", "New Grad"))])
        self.assertEqual(("intern", "internship"), reading(level(
            "Campus - Internship Programme - Undergraduate - Product Manager - 2027 (UK - London)", PRODUCT))[:2])

    def test_bank_bands_are_experienced(self):
        # D19 (PL6, PL8): the corporate title after the PM title, and Capital One's mid-level band.
        self.assertLevels([
            ("Transaction Banking, Channels Product Manager, Associate", ("pm_associate_band", "experienced", "Associate")),
            ("Martech Product Manager - Associate", ("pm_associate_band", "experienced", "Associate")),
            ("Principal Associate, Product Management", ("principal_associate", "experienced", "Principal Associate"))])

    def test_french_and_german_intern_words_are_internships(self):
        # D18 (PL1): 'stage' only with 'N mois' or 'ingénieur'.
        self.assertLevels([(t, ("intern", "internship", "Intern")) for t in (
            "Product Manager AI Assistant – Stage (6 mois) Janvier 2027 (F/H/NB)", "PRODUCT MANAGER (H/F) en alternance",
            "Werkstudent (m/w/d) Global Service Marketing & Product Management", "Stagiaire Gestion de Produit",
            "Praktikum Produktmanagement")])
        for title in ("Early-Stage Product Manager", "Product Manager, Early Stage Ventures",
                      "Product Manager, Stage Gate Process"):
            self.assertEqual(("pm", "experienced"), reading(level(title, PRODUCT))[:2], title)
        # 'Product Associate Intern' is an internship, not main's Summer Associate (no MBA penalty).
        result = level("Product Associate Intern", PRODUCT)
        self.assertEqual(("intern", "internship", False), (result["level"], result["stage"], result["post_mba"]))

    def test_an_mba_internship_is_a_summer_associate(self):
        # D18: the shared Summer Associate level, keyed so, sets post_mba; a full-time MBA hire is no internship.
        for title in ("MBA Product Intern - Summer 2027", "Product Management Intern, MBA",
                      "Summer 2027 Terawave Product Management Internship - MBA", "MBA Product Management Intern",
                      "Product Management Intern (Master's/MBA)", "Product Management MBA Intern"):
            result = level(title, PRODUCT)
            self.assertEqual(("summer_associate", "internship", "Summer Associate", True, True),
                             reading(result) + (result["post_mba"], result.get("board_level")), title)
        for title in ("2027 MBA University Graduate - Product Manager", "MBA Full-Time Hire - Product Manager",
                      "Product Manager, MBA Full-Time and Internship", "Post-MBA Product Manager"):
            result = level(title, PRODUCT)
            self.assertNotEqual("summer_associate", result["level"], title)
            self.assertFalse(result["post_mba"], title)
        profile = merge_profile({"fields": ["product"], "target_roles": ["product"]})
        result = analyze({"title": "MBA Product Intern - Summer 2027", "company": "Acme", "posted": NOW - 3600},
                         profile, KN, now=NOW)
        self.assertIn("degree", {p["key"] for p in result["penalties"]})

    def test_a_team_word_before_program_manager_is_no_level(self):
        # D20: the programs the job runs, not its level.
        self.assertLevels([(t, ("pm", "experienced", "Experienced")) for t in (
            "Internship Program Manager - B4", "Early Career Program Manager", "University Program Manager",
            "Campus Program Manager", "Fellowship Program Manager", "Program Manager, Early Career Programs",
            "Technical Program Manager, University Recruiting",
            "L&D Program Manager - Early Career Onboarding and Professional Development",
            "Program Manager, Learning Enablement & Early-Career Development")])
        self.assertLevels([(t, ("senior_ic", "senior", "Senior")) for t in (
            "Vice President, Asia Early Career Program Manager - Maternity Cover 8 months Fixed Term Contract",
            "Senior University Program Manager")])
        # The posting's own level words still decide.
        for title, expected in (("2027 Early Career Technical Program Manager", ("new_grad", "new_grad")),
                                ("Technical Program Manager Intern", ("intern", "internship")),
                                ("Intern - Program Manager", ("intern", "internship")),
                                ("Program Manager Intern, University Programs", ("intern", "internship")),
                                ("Technical Program Manager, Early Career Development Program", ("rotational", "new_grad"))):
            self.assertEqual(expected, reading(level(title, PRODUCT))[:2], title)

    def test_bare_apm_and_rpm_are_left_alone(self):
        for title in ("Software Development Engineer, Amazon, APM Twitch", "Software Development Engineer, APM Insights",
                      "APM Software Team Leader", "RPM Nurse Coordinator"):
            self.assertNotEqual("new_grad_program", level(title, PRODUCT)["level"], title)
        self.assertEqual(("principal", "senior", "Principal"),
                         reading(level("Principal Product Manager, Technical, Ads , APM", PRODUCT)))

    def test_labels_change_and_stages_dont(self):
        # D21 (PL9 to PL11).
        for title, expected in (("Principal Product Manager - Technical, External Services, AWS, GenAIUX",
                                 ("principal", "senior", "Principal")),
                                ("Senior Director, Product Management", ("director", "senior", "Director")),
                                ("Director of Product", ("director", "senior", "Director")),
                                ("Head of Product Management - Artist Products", ("head", "senior", "Head / Chief")),
                                ("Chief Product Officer", ("head", "senior", "Head / Chief"))):
            result = level(title, PRODUCT)
            self.assertEqual(expected, reading(result), title)
            self.assertEqual(detect_seniority(title)["stage"], result["stage"], title)
        self.assertEqual("managing_director", level("Chief of Staff, Product", PRODUCT)["level"])


class DesignLevelTests(unittest.TestCase):
    def assertLevels(self, cases):
        for title, expected in cases:
            result = level(title, DESIGN)
            self.assertEqual(expected, reading(result), title)
            self.assertTrue(result.get("board_level"), title)

    def test_level_one_and_art_direction(self):
        # D18 (DL6) and D19 (DL3, DL5, DL7).
        self.assertLevels([
            ("Product Designer 1", ("designer_one", "entry", "Level I")),
            ("Experience Designer I - - EA SPORTS FC", ("designer_one", "entry", "Level I")),
            ("UI Production Artist 1", ("designer_one", "entry", "Level I")),
            ("Associate Art Director / Graphic Designer - Brand Team", ("associate_art_director", "entry", "Associate Art Director")),
            ("Art Director, Design", ("art_director", "experienced", "Art Director")),
            ("Art Director, Motion Design", ("art_director", "experienced", "Art Director")),
            ("Product Designer, Principal Associate Level", ("principal_associate", "experienced", "Principal Associate"))])
        self.assertEqual("senior", level("Senior Product Designer I (Remote Eligible)", DESIGN)["stage"])
        self.assertEqual(("new_grad", "new_grad", "New Grad"), reading(level("Junior Designer", DESIGN)))

    def test_labels_change_and_stages_dont(self):
        # D21 (DL2, DL4, DL8 to DL10).
        for title, expected in (("Creative Director - Brand Narrative", ("creative_director", "senior", "Creative Director")),
                                ("Associate Creative Director, Art Director", ("creative_director", "senior", "Creative Director")),
                                ("Senior Art Director, Motion Design", ("senior_art_director", "senior", "Senior Art Director")),
                                ("Manager, Creative Art Director - Retail Bank", ("senior_art_director", "senior", "Senior Art Director")),
                                ("Head of Design, Product Design", ("head", "senior", "Head / Chief")),
                                ("Director, Product Design", ("director", "senior", "Director")),
                                ("Principal Product Designer", ("principal", "senior", "Principal"))):
            result = level(title, DESIGN)
            self.assertEqual(expected, reading(result), title)
            self.assertEqual(detect_seniority(title)["stage"], result["stage"], title)

    def test_design_programs_are_new_grad(self):
        # D18: apprenticeships, residencies and fellowships, on Healthcare's keys.
        self.assertLevels([
            ("UX Design Apprenticeship", ("new_grad_program", "new_grad", "Apprenticeship")),
            ("Design Apprentice Program", ("new_grad_program", "new_grad", "Apprenticeship")),
            ("Product Design Residency", ("residency", "new_grad", "Residency")),
            ("UX Design Resident", ("residency", "new_grad", "Residency")),
            ("Fellow, Digital News Design", ("fellowship", "new_grad", "Fellowship")),
            ("Fellow, Opinion Design", ("fellowship", "new_grad", "Fellowship"))])

    def test_ranks_and_engineers_are_no_programs(self):
        # Northrop Grumman's 'Fellow 1/2' is a senior technical rank; chip and CAD apprenticeships and a resident
        # engineer aren't design programs.
        for title in ("Airframe Design for Survivability - NG Fellow 1", "System Life Cycle Design & Integration- Fellow 2",
                      "Design Fellow 2", "Technical Fellow, Design", "Senior Design Fellow", "Fellow, Design Engineering",
                      "Design Fellowship Program Manager", "Digital Design Engineer Apprenticeship",
                      "CAD / Design Support Apprenticeship",
                      "Resident Engineer – Service Provider Routing and Switching Design Consultant",
                      "Design Residency Program Manager", "Residential Interior Designer"):
            result = level(title, DESIGN)
            self.assertNotIn(result["level"], ("fellowship", "residency", "new_grad_program"), title)
            self.assertNotEqual("new_grad", result["stage"], title)

    def test_french_intern_words_and_early_stage(self):
        self.assertLevels([(t, ("intern", "internship", "Intern")) for t in (
            "Stage Level Designer - 6 mois (F/H/NB)", "Stage ingénieur : mmW IC Designer",
            "Alternant/Stagiaire - Chef de projets IA Design Change (H/F)", "Design Associate Intern")])
        for title, expected in (("Structural Design Engineer II - New Glenn Stage 2", "mid_ic"),
                                ("Creative Director, Stage 31 AFX", "creative_director"),
                                ("Early-Stage Startup Product Designer", "unspecified")):
            self.assertEqual(expected, level(title, DESIGN)["level"], title)

    def test_a_designer_with_no_level_word_is_unchanged(self):
        # D22.
        for title in ("Product Designer", "UX Designer", "Industrial Designer", "Content Designer"):
            result = level(title, DESIGN)
            self.assertEqual(("unspecified", "experienced", "Unspecified"), reading(result), title)
            self.assertNotIn("board_level", result, title)


class BoardIsolationTests(unittest.TestCase):
    def facts(self, title, company="Acme"):
        return build_facts({"title": title, "company": company}, KN)

    def test_levels_are_read_on_their_own_board(self):
        for title, board, lvl in (("Product Manager", "product", "pm"), ("Associate Product Manager", "product", "associate_pm"),
                                  ("Art Director", "design", "art_director"), ("Product Designer 1", "design", "designer_one")):
            facts = self.facts(title)
            self.assertEqual((board, lvl, True), (facts["classification"]["family"], facts["seniority"]["level"],
                                                  facts["seniority"].get("board_level")), title)

    def test_finance_and_other_boards_read_their_titles_as_before(self):
        # Product's words in a Finance or Operations title don't bring Product's levels: each reads as the shared
        # rules read it.
        for title, board in (("Program Manager, Risk", "finance"),
                             ("Head of Product Development & Strategy, BMO Global Asset Management (U.S.)", "finance"),
                             ("Investment Banking Summer Analyst", "finance"), ("Associate, Private Equity", "finance"),
                             ("Equity Research Associate", "finance"),
                             ("Program Manager", "operations"), ("Program Manager I", "operations"),
                             ("Development Program Manager", "operations"), ("Early Career Program Manager", "operations"),
                             ("Senior Software Engineer", "software"), ("Software Development Engineer, Amazon, APM Twitch", "software"),
                             ("Airframe Design for Survivability - NG Fellow 1", "other")):
            facts = self.facts(title)
            cls = facts["classification"]
            self.assertEqual(board, "finance" if cls["is_finance"] else cls["family"], title)
            self.assertNotIn("board_level", facts["seniority"], title)
            shared = detect_seniority(title, "", cls["associate_stage"], cls["category"])
            self.assertEqual(reading(shared), reading(facts["seniority"]), title)
        self.assertEqual(("senior_ic", "senior"), reading(self.facts("Program Manager, Risk")["seniority"])[:2])
        self.assertEqual("managing_director", self.facts(
            "Head of Product Development & Strategy, BMO Global Asset Management (U.S.)")["seniority"]["level"])
        # Healthcare keeps its own levels.
        self.assertEqual("residency", self.facts("PGY1 Pharmacy Resident")["seniority"]["level"])

    def test_without_board_rules_nothing_changes(self):
        for title in ("Product Manager", "Associate Product Manager", "Art Director, Design", "Product Designer 1",
                      "Principal Product Manager", "MBA Product Intern - Summer 2027", "Fellow, Digital News Design"):
            self.assertNotIn("board_level", detect_seniority(title), title)
        self.assertEqual(("senior_ic", "senior", "Senior"), reading(detect_seniority("Product Manager")))
        self.assertEqual(("vp", "senior", "Vice President"), reading(detect_seniority("Principal Product Manager")))


class BadgeTests(unittest.TestCase):
    def badges(self, title, field):
        facts = build_facts({"title": title, "company": "Acme"}, KN)
        return facts, score_job(facts, merge_profile({"fields": [field]}), KN, {}, NOW)

    def test_programs_carry_healthcares_badges(self):
        # D21: an APM program shows NEW GRAD PROGRAM, and its stage line names the program.
        for title, field, badge in (("Associate Product Manager Program", "product", "NEW GRAD PROGRAM"),
                                    ("Product Management Apprentice", "product", "NEW GRAD PROGRAM"),
                                    ("UX Design Apprenticeship", "design", "NEW GRAD PROGRAM"),
                                    ("Product Design Residency", "design", "RESIDENCY"),
                                    ("Fellow, Digital News Design", "design", "FELLOWSHIP")):
            facts, scored = self.badges(title, field)
            self.assertEqual(field, facts["classification"]["family"], title)
            self.assertIn(badge, scored["badges"], title)
        _, scored = self.badges("Associate Product Manager Program", "product")
        stage = {s["key"]: s for s in scored["subscores"]}["stage"]
        self.assertEqual((20, "APM Program — target career stage"), (stage["points"], stage["detail"]))

    def test_other_board_levels_show_no_badge(self):
        for title, field in (("Associate Product Manager", "product"), ("Product Manager", "product"),
                             ("MBA Product Intern - Summer 2027", "product"), ("Art Director", "design"),
                             ("Product Designer 1", "design")):
            _, scored = self.badges(title, field)
            self.assertFalse({"NEW GRAD PROGRAM", "RESIDENCY", "FELLOWSHIP", "SUMMER ASSOCIATE"} & set(scored["badges"]),
                             title)

    def test_an_entry_board_level_drops_in_finance(self):
        profile = merge_profile({"fields": ["product"], "target_stages": ["internship", "new_grad"]})
        result = analyze({"title": "Associate Product Manager", "company": "Acme"}, profile, KN, now=NOW)
        stage = {s["key"]: s for s in result["subscores"]}["stage"]
        self.assertEqual((16, "Associate PM — entry level"), (stage["points"], stage["detail"]))


if __name__ == "__main__":
    unittest.main()
