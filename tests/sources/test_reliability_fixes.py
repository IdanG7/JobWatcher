"""Regression tests for the 2026-10 reliability audit (batch 1)."""
import io
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import portable_start
from intel_store import COMPLETE_LISTING_ATS, IntelStore
from portable_start import RotatingLog, initialize_data, should_repoint_autostart
from tests.app import test_dashboard as fixtures
from tests.resume.test_resume_matching import RESUME
from tools.source_history import record_release
import watcher


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def workday_server(facets, parts):
    """A Workday search that caps "total" at 2000 unless a facet is applied."""
    def post(url, json=None, **_):
        applied = json["appliedFacets"]
        if not applied:
            jobs = [f"/job/all-{n}" for n in range(watcher.WORKDAY_TOTAL_CAP)]
            total = watcher.WORKDAY_TOTAL_CAP
        else:
            (value,), = applied.values()
            jobs = parts[value]
            total = len(jobs)
        page = jobs[json["offset"]:json["offset"] + json["limit"]]
        return FakeResponse({"total": total, "facets": facets,
                             "jobPostings": [{"externalPath": p, "title": "Analyst"} for p in page]})
    return post


class WorkdayCapTests(unittest.TestCase):
    CFG = {"host": "x.wd1.myworkdayjobs.com", "tenant": "t", "site": "s"}

    def test_capped_search_is_split_by_a_covering_facet(self):
        facets = [{"facetParameter": "remoteType", "values": [{"id": "remote", "count": 10}]},
                  {"facetParameter": "locations", "values": [{"id": "ny", "count": 1500},
                                                             {"id": "to", "count": 1200}]}]
        parts = {"ny": ["/job/a", "/job/b"], "to": ["/job/b", "/job/c"]}
        with patch.object(watcher.requests, "post", side_effect=workday_server(facets, parts)):
            listing = watcher.fetch_workday(self.CFG)
        self.assertEqual(["/job/a", "/job/b", "/job/c"], [j["id"] for j in listing])
        self.assertTrue(listing.complete)

    def test_unsplittable_capped_search_is_never_complete(self):
        with patch.object(watcher.requests, "post", side_effect=workday_server([], {})):
            listing = watcher.fetch_workday({**self.CFG, "max": 40})
        self.assertEqual(40, len(listing))
        self.assertFalse(listing.complete)

    def test_small_facets_are_not_used_to_split(self):
        facets = [{"facetParameter": "remoteType", "values": [{"id": "remote", "count": 10}]}]
        self.assertIsNone(watcher._workday_split_facet(facets, {}, 5000))


class ListingClosureTests(unittest.TestCase):
    def test_markdown_lists_do_not_close_jobs(self):
        self.assertNotIn("github_md", COMPLETE_LISTING_ATS)
        self.assertIn("greenhouse", COMPLETE_LISTING_ATS)


class ApplicationStatusTests(fixtures.ServiceFixture):
    def test_saving_a_tracked_job_keeps_its_progress(self):
        self.service.save_application({"key": "rbc:one", "status": "saved"})
        self.service.patch_application("rbc:one", {"status": "first_round"})
        self.service.save_application({"key": "rbc:one", "status": "saved"})
        apps = self.service.applications()
        self.assertEqual("first_round", apps["applications"][0]["status"])


