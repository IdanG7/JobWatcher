"""Product and Design's own track: what it shares with tech, its employer types and its skills
(plans/product-design-board.md 6.1, 6.2 and 9.5; decisions D24, D25 and D42). Every other board's employers, points
and skills stay as they were."""
import time
import unittest

from intel import load_knowledge, merge_profile, score_job
from intel.facts import build_facts
from intel.skills import extract_skills
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()
SHARED = ("big_tech", "consumer_tech", "enterprise_saas", "high_growth_startup")
OWN = ("design_studio", "consumer_products")


def company_points(ctype, fields, target_types=()):
    """The Company row of the fit breakdown at an employer of this type, for a first run's profile on these boards."""
    facts = build_facts({"title": "Product Designer", "company": "Acme", "location": "Toronto, ON"}, KN)
    facts["company"] = {**facts["company"], "type": ctype, "type_label": KN.type_label(ctype), "known": True}
    profile = merge_profile({"fields": list(fields), "target_roles": [f for f in fields if f != "finance"],
                             "target_company_types": list(target_types)})
    row = {s["key"]: s for s in score_job(facts, profile, KN, {}, NOW)["subscores"]}["company"]
    return row["points"], row["detail"]


class TrackTests(unittest.TestCase):
    def test_product_and_design_share_one_track_and_still_read_tech_skills(self):
        track = KN.tracks["product_design"]
        self.assertEqual(("Product & Design", "Product & Design employer types", "recognized product and design employer"),
                         (track.label, track.employer_heading, track.employer_noun))
        self.assertEqual(["product", "design"], KN.track_boards["product_design"])
        # AEC postings read P&D skills too (Rhino, SketchUp, Adobe), as AEC resumes do (plans/aec-board.md 9).
        self.assertEqual({"product", "design", "aec"}, track.skills_from)
        self.assertTrue(track.resume)
        for board in ("product", "design"):
            self.assertEqual("product_design", KN.board_track[board])
            self.assertEqual(frozenset({"tech", "product_design"}), KN.skill_tracks(board))
        # Tech's other boards, Healthcare and Finance read no P&D skill.
        self.assertEqual(frozenset({"tech"}), KN.skill_tracks("software"))
        self.assertEqual(frozenset({"tech", "healthcare"}), KN.skill_tracks("healthcare"))
        self.assertEqual(frozenset(), KN.skill_tracks("finance"))

    def test_the_four_pd_types_stay_tech_and_the_new_ones_are_pd_only(self):
        for ctype in SHARED:
            self.assertEqual(["tech", "product_design"], KN.type_tracks(ctype), ctype)
        for ctype in OWN:
            with self.subTest(type=ctype):
                # Off the finance track, so an employer of this type lends no HQ country to a posting naming no place.
                self.assertEqual(["product_design"], KN.type_tracks(ctype))
                # Priors only on Design's and Product's filters, so they never make a title Finance or move it.
                self.assertTrue(KN.company_priors[ctype])
                self.assertTrue(all(key.split(".")[0] in {"product", "design"} for key in KN.company_priors[ctype]))
        self.assertEqual("Design Studio & Agency", KN.type_label("design_studio"))
        self.assertEqual("Consumer Products", KN.type_label("consumer_products"))
        for ctype in ("semiconductors", "gaming", "hardware_devices", "defense_tech", "health_tech", "research_lab"):
            self.assertNotIn("product_design", KN.type_tracks(ctype), ctype)

    def test_a_studio_prior_only_settles_a_design_filter_the_title_leaves_open(self):
        # A prior adds to a filter's score but never outranks a filter the title names.
        self.assertEqual(classify("Product Designer", KN)["subcategory"],
                         classify("Product Designer", KN, company_type="design_studio")["subcategory"])
        self.assertEqual("industrial_design",
                         classify("Industrial Designer", KN, company_type="consumer_products")["subcategory"])
        # A finance title at a studio stays Finance.
        self.assertTrue(classify("Financial Analyst", KN, company_type="design_studio")["is_finance"])


