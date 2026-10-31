"""A large backlog: listed once per pass, read by key, and its facts built in processes of their own, with the
same facts as one process builds."""

import os
import sqlite3
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import intel_store
import watcher
from intel_store import IntelStore
from tests.store.test_store import CONFIG, add_job

ROOT = Path(__file__).resolve().parents[2]
TITLES = ["2027 Investment Banking Summer Analyst", "Senior Software Engineer", "Registered Nurse - ICU",
          "Equity Research Associate", "Data Scientist Intern", "Pharmacist", "Quantitative Trader",
          "Product Designer", "Accountant, Audit", "Sales Development Representative"]


def intel_rows(con) -> list:
    con.row_factory = sqlite3.Row
    rows = [{k: r[k] for k in r.keys() if k not in ("facts_at", "scored_at")}
            for r in con.execute("SELECT * FROM job_intel ORDER BY board, job_id")]
    con.row_factory = None
    return rows


class FactsBacklogTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        now = time.time()
        for n in range(1200):
            add_job(self.con, "rbc" if n % 3 else "linkedin_ca", str(n), f"{TITLES[n % len(TITLES)]} {n // 10}",
                    ["Toronto, ON", "New York, NY", "Remote", "London, UK"][n % 4],
                    ["RBC", "Shopify", "UHN", "Goldman Sachs"][n % 4], posted=now - n * 3600)
            self.con.execute("INSERT INTO job_text(board, job_id, description) VALUES (?, ?, ?)",
                             ("rbc" if n % 3 else "linkedin_ca", str(n), "Excel, Python and SQL. BScN required."
                              if n % 2 else "Financial modelling for M&A. Applications close November 30, 2026."))
        self.con.commit()

    def clone(self):
        other = sqlite3.connect(":memory:")
        self.addCleanup(other.close)
        self.con.backup(other)
        return other

    def test_the_backlog_is_listed_once_a_pass(self):
        store = IntelStore(self.con, CONFIG)
        with patch.object(store, "_backlog_keys", wraps=store._backlog_keys) as listed:
            self.assertEqual(1200, store.facts_pass())
        self.assertEqual(2, listed.call_count)      # the backlog, then nothing left
        self.assertEqual(0, store.facts_pass())

    def test_a_limited_pass_takes_the_first_postings_in_order(self):
        store = IntelStore(self.con, CONFIG)
        first = store._backlog_keys(700)
        self.assertEqual(700, store.facts_pass(700))
        self.assertEqual(sorted(first), sorted(self.con.execute("SELECT board, job_id FROM job_intel")))

    def test_facts_built_in_processes_are_the_ones_built_here(self):
        here = self.clone()
        IntelStore(here, CONFIG).refresh()
        store = IntelStore(self.con, CONFIG)
        store.facts_workers = 2
        with patch.object(intel_store, "PARALLEL_FACTS_FROM", 1), \
                patch.object(store, "_facts_pool", wraps=store._facts_pool) as pool:
            store.refresh()
        self.assertEqual(1, pool.call_count)
        self.assertFalse(store._pool_failed)
        self.assertEqual(intel_rows(here), intel_rows(self.con))

    def test_facts_processes_start_while_a_thread_reads_commands_on_stdin(self):
        """The worker reads its commands from a stdin pipe the server keeps open. On Windows, a process started
        meanwhile hung as it started, on that pipe (found running the worker on the app's runtime)."""
        script = textwrap.dedent("""
            import sys, threading, time
            import intel_store, watcher
            from intel_store import IntelStore
            from tests.store.test_store import CONFIG, add_job
            threading.Thread(target=sys.stdin.readline, daemon=True).start()
            time.sleep(0.3)
            con = watcher.db_open(":memory:")
            for n in range(40):
                add_job(con, "rbc", str(n), f"2027 Investment Banking Summer Analyst {n}")
            intel_store.PARALLEL_FACTS_FROM = 1
            store = IntelStore(con, CONFIG)
            store.facts_workers = 2
            print(store.facts_pass(), store._pool_failed, flush=True)
        """)
        proc = subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, cwd=ROOT)
        try:
            proc.wait(timeout=90)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"] if os.name == "nt" else
                           ["kill", "-9", str(proc.pid)], capture_output=True)
            self.fail("the facts processes hung as they started")
        finally:
            proc.stdin.close()
        self.assertEqual("40 False", proc.stdout.read().decode().strip().splitlines()[-1])

    def test_a_pool_that_breaks_leaves_the_work_here(self):
        here = self.clone()
        IntelStore(here, CONFIG).refresh()

        class Broken:
            def map(self, *args):
                raise OSError("no processes")

            def shutdown(self, **kwargs):
                pass

        store = IntelStore(self.con, CONFIG)
        store.facts_workers = 2
        with patch.object(intel_store, "PARALLEL_FACTS_FROM", 1), patch.object(store, "_facts_pool", Broken):
            store.refresh()
        self.assertTrue(store._pool_failed)
        self.assertEqual(intel_rows(here), intel_rows(self.con))


if __name__ == "__main__":
    unittest.main()
