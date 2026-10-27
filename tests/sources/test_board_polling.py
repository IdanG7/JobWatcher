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
        for name, expected in V0_3_11["profiles"].items():
            with self.subTest(profile=name):
                polled = self.polled({"fields": expected["fields"], "target_roles": expected["target_roles"]})
                self.assertEqual(V0_3_11["lists"][expected["hash"]], sorted(polled))
                self.assertEqual(expected["hash"], boards_hash(polled))

    def test_healthcare_polls_its_own_groups_and_no_finance_source(self):
        self.assertEqual({"lists", "health_tech"}, groups_for("healthcare", {"fields": ["healthcare"]}, self.kn, self.packs))
        polled = self.polled({"fields": ["healthcare"]})
        self.assertEqual({key for key, p in self.packs.packs.items() if p.group in ("lists", "health_tech")},
                         {self.packs.source_pack[name] for name in polled})
        self.assertEqual(0, self.folder(polled).get("finance", 0))
        self.assertLess(len(polled), len(enabled_sources(self.config)))

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
        self.assertEqual(376, len(self.polled({"fields": ["finance", "healthcare"]})))

    def test_boards_that_poll_every_source_also_poll_health_packs(self):
        every = set(enabled_sources(self.config))
        for boards in (["sales"], ["operations"], ["people_legal"], ["healthcare", "sales"]):
            with self.subTest(boards=boards):
                self.assertEqual(every, set(self.polled({"fields": boards})))


if __name__ == "__main__":
    unittest.main()
