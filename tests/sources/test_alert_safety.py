"""Alerts and posting pages: a failed send never logs where it was sent, one failed delivery doesn't stop the
poll, and a posting's link is only read from the public internet."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import watcher
from tests.app.test_dashboard import ServiceFixture

HOOK = "https://discord.com/api/webhooks/123456/made-up-token-value"


class SendLogTests(unittest.TestCase):
    def test_a_failed_send_never_logs_the_address_it_was_sent_to(self):
        refused = MagicMock(status_code=404)

        def send():
            raise watcher.requests.HTTPError(f"404 Client Error: Not Found for url: {HOOK}", response=refused)

        with patch.object(watcher.time, "sleep"), patch.object(watcher, "log") as log:
            self.assertFalse(watcher._post_with_retry(send, "discord"))
        said = " ".join(str(call.args[0]) for call in log.call_args_list)
        self.assertIn("discord", said)
        self.assertIn("404", said)
        self.assertNotIn("made-up-token-value", said)
        self.assertNotIn("webhooks", said)


class DeliveryFailureTests(ServiceFixture):
    def test_a_delivery_that_fails_does_not_stop_the_poll(self):
        self.service.config["description_budget"] = 0
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        subscribers = Path(folder.name) / "subscribers.json"
        subscribers.write_text(json.dumps({"me": {"discord_webhook": HOOK, "filters": {"include": "."}}}),
                               encoding="utf-8")
        listing = [{"id": "x1", "title": "Investment Banking Analyst", "location": "Toronto", "url": "https://e/x1"}]

        def fetch(name, cfg):
            return name, list(listing) if name == "rbc" else []

        patches = [patch.object(watcher, "fetch_board", side_effect=fetch),
                   patch.object(watcher, "SUBSCRIBERS", subscribers),
                   patch.object(watcher.requests, "post", return_value=MagicMock(status_code=204)),
                   patch.object(watcher, "deliver", side_effect=KeyError("title")),
                   patch.object(watcher, "deliver_fit", side_effect=KeyError("title")),
                   patch.object(watcher, "log")]
        started = [p.start() for p in patches]
        for p in patches:
            self.addCleanup(p.stop)
        con = watcher.db_open(self.db_path)
        try:
            watcher.cycle(self.service.config, con)      # the first poll of a source only records what is there
            listing.append({"id": "x2", "title": "Equity Research Analyst", "location": "Toronto",
                            "url": "https://e/x2"})
            con.execute("UPDATE boards SET last_poll=0")
            con.commit()
            watcher.cycle(self.service.config, con)
            polls = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
            recorded = con.execute("SELECT 1 FROM recent WHERE title='Equity Research Analyst'").fetchone()
        finally:
            con.close()
        self.assertTrue(started[3].called or started[4].called, "the new role was never handed to a delivery")
        self.assertEqual(2, polls)
        self.assertTrue(recorded)
        said = " ".join(str(call.args[0]) for call in started[5].call_args_list)
        self.assertIn("alerts for me failed", said)


class PrivateLinkTests(unittest.TestCase):
    def test_a_link_to_this_machine_or_the_home_network_is_not_fetched(self):
        for url in ("http://127.0.0.1:5550/api/overview", "http://localhost/x", "http://192.168.1.1/admin",
                    "http://[::1]/", "http://169.254.169.254/latest/meta-data", "http://printer.local/status",
                    "file:///C:/Users/someone/notes.txt", "ftp://example.com/posting"):
            with self.subTest(url), patch.object(watcher.requests, "get") as get:
                with self.assertRaises(ValueError):
                    watcher.detail_page(url)
                get.assert_not_called()

    def test_a_name_that_leads_to_a_private_address_is_not_fetched(self):
        with patch.object(watcher, "_host_ips", return_value={"10.0.0.5"}), patch.object(watcher.requests, "get") as get:
            with self.assertRaises(ValueError):
                watcher.detail_page("https://careers.example.com/jobs/1")
            get.assert_not_called()

    def test_a_redirect_to_a_private_address_is_not_followed(self):
        hop = MagicMock(is_redirect=True, url="https://careers.example.com/jobs/1",
                        headers={"location": "http://127.0.0.1:8080/admin"})
        with self.assertRaises(ValueError):
            watcher._refuse_private_redirect(hop)
        onward = MagicMock(is_redirect=True, url="https://careers.example.com/jobs/1", headers={"location": "/jobs/1/"})
        with patch.object(watcher, "_host_ips", return_value={"93.184.216.34"}):
            watcher._refuse_private_redirect(onward)

    def test_a_public_page_is_still_read(self):
        body = ("<html><body><main><h1>Analyst</h1><p>" + "Build three-statement models and prepare client materials. " * 12
                + "</p></main></body></html>")
        page = MagicMock(url="https://careers.example.com/jobs/1", status_code=200, content=body.encode("utf-8"),
                         headers={"content-type": "text/html; charset=utf-8"})
        page.__enter__.return_value = page
        page.__exit__.return_value = False
        page.raise_for_status.side_effect = None
        with patch.object(watcher, "_host_ips", return_value={"93.184.216.34"}), \
                patch.object(watcher.requests, "get", return_value=page) as get:
            text, _ = watcher.detail_page("https://careers.example.com/jobs/1")
        self.assertIn("three-statement", text)
        self.assertIs(watcher._refuse_private_redirect, get.call_args.kwargs["hooks"]["response"])


if __name__ == "__main__":
    unittest.main()
