"""French month names in a resume's dates read as English ones do: "Ingénieur junior Juin 2016 – Avril 2019" is a
job from 2016 to 2019 titled "Ingénieur junior", with the month in full or abbreviated, with or without its accent,
in any case, and "à" (or "a") between them. A "Stagiaire" is an intern, and the cover letter's checks read French
dates and "Présent" too. Invented person, school and employers."""
import unittest
from datetime import date

from intel import load_knowledge
from intel.cover_letter import mark_dates
from intel.resume import parse_resume
from intel.resume_facts import role_state
from intel.resume_insights import experience_entries, month_number, student_roles

KN = load_knowledge()
TODAY = date(2026, 10, 18)

QUEBEC_ENGINEER = """CAMILLE GAGNON, ing.
camille.gagnon@example.com | 555-010-0371 | Québec, QC
Formation
Université du Saint-Laurent Québec, QC
Baccalauréat en génie civil Sept. 2012 – Decembre 2015
Expérience professionnelle
Groupe Conseil Boréal Québec, QC
Ingénieur de projet principal FÉVRIER 2023 – Présent
• Gestion des projets d'infrastructures municipales et coordination des équipes de conception.
Ingénieur de projet, infrastructures municipales juil. 2019 – janv. 2023
• Conception des réseaux d'aqueduc et d'égout et des plans de voirie pour des municipalités de la Rive-Sud.
Laval Ingénierie Laval, QC
Ingénieur junior Juin 2016 – Avril 2019
• Modélisation hydraulique avec SWMM et dessin des plans dans AutoCAD Civil 3D.
Ville de Lévis Lévis, QC
Stagiaire en génie civil mai 2015 a aout 2015
• Relevés d'arpentage et inspection des travaux de pavage.
Compétences
Logiciels : AutoCAD Civil 3D, SWMM, HEC-RAS, MS Project
"""

# Each spelling of each month: full, abbreviated, unaccented, upper case.
SPELLINGS = {1: ("janvier", "janv.", "JANVIER"), 2: ("février", "févr.", "fevrier", "fevr.", "Fév"),
             3: ("mars", "MARS"), 4: ("avril", "avr.", "Avril"), 5: ("mai", "Mai"), 6: ("juin", "JUIN"),
             7: ("juillet", "juil.", "juill.", "Juil"), 8: ("août", "aout", "AOÛT"), 9: ("septembre", "sept."),
             10: ("octobre", "oct."), 11: ("novembre", "nov."), 12: ("décembre", "déc.", "decembre", "DÉC.")}


class FrenchDateTests(unittest.TestCase):
    def test_every_range_in_a_french_experience_block_dates_its_role(self):
        parsed = parse_resume(QUEBEC_ENGINEER, KN)
        this_year = date.today().year
        self.assertEqual([("Ingénieur de projet principal", this_year),
                          ("Ingénieur de projet, infrastructures municipales", 2023),
                          ("Ingénieur junior", 2019), ("Stagiaire en génie civil", 2015)],
                         [(e["title"], e["end"]) for e in parsed["entries"] if e["block"] == "experience"])
        # Ten years in 2026, from June 2016 on: the summer internship is no work year.
        self.assertEqual(this_year - 2016, parsed["career"]["work_years"])
        self.assertEqual(1, parsed["internships"])
        # The degree's range ends in December 2015.
        self.assertEqual((2015, 12), (parsed["education"]["graduation_year"], parsed["education"]["graduation_month"]))

    def test_each_spelling_of_each_month(self):
        for number, spellings in SPELLINGS.items():
            for spelling in spellings:
                with self.subTest(month=spelling):
                    self.assertEqual(number, month_number(spelling))
                    line = f"Ingénieur junior {spelling} 2016 – {spelling} 2019"
                    self.assertEqual([("Ingénieur junior", 2016, 2019)],
                                     [(e["title"], e["start"], e["end"])
                                      for e in experience_entries({"experience": [line]})])

    def test_english_months_read_as_before(self):
        for spelling, number in (("Jan", 1), ("February", 2), ("Mar.", 3), ("June", 6), ("Jul", 7), ("Sept.", 9),
                                 ("Dec", 12)):
            with self.subTest(month=spelling):
                self.assertEqual(number, month_number(spelling))

    def test_a_or_à_between_the_dates(self):
        this_year = date.today().year
        for line, dates in (("Ingénieur junior Juin 2016 à Avril 2019", (2016, 2019)),
                            ("Ingénieur junior juin 2016 a avril 2019", (2016, 2019)),
                            ("Ingénieur junior 2016 a 2019", (2016, 2019)),
                            ("Ingénieur junior mai 2019 a present", (2019, this_year))):
            with self.subTest(line=line):
                self.assertEqual([("Ingénieur junior", *dates)],
                                 [(e["title"], e["start"], e["end"]) for e in experience_entries({"experience": [line]})])
        # English's "a" is no date range.
        self.assertEqual([], experience_entries({"experience": ["Designed in 2019 a current sensor for the line"]}))

    def test_french_student_titles_are_internships(self):
        for title, student in (("Stagiaire en génie civil", True), ("Stage en ingénierie des structures", True),
                               ("Stage d'été, génie civil", True), ("Étudiante chercheuse", True),
                               ("Stage Manager", False), ("Ingénieur junior", False)):
            with self.subTest(title=title):
                entries = experience_entries({"experience": [f"{title} Mai 2015 – Août 2015"]})
                self.assertEqual(int(student), student_roles(entries))


class FrenchLetterDateTests(unittest.TestCase):
    """The cover letter's facts for today, and the resume text it marks, read French dates as English ones."""

    def test_french_roles_are_ended_or_ongoing(self):
        for dates, state in (("Juin 2016 – Avril 2019", "ended"), ("Juin 2016 à Avril 2019", "ended"),
                             ("juin 2016 a avril 2019", "ended"), ("janv. 2026 – août 2026", "ended"),
                             ("Mai 2019 – Présent", "ongoing"), ("Mai 2019 à aujourd'hui", "ongoing"),
                             ("Sept. 2026 – déc. 2026", "ongoing"), ("Juillet 2026 – Février 2027", "ongoing")):
            with self.subTest(dates=dates):
                self.assertEqual(state, role_state(dates, TODAY))

    def test_the_resume_marks_french_ranges(self):
        for text, marked in (("Ingénieur junior Juin 2016 – Avril 2019", "Juin 2016 – Avril 2019 (ended)"),
                             ("Ingénieur junior Juin 2016 à Avril 2019", "Juin 2016 à Avril 2019 (ended)"),
                             ("Ingénieur de projet Mai 2019 – Présent", "Mai 2019 – Présent (ongoing)"),
                             ("Analyste juil. 2026 – févr. 2027", "juil. 2026 – févr. 2027 (ongoing)"),
                             ("Analyst May 2026 - August 2026", "May 2026 - August 2026 (ended)")):
            with self.subTest(text=text):
                self.assertIn(marked, mark_dates(text, TODAY))
        sentence = "Since May 2019 a current sensor project."
        self.assertEqual(sentence, mark_dates(sentence, TODAY))


if __name__ == "__main__":
    unittest.main()
