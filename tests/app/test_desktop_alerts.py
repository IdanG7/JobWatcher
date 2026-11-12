"""Windows notifications: what a notification says, that a posting's words never become part of a command,
who gets them by default, and that only the installed app shows them."""
import json
import subprocess
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from xml.etree import ElementTree

import desktop_alerts
import watcher
from tests.app.test_dashboard import ServiceFixture
from tests.sources.test_watcher_finance import FitAlertTests

HOOK = "https://discord.com/api/webhooks/1/made-up"


def ran(setting="Enabled", code=0):
    return MagicMock(returncode=code, stdout=f"setting={setting}\n", stderr="")


class NoticeTests(unittest.TestCase):
    def setUp(self):
        desktop_alerts._state.update(at=0.0, value="")
        on_windows = patch.object(desktop_alerts, "powershell", return_value=r"C:\Windows\powershell.exe")
        on_windows.start()
        self.addCleanup(on_windows.stop)

    def test_a_postings_words_are_text_and_never_markup_or_a_command(self):
        title = 'Analyst"; Remove-Item C:\\ -Recurse; <toast launch="calc.exe"> & $(whoami)'
        address = 'http://127.0.0.1:5550/#/x" onclick="'
        xml = desktop_alerts.toast_xml(title, ["Toronto <b>"], address)
        toast = ElementTree.fromstring(xml)                                  # still one well-formed notification
        self.assertEqual({"activationType": "protocol", "launch": address}, toast.attrib)
        self.assertEqual([title, "Toronto <b>"], [text.text for text in toast.iter("text")])
        self.assertEqual(1, len(list(toast.iter("toast"))))
        with patch.object(desktop_alerts.subprocess, "run", return_value=ran()) as run:
            self.assertTrue(desktop_alerts.show(title, ["Toronto"], "http://127.0.0.1:5550/"))
        command = run.call_args.args[0]
        self.assertEqual(desktop_alerts.SCRIPT, command[-1])                 # the same fixed script every time
        self.assertFalse(any("Remove-Item" in part for part in command))
        self.assertIn("Remove-Item", run.call_args.kwargs["env"]["FOOTHOLD_TOAST_XML"])

    def test_only_a_web_address_can_be_opened_by_a_click(self):
        for url in ("file:///C:/Windows/System32/calc.exe", "ms-settings:privacy", "calc.exe", ""):
            self.assertNotIn("launch", desktop_alerts.toast_xml("A role", [], url), url)
        self.assertIn('launch="http://127.0.0.1:5550/#/opportunities"',
                      desktop_alerts.toast_xml("A role", [], "http://127.0.0.1:5550/#/opportunities"))

    def test_one_role_names_it_and_several_are_counted(self):
        one = desktop_alerts.roles_notice([("Northwind", "Site Engineer", "Calgary, AB", "nw:12 3")],
                                          "http://127.0.0.1:5550/")
        self.assertEqual(("New on your short list: Northwind", ["Site Engineer", "Calgary, AB"],
                          "http://127.0.0.1:5550/#/opportunities?job=nw:12%203"), one)
        roles = [("Northwind", "Site Engineer", "", "nw:1"), ("Contoso", "Analyst", "", "c:2"),
                 ("Fabrikam", "Planner", "", "f:3"), ("Tailspin", "Estimator", "", "t:4")]
        title, lines, url = desktop_alerts.roles_notice(roles, "http://127.0.0.1:5550")
        self.assertEqual("4 new roles on your short list", title)
        self.assertEqual(["Northwind: Site Engineer", "Contoso: Analyst, and 2 more"], lines)
        self.assertEqual("http://127.0.0.1:5550/#/opportunities", url)

    def test_windows_having_notifications_off_is_reported_not_hidden(self):
        with patch.object(desktop_alerts.subprocess, "run", return_value=ran("DisabledForUser")):
            self.assertFalse(desktop_alerts.show("A role"))
            self.assertEqual("off", desktop_alerts.windows_state())
        with patch.object(desktop_alerts.subprocess, "run", return_value=ran()):
            self.assertEqual("on", desktop_alerts.windows_state(fresh=True))

    def test_a_failure_to_show_never_raises(self):
        for failure in (OSError("no powershell"), subprocess.TimeoutExpired("powershell", 20)):
            with patch.object(desktop_alerts.subprocess, "run", side_effect=failure):
                self.assertFalse(desktop_alerts.show("A role"))
        with patch.object(desktop_alerts.subprocess, "run", return_value=ran(code=1)):
            self.assertFalse(desktop_alerts.show("A role"))

    def test_on_unless_discord_is_connected_or_the_person_chose(self):
        self.assertTrue(desktop_alerts.enabled(None))
        self.assertTrue(desktop_alerts.enabled({}))
        self.assertFalse(desktop_alerts.enabled({"discord_webhook": HOOK}))
        self.assertTrue(desktop_alerts.enabled({"discord_webhook": HOOK, "desktop_notifications": True}))
        self.assertFalse(desktop_alerts.enabled({"desktop_notifications": False}))


