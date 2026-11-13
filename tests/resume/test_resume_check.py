"""The resume check: weaknesses a rule can see, each quoting the line. The resumes here are invented."""
import unittest

from intel import resume_check

STUDENT = """Jordan Lee
jordan.lee@example.com | 416-555-0134 | Toronto, ON
Education
University of Toronto - Bachelor of Commerce, Expected April 2028
Technical Skills
Excel, Python, SQL
Experience
Treasury Analyst Intern | Example Company | May 2026 - August 2026
• Built 13-week cash flow forecasts covering $40M of facilities for the CFO.
• Responsible for the weekly liquidity report sent to the treasurer and the
controller, and its checks.
• Helped with month-end close.
Operations Intern | Sample Logistics | 01/2025 - 04/2025
• Developed a routing sheet in Excel.
• Developed pick lists for the night shift.
• Developed a dashboard used by 6 supervisors.
"""

CLEAN = """Jordan Lee
jordan.lee@example.com | 416-555-0134
Education
University of Toronto - Bachelor of Commerce, Expected April 2028
Skills
Excel, Python
Experience
Treasury Analyst Intern | Example Company | May 2026 - August 2026
• Built 13-week cash flow forecasts covering $40M of facilities.
• Cut the weekly liquidity report from 3 hours to 40 minutes.
"""


def keys(findings):
    return [f["key"] for f in findings]


class ResumeCheckTests(unittest.TestCase):
    def test_bullets_are_read_whole_with_their_wrapped_lines(self):
        bullets = resume_check.bullets(STUDENT)
        self.assertEqual(6, len(bullets))
        self.assertEqual("Responsible for the weekly liquidity report sent to the treasurer and the controller, "
                         "and its checks.", bullets[1])

    def test_a_job_title_or_label_after_a_bullet_without_a_full_stop_is_not_glued_on(self):
        text = ("Experience\n• Built 3 dashboards for the night shift supervisors and their two regional managers\n"
                "• Ran 2 audits\nSample Logistics (Remote)\nLanguages: English, French\n"
                "• Wrote the onboarding guide used by 40 new hires across the Toronto and Montreal\nOperations teams\n")
        self.assertEqual(["Built 3 dashboards for the night shift supervisors and their two regional managers",
                          "Ran 2 audits",
                          "Wrote the onboarding guide used by 40 new hires across the Toronto and Montreal Operations teams"],
                         resume_check.bullets(text))
        self.assertNotIn("date_styles", keys(resume_check.check(CLEAN + "Analyst | Example Company | 2019-21\n")))

    def test_a_clean_resume_has_nothing_to_fix(self):
        self.assertEqual([], resume_check.check(CLEAN))

    def test_each_weakness_quotes_its_lines(self):
        found = {f["key"]: f for f in resume_check.check(STUDENT)}
        self.assertEqual(["Responsible for the weekly liquidity report sent to the treasurer and the controller, "
                          "and its checks.", "Helped with month-end close."], found["weak_openers"]["lines"])
        self.assertIn("4 of 6", found["no_numbers"]["title"])
        self.assertNotIn("Built 13-week cash flow forecasts covering $40M of facilities for the CFO.",
                         found["no_numbers"]["lines"])
        self.assertIn("Developed", found["repeated_openers"]["title"])
        self.assertEqual(3, len(found["repeated_openers"]["lines"]))
        # the first date seen in each form
        self.assertEqual({"April 2028", "01/2025 - 04/2025"}, set(found["date_styles"]["lines"]))
        for finding in found.values():
            self.assertTrue(finding["title"] and finding["detail"])

    def test_most_bullets_with_numbers_is_not_flagged(self):
        text = CLEAN + "• Wrote the team's onboarding guide.\n"
        self.assertNotIn("no_numbers", keys(resume_check.check(text)))

    def test_missing_contact_details_and_sections_are_named(self):
        bare = "Jordan Lee\nExperience\nAnalyst | Example Company | May 2026 - August 2026\n• Built 3 models.\n• Ran 2 audits.\n"
        found = {f["key"]: f for f in resume_check.check(bare)}
        self.assertIn("email", found["missing_contact"]["title"])
        self.assertIn("phone", found["missing_contact"]["title"])
        self.assertIn("Education", found["missing_sections"]["title"])
        self.assertIn("Skills", found["missing_sections"]["title"])

    def test_length_goes_by_career_stage(self):
        self.assertIn("length", keys(resume_check.check(CLEAN, pages=2)))                       # a student: one page
        self.assertNotIn("length", keys(resume_check.check(CLEAN, experienced=True, pages=2)))
        self.assertIn("length", keys(resume_check.check(CLEAN, experienced=True, pages=3)))
        long = CLEAN + "• Reviewed 12 filings and wrote notes on each one for the team lead.\n" * 80
        self.assertIn("length", keys(resume_check.check(long)))                                  # no file: by words
        self.assertNotIn("length", keys(resume_check.check(long, experienced=True)))

    def test_a_long_bullet_is_flagged(self):
        text = CLEAN + "• " + "Reconciled 14 accounts " * 13 + "each month.\n"
        self.assertIn("long_bullets", keys(resume_check.check(text)))

    def test_without_bullet_marks_sentences_under_a_job_are_read_as_bullets(self):
        text = CLEAN.replace("• ", "")
        self.assertEqual(2, len(resume_check.bullets(text)))


if __name__ == "__main__":
    unittest.main()
