"""Program windows in Calendar (plans/healthcare-board.md, D16): the Healthcare board's yearly program dates show
to profiles with that board, narrowed by their filters and licences, and so do Product's and Design's
(plans/product-design-board.md 5.6, D23). Finance and tech calendars are unchanged."""
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


class ProductDesignWindowTests(unittest.TestCase):
    """Product's and Design's windows (plans/product-design-board.md 5.6, D23)."""

    def test_each_board_sees_its_own_windows_and_the_co_op_terms(self):
        product = windows({"fields": ["product"], "target_roles": ["product"]})
        self.assertEqual(["apm_early", "pm_internships", "apm_fall", "apm_winter", "coop_winter", "coop_spring",
                          "coop_fall"], [k for _, k in product])
        design = windows({"fields": ["design"], "target_roles": ["design"]})
        self.assertEqual({"design_internships", "design_apprenticeships", "industrial_design_internships",
                          "studio_internships", "brand_design_internships", "coop_winter", "coop_spring", "coop_fall"},
                         {k for _, k in design})
        self.assertTrue(all("typically" in i["title"] for i in program_windows(
            merge_profile({"fields": ["product", "design"]}), KN, *SCHOOL_YEAR)))

    def test_filters_narrow_them_and_the_co_op_terms_stay(self):
        self.assertEqual([("2026-09-15", "industrial_design_internships"), ("2026-09-15", "coop_winter"),
                          ("2027-01-15", "coop_spring"), ("2027-05-15", "coop_fall")],
                         windows({"fields": ["design"], "target_roles": ["design.industrial_design"]}))
        self.assertEqual(["coop_winter", "coop_spring", "coop_fall"],
                         [k for _, k in windows({"fields": ["design"], "target_roles": ["design.game_design"]})])
        self.assertEqual(["pm_internships", "coop_winter", "coop_spring", "coop_fall"],
                         [k for _, k in windows({"fields": ["product"], "target_roles": ["product.product_ops"]})])

    def test_a_window_two_boards_list_shows_once(self):
        both = windows({"fields": ["product", "design"], "target_roles": ["product", "design"]})
        self.assertEqual(12, len(both))
        self.assertEqual(1, [k for _, k in both].count("coop_winter"))
        # Each year in the range still shows.
        self.assertEqual(2, [k for _, k in windows({"fields": ["product", "design"]}, "2026-09-01", "2027-09-30")]
                         .count("coop_winter"))


class CalendarProgramTests(ServiceFixture):
    def test_calendar_shows_windows_only_with_the_board(self):
        dec = {"start": ["2026-12-01"], "end": ["2026-12-31"]}
        self.assertFalse([i for i in self.service.calendar(dec)["items"] if i["kind"] == "program"])
        self.service.put_profile({"fields": ["finance", "healthcare"], "licences": ["pharmacist"]})
        items = [i for i in self.service.calendar(dec)["items"] if i["kind"] == "program"]
        self.assertEqual([(i["date"], i["key"]) for i in items], [("2026-12-12", "aifa")])
        # The saved licence narrows them: October's nurse externships are for RNs.
        octo = {"start": ["2026-10-01"], "end": ["2026-10-31"]}
        self.assertEqual([i["key"] for i in self.service.calendar(octo)["items"] if i["kind"] == "program"],
                         ["industry_fellowships"])

    def test_a_product_and_design_profile_sees_each_co_op_term_once(self):
        self.service.put_profile({"fields": ["product", "design"]})
        sep = {"start": ["2026-09-01"], "end": ["2026-09-30"]}
        items = [i["key"] for i in self.service.calendar(sep)["items"] if i["kind"] == "program"]
        self.assertEqual(["apm_fall", "coop_winter", "design_apprenticeships", "industrial_design_internships"],
                         sorted(items))


if __name__ == "__main__":
    unittest.main()
