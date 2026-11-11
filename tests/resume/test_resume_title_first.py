"""A first-year student's resume in the common "title and dates, then the organisation" layout, as a PDF gives its
text: the right-aligned dates and city run into the words before them. The degree is the only evidence of the
field; the one hardware-sounding line is a school project. The person, school and clubs are invented."""
import unittest

from intel import load_knowledge, merge_profile
from intel.resume import clean_pdf_text, parse_resume, profile_from_resume

KN = load_knowledge()

STUDENT = """MORGAN ELLERY
morgan.ellery@example.com | 555-010-0477
Education
Lakehead Polytechnic UniversityThunder Bay, ON
Candidate for Bachelor of Engineering - Civil Engineering September 2026 – April 2031
• Entrance Scholarship of Distinction
Skills
Programming:Python, Java
Technical Skills:Drawing skills, AutoCAD, Revit, Excel
Experience
Vice PresidentApril 2025 – June 2026
Engineering Club - Northfield High School Barrie, ON
• Won first place in bridge-building and tower assembly competitions.
• Designed and built structures to meet the criteria of each competition.
Team LeaderOctober 2024 – June 2025
Math Team - Northfield High School Barrie, ON
• Tutored younger members of the team in mathematics.
Projects
Mechanical ArmMarch 2025 - April 2025
• Designed a working mechanical arm in AutoCAD and built it from wood, cardboard and hydraulics.
Cottage Floor PlanMay 2025 - June 2025
• Drew a floor plan for a cottage to the Ontario Building Code after consulting an architect.
Achievements & Awards
1st Place- Regional Math Contest. March 2024
Computer Science- Highest Mark in Computer Science. September 2024 - June 2025
Hobbies & Interests
Interests:Rock Climbing, Puzzles
"""


class TitleFirstTests(unittest.TestCase):
    def setUp(self):
        self.parsed = parse_resume(STUDENT, KN)

    def test_each_role_is_one_entry_with_its_title_organisation_and_bullets(self):
        entries = [(e["block"], e["title"], e["company"]) for e in self.parsed["entries"]]
        self.assertEqual([("experience", "Vice President", "Engineering Club - Northfield High School"),
                          ("experience", "Team Leader", "Math Team - Northfield High School"),
                          ("projects", "Mechanical Arm", ""),
                          ("projects", "Cottage Floor Plan", "")], entries)

    def test_the_school_is_named_without_its_city(self):
        self.assertEqual("Lakehead Polytechnic University", self.parsed["education"]["school"])
        self.assertEqual("Civil Engineering", self.parsed["education"]["program"])
        self.assertEqual((2031, 4), (self.parsed["education"]["graduation_year"],
                                     self.parsed["education"]["graduation_month"]))

    def test_the_degree_decides_the_board_and_a_school_project_does_not(self):
        self.assertEqual(["aec"], self.parsed["role_categories"])
        self.assertIn("degree: civil engineering", self.parsed["role_interests"][0]["evidence"])
        profile = profile_from_resume(self.parsed, merge_profile({}), KN)
        self.assertEqual((["aec"], ["aec"]), (profile["fields"], profile["target_roles"]))
        # the languages it lists are still read
        self.assertLessEqual({"python", "java", "autocad", "revit"}, set(profile["skills"]))

    def test_a_job_in_another_field_still_counts_beside_the_degree(self):
        worked = STUDENT.replace("Vice PresidentApril 2025", "Embedded Firmware InternApril 2025")
        self.assertEqual({"aec", "hardware.embedded_firmware"}, set(parse_resume(worked, KN)["role_categories"]))

    def test_a_kerning_split_is_rejoined_once_the_glued_city_is_apart(self):
        self.assertIn("University of Northgate Northgate, ON",
                      clean_pdf_text("University of N orthgateNorthgate, ON\nBachelor of Science"))
        # a name written with an inner capital is left alone
        self.assertIn("McAllen, TX", clean_pdf_text("Rio Clinic McAllen, TX"))


if __name__ == "__main__":
    unittest.main()
