"""Every board is defined in data: its track, skill groups and employers resolve, so a new board needs no code."""

import re
import unittest
from pathlib import Path

from intel import load_knowledge

ROOT = Path(__file__).resolve().parents[2]
KN = load_knowledge()
TECH = ["data_ml", "software", "hardware", "product", "design"]


def field_info() -> list[str]:
    """The boards onboarding offers (FIELD_INFO in web/js/fields.js)."""
    text = (ROOT / "web/js/fields.js").read_text(encoding="utf-8")
    block = re.search(r"export const FIELD_INFO = \{(.*?)\n\};", text, re.S).group(1)
    return re.findall(r"^\s+(\w+): \{", block, re.M)


class BoardDefinitionTests(unittest.TestCase):
    def test_every_board_onboarding_offers_has_a_taxonomy_entry(self):
        self.assertEqual({"finance", *KN.families}, set(field_info()))

    def test_each_boards_track_skill_groups_and_employers_resolve(self):
        groups = set(KN.skill_groups)
        self.assertTrue(KN.finance_skill_groups)
        self.assertLessEqual(set(KN.finance_skill_groups), groups)
        for key, node in KN.families.items():
            with self.subTest(board=key):
                self.assertTrue(node.meta.get("skill_groups"))
                self.assertLessEqual(set(node.meta["skill_groups"]), groups)
                self.assertIn(KN.board_track.get(key, "finance"), {"finance", *KN.tracks})
        for key, types in KN.board_employer_types.items():
            with self.subTest(employers=key):
                self.assertLessEqual(set(types), set(KN.company_types) - {"unknown"})

    def test_each_type_and_skill_names_known_tracks(self):
        tracks = {"finance", *KN.tracks}
        for key in KN.company_types:
            with self.subTest(type=key):
                self.assertLessEqual(set(KN.type_tracks(key)), tracks)
                if "finance" in KN.type_tracks(key):
                    self.assertTrue(KN.company_types[key].get("section"))
        self.assertLessEqual({s.track for s in KN.skills if s.track}, set(KN.tracks))

    def test_a_tracks_resume_signals_point_at_its_own_boards(self):
        for key, track in KN.tracks.items():
            boards = set(KN.track_boards[key])
            with self.subTest(track=key):
                self.assertTrue(track.label and track.employer_heading and track.employer_noun)
                self.assertLessEqual(track.skills_from, {*KN.families, "other"})
                for role, weight, _ in track.signals:
                    self.assertIn(role.split(".")[0], boards, role)
                    self.assertTrue(role in boards or role in {f"{n.parent}.{n.key}" for n in KN.subcategories.values()})
                    self.assertGreater(weight, 0)

    def test_the_tech_track_is_todays_tech_boards(self):
        self.assertEqual(TECH, KN.track_boards["tech"])
        self.assertEqual(["finance"], KN.track_boards["finance"])
        # Tech skills are read from every posting outside finance, as before boards had tracks.
        self.assertEqual({*KN.families, "other"}, KN.tracks["tech"].skills_from)
        self.assertEqual(frozenset(), KN.skill_tracks("finance"))
        self.assertEqual({*TECH, "healthcare"}, KN.occupation_families)


if __name__ == "__main__":
    unittest.main()
