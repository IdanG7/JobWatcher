"""What each board polls: existing boards exactly as in v0.3.11, Healthcare from its own groups."""

import json
import unittest
from pathlib import Path

from intel import load_knowledge
from intel.sources import enabled_sources, groups_for, load_config, load_packs, polled_sources
from tools.source_history import boards_hash

ROOT = Path(__file__).resolve().parents[2]
V0_3_11 = json.loads(Path(__file__).with_name("board_polling_v0_3_11.json").read_text(encoding="utf-8"))


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
        # Boards that poll every source also gain the health/ packs, and nothing else changes.
        every = set(enabled_sources(self.config))
        for name, expected in V0_3_11["profiles"].items():
            with self.subTest(profile=name):
                polled = self.polled({"fields": expected["fields"], "target_roles": expected["target_roles"]})
                kept = {k: cfg for k, cfg in polled.items() if not self.packs.source_pack.get(k, "").startswith("health/")}
                self.assertEqual(V0_3_11["lists"][expected["hash"]], sorted(kept))
                self.assertEqual(expected["hash"], boards_hash(kept))
                if len(kept) < len(polled):
                    self.assertEqual(every, set(polled))

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

    def test_finance_polls_no_tech_or_health_source(self):
        folders = self.folder(self.polled({"fields": ["finance"]}))
        self.assertEqual({"finance", "shared"}, set(folders))

    def test_a_mixed_profile_polls_the_union_of_its_boards(self):
        # Finance + Healthcare stops polling every source: Finance's packs plus Healthcare's groups.
        for boards in (["finance", "healthcare"], ["software", "healthcare"], ["data_ml", "healthcare"],
                       ["finance", "software"]):
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
