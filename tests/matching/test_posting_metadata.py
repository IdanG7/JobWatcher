"""Posting dates and pay need explicit recruiting / compensation evidence."""
from datetime import datetime, timezone
import unittest

from intel.compensation import comp_from_description, parse_compensation
from intel.cycle import extract_deadline


class PostingDeadlineTests(unittest.TestCase):
    REF = datetime(2026, 10, 10, tzinfo=timezone.utc)

    def test_explicit_source_deadlines_and_posting_close_labels(self):
        for text, expected in (
            ("Application Deadline:\n2026-11-01", "2026-11-01"),
            ("Application Deadline: 2026-11-01T23:59:59Z", "2026-11-01"),
            ("Posting End Date:\n2026/11/02", "2026-11-02"),
            ("Job Posting Closing Date: 03-Nov-2026", "2026-11-03"),
            ("Applications will be accepted until 14/11/2026.", "2026-11-14"),
            ("Submit your application no later than November 15, 2026.", "2026-11-15"),
        ):
            with self.subTest(text=text):
                deadline = extract_deadline(text, self.REF)
                self.assertEqual(expected, deadline.get("date"))
                self.assertEqual("high", deadline.get("confidence"))
                self.assertIn(expected[:4], deadline["text"])

    def test_unrelated_term_and_project_dates_do_not_close_a_posting(self):
        for text in (
            "The internship runs until August 31, 2027.",
            "You must remain enrolled until May 1, 2027.",
            "Benefits are available until December 31, 2026.",
            "Employment End Date: November 1, 2026",
            "Project deadline: November 1, 2026",
            "Application deadline: not yet announced. Start date: November 1, 2026.",
            "Application deadline: not yet announced. Graduation: November 1, 2026.",
        ):
            with self.subTest(text=text):
                self.assertEqual({}, extract_deadline(text, self.REF))


class PostingCompensationTests(unittest.TestCase):
    def test_bank_annual_and_hourly_pay_and_source_metadata(self):
        for text, period, low, high in (
            ("Base salary:\nCAD 58,000 - 76,000 YEAR", "year", 58000, 76000),
            ("The hourly pay range is $24.50–$32.75 per hour.", "hour", 50960, 68120),
            ("Base salary: CAD 25.50 - 32.00 HOUR", "hour", 53040, 66560),
            ("Base salary: CAD 1,000 - 1,500 WEEK", "week", 52000, 78000),
            ("The annual base salary range for this role is CAD $90–105k.", "year", 90000, 105000),
            ("Salary range: $90,000 CAD - $105,000 CAD per year.", "year", 90000, 105000),
        ):
            with self.subTest(text=text):
                comp = comp_from_description(text, "CA")
                self.assertEqual((period, low, high),
                                 (comp.get("period"), comp.get("annual_min"), comp.get("annual_max")))
                self.assertEqual("CAD", comp["currency"])
                self.assertEqual("description", comp["source"])
                self.assertTrue(comp["original"])

    def test_shorthand_scales_both_range_endpoints(self):
        comp = parse_compensation("CAD $90–105k per year", "CA")
        self.assertEqual((90000, 105000), (comp.get("annual_min"), comp.get("annual_max")))

    def test_benefits_and_business_amounts_are_not_candidate_pay(self):
        for text in (
            "We pay attention to our $150 billion assets under management.",
            "Our compensation team supports $120 million in annual revenue.",
            "Compensation and benefits include $5,000 annual tuition reimbursement.",
            "We offer a $1,000 monthly wellness benefit.",
            "Pay benefits include a $5,000 signing bonus.",
            "The salary team manages a $100,000 operating budget.",
        ):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "CA"))

    def test_base_pay_survives_separate_benefit_amounts(self):
        comp = comp_from_description(
            "We offer a $5,000 tuition allowance. Base salary: CAD $65,000–$75,000 per year. "
            "Benefits include $1,000 for wellness.", "CA")
        self.assertEqual((65000, 75000), (comp.get("annual_min"), comp.get("annual_max")))


