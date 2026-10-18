"""Cover letters for resumes unlike the one Foothold was first tuned on.

Eight made-up candidates, each with a resume laid out differently and a past cover letter written months ago,
so some of what it says is out of date on TODAY. The tests here check the parts that run without a model: reading
role dates in any format, the candidate's name, the letter's greeting and closing, which facts the model reads
are kept, and that every out-of-date sentence is put to the model's check. tools/letter_eval.py runs the same
candidates through the local model.

Each candidate has:
roles / credentials: what a correct reading of the resume gives, with each role's state on TODAY.
stale: phrases in the past letter that are now wrong; keep: phrases that are still right.
"""
import json
import unittest
from datetime import date
from unittest import mock

from intel import cover_letter, letterhead, resume_facts

TODAY = date(2026, 10, 18)

CANDIDATES = [
    dict(
        id="ey_accounting",
        note="2-letter employer (EY), en dashes, credential without a level (CSC), 'Completed'",
        name="Priya Natarajan",
        resume="""Priya Natarajan
Toronto, ON | priya.natarajan@example.com | 416-555-0132
EDUCATION
York University, Schulich School of Business — BBA, Accounting, Expected May 2028
EXPERIENCE
EY — Assurance Intern                                   May 2025 – Aug 2025
• Tested revenue controls for three mid-market clients and documented 40+ walkthroughs.
Schulich School of Business — Teaching Assistant, Financial Accounting   Sept 2025 – Present
• Run weekly tutorials for 60 students.
CERTIFICATIONS
Canadian Securities Course (CSC) — Completed, 2025
CPA PEP Core 1 — In progress
SKILLS
Excel, CaseWare, IDEA, Power BI""",
        letter="""Priya Natarajan
Toronto, ON | priya.natarajan@example.com | 416-555-0132

June 30, 2025

Dear Hiring Manager,

I am writing to apply for the Audit Co-op role at Deloitte. I am currently an Assurance Intern at EY, where I test revenue controls for mid-market clients and document process walkthroughs.

I am also completing the Canadian Securities Course this summer, which has deepened my understanding of capital markets and the products our clients hold.

Beyond the technical work, I enjoy explaining accounting concepts clearly, and I am pursuing the CPA designation through the PEP program.

Thank you for considering my application.

Kind regards,
Priya Natarajan""",
        roles=[("EY", "Assurance Intern", "May 2025 – Aug 2025", "ended"),
               ("Schulich School of Business", "Teaching Assistant, Financial Accounting", "Sept 2025 – Present", "ongoing")],
        credentials=[("Canadian Securities Course (CSC)", "passed"), ("CPA PEP Core 1", "in progress")],
        stale=["I am currently an Assurance Intern at EY", "I am also completing the Canadian Securities Course"],
        keep=["pursuing the CPA"],
    ),
    dict(
        id="td_numeric",
        note="numeric dates 05/2024 – 08/2024, name in capitals, FRM still a candidacy",
        name="Marcus Chen",
        resume="""MARCUS CHEN
marcus.chen@example.com • (647) 555-0199 • linkedin.com/in/marcuschen
Education
University of Waterloo — Bachelor of Mathematics, Mathematical Finance (09/2022 – 04/2027)
Experience
Summer Analyst, Global Markets | TD Securities | 05/2024 – 08/2024
- Built a Python tool that reconciled 2,000 daily FX trades.
Quantitative Research Intern | Manulife Investment Management | 09/2025 – Present
- Backtest factor models for Canadian equities.
Certifications
FRM Part I Candidate (exam November 2026)
Skills: Python, SQL, Excel/VBA, Bloomberg""",
        letter="""MARCUS CHEN
marcus.chen@example.com • (647) 555-0199

July 15, 2024

Dear Recruiting Team,

I am excited to apply for the Sales & Trading Summer Analyst program at RBC Capital Markets. I currently work at TD Securities as a Summer Analyst on the Global Markets desk, where I built a Python tool that reconciles 2,000 daily FX trades.

As an FRM Part I candidate, I am building a rigorous grounding in market and credit risk that I would bring to the trading floor.

I would welcome the chance to discuss how my quantitative background fits your team.

Best regards,
Marcus Chen""",
        roles=[("TD Securities", "Summer Analyst, Global Markets", "05/2024 – 08/2024", "ended"),
               ("Manulife Investment Management", "Quantitative Research Intern", "09/2025 – Present", "ongoing")],
        credentials=[("FRM Part I Candidate", "planned")],
        stale=["I currently work at TD Securities"],
        keep=["FRM Part I candidate"],
    ),
    dict(
        id="deloitte_seasons",
        note="season dates (Summer 2025), 'This summer I am' wording, BMC 'certificate earned', 'Hello' greeting",
        name="Sofia Alvarez",
        resume="""Sofia Alvarez
Vancouver, BC · sofia.alvarez@example.com · 604-555-0117
EDUCATION
University of British Columbia, Sauder School of Business
Bachelor of Commerce, Finance — Expected 2027
WORK EXPERIENCE
Deloitte — Financial Advisory Summer Intern, Summer 2025
Supported valuation work on two mid-market transactions; built comparable company analyses.
UBC Investment Club — Portfolio Manager, Fall 2025 – Present
Lead a team of six analysts covering Canadian energy names.
CERTIFICATES
Bloomberg Market Concepts (BMC) — certificate earned
SKILLS
Excel, PowerPoint, Capital IQ, FactSet""",
        letter="""Sofia Alvarez
Vancouver, BC · sofia.alvarez@example.com · 604-555-0117

July 2, 2025

Hello Hiring Team,

I am applying for the Investment Banking Analyst internship at CIBC Capital Markets. This summer I am interning in Financial Advisory at Deloitte, supporting valuation work on two mid-market transactions.

I am working toward the Bloomberg Market Concepts certificate to strengthen my command of market data and terminal workflows.

I would be glad to bring this experience and my enthusiasm for transactions to your team.

Warm regards,
Sofia Alvarez""",
        roles=[("Deloitte", "Financial Advisory Summer Intern", "Summer 2025", "ended"),
               ("UBC Investment Club", "Portfolio Manager", "Fall 2025 – Present", "ongoing")],
        credentials=[("Bloomberg Market Concepts (BMC)", "passed")],
        stale=["This summer I am interning in Financial Advisory at Deloitte",
               "I am working toward the Bloomberg Market Concepts certificate"],
        keep=[],
    ),
    dict(
        id="nbc_year_only",
        note="year-only dates (2023 – 2025), 'CURRICULUM VITAE' heading, CFA Level II candidate with Level I passed",
        name="Olivier Tremblay",
        resume="""CURRICULUM VITAE
Olivier Tremblay
Montréal, QC | olivier.tremblay@example.com | 514-555-0144
Education
HEC Montréal — B.B.A., Finance, 2022 – 2026
Experience
National Bank of Canada — Credit Analyst Intern, 2023 – 2025
Prepared credit memos for commercial borrowers in Quebec.
Desjardins — Junior Portfolio Analyst, 2026 – present
Monitor client portfolios and prepare rebalancing proposals.
Professional designations
CFA Level II Candidate (Level I passed, February 2026)
Languages: French, English""",
        letter="""Olivier Tremblay
Montréal, QC | olivier.tremblay@example.com | 514-555-0144

October 3, 2025

Dear Hiring Manager,

I am pleased to apply for the Equity Research Associate role at Desjardins Capital Markets. I currently work at National Bank of Canada as a Credit Analyst Intern, preparing credit memos for commercial borrowers.

I am presently a CFA Level I candidate, and my studies have sharpened my financial statement analysis.

I would welcome the opportunity to contribute to your research team.

Sincerely,
Olivier Tremblay""",
        roles=[("National Bank of Canada", "Credit Analyst Intern", "2023 – 2025", "ended"),
               ("Desjardins", "Junior Portfolio Analyst", "2026 – present", "ongoing")],
        credentials=[("CFA Level II Candidate", "in progress"), ("CFA Level I", "passed")],
        stale=["I currently work at National Bank of Canada", "I am presently a CFA Level I candidate"],
        keep=[],
    ),
    dict(
        id="scotia_pipes",
        note="table rows with pipes, 'Jan–Apr 2026' (start month without a year), Series 7 'passed'",
        name="Aisha Mohammed",
        resume="""Aisha Mohammed | aisha.mohammed@example.com | 905-555-0181 | Mississauga, ON
EDUCATION | McMaster University | Bachelor of Commerce (Honours) | Expected Apr 2027
EXPERIENCE
Scotiabank | Market Risk Analyst Co-op | Jan–Apr 2026
Calculated daily VaR for the rates desk and flagged limit breaches.
Mac Finance Society | VP Education | Sep 2025–present
Organize technical workshops for 120 members.
LICENCES
Series 7 — passed
SKILLS | Python | SQL | Excel | Tableau""",
        letter="""Aisha Mohammed | aisha.mohammed@example.com | 905-555-0181

February 10, 2026

Dear Hiring Manager,

I am applying for the Risk Management Summer Analyst role at BMO. I am currently a Market Risk Analyst Co-op at Scotiabank, where I calculate daily VaR for the rates desk.

I am preparing to write the Series 7 exam this spring, and I am eager to deepen my knowledge of securities regulation.

Thank you for your time.

Best regards,
Aisha Mohammed""",
        roles=[("Scotiabank", "Market Risk Analyst Co-op", "Jan–Apr 2026", "ended"),
               ("Mac Finance Society", "VP Education", "Sep 2025–present", "ongoing")],
        credentials=[("Series 7", "passed")],
        stale=["I am currently a Market Risk Analyst Co-op at Scotiabank", "I am preparing to write the Series 7"],
        keep=[],
    ),
    dict(
        id="gs_current_role",
        note="'June 2024 to August 2024', 'In my current role at' wording, CAIA Level I passed",
        name="Daniel Kim",
        resume="""Daniel Kim
New York, NY — daniel.kim@example.com — (212) 555-0170
EDUCATION
New York University, Stern School of Business — B.S. Finance, expected May 2027
EXPERIENCE
Goldman Sachs, Asset Management Summer Analyst — June 2024 to August 2024
Screened 30+ private credit deals and drafted investment memo sections.
Stern Investment Fund, Analyst — September 2025 to Present
Pitch two long/short ideas per semester.
CERTIFICATIONS
CAIA Level I — Passed (September 2026)""",
        letter="""Daniel Kim
New York, NY — daniel.kim@example.com — (212) 555-0170

August 1, 2024

Dear Recruiting Team,

I am writing to apply for the Private Credit Analyst internship at Blackstone. In my current role at Goldman Sachs, I screen private credit deals and draft sections of investment memos.

I am a CAIA Level I candidate, which reflects my commitment to alternative investments.

I look forward to discussing how I can contribute to your team.

Respectfully,
Daniel Kim""",
        roles=[("Goldman Sachs, Asset Management", "Summer Analyst", "June 2024 to August 2024", "ended"),
               ("Stern Investment Fund", "Analyst", "September 2025 to Present", "ongoing")],
        credentials=[("CAIA Level I", "passed")],
        stale=["In my current role at Goldman Sachs", "I am a CAIA Level I candidate"],
        keep=[],
    ),
    dict(
        id="kpmg_iso",
        note="ISO dates (2025-05 – 2025-08), no current role, present tense without 'currently', 'To the Hiring Committee'",
        name="Hannah O'Brien",
        resume="""Hannah O'Brien
Halifax, NS · hannah.obrien@example.com · 902-555-0108
EDUCATION
Dalhousie University — Bachelor of Commerce, Accounting (graduated 2026-05)
EXPERIENCE
KPMG — Tax Intern (2025-05 – 2025-08)
Prepared corporate tax provisions for 12 clients.
Dalhousie Commerce Society — Treasurer (2024-09 – 2026-04)
Managed a $45,000 annual budget.
DESIGNATIONS
CPA Candidate (CPA Atlantic School of Business)""",
        letter="""Hannah O'Brien
Halifax, NS · hannah.obrien@example.com · 902-555-0108

July 20, 2025

To the Hiring Committee,

I am applying for the Staff Accountant position at Grant Thornton. I am currently interning in Tax at KPMG, where I prepare corporate tax provisions for twelve clients.

As Treasurer of the Dalhousie Commerce Society, I manage a $45,000 annual budget.

I am pursuing my CPA designation and would be glad to grow with your firm.

Thank you,
Hannah O'Brien""",
        roles=[("KPMG", "Tax Intern", "2025-05 – 2025-08", "ended"),
               ("Dalhousie Commerce Society", "Treasurer", "2024-09 – 2026-04", "ended")],
        credentials=[("CPA Candidate", "in progress")],
        stale=["I am currently interning in Tax at KPMG", "I manage a $45,000 annual budget"],
        keep=["pursuing my CPA"],
    ),
    dict(
        id="manulife_stacked",
        note="title, employer and dates on separate lines; CFA Level I only scheduled; 'Hi there'",
        name="Wei Zhang",
        resume="""Wei Zhang
Calgary, AB | wei.zhang@example.com | 403-555-0155

Education
University of Calgary, Haskayne School of Business
BComm, Finance | Expected 2027

Experience
Finance Co-op
Manulife
Sep 2025 - Dec 2025
Automated the monthly expense variance report.

Investment Banking Summer Analyst
BMO Capital Markets
May 2026 - Present
Build trading comparables for energy clients.

Certifications
CFA Level I — scheduled for February 2027""",
        letter="""Wei Zhang
Calgary, AB | wei.zhang@example.com | 403-555-0155

November 5, 2025

Hi there,

I am excited to apply for the Investment Banking Summer Analyst role at BMO Capital Markets. Currently, I am a Finance Co-op at Manulife, where I automated the monthly expense variance report.

I am a CFA Level I candidate, sitting the exam in February 2027.

I would love to bring my energy for markets to your team.

Best,
Wei Zhang""",
        roles=[("Manulife", "Finance Co-op", "Sep 2025 - Dec 2025", "ended"),
               ("BMO Capital Markets", "Investment Banking Summer Analyst", "May 2026 - Present", "ongoing")],
        credentials=[("CFA Level I", "planned")],
        stale=["Currently, I am a Finance Co-op at Manulife"],
        keep=["CFA Level I candidate"],
    ),
]


