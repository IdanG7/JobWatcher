import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import watcher
from intel_store import IntelStore
from portable_start import initialize_data
from tools.source_history import MISSING, merge_history

NOW = datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc).timestamp()
ZAPPLY_ROW = ("| **Manulife** | Winter Co-op 2027 - ALM Data Management & Analytics | Toronto | {age} |  | "
              "[<img src=\"images/apply.png\" alt=\"Apply\">](https://zapply.jobs/l/d/workday-manulife-{n}?s=gh) |")


class AgeColumnTests(unittest.TestCase):
    def test_relative_ages(self):
        self.assertEqual(NOW - 36 * 60, watcher._age_posted_epoch("36m", NOW))
        self.assertEqual(NOW - 8 * 3600, watcher._age_posted_epoch("8h", NOW))
        two_days = datetime(2026, 10, 9, 12, tzinfo=timezone.utc).timestamp()
        self.assertEqual(two_days, watcher._age_posted_epoch("2d", NOW))
        self.assertEqual(two_days, watcher._age_posted_epoch("2d", NOW - 3600))      # stable within the day
        self.assertEqual(datetime(2026, 9, 27, 12, tzinfo=timezone.utc).timestamp(), watcher._age_posted_epoch("2w", NOW))
        self.assertEqual(datetime(2026, 8, 12, 12, tzinfo=timezone.utc).timestamp(), watcher._age_posted_epoch("2mo", NOW))
        for text in ("Date unknown", "", None, "2 days"):
            self.assertIsNone(watcher._age_posted_epoch(text, NOW))

    def test_markdown_list_reads_age_column(self):
        readme = "\n".join(["| Company | Role | Location | Posted | Visa | **Apply** |",
                            "|---|---|---|---|---|---|",
                            ZAPPLY_ROW.format(age="1w", n="JR1"), ZAPPLY_ROW.format(age="Date unknown", n="JR2")])
        response = mock.Mock(text=readme, raise_for_status=lambda: None)
        with mock.patch.object(watcher.requests, "get", return_value=response):
            jobs = watcher.fetch_github_md({"repo": "z/z", "cols": {"company": 0, "title": 1, "location": 2,
                                                                    "age": 3, "url": 5}})
        self.assertEqual(2, len(jobs))
        self.assertIn("posted", jobs[0])
        self.assertNotIn("posted", jobs[1])


class MarkdownTitleTests(unittest.TestCase):
    # As DereC4's list copied zapply's: the link sits in the title cell, with escaped brackets in its text.
    LINKED = ("| FightCamp | [Embedded Software Engineering Intern \\[Winter 2027\\]]"
              "(https://zapply.jobs/l/d/greenhouse-figureai-4722086006?s=gh-internships-2027) | San Jose, CA | 11d |")
    PLAIN = ("| **Roblox** | \\[2027\\] Data Scientist - PhD Intern | San Mateo, CA | 1w | ✅ Sponsor | "
             "[<img src=\"images/apply.png\" alt=\"Apply\">](https://zapply.jobs/l/d/greenhouse-roblox-8242619?s=gh) |")

    def read(self, row, cols):
        response = mock.Mock(text=row, raise_for_status=lambda: None)
        with mock.patch.object(watcher.requests, "get", return_value=response):
            return watcher.fetch_github_md({"repo": "z/z", "cols": cols})[0]

    def test_escaped_brackets_are_read_as_brackets(self):
        job = self.read(self.LINKED, {"company": 0, "title": 1, "location": 2, "url": 1})
        self.assertEqual("Embedded Software Engineering Intern [Winter 2027]", job["title"])
        self.assertEqual("https://zapply.jobs/l/d/greenhouse-figureai-4722086006?s=gh-internships-2027", job["url"])
        job = self.read(self.PLAIN, {"company": 0, "title": 1, "location": 2, "url": 5})
        self.assertEqual("[2027] Data Scientist - PhD Intern", job["title"])

    def test_titles_stored_with_markup_are_repaired(self):
        con = watcher.db_open(":memory:")
        stored = {"1": "[Embedded Software Engineering Intern \\[Winter 2027\\]](https://zapply.jobs/l/d/x?s=gh)",
                  "2": "\\[2027\\] Data Scientist - PhD Intern", "3": "Analyst, M&A (2027)"}
        for job_id, title in stored.items():
            con.execute("INSERT INTO jobs VALUES ('derec4',?,?,'','u','t','t')", (job_id, title))
        con.execute("INSERT INTO applications(job_key, board, job_id, title) VALUES ('derec4:1','derec4','1',?)",
                    (stored["1"],))
        config = {"boards": {"derec4": {"ats": "github_md", "repo": "z/z"}}}
        self.assertEqual(2, watcher.repair_list_titles(con, config))
        titles = dict(con.execute("SELECT job_id, title FROM jobs"))
        self.assertEqual({"1": "Embedded Software Engineering Intern [Winter 2027]",
                          "2": "[2027] Data Scientist - PhD Intern", "3": "Analyst, M&A (2027)"}, titles)
        self.assertEqual(titles["1"], con.execute("SELECT title FROM applications").fetchone()[0])
        self.assertEqual(0, watcher.repair_list_titles(con, config))


class DuplicateSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = watcher.db_open(Path(self.tmp.name) / "jobwatch.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def add(self, board, job_id, url, first_seen, posted=None):
        self.con.execute("INSERT INTO jobs(board,job_id,title,location,url,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)",
                         (board, job_id, "Winter Co-op 2027 - ALM Data Management & Analytics", "Toronto, ON",
                          url, first_seen, first_seen))
        self.con.execute("INSERT INTO job_details(board,job_id,company,salary,posted) VALUES (?,?,?,?,?)",
                         (board, job_id, "Manulife", "", posted))

    def test_linkedin_beats_list_with_dead_links_and_dates_are_shared(self):
        week_ago = NOW - 7 * 86400
        self.add("linkedin_canada", "1", "https://www.linkedin.com/jobs/view/1", "2026-10-11T00:38:40+00:00", week_ago)
        self.add("zapply", "2", "https://zapply.jobs/l/d/x", "2026-10-11T17:09:19+00:00")
        boards = {"linkedin_canada": {"ats": "linkedin"},
                  "zapply": {"ats": "github_md", "indirect_links": True}}
        IntelStore(self.con, {"boards": boards}).refresh(force_score=True)
        rows = dict(self.con.execute("SELECT board, is_canonical FROM job_intel").fetchall())
        self.assertEqual({"linkedin_canada": 1, "zapply": 0}, rows)
        posted = dict(self.con.execute("SELECT board, posted_ref FROM job_intel").fetchall())
        self.assertEqual({"linkedin_canada": week_ago, "zapply": week_ago}, posted)

    def test_rank_change_repicks_existing_duplicates(self):
        self.add("linkedin_canada", "1", "https://www.linkedin.com/jobs/view/1", "2026-10-11T00:38:40+00:00")
        self.add("zapply", "2", "https://zapply.jobs/l/d/x", "2026-10-11T17:09:19+00:00")
        IntelStore(self.con, {"boards": {"linkedin_canada": {"ats": "linkedin"},
                                         "zapply": {"ats": "github_md"}}}).refresh(force_score=True)
        self.assertEqual("zapply", self.con.execute("SELECT board FROM job_intel WHERE is_canonical=1").fetchone()[0])
        IntelStore(self.con, {"boards": {"linkedin_canada": {"ats": "linkedin"},
                                         "zapply": {"ats": "github_md", "indirect_links": True}}}).refresh()
        self.assertEqual("linkedin_canada",
                         self.con.execute("SELECT board FROM job_intel WHERE is_canonical=1").fetchone()[0])


class SourceUpgradeHistoryTests(unittest.TestCase):
    def test_settings_from_any_release_upgrade_but_edits_stay(self):
        v1 = {"cols": {"title": 1, "url": 4}}
        v3 = {"cols": {"title": 1, "url": 5}, "min_interval": 600}
        v4 = {"cols": {"title": 1, "age": 3, "url": 5}, "min_interval": 600, "indirect_links": True}
        history = merge_history(merge_history({}, {"zapply": {"ats": "github_md", **v1}}), {"zapply": {"ats": "github_md", **v3}})
        self.assertEqual([MISSING, 600], history["zapply"]["min_interval"])
        with tempfile.TemporaryDirectory() as directory:
            app, data = Path(directory, "app"), Path(directory, "data")
            (app / "config").mkdir(parents=True)
            data.mkdir()
            (app / "config.json").write_text(json.dumps({"sources_version": 4, "boards": {
                "zapply": {"ats": "github_md", **v4}, "edited": {"ats": "github_md", **v4}}}))
            (app / "config/source_defaults_history.json").write_text(json.dumps(merge_history(
                history, {"edited": {"ats": "github_md", **v3}})))
            (app / "subscribers.json").write_text("{}")
            (data / "config.json").write_text(json.dumps({"sources_version": 3, "boards": {
                "zapply": {"ats": "github_md", **v3},
                "edited": {"ats": "github_md", **v3, "min_interval": 60}}}))
            initialize_data(app, data)
            boards = json.loads((data / "config.json").read_text())["boards"]
        self.assertEqual({"ats": "github_md", **v4}, boards["zapply"])
        self.assertEqual(60, boards["edited"]["min_interval"])           # the recipient's own value
        self.assertEqual(v4["cols"], boards["edited"]["cols"])
        self.assertTrue(boards["edited"]["indirect_links"])


if __name__ == "__main__":
    unittest.main()


class DamagedTextTests(unittest.TestCase):
    def test_one_damaged_description_does_not_stop_indexing(self):
        with tempfile.TemporaryDirectory() as tmp:
            con = watcher.db_open(Path(tmp) / "jobwatch.db")
            for job_id in ("1", "2"):
                con.execute("INSERT INTO jobs(board,job_id,title,location,url,first_seen,last_seen) VALUES "
                            "('cap',?,'Finance Analyst Intern','Toronto, ON','u','2026-10-11T00:00:00+00:00','t')", (job_id,))
            con.execute("INSERT INTO job_text(board,job_id,description) VALUES ('cap','1', CAST(? AS TEXT))",
                        (b"Build scripts and t\xefols in Excel",))
            con.commit()
            IntelStore(con, {"boards": {"cap": {"ats": "workday"}}}).refresh(force_score=True)
            self.assertEqual(2, con.execute("SELECT COUNT(*) FROM job_intel WHERE facts IS NOT NULL").fetchone()[0])
            con.close()
