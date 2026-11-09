"""tools/poll_time.py: a poll replayed from source times, and each source timed once with its lock group's turns."""

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tools import poll_time

ROOT = Path(__file__).resolve().parents[2]


class ReplayTests(unittest.TestCase):
    def test_sources_go_to_the_next_free_thread_in_poll_order(self):
        seconds = {"a": 5, "b": 3, "c": 1, "d": 4}
        # a on thread 0 (0-5), b on 1 (0-3), c on 1 (3-4), d on 1 (4-8)
        self.assertEqual(8, poll_time.replay(["a", "b", "c", "d"], seconds, {}, workers=2))
        self.assertEqual(13, poll_time.replay(["a", "b", "c", "d"], seconds, {}, workers=1))

    def test_a_lock_group_runs_one_source_at_a_time_and_holds_its_thread_while_it_waits(self):
        seconds = {"li1": 10, "li2": 10, "x": 1}
        group = {"li1": "linkedin", "li2": "linkedin"}
        # li2 takes thread 1 at 0 but starts at 10; x takes thread 0 when li1 is done
        self.assertEqual(20, poll_time.replay(["li1", "li2", "x"], seconds, group, workers=2))
        self.assertEqual(20, poll_time.replay(["li1", "li2", "x"], seconds, group, workers=10))
        self.assertEqual(10, poll_time.replay(["li1", "li2", "x"], seconds, {}, workers=10))


class TimeSourcesTests(unittest.TestCase):
    def test_each_source_is_read_once_lock_groups_in_turn_and_a_failure_is_recorded(self):
        spans, guard = {}, threading.Lock()

        def fetch(name, cfg):
            t0 = time.perf_counter()
            time.sleep(0.05)
            with guard:
                spans[name] = (t0, time.perf_counter())
            if name == "broken":
                raise RuntimeError("403 Forbidden")
            return name, [{"id": "1"}, {"id": "2"}]

        sources = {"li1": {"ats": "linkedin"}, "li2": {"ats": "linkedin"}, "gh": {"ats": "greenhouse"},
                   "broken": {"ats": "workday"}}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.jsonl"
            out.write_text(json.dumps({"name": "gh", "seconds": 1.0, "error": ""}) + "\n", encoding="utf-8")
            poll_time.time_sources(sources, out, workers=4, fetch=fetch)
            rows = poll_time.read_timings(out)
        self.assertEqual({"li1", "li2", "broken"}, set(spans))      # gh was already timed
        self.assertTrue(spans["li1"][1] <= spans["li2"][0] or spans["li2"][1] <= spans["li1"][0])
        self.assertEqual(2, rows["li1"]["count"])
        self.assertEqual("RuntimeError: 403 Forbidden", rows["broken"]["error"])
        self.assertGreater(rows["broken"]["seconds"], 0)

    def test_a_profile_reports_its_linkedin_time_and_its_untimed_and_failed_sources(self):
        timings = {"li": {"seconds": 100, "error": ""}, "wd": {"seconds": 5, "error": "HTTPError: 500"}}
        report = poll_time.profile_times({"li": "linkedin", "wd": "workday", "new": "greenhouse"}, timings)
        self.assertEqual((3, 100, 100), (report["sources"], report["poll"], report["linkedin"]))
        self.assertEqual((["new"], ["wd"]), (report["untimed"], report["failed"]))

    def test_lever_and_eightfold_are_serialised_for_the_upper_bound_and_free_for_the_lower(self):
        # They only space their requests' starts, so two slow Lever reads can overlap in a real poll.
        timings = {n: {"seconds": 2, "error": ""} for n in ("lv1", "lv2", "ef")}
        report = poll_time.profile_times({"lv1": "lever", "lv2": "lever", "ef": "eightfold"}, timings)
        self.assertEqual((4, 2), (report["poll"], report["poll_low"]))
        self.assertEqual((4, 2, ["ef"]), (report["lever"], report["eightfold"], report["eightfold_sources"]))


class OrdersTests(unittest.TestCase):
    def test_every_sample_profile_polls_in_config_order_and_everything_polls_every_source(self):
        orders = poll_time.orders(ROOT)
        everything = list(orders["everything"])
        self.assertIn("product", orders)
        for name, order in orders.items():
            with self.subTest(profile=name):
                listed = [n for n in everything if n in order]
                self.assertEqual(listed, list(order))
        self.assertEqual("linkedin", orders["product"]["linkedin_us_product"])
        self.assertNotIn("linkedin_us_product", orders["finance"])


if __name__ == "__main__":
    unittest.main()
