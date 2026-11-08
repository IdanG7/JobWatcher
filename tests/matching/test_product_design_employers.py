"""The short list of shared employers Product and Design type (plans/product-design-board.md 6.5 to 6.7, D27): each
entry renames and types its employer's postings and changes nothing else, on every board."""
import unittest

from intel import load_knowledge
from intel.companies import resolve_company
from intel.facts import build_facts
from intel.taxonomy import classify

KN = load_knowledge()
SHORT_LIST = {"figma": ("Figma", "enterprise_saas"), "adobe": ("Adobe", "big_tech"),
              "webflow": ("Webflow", "enterprise_saas"), "notion": ("Notion", "enterprise_saas"),
              "duolingo": ("Duolingo", "consumer_tech"), "asana": ("Asana", "enterprise_saas"),
              "airbnb": ("Airbnb", "consumer_tech"), "spotify": ("Spotify", "consumer_tech")}


class ShortListTests(unittest.TestCase):
    def test_each_employer_is_named_and_typed_by_its_exact_name_only(self):
        # An '=' alias, the employer's own name and a type without priors, so only labels change.
        for key, (name, ctype) in SHORT_LIST.items():
            with self.subTest(employer=key):
                for written in (name, name.upper(), f"{name}, Inc."):
                    resolved = resolve_company(written, KN)
                    self.assertEqual((key, name, ctype, True), (resolved["key"], resolved["name"], resolved["type"],
                                                                resolved["known"]), written)
                # Tech types hire worldwide: the HQ shows in the Companies view and never stands in for a location.
                self.assertEqual("", resolve_company(name, KN)["country"])
                self.assertTrue(KN.companies[key].country and KN.companies[key].hq)
                self.assertNotIn(ctype, KN.company_priors)
        # Through the source name, as the employers' own feeds resolve.
        self.assertEqual("figma", resolve_company("", KN, "figma", {"ats": "greenhouse", "token": "figma"})["key"])

    def test_longer_names_and_sibling_feeds_keep_the_key_they_had(self):
        # A name-only entry would have taken these (6.5): each stays unclassified, under its own key.
        for written, key in (("Asana Partners", "asana_partners"), ("Adobe University", "adobe_university"),
                             ("Spotify for Artists", "spotify_for_artists"), ("Notion Capital", "notion_capital")):
            resolved = resolve_company(written, KN)
            self.assertEqual((key, "unknown"), (resolved["key"], resolved["type"]), written)
        workday = {"ats": "workday", "host": "adobe.wd5.myworkdayjobs.com", "tenant": "adobe"}
        self.assertEqual("adobe_university", resolve_company("", KN, "adobe_university", workday)["key"])

    def test_a_short_list_posting_keeps_its_board_and_filter(self):
        for title, company, board, sub in (("Product Designer, Editor", "Figma", "design", "product_design"),
                                           ("Senior Product Manager, Growth", "Duolingo", "product", "product_management"),
                                           ("Software Engineer, Backend", "Airbnb", "software", "backend"),
                                           ("Financial Analyst, FP&A", "Spotify", "finance", None)):
            with self.subTest(title=title):
                facts = build_facts({"title": title, "company": company}, KN)
                self.assertEqual(SHORT_LIST[company.lower()][1], facts["company"]["type"])
                # As the posting read while the employer was unclassified.
                before = classify(title, KN, company_type="unknown")
                for c in (facts["classification"], before):
                    self.assertEqual(board, "finance" if c["is_finance"] else c["family"])
                    if sub:
                        self.assertEqual(sub, c["subcategory"])
                self.assertEqual((before["category"], before["subcategory"]),
                                 (facts["classification"]["category"], facts["classification"]["subcategory"]))


if __name__ == "__main__":
    unittest.main()
