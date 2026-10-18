"""Finance intelligence: taxonomy, seniority, cycles, eligibility, skills, pay, scoring."""

import time
import unittest
from datetime import datetime, timezone

from intel import analyze, load_knowledge, merge_profile, validate_profile
from intel.companies import resolve_company
from intel.compensation import comp_from_description, parse_compensation
from intel.cycle import detect_cycle, extract_deadline, graduation_window, is_rolling, window_status
from intel.eligibility import extract_eligibility
from intel.locations import parse_location
from intel.seniority import detect_seniority
from intel.skills import extract_skills
from intel.taxonomy import classify

KN = load_knowledge()
NOW = time.time()


def cls(title, description="", company_type="unknown", department=""):
    return classify(title, KN, description, department, company_type)


class TaxonomyTests(unittest.TestCase):
    def assertCategory(self, result, category, sub=None):
        self.assertEqual(category, result["category"], result)
        if sub is not None:
            self.assertEqual(sub, result["subcategory"], result)
        self.assertTrue(result["is_finance"])

    def test_investment_banking_and_groups(self):
        self.assertCategory(cls("Investment Banking Analyst"), "investment_banking")
        self.assertCategory(cls("Analyst, Mergers & Acquisitions"), "investment_banking", "ma")
        self.assertCategory(cls("M&A Summer Analyst"), "investment_banking", "ma")
        self.assertCategory(cls("Equity Capital Markets Analyst"), "investment_banking", "ecm")
        self.assertCategory(cls("Leveraged Finance Associate"), "investment_banking", "leveraged_finance")
        self.assertCategory(cls("Restructuring Analyst"), "investment_banking", "restructuring")
        self.assertCategory(cls("Healthcare Investment Banking Analyst"), "investment_banking", "coverage")

    def test_description_selects_group_when_title_is_generic(self):
        result = cls("2027 Investment Banking Summer Analyst",
                     "You will join our M&A team executing sell-side processes.")
        self.assertCategory(result, "investment_banking", "ma")

    def test_private_markets(self):
        self.assertCategory(cls("Private Equity Analyst"), "private_markets", "private_equity")
        self.assertCategory(cls("Growth Equity Associate"), "private_markets", "growth_equity")
        self.assertCategory(cls("Venture Capital Fellow"), "private_markets", "venture_capital")
        self.assertCategory(cls("Direct Lending Analyst"), "private_markets", "private_credit")
        self.assertCategory(cls("Real Estate Acquisitions Analyst"), "private_markets", "real_estate")

    def test_employer_type_breaks_generic_investment_titles(self):
        self.assertCategory(cls("Investment Analyst", company_type="private_equity"),
                            "private_markets", "private_equity")
        self.assertCategory(cls("Investment Analyst", company_type="asset_manager"),
                            "public_markets", "asset_management")

    def test_public_markets(self):
        self.assertCategory(cls("Equity Research Associate"), "public_markets", "equity_research")
        self.assertCategory(cls("Asset Management Analyst"), "public_markets", "asset_management")
        self.assertCategory(cls("Portfolio Manager Assistant"), "public_markets", "portfolio_management")
        self.assertCategory(cls("Long/Short Equity Analyst"), "public_markets", "hedge_fund")

    def test_sales_and_trading(self):
        self.assertCategory(cls("Sales & Trading Summer Analyst"), "markets", "sales_trading")
        self.assertCategory(cls("Fixed Income Trading Analyst"), "markets", "fixed_income")
        self.assertCategory(cls("FX Options Trader"), "markets")
        self.assertCategory(cls("Commodities Trading Intern"), "markets", "commodities")

    def test_quant(self):
        self.assertCategory(cls("Quantitative Researcher"), "quant", "quant_research")
        self.assertCategory(cls("Quantitative Trader Intern"), "quant", "quant_trading")
        self.assertFalse(cls("Quantitative Developer")["is_finance"])
        self.assertCategory(cls("Trader", company_type="quant_firm"), "quant", "quant_trading")

    def test_engineering_at_trading_firm_stays_technical(self):
        result = cls("Software Engineer", company_type="quant_firm")
        self.assertFalse(result["is_finance"])
        self.assertEqual("software", result["category"])
        self.assertFalse(cls("Trading Systems Engineer", company_type="quant_firm")["is_finance"])

    def test_software_elsewhere_stays_software(self):
        for title, ctype in (("Software Engineer, Payments", "fintech"),
                             ("Senior Software Engineer", "bulge_bracket"),
                             ("Machine Learning Engineer", "unknown")):
            result = cls(title, company_type=ctype)
            self.assertFalse(result["is_finance"], (title, result))

    def test_banking_corporate_finance_and_risk(self):
        self.assertCategory(cls("Corporate Banking Analyst"), "banking", "corporate_banking")
        self.assertCategory(cls("Commercial Banking Associate"), "banking", "commercial_banking")
        self.assertCategory(cls("Credit Analyst"), "banking", "credit")
        self.assertCategory(cls("FP&A Analyst"), "corporate_finance", "fpa")
        self.assertCategory(cls("Financial Planning & Analysis Intern"), "corporate_finance", "fpa")
        self.assertCategory(cls("Treasury Analyst"), "corporate_finance", "treasury")
        self.assertCategory(cls("Corporate Development Associate"), "corporate_finance", "corporate_development")
        self.assertCategory(cls("Market Risk Analyst"), "risk", "market_risk")
        self.assertCategory(cls("Credit Risk Co-op"), "risk", "credit_risk")
        self.assertCategory(cls("Model Validation Analyst"), "risk", "model_risk")
        self.assertCategory(cls("Actuarial Analyst"), "insurance", "actuarial")
        self.assertCategory(cls("Wealth Management Associate"), "wealth", "wealth_management")

    def test_untitled_summer_analyst_at_bank_is_low_confidence_finance(self):
        result = cls("Summer Analyst", company_type="bulge_bracket")
        self.assertTrue(result["is_finance"])
        self.assertLess(result["confidence"], 0.5)

    def test_secondary_categories_and_evidence(self):
        result = cls("Credit Risk Analyst, Leveraged Finance")
        self.assertTrue(result["secondary"])
        self.assertTrue(any(e.startswith("title:") for e in result["evidence"]))


