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

    def test_united_kingdom_filter_covers_the_whole_country(self):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.executescript("""CREATE TABLE jobs(title TEXT); INSERT INTO jobs VALUES ('intern');
            CREATE TABLE job_intel(country TEXT, location_bucket TEXT, facts TEXT);
            CREATE TABLE job_state(status TEXT); INSERT INTO job_state VALUES ('active');""")
        kn = load_knowledge()
        for location in ("London, United Kingdom", "Edinburgh, Scotland", "Manchester, England, UK",
                         "London, ON", "New York, NY"):
            facts = build_facts({"title": "Finance Intern", "location": location}, kn)
            loc = facts["location"]
            con.execute("INSERT INTO job_intel VALUES (?,?,?)",
                        ((loc["countries"] or [None])[0], loc["bucket"], json.dumps(facts)))
        where, args = build_where({"location": "UK", "all_sources": "1", "include_hidden": "1",
                                   "include_closed": "1"}, False)
        self.assertEqual(3, con.execute("SELECT COUNT(*) FROM job_intel i CROSS JOIN jobs j WHERE " +
                                       " AND ".join(where), args).fetchone()[0])

    def test_saved_united_kingdom_choices_use_the_location_code(self):
        # Settings once saved the United Kingdom as GB; postings are tagged UK.
        profile = merge_profile({"target_countries": ["CA", "GB"],
                                 "work_authorization": {"CA": "citizen", "GB": "citizen"}})
        self.assertEqual(["CA", "UK"], profile["target_countries"])
        self.assertEqual("citizen", profile["work_authorization"]["UK"])
        self.assertNotIn("GB", profile["work_authorization"])
        kn = load_knowledge()
        facts = build_facts({"title": "Investment Banking Summer Analyst", "location": "London, United Kingdom"}, kn)
        result = match_resume(facts, profile, score_job(facts, profile, kn))
        notes = [*result.get("exclusions", []), *result.get("review", [])]
        self.assertNotIn("Location is outside your target countries", notes)
        self.assertNotIn("Work authorization is not confirmed for the posting location", notes)

    def test_canadian_city_disambiguates_ca_but_california_still_us(self):
        kn = load_knowledge()
        for location, expected in (("Toronto, CA", ["CA"]), ("Los Angeles, CA", ["US"])):
            facts = build_facts({"title": "Finance Intern", "location": location}, kn)
            self.assertEqual(expected, facts["location"]["countries"])


class FamilyFilterTests(unittest.TestCase):
    """Interests can mix job families: finance (any finance category) plus software, say."""

    def count(self, family):
        con = sqlite3.connect(":memory:")
        self.addCleanup(con.close)
        con.executescript("""CREATE TABLE jobs(title TEXT); INSERT INTO jobs VALUES ('x');
            CREATE TABLE job_intel(family TEXT, is_finance INT);
            INSERT INTO job_intel VALUES ('finance', 1), ('software', 0), ('data_ml', 0), ('sales', 0);""")
        where, args = build_where({"family": family, "all_sources": "1", "include_hidden": "1",
                                   "include_closed": "1"}, False)
        return con.execute("SELECT COUNT(*) FROM job_intel i CROSS JOIN jobs j WHERE " +
                           " AND ".join(where), args).fetchone()[0]

    def test_single_family_keeps_its_meaning(self):
        self.assertEqual(1, self.count("finance"))
        self.assertEqual(1, self.count("software"))
        self.assertEqual(4, self.count(None))

    def test_families_can_be_combined(self):
        self.assertEqual(2, self.count("software,data_ml"))
        self.assertEqual(3, self.count("finance,software,data_ml"))
