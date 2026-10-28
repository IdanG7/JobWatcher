"""Program windows in Calendar (plans/healthcare-board.md, D16): the Healthcare board's yearly program dates show
to profiles with that board, narrowed by their filters and licences. Finance and tech calendars are unchanged."""
import unittest

from intel import load_knowledge, merge_profile
from intel.programs import program_windows
from tests.app.test_dashboard import ServiceFixture

KN = load_knowledge()
SCHOOL_YEAR = ("2026-09-01", "2027-08-31")


def windows(profile, start=SCHOOL_YEAR[0], end=SCHOOL_YEAR[1]):
    return [(i["date"], i["key"]) for i in program_windows(merge_profile(profile), KN, start, end)]


class ProgramWindowTests(unittest.TestCase):
    def test_finance_and_tech_profiles_see_none(self):
        self.assertEqual(windows({}), [])
        self.assertEqual(windows({"fields": ["software"], "target_roles": ["software"]}), [])

    def test_filters_and_licences_narrow_the_windows(self):
        nurse = {"fields": ["healthcare"], "target_roles": ["healthcare.clinical_care"], "licences": ["rn", "bls"],
                 "graduation_year": 2027, "graduation_month": 4}
        self.assertEqual(windows(nurse), [("2026-10-01", "nurse_externships"), ("2027-04-01", "ngg")])
        pharmacy = {"fields": ["healthcare"], "target_roles": ["healthcare.medical_affairs"], "licences": ["pharmacist"]}
        self.assertEqual(sorted(windows(pharmacy)), [("2026-10-01", "industry_fellowships"), ("2026-12-12", "aifa"),
                                                     ("2027-01-01", "phorcas"), ("2027-03-15", "ashp_match_phase1")])
        self.assertEqual(windows({"fields": ["healthcare"], "target_roles": ["healthcare.lab_research"]}),
                         [("2027-05-01", "summer_research")])

    def test_the_whole_board_sees_every_window(self):
        self.assertEqual(len(windows({"fields": ["healthcare"], "target_roles": ["healthcare"]})), 7)

    def test_windows_repeat_each_year_inside_the_range(self):
        board = {"fields": ["healthcare"], "target_roles": ["healthcare"], "licences": ["pharmacist"]}
        self.assertEqual([k for _, k in windows(board, "2026-12-01", "2027-12-31") if k == "aifa"], ["aifa", "aifa"])
        self.assertEqual(windows(board, "2026-12-13", "2026-12-31"), [])

    def test_items_say_the_dates_are_typical(self):
        item = program_windows(merge_profile({"fields": ["healthcare"], "target_roles": ["healthcare"]}), KN,
                               "2027-01-01", "2027-01-31")[0]
        self.assertEqual((item["kind"], item["key"], item["when"]), ("program", "phorcas", "Early January"))
        self.assertIn("typically", item["title"])


class CalendarProgramTests(ServiceFixture):
    def test_calendar_shows_windows_only_with_the_board(self):
        dec = {"start": ["2026-12-01"], "end": ["2026-12-31"]}
        self.assertFalse([i for i in self.service.calendar(dec)["items"] if i["kind"] == "program"])
        self.service.put_profile({"fields": ["finance", "healthcare"], "licences": ["pharmacist"]})
        items = [i for i in self.service.calendar(dec)["items"] if i["kind"] == "program"]
        self.assertEqual([(i["date"], i["key"]) for i in items], [("2026-12-12", "aifa")])


if __name__ == "__main__":
    unittest.main()