class SeniorityTests(unittest.TestCase):
    def test_finance_levels(self):
        cases = {
            "2027 Summer Analyst": ("internship", "summer_analyst"),
            "Summer Associate, Investment Banking": ("internship", "summer_associate"),
            "Off-Cycle Intern, Global Markets": ("internship", "off_cycle"),
            "Spring Week 2027": ("internship", "spring_week"),
            "Finance Co-op (Winter 2027)": ("internship", "co_op"),
            "Graduate Analyst Program": ("new_grad", "graduate_analyst"),
            "First-Year Analyst": ("new_grad", "graduate_analyst"),
            "Rotational Analyst Program": ("new_grad", "rotational"),
            "Investment Banking Analyst": ("entry", "analyst"),
            "Research Analyst": ("entry", "analyst"),
            "Senior Associate": ("experienced", "senior_associate"),
            "Vice President, Leveraged Finance": ("senior", "vp"),
            "Executive Director": ("senior", "executive_director"),
            "Managing Director, M&A": ("senior", "managing_director"),
        }
        for title, (stage, level) in cases.items():
            result = detect_seniority(title)
            self.assertEqual((stage, level), (result["stage"], result["level"]), title)

    def test_analyst_is_entry_level_not_experienced(self):
        self.assertEqual("entry", detect_seniority("Analyst, Equity Research")["stage"])

    def test_associate_depends_on_division(self):
        ib = detect_seniority("Investment Banking Associate", associate_stage="experienced")
        am = detect_seniority("Associate, Asset Management", associate_stage="entry")
        self.assertEqual("experienced", ib["stage"])
        self.assertEqual("entry", am["stage"])
        self.assertTrue(any("post-MBA" in note for note in ib["notes"]))

    def test_years_of_experience_override_entry_titles(self):
        result = detect_seniority("Analyst", "Requires 4+ years of relevant experience in banking.")
        self.assertEqual("experienced", result["stage"])
        self.assertEqual(4, result["years_required"])


