"""The pages' response cache: kept until the data changes, refreshed in the background, never stale after a
change the user made."""
import json
import sqlite3
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import dashboard
from tests.app import test_dashboard as fixtures


class ResponseCacheTests(fixtures.ServiceFixture):
    def setUp(self):
        super().setUp()
        self.calls = 0

    def compute(self):
        self.calls += 1
        return self.calls

    def commit_elsewhere(self):
        """A change from another connection, as a poll or the scorer makes."""
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cache_test', ?)", (str(time.time()),))
        con.commit()
        con.close()

    def wait_for_calls(self, n):
        deadline = time.monotonic() + 5
        while self.calls < n and time.monotonic() < deadline:
            time.sleep(0.02)

    def test_a_page_is_kept_until_the_data_changes(self):
        with patch.object(dashboard, "CACHE_REFRESH_SECONDS", 0), patch.object(dashboard, "CACHE_STALE_SECONDS", 0):
            self.assertEqual(1, self.service.cached("page", self.compute))
            self.assertEqual(1, self.service.cached("page", self.compute))     # however long ago: nothing changed
            self.commit_elsewhere()
            self.assertEqual(2, self.service.cached("page", self.compute))

    def test_postings_arriving_leave_the_page_as_it_was_for_a_while(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.commit_elsewhere()
        self.assertEqual(1, self.service.cached("page", self.compute))         # keep_ready refreshes it meanwhile

    def test_after_background_changes_the_kept_page_shows_while_it_is_recomputed(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.commit_elsewhere()
        with patch.object(dashboard, "CACHE_REFRESH_SECONDS", 0):
            self.assertEqual((1, True), self.service.cached_page("page", self.compute))
            self.wait_for_calls(2)
            self.assertEqual((2, False), self.service.cached_page("page", self.compute))
        self.assertEqual(2, self.calls)

    def test_a_refresh_the_user_clicked_waits_for_current_data(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.assertEqual(1, self.service.cached("page", self.compute, fresh=True))     # nothing changed
        self.commit_elsewhere()
        self.assertEqual(2, self.service.cached("page", self.compute, fresh=True))

    def test_background_work_finishing_keeps_the_pages(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.service.data_changed()
        self.assertEqual(1, self.service.cached("page", self.compute))

    def test_a_change_the_user_made_is_never_served_stale(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.service.invalidate()
        self.assertEqual(2, self.service.cached("page", self.compute))

    def test_requests_for_a_page_being_computed_wait_for_it(self):
        release, started = threading.Event(), threading.Event()

        def slow():
            started.set()
            release.wait(5)
            return self.compute()

        answers = []
        first = threading.Thread(target=lambda: answers.append(self.service.cached("page", slow)))
        first.start()
        started.wait(5)
        second = threading.Thread(target=lambda: answers.append(self.service.cached("page", slow)))
        second.start()
        time.sleep(0.1)
        release.set()
        first.join(5)
        second.join(5)
        self.assertEqual([1, 1], answers)
        self.assertEqual(1, self.calls)

    def test_the_pages_in_use_are_recomputed_in_the_background(self):
        threading.Thread(target=self.service.keep_ready, daemon=True).start()
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.service.invalidate()
        deadline = time.monotonic() + 5
        while self.calls < 2 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(2, self.calls)                                         # nobody asked for it
        self.assertEqual(2, self.service.cached("page", self.compute))
        self.assertEqual(2, self.calls)

    def test_a_page_nobody_has_asked_for_lately_is_left_alone(self):
        self.service.cached("page", self.compute)
        with patch.object(dashboard, "CACHE_HOT_SECONDS", 0):
            threading.Thread(target=self.service.keep_ready, daemon=True).start()
            self.service.invalidate()
            time.sleep(0.3)
        self.assertEqual(1, self.calls)

    def test_the_resume_pending_count_is_counted_again_after_a_change(self):
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT INTO candidate_resume(id, filename, parsed, enabled, version, updated_at) "
                    "VALUES (1, 'resume.pdf', '{}', 1, 'v1', '2026-10-01')")
        con.commit()
        self.service.data_version()                 # the response cache's connection is open
        before = self.service.get_resume()["pending"]
        con.execute("INSERT INTO jobs VALUES ('rbc', 'new', 'Summer Analyst', 'Toronto, ON', "
                    "'https://example.com/new', '2026-10-01', '2026-10-01')")
        con.commit()
        con.close()
        self.assertEqual(before + 1, self.service.get_resume()["pending"])


class ResponseCacheHttpTests(fixtures.ServiceFixture):
    def setUp(self):
        super().setUp()
        handler = type("H", (dashboard.JobwatchHandler,), {"service": self.service})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.cleared = 0
        clear = self.service.invalidate

        def counted():
            self.cleared += 1
            clear()
        self.service.invalidate = counted

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        super().tearDown()

    def call(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.base + path, data=data, method=method, headers={
            "Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.headers.get("X-Foothold-Stale"), json.loads(response.read() or b"null")

    def test_changes_that_leave_the_pages_as_they_were_keep_them(self):
        from version import APP_VERSION
        self.call("POST", "/api/whats-new/seen", {"version": APP_VERSION})
        self.call("POST", "/api/refresh", {})
        self.assertEqual(0, self.cleared)
        self.call("POST", "/api/applications", {"key": "rbc:one", "status": "saved"})
        self.assertEqual(1, self.cleared)

    def test_a_kept_page_says_so_and_a_refresh_gets_the_current_one(self):
        self.assertEqual(None, self.call("GET", "/api/companies")[0])
        con = sqlite3.connect(self.db_path)
        con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cache_test', 'changed')")
        con.commit()
        con.close()
        with patch.object(dashboard, "CACHE_REFRESH_SECONDS", 0):
            self.assertEqual("1", self.call("GET", "/api/companies")[0])
            self.assertEqual(None, self.call("GET", "/api/companies", headers={"Cache-Control": "no-cache"})[0])