def facts_of(candidate: dict) -> dict:
    """What a correct reading of the candidate's resume gives (cover_letter.read_facts)."""
    return {"roles": [{"employer": e, "title": t, "dates": d} for e, t, d, _ in candidate["roles"]],
            "credentials": [{"name": n, "status": s} for n, s in candidate["credentials"]]}


class LetterCorpusTests(unittest.TestCase):
    def test_role_dates_are_read_in_any_format(self):
        for candidate in CANDIDATES:
            for employer, _, dates, state in candidate["roles"]:
                with self.subTest(candidate=candidate["id"], dates=dates):
                    self.assertEqual(state, resume_facts.role_state(dates, TODAY))
        for dates, state in (("Sept. 2025 – Apr. 2026", "ended"), ("2023-2025", "ended"), ("Winter 2026", "ended"),
                             ("Oct 2026 – Dec 2026", "ongoing"), ("Sep 2025-present", "ongoing"), ("Jan 2026 - Aug 2026", "ended"),
                             ("2022 – 2026", ""), ("Toronto, ON", "")):
            with self.subTest(dates=dates):     # a year ending this year could end any month: no guess
                self.assertEqual(state, resume_facts.role_state(dates, TODAY))

    def test_the_name_is_read_from_any_resume(self):
        for candidate in CANDIDATES:
            with self.subTest(candidate=candidate["id"]):
                self.assertEqual(candidate["name"], letterhead.candidate_name(candidate["resume"]))

    def test_every_past_letter_has_its_greeting_closing_and_date_found(self):
        for candidate in CANDIDATES:
            with self.subTest(candidate=candidate["id"]):
                labels = [label for label, _ in cover_letter.letter_sections(candidate["letter"])[1]]
                self.assertEqual("greeting", labels[0])
                self.assertEqual("closing", labels[-1])
                self.assertIsNotNone(letterhead.header(candidate["letter"])[1])
        # a line that only starts like a greeting, wrapped in a PDF, isn't one
        self.assertIsNone(cover_letter.GREETING.match("to the success of your team."))

    def test_only_facts_the_resume_states_are_kept(self):
        for candidate in CANDIDATES:
            facts = facts_of(candidate)
            invented = {"roles": facts["roles"] + [{"employer": "Morgan Stanley", "title": "Analyst", "dates": "2024"}],
                        "credentials": facts["credentials"] + [{"name": "CFA Charter", "status": "passed"},
                                                               {"name": "Languages", "status": "passed"},  # a heading
                                                               {"name": candidate["credentials"][0][0], "status": "maybe"}]}
            with self.subTest(candidate=candidate["id"]):
                self.assertEqual(facts, resume_facts.checked(invented, candidate["resume"]))

    def test_every_out_of_date_sentence_goes_to_the_check(self):
        for candidate in CANDIDATES:
            items = cover_letter.status_items(candidate["letter"], facts_of(candidate), TODAY)
            for phrase in candidate["stale"]:
                with self.subTest(candidate=candidate["id"], phrase=phrase):
                    self.assertTrue(any(phrase in item["sentence"] for item in items))
            # and a role still held goes as current, so only words that call it over are changed
            current = {e for e, _, _, state in candidate["roles"] if state == "ongoing"}
            self.assertEqual({"ongoing"}, {i["status"] for i in items if i["kind"] == "role" and i["name"] in current}
                             or {"ongoing"}, candidate["id"])

    def test_a_current_role_written_as_ended_is_put_back(self):
        """What qwen3:8b wrote for Wei Zhang, whose BMO role is current: the check says so in its own words."""
        candidate = next(c for c in CANDIDATES if c["id"] == "manulife_stacked")
        sentence = "Having served as an Investment Banking Summer Analyst at BMO Capital Markets, I built trading comparables."
        letter = f"Hi there,\n\n{sentence}\n\nI am a CFA Level I Candidate.\n\nBest,\nWei Zhang"
        current = sentence.replace("Having served as", "Currently serving as")
        replies = [_chat({"answers": [{"n": 1, "presents": "past"}, {"n": 2, "presents": "not passed"}]}),
                   _chat({"changes": [{"part": "1", "text": current}]}), _chat({"answers": [{"n": 1, "presents": "current"}]})]
        with mock.patch("requests.post", side_effect=replies) as post:
            fixed = cover_letter.check_status("qwen3:8b", {}, candidate["resume"], letter, facts_of(candidate), TODAY)
        self.assertEqual(letter.replace(sentence, current), fixed)
        self.assertIn("role at BMO Capital Markets as one that has ended, but it is current (May 2026 - Present)",
                      post.call_args_list[1].kwargs["json"]["messages"][1]["content"])
        # without the model's rewrite, the usual words
        self.assertEqual(current, cover_letter._usual({"kind": "role", "status": "ongoing", "sentence": sentence}))
        # a rewrite that isn't a whole sentence isn't used, as qwen3:8b wrote when Manulife's story went to BMO
        swapped = ("Previously, I was an Investment Banking Summer Analyst at BMO Capital Markets, where I built trading "
                   "comparables for energy clients.")
        letter = f"Hi there,\n\n{swapped}\n\nBest,\nWei Zhang"
        replies = [_chat({"answers": [{"n": 1, "presents": "past"}]}),
                   _chat({"changes": [{"part": "1", "text": swapped.replace("Previously, I was an", "As an")}]}),
                   _chat({"answers": [{"n": 1, "presents": "past"}]})]
        with mock.patch("requests.post", side_effect=replies):
            fixed = cover_letter.check_status("qwen3:8b", {}, candidate["resume"], letter, facts_of(candidate), TODAY)
        self.assertEqual(letter.replace("Previously, I was an", "Currently, I am an"), fixed)

    def test_a_rewrite_that_still_calls_a_passed_exam_a_candidacy_isnt_used(self):
        """What qwen3:8b wrote for Daniel Kim, who has passed CAIA Level I."""
        candidate = next(c for c in CANDIDATES if c["id"] == "gs_current_role")
        sentence = "I am a CAIA Level I candidate, which reflects my commitment to alternative investments."
        letter = f"Dear Recruiting Team,\n\n{sentence}\n\nRespectfully,\nDaniel Kim"
        replies = [_chat({"answers": [{"n": 1, "presents": "not passed"}]}),
                   _chat({"changes": [{"part": "1", "text": sentence.replace("candidate,", "candidate who has passed,")}]}),
                   _chat({"answers": [{"n": 1, "presents": "not passed"}]})]
        with mock.patch("requests.post", side_effect=replies):
            fixed = cover_letter.check_status("qwen3:8b", {}, candidate["resume"], letter, facts_of(candidate), TODAY)
        self.assertEqual(letter.replace("I am a CAIA Level I candidate", "I have passed CAIA Level I"), fixed)

    def test_an_experience_the_model_drops_while_adapting_goes_back_in(self):
        """What qwen3:8b wrote for Wei Zhang: the past letter's Manulife co-op swapped for the BMO role he holds now."""
        candidate = next(c for c in CANDIDATES if c["id"] == "manulife_stacked")
        story = candidate["letter"].replace("Currently, I am a Finance Co-op", "Previously, I was a Finance Co-op")
        opening = "I am excited to apply for the 2027 Investment Banking Summer Analyst role at William Blair."
        bmo = ("Currently, I am an Investment Banking Summer Analyst at BMO Capital Markets, where I built trading "
               "comparables for energy clients.")
        letter = (f"Hi there,\n\n{opening} {bmo} This experience has sharpened my analytical skills.\n\n"
                  "I am a CFA Level I Candidate, sitting the exam in February 2027.\n\nBest,\nWei Zhang")
        manulife = "Previously, I was a Finance Co-op at Manulife, where I automated the monthly expense variance report."
        self.assertEqual(letter.replace(bmo, f"{bmo} {manulife}"),
                         cover_letter.keep_experiences(story, letter, facts_of(candidate)))
        # a letter that still names every company the past letter does is left as it is
        self.assertEqual(story, cover_letter.keep_experiences(story, story, facts_of(candidate)))

    def test_a_sentence_that_lost_its_company_gets_it_back_in_place(self):
        candidate = next(c for c in CANDIDATES if c["id"] == "td_numeric")
        told = ("Having served as a Summer Analyst on the Global Markets desk at TD Securities, I built a Python tool\n"
                "that reconciled 2,000 daily FX trades.")                  # wrapped as a PDF's text is
        story = f"Dear Recruiting Team,\n\nI am applying to your firm. {told}\n\nBest regards,\nMarcus Chen"
        dropped = told.replace(" at TD Securities", "").replace("\n", " ")
        letter = f"Dear Recruiting Team,\n\nI am applying to William Blair. {dropped}\n\nBest regards,\nMarcus Chen"
        self.assertEqual(letter.replace(dropped, " ".join(told.split())),
                         cover_letter.keep_experiences(story, letter, facts_of(candidate)))

    def test_what_the_past_letter_said_to_its_reader_stays_out(self):
        """Olivier Tremblay's past letter applied to Desjardins, where he now works: that sentence was the old posting's."""
        candidate = next(c for c in CANDIDATES if c["id"] == "nbc_year_only")
        letter = ("Dear Hiring Manager,\n\nI am pleased to apply for the role at William Blair. Having served as a Credit "
                  "Analyst Intern at National Bank of Canada, I prepared credit memos.\n\nSincerely,\nOlivier Tremblay")
        self.assertEqual(letter, cover_letter.keep_experiences(candidate["letter"], letter, facts_of(candidate)))

    def test_a_second_salutation_under_the_greeting_is_dropped(self):
        """What qwen3:8b wrote for Hannah O'Brien's 'To the Hiring Committee,' letter."""
        letter = "Hannah O'Brien\n\nTo the Hiring Manager,\n\nHiring Manager,\n\nI am applying for the role.\n\nThank you,\nHannah"
        self.assertEqual("Hannah O'Brien\nOctober 18, 2026\n\nWilliam Blair\n\nTo the Hiring Manager,\n\nI am applying for "
                         "the role.\n\nThank you,\nHannah",
                         letterhead.set_header(letter, ["Hannah O'Brien"], "October 18, 2026", ["William Blair"]))
        # a first line that only ends with a comma stays
        kept = "Dear Hiring Manager,\n\nAs a student,\nI led a team."
        self.assertTrue(letterhead.set_header(kept, ["Hannah O'Brien"], "October 18, 2026", []).endswith("\n" + kept))

    def test_the_facts_for_today_go_to_the_model_for_every_candidate(self):
        for candidate in CANDIDATES:
            prompt = cover_letter.build_prompt({"company": "RBC", "title": "Analyst"}, candidate["resume"],
                                               candidate["letter"], today=TODAY, facts=facts_of(candidate))[1]
            with self.subTest(candidate=candidate["id"]):
                for employer, _, dates, state in candidate["roles"]:
                    line = "Roles that have ended" if state == "ended" else "Current roles"
                    self.assertRegex(prompt, rf"- {line}[^\n]*{employer}[^\n]*\({dates}\)")
                for name, status in candidate["credentials"]:
                    line = {"passed": "Passed", "in progress": "In progress", "planned": "Planned"}[status]
                    self.assertRegex(prompt, rf"- {line}[^\n]*{name.replace('(', '[(]').replace(')', '[)]')}")

    def test_the_usual_phrasings_put_right_what_the_model_leaves(self):
        """The model judges every status wrong and rewrites nothing: the usual phrasings fix the common ones, the
        rest of the letter stays the candidate's, and a planned exam is never called passed."""
        for candidate in CANDIDATES:
            status = dict(candidate["credentials"])

            def reply(url, json=None, **kwargs):
                if json["messages"][0]["content"] != cover_letter.CHECK:
                    return _chat({"changes": []})
                shown = [line.split(": ", 1) for line in json["messages"][1]["content"].splitlines() if line[:1].isdigit()]
                return _chat({"answers": [{"n": n, "presents": "current" if kind.endswith("Role") else
                                           "not passed" if status[name] == "passed" else "passed"}
                                          for n, (kind, name) in enumerate(shown, 1)]})
            with self.subTest(candidate=candidate["id"]), mock.patch("requests.post", side_effect=reply):
                fixed = cover_letter.check_status("qwen3:8b", {"company": "RBC"}, candidate["resume"],
                                                  candidate["letter"], facts_of(candidate), TODAY)
                for phrase in candidate["stale"]:
                    if phrase not in MODEL_ONLY:
                        self.assertNotIn(phrase, fixed)
                for phrase in USUAL[candidate["id"]]:
                    self.assertIn(phrase, fixed)
                for phrase in candidate["keep"]:
                    self.assertIn(phrase, fixed)
                items = cover_letter.status_items(candidate["letter"], facts_of(candidate), TODAY)
                fixable = {i["sentence"] for i in items if i["kind"] == "role" or i["status"] == "passed"}
                for item in items:              # what the letter says about an exam not passed yet stays as it was
                    if item["sentence"] not in fixable:
                        self.assertIn(item["sentence"], fixed)
                self.assertEqual(len(candidate["letter"].split("\n\n")), len(fixed.split("\n\n")))