class RecruitingCycleTests(unittest.TestCase):
    def test_year_first_summer_analyst(self):
        cycle = detect_cycle("2027 Summer Analyst", stage="internship")
        self.assertEqual(("summer_2027", 2027, "internship"),
                         (cycle["cycle"], cycle["internship_year"], cycle["kind"]))

    def test_season_first(self):
        self.assertEqual("summer_2028", detect_cycle("Investment Banking Intern - Summer 2028",
                                                     stage="internship")["cycle"])
        self.assertEqual("winter_2027", detect_cycle("Risk Co-op (Winter 2027)", stage="internship")["cycle"])

    def test_new_grad_and_class_of(self):
        self.assertEqual("new_grad_2027", detect_cycle("New Grad 2027 Analyst", stage="new_grad")["cycle"])
        self.assertEqual("new_grad_2027", detect_cycle("Analyst Program - Class of 2027", stage="new_grad")["cycle"])
        self.assertEqual("new_grad_2027", detect_cycle("2027 Analyst Program", stage="new_grad")["cycle"])

    def test_off_cycle(self):
        self.assertEqual("off_cycle_2027", detect_cycle("Off-Cycle Internship 2027", stage="internship")["cycle"])

    def test_inferred_cycle_is_flagged(self):
        posted = datetime(2026, 9, 15, tzinfo=timezone.utc).timestamp()
        cycle = detect_cycle("Investment Banking Intern", stage="internship", posted_epoch=posted)
        self.assertEqual("summer_2027", cycle["cycle"])
        self.assertTrue(cycle["inferred"])

    def test_graduation_windows(self):
        window = graduation_window("Candidates graduating between December 2026 and June 2027 are eligible.")
        self.assertEqual(("2026-12", "2027-06"), (window["start"], window["end"]))
        self.assertEqual([2027], graduation_window("Open to the Class of 2027.")["years"])
        cycle = detect_cycle("2027 Summer Analyst", stage="internship")
        penultimate = graduation_window("Open to penultimate-year students.", cycle=cycle)
        self.assertEqual([2028], penultimate["years"])
        self.assertEqual({}, graduation_window("A great team culture."))


class DeadlineTests(unittest.TestCase):
    REF = datetime(2026, 10, 1, tzinfo=timezone.utc)

    def test_explicit_dates_are_high_confidence(self):
        for text, expected in (
                ("Applications close October 18, 2026.", "2026-10-18"),
                ("The application deadline is 18 October 2026.", "2026-10-18"),
                ("Please apply by 10/18/2026", "2026-10-18"),
                ("Deadline: 2026-11-01", "2026-11-01")):
            result = extract_deadline(text, self.REF)
            self.assertEqual(expected, result["date"], text)
            self.assertEqual("high", result["confidence"], text)

    def test_year_inferred_is_medium(self):
        result = extract_deadline("Apply by November 3rd to be considered.", self.REF)
        self.assertEqual(("2026-11-03", "medium"), (result["date"], result["confidence"]))

    def test_start_dates_are_not_deadlines(self):
        self.assertEqual({}, extract_deadline("The program starts June 1, 2027 in Toronto.", self.REF))
        self.assertEqual({}, extract_deadline("No dates here at all.", self.REF))

    def test_rolling_and_window_status(self):
        self.assertTrue(is_rolling("Applications are reviewed on a rolling basis; apply early."))
        today = datetime(2026, 10, 10).date()
        self.assertEqual("closing_soon", window_status("2026-10-14", False, "active", today))
        self.assertEqual("closed", window_status("2026-10-01", False, "active", today))
        self.assertEqual("rolling", window_status(None, True, "active", today))
        self.assertEqual("closed", window_status(None, True, "closed", today))


