"""Regression tests for the 2026-10 reliability audit (batch 2): jobs wrongly
hidden or mislabelled by resume matching."""
import time
import unittest
from unittest.mock import patch

from intel import build_facts, load_knowledge, merge_profile, score_job
from intel.cycle import detect_cycle, graduation_window
from intel.matching import match_resume
from intel.resume import _graduation
from intel.resume_insights import experience_entries
from intel.seniority import detect_seniority
from intel.taxonomy import classify
import watcher

KN = load_knowledge()


def match(job, **profile):
    profile = merge_profile({"target_cycles": [], **profile})
    facts = build_facts({"location": "Toronto, ON", **job}, KN)
    return facts, match_resume(facts, profile, score_job(facts, profile, KN))


class GraduationTests(unittest.TestCase):
    def test_graduating_range_is_read_as_a_range(self):
        window = graduation_window("Candidates graduating Dec 2027 – Jun 2028 are eligible.")
        self.assertEqual(("2027-12", "2028-06"), (window["start"], window["end"]))

    def test_month_near_miss_is_a_review_note_not_an_exclusion(self):
        job = {"title": "Investment Banking Summer Analyst", "company": "RBC",
               "description": "Summer 2027 internship. Graduation date of May 2028."}
        _, near = match(job, graduation_year=2028, graduation_month=4, target_roles=["investment_banking"])
        self.assertTrue(near["matched"], near["exclusions"])
        self.assertTrue(any("close" in r for r in near["review"]))
        _, far = match(job, graduation_year=2029, graduation_month=4, target_roles=["investment_banking"])
        self.assertFalse(far["matched"])


class TitleTests(unittest.TestCase):
    def test_summer_and_student_titles_are_internships(self):
        for title in ("Summer 2027 Analyst – Global Banking", "Student, Treasury Reporting Analyst",
                      "Treasury Analyst (Student)", "Summer Investment Management Analyst"):
            self.assertEqual("internship", detect_seniority(title)["stage"], title)
        self.assertEqual("entry", detect_seniority("Student Loan Analyst")["stage"])

    def test_team_names_do_not_make_a_role_senior(self):
        for title in ("Analyst, Office of the CFO", "Analyst - Office of the Chief Financial Officer",
                      "Analyst, Chief Investment Office", "Analyst, Head Office Finance"):
            self.assertEqual("entry", detect_seniority(title)["stage"], title)
        self.assertEqual("senior", detect_seniority("Chief Financial Officer")["stage"])
        self.assertEqual("senior", detect_seniority("Head of Trading")["stage"])

    def test_campus_recruiter_is_not_a_new_grad_job(self):
        self.assertNotEqual("new_grad", detect_seniority("Campus Recruiter")["stage"])
        self.assertEqual("new_grad", detect_seniority("Campus Hire Analyst")["stage"])

    def test_plain_analyst_is_reviewed_for_new_grad_targets(self):
        job = {"title": "Analyst, Global Investment Banking - Mining & Metals", "company": "RBC"}
        _, result = match(job, target_roles=["investment_banking"], target_stages=["new_grad"])
        self.assertTrue(result["matched"], result["exclusions"])
        _, store = match({"title": "Warehouse Associate"}, target_stages=["new_grad"])
        self.assertFalse(store["matched"])


class EmployerPriorTests(unittest.TestCase):
    def test_employer_only_guess_is_not_a_target_match(self):
        cls = classify("Global Technology Summer Analyst", KN, company_type="bulge_bracket")
        self.assertTrue(cls["prior_only"])
        self.assertFalse(classify("Investment Banking Summer Analyst", KN, company_type="bulge_bracket")["prior_only"])
        facts, result = match({"title": "Global Technology Summer Analyst", "company": "Goldman Sachs"},
                              target_roles=["investment_banking"])
        self.assertTrue(facts["classification"]["prior_only"])
        self.assertFalse(any(r.startswith("Relevant role") for r in result["reasons"]))
        self.assertTrue(any("Division is not named" in r for r in result["review"]))


class CycleTests(unittest.TestCase):
    def test_past_years_in_descriptions_do_not_set_the_cycle(self):
        cycle = detect_cycle("Investment Banking Summer Analyst",
                             "Our 2025 Summer Analysts closed 40 deals. The Summer 2027 program runs 10 weeks.",
                             "internship", time.time())
        self.assertEqual("summer_2027", cycle["cycle"])


class ClusterTests(unittest.TestCase):
    def test_unknown_towns_are_not_merged_country_wide(self):
        keys = {build_facts({"title": "Relationship Banker", "company": "BMO", "location": place}, KN)["cluster_key"]
                for place in ("Brampton, ON", "Kelowna, BC, Canada")}
        self.assertEqual(2, len(keys))
        same = {build_facts({"title": "Relationship Banker", "company": "BMO", "location": place}, KN)["cluster_key"]
                for place in ("Canada", "Remote - Canada")}
        self.assertEqual(1, len(same))


class ResumeParsingTests(unittest.TestCase):
    def test_gpa_on_ten_and_twelve_point_scales(self):
        from intel.resume import _GPA
        self.assertEqual(("10.5", "12"), _GPA.search("GPA: 10.5/12").groups())
        self.assertEqual(("8.7", "10"), _GPA.search("CGPA 8.7/10").groups())

    def test_date_formats_keep_the_role_title(self):
        lines = ["Example Co", "Treasury Analyst | May – Aug 2026", "Big Bank",
                 "Investment Banking Summer Analyst 05/2026 – 08/2026", "Acme Capital",
                 "Summer 2025 Equity Research Intern"]
        titles = [e["title"] for e in experience_entries({"experience": lines})]
        self.assertEqual(["Treasury Analyst", "Investment Banking Summer Analyst", "Equity Research Intern"], titles)
        self.assertEqual(2028, _graduation("Bachelor of Commerce 09/2024 – 04/2028", "")[0])


class AlertDedupeTests(unittest.TestCase):
    def setUp(self):
        with patch.object(watcher, "DB_PATH", ":memory:"):
            self.con = watcher.db_open()

    def test_same_title_in_another_city_alerts_separately(self):
        toronto = {"company": "RBC", "title": "Analyst", "location": "Toronto, ON", "url": "https://x/1"}
        watcher.mark_alerted(self.con, toronto)
        echo = {**toronto, "location": "Toronto, Ontario, Canada", "url": "https://linkedin/1"}
        self.assertTrue(watcher.already_alerted(self.con, echo))
        self.assertFalse(watcher.already_alerted(self.con, {**toronto, "location": "Montreal, QC", "url": "https://x/2"}))

    def test_relisted_link_on_the_same_board_is_not_new(self):
        self.con.execute("INSERT INTO jobs(board, job_id, title, location, url, first_seen, last_seen) "
                         "VALUES ('list','old','Analyst Intern','Toronto, ON','https://a?x=1','t','t')")
        job = {"id": "new", "company": "", "title": "Analyst Intern", "location": "Toronto, ON"}
        self.assertTrue(watcher.known_on_board(self.con, "list", job))
        self.assertFalse(watcher.known_on_board(self.con, "list", job, {"old", "new"}))
        self.assertFalse(watcher.known_on_board(self.con, "list", {**job, "location": "Calgary, AB"}))


if __name__ == "__main__":
    unittest.main()
