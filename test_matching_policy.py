"""Interests rank finance roles; eligibility and country filters keep their meaning."""
import json
import sqlite3
import unittest

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.matching import match_resume
from job_query import build_where


class MatchingPolicyTests(unittest.TestCase):
    def test_finance_outside_interests_stays_visible_and_targets_rank_higher(self):
        kn = load_knowledge()
        profile = merge_profile({"target_roles": ["corporate_finance.treasury"],
                                 "target_cycles": [], "target_stages": ["internship"]})
        scores = []
        for title in ("Treasury Analyst Intern", "Equity Research Intern"):
            facts = build_facts({"title": title, "location": "Toronto, ON"}, kn)
            scored = score_job(facts, profile, kn)
            self.assertTrue(match_resume(facts, profile, scored)["matched"])
            scores.append(scored["score"] if "score" in scored else scored["fit"])
        self.assertGreater(scores[0], scores[1])
        facts = build_facts({"title": "Software Engineering Intern", "location": "Toronto, ON"}, kn)
        self.assertFalse(match_resume(facts, profile, score_job(facts, profile, kn))["matched"])

    def test_country_filter_includes_remote_and_multi_country_postings(self):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.executescript("""CREATE TABLE jobs(title TEXT); INSERT INTO jobs VALUES ('intern');
            CREATE TABLE job_intel(country TEXT, location_bucket TEXT, facts TEXT);
            CREATE TABLE job_state(status TEXT); INSERT INTO job_state VALUES ('active');""")
        kn = load_knowledge()
        for location in ("Remote - Canada", "Toronto, ON / New York, NY", "New York, NY"):
            facts = build_facts({"title": "Finance Intern", "location": location}, kn)
            loc = facts["location"]
            con.execute("INSERT INTO job_intel VALUES (?,?,?)",
                        (loc["countries"][0], loc["bucket"], json.dumps(facts)))
        where, args = build_where({"location": "canada", "all_sources": "1", "include_hidden": "1",
                                  "include_closed": "1"}, False)
        self.assertEqual(2, con.execute("SELECT COUNT(*) FROM job_intel i CROSS JOIN jobs j WHERE " +
                                       " AND ".join(where), args).fetchone()[0])

    def test_canadian_city_disambiguates_ca_but_california_still_us(self):
        kn = load_knowledge()
        for location, expected in (("Toronto, CA", ["CA"]), ("Los Angeles, CA", ["US"])):
            facts = build_facts({"title": "Finance Intern", "location": location}, kn)
            self.assertEqual(expected, facts["location"]["countries"])
