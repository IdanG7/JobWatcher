"""Sources live in packs (config/sources/<folder>/<group>.json) and each profile
polls only the packs of its boards.  The Finance board must keep exactly the
sources it polled in 0.3.7, whatever tech sources are added."""
import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import intel.sources
import watcher
from intel import load_knowledge
from intel.companies import resolve_company
from intel.sources import MAX_PACK, Packs, enabled_sources, load_config, load_packs, polled_sources, \
    profile_fields, selected_packs
from intel_store import board_sections, save_profile
from tools.build_windows import clean_config
from tools.source_history import boards_hash

ROOT = Path(__file__).resolve().parents[2]
V0_3_7 = Path(__file__).with_name("v0_3_7_sources.json")     # config.json's "boards" at v0.3.7, verbatim
SHIPPED_0_3_7 = "ddb8d7057c16c87e"      # their packaged hash: __shipped__ for sources_version 9


def v0_3_7() -> dict:
    return {name: cfg for name, cfg in json.loads(V0_3_7.read_text(encoding="utf-8")).items()
            if not name.startswith("_")}


def in_folder(packs: Packs, folder: str) -> set[str]:
    return {name for name, key in packs.source_pack.items() if packs.packs[key].folder == folder}


def with_tech_pack(root: Path) -> Packs:
    """The repository's packs plus a tech-only pack that Software polls."""
    shutil.copytree(ROOT / "config" / "sources", root)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    manifest["fields"]["software"]["core"].append("new_grad_tech")
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (root / "tech").mkdir(exist_ok=True)
    (root / "tech" / "new_grad_tech.json").write_text(json.dumps(
        {"title": "New grad tech", "boards": {"acme_tech": {"ats": "greenhouse", "token": "acme"}}}), encoding="utf-8")
    return load_packs(root)


class PackTests(unittest.TestCase):
    def test_every_source_is_in_one_pack_of_at_most_fifty(self):
        packs = load_packs()
        self.assertTrue(packs.packs)
        for key, pack in packs.packs.items():
            with self.subTest(pack=key):
                self.assertLessEqual(len(pack.sources), MAX_PACK)
                self.assertTrue(pack.title)
        self.assertEqual(sum(len(p.sources) for p in packs.packs.values()), len(packs.source_pack))

    def test_manifest_names_known_boards_and_keeps_finance_out_of_tech(self):
        packs, kn = load_packs(), load_knowledge()
        self.assertLessEqual(set(packs.fields), {"finance", *kn.families})
        self.assertEqual({"finance"}, packs.folders["finance"])
        self.assertIn("finance", packs.folders["shared"])
        self.assertNotIn("finance", packs.folders["tech"])

    def test_a_source_defined_twice_or_a_group_without_a_pack_is_refused(self):
        manifest = {"folders": {"finance": {"fields": ["finance"]}, "tech": {"fields": ["software"]}},
                    "fields": {"software": {"core": ["missing"]}}}
        packs = {"finance/banks": {"boards": {"rbc": {"ats": "workday"}}},
                 "tech/big_tech": {"boards": {"rbc": {"ats": "workday"}}},
                 "elsewhere/x": {"boards": {}}}
        with self.assertRaises(ValueError) as raised:
            Packs(manifest, packs)
        for problem in ("source rbc: defined in finance/banks and tech/big_tech",
                        "board software: no pack for group missing", "folder elsewhere/"):
            self.assertIn(problem, str(raised.exception))
        stray = {"finance/banks": {"sections": {"old": ["td"]}, "boards": {"rbc": {}}}}
        with self.assertRaisesRegex(ValueError, "section old lists td"):
            Packs(manifest | {"fields": {}}, stray)
        too_many = {"finance/banks": {"boards": {f"b{i}": {} for i in range(MAX_PACK + 1)}}}
        with self.assertRaisesRegex(ValueError, "at most 50"):
            Packs(manifest | {"fields": {}}, too_many)

    def test_the_repository_config_lists_no_sources_of_its_own(self):
        self.assertNotIn("boards", json.loads((ROOT / "config.json").read_text(encoding="utf-8")))


