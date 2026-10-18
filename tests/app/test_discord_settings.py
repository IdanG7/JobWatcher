import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import watcher
from dashboard import ApiError, JobwatchService

HOOK = "https://discord.com/api/webhooks/123456789/abc-DEF_ghi"


class DiscordSettingsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "config.json").write_text(json.dumps({"boards": {}}), encoding="utf-8")
        (root / "subscribers.json").write_text(json.dumps({"other": {"companies": ["all"]}}), encoding="utf-8")
        self.service = JobwatchService(root / "jobwatch.db", root / "config.json", root / "subscribers.json")
        self.subs = root / "subscribers.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_connect_sends_test_and_creates_subscriber(self):
        with mock.patch.object(watcher, "send_discord_note", return_value=True) as sent:
            result = self.service.put_discord({"webhook": HOOK})
        sent.assert_called_once()
        self.assertTrue(result["configured"])
        self.assertNotIn(HOOK, json.dumps(result))
        subs = json.loads(self.subs.read_text(encoding="utf-8"))
        self.assertEqual(HOOK, subs["desktop"]["discord_webhook"])
        self.assertIn("other", subs)

    def test_rejects_non_discord_urls_without_sending(self):
        with mock.patch.object(watcher, "send_discord_note") as sent:
            for bad in ("", "http://discord.com/api/webhooks/1/x", "https://evil.example/api/webhooks/1/x",
                        "https://discord.com.evil.example/api/webhooks/1/x"):
                with self.assertRaises(ApiError):
                    self.service.put_discord({"webhook": bad})
        sent.assert_not_called()
        self.assertNotIn("desktop", json.loads(self.subs.read_text(encoding="utf-8")))

    def test_failed_test_message_does_not_save(self):
        with mock.patch.object(watcher, "send_discord_note", return_value=False):
            with self.assertRaises(ApiError):
                self.service.put_discord({"webhook": HOOK})
        self.assertFalse(self.service.get_discord()["configured"])

    def test_test_button_sends_to_saved_webhook(self):
        with self.assertRaises(ApiError):
            self.service.test_discord()
        with mock.patch.object(watcher, "send_discord_note", return_value=True):
            self.service.put_discord({"webhook": HOOK})
        with mock.patch.object(watcher, "send_discord_note", return_value=True) as sent:
            self.assertEqual({"ok": True}, self.service.test_discord())
        self.assertEqual(HOOK, sent.call_args.args[0])
        with mock.patch.object(watcher, "send_discord_note", return_value=False):
            with self.assertRaises(ApiError):
                self.service.test_discord()

    def test_disconnect_removes_only_desktop_subscriber(self):
        with mock.patch.object(watcher, "send_discord_note", return_value=True):
            self.service.put_discord({"webhook": HOOK})
        self.assertFalse(self.service.delete_discord()["configured"])
        self.assertIn("other", json.loads(self.subs.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()


class DiscordModeTests(DiscordSettingsTests):
    def test_views_only_mode_is_saved_survives_reconnect_and_turns_off_match_alerts(self):
        with mock.patch.object(watcher, "send_discord_note", return_value=True):
            self.service.put_discord({"webhook": HOOK})
            self.assertEqual("matches_and_views", self.service.get_discord()["mode"])
            self.assertEqual("views_only", self.service.put_discord_settings({"mode": "views_only"})["mode"])
            self.service.put_discord({"webhook": HOOK})
        self.assertEqual("views_only", self.service.get_discord()["mode"])
        with mock.patch.object(watcher, "SUBSCRIBERS", self.subs):
            desktop = next(s for s in watcher.load_subscribers({}) if s["name"] == "desktop")
        self.assertFalse(desktop["match_alerts"])
        self.assertTrue(desktop["saved_search_alerts"])
        with self.assertRaises(ApiError):
            self.service.put_discord_settings({"mode": "everything"})
