"""The facts setup shows a new person on its first screen ("What Foothold read"): the school without its city's
comma, the GPA as a number, and the languages a resume lists under a heading or with a level beside them.
The people, schools and employers are invented."""
import unittest

from intel import load_knowledge
from intel.resume import parse_resume

KN = load_knowledge()

WORK = """
EXPERIENCE
Northwind Software, Vancouver, BC
Backend Software Engineering Intern, May 2026 - Aug 2026
- Built REST APIs in Python and Go serving 2M requests a day

SKILLS
Python, Go, Java, SQL
"""


def read(education, languages=""):
    return parse_resume(f"Jordan Example\nVancouver, BC\n\nEDUCATION\n{education}\n{WORK}\n{languages}", KN)


class CardFactsTests(unittest.TestCase):
    def test_a_school_written_with_its_city_is_read_without_the_comma(self):
        for line, school in (("Eastlake University, Vancouver, BC", "Eastlake University"),
                             ("Eastlake University, Toronto, ON", "Eastlake University"),
                             ("Eastlake University", "Eastlake University"),
                             ("Eastlake University - Waterloo, ON", "Eastlake University")):
            with self.subTest(line):
                edu = read(f"{line}\nBachelor of Science in Computer Science, Expected May 2028")["education"]
                self.assertEqual(school, edu["school"])

    def test_an_employer_written_with_its_city_has_no_comma_left_either(self):
        parsed = read("Eastlake University\nBachelor of Science in Computer Science, Expected May 2028")
        self.assertEqual(["Northwind Software"], [e["company"] for e in parsed["entries"]])

    def test_the_gpa_is_shown_as_its_number_and_scale(self):
        degree = "Eastlake University\nBachelor of Science in Computer Science, Expected May 2028\n"
        for line, value, shown in (("GPA: 3.7/4.0", 3.7, "3.7/4.0"), ("Cumulative GPA 3.52 / 4.00", 3.52, "3.52/4.00"),
                                   ("GPA: 3.9", 3.9, "3.9"), ("cGPA - 10.2/12", 3.4, "10.2/12")):
            with self.subTest(line):
                edu = read(degree + line)["education"]
                self.assertEqual((value, shown), (edu["gpa"], edu["gpa_text"]))

    def test_a_percentage_average_is_shown_but_not_turned_into_a_gpa(self):
        degree = "Eastlake University\nBachelor of Applied Science, Honours Civil Engineering"
        for line in (" | GPA 88%", "\nCumulative average: 88%", "\nGPA: 88 %"):
            with self.subTest(line):
                edu = read(degree + line)["education"]
                self.assertEqual((None, "88%"), (edu["gpa"], edu["gpa_text"]))
        # A percentage that is not a grade ("increased sales by 40%") is left alone.
        self.assertIsNone(read(degree + "\nRaised club membership by 40%")["education"]["gpa_text"])

    def test_languages_under_their_own_heading_are_read(self):
        degree = "Eastlake University\nBachelor of Science in Computer Science, Expected May 2028"
        for block, languages in (
                ("LANGUAGES\nEnglish, French", ["English", "French"]),
                ("Languages\n- English (native)\n- French (fluent)\n- Spanish (conversational)", ["English", "French", "Spanish"]),
                ("LANGUAGES\nEnglish and Mandarin", ["English", "Mandarin"]),
                ("Languages: English, Mandarin", ["English", "Mandarin"])):
            with self.subTest(block):
                self.assertEqual(languages, read(degree, block)["languages"])

    def test_a_level_beside_a_language_counts_wherever_it_is_written(self):
        degree = "Eastlake University\nBachelor of Science in Computer Science, Expected May 2028"
        self.assertEqual(["French", "Hindi"], read(degree, "ADDITIONAL\nHindi (native), French - conversational")["languages"])
        self.assertEqual(["Spanish"], read(degree, "ADDITIONAL\nFluent in Spanish")["languages"])

    def test_programming_languages_and_passing_mentions_are_not_spoken_languages(self):
        degree = "Eastlake University\nBachelor of Science in Computer Science, Expected May 2028"
        self.assertEqual([], read(degree, "LANGUAGES\nPython, Java, Go")["languages"])
        self.assertEqual([], read(degree, "ACTIVITIES\nEnglish tutor, proficient in Excel\nFrench club treasurer")["languages"])


if __name__ == "__main__":
    unittest.main()