class FinanceBoardTests(unittest.TestCase):
    def test_finance_and_shared_packs_hold_exactly_the_0_3_7_sources(self):
        old = v0_3_7()
        self.assertEqual(256, len(old))
        self.assertEqual(SHIPPED_0_3_7, boards_hash(clean_config({"boards": old})["boards"]))
        packs = load_packs()
        finance_board = {name: cfg for key, pack in packs.packs.items()
                         if pack.folder in ("finance", "shared") for name, cfg in pack.sources.items()}
        self.assertEqual(old, finance_board)            # same sources, same settings
        assembled = load_config(ROOT / "config.json")["boards"]
        self.assertEqual(old, {k: v for k, v in assembled.items() if not k.startswith("_")})
        self.assertEqual(SHIPPED_0_3_7, boards_hash(clean_config(load_config(ROOT / "config.json"))["boards"]))

    def test_every_source_keeps_the_company_type_its_old_heading_implied(self):
        # A heading's name types employers missing from companies.json (intel/companies.py).
        kn = load_knowledge()
        old = board_sections({"boards": json.loads(V0_3_7.read_text(encoding="utf-8"))})
        new = board_sections(load_config(ROOT / "config.json"))
        for name, cfg in v0_3_7().items():
            with self.subTest(source=name):
                self.assertEqual(resolve_company("", kn, name, cfg, old[name])["type"],
                                 resolve_company("", kn, name, cfg, new[name])["type"])
        self.assertEqual("fintech", resolve_company("", kn, "peloton", {"ats": "greenhouse"}, new["peloton"])["type"])

    def test_a_finance_profile_polls_every_enabled_0_3_7_source(self):
        config, kn = load_config(ROOT / "config.json"), load_knowledge()
        expected = enabled_sources({"boards": v0_3_7()})
        self.assertEqual(246, len(expected))
        for profile in ({}, {"fields": ["finance"]}, {"target_roles": ["investment_banking"]},
                        {"fields": ["finance"], "target_roles": ["quant", "markets"]}):
            with self.subTest(profile=profile):
                self.assertEqual(expected, polled_sources(config, profile, kn))

    def test_tech_sources_never_reach_the_finance_board(self):
        kn = load_knowledge()
        with tempfile.TemporaryDirectory() as directory:
            packs = with_tech_pack(Path(directory) / "sources")
            config = {"boards": packs.flat()}
            finance = polled_sources(config, {"fields": ["finance"]}, kn, packs)
            software = polled_sources(config, {"fields": ["software"]}, kn, packs)
            both = polled_sources(config, {"fields": ["finance", "software"]}, kn, packs)
        self.assertEqual(enabled_sources({"boards": v0_3_7()}), finance)
        self.assertFalse(set(finance) & in_folder(packs, "tech"))
        self.assertIn("acme_tech", software)
        self.assertFalse(set(software) & in_folder(packs, "finance"))
        self.assertEqual(finance | software, both)
        self.assertEqual(len(set(finance) | set(software)), len(both))


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.kn, self.packs = load_knowledge(), load_packs()
        self.config = load_config(ROOT / "config.json")

    def polled(self, profile: dict) -> set[str]:
        return set(polled_sources(self.config, profile, self.kn, self.packs))

    def groups(self, profile: dict) -> set[str]:
        return {self.packs.packs[key].group for key in selected_packs(profile, self.kn, self.packs)}

    def test_profile_fields_mirror_onboarding(self):
        self.assertEqual(["finance"], profile_fields({}, self.kn))
        self.assertEqual(["software", "finance"],
                         profile_fields({"fields": ["software", 3], "target_roles": ["investment_banking.ma"]}, self.kn))
        self.assertEqual(["data_ml"], profile_fields({"target_roles": ["data_ml.ml_engineering"]}, self.kn))

    def test_tech_boards_poll_no_finance_only_source(self):
        finance_only = in_folder(self.packs, "finance")
        for field in ("software", "data_ml", "hardware", "product", "design"):
            with self.subTest(board=field):
                polled = self.polled({"fields": [field]})
                self.assertTrue(polled)
                self.assertFalse(polled & finance_only)
                self.assertLess(len(polled), len(self.polled({})))

    def test_a_filter_narrows_its_board_and_all_of_it_keeps_every_filter(self):
        software = self.packs.fields["software"]
        self.assertEqual(set(software["core"]) | {"gaming"}, self.groups({"target_roles": ["software.game_dev"]}))
        everything = self.groups({"fields": ["software"]})
        self.assertEqual(set(software["core"]).union(*software["filters"].values()), everything)
        self.assertEqual(everything, self.groups({"target_roles": ["software", "software.game_dev"]}))
        narrowed = self.polled({"target_roles": ["software.backend", "software.infrastructure"]})
        self.assertLess(len(narrowed), len(self.polled({"fields": ["software"]})))
        self.assertLessEqual(narrowed, self.polled({"fields": ["software"]}))

    def test_boards_without_packs_of_their_own_poll_every_source(self):
        every = set(enabled_sources(self.config))
        for profile in ({"fields": ["sales"]}, {"fields": ["software", "healthcare"]}, {"fields": ["astronomy"]}):
            with self.subTest(profile=profile):
                self.assertEqual(every, self.polled(profile))

    def test_own_sources_are_always_polled_and_disabled_ones_never(self):
        config = {"boards": {**self.config["boards"], "mine": {"ats": "greenhouse", "token": "mine"},
                             "rbc": {**self.config["boards"]["rbc"], "disabled": True}}}
        for profile in ({}, {"fields": ["software"]}, {"target_roles": ["hardware.chip_design"]}):
            with self.subTest(profile=profile):
                polled = polled_sources(config, profile, self.kn, self.packs)
                self.assertIn("mine", polled)
                self.assertNotIn("rbc", polled)


