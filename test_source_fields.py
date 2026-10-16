"""Sources serve fields: a Software profile skips bank boards, a Finance one skips tech employers."""
import json
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import watcher
from intel import load_knowledge
from intel.companies import resolve_company
from intel.sources import SHARED_ATS, polls, profile_tracks, source_track
from intel_store import save_profile
from portable_start import upgrade_sources
from tools.build_windows import clean_config

ROOT = Path(__file__).parent


class SourceTrackTests(unittest.TestCase):
    kn = load_knowledge()

    def track(self, name, **cfg):
        return source_track(name, {"ats": "greenhouse", **cfg}, self.kn)

    def test_the_employer_type_decides_a_sources_track(self):
        for name, track in (("jpmorgan", "finance"), ("evercore", "finance"), ("blackstone", "finance"), ("rbc", "finance"),
                            ("anthropic", "tech"), ("snowflake", "tech"), ("geotab", "tech"), ("micron", "tech"),
                            ("jane_street", "both"), ("stripe", "both"), ("nasdaq", "both")):
            self.assertEqual(track, self.track(name), name)

    def test_shared_and_unknown_sources_serve_both_unless_they_say(self):
        self.assertEqual("both", source_track("simplify", {"ats": "github_listings"}, self.kn))
        self.assertEqual("finance", source_track("linkedin_us", {"ats": "linkedin", "track": "finance"}, self.kn))
        self.assertEqual("both", self.track("acme_widgets"))
        self.assertEqual("both", self.track("capital_one", track="both"))     # the board's own track wins

    def test_profile_fields_pick_the_tracks_polled(self):
        tracks = lambda **profile: profile_tracks(profile, self.kn)
        self.assertEqual({"tech"}, tracks(target_roles=["software"]))
        self.assertEqual({"tech"}, tracks(fields=["software", "data_ml"], target_roles=["software.backend"]))
        self.assertEqual({"finance"}, tracks(target_roles=["investment_banking", "private_markets.private_equity"]))
        self.assertEqual({"finance", "tech"}, tracks(fields=["finance", "software"]))
        self.assertEqual({"finance", "tech"}, tracks(fields=["sales"]))     # every employer hires sales
        self.assertEqual({"finance", "tech"}, tracks())
        self.assertTrue(polls("both", {"tech"}))
        self.assertFalse(polls("finance", {"tech"}))

    def test_every_shipped_source_knows_its_track_without_section_headers(self):
        # Installed copies drop the '_section' headers, so a track can't come from where a board sits.
        boards = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))["boards"]
        for name, cfg in boards.items():
            if name.startswith("_") or cfg.get("disabled") or cfg.get("track"):
                continue
            self.assertNotIn(cfg.get("ats"), SHARED_ATS, f"{name}: shared sources name their track")
            self.assertNotEqual("unknown", resolve_company("", self.kn, board=name, board_cfg=cfg)["type"],
                                f"{name}: add its employer to config/companies.json or give the board a track")


class FieldBoardsTests(unittest.TestCase):
    BOARDS = {"rbc": {"ats": "workday"}, "stripe": {"ats": "greenhouse"}, "anthropic": {"ats": "greenhouse"},
              "linkedin_us": {"ats": "linkedin", "track": "finance"}, "speedy": {"ats": "github_md", "track": "tech"},
              "simplify": {"ats": "github_listings"}, "_aggregators": "---", "off": {"ats": "greenhouse", "disabled": True}}

    def polled(self, profile=None):
        with tempfile.TemporaryDirectory() as tmp, closing(watcher.db_open(Path(tmp) / "t.db")) as con:
            if profile is not None:
                save_profile(con, profile)
            return set(watcher.field_boards({"boards": self.BOARDS}, con))

    def test_polls_follow_the_profile_fields(self):
        self.assertEqual({"stripe", "anthropic", "speedy", "simplify"}, self.polled({"target_roles": ["software"]}))
        self.assertEqual({"rbc", "stripe", "linkedin_us", "simplify"}, self.polled({"target_roles": ["investment_banking"]}))
        self.assertEqual({"rbc", "stripe", "anthropic", "linkedin_us", "speedy", "simplify"},
                         self.polled({"fields": ["finance", "data_ml"], "target_roles": []}))

    def test_a_poll_works_out_its_sources_once(self):
        # Descriptions are fetched from the poll's own boards, not worked out a second time.
        with tempfile.TemporaryDirectory() as tmp, closing(watcher.db_open(Path(tmp) / "t.db")) as con:
            save_profile(con, {"target_roles": ["software"]})
            # A local install: on GitHub Actions (EPHEMERAL) a poll skips descriptions altogether.
            with patch.object(watcher, "EPHEMERAL", False), \
                    patch.object(watcher, "field_boards", wraps=watcher.field_boards) as boards, \
                    patch.object(watcher, "enrich_descriptions", return_value=0) as enrich, \
                    patch.object(watcher, "fetch_board", side_effect=lambda name, cfg: (name, [])), \
                    patch.object(watcher, "load_subscribers", return_value=[]):
                watcher.cycle({"boards": self.BOARDS, "description_budget": 5}, con)
        self.assertEqual(1, boards.call_count)
        self.assertEqual({"stripe", "anthropic", "speedy", "simplify"}, set(enrich.call_args.kwargs["boards"]))


class ExistingInstallTests(unittest.TestCase):
    def test_an_install_from_the_last_release_gets_the_split_linkedin_searches(self):
        # Upgrade the way the installer does: the bundled sources and the history of shipped values.
        bundled = clean_config(json.loads((ROOT / "config.json").read_text(encoding="utf-8")))
        history = json.loads((ROOT / "config" / "source_defaults_history.json").read_text(encoding="utf-8"))
        version = bundled["sources_version"]
        # The release before shipped neither tracks nor the tech searches, and LinkedIn mixed both kinds of query.
        old = {name: dict(board) for name, board in bundled["boards"].items() if history["__since__"][name] < version}
        for name in ("linkedin_us", "linkedin_canada"):
            del old[name]["track"]
            old[name]["queries"] = history[name]["queries"][-2]
            self.assertIn("software engineer intern", old[name]["queries"])
        with tempfile.TemporaryDirectory() as tmp:
            app, data = Path(tmp) / "app", Path(tmp) / "data"
            (app / "config").mkdir(parents=True)
            data.mkdir()
            (app / "config.json").write_text(json.dumps(bundled), encoding="utf-8")
            (app / "config" / "source_defaults_history.json").write_text(json.dumps(history), encoding="utf-8")
            (data / "config.json").write_text(json.dumps({"sources_version": version - 1, "boards": old}), encoding="utf-8")
            upgrade_sources(app, data)
            boards = json.loads((data / "config.json").read_text(encoding="utf-8"))["boards"]
        kn = load_knowledge()
        for name in ("linkedin_us", "linkedin_canada"):
            self.assertEqual("finance", boards[name]["track"])
            self.assertNotIn("software engineer intern", boards[name]["queries"])
            self.assertFalse(polls(source_track(name, boards[name], kn), {"tech"}))   # a Software profile skips it
        self.assertEqual("tech", boards["linkedin_us_tech"]["track"])
        self.assertTrue({"snowflake", "geotab", "micron"} <= boards.keys())


if __name__ == "__main__":
    unittest.main()
