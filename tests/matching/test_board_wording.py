"""The fit breakdown's wording names the profile's boards, not finance, outside Finance (plans/product-design-board.md
decision D44). The wording never changes the points, and a Finance-only profile reads every line as before."""
import time
import unittest

from intel import load_knowledge, merge_profile, score_job
from intel.facts import build_facts

KN = load_knowledge()
NOW = time.time()
STUDENT = ["internship", "new_grad"]


def row(key, title, fields, ctype=None, description="Join our team in Toronto."):
    """One row of the fit breakdown, as (points, detail), for a first run's profile on these boards."""
    facts = build_facts({"title": title, "company": "Acme", "location": "Toronto, ON", "description": description}, KN)
    if ctype:
        facts["company"] = {**facts["company"], "type": ctype, "type_label": KN.type_label(ctype), "known": True}
    profile = merge_profile({"fields": list(fields), "target_stages": STUDENT} if fields else {"target_stages": STUDENT})
    subs = {s["key"]: s for s in score_job(facts, profile, KN, {}, NOW)["subscores"]}
    return subs[key]["points"], subs[key]["detail"]


class EntryLevelTests(unittest.TestCase):
    def test_a_finance_posting_keeps_finance_entry_level(self):
        for fields in (["finance"], ["product"], ["design"], []):
            with self.subTest(fields=fields):
                self.assertEqual((6, "Analyst — entry level in finance"), row("stage", "Financial Analyst", fields))
                self.assertEqual((6, "Analyst — entry level in finance"),
                                 row("stage", "Investment Banking Analyst", fields))

    def test_other_boards_postings_name_no_board(self):
        for title, label in (("Product Analyst", "Analyst"), ("UX Analyst", "Analyst"), ("Data Analyst", "Analyst"),
                             ("Associate Product Designer", "Associate")):
            for fields in (["finance"], ["product"], ["design"]):
                with self.subTest(title=title, fields=fields):
                    self.assertEqual((6, f"{label} — entry level"), row("stage", title, fields))


class SkillsTests(unittest.TestCase):
    def test_a_finance_only_profile_still_reads_no_finance_skills(self):
        # No boards picked reads as Finance (profile_fields), as before boards.
        for fields in (["finance"], []):
            with self.subTest(fields=fields):
                self.assertEqual((5, "No finance skills detected"), row("skills", "Product Designer", fields))
                self.assertEqual((5, "No finance skills detected"), row("skills", "Financial Analyst", fields))

    def test_other_profiles_read_no_skills(self):
        for fields in (["product"], ["design"], ["software"], ["finance", "design"]):
            with self.subTest(fields=fields):
                self.assertEqual((5, "No skills detected"), row("skills", "Product Designer", fields))

    def test_a_posting_without_text_says_so_for_every_profile(self):
        for fields in (["finance"], ["design"]):
            self.assertEqual((6, "No description available yet"), row("skills", "Product Designer", fields, description=""))


class CompanyTests(unittest.TestCase):
    def test_outside_names_finance_only_for_a_finance_only_profile(self):
        self.assertEqual((3, "Semiconductors — outside finance"), row("company", "Product Designer", ["finance"],
                                                                      "semiconductors"))
        self.assertEqual((3, "Semiconductors — outside finance"), row("company", "Product Designer", [],
                                                                      "semiconductors"))
        for fields in (["product"], ["design"], ["healthcare"], ["finance", "design"]):
            with self.subTest(fields=fields):
                self.assertEqual((3, "Semiconductors — outside your boards"),
                                 row("company", "Product Designer", fields, "semiconductors"))


if __name__ == "__main__":
    unittest.main()
