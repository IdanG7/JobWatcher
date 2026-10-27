"""Stated hours (plans/healthcare-board.md, D15): read from the title and stated phrases, never from passing
words; a fact and a filter, never fit points."""
import json
import sqlite3
import time
import unittest

from intel import analyze, load_knowledge, merge_profile
from intel.facts import FACTS_VERSION, build_facts
from intel.hours import extract_hours
from job_query import build_where

KN = load_knowledge()
NOW = time.time()


class HoursTests(unittest.TestCase):
    def test_titles_state_employment_type_and_shifts(self):
        for title, expected in (
                ("Registered Nurse - Casual, Nights", {"employment": ["casual"], "shifts": ["night"]}),
                ("Per Diem Days, 8a-4p Registered Nurse", {"employment": ["per_diem"], "shifts": ["day"]}),
                ("PRN Pharmacist", {"employment": ["per_diem"]}),
                ("RN - 12 Hour Rotating Shifts", {"shifts": ["rotating", "twelve_hour"]}),
                ("Pharmacy Technician - Part-Time, Days/Nights", {"employment": ["part_time"], "shifts": ["day", "night"]}),
                ("Nurse - Temp (Contract)", {"employment": ["temporary"]}),
                ("On-Call Patient Transporter", {"on_call": True})):
            self.assertEqual(expected, extract_hours(title), title)

    def test_descriptions_count_only_where_they_state_hours(self):
        stated = ("Employment Type: Part-Time\nStatus: Casual\nThis is a temporary full-time position. "
                  "Day shift and every other weekend; 12-hour rotating shifts.")
        self.assertEqual({"employment": ["full_time", "part_time", "casual", "temporary"],
                          "shifts": ["day", "weekend", "rotating", "twelve_hour"]}, extract_hours("Registered Nurse", stated))
        self.assertEqual({"on_call": True}, extract_hours("Site Reliability Engineer", "You will participate in an on-call rotation."))
        for description in ("Business casual dress. Full-time students in their third year may apply.",
                            "Strong performers receive a full-time offer after graduation.",
                            "Our long-term care partners and contract management teams.",
                            "Analysts may be required to work evenings and weekends."):
            self.assertEqual({}, extract_hours("Analyst", description), description)
        for title in ("Contracts Manager", "Day Surgery Nurse", "Long-Term Planning Analyst", "External Affairs Intern"):
            self.assertEqual({}, extract_hours(title), title)

    def test_every_posting_carries_hours_and_they_add_no_fit(self):
        self.assertEqual(11, FACTS_VERSION)
        job = {"title": "Investment Banking Analyst", "company": "Goldman Sachs", "location": "New York, NY",
               "posted": NOW - 3600}
        self.assertEqual({}, build_facts(job, KN)["hours"])
        stated = {**job, "description": "Employment type: Casual. Night shift and every other weekend."}
        self.assertEqual({"employment": ["casual"], "shifts": ["night", "weekend"]}, build_facts(stated, KN)["hours"])
        profile = merge_profile({"fields": ["finance"], "target_roles": ["investment_banking"]})
        base = analyze({**job, "description": "Work with the M&A team."}, profile, KN, now=NOW)
        shifts = analyze({**stated, "description": stated["description"] + " Work with the M&A team."}, profile, KN, now=NOW)
        self.assertEqual([(s["key"], s["points"]) for s in base["subscores"]],
                         [(s["key"], s["points"]) for s in shifts["subscores"]])

    def test_the_hours_filter_reads_the_facts(self):
        where, args = build_where({"hours": "casual,night,on_call,bogus"}, fts=False)
        clause = next(w for w in where if "hours" in w)
        con = sqlite3.connect(":memory:")
        rows = {"casual": {"hours": {"employment": ["casual"]}}, "nights": {"hours": {"shifts": ["night", "weekend"]}},
                "on_call": {"hours": {"on_call": True}}, "part_time": {"hours": {"employment": ["part_time"]}},
                "none": {}}
        hits = [name for name, facts in rows.items()
                if con.execute(f"SELECT 1 FROM (SELECT ? AS facts) i WHERE {clause}",
                               [json.dumps(facts), *[a for a in args if a in ("casual", "night")]]).fetchone()]
        self.assertEqual(["casual", "nights", "on_call"], hits)
        self.assertNotIn("bogus", args)
        self.assertFalse(any("hours" in w for w in build_where({}, fts=False)[0]))


if __name__ == "__main__":
    unittest.main()