class EligibilityTests(unittest.TestCase):
    TEXT = ("Pursuing a Bachelor's degree with a minimum GPA of 3.5. Must be legally eligible to work in "
            "Canada. We are unable to provide visa sponsorship for this role. Bilingualism (English and "
            "French) is required.")

    def test_full_extraction(self):
        result = extract_eligibility(self.TEXT)
        self.assertEqual("Undergraduate", result["degree"])
        self.assertEqual(3.5, result["gpa_min"])
        self.assertEqual(["Canada"], result["work_authorization"])
        self.assertEqual("not_available", result["sponsorship"])
        self.assertEqual(["French"], result["languages"])

    def test_unknowns_stay_unknown(self):
        result = extract_eligibility("Join a collaborative team building great products.")
        self.assertIsNone(result["degree"])
        self.assertIsNone(result["gpa_min"])
        self.assertIsNone(result["sponsorship"])
        self.assertEqual([], result["languages"])

    def test_preferred_graduate_degree_is_not_required(self):
        result = extract_eligibility("Bachelor's required; a PhD is preferred but not required.")
        self.assertNotIn("phd", result["degree_required"])

    def test_gpa_formats_and_citizenship(self):
        self.assertEqual(3.3, extract_eligibility("3.3/4.0 GPA or higher")["gpa_min"])
        self.assertEqual("U.S. citizenship required",
                         extract_eligibility("U.S. citizenship is required for this position.")["citizenship"])
        self.assertEqual("available", extract_eligibility("Sponsorship: Offers Sponsorship.")["sponsorship"])


class SkillTests(unittest.TestCase):
    def labels(self, text):
        return {s["label"] for s in extract_skills(text, KN)}

    def test_synonyms_normalize(self):
        self.assertIn("DCF", self.labels("Build discounted cash flow analysis for clients."))
        self.assertIn("DCF", self.labels("Run a DCF."))
        self.assertIn("Comparable Companies", self.labels("trading comps and precedent transactions"))
        self.assertIn("Precedent Transactions", self.labels("trading comps and precedent transactions"))
        self.assertIn("Capital IQ", self.labels("Experience with CapIQ or FactSet"))
        self.assertIn("LBO", self.labels("leveraged buyout models"))

    def test_counts_are_merged_per_canonical_skill(self):
        skills = {s["key"]: s for s in extract_skills("DCF models. Discounted cash flow. DCF again.", KN)}
        self.assertEqual(3, skills["dcf"]["count"])

    def test_substrings_do_not_match(self):
        self.assertNotIn("Excel", self.labels("We excelled at teamwork"))
        self.assertNotIn("R", self.labels("Our recruiters are friendly"))


class CompensationTests(unittest.TestCase):
    def test_cad_range(self):
        comp = parse_compensation("$90,000–$105,000 CAD")
        self.assertEqual(("CAD", "year", 90000, 105000, False),
                         (comp["currency"], comp["period"], comp["annual_min"], comp["annual_max"],
                          comp["currency_inferred"]))
        self.assertEqual("$90,000–$105,000 CAD", comp["original"])
        self.assertIn("90k", comp["display"])

    def test_hourly_internship_is_annualized_estimate(self):
        comp = parse_compensation("$35/hour", "CA")
        self.assertEqual(72800, comp["annual_min"])
        self.assertTrue(comp["annualized_estimate"])
        self.assertEqual("CAD", comp["currency"])
        self.assertTrue(comp["currency_inferred"])

    def test_k_suffix_and_gbp(self):
        self.assertEqual((140000, 180000), tuple(parse_compensation("$140K – $180K", "US")[k]
                                                  for k in ("annual_min", "annual_max")))
        gbp = parse_compensation("£45,000 per annum")
        self.assertEqual(("GBP", 45000), (gbp["currency"], gbp["annual_min"]))

    def test_pay_transparency_text(self):
        comp = comp_from_description(
            "The expected base salary range for this role in New York is $110,000 - $125,000.", "US")
        self.assertEqual((110000, 125000, "USD"), (comp["annual_min"], comp["annual_max"], comp["currency"]))

    def test_non_numbers_return_empty(self):
        self.assertEqual({}, parse_compensation("Competitive"))