class CycleTests(unittest.TestCase):
    def test_a_board_change_in_settings_applies_on_the_next_poll(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "finance").mkdir()
            (root / "tech").mkdir()
            (root / "manifest.json").write_text(json.dumps({
                "folders": {"finance": {"fields": ["finance"]}, "tech": {"fields": ["software"]}},
                "fields": {"finance": {"groups": "*"}, "software": {"core": ["big_tech"]}}}), encoding="utf-8")
            (root / "finance" / "banks.json").write_text(json.dumps(
                {"boards": {"bank": {"ats": "fake", "token": "bank"}}}), encoding="utf-8")
            (root / "tech" / "big_tech.json").write_text(json.dumps(
                {"boards": {"techco": {"ats": "fake", "token": "techco"}}}), encoding="utf-8")
            config = {"boards": load_packs(root).flat(), "filters": {}, "profile": {}}
            adapter = Mock(side_effect=lambda cfg: [{"id": cfg["token"], "title": "Analyst", "location": "Toronto, ON",
                                                     "url": f"https://x/{cfg['token']}", "company": cfg["token"]}])
            subs = root / "subs.json"
            subs.write_text("{}")
            polled = lambda: sorted(c.args[0]["token"] for c in adapter.call_args_list)
            with patch.object(intel.sources, "SOURCES_DIR", root), \
                    patch.object(watcher, "SUBSCRIBERS", subs), \
                    patch.dict(watcher.ADAPTERS, {"fake": adapter}), \
                    patch.object(watcher, "EPHEMERAL", False), \
                    patch("watcher.enrich_descriptions", return_value=0):
                con = watcher.db_open(":memory:")
                watcher.cycle(config, con)                    # no profile yet: the Finance board
                self.assertEqual(["bank"], polled())
                adapter.reset_mock()
                save_profile(con, {"fields": ["software"], "target_roles": ["software"]})
                con.commit()
                watcher.cycle(config, con)
                self.assertEqual(["techco"], polled())


if __name__ == "__main__":
    unittest.main()