class PostingPayFormatsTests(unittest.TestCase):
    """How employers' sites write pay, taken from stored postings that showed none or the wrong figure."""

    def pay(self, text, country="US"):
        comp = comp_from_description(text, country)
        return (comp.get("min"), comp.get("max"), comp.get("period"), comp.get("currency"))

    def test_html_codes_in_the_text_are_read_as_what_they_stand_for(self):
        self.assertEqual((191000, 250000, "year", "USD"), self.pay("Salary Range $191,000 &mdash; $250,000 USD"))
        self.assertEqual((105000, 145000, "year", "USD"),
                         self.pay("COMPENSATION AND BENEFITS:&#xa;Pay Range:&#xa;Level 1: $105,000.00 - $145,000.00"))

    def test_an_amount_with_its_currency_after_it(self):
        amazon = ("Learn more about our benefits at https://amazon.jobs/en/benefits . \xa0 \n\n"
                  "USA, NY, New York - 172,400.00 - 223,400.00 USD annually\nUSA, WA, Seattle - 143,700.00 - 194,400.00 USD annually")
        self.assertEqual((172400, 223400, "year", "USD"), self.pay(amazon))
        self.assertEqual((109395, 109395, "year", "USD"),
                         self.pay("Austin, TX, USA - 109,395.00 USD Annually\nSan Francisco, CA, USA - 125,885.00 USD Annually"))
        self.assertEqual((300000, 300000, "year", "USD"),
                         self.pay("The estimated base salary range for this position is 300,000 USD per year (or local equivalent)."))

    def test_the_ways_a_pay_range_is_introduced(self):
        self.assertEqual((133194, 190278, "year", "USD"),
                         self.pay("The United States base range for this position is $133,194 - $190,278 plus equity."))
        self.assertEqual((57, 57, "hour", "USD"), self.pay(
            "For roles based in San Francisco or New York City, the estimated hourly range for this role is "
            "$57/hr for Bachelors and $61/hr for Master’s."))
        self.assertEqual((90000, 136000, "year", "USD"), self.pay("Hiring Range: $90,000 — $136,000 USD"))

    def test_a_location_or_level_label_between_the_heading_and_the_amount(self):
        self.assertEqual((127000, 203000, "year", "CAD"), self.pay(
            "may be eligible to participate in a discretionary annual incentive program. \n Pay Ranges \n"
            "Vancouver, Canada: $127,000 - $203,000 CAD", "CA"))
        self.assertEqual((135150, 182850, "year", "USD"), self.pay(
            "Summary Pay Range: \n Level 4: $135,150-$182,850\n Level 5: $165,750-$224,250"))
        self.assertEqual((144000, 208000, "year", "USD"), self.pay(
            "Individual pay is determined by factors including job-related skills, experience, and relevant education "
            "or training.\n US: $144000 - $208000 (USD) + 15% bonus target + equity + benefits\n"
            "Learn more about benefits at Google ."))
        self.assertEqual((179400, 204700, "year", "USD"), self.pay(
            "The minimum and maximum full-time annual salaries for this role are listed below, by location. Please "
            "note that this salary information is solely for candidates hired to perform work within one of these "
            "locations. Salaries for part-time roles will be prorated based upon the agreed upon number of hours to "
            "be regularly worked.\n\nPlano, TX: $179,400 - $204,700 for Full-stack Engineer 4"))

    def test_the_period_is_the_one_written_by_the_amount(self):
        for text, expected in (
            ("Salary Range\n $42 — $42 USD", (42, 42, "hour", "USD")),
            ("Salary Range: $22.00 - $24.00 based on experience and location.", (22, 24, "hour", "USD")),
            ("The hourly pay for this role is $24-$28, commensurate with the year in school and experience",
             (24, 28, "hour", "USD")),
            ("Salary Range: 40 hours/week; $221,187 to $290,000/year", (221187, 290000, "year", "USD")),
            ("Anticipated New York and Chicago weekly base salary range $3,500-5,700.", (3500, 5700, "week", "USD")),
            ("Hardware Interns are paid an hourly rate equivalent to an annualized range of $108,000-126,000, "
             "depending on experience and education level.", (108000, 126000, "year", "USD")),
            ("For roles based in Coppell, TX: The salary range for this position is $104,000.00 - $166,000.00 per hour.",
             (104000, 166000, "year", "USD")),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, self.pay(text))
        self.assertEqual((2450, 2450, "month", "EUR"),
                         self.pay("• For Portugal based hires: the monthly salary is €2,450.", None))

    def test_semi_monthly_pay(self):
        comp = comp_from_description("Salary Range (Semi-Monthly Rate) \n Client & Product Functions: $5,500 – $7,500 \n\n"
                                     " Our benefits", "US")
        self.assertEqual((5500, 7500, "semimonth", 132000, 180000),
                         (comp.get("min"), comp.get("max"), comp.get("period"), comp.get("annual_min"), comp.get("annual_max")))
        self.assertIn("semi-monthly", comp["display"])

    def test_ranges_written_with_labels_or_units_on_each_end(self):
        for text, expected in (
            ("Pay Range: MIN $134,950.00 -MID $179,930.00 - MAX $224,920.00", (134950, 224920, "year", "USD")),
            ("Salary: $178,000/year to $250,000/year", (178000, 250000, "year", "USD")),
            ("The US base salary range for this full-time position is: $125,000 - $190,000K + equity + benefits",
             (125000, 190000, "year", "USD")),
            ("CA Salary Min $38.77 to Max $41.75\n\n This position is on-site in Santa Rosa, California.",
             (38.77, 41.75, "hour", "USD")),
            ("The United States base range for this position is $184,050 $262,928 plus equity.",
             (184050, 262928, "year", "USD")),
            ("$20 min hourly wage – $35 max hourly wage, sign-on bonus, 11 paid holidays annually",
             (20, 35, "hour", "USD")),
            ("Starting base pay (Cash + RSU): $137,500 + sign on bonus in Pleasanton", (137500, 137500, "year", "USD")),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, self.pay(text))

    def test_a_placeholder_range_gives_way_to_the_real_one(self):
        self.assertEqual((20, 40, "hour", "USD"), self.pay(
            "Expected Salary Range \xa0 \n $20.00 - $40.00\xa0 \n\n Expected Salary Range \n$0.00 - $0.00 \n"
            " The exact Salary will be determined based on qualifications"))
        self.assertEqual({}, comp_from_description("Target salary range: USD $0.00/Yr. - USD $0.00/Yr.", "US"))

    def test_a_pay_range_written_without_a_currency_sign(self):
        self.assertEqual((140000, 160000, "year", "USD"), self.pay(
            "Salary range for the position: 140,000 - 160,000 per year. The successful candidate's salary will be "
            "determined based on factors."))
        self.assertEqual((120000, 120000, "year", "CAD"), self.pay("Salary Range: 120,000.00 - 120,000.00", "CA"))
        for text in ("Pay grade: 7 - 9", "Salary grade: 12 - 14 depending on experience"):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "US"))

    def test_base_pay_named_inside_an_on_target_earnings_line(self):
        self.assertEqual((25.49, 26.93, "hour", "USD"), self.pay(
            "For Miami, FL-based roles: The total annualized on-target earnings (OTE) for this position is USD $88,365 "
            "- USD $93,357. The OTE includes a base hourly rate of USD $25.49 per hour - USD $26.93 per hour and an "
            "annualized cash variable incentive target range of USD $35,346 - USD $37,343."))
        self.assertEqual({}, comp_from_description(
            "The on-target earnings (OTE) range for this role is $147,300 to $231,300 USD.", "US"))

    def test_a_range_by_location_with_its_pay_word_after_it(self):
        self.assertEqual((164700, 266000, "year", "USD"), self.pay(
            "Wage Transparency:\n\nBased on applicable legislation, the below details pay ranges in the following "
            "locations: California: $164,700.00 - $266,000.00 base salary This role is also eligible for the following: "
            "Bonus: Sales incentive"))

    def test_a_posting_run_into_one_line_reads_only_the_words_near_the_pay(self):
        bullets = ("Experience with month-end close and monthly sales targets Benefits coverage and 401(k) matching "
                   "from day one Familiarity with 3D CAD software " * 4)
        self.assertEqual((171100, 213900, "year", "USD"), self.pay(
            f"{bullets}Pay Disclosure The salary range for this role is USD 171,100-213,900 for Southern California "
            "based applicants."))
        self.assertEqual((40, 45, "hour", "USD"), self.pay(
            f"{bullets}Pay Disclosure The salary range for this role is $40 - $45 an hour for Illinois based applicants."))

    def test_a_period_away_from_the_figures_must_fit_their_size(self):
        self.assertEqual((27700, 27700, "year", "GBP"), self.pay(
            "You'll work 5 days per week from our Leeds office and start with a competitive salary of £27,700.", "UK"))
        self.assertEqual((12600, 167000, "year", "USD"), self.pay("US Salary Range $12,600 — $167,000 USD"))
        self.assertEqual((25, 40, "hour", "USD"), self.pay(
            "Knowledge of 3D CAD systems like CATIA is preferred.\n\nPay: $25.00-40.00 per hour"))

    def test_a_starting_rate_gives_way_to_the_pay_range_below_it(self):
        self.assertEqual((19.5, 29.25, "hour", "USD"), self.pay(
            "The Starting Hourly Rate / Salario por Hora Inicial is $19.50 USD per hour.\n\n"
            "The Pay Range / Rango salarial is $19.50 USD - $29.25 USD per hour."))

    def test_the_figure_a_pay_label_gives_wins_over_others(self):
        self.assertEqual((40000, 40000, "year", "CAD"), self.pay(
            "Please note the base salary for this specific position is $40,000 and this role may be eligible to receive "
            "additional monthly discretionary bonus.\n\n Salary : \n\n$33,500.00 - $60,000.00 \n Pay Type: Salaried", "CA"))
        self.assertEqual((43000, 43000, "year", "USD"), self.pay(
            "Signing bonus valued at $7,500 to be paid in three installments. The first $2,500 will be issued in the pay "
            "period following 90 days of employment, and the final $2,500 after one year of employment.\n\n"
            " Compensation \nBase Pay: $43,000.00 \n\nTotal Target Compensation (Base Pay plus Targeted Commission): "
            "$77,000.00"))

    def test_labels_that_name_bonus_only_to_set_it_aside(self):
        for text, expected in (
            ("Annual base salary range (excluding equity and bonus): $218,025 — $256,500 USD",
             (218025, 256500, "year", "USD")),
            ("On-target Earnings OR Base Salary range (San Francisco, CA) $207,000 — $244,000 USD",
             (207000, 244000, "year", "USD")),
            ("Salary range: $246,000 - $320,000 / year - Plus eligible for annual bonus", (246000, 320000, "year", "USD")),
            ("Annual Salary Range: $130,000-$170,000 Annual Bonus Target: 20%", (130000, 170000, "year", "USD")),
            ("Below is the US base salary for this position. Additional compensation such as Bonus, Commission, Equity "
             "and other benefits may also apply.\n $163,800 — $257,400 USD", (163800, 257400, "year", "USD")),
            ("the compensation range for this position is typically between $$55,000 base pay - $115,000 OTE.",
             (55000, 55000, "year", "USD")),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, self.pay(text))

    def test_one_figure_under_a_label_on_the_line_above(self):
        self.assertEqual((70000, 70000, "year", "USD"), self.pay(
            "The base salary is one component of total compensation, which also includes discretionary bonus and "
            "incentive compensation. The firm's good faith and reasonable estimate of the possible salary range for "
            "this role at the time of posting is:\n\n $70,000\n\n\nActual salary at the time of hire may vary"))
        self.assertEqual((7100, 89100, "year", "USD"), self.pay(
            "The US base salary range for this position (this does not include bonus, equity and benefits):\n "
            "$7,100 — $89,100 USD \n\n Commitment to Equal Opportunity"))

    def test_figures_written_the_european_way_or_run_together(self):
        self.assertEqual((85600, 128400, "year", "EUR"), self.pay(
            "Full Time Salary Range:  85 600,00 € - 128 400,00 € ---------------", "IE"))
        self.assertEqual((100000, 130000, "year", "EUR"), self.pay("Base Salary Range €100.000 — €130.000 EUR", "DE"))
        self.assertEqual((55200, 99240, "year", "USD"), self.pay(
            "The compensation range for the position in the U.S. is - $55,200to$99,240based on a full-time schedule"))
        self.assertEqual((140000, 170000, "year", "USD"), self.pay(
            "Pay Details: 170,000$140,000 - 170,000$160,000 USDUSD", "CA"))

    def test_odd_number_writing(self):
        for text, expected in (
            ("Compensation Range: Between $38,85 - $54,34 CDN hourly", (38.85, 54.34, "hour", "CAD")),
            ("The pay range for this position in Canada is $97, 300 - $155, 300 CAD", (97300, 155300, "year", "CAD")),
            ("The base salary is between $108,00 and $154,500 per year.", (108000, 154500, "year", "USD")),
            ("Pay Equity $43,900.00 - $54,900.00 - $65,800.00 of salary range", (43900, 65800, "year", "USD")),
            ("a minimum annual salary of $98,300, a midpoint of $115,700, and a maximum salary of $133,100",
             (98300, 133100, "year", "USD")),
            ("USD Salary Range: $160,000 - $210,000   CAD Salary Range: C$225,000 - C$285,000",
             (160000, 210000, "year", "USD")),
            ("Pay Range: \nUnited States: 69,077 - 84,427 USD\n \n Base pay offered may vary", (69077, 84427, "year", "USD")),
        ):
            with self.subTest(text=text):
                self.assertEqual(expected, self.pay(text))

    def test_pay_in_another_currency_shows_nothing(self):
        for text in ("Mexico Monthly Pay Range $153,333.33 - $191,666.67 MXN",
                     "Salary range: 307 800 zł — 486 900 zł PLN"):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "US"))
        self.assertEqual({}, parse_compensation("A$235K – A$425K • Offers Equity", "US"))

    def test_commission_bonus_and_target_earnings_are_not_base_pay(self):
        self.assertEqual((15, 15, "hour", "USD"), self.pay(
            "Compensation:\nTotal Target Compensation (Base Pay plus Targeted Commission): $23.38\nBase Pay: $15.00"))
        self.assertEqual((38800, 58200, "year", "USD"), self.pay(
            "At 100% of target, annual earnings range from $88,100 to $109,700.\n\n"
            "The base salary for this role in Louisville ranges from $38,800 to $58,200."))
        for text in ("Targeted Commission: $45,000.00",
                     "Annual OTE Salary\n $54,621 — $73,440 USD \n\n Total Rewards",
                     "The bonus will be paid out as $1,250 gross pay adjustment on the employee's first pay warrant",
                     "The state also covers a life-insurance benefit of two times employees' annual salary (up to $200,000).",
                     "You'll own a book of customer accounts up to $50K a year."):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "US"))

    def test_benefit_and_business_amounts_stay_out(self):
        for text in (
            " - Annual learning & development stipend ($1,500 USD equivalent per year)",
            " - Annual learning & development stipend (€1,400 per year)",
            " - 401(k) retirement plan with an employer match of up to 1% of your eligible pay each pay period up to "
            "$2,000 annually",
            " - Achieving revenue targets >$1M per year for more than 3 years",
            "a one-time Work From Home allowance, up to $3,000 in mental health coverage and up to $5,000 in annual "
            "tuition subsidies.",
            "We automate how over $275B in annualized spend flows in and out of 85,000+ companies.",
            "Compensation: our $5m of safety funding awards support research.",
        ):
            with self.subTest(text=text):
                self.assertEqual({}, comp_from_description(text, "US"))


if __name__ == "__main__":
    unittest.main()