class CompanyAndLocationTests(unittest.TestCase):
    def test_aliases(self):
        for name, key in (("Goldman Sachs & Co. LLC", "goldman_sachs"), ("J.P. Morgan", "jpmorgan"),
                          ("RBC Capital Markets", "rbc"), ("TD Securities", "td"),
                          ("CPP Investments", "cpp_investments"), ("Citadel Securities", "citadel_securities"),
                          ("The Blackstone Group", "blackstone"), ("Bain & Company", "bain_company"),
                          ("Bain Capital", "bain_capital")):
            self.assertEqual(key, resolve_company(name, KN)["key"], name)

    def test_generic_words_do_not_match(self):
        self.assertFalse(resolve_company("Acme Capital Partners", KN)["known"])
        self.assertFalse(resolve_company("SIG Sauer Firearms", KN)["known"])

    def test_locations(self):
        self.assertEqual(["toronto"], parse_location("Toronto, ON, CA", KN)["cities"])
        self.assertEqual("canada", parse_location("Toronto, ON, CA", KN)["bucket"])
        self.assertEqual("us", parse_location("San Francisco, CA", KN)["bucket"])
        self.assertEqual(["london"], parse_location("London, United Kingdom", KN)["cities"])
        self.assertEqual(["london_on"], parse_location("London, ON", KN)["cities"])
        self.assertNotIn("vancouver", parse_location("Vancouver, WA", KN)["cities"])
        self.assertEqual("remote", parse_location("Remote", KN)["bucket"])


class FitScoreTests(unittest.TestCase):
    def target(self, **extra):
        job = {"title": "2027 Global Investment Banking Summer Analyst", "company": "RBC Capital Markets",
               "location": "Toronto, Ontario", "posted": NOW - 6 * 3600,
               "description": "Build financial models and valuation analysis in Excel. Pursuing an "
                              "undergraduate degree."}
        job.update(extra)
        return analyze(job)

    def test_target_role_scores_high_with_explained_subscores(self):
        result = self.target()
        self.assertGreaterEqual(result["fit"], 85)
        self.assertEqual(result["fit"], max(0, min(100, result["raw_total"])))
        self.assertEqual(result["raw_total"], sum(s["points"] for s in result["subscores"])
                         + sum(p["points"] for p in result["penalties"]))
        self.assertEqual(100, sum(s["max"] for s in result["subscores"]))
        for item in result["subscores"]:
            self.assertTrue(item["detail"], item)
            self.assertLessEqual(item["points"], item["max"])
        self.assertIn("Toronto preferred", result["reasons"])
        self.assertIn("Summer 2027 target cycle", result["reasons"])

    def test_penalties_are_explicit(self):
        senior = analyze({"title": "Managing Director, M&A", "company": "Evercore", "location": "London, UK"})
        keys = {p["key"] for p in senior["penalties"]}
        self.assertIn("senior", keys)
        self.assertIn("geography", keys)
        self.assertLess(senior["fit"], 40)
        mba = self.target(title="Summer Associate, Investment Banking")
        self.assertIn("degree", {p["key"] for p in mba["penalties"]})
        wrong_year = self.target(title="2025 Summer Analyst, Investment Banking")
        self.assertIn("cycle_year", {p["key"] for p in wrong_year["penalties"]})

    def test_freshness_matters_more_for_competitive_roles(self):
        fresh = self.target(posted=NOW - 3 * 3600)
        stale = self.target(posted=NOW - 3 * 86400)
        f = {s["key"]: s["points"] for s in fresh["subscores"]}["freshness"]
        s = {s["key"]: s["points"] for s in stale["subscores"]}["freshness"]
        self.assertGreaterEqual(f - s, 5)
        self.assertGreater(fresh["fit"], stale["fit"])

    def test_sponsorship_and_language_penalties_use_profile(self):
        job = {"title": "Investment Banking Analyst", "company": "National Bank Financial", "location": "Montreal, QC",
               "description": "Bilingualism (English and French) is required. We will not provide sponsorship."}
        profile = {"work_authorization": {"CA": "needs_sponsorship"}, "languages": ["English"]}
        keys = {p["key"] for p in analyze(job, profile)["penalties"]}
        self.assertEqual({"language", "sponsorship"} & keys, {"language", "sponsorship"})
        keys = {p["key"] for p in analyze(job, {"languages": ["English", "French"]})["penalties"]}
        self.assertNotIn("language", keys)

    def test_closed_and_watchlist(self):
        closed = analyze({"title": "Investment Banking Analyst", "company": "RBC"}, dyn={"status": "closed"})
        self.assertIn("closed", {p["key"] for p in closed["penalties"]})
        self.assertIn("CLOSED", closed["badges"])
        watched = analyze({"title": "Investment Banking Analyst", "company": "Unknown Advisors LLC"},
                          dyn={"watched": True})
        self.assertEqual(15, {s["key"]: s["points"] for s in watched["subscores"]}["company"])

    def test_profile_drives_ranking_for_other_families(self):
        swe = {"target_roles": ["software"], "target_company_types": ["fintech"],
               "target_locations": ["san_francisco"], "skills": ["python"]}
        job = {"title": "Software Engineer Intern - Summer 2027", "company": "Stripe",
               "location": "San Francisco, CA", "posted": NOW - 3600, "description": "Python services."}
        self.assertGreaterEqual(analyze(job, swe)["fit"], 85)
        self.assertLess(analyze(job)["fit"], 60)

    def test_badges(self):
        result = self.target(description="Applications are accepted on a rolling basis.")
        for badge in ("TODAY", "ROLLING", "2027", "SUMMER ANALYST"):
            self.assertIn(badge, result["badges"])

    def test_profile_validation(self):
        self.assertEqual([], validate_profile(merge_profile({}), KN))
        problems = validate_profile(merge_profile({"target_roles": ["astrology"], "graduation_year": 1990}), KN)
        self.assertEqual(2, len(problems))


