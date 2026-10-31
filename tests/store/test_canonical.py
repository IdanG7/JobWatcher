"""Canonical picks: re-picked where something they rank by changed, and only there."""

import json
import sqlite3
import time
import unittest
from unittest.mock import patch

import watcher
from intel_store import IntelStore, update_lifecycle
from tests.store.test_store import add_job, iso

CONFIG = {
    "profile": {},
    "boards": {
        "_canadian_banks": "---",
        "rbc": {"ats": "greenhouse", "token": "rbc"},
        "_quant": "---",
        "demo_quant": {"ats": "greenhouse", "token": "quant"},
        "_linkedin": "---",
        "linkedin_ca": {"ats": "linkedin", "location": "Canada"},
    },
}


def with_boards(**changes) -> dict:
    config = json.loads(json.dumps(CONFIG))
    for name, cfg in changes.items():
        if cfg is None:
            config["boards"].pop(name)
        else:
            config["boards"][name] = cfg
    return config


class CanonicalTests(unittest.TestCase):
    def setUp(self):
        self.con = watcher.db_open(":memory:")
        self.addCleanup(self.con.close)
        now = time.time()
        add_job(self.con, "rbc", "1", "2027 Investment Banking Summer Analyst", "Toronto, ON", "RBC", now - 7200,
                first_seen=iso(2))
        add_job(self.con, "linkedin_ca", "9", "2027 Investment Banking Summer Analyst", "Toronto, Ontario, Canada",
                "RBC Capital Markets", now - 3600, first_seen=iso(1))
        add_job(self.con, "demo_quant", "5", "Quantitative Researcher", "Chicago, IL", "Demo Capital", now - 3600,
                first_seen=iso(3))
        add_job(self.con, "linkedin_ca", "8", "Quantitative Researcher", "Chicago, IL", "Demo Capital", now - 3600,
                first_seen=iso(1))
        self.con.commit()
        IntelStore(self.con, CONFIG).refresh()
        self.assertEqual({"rbc:1", "demo_quant:5"}, self.canonical())
        self.assertEqual(2, self.con.execute("SELECT COUNT(DISTINCT cluster_key) FROM job_intel").fetchone()[0])

    def canonical(self) -> set[str]:
        return {f"{b}:{j}" for b, j in self.con.execute("SELECT board, job_id FROM job_intel WHERE is_canonical=1")}

    def unscored(self) -> set[str]:
        return {f"{b}:{j}" for b, j in self.con.execute("SELECT board, job_id FROM job_intel "
                                                        "WHERE profile_version IS NULL")}

    def repicked(self, config) -> list:
        """The clusters re-picked while ``config``'s store checks the ranks."""
        store = IntelStore(self.con, config)
        with patch.object(store, "recluster", wraps=store.recluster) as recluster:
            store.recluster_if_ranks_changed()
        return sorted(k for call in recluster.call_args_list for k in call.args[0])

    def test_an_added_source_repicks_and_rescores_nothing(self):
        config = with_boards(td={"ats": "workday", "url": "https://td.wd3.myworkdayjobs.com/TD"})
        self.assertEqual([], self.repicked(config))
        self.assertEqual(set(), self.unscored())
        self.assertEqual([], self.repicked(config))

    def test_a_rank_change_repicks_and_rescores_only_that_sources_clusters(self):
        config = with_boards(rbc={"ats": "greenhouse", "token": "rbc", "indirect_links": True})
        rbc_cluster = self.con.execute("SELECT cluster_key FROM job_intel WHERE board='rbc'").fetchone()[0]
        self.assertEqual([rbc_cluster], self.repicked(config))
        self.assertEqual({"linkedin_ca:9", "demo_quant:5"}, self.canonical())
        self.assertEqual({"rbc:1", "linkedin_ca:9"}, self.unscored())
        full = sqlite3.connect(":memory:")
        self.addCleanup(full.close)
        self.con.commit()
        self.con.backup(full)
        IntelStore(full, config).recluster([k for (k,) in full.execute("SELECT DISTINCT cluster_key FROM job_intel")])
        self.assertEqual(sorted(full.execute("SELECT board, job_id, is_canonical FROM job_intel")),
                         sorted(self.con.execute("SELECT board, job_id, is_canonical FROM job_intel")))

    def test_a_removed_source_repicks_everything(self):
        self.assertEqual(2, len(self.repicked(with_boards(demo_quant=None))))

    def test_a_canonical_posting_that_closes_or_reopens_is_repicked(self):
        store = IntelStore(self.con, CONFIG)
        life = update_lifecycle(self.con, "rbc", set(), True, iso())
        self.assertEqual([("rbc", "1")], life["changed"])
        store.recluster_postings(life["changed"])
        self.assertEqual({"linkedin_ca:9", "demo_quant:5"}, self.canonical())
        self.con.execute("UPDATE job_intel SET profile_version='x'")
        life = update_lifecycle(self.con, "rbc", {"1"}, True, iso())
        self.assertEqual([("rbc", "1")], life["changed"])
        self.assertEqual({"rbc:1"}, self.unscored())        # its fit loses the closed penalty
        store.recluster_postings(life["changed"])
        self.assertEqual({"rbc:1", "demo_quant:5"}, self.canonical())

    def test_a_canonical_posting_pruned_hands_the_flag_on(self):
        self.con.execute("UPDATE jobs SET last_seen=? WHERE board='demo_quant'", (iso(24 * 100),))
        self.con.execute("INSERT INTO kv(k, v) VALUES ('orphan_sweep', ?)", (iso(0),))
        watcher.prune(self.con, IntelStore(self.con, CONFIG))
        self.assertEqual({"rbc:1", "linkedin_ca:8"}, self.canonical())

    def test_picks_left_stale_by_older_versions_are_repaired_once(self):
        self.con.execute("UPDATE job_intel SET is_canonical=1-is_canonical WHERE board IN ('rbc', 'linkedin_ca') "
                         "AND job_id IN ('1', '9')")
        self.con.execute("DELETE FROM kv WHERE k='canonical_repaired'")
        self.assertEqual(0, IntelStore(self.con, CONFIG).refresh()["scored"])    # fits don't read the pick
        self.assertEqual({"rbc:1", "demo_quant:5"}, self.canonical())
        self.con.execute("UPDATE job_intel SET is_canonical=1-is_canonical WHERE board IN ('rbc', 'linkedin_ca') "
                         "AND job_id IN ('1', '9')")
        IntelStore(self.con, CONFIG).refresh()
        self.assertEqual({"linkedin_ca:9", "demo_quant:5"}, self.canonical())

    def test_a_poll_repicks_the_clusters_of_postings_that_closed(self):
        def fetch(name, cfg):
            listing = {"rbc": [("2", "Equity Research Associate", "Toronto, ON", "RBC")],
                       "demo_quant": [("5", "Quantitative Researcher", "Chicago, IL", "Demo Capital")],
                       "linkedin_ca": [("9", "2027 Investment Banking Summer Analyst", "Toronto, Ontario, Canada",
                                        "RBC Capital Markets"),
                                       ("8", "Quantitative Researcher", "Chicago, IL", "Demo Capital")]}[name]
            return name, [{"id": i, "title": t, "location": loc, "company": company,
                           "url": f"https://example.com/{name}/{i}"} for i, t, loc, company in listing]

        config = {**CONFIG, "description_budget": 0}
        self.con.executemany("INSERT OR REPLACE INTO boards(board, seeded, last_ok, failures, last_poll) "
                             "VALUES (?,1,?,0,0)", [(b, watcher.now()) for b in ("rbc", "demo_quant", "linkedin_ca")])
        self.con.commit()
        with patch.object(watcher, "fetch_board", side_effect=fetch), \
                patch.object(watcher, "load_subscribers", return_value=[]):
            watcher.cycle(config, self.con)
        self.assertEqual("possibly_closed", self.con.execute(
            "SELECT status FROM job_state WHERE board='rbc' AND job_id='1'").fetchone()[0])
        self.assertIn("linkedin_ca:9", self.canonical())
        self.assertNotIn("rbc:1", self.canonical())


if __name__ == "__main__":
    unittest.main()
