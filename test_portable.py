"""Portable distribution must start clean and preserve the recipient's data."""
import json
from contextlib import closing
from pathlib import Path
import tempfile
import sqlite3
import threading
import time
import unittest
from unittest.mock import patch

from tools.build_windows import bundle_files, clean_config, stage_app
from tools.verify_windows_bundle import verify_builder_path
from portable_start import initialize_data, instance_url
from intel import load_knowledge, merge_profile, validate_profile
import watcher


class PortableTests(unittest.TestCase):
    def test_upstream_binary_build_paths_do_not_mask_private_app_or_wrapper_paths(self):
        home = Path(r"C:\Users\runneradmin")
        content = b"compiler source: C:\\Users\\runneradmin\\build\\src"
        verify_builder_path("Jobwatch/runtime/Lib/site-packages/cryptography/_rust.pyd", content, home)
        for member in ("Jobwatch/app/watcher.py", "Jobwatch/app/private.pyd",
                       "Jobwatch/runtime/Lib/site-packages/bin/wrapper.exe",
                       "Jobwatch/runtime/Lib/site-packages/cryptography/__init__.py"):
            with self.subTest(member=member), self.assertRaises(AssertionError):
                verify_builder_path(member, content, home)

    def test_source_upgrade_preserves_private_preferences_and_custom_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, data = root / "app", root / "data"
            (app / "config").mkdir(parents=True)
            data.mkdir()
            old = {"bank": {"ats": "workday", "site": "jobs", "max": 300, "min_interval": 60},
                   "deleted": {"ats": "greenhouse", "token": "deleted"},
                   "customized": {"ats": "linkedin", "queries": ["old"], "pages": 3, "disabled": True}}
            new = {"bank": {**old["bank"], "max": 5000, "min_interval": 120},
                   "deleted": old["deleted"],
                   "customized": {"ats": "linkedin", "queries": ["finance"], "pages": 5, "disabled": True},
                   "students": {"ats": "workday", "site": "students"}}
            private = {"profile": {"name": "PRIVATE", "target_roles": ["quant"]},
                       "boards": {"bank": {**old["bank"], "disabled": True, "min_interval": 90},
                                  "customized": {"ats": "linkedin", "queries": ["my search"], "pages": 3},
                                  "mine": {"ats": "greenhouse", "token": "mine"}}}
            (app / "config.json").write_text(json.dumps({"sources_version": 2, "boards": new}))
            (app / "config/source_defaults_v1.json").write_text(json.dumps({"boards": old}))
            (app / "subscribers.json").write_text('{}')
            (data / "config.json").write_text(json.dumps(private))
            (data / "subscribers.json").write_text('{"secret":"unchanged"}')
            initialize_data(app, data)
            upgraded = json.loads((data / "config.json").read_text())
            self.assertEqual(private["profile"], upgraded["profile"])
            self.assertEqual(5000, upgraded["boards"]["bank"]["max"])
            self.assertEqual(90, upgraded["boards"]["bank"]["min_interval"])
            self.assertTrue(upgraded["boards"]["bank"]["disabled"])
            self.assertEqual(["my search"], upgraded["boards"]["customized"]["queries"])
            self.assertEqual(5, upgraded["boards"]["customized"]["pages"])
            self.assertNotIn("disabled", upgraded["boards"]["customized"])
            self.assertEqual(private["boards"]["mine"], upgraded["boards"]["mine"])
            self.assertIn("students", upgraded["boards"])
            self.assertNotIn("deleted", upgraded["boards"])
            saved = (data / "config.json").read_bytes()
            initialize_data(app, data)
            self.assertEqual(saved, (data / "config.json").read_bytes())
            self.assertEqual('{"secret":"unchanged"}', (data / "subscribers.json").read_text())

    def test_distribution_drops_private_config_and_subscribers(self):
        source = {
            "profile": {"name": "PRIVATE NAME", "skills": ["python"]},
            "healthcheck_url": "PRIVATE HOOK", "private_token": "SECRET",
            "boards": {"bank": {"ats": "greenhouse", "token": "public-slug",
                                "private_token": "SECRET", "_note": "PRIVATE NOTE"}},
            "filters": {"include": "intern", "_note": "PRIVATE NOTE"},
        }
        result = clean_config(source)
        encoded = json.dumps(result)
        self.assertNotIn("PRIVATE", encoded)
        self.assertNotIn("SECRET", encoded)
        self.assertEqual("public-slug", result["boards"]["bank"]["token"])
        self.assertEqual([], result["profile"]["skills"])
        self.assertIsNone(result["profile"]["graduation_year"])
        self.assertEqual({"CA": "unknown", "US": "unknown"}, result["profile"]["work_authorization"])
        self.assertEqual([], validate_profile(merge_profile(result["profile"]), load_knowledge()))

    def test_packaged_sources_keep_every_field_their_adapters_use(self):
        source = json.loads((Path(__file__).parent / "config.json").read_text(encoding="utf-8"))
        cleaned = clean_config(source)["boards"]
        for name, board in source["boards"].items():
            if name.startswith("_") or not isinstance(board, dict):
                continue
            with self.subTest(board=name):
                dropped = set(board) - set(cleaned[name])
                self.assertFalse({k for k in dropped if not k.startswith("_")}, "fields lost in packaging")

    def test_stage_uses_allowlist_without_database_or_personal_files(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory) / "Jobwatch"
            stage_app(Path(__file__).parent, stage)
            self.assertTrue((stage / "Start Jobwatch.bat").is_file())
            self.assertTrue((stage / "app/web/js/views/settings.js").is_file())
            self.assertTrue((stage / "app/intel/resume.py").is_file())
            self.assertEqual({}, json.loads((stage / "app/subscribers.json").read_text()))
            names = [p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file()]
            self.assertFalse(any(".git" in n or "test_" in n or "__pycache__" in n for n in names))
            self.assertFalse(any(n.endswith((".db", ".pdf", ".csv")) for n in names))
            self.assertNotIn("app/state.json", names)
            self.assertNotIn("app/README.md", names)

    def test_bundle_omits_generated_wrappers_with_creator_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            for name in ("runtime/python.exe", "runtime/Lib/site-packages/bin/normalizer.exe",
                         "runtime/Lib/site-packages/Scripts/idna.exe", "runtime/Lib/site-packages/idna/__init__.py"):
                path = stage / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"CONTENT")
            self.assertEqual({"runtime/python.exe", "runtime/Lib/site-packages/idna/__init__.py"},
                             {p.relative_to(stage).as_posix() for p in bundle_files(stage)})

    def test_first_start_creates_only_clean_config_then_preserves_edits(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            app, data = root / "app", root / "data"
            app.mkdir()
            (app / "config.json").write_text('{"profile":{"name":"My search"}}')
            (app / "subscribers.json").write_text('{}')
            initialize_data(app, data)
            (data / "config.json").write_text('{"profile":{"name":"My own search"}}')
            (data / "jobwatch.db").write_bytes(b"MY LOCAL DATABASE")
            initialize_data(app, data)
            self.assertEqual("My own search", json.loads((data / "config.json").read_text())["profile"]["name"])
            self.assertEqual(b"MY LOCAL DATABASE", (data / "jobwatch.db").read_bytes())

    def test_duplicate_instance_urls_are_local_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "instance.json"
            for url in ("https://evil.example", "http://localhost:8787", "http://127.0.0.1:8000/private", "file:///x"):
                path.write_text(json.dumps({"url": url}))
                self.assertIsNone(instance_url(path))
            path.write_text('{"url":"http://127.0.0.1:8787"}')
            self.assertEqual("http://127.0.0.1:8787", instance_url(path))
            path.write_text("broken")
            self.assertIsNone(instance_url(path))

    def test_fetching_sources_does_not_lock_out_profile_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "jobs.db"
            watcher.db_open(database).close()
            release = threading.Event()
            release_fast = threading.Event()
            fetching = threading.Event()
            completed = threading.Event()
            errors = []
            config = {"boards": {"fast": {"ats": "greenhouse"}, "slow": {"ats": "greenhouse"}},
                      "description_budget": 0}

            def fetch(name, board):
                fetching.set()
                if name == "slow":
                    release.wait(5)
                    return name, []
                release_fast.wait(5)
                return name, [{"id": "one", "title": "Investment Banking Analyst",
                               "location": "Toronto", "url": "https://example.com/job"}]

            def poll():
                connection = watcher.db_open(database)
                try:
                    watcher.cycle(config, connection)
                except Exception as error:
                    errors.append(error)
                finally:
                    connection.close()
                    completed.set()

            with patch.object(watcher, "fetch_board", side_effect=fetch), patch.object(watcher, "load_subscribers", return_value=[]):
                thread = threading.Thread(target=poll)
                thread.start()
                try:
                    with closing(sqlite3.connect(database, timeout=0.2)) as connection:
                        self.assertTrue(fetching.wait(2))
                        connection.execute("INSERT OR REPLACE INTO user_profile VALUES ('profile', '{}')")
                        connection.commit()
                        release_fast.set()
                        deadline = time.monotonic() + 2
                        while time.monotonic() < deadline:
                            if connection.execute("SELECT count(*) FROM jobs").fetchone()[0]:
                                break
                            time.sleep(0.02)
                        self.assertFalse(completed.is_set(), "slow source should still be fetching")
                        self.assertEqual(1, connection.execute("SELECT count(*) FROM jobs").fetchone()[0])
                        connection.execute("INSERT OR REPLACE INTO user_profile VALUES ('profile', '{}')")
                        connection.commit()
                finally:
                    release_fast.set()
                    release.set()
                    thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
                self.assertEqual([], errors)

    def test_fetching_descriptions_does_not_lock_out_profile_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "jobs.db"
            with closing(watcher.db_open(database)) as connection:
                for board in ("fast", "slow"):
                    connection.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                        (board, "one", "Analyst", "Toronto", "https://example.com/job", watcher.now(), watcher.now()))
                    connection.execute("INSERT INTO job_intel(board,job_id,is_finance) VALUES (?,?,1)", (board, "one"))
                connection.commit()
            release = threading.Event()
            errors = []
            config = {"boards": {b: {"ats": "greenhouse", "token": b} for b in ("fast", "slow")},
                      "description_budget": 2}

            def fetch(board, job_id):
                if board["token"] == "slow":
                    release.wait(5)
                return "Valuation and financial analysis", "Finance"

            def enrich():
                with closing(watcher.db_open(database)) as connection:
                    try:
                        watcher.enrich_descriptions(config, connection)
                    except Exception as error:
                        errors.append(error)

            with patch.dict(watcher.DETAIL_FETCHERS, {"greenhouse": fetch}):
                thread = threading.Thread(target=enrich)
                thread.start()
                try:
                    with closing(sqlite3.connect(database, timeout=0.2)) as connection:
                        deadline = time.monotonic() + 2
                        while time.monotonic() < deadline:
                            if connection.execute("SELECT count(*) FROM job_text").fetchone()[0]:
                                break
                            time.sleep(0.02)
                        self.assertTrue(thread.is_alive())
                        self.assertEqual(1, connection.execute("SELECT count(*) FROM job_text").fetchone()[0])
                        connection.execute("INSERT OR REPLACE INTO user_profile VALUES ('profile', '{}')")
                        connection.commit()
                finally:
                    release.set()
                    thread.join(timeout=10)
                self.assertFalse(thread.is_alive())
                self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
