import unittest
from unittest import mock

import watcher

CARD = ('<li><div data-entity-urn="urn:li:jobPosting:{id}"></div>'
        '<h3 class="base-search-card__title">Analyst {id}</h3></li>')


def response(status, ids=(), headers=None):
    r = mock.Mock(status_code=status, headers=headers or {})
    r.text = "".join(CARD.format(id=i) for i in ids)
    r.raise_for_status.side_effect = None if status < 400 else watcher.requests.HTTPError(str(status))
    return r


class LinkedInRateLimitTests(unittest.TestCase):
    def setUp(self):
        watcher._linkedin_next = watcher._linkedin_blocked_until = 0.0
        self.sleeps = []
        patches = [mock.patch.object(watcher.time, "sleep", side_effect=self.sleeps.append),
                   mock.patch.object(watcher, "LINKEDIN_SPACING", 0),
                   mock.patch.object(watcher.random, "uniform", return_value=0)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(lambda: setattr(watcher, "_linkedin_blocked_until", 0.0))

    def test_429_is_retried_after_a_backoff_and_results_are_complete(self):
        replies = [response(429), response(200, ids=[1, 2]), response(400)]
        with mock.patch.object(watcher.requests, "get", side_effect=replies) as get:
            out = watcher.fetch_linkedin({"queries": ["analyst"], "pages": 3})
        self.assertEqual(["1", "2"], [j["id"] for j in out])
        self.assertNotIn("failed", out.reason)
        self.assertEqual(3, get.call_count)
        self.assertTrue(any(s >= watcher.LINKEDIN_BACKOFF[0] - 1 for s in self.sleeps), self.sleeps)

    def test_retry_after_header_is_honoured(self):
        replies = [response(429, headers={"Retry-After": "3"}), response(400)]
        with mock.patch.object(watcher.requests, "get", side_effect=replies):
            watcher.fetch_linkedin({"queries": ["analyst"], "pages": 1})
        self.assertTrue(any(2 <= s <= 3 for s in self.sleeps), self.sleeps)

    def test_persistent_429_pauses_linkedin_instead_of_hammering(self):
        with mock.patch.object(watcher.requests, "get", return_value=response(429)) as get:
            with self.assertRaises(watcher.LinkedInRateLimited):
                watcher.fetch_linkedin({"queries": ["a", "b", "c"], "pages": 2})
        # one request's retries, then the remaining queries are skipped while paused
        self.assertEqual(len(watcher.LINKEDIN_BACKOFF) + 1, get.call_count)

    def test_partial_results_survive_a_later_blocked_query(self):
        def reply(url, params, **kw):
            return response(200, ids=[7]) if params["keywords"] == "a" and params["start"] == 0 else (
                response(400) if params["keywords"] == "a" else response(429))
        with mock.patch.object(watcher.requests, "get", side_effect=reply):
            out = watcher.fetch_linkedin({"queries": ["a", "b"], "pages": 2})
        self.assertEqual(["7"], [j["id"] for j in out])
        self.assertIn("1 query request(s) failed", out.reason)


if __name__ == "__main__":
    unittest.main()
