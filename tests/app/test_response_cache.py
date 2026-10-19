"""The pages' response cache: kept until the data changes, refreshed in the background, never stale after a
change the user made."""
import sqlite3
import threading
import time
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

    def test_a_page_is_kept_until_the_data_changes(self):
        with patch.object(dashboard, "CACHE_REFRESH_SECONDS", 0):
            self.assertEqual(1, self.service.cached("page", self.compute))
            self.assertEqual(1, self.service.cached("page", self.compute))     # however long ago: nothing changed
            self.commit_elsewhere()
            self.assertEqual(2, self.service.cached("page", self.compute))

    def test_postings_arriving_leave_the_page_as_it_was_for_a_while(self):
        self.assertEqual(1, self.service.cached("page", self.compute))
        self.commit_elsewhere()
        self.assertEqual(1, self.service.cached("page", self.compute))         # keep_ready refreshes it meanwhile

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
