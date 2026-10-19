import json
import sqlite3
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import version
from dashboard import ApiError, JobwatchHandler, JobwatchService
from tests.app.test_dashboard import ServiceFixture


class WhatsNewTests(ServiceFixture):
    """The last version whose release notes were closed lives in the database, not the browser."""

    def running(self, app_version):
        return mock.patch.object(version, "APP_VERSION", app_version)

    def restart(self, app_version):
        with self.running(app_version):
            return JobwatchService(self.db_path, self.config_path, self.subscribers_path)

    def mark(self):
        con = sqlite3.connect(self.db_path)
        try:
            row = con.execute("SELECT v FROM kv WHERE k='whats_new_seen'").fetchone()
        finally:
            con.close()
        return row[0] if row else None

    def forget(self):
        """A database from before this card: a dashboard has opened it, but it has no mark."""
        con = sqlite3.connect(self.db_path)
        con.execute("DELETE FROM kv WHERE k='whats_new_seen'")
        con.commit()
        con.close()

    def test_a_new_install_has_nothing_to_catch_up_on(self):
        self.assertEqual({"version": version.APP_VERSION, "seen": version.APP_VERSION}, self.service.whats_new())

    def test_an_update_keeps_the_mark_so_the_new_notes_show(self):
        installed = version.APP_VERSION
        service = self.restart("9.9.0")
        with self.running("9.9.0"):
            self.assertEqual({"version": "9.9.0", "seen": installed}, service.whats_new())

    def test_an_existing_install_without_a_mark_shows_this_versions_notes(self):
        self.forget()
        service = self.restart("9.9.0")
        with self.running("9.9.0"):
            self.assertEqual({"version": "9.9.0", "seen": None}, service.whats_new())

    def test_closing_marks_the_version_and_never_moves_back(self):
        self.forget()
        with self.running("9.9.5"):
            self.assertEqual("9.9.4", self.service.close_whats_new({"version": "9.9.4"})["seen"])
            self.assertEqual("9.9.5", self.service.close_whats_new({"version": "9.9.5"})["seen"])
            # A tab left open from before the update closes its older card: the mark stays.
            self.assertEqual("9.9.5", self.service.close_whats_new({"version": "9.9.4"})["seen"])
            for bad in ({"version": "9.9.6"}, {"version": "latest"}, {"version": ""}, {}, {"version": "1.2.3.4"}):
                with self.assertRaises(ApiError, msg=bad):
                    self.service.close_whats_new(bad)
        self.assertEqual("9.9.5", self.mark())

    def test_versions_compare_by_number(self):
        with self.running("9.9.10"):
            self.service.close_whats_new({"version": "9.9.10"})
            self.assertEqual("9.9.10", self.service.close_whats_new({"version": "9.9.9"})["seen"])


class WhatsNewHttpTests(ServiceFixture):
    def setUp(self):
        super().setUp()
        handler = type("H", (JobwatchHandler,), {"service": self.service})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def call(self, method, path, body=None):
        request = urllib.request.Request(f"http://127.0.0.1:{self.server.server_port}{path}", method=method,
                                         data=json.dumps(body).encode() if body is not None else None,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def test_endpoints(self):
        status, body = self.call("GET", "/api/whats-new")
        self.assertEqual((200, {"version": version.APP_VERSION, "seen": version.APP_VERSION}), (status, body))
        status, body = self.call("POST", "/api/whats-new/seen", {"version": version.APP_VERSION})
        self.assertEqual((200, version.APP_VERSION), (status, body["seen"]))
        self.assertEqual(400, self.call("POST", "/api/whats-new/seen", {"version": "99.0.0"})[0])
        self.assertEqual(400, self.call("POST", "/api/whats-new/seen", ["0.3.4"])[0])
