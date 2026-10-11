import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import watcher
import dashboard

TODAY = date(2026, 10, 12)
HOOK = "https://discord.com/api/webhooks/1/x"


def sub(**extra):
    return {"name": "desktop", "discord": HOOK, "reminders": True, **extra}


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = watcher.db_open(Path(self.tmp.name) / "jobwatch.db")

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def app(self, key, status="saved", **fields):
        cols = {"job_key": key, "company": "RBC", "title": "Analyst", "url": "https://jobs.example/1",
                "status": status, **fields}
        self.con.execute(f"INSERT INTO applications({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                         list(cols.values()))

    def test_daily_lines_cover_deadlines_interviews_next_steps_and_follow_ups(self):
        self.app("rbc:1", deadline="2026-10-13")
        self.app("rbc:2", status="applied", deadline="2026-10-13")          # already applied: no deadline nag
        self.app("rbc:3", deadline="2026-10-30")                            # too far away
        self.app("td:1", status="first_round", company="TD", interview_date="2026-10-12T14:00")
        self.app("bmo:1", status="applied", company="BMO", next_action_date="2026-10-10", next_step="Email recruiter")
        self.con.execute("INSERT INTO contacts(name, company, next_follow_up) VALUES ('Jane Doe', 'CIBC', '2026-10-12')")
        lines = watcher.reminder_lines(self.con, TODAY)
        self.assertEqual(4, len(lines), lines)
        self.assertIn("Deadline tomorrow", lines[0])
        self.assertIn("[RBC: Analyst](https://jobs.example/1)", lines[0])
        self.assertIn("Interview today", lines[1])
        self.assertIn("Email recruiter", lines[2])
        self.assertIn("Jane Doe (CIBC)", lines[3])

    def test_summary_is_sent_once_per_day_and_not_before_the_morning(self):
        self.app("rbc:1", deadline="2026-10-12")
        with mock.patch.object(watcher, "send_discord_note", return_value=True) as sent:
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 6, 0))
            self.assertEqual(0, sent.call_count)
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 9, 0))
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 15, 0))
            self.assertEqual(1, sent.call_count)
            self.assertIn("Deadline today", sent.call_args.args[2])
            watcher.maybe_reminders(self.con, [sub(reminders=False)], datetime(2026, 10, 13, 9, 0))
            self.assertEqual(1, sent.call_count)

    def test_taken_down_saved_job_is_announced_once(self):
        closed_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        old = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(timespec="seconds")
        self.app("rbc:1")
        self.app("rbc:2", status="applied")      # applied: closing does not matter
        self.app("rbc:3")                         # closed long ago: not news
        for job_id, ts in (("1", closed_at), ("2", closed_at), ("3", old)):
            self.con.execute("INSERT INTO job_state(board, job_id, status, closed_at) VALUES ('rbc', ?, 'closed', ?)",
                             (job_id, ts))
        with mock.patch.object(watcher, "send_discord_note", return_value=True) as sent:
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 6, 0))
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 6, 5))
        self.assertEqual(1, sent.call_count)
        self.assertEqual("🚫 Saved job taken down", sent.call_args.args[1])
        self.assertIn("RBC: Analyst", sent.call_args.args[2])
        self.assertEqual(1, sent.call_args.args[2].count("• "))

    def test_failed_send_is_retried_next_cycle(self):
        closed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.app("rbc:1")
        self.con.execute("INSERT INTO job_state(board, job_id, status, closed_at) VALUES ('rbc', '1', 'closed', ?)",
                         (closed_at,))
        with mock.patch.object(watcher, "send_discord_note", return_value=False):
            watcher.maybe_reminders(self.con, [sub()], datetime(2026, 10, 12, 6, 0))
        self.assertEqual(1, len(watcher.closed_saved_jobs(self.con)))


class UpdateCheckTests(unittest.TestCase):
    def service(self):
        svc = dashboard.JobwatchService.__new__(dashboard.JobwatchService)
        svc._update_cache = None
        return svc

    def reply(self, tag, url=None):
        response = mock.Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"tag_name": tag,
                                      "html_url": url or f"https://github.com/IdanG7/JobWatcher/releases/tag/{tag}"}
        return response

    def test_newer_release_is_reported_and_cached(self):
        svc = self.service()
        with mock.patch("version.APP_VERSION", "0.1.6"), \
                mock.patch.object(watcher.requests, "get", return_value=self.reply("v0.1.10")) as get:
            info = svc.update_info()
            svc.update_info()
        self.assertEqual(1, get.call_count)
        self.assertTrue(info["available"])
        self.assertEqual("0.1.10", info["latest"])

    def test_same_or_older_release_and_foreign_links_are_not_offered(self):
        for tag, url in (("v0.1.6", None), ("v0.1.5", None), ("v9.0.0", "https://evil.example/download")):
            svc = self.service()
            with mock.patch("version.APP_VERSION", "0.1.6"), \
                    mock.patch.object(watcher.requests, "get", return_value=self.reply(tag, url)):
                self.assertFalse(svc.update_info()["available"], tag)

    def test_offline_is_silent(self):
        svc = self.service()
        with mock.patch.object(watcher.requests, "get", side_effect=watcher.requests.ConnectionError()):
            self.assertFalse(svc.update_info()["available"])


if __name__ == "__main__":
    unittest.main()