class SourceUpgradeTests(unittest.TestCase):
    def test_board_added_after_installed_version_reaches_upgrades(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, data = root / "app", root / "data"
            (app / "config").mkdir(parents=True)
            data.mkdir()
            old = {"bank": {"ats": "greenhouse", "token": "bank"}}
            new = {**old, "later": {"ats": "greenhouse", "token": "later"},
                   "removed": {"ats": "greenhouse", "token": "removed"}}
            history = {name: {k: [v] for k, v in board.items()} for name, board in new.items()}
            history["__since__"] = {"bank": 1, "removed": 1, "later": 3}
            (app / "config.json").write_text(json.dumps({"sources_version": 4, "boards": new}))
            (app / "config/source_defaults_history.json").write_text(json.dumps(history))
            (app / "subscribers.json").write_text("{}")
            (data / "config.json").write_text(json.dumps({"sources_version": 2, "boards": old}))
            initialize_data(app, data)
            boards = json.loads((data / "config.json").read_text())["boards"]
            self.assertIn("later", boards)          # shipped after this install's version
            self.assertNotIn("removed", boards)     # it had it before: the user deleted it

    def test_changed_defaults_need_a_version_bump(self):
        history = record_release({}, {"a": {"ats": "lever"}}, 4)
        with self.assertRaises(SystemExit):
            record_release(history, {"a": {"ats": "lever", "max": 9}}, 4)
        self.assertEqual(5, record_release(history, {"a": {"ats": "lever", "max": 9}}, 5)["__shipped__"]["version"])


class AutostartTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("JOBWATCH_NO_AUTOSTART", None)
        self.data = Path(tempfile.gettempdir()) / "jobwatch-data"

    def current(self, data):
        return f'"C:\\old\\pythonw.exe" "C:\\old\\portable_start.py" --serve --data-dir "{data}"'

    def test_only_the_same_data_folder_moves_the_sign_in_start(self):
        command = "new command"
        self.assertTrue(should_repoint_autostart(self.current(self.data), command, self.data))
        self.assertFalse(should_repoint_autostart(self.current(self.data / "other"), command, self.data))
        self.assertFalse(should_repoint_autostart(None, command, self.data))
        self.assertFalse(should_repoint_autostart("other-app.exe", command, self.data))
        self.assertFalse(should_repoint_autostart(command, command, self.data))
        os.environ["JOBWATCH_NO_AUTOSTART"] = "1"
        self.assertFalse(should_repoint_autostart(self.current(self.data), command, self.data))


class RotatingLogTests(unittest.TestCase):
    def test_write_failures_never_raise(self):
        with tempfile.TemporaryDirectory() as directory:
            log = RotatingLog(Path(directory) / "jobwatch.log")
            log._file.close()                         # e.g. the handle went bad
            self.assertEqual(5, log.write("hello"))
            log.write(" again")
            log._file.close()
            self.assertIn("again", (Path(directory) / "jobwatch.log").read_text())

    def test_failed_rollover_keeps_appending(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "jobwatch.log"
            path.write_text("x")
            with patch.object(portable_start, "LOG_LIMIT", 0), \
                    patch.object(Path, "replace", side_effect=PermissionError):
                log = RotatingLog(path)
                log.write("more")
            log._file.close()
            self.assertEqual("xmore", path.read_text())


class FeedDeliveryTests(unittest.TestCase):
    def setUp(self):
        with patch.object(watcher, "DB_PATH", ":memory:"):
            self.con = watcher.db_open()
        self.sub = {"name": "me", "watch": None, "discord": "hook", "feeds": {}, "telegram_chat": "chat"}
        self.con.execute("INSERT INTO pending VALUES (?,?,?,?,?,?,?,?,?)",
                         ("me", "intern", "2026-01-01T00:00:00+00:00", "Co", "Analyst Intern", "https://x/1", "", "", None))

    def flush(self, discord_ok, telegram_ok):
        with patch.object(watcher, "send_discord_feed", return_value=discord_ok) as discord, \
                patch.object(watcher, "send_telegram", return_value=telegram_ok) as telegram:
            watcher.flush_feeds({}, self.con, [self.sub], force=True)
        return discord.call_count, telegram.call_count

    def pending(self):
        return self.con.execute("SELECT COUNT(*) FROM pending").fetchone()[0]

    def test_one_failing_channel_never_resends_to_the_other(self):
        self.assertEqual((1, 1), self.flush(True, False))
        self.assertEqual(1, self.pending())                   # kept for the failed channel
        self.assertEqual((0, 0), self.flush(True, True))      # failed channel waits; discord had it
        with patch.object(watcher.time, "time", return_value=time.time() + watcher.FEED_RETRY_SECONDS + 1):
            self.assertEqual((0, 1), self.flush(True, True))
        self.assertEqual(0, self.pending())


class DiscordEmbedTests(unittest.TestCase):
    def test_chunks_respect_count_and_size_limits(self):
        small = [{"title": "t"} for _ in range(25)]
        self.assertEqual([10, 10, 5], [len(c) for c in watcher._embed_chunks(small)])
        big = [{"description": "x" * 2000} for _ in range(5)]
        chunks = list(watcher._embed_chunks(big))
        self.assertTrue(all(sum(watcher._embed_size(c) for c in chunk) <= watcher.DISCORD_EMBED_CHARS
                            for chunk in chunks))
        self.assertEqual(5, sum(len(c) for c in chunks))


class ScoringVersionTests(fixtures.ServiceFixture):
    def test_drifted_resume_version_does_not_stop_scoring(self):
        with patch.object(self.service, "kick"):
            self.service.apply_resume({"text": RESUME})
        self.service.refresh_now()
        with self.service.db() as con:
            con.execute("UPDATE candidate_resume SET version='from-an-older-release' WHERE id=1")
            store = IntelStore(con, self.service.config)
            self.assertGreater(store.score_pass(force=True), 0)
            self.assertEqual(store.version, con.execute("SELECT version FROM candidate_resume").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