class SubscriberTests(unittest.TestCase):
    def load(self, subscribers, app=True, windows=True):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "subscribers.json"
        path.write_text(json.dumps(subscribers), encoding="utf-8")
        with patch.object(watcher, "SUBSCRIBERS", path), patch.object(watcher, "DESKTOP_APP", app), \
                patch.object(desktop_alerts, "supported", return_value=windows):
            return {s["name"]: s for s in watcher.load_subscribers({})}

    def test_the_installed_app_reaches_someone_who_set_nothing_up(self):
        subs = self.load({})
        self.assertEqual(["desktop"], list(subs))
        self.assertTrue(subs["desktop"]["desktop"])
        self.assertEqual(("fit", True, True, ""), (subs["desktop"]["alert_mode"], subs["desktop"]["match_alerts"],
                                                   subs["desktop"]["reminders"], subs["desktop"]["discord"]))
        self.assertFalse(subs["desktop"]["finance_only"])

    def test_a_run_of_the_source_or_another_system_never_shows_them(self):
        self.assertEqual({}, self.load({}, app=False))
        self.assertEqual({}, self.load({}, windows=False))
        chosen = {"desktop": {"desktop_notifications": True}, "friend": {"discord_webhook": HOOK}}
        self.assertFalse(self.load(chosen, app=False)["desktop"]["desktop"])

    def test_discord_users_keep_one_channel_unless_they_ask_for_both(self):
        self.assertFalse(self.load({"desktop": {"discord_webhook": HOOK}})["desktop"]["desktop"])
        both = self.load({"desktop": {"discord_webhook": HOOK, "desktop_notifications": True},
                          "friend": {"discord_webhook": HOOK, "desktop_notifications": True}})
        self.assertTrue(both["desktop"]["desktop"])
        self.assertFalse(both["friend"]["desktop"])              # only the person at this PC
        self.assertFalse(self.load({"desktop": {"desktop_notifications": False}})["desktop"]["desktop"])


class DeliveryTests(unittest.TestCase):
    sub = FitAlertTests.sub
    intel = staticmethod(FitAlertTests.intel)

    def deliver(self, fits, **sub):
        con = watcher.db_open(":memory:")
        self.addCleanup(con.close)
        jobs = [("rbc", {"id": str(i), "title": f"Role {i}", "location": "Toronto, ON",
                         "url": f"https://x/{i}", "posted": time.time() - 3600}) for i in range(len(fits))]
        rows = {("rbc", str(i)): self.intel(fit, company=f"Firm {i}") for i, fit in enumerate(fits)}
        with patch.object(desktop_alerts, "show", return_value=True) as show, \
                patch("watcher.send_finance_alerts", return_value=True) as discord:
            watcher.deliver_fit(self.sub(**sub), jobs, rows, con, {"dashboard_url": "http://127.0.0.1:5550"},
                                {"target_cycles": ["summer_2027"]})
        return show, discord, con

    def test_a_poll_shows_one_notification_for_its_alert_worthy_roles(self):
        show, discord, con = self.deliver([95, 80, 78, 60, 30], desktop=True, discord="")
        discord.assert_not_called()
        self.assertEqual(1, show.call_count)
        title, lines, url = show.call_args.args
        self.assertEqual("3 new roles on your short list", title)            # 60 waits for the digest, 30 is dropped
        self.assertEqual(["Firm 0: Role 0", "Firm 1: Role 1, and 1 more"], lines)
        self.assertEqual("http://127.0.0.1:5550/#/opportunities", url)
        self.assertEqual(3, con.execute("SELECT COUNT(*) FROM alert_log").fetchone()[0])

    def test_one_role_is_named_and_opens_in_foothold(self):
        show, _, _ = self.deliver([95], desktop=True, discord="")
        self.assertEqual(("New on your short list: Firm 0", ["Role 0", "Toronto, ON"],
                          "http://127.0.0.1:5550/#/opportunities?job=rbc:0"), show.call_args.args)

    def test_nothing_alert_worthy_or_notifications_off_shows_nothing(self):
        self.assertFalse(self.deliver([60, 30], desktop=True, discord="")[0].called)
        show, discord, _ = self.deliver([95])                                # a Discord-only person
        self.assertFalse(show.called)
        self.assertTrue(discord.called)


class ReminderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.con = watcher.db_open(Path(self.tmp.name) / "jobwatch.db")
        self.addCleanup(self.tmp.cleanup)
        self.addCleanup(self.con.close)

    def test_the_morning_summary_reaches_a_person_without_discord(self):
        for key, company, day in (("a:1", "Northwind", "2026-10-13"), ("b:2", "Contoso", "2026-10-13"),
                                  ("c:3", "Fabrikam", "2026-10-14")):
            self.con.execute("INSERT INTO applications(job_key, company, title, url, status, deadline) "
                             "VALUES (?,?,?,?,?,?)", (key, company, "Analyst", "https://jobs.example/1", "saved", day))
        person = {"name": "desktop", "discord": "", "desktop": True, "reminders": True}
        with patch.object(desktop_alerts, "show", return_value=True) as show, \
                patch.object(watcher, "send_discord_note") as discord:
            watcher.maybe_reminders(self.con, [person], datetime(2026, 10, 12, 9, 0),
                                    {"dashboard_url": "http://127.0.0.1:5550"})
            watcher.maybe_reminders(self.con, [person], datetime(2026, 10, 12, 15, 0))
            watcher.maybe_reminders(self.con, [{**person, "desktop": False}], datetime(2026, 10, 13, 9, 0))
        discord.assert_not_called()
        self.assertEqual(1, show.call_count)                                 # once a day, and not when switched off
        title, lines, url = show.call_args.args
        self.assertIn("Foothold today", title)
        self.assertEqual(2, len(lines))
        self.assertIn("Deadline tomorrow: Northwind: Analyst", lines[0])     # plain words, no link markup
        self.assertNotIn("](", " ".join(lines))
        self.assertTrue(lines[1].endswith("and 1 more"))
        self.assertEqual("http://127.0.0.1:5550/#/overview", url)


class SettingsTests(ServiceFixture):
    def setUp(self):
        super().setUp()
        self.service.desktop = True
        for target, value in ((desktop_alerts.supported, True), (desktop_alerts.windows_state, "on")):
            p = patch.object(desktop_alerts, target.__name__, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def stored(self):
        return json.loads(self.service.subscribers_path.read_text(encoding="utf-8")).get("desktop")

    def test_on_by_default_and_the_choice_is_kept(self):
        self.assertEqual({"supported": True, "enabled": True, "windows": "on"}, self.service.get_desktop_alerts())
        self.assertFalse(self.service.put_desktop_alerts({"enabled": False})["enabled"])
        self.assertEqual(False, self.stored()["desktop_notifications"])
        self.assertEqual("fit", self.stored()["alert_mode"])
        self.assertTrue(self.service.put_desktop_alerts({"enabled": True})["enabled"])
        with self.assertRaises(Exception):
            self.service.put_desktop_alerts({"enabled": "yes"})

    def test_connecting_and_disconnecting_discord_keeps_the_choice(self):
        with patch.object(watcher, "send_discord_note", return_value=True):
            self.service.put_discord({"webhook": "https://discord.com/api/webhooks/123/abc-DEF"})
            self.assertFalse(self.service.get_desktop_alerts()["enabled"])       # Discord alone, until asked for both
            self.service.put_desktop_alerts({"enabled": True})
            self.service.put_discord({"webhook": "https://discord.com/api/webhooks/456/abc-DEF"})
        self.assertTrue(self.service.get_desktop_alerts()["enabled"])
        self.assertTrue(self.service.get_discord()["configured"])
        self.service.delete_discord()
        self.assertFalse(self.service.get_discord()["configured"])
        self.assertTrue(self.service.get_desktop_alerts()["enabled"])
        self.assertNotIn("discord_webhook", self.stored())

    def test_only_the_windows_app_offers_them(self):
        self.service.desktop = False
        self.assertEqual({"supported": False, "enabled": False, "windows": "unknown"},
                         self.service.get_desktop_alerts())
        with self.assertRaises(Exception):
            self.service.test_desktop_alerts()

    def test_a_test_says_when_windows_has_notifications_off(self):
        with patch.object(desktop_alerts, "show", return_value=True) as show:
            self.assertEqual({"ok": True}, self.service.test_desktop_alerts())
        self.assertEqual("Foothold test", show.call_args.args[0])
        with patch.object(desktop_alerts, "show", return_value=False), \
                patch.object(desktop_alerts, "windows_state", return_value="off"):
            with self.assertRaises(Exception) as refused:
                self.service.test_desktop_alerts()
        self.assertIn("Windows has notifications switched off", str(refused.exception))


if __name__ == "__main__":
    unittest.main()