# What the usual phrasings make of each candidate's out-of-date sentences, and what they say of the work after.
USUAL = {
    "ey_accounting": ["I was previously an Assurance Intern at EY, where I test revenue controls"],
    "td_numeric": ["I previously worked at TD Securities as a Summer Analyst"],
    "deloitte_seasons": ["Previously, I was interning in Financial Advisory at Deloitte"],
    "nbc_year_only": ["I previously worked at National Bank of Canada", "I have passed CFA Level I, and my studies"],
    "scotia_pipes": ["I was previously a Market Risk Analyst Co-op at Scotiabank"],
    "gs_current_role": ["In my previous role at Goldman Sachs", "I have passed CAIA Level I, which reflects"],
    "kpmg_iso": ["I was interning in Tax at KPMG"],
    "manulife_stacked": ["Previously, I was a Finance Co-op at Manulife"],
}
# Out-of-date phrasings only the model's rewrite puts right: no usual pattern knows them.
MODEL_ONLY = {"I am also completing the Canadian Securities Course", "I am working toward the Bloomberg Market Concepts certificate",
              "I am preparing to write the Series 7", "I manage a $45,000 annual budget"}


def _chat(answer):
    response = mock.Mock(status_code=200, ok=True)
    response.json.return_value = {"message": {"role": "assistant", "content": json.dumps(answer)}}
    return response


if __name__ == "__main__":
    unittest.main()
