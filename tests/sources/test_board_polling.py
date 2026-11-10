"""What each board polls: existing boards exactly as in v0.3.11; Healthcare, Product, Design and Architecture, Engineering &
Construction from their own groups."""

import json
import unittest
from pathlib import Path

from intel import load_knowledge
from intel.sources import enabled_sources, groups_for, load_config, load_packs, polled_sources
from tools.board_gate import MIXES
from tools.source_history import boards_hash

ROOT = Path(__file__).resolve().parents[2]
V0_3_11 = json.loads(Path(__file__).with_name("board_polling_v0_3_11.json").read_text(encoding="utf-8"))
OWN_GROUPS = {"product", "design"}      # poll their own groups since D28 (plans/product-design-board.md)
OWN_FOLDERS = ("health/", "product_design/", "aec/")


class BoardPollingTests(unittest.TestCase):
    def setUp(self):
        self.kn, self.packs = load_knowledge(), load_packs()
        self.config = load_config(ROOT / "config.json")

    def polled(self, profile: dict) -> dict:
        return polled_sources(self.config, profile, self.kn, self.packs)

    def folder(self, names) -> dict[str, int]:
        out: dict[str, int] = {}
        for name in names:
            folder = self.packs.source_pack[name].partition("/")[0]
            out[folder] = out.get(folder, 0) + 1
        return out

    def test_every_existing_board_polls_what_it_polled_in_0_3_11_with_the_same_settings(self):
        # Boards that poll every source also gain the health/, product_design/ and aec/ packs, and nothing else changes.
        # Product and Design poll more since D28: the next test.
        every = set(enabled_sources(self.config))
        for name, expected in V0_3_11["profiles"].items():
            if OWN_GROUPS & set(expected["fields"]):
                continue
            with self.subTest(profile=name):
                polled = self.polled({"fields": expected["fields"], "target_roles": expected["target_roles"]})
                kept = {k: cfg for k, cfg in polled.items() if not self.packs.source_pack.get(k, "").startswith(OWN_FOLDERS)}
                self.assertEqual(V0_3_11["lists"][expected["hash"]], sorted(kept))
                self.assertEqual(expected["hash"], boards_hash(kept))
                if len(kept) < len(polled):
                    self.assertEqual(every, set(polled))

    def test_product_and_design_poll_their_own_groups_and_every_source_they_polled_in_0_3_11(self):
        # D28: All of Product names 27 groups, All of Design the same minus 7 plus its studios, its industrial design
        # employers and its LinkedIn searches (D30), and neither polls less than in 0.3.11, with the same settings.
        # Since Phase 3 they are core plus their filters' groups (option E).
        product, design = (set(self.packs.fields[board]["core"]).union(*self.packs.fields[board]["filters"].values())
                           for board in ("product", "design"))
        self.assertEqual((27, 23), (len(product), len(design)))
        self.assertEqual({"semiconductors", "data_infrastructure", "ai_infrastructure", "cloud_infrastructure",
                          "ratings_data", "asset_managers", "product_core"}, product - design)
        self.assertEqual({"design_studios", "industrial_design", "design_core"}, design - product)
        for board, groups in (("product", product), ("design", design)):
            with self.subTest(board=board):
                expected = V0_3_11["profiles"][board]
                profile = {"fields": expected["fields"], "target_roles": expected["target_roles"]}
                self.assertEqual(groups, groups_for(board, profile, self.kn, self.packs))
                polled = self.polled(profile)
                self.assertEqual({key for key, p in self.packs.packs.items()
                                  if p.group in groups and board in self.packs.folders[p.folder]},
                                 {self.packs.source_pack[name] for name in polled})
                self.assertEqual(0, self.folder(polled).get("finance", 0))
                before = V0_3_11["lists"][expected["hash"]]
                self.assertLessEqual(set(before), set(polled))
                self.assertEqual(expected["hash"], boards_hash({name: polled[name] for name in before}))

    def test_healthcare_polls_its_own_groups_and_no_finance_source(self):
        manifest = json.loads((ROOT / "config" / "sources" / "manifest.json").read_text(encoding="utf-8"))["fields"]["healthcare"]
        groups = set(manifest["core"]).union(*manifest.get("filters", {}).values())
        self.assertLessEqual({"lists", "health_tech", "health_core"}, groups)
        self.assertEqual(groups, groups_for("healthcare", {"fields": ["healthcare"]}, self.kn, self.packs))
        polled = self.polled({"fields": ["healthcare"]})
        self.assertEqual({key for key, p in self.packs.packs.items() if p.group in groups},
                         {self.packs.source_pack[name] for name in polled})
        self.assertEqual(0, self.folder(polled).get("finance", 0))
        self.assertLess(len(polled), len(enabled_sources(self.config)))

    def test_healthcare_names_each_of_its_filters_and_health_packs_hold_its_employers(self):
        manifest = self.packs.fields["healthcare"]
        tree = {f["key"]: f for f in self.kn.family_tree()}["healthcare"]
        self.assertEqual([s["key"] for s in tree["subcategories"]], list(manifest["filters"]))
        health = [(name, cfg) for pack in self.packs.packs.values() if pack.folder == "health"
                  for name, cfg in pack.sources.items() if cfg["ats"] != "linkedin"]
        self.assertTrue(health)
        for name, cfg in health:
            with self.subTest(source=name):
                self.assertIn("healthcare", self.kn.type_tracks(self.kn.companies[cfg["company_key"]].type))

    def test_product_and_design_name_each_of_their_filters_and_a_filter_adds_only_its_groups(self):
        # Option E (D28): the filters are the taxonomy's, in order. A picked filter polls core and its own groups:
        # APM & Programs only the early-career pack, and Design Engineering none, so it polls core.
        tree = {f["key"]: f for f in self.kn.family_tree()}
        for board, picked, own in (("product", "apm_programs", ["early_career_programs"]), ("design", "design_engineering", [])):
            with self.subTest(board=board):
                rule = self.packs.fields[board]
                self.assertEqual([s["key"] for s in tree[board]["subcategories"]], list(rule["filters"]))
                self.assertEqual(own, rule["filters"][picked])
                self.assertEqual({*rule["core"], *own}, groups_for(board, {"fields": [board], "target_roles": [f"{board}.{picked}"]},
                                                                   self.kn, self.packs))
        self.assertEqual({*self.packs.fields["design"]["core"], "gaming"},
                         groups_for("design", {"fields": ["design"], "target_roles": ["design.game_design"]}, self.kn, self.packs))

    def test_product_design_packs_hold_employers_on_the_product_design_track(self):
        # As health/ does for Healthcare: every employer a product_design/ source reads, LinkedIn aside, has a type
        # on the P&D track (plans/product-design-board.md, section 6). Visa's and Mastercard's early-career boards
        # and T-Mobile's are the exceptions: fintech and telecom employers, allowed by name (section 14.7).
        folder = {name: cfg for pack in self.packs.packs.values() if pack.folder == "product_design"
                  for name, cfg in pack.sources.items() if cfg["ats"] != "linkedin"}
        for name, kind in (("visa_early_careers", "fintech"), ("mastercard_campus", "fintech"), ("t_mobile", "telecom")):
            self.assertEqual(kind, self.kn.companies[folder.pop(name)["company_key"]].type)
        self.assertTrue(folder)
        for name, cfg in folder.items():
            with self.subTest(source=name):
                self.assertIn("product_design", self.kn.type_tracks(self.kn.companies[cfg["company_key"]].type))

    def test_aec_polls_its_own_groups_and_the_facilities_groups_of_three_filters(self):
        # plans/aec-board.md 7.3 and D10: core is the lists and the board's LinkedIn searches; Structural, Building
        # Systems and Construction also poll the big tech, semiconductor and defense groups (data-centre, fab and
        # facilities work). Consultancies are two packs (a pack holds at most 50), named together (section 13).
        rule = self.packs.fields["aec"]
        tree = {f["key"]: f for f in self.kn.family_tree()}["aec"]
        self.assertEqual([s["key"] for s in tree["subcategories"]], list(rule["filters"]))
        self.assertEqual(["lists", "aec_core"], rule["core"])
        facilities = {"big_tech", "semiconductors", "defense_aerospace"}
        for name, groups in rule["filters"].items():
            with self.subTest(filter=name):
                self.assertEqual(name in ("structural", "building_systems", "construction"), facilities <= set(groups))
                self.assertLessEqual({"consultancies", "infrastructure_consultancies"}, set(groups))
        groups = groups_for("aec", {"fields": ["aec"]}, self.kn, self.packs)
        polled = self.polled({"fields": ["aec"]})
        self.assertEqual({key for key, p in self.packs.packs.items() if p.group in groups and "aec" in self.packs.folders[p.folder]},
                         {self.packs.source_pack[name] for name in polled})
        folders = self.folder(polled)
        self.assertEqual({"aec", "shared", "tech"}, set(folders))
        self.assertEqual(130, folders["aec"])

    def test_a_picked_aec_filter_polls_core_and_its_own_groups(self):
        rule = self.packs.fields["aec"]
        architecture = {"fields": ["aec"], "target_roles": ["aec.architecture"]}
        self.assertEqual({*rule["core"], *rule["filters"]["architecture"]}, groups_for("aec", architecture, self.kn, self.packs))
        packs = {self.packs.source_pack[name] for name in self.polled(architecture)}
        self.assertFalse({"shared/big_tech", "tech/big_tech", "aec/contractors", "aec/building_systems"} & packs)
        self.assertLessEqual({"aec/aec_core", "aec/architecture_firms", "shared/lists"}, packs)

    def test_aec_packs_hold_employers_on_the_aec_track(self):
        # As health/ does for Healthcare: every employer an aec/ source reads, LinkedIn aside, has a type on the AEC track.
        folder = {name: cfg for pack in self.packs.packs.values() if pack.folder == "aec"
                  for name, cfg in pack.sources.items() if cfg["ats"] != "linkedin"}
        self.assertEqual(126, len(folder))
        for name, cfg in folder.items():
            with self.subTest(source=name):
                self.assertEqual(["aec"], self.kn.type_tracks(self.kn.companies[cfg["company_key"]].type))

    def test_the_aec_linkedin_searches_cover_the_employers_whose_sites_refuse_robots(self):
        # D12: two keyword searches with senior queries beside the co-op ones, two company searches of 24 employers.
        core = self.packs.packs["aec/aec_core"].sources
        self.assertEqual({"linkedin_canada_aec", "linkedin_us_aec", "linkedin_aec_firms_canada", "linkedin_aec_firms_us"}, set(core))
        for name in ("linkedin_aec_firms_canada", "linkedin_aec_firms_us"):
            self.assertEqual(24, len(set(core[name]["companies"])))
        self.assertEqual(core["linkedin_aec_firms_canada"]["companies"], core["linkedin_aec_firms_us"]["companies"])
        for name in ("linkedin_canada_aec", "linkedin_us_aec"):
            self.assertTrue({"structural engineer", "civil engineer", "construction project manager"} <= set(core[name]["queries"]))

    def test_no_board_but_the_everything_boards_polls_an_aec_pack(self):
        for boards in (["finance"], ["software"], ["data_ml"], ["hardware"], ["product"], ["design"], ["healthcare"]):
            with self.subTest(boards=boards):
                self.assertEqual(0, self.folder(self.polled({"fields": boards})).get("aec", 0))
        self.assertEqual(130, self.folder(self.polled({"fields": ["sales"]}))["aec"])

    def test_finance_polls_no_tech_or_health_source(self):
        folders = self.folder(self.polled({"fields": ["finance"]}))
        self.assertEqual({"finance", "shared"}, set(folders))

    def test_a_mixed_profile_polls_the_union_of_its_boards(self):
        # Finance + Healthcare stops polling every source: Finance's packs plus Healthcare's groups.
        for boards in MIXES:
            with self.subTest(boards=boards):
                alone = set().union(*(self.polled({"fields": [b]}) for b in boards))
                self.assertEqual(alone, set(self.polled({"fields": boards})))
        # Finance's 347 and tech/health_tech's 29, plus Healthcare's own packs.
        health = self.folder(self.polled({"fields": ["healthcare"]})).get("health", 0)
        self.assertEqual(376 + health, len(self.polled({"fields": ["finance", "healthcare"]})))

    def test_boards_that_poll_every_source_also_poll_health_packs(self):
        every = set(enabled_sources(self.config))
        for boards in (["sales"], ["operations"], ["people_legal"], ["healthcare", "sales"]):
            with self.subTest(boards=boards):
                self.assertEqual(every, set(self.polled({"fields": boards})))


if __name__ == "__main__":
    unittest.main()
