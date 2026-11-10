"""French month names in a resume's dates read as English ones do: "Ingénieur junior Juin 2016 – Avril 2019" is a
job from 2016 to 2019 titled "Ingénieur junior", with the month in full or abbreviated, with or without its accent,
in any case. Invented person, school and employers."""
import unittest
from datetime import date

from intel import load_knowledge
from intel.resume import parse_resume
from intel.resume_insights import experience_entries, month_number

KN = load_knowledge()

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
                          ("Ingénieur junior", 2019)],
                         [(e["title"], e["end"]) for e in parsed["entries"] if e["block"] == "experience"])
        # Ten years in 2026, from June 2016 on.
        self.assertEqual(this_year - 2016, parsed["career"]["work_years"])
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


if __name__ == "__main__":
    unittest.main()