class FamilyClassifierTests(unittest.TestCase):
    """Job families outside finance: physical engineering, subject words and exact aliases."""

    def test_engineering_outside_software_is_not_software(self):
        for title in ("Civil Engineering Intern", "Water Infrastructure Engineering Intern",
                      "Environmental Engineering Co-op", "Welding Engineer (Starship)",
                      "Chemical Process Engineer", "Water Systems Engineer"):
            self.assertNotEqual("software", cls(title)["family"], title)
        self.assertEqual("hardware", cls("Mechanical Engineering Intern")["family"])
        for title in ("Infrastructure Engineer Intern", "Cloud Infrastructure Engineer",
                      "Software Engineer, Energy Trading", "Data Platform Engineer, Utilities",
                      "Privacy & Civil Liberties Engineer - New Grad",
                      "IT Systems Engineer, Propellant Generation & Industrial Systems"):
            self.assertIn(cls(title)["family"], ("software", "data_ml"), title)

    def test_subject_words_do_not_override_a_business_occupation(self):
        for title, family in (("Cybersecurity Analyst", "software"), ("2027 Summer Intern - Cyber Security", "software"),
                              ("AI Research Intern", "data_ml")):
            result = cls(title)
            self.assertEqual((family, None, False), (result["family"], result["subcategory"], result["is_finance"]), title)
        self.assertEqual("product", cls("Principal Product Manager - Identity Threat Detection & Response")["family"])
        self.assertEqual("people_legal", cls("Recruiter, AI Research")["family"])
        self.assertEqual("people_legal", cls("Senior Legal Counsel – Cybersecurity & Data Protection")["family"])
        self.assertEqual("sales", cls("Product Marketing Manager, Cybersecurity")["family"])
        self.assertEqual("hardware", cls("Hardware Test Automation Engineer")["family"])

    def test_finance_roles_stay_finance(self):
        result = cls("2027 Investment Banking Summer Analyst")
        self.assertTrue(result["is_finance"])
        self.assertEqual("investment_banking", result["category"])
        self.assertTrue(cls("Quantitative Research Intern (NLP)", company_type="quant_firm")["is_finance"])

    def test_exact_only_aliases_keep_the_display_name_exact(self):
        # '=harvey' and '=cohere': other firms that merely contain the word stay unknown.
        for name in ("Harvey Nash", "Cohere Health", "Apple Bank", "Google Gemini Team"):
            self.assertNotIn(resolve_company(name, KN)["key"], {"harvey", "cohere", "apple", "gemini"}, name)
        self.assertEqual("harvey", resolve_company("Harvey", KN)["key"])
        self.assertEqual("gemini", resolve_company("Gemini", KN)["key"])


if __name__ == "__main__":
    unittest.main()