class CompanyPointTests(unittest.TestCase):
    def test_a_pd_profile_scores_its_four_types_as_recognized_and_other_tech_types_as_outside(self):
        # D24: 5 at the four shared types and at its own types, 3 at the other tech types (semiconductors 549
        # Product and 1,354 Design postings among them).
        for fields in (["product"], ["design"], ["product", "design"]):
            with self.subTest(fields=fields):
                self.assertEqual((5, "Big Tech — recognized product and design employer"), company_points("big_tech", fields))
                self.assertEqual((5, "Design Studio & Agency — recognized product and design employer"),
                                 company_points("design_studio", fields))
                self.assertEqual((3, "Semiconductors — outside your boards"), company_points("semiconductors", fields))
                self.assertEqual((3, "Gaming — outside your boards"), company_points("gaming", fields))
                self.assertEqual((8, "Big Tech — a target employer tier"), company_points("big_tech", fields, SHARED))

    def test_other_boards_score_the_shared_types_as_before_and_the_new_ones_as_outside(self):
        self.assertEqual((5, "Big Tech — recognized tech employer"), company_points("big_tech", ["software"]))
        self.assertEqual((5, "Semiconductors — recognized tech employer"), company_points("semiconductors", ["hardware"]))
        self.assertEqual((5, "Big Tech — recognized tech employer"), company_points("big_tech", ["software", "product"]))
        self.assertEqual((5, "Semiconductors — recognized tech employer"), company_points("semiconductors", ["software", "design"]))
        self.assertEqual((3, "Big Tech — outside finance"), company_points("big_tech", ["finance"]))
        self.assertEqual((3, "Big Tech — outside your boards"), company_points("big_tech", ["healthcare"]))
        for fields in (["software"], ["data_ml"], ["hardware"], ["healthcare"], ["finance"]):
            with self.subTest(fields=fields):
                self.assertEqual(3, company_points("design_studio", fields)[0])
                self.assertEqual(3, company_points("consumer_products", fields)[0])


class SkillTests(unittest.TestCase):
    TEXT = ("Product Designer. You will run usability testing, build wireframes and high-fidelity prototypes in Figma, "
            "and grow our design system. Experience with Adobe Creative Cloud, SolidWorks and A/B testing. SQL and Jira.")

    def test_pd_skills_are_read_only_on_pd_postings(self):
        pd = {"figma", "usability_testing", "wireframing", "prototyping", "design_systems", "adobe_cc", "solidworks",
              "ab_testing"}
        for board in ("product", "design"):
            skills = {s["key"] for s in extract_skills(self.TEXT, KN, tracks=KN.skill_tracks(board))}
            self.assertLessEqual(pd | {"sql", "agile", "jira"}, skills, board)
        for board in ("finance", "software", "hardware", "data_ml", "healthcare", "sales", "other"):
            with self.subTest(board=board):
                skills = {s["key"] for s in extract_skills(self.TEXT, KN, tracks=KN.skill_tracks(board))}
                self.assertFalse(pd & skills, board)
                self.assertIn("sql", skills)

    def test_broad_words_alone_are_no_skill(self):
        # Narrowed (9.5): a roadmap or a prototype in passing, a sketch, an illustrator's title and an EEO line.
        text = ("Hardware prototype bring-up and our technology roadmap. Sketch ideas with the team. Illustrator wanted. "
                "We provide accessibility accommodations on request.")
        skills = {s["key"] for s in extract_skills(text, KN, tracks=KN.skill_tracks("design"))}
        self.assertFalse(skills & {"roadmaps", "prototyping", "sketch_xd", "adobe_design_apps", "accessibility"}, skills)
        # CAD as Canadian dollars in a pay line is no 3D CAD, however it is spaced; CAD drawings are.
        for pay in ("Base pay: $120,000 - $170,000 CAD", "Base pay: $120,000 - $170,000  CAD", "salary 95000 CAD"):
            self.assertNotIn("cad", {s["key"] for s in extract_skills(pay, KN, tracks=KN.skill_tracks("design"))}, pay)
        self.assertIn("cad", {s["key"] for s in extract_skills("Review CAD drawings", KN, tracks=KN.skill_tracks("design"))})

    def test_pd_boards_offer_their_own_skill_groups_and_not_finances_tools(self):
        groups = {f["key"]: f["skill_groups"] for f in KN.family_tree()}
        own = {"design_tools", "research_methods", "product_tools", "industrial_tools"}
        self.assertEqual(own | {"programming", "soft"}, set(groups["product"]))
        self.assertEqual(own | {"soft"}, set(groups["design"]))
        for group in own:
            members = [s for s in KN.skills if s.group == group]
            self.assertTrue(members, group)
            self.assertTrue(all(s.track == "product_design" for s in members), group)
        self.assertIn("tools", KN.finance_skill_groups)
        self.assertEqual(["tools", "soft"], groups["sales"])


if __name__ == "__main__":
    unittest.main()
