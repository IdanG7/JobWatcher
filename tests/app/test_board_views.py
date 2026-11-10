"""Today's New today, Analytics and Companies count the profile's boards (plans/product-design-board.md 10.1,
decision D43): A for New today and Analytics, A' for Companies. A Finance-only profile, or one with no boards,
sees exactly what it saw before."""
import json
import tempfile
import time
import unittest
from pathlib import Path

import watcher
from dashboard import JobwatchService
from intel_store import save_profile, update_lifecycle

HOUR = 3600
POSTINGS = [  # board, id, title, company, posted (hours ago)
    ("rbc", "ib1", "2027 Investment Banking Summer Analyst", "RBC", 1),          # Finance, a typed employer
    ("rbc", "apm1", "Associate Product Manager", "RBC", 1),                     # Product at the same bank
    ("northwind", "pm1", "Product Manager, Growth", "Northwind Labs", 1),        # Product, an untyped employer
    ("northwind", "pd1", "Senior Product Designer", "Northwind Labs", 1),        # Design
    ("northwind", "be1", "Backend Software Engineer", "Northwind Labs", 1),      # Software
    ("figma", "ux1", "UX Researcher", "Figma", 72),                             # Design, typed, three days ago
]


class BoardViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        db_path, config_path, subscribers_path = root / "test.db", root / "config.json", root / "subscribers.json"
        config_path.write_text(json.dumps({"profile": {}, "boards": {
            "rbc": {"ats": "greenhouse", "token": "rbc"}, "northwind": {"ats": "greenhouse", "token": "northwind"},
            "figma": {"ats": "greenhouse", "token": "figma"}}}))
        subscribers_path.write_text("{}")
        con = watcher.db_open(db_path)
        now = watcher.now()
        for board, job_id, title, company, hours in POSTINGS:
            con.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?)",
                        (board, job_id, title, "Toronto, ON", f"https://example.com/{job_id}", now, now))
            con.execute("INSERT INTO job_details VALUES (?,?,?,?,?)", (board, job_id, company, "", time.time() - hours * HOUR))
        for board in ("rbc", "northwind", "figma"):
            ids = {p[1] for p in POSTINGS if p[0] == board}
            update_lifecycle(con, board, ids, False, now, ids, discovered=True)
        con.commit()
        con.close()
        self.service = JobwatchService(db_path, config_path, subscribers_path)
        self.service.refresh_now()

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def use(self, profile):
        with self.service.db() as con:
            save_profile(con, profile)

    def views(self):
        overview, analytics = self.service.overview(), self.service.analytics({"window": ["30"]})
        companies = {c["company_key"]: c["active"] for c in self.service.companies({})["companies"]}
        return {"boards": overview["boards"], "new_today": overview["stats"]["new_today"],
                "flow": analytics["flow"][7], "by_category": sorted(c["key"] for c in analytics["by_category"]),
                "employers": sorted(c["key"] for c in analytics["companies"]),
                "heat": sum(map(sum, analytics["heatmap"])),
                "yours": {s["board"]: s["yours"] for s in analytics["sources"]}, "companies": companies}

    def test_a_finance_only_profile_sees_finance_as_before(self):
        # Before D43 every profile saw these: Finance's postings, and Companies' finance roles plus every role at
        # a typed employer (RBC's APM, Figma's researcher).
        finance = {"boards": ["Finance"], "new_today": 1, "flow": 1, "by_category": ["investment_banking"],
                   "employers": ["rbc"], "heat": 1, "yours": {"rbc": 1, "northwind": 0, "figma": 0},
                   "companies": {"rbc": 2, "figma": 1}}
        self.assertEqual(finance, self.views())                     # no profile saved: the default
        self.use({"fields": ["finance"]})
        self.assertEqual(finance, self.views())

    def test_a_product_only_profile_counts_product(self):
        self.use({"fields": ["product"], "target_roles": ["product"]})
        self.assertEqual({"boards": ["Product"], "new_today": 2, "flow": 2,
                          "by_category": ["product.apm_programs", "product.product_management"],
                          "employers": ["northwind_labs", "rbc"], "heat": 2,
                          "yours": {"rbc": 1, "northwind": 1, "figma": 0},
                          "companies": {"rbc": 1, "northwind_labs": 1}}, self.views())

    def test_a_design_only_profile_counts_design(self):
        self.use({"fields": ["design"], "target_roles": ["design"]})
        self.assertEqual({"boards": ["Design"], "new_today": 1, "flow": 2,
                          "by_category": ["design.product_design", "design.ux_research"],
                          "employers": ["figma", "northwind_labs"], "heat": 2,
                          "yours": {"rbc": 0, "northwind": 1, "figma": 1},
                          "companies": {"northwind_labs": 1, "figma": 1}}, self.views())

    def test_a_profile_with_finance_keeps_companies_typed_employers(self):
        # Two boards, one of them bound as an argument: every count holds Finance's and Design's postings.
        self.use({"fields": ["finance", "design"]})
        self.assertEqual({"boards": ["Finance", "Design"], "new_today": 2, "flow": 3,
                          "by_category": ["design.product_design", "design.ux_research", "investment_banking"],
                          "employers": ["figma", "northwind_labs", "rbc"], "heat": 3,
                          "yours": {"rbc": 1, "northwind": 1, "figma": 1},
                          "companies": {"rbc": 2, "northwind_labs": 1, "figma": 1}}, self.views())

    def test_filters_and_areas_carry_their_labels(self):
        self.use({"fields": ["finance", "product"]})
        labels = {c["key"]: c["label"] for c in self.service.analytics({"window": ["30"]})["by_category"]}
        kn = self.service.kn
        self.assertEqual({"investment_banking": kn.category_label("investment_banking"),
                          "product.apm_programs": kn.subcategory_label("product", "apm_programs"),
                          "product.product_management": kn.subcategory_label("product", "product_management")}, labels)
        self.assertNotIn("", labels.values())


if __name__ == "__main__":
    unittest.main()
