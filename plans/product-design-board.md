# Product & Design boards: design (Phase 1)

Status: **Phase 4 in progress** (section 13): `canadian_product_design` (35 sources), `design_studios` (34), `industrial_design` (33), `early_career_programs` (7), `big_tech` (2), `consumer_tech` (1), `product_core` (2), `design_core` (2) and the sweep's `enterprise_saas` (2) and T-Mobile are in. You approved the 46 decisions of section 14 (D1–D46) as recommended on 2026-11-07, and the Phase 3 answers on 2026-11-07 and 2026-11-08 (14.7). Branch
`feat/product-design-board`, worktree `.claude/worktrees/product-design-board`, created from `main` at `598b525`
(v0.3.14). The brief is `plans/board-expansion-prompt.md` in the main checkout: Part A, Part B §2 and the lessons
in Part C. Healthcare's design (`plans/healthcare-board.md`) is the model: boards are data (§9 there), so this work
should need data and tests. The few code changes it may need are each a decision of their own (D5, D23, D35, D37
to D39, D43 and D44), and none happens without your yes.

Phase 1 adds no product code. It adds the placement check, the polled-list recorder and the fixture-resume
recorder as tools with tests (section 2.7), records the baselines, and gathers the counts this design rests on.
Scratch work and copies are in `E:\product-design-board\` (section 16 lists them).

**How to read it.** Section 14 lists every decision with its counts and my recommendation, so it can be read on its
own; each row names the section that has the detail. Sections 3 to 11 give the evidence: filters, the title-move
census, levels, track and employers, sources, candidate employers, resumes, views, and the config and robots.txt
checks. Counts are from a copy of your database on E: and from `main`'s own code. "Stored" means every posting, and
"open" means `status != 'closed'`. "(judgement)" marks a call that is not a count.

## Terms

| Your word | Meaning | In the code |
|---|---|---|
| **Board** | A field picked in onboarding: Finance, Software, Product, Design… | `profile.fields`; `non_finance_families` in `config/taxonomy.json` |
| **Source** | One polled feed: a Workday site, a Greenhouse board, a LinkedIn search | an entry of `config["boards"]`; the `board` column in the DB |
| **Filter** | A subcategory inside a board: Product · Technical PM | a target role such as `product.technical_pm` |
| **Pack** | A file of sources | `config/sources/<folder>/<group>.json` |
| **Track** | Boards that share employer types, skills and resume vocabulary: tech = Software, AI & Data, Hardware, Product and Design | `"track"` on a board |

---

## 1. The guarantee

Your rule for this work: no role of another board may land in a different board, filter, company or location, and
none may go missing. Fit and order may change. It is proven two ways:

1. **Polling (a test).** Every board other than Product and Design polls the same sources with the same settings
   (`tests/sources/test_board_polling.py`, pinned to `board_polling_v0_3_11.json`). Sales, Operations and People &
   Legal poll every source, so they gain the new packs and nothing else.
2. **Placement (on your postings).** `python -m tools.board_gate place` computes facts for the same sample of
   stored postings with `main`'s code and with the branch's code on one DB copy. `place-compare` reports every
   change of board, filter, company, employer type or location. Moves into Product and Design are allowed only
   where you approve them (section 14), by `--allow <from>:<to>`. Everything else blocks the commit: any other
   move, a posting that goes missing, and any move from or to "other", which Finance profiles review. Label-only
   changes (a known employer type where it was unknown, the company otherwise the same) are listed apart.

It runs in minutes (section 2.4). The full gate (`snapshot`/`compare`, fit and order, hours) runs only if you
ask for it.

---

## 2. Baseline (recorded before any product edit)

Everything here was read from files, from a command, or from a copy of your database on E:. The copy was taken
through a `mode=ro` connection with SQLite's backup API (`E:\product-design-board\scripts\copy_db.py`). Nothing in
`%LOCALAPPDATA%\Jobwatch` was written.

### 2.1 The install and the copy
- **Version:** 0.3.14 (`instance.json`). DB schema 8. 1,014 sources in the installed `config.json`, 10 of them
  disabled, so 1,004 are polled by the boards that poll everything.
- **Postings:** 410,490 in `jobs` (410,486 with a title). The newest was first seen 2026-10-31 15:32 UTC.
- **Facts are current** (the test `facts_pending` applies, `E:\product-design-board\scripts\check_copy.py`): every
  titled posting has a `job_intel` row with an `input_hash`, `FACTS_VERSION` 11, and fingerprint `5c56de7ad2d6`
  (15,408) or `2ca05a78664b` (395,078), which `LEGACY_FINGERPRINTS` maps to it. 0 stale. So the stored placement
  is `main`'s, and section 2.4 proves it posting by posting on the sample.
- **Your profile:** Software and Hardware (targets Software · Backend, Frontend, Infrastructure, Systems; Hardware ·
  Embedded & Firmware, Robotics & Autonomy). Your resume is on. Neither board is Product or Design.

Stored postings per board today (`field` is Finance when `is_finance`, else the family; `E:\product-design-board\census\census.db`):

| Board | Postings | Open |
|---|---|---|
| other (no board; Finance reviews) | 106,394 | 95,900 |
| Software | 105,538 | 93,225 |
| Finance | 46,332 | 39,025 |
| Healthcare | 44,236 | 43,624 |
| Sales | 26,377 | 22,668 |
| Operations | 20,809 | 18,050 |
| Hardware | 20,376 | 18,684 |
| AI & Data | 18,735 | 16,258 |
| **Product** | **10,387** | **9,011** |
| **Design** | **6,295** | **5,546** |
| People & Legal | 5,007 | 4,346 |

Healthcare counted 6,822 Product and 3,979 Design postings on 294k; the brief asked for this recount.

### 2.2 What changed since the brief
Re-checked against the code at `598b525`:
- About 398k stored postings in "Where things stand": **410,490** now.
- Installs carry no `_` section headers: `tools/build_windows.py` `clean_config` strips them. So the placement
  check reads the installed `config.json` as its source settings, and a pack heading can't type a posting on an
  install the way it can in a checkout.
- **ServiceNow** has no `companies.json` entry (its 1,247 postings are type "Unclassified", section 6.5).
- **SAP**'s SmartRecruiters token is `SAPITBusinessSysteme` (section 11.3).
- Everything else in "Where things stand" and Part B §2 holds: 319 sources each for Product and Design from the
  9 groups named, the title words, types and skill groups, `occupation_beats_finance`, `MIXES` without a P&D
  mix, `FACTS_VERSION` 11, `RULES_VERSION` 3, schema 8, fingerprint `5c56de7ad2d6`.

### 2.3 Tests
Before any edit: `python -m unittest discover` 790 tests OK (105 s); `node --experimental-test-isolation=none --test
web/tests/*.test.js` 116/116. With the Phase 1 tools: 804 tests OK (the 14 new ones are the gate's and the
recorder's) and 116/116 (`E:\product-design-board\baseline_py_tests.txt`, `phase1_py_tests_final.txt`,
`phase1_js_tests_final.txt`).

### 2.4 Placement on `main` (the baseline every later check compares against)
- **Sample** (`ids.json`): 73,863 postings. That is up to 50 at random from each of the 998 sources with stored
  postings, plus all 37,819 postings whose title matches a Product or Design word: `main`'s words, read from
  `main`'s taxonomy (12), and the 58 candidate words in `E:\product-design-board\scripts\candidate_titles.json`
  (plurals and the words the census reads; 68 patterns once repeats are dropped). Seed 0, clock frozen at the
  sample's epoch, 1793463151 (2026-10-31 16:12 UTC).
- **`main`'s placement:** 73,863 of 73,863 placed in 478 s on 6 workers (155 postings/s), with the copy migrated
  by `main`'s `db_migrations` first (`E:\product-design-board\baseline\placed_main.db`, `placed_main.log`).
- **Self-check:** `place --stored` reads the app's own stored facts for the same ids (58 s). `place-compare` of the
  two: missing 0, added 0, moved 0, changed 0, label changes 0, stage changes 0 (`stored_vs_main.txt`). So the
  check's facts are the app's, posting by posting, in every compared field: board, family, category, filter,
  `is_finance`, company key and name, employer type, country, countries, city, cities and location bucket.

### 2.5 Polled sources for each sample profile
A sample profile is what onboarding saves on a first run (`tools/board_gate.py` `sample_profiles`). The new mixes
finance+product, software+product, software+design and product+design are in `MIXES` and in
`test_a_mixed_profile_polls_the_union_of_its_boards`. "Bundle hash" hashes the polled sources' settings as the
packs list them, "Packaged hash" as an install stores them (`clean_config`); both lists are identical source for
source (`polled-compare`).

| Profile | Boards | Sources | By folder | Bundle hash | Packaged hash |
|---|---|---|---|---|---|
| default | finance | 347 | finance 38, shared 309 | `1a3363eaef933c0f` | `bc20951ee09def58` |
| finance | finance | 347 | finance 38, shared 309 | `1a3363eaef933c0f` | `bc20951ee09def58` |
| software | software | 713 | shared 300, tech 413 | `384408b2e846d59c` | `2d215bdd1a94fd29` |
| data_ml | data_ml | 524 | shared 236, tech 288 | `a94546615cd95e7e` | `6e4aaac107859b5f` |
| hardware | hardware | 191 | shared 97, tech 94 | `eddb558e9d2af4a4` | `54d5e4448e179f74` |
| **product** | product | 319 | shared 130, tech 189 | `307abf02da7972b4` | `5f3094df2d5d5f5e` |
| **design** | design | 319 | shared 130, tech 189 | `307abf02da7972b4` | `5f3094df2d5d5f5e` |
| sales | sales | 1,004 | (every enabled source) | `77bf85900d02d6ff` | `01ebdd4b496c0eb7` |
| operations | operations | 1,004 | (every enabled source) | `77bf85900d02d6ff` | `01ebdd4b496c0eb7` |
| people_legal | people_legal | 1,004 | (every enabled source) | `77bf85900d02d6ff` | `01ebdd4b496c0eb7` |
| healthcare | healthcare | 272 | health 219, shared 24, tech 29 | `ee9fdbee859d02d3` | `a7bf79e14fafc7e5` |
| finance+healthcare | finance, healthcare | 595 | finance 38, health 219, shared 309, tech 29 | `ef8a2aa0b8fe8cad` | `962c7fde0f2a21cf` |
| software+healthcare | software, healthcare | 932 | health 219, shared 300, tech 413 | `77fbbb65c818be32` | `82e57c8f41bf6ff4` |
| data_ml+healthcare | data_ml, healthcare | 743 | health 219, shared 236, tech 288 | `085b86821e5a6791` | `0f27c8fb781d5ddf` |
| finance+software | finance, software | 760 | finance 38, shared 309, tech 413 | `0b6788b94cc8fbbf` | `f06c9b4e36cda9b7` |
| finance+sales | finance, sales | 1,004 | (every enabled source) | `77bf85900d02d6ff` | `01ebdd4b496c0eb7` |
| **finance+product** | finance, product | 536 | finance 38, shared 309, tech 189 | `625cfe458f71e203` | `8920a7d7e4a6fa13` |
| **software+product** | software, product | 713 | shared 300, tech 413 | `384408b2e846d59c` | `2d215bdd1a94fd29` |
| **software+design** | software, design | 713 | shared 300, tech 413 | `384408b2e846d59c` | `2d215bdd1a94fd29` |
| **product+design** | product, design | 319 | shared 130, tech 189 | `307abf02da7972b4` | `5f3094df2d5d5f5e` |

Product and Design poll a subset of Software's sources today, so software+product and software+design poll exactly
Software's 713. Saved in full as `E:\product-design-board\baseline\polled_main_bundle.json` and
`polled_main_installed.json`.

### 2.6 Fixture resumes on `main`
`python -m tools.resume_record record` runs `main`'s own `JobwatchService.parse_resume`, as the resume preview does
(`.docx` unwrapped, PDF and text wrapped), with the clock frozen, on the 8 fixture resumes in `main`'s tests:
finance, cover-letter, mixed, CS, nursing, biology, pharmacy and biomedical. Each is read in 6 forms: pasted text,
a PDF with plain fonts, a PDF as LaTeX's fonts encode it, and a Word file in each of the three list layouts. Each
form is read 8 times: with no saved profile, and with each of 7 saved first-run profiles (finance, software,
product, design, healthcare, finance+product, software+design), because the profile a resume proposes starts from
the saved one (the CS resume proposes Hardware and Software alone, and adds them to Product under a Product
profile). That is 8 × 6 × 8 = 384 recordings, each with a hash of the document the parser was given
(`E:\product-design-board\baseline\resumes_main.json`, clock 1793070000, UTC offset −14,400 s).

`main` and this branch record identically: 384 → 384, 0 skipped, "resumes: passed" (`resumes_compare.txt`).

Known bug, recorded as is: **the pharmacy fixture is refused** in all 48 readings ("could not recognize education
and experience or skills"). "Doctor of Pharmacy (PharmD)" sets no education level (`_DEGREES`), so the preview
refuses it, as the brief says of PharmD-only resumes. The recorder keeps what the parser read beside the refusal,
so a change to its roles or skills still shows. Its tests call `parse_resume` directly, so they pass.

### 2.7 The tools (committed with tests)
`tools/board_gate.py` gains four commands next to `snapshot`/`compare`, and `tools/resume_record.py` is new:

- `sample --db <copy> --out <ids.json> [--cap 50] [--seed 0] [--words <checkout>… --board <b>…] [--title <word>…]
  [--title-file <words.json>]` picks the postings: up to `--cap` at random from each source (seeded, by sorted
  source), plus every posting whose title matches the `--board` boards' title words, filter words, claims and
  fallback titles in each `--words` checkout, or a `--title` word. Title words are wrapped by the app's own `fragment`, so they match
  as the classifier does. It saves the ids, the patterns and the clock.
- `place --code <checkout> --db <copy> --config <config.json> --ids <ids.json> --out <placed.db> [--workers 6]`
  runs the checkout's `db_migrations` on the copy, computes facts for the ids with the checkout's `build_facts`
  in worker processes (the gate's `_facts_worker`, clock frozen at the sample's epoch), and records where each
  lands. `place --stored` records the app's stored facts instead. It refuses the installed database (anything
  under `%LOCALAPPDATA%\Jobwatch`), a config that lists no sources, and an existing output. If a worker fails,
  it stops the others and leaves no partial output.
- `place-compare <old> <new> [--board <b>…] [--allow <from>:<to>…] [--samples 8] [--json <file>]` sorts every
  difference into:
  - missing and added postings
  - moves between boards: allowed only by `--allow`, with `*` for any board other than Finance and "other".
    A move from or to Finance or "other" is marked "changes what Finance shows".
  - filter changes on the `--board` boards
  - label changes: a known employer type in place of an unknown one, company key the same, given per board and
    new type
  - other changes of filter, company, employer type or location, where every country and city counts
  - career-stage changes off the `--board` boards, listed without blocking

  It exits 1 on anything not allowed, and it notes when the two sides used different ids or clocks.
- `polled --code <checkout> --config <config.json> --out <file>` and `polled-compare <old> <new> [--expect <profile>]`
  record and compare what every sample profile polls, with both hashes.
- `resume_record record --code <checkout> --out <file> [--only <fixture>,…]` and
  `resume_record compare <old> <new>`. compare exits 1 on a changed reading (key order included), a changed
  document, a missing reading or a new skip.

Tests: `tests/sources/test_board_gate.py` (`PolledTests`, `PlaceTests`, `PlaceCompareTests`) and
`tests/resume/test_resume_record.py`. `MIXES` in `tools/board_gate.py` gains finance+product, software+product,
software+design and product+design, and `tests/sources/test_board_polling.py` now loops over `MIXES`, so the two
lists can't drift apart.

The exact commands of this phase's runs:

```
python -m tools.board_gate sample --db E:/product-design-board/live_copy.db --out E:/product-design-board/baseline/ids.json --words E:/product-design-board/code-main --board product --board design --title-file E:/product-design-board/scripts/candidate_titles.json
python -m tools.board_gate place --code E:/product-design-board/code-main --db E:/product-design-board/live_copy.db --config E:/product-design-board/installed-config/config.json --ids E:/product-design-board/baseline/ids.json --out E:/product-design-board/baseline/placed_main.db --workers 6
python -m tools.board_gate place --stored --db E:/product-design-board/live_copy.db --ids E:/product-design-board/baseline/ids.json --out E:/product-design-board/baseline/placed_stored.db
python -m tools.board_gate place-compare E:/product-design-board/baseline/placed_stored.db E:/product-design-board/baseline/placed_main.db --json E:/product-design-board/baseline/stored_vs_main.json
python -m tools.board_gate polled --code E:/product-design-board/code-main --config E:/product-design-board/code-main/config.json --out E:/product-design-board/baseline/polled_main_bundle.json
python -m tools.board_gate polled --code E:/product-design-board/code-main --config E:/product-design-board/installed-config/config.json --out E:/product-design-board/baseline/polled_main_installed.json
python -m tools.resume_record record --code E:/product-design-board/code-main --out E:/product-design-board/baseline/resumes_main.json
python -m tools.resume_record record --code . --out E:/product-design-board/baseline/resumes_worktree_check.json
python -m tools.resume_record compare E:/product-design-board/baseline/resumes_main.json E:/product-design-board/baseline/resumes_worktree_check.json
```

Each runs from the worktree as `PYTHONUTF8=1 uv run --no-project --with-requirements requirements.txt python -m …`.
The placement and resume runs are in `E:\product-design-board\scripts\rerun_baselines.sh`.
`E:\product-design-board\code-main` is `git archive 598b525`. `installed-config\config.json` is a copy of the
installed `config.json` in a folder of its own, away from any DB copy.

---

## 3. Filters and overlaps

Counts are open postings (`status != 'closed'`) in table `p` of `E:\product-design-board\census\census.db` (366,337
open of 410,486 titled postings), placed by `main` at `598b525`, unless a line says stored. Before counting, each
census re-ran `main`'s `classify` on its own postings and matched the stored placement: 21,725 Product candidates,
12,693 Design candidates and all 4,168 claimed postings, 0 mismatches. "Canonical" drops copies of one job across
sources. The word lists are the censuses' drafts for counting. Phase 3 writes the final patterns, with tests. Every
candidate word was run title-only over all open postings and its hits read (§4.1, §4.2.2). This section's own checks
are `s3_program_evidence.py`, `s3_labq_narrow.py`, `s3_unless_probe.py`, `s3_probes.py`, `s3_content_union.py`,
`s3_kind_landing.py` and `s3_motion.py` in `E:\product-design-board\phase1\plan\scratch\`, each with its `.out.txt`.

### 3.1 How the filters are built

Each filter is a subcategory under `non_finance_families.product.subcategories` or `….design.subcategories` in
`config/taxonomy.json`, written like the tech and Healthcare filters: `label`, `note`, `employer_types` (§6),
`tie_priority`, `related`, `title`, `department`, `description`, and `also_targets` where 3.5 proposes it.

**The board is decided first.** `family_of` reads each board's `title` words, title only, in `_order`: Healthcare,
AI & Data, Software, Hardware, Product, Design, Sales, Operations, People & Legal. AI & Data's and Software's
`domain_title` words (ML, LLM, cybersecurity…) count too, unless the title names a business occupation. Finance is
decided next, and a claim may then move the title (3.5, 3.6). Only after that does `specialty()` (`intel/taxonomy.py`
~110-160) pick a filter, among that board's own filters. So a filter's words never take a posting onto Product or
Design, or off them. Every move in this section comes from a board title word or a claim.

**How `specialty()` picks a filter** (read in `E:\product-design-board\code-main`):
- The title head is the text before the first comma, open parenthesis, colon, pipe, en or em dash, or spaced hyphen
  (`_TITLE_TAIL`). Each title pattern that matches adds 4 in the head and 3 after it.
- Each department pattern adds 2. Description patterns add 1 each, up to 4 (`description_cap`). An employer-type
  prior (`company_priors`, key `product.<filter>`) adds its points but names nothing. The censuses propose no priors.
- Filters sort by what names them: a title word in the head, then a title word after it, then a department word,
  then description words and priors alone. Then by score, then by `tie_priority`.
- A named filter needs a score of 3 (`min_specialty_score`). One read from the description alone needs 4 and a lead
  of 2 over the runner-up. Otherwise the posting stays on the board with no filter.
- Runners-up that score at least 3 and at least half the winner become up to 2 secondary filters.
- In scoring (`intel/scoring.py` ~117-130), a posting in the target filter earns 25 role-fit points, one with no
  filter on the target's board 14, one in a sibling filter 9, and one in a `related` sibling 14.

**Title words.**
- Words are whole words (`fragment` adds word boundaries), so each is written with its plural and -ing forms:
  `managers?`, `designers?`, `researchers?`, `illustrators?`, `program manag(er|ers|ement)`. On `main`, "Product
  Managers" (4 open: Microsoft ×3, Synechron), "Senior Program Managers" (1, Intel) and "Senior Product Designers"
  (1, FIS) sit in "other". Title only, "Product Analysts", "Motion Designers", "Junior Product Designers", "Product
  Designers" @ big_tech and "Graphic Designers" land there too. All go into the classifier tests and the placement
  sample.
- Title words must place a filter alone. LinkedIn postings arrive without a description, and of 5,244 open
  program-manager titles, 2,076 have a description under 200 characters (1,797 have none) and 3,234 have no
  department (`s3_program_evidence.py`).
- A word names the occupation, never only the subject. No board or filter word is bare `products?`, `pms?` (207 of
  its 357 hits sit in "other", nearly all shift times), `apms?` (mostly Application Performance Monitoring), `cpo`,
  `designs?`, `ui`, `creative` or `researchers?` (Quant holds 404 of its 1,235 hits). `tpms?` needs `unless` total
  productive, trusted platform, third party and QA.

**Department words.** Only `technical_pm` has measured ones: `Project/Program/Product Management--Technical` (493
open program titles, Amazon) and `Technical Program Management` (77, and 11 more spelled "Technical Program
Management / Technical Program Management"). "Operations and Supply Chain" (58) and "Business Program Management"
(35) sit on non-technical program titles.

**Description words** only choose among a board's filters, so they can't move a posting between boards. They still
follow Healthcare's rule: a phrase must name the work. "Portfolio" is in 19.4% of open product descriptions (1,175,
mostly a product or investment portfolio, judgement) and 28.2% of design ones (808) (`career_research.md` §5.1), so
it is no description word.

**Claims.** A word that also names another board's roles is never added bare. It becomes a named rule in the board's
`claims`, and each posting the rule moves carries its name in `classification.rule`, so the placement check names
it. The brief asks each claim for evidence: an employer type, a subject in the title that isn't one of its title
words, or 3 description phrases (`min_description`). The claims proposed in 3.5:
- `program_tech_evidence` (B1 of (D2)) has evidence: a tech subject in the title, or 3 tech
  description phrases.
- `pm_over_topic`, `program_over_topic` and Design's `design_occupation` were simulated with no evidence fields, so
  they take on title words alone. Phase 3 adds evidence and recounts their moves (§4.1, §4.2.6).

A claim from "other" or a `fallback_title` word can't place a title that names a designer, product manager or
program manager: both skip what `_other_work` reads as tech or business work. So these occupations stay P&D's own
title words, with exclusions written into the patterns (§4.2.5; the 7 clinical program managers in 3.6 show it).

**`tie_priority` and `related`** (judgement: the censuses set the order, not the numbers). The more specific filter
wins a tie.
- Product: apm_programs 5, technical_pm 4, growth_pm (if kept, D16), product_ops and product_analytics 3, product_management 1.
- Design: design_engineering and industrial_design 5, ux_research and content_design 4, visual_brand 2,
  product_design 1.
- `related`: product_management with technical_pm, apm_programs and growth_pm (if kept); product_design with ux_research,
  content_design and design_engineering.
- Ties are common. "Technical Product Manager" scores 4 in technical_pm and 4 in product_management. "Product
  Management Intern" scores 4 in apm_programs and 4 in product_management.

Every filter gets classifier tests: the examples in 3.2 and 3.3 with their plurals, and the near-misses in 3.2, 3.3,
3.5 and 3.6.

### 3.2 Product's filters

"Today" is `main`'s `classify`, title only, at each employer type where the exact title shows up among open postings
(`census_product_today.py`). The last number in each bracket is the open postings with exactly that title; 0 means
the title isn't stored and was classified at an unknown employer. **Bold** is a title `main` places on another board
or in "other": a move, counted in §4.1 (§4.3 when the other board is Finance).

| Filter | Holds | Title words (sketch) | Example titles (where they show up; open) | Today |
|---|---|---|---|---|
| `product.product_management` · Product Management | Product managers and product owners at any level, and product leaders | `product manag(er\|ers\|ement)`, `products? owners?`, `group product manag(er\|ers)`, `(heads?\|vp\|vice president\|directors?) (of )?products?` unless marketing, design, counsel, engineering, security. Not `chief product officer` (its 2 hits are executive assistants), not executive assistants | Senior Product Manager (big_tech ×29, consumer_tech ×18, enterprise_saas ×13, unknown ×10, cybersecurity ×7, health_tech ×7; 127) · Director of Product Management (semiconductors ×4, robotics_autonomy, gaming; 6) · Product Owner (defense_tech ×4, bulge_bracket ×4, unknown ×3, insurance ×3, canadian_bank ×2, hardware_devices ×2; 22) · Product Managers (1) · Head of Product (0) | Product · Product · **other** at every type (all product-owner titles: other 354, Finance 107) · **other** (plural) · **other** |
| `product.technical_pm` · Technical PM & TPM | Technical product managers, technical and engineering program managers. Plain program managers: D2 | `technical (product\|program) manag(er\|ers\|ement)`, `technical programs?`, `engineering program manag(er\|ers\|ement)`, `tpms?` with its `unless`, `pm ?t`, `(platform\|api\|infrastructure\|cloud\|developer\|data\|ai\|ml\|hardware\|silicon\|devices?\|security\|network(ing)?\|systems?) product manag(er\|ers\|ement)`. Departments as in 3.1 | Technical Program Manager (unknown ×20, semiconductors ×13, big_tech ×11, defense_tech ×9, fintech ×4; 78) · Technical Product Manager (health_tech ×6, hardware_devices ×3, bulge_bracket ×2, defense_tech ×2; 20) · Engineering Program Manager (semiconductors ×6, big_tech ×6; 17) · Technical Program Manager, Infrastructure (unknown ×2, semiconductors; 3) · Senior Product Manager, Cloud Networking (0; Confluent's 12 carry a "Confluent - " prefix) · Sr. TPM – Antenna Development, Amazon Leo (big_tech; 1) | Product · Product · Product · **Software · Infrastructure & DevOps** · **Software · Infrastructure & DevOps** · **other** |
| `product.apm_programs` · APM & Programs | APM and rotational programs, PM internships and co-ops, new-grad PM. Scope: D16 | `associate product manag(er\|ers\|ement)`, `rotational product manag(er\|ers)`, `apm (program\|programs\|interns?\|internships?)`, `product manag(er\|ement) (interns?\|internships?\|co ?ops?\|new grad)`, `products? (interns?\|internships?\|co ?ops?)` unless drug, device, regulatory, tax, `pm interns?`. Not bare `apms?` | Associate Product Manager Intern (unknown ×21, fintech ×2, big_tech ×2; 25) · Associate Product Manager (unknown ×13, medtech ×2, hardware_devices, defense_tech, fintech, pharma; 19) · Product Management Intern (unknown ×75, big_tech ×11, hardware_devices ×9, climate_energy ×8, gaming ×5, global_bank ×4; 119) · Product Management Co-op (unknown ×6; 6) · Rotational Product Manager (0) · Product Intern (unknown ×22; 22) | Product · Product · Product · Product · Product · **other** (all product-intern titles: other 44, Finance 10) |
| `product.growth_pm` · Growth PM. Fold or keep: D16 | Growth, monetization, acquisition and lifecycle PMs | `growth (product\|products\|pms?)`, `monetization`, a product title naming growth or monetization after the separator | Growth Product Manager (data_infrastructure, enterprise_saas, unknown; 3) · Senior Product Manager, Growth (unknown ×2; 2) · Product Manager, Monetization (0) · Growth PM (unknown; 1) · VP of Product, Growth and Monetization (unknown; 1) | Product · Product · Product · **Sales** · **Sales** |
| `product.product_ops` · Product Operations. The move: D4 | Product operations | `product (operations\|ops)` | Product Operations Manager (gaming ×4, unknown ×3, fintech ×2, bulge_bracket; 10) · Product Operations Specialist (fintech, unknown, market_infrastructure, canadian_tech; 4) · Product Operations Intern (unknown ×3; 3) · Head of Product Operations (robotics_autonomy ×2; 2) | **Operations** at every type, for all four |
| `product.product_analytics` · Product Analytics | Product analysts and product analytics, not data scientists | `product analysts?`, `product analytics` unless drug product, `product insights?` | Product Analyst (consumer_tech ×3, insurance, hardware_devices, canadian_tech, enterprise_saas, cybersecurity; 8) · Senior Product Analyst (consumer_tech ×2, unknown, pharma, gaming; 5) · Product Analytics Intern (unknown ×3, health_tech ×2; 5) · Product Analyst, Credit Risk (0) | Product · Product · **other** · **Finance (Risk)** |

Where the filters' draft words reach, title only, over every open posting that names a product word
(`census_product_filters.py`). Hits off Product are not moves (3.1): the moves are in 3.5 and §4.1.

| Filter | Open hits (canonical) | On Product | Elsewhere |
|---|---|---|---|
| product_management | 6,645 (5,642) | 5,163 | Software 717, other 409, Finance 124, AI & Data 82, Hardware 45, Sales 41, Healthcare 35, Operations 15, Design 9, People & Legal 5 |
| technical_pm | 6,003 (5,047) | 4,425 | other 553, Software 534, Finance 188, Hardware 142, Healthcare 58, AI & Data 51, Operations 46, Design 3, Sales 2, People & Legal 1 |
| apm_programs | 628 (346) | 522 | Software 45, other 45, Finance 10, AI & Data 3, Healthcare 3 |
| growth_pm | 169 (150) | 76 | Sales 41, Design 20, Software 11, AI & Data 9, Finance 6, Operations 3, other 3 |
| product_ops | 159 (137) | 16 | Operations 123, Software 6, Sales 5, Design 3, other 3, Finance 2, Hardware 1 |
| product_analytics | 252 (202) | 112 | AI & Data 85, other 30, Finance 17, Software 5, Healthcare 3 |

- The draft technical_pm words include plain `program manag(er|ers|ement)`, so its 4,425 on Product include the plain
  program managers. Plain program-manager titles on Product: 2,049. Strict tech titles (technical, tech, TPM,
  engineering): 1,694.
- **Co-hits** (one title names two filters' words, all open): product_management & technical_pm 769 ("Technical
  Product Manager" ×20, "Senior Technical Product Manager" ×14, "AI Product Manager" ×9); product_management &
  apm_programs 569 ("Product Management Intern" ×118, "Product Manager Intern" ×38, "Associate Product Manager
  Intern" ×25); product_management & growth_pm 74; technical_pm & apm_programs 42; technical_pm & product_ops 12;
  technical_pm & growth_pm 11; product_management & product_ops 10; apm_programs & growth_pm 6; product_management &
  product_analytics 4; growth_pm & product_ops 1; growth_pm & product_analytics 1. `tie_priority` settles them.
- **apm_programs is also a level.** §5 reads an APM or rotational program as New grad ("APM Program") and a bare
  Associate PM as Entry: 53 of 100 open APM titles read Senior on `main`. All four Product program windows in §5
  name `apm_programs`.
- **Near-misses** (title only, `main`; each is a classifier test): "Data Scientist, Product Analytics" @ big_tech ×15
  → AI & Data · Data Science (stays); "Product Marketing Manager" ×62 → Sales; "Product Designer" ×35 → Design;
  "Product Engineer" ×53 → Software; "Product Security Engineer" ×22 → Software · Security; "Product Specialist" ×23
  → other (pharma ×13, medtech ×6); "Product Counsel" ×10 → People & Legal; "Scrum Master" ×24 → other; "Product
  Strategy Intern" ×3 → Finance (Strategy); "Clinical Program Manager" ×4 → Healthcare; "Quality Product Manager" @
  pharma → Product; "Program Manager, Risk" and "Technical Program Manager, Payments Risk" → Finance (Risk), §4.3;
  "Executive Assistant, VP, Product Management" → Product (wrong: 3.5).

### 3.3 Design's filters

"Today" is `classify`, title only, at the employer type shown (`census_design_examples.py`). The number is the open
postings with exactly that title, at any employer. **Bold** is a move, counted in §4.2 (§4.3 for Finance, 3.6 for
Healthcare).

| Filter | Holds | Title words (sketch) | Example titles (employer type; open) | Today |
|---|---|---|---|---|
| `design.product_design` · Product & UX Design | Product, UX, UI, interaction, experience and service design; design systems and design ops; design leaders | `(product\|ux\|ui\|user experience\|user interface\|interaction\|experience\|service) design(ers?)?`, `ux`, `user experience`, `ui/ux`, `ux/ui`, `ui design(ers?)`, `design (systems?\|ops\|operations\|program managers?\|managers?\|directors?\|interns?\|internships?\|co ?ops?)`, `(head\|director\|vp\|manager\|lead) of design`, a leader word before or after design ("Director, Design", "Design Lead"), `human interface design` | Product Designer (big_tech; 35) · Senior UX Designer (enterprise_saas; 13) · Product Design Intern (unknown; 11) · Director, Product Design (commercial_bank; 9) · Experience Design Vice President (bulge_bracket; 7) · Mobile Product Designer (robotics_autonomy; 2) · Product Designer, Cloud Infrastructure (unknown; 1) · Senior Product Designers (unknown; 1) · Senior UI Designer (f/m/d) for medical software products (medtech; 1) | Design · Design · Design · Design · Design · **Software · Mobile** · **Software · Infrastructure & DevOps** · **other** (plural) · **Healthcare** |
| `design.ux_research` · UX Research | UX and user research, usability, quantitative UX research | `ux researchers?`, `user research(ers?)?`, `user experience research(ers?)?`, `design research(ers?)?`. Not bare `researchers?` | UX Researcher (big_tech; 6) · User Experience Research Intern, PhD, Summer 2027 (big_tech; 3) · Design Researcher (consumer_tech; 0) · Staff User Researcher (unknown; 2) · UX Researcher, Quantitative (big_tech; 3) · UX Researcher, Wealth Management (bulge_bracket; 0) | Design · Design · Design · **other** · **Finance (Quant)** · **Finance (Wealth Management)** |
| `design.visual_brand` · Visual, Brand & Motion | Graphic, brand, visual, marketing, communication and motion design; art direction; illustration | `(visual\|graphic\|brand\|motion\|communications?\|marketing\|web\|digital\|packaging) design(ers?)?`, `brand identity`, `art directors?`, `art direction`, `creative (directors?\|leads?)`, `head of creative`, `(brand\|integrated) creative`, `creative direction`, `motion graphics`, `illustrators?` unless technical | Brand Designer (enterprise_saas; 15) · Graphic Designer (unknown; 10) · Motion Designer (consumer_tech; 5) · Creative Director (consumer_tech; 5) · Art Director (consumer_tech; 7) · Illustrator (unknown; 1) · Motion Designers (unknown; 0) | Design · Design · Design · Design · **other** · **other** · **other** (plural) |
| `design.content_design` · Content Design & UX Writing | UX writing, content design, conversation design | `ux (writers?\|writing)`, `ux content writers?`, `content design(ers?)?`, `conversation(al)? design(ers?)?`, `content strateg(y\|ist\|ists)` only with ux or product | Content Designer (big_tech; 2) · UX Writer (fintech; 0) · Conversation Designer (big_tech; 1) · Staff Content Designer, UX Platform (consumer_tech, Etsy; 1) · Staff Conversation and Content Designer, Google Cloud Business Platform (big_tech; 1) | Design · Design · Design · **Software** (stored) · **Software · Infrastructure & DevOps** (stored) |
| `design.design_engineering` · Design Engineering | Design engineers and technologists at software employers who build prototypes and design systems; UX engineers | `ux engineers?`, `design technologists?`, `creative technologists?`, `design engineers?` (only what stays on Design under (D8)) | Design Engineer (developer_tools; 26 at all employers) · UX Engineer (big_tech; 2) · Creative Technologist (consumer_tech; 4) · Design Technologist (big_tech; 0) · Design Engineer (semiconductors; the same 26) | Design · Design · Design · Design · Design (chip work: leaves under (D8)) |
| `design.industrial_design` · Industrial Design | Industrial design, CMF, vehicle exterior and interior design. Not architectural interior design, a licensed trade (§5) | `industrial design(ers?)?`, `cmf design(ers?)?`, `colou?r (and\|&) material design(ers?)?`, `(exterior\|interior) designers?` at vehicle makers. Not bare `cmf`: D14 | Industrial Designer (hardware_devices; 4) · Industrial Design Intern (consumer_tech; 2) · Color & Material Designer (robotics_autonomy; 1) · Senior Exterior Designer (robotics_autonomy; 1) · CMF Designer (hardware_devices; 0) · Product Design Engineer (big_tech; 8) | Design · Design · Design · Design · Design · Design (mechanical work at Apple and Google: Hardware under (D8)) |

Size on Design today, by the census's reading of each title (judgement: ordered regex rules, under 5% noise by its
author's estimate; `census_design\kinds.txt`):

| Filter | Open on Design | Canonical |
|---|---|---|
| product_design | 1,093 | 945 |
| visual_brand | 387 | 341 |
| industrial_design | 82 | 66 |
| ux_research | 58 | 53 |
| content_design | 58 | 54 |
| design_engineering | 33 | 30 |
| no filter: plain "Designer", "Designer Intern" | 96 | 87 |

That is 1,807 design roles in 5,546 open Design postings (4,542 canonical). 3,458 are not design, 214 are borderline
and 67 name nothing. D8, D10, D11 and D12 decide them (§4.2.4-4.2.8).

**Near-misses** that classify as Design today (title only; each is a classifier test): "Instructional Designer" @
university (18 open), "Learning Experience Designer" (5), "Game Designer" @ gaming (1), "CAD Designer" (5), "Network
Designer" @ canadian_tech (2), "Design Recruiter" @ fintech (1), "Creative Arts Therapist" @ hospital (1), "Design
Quality Engineer" @ medtech (5), "Construction Manager - Data Center Design" @ big_tech (0), and "Interior",
"Landscape", "Kitchen", "Floral" and "Fashion Designer" (0 each). Off Design: "Design Systems Engineer" @
enterprise_saas → Software, "UI Engineer" → Software · Frontend (1), "Front End Engineer, Design Systems" → Software ·
Frontend, "Design Verification Engineer" @ semiconductors → Hardware · Chip Design & Verification (80), "Mechanical
Designer" → Hardware (6), "Mechanical Product Design Intern" → Hardware (3), "CMF Engineer" @ hardware_devices →
Software, "Copywriter" @ consumer_tech → other (4 open: other 3, Finance · FinTech 1), "Technical Writer" → other
(41).

§7.5's LinkedIn drafts add two tests (`s3_probes.py`, title only): "Product Design Engineering Intern" is Design
today but mechanical work, so it must not reach `product_design`; "Industrial Engineering Co-op" is "other" today
and must stay off `industrial_design`.

**UX writing and content design vs copy** (`census_design.md` §6, title words, open):

| Title words | Open | Where they land |
|---|---|---|
| `ux (writers?\|writing)` | 9 | Design 9 |
| `content design(ers?)?` | 43 | Design 41, Software 2 |
| `conversation(al)? design(ers?)?` | 13 | Design 13 |
| `content strateg(y\|ist\|ists)` | 36 | other 22, Finance 7, Sales 5, People & Legal 1, Software 1 |
| `content writ(er\|ers\|ing)` | 10 | other 6, Finance 3, Design 1 ("UX Content Writer", Nutanix) |
| `copy ?writ(er\|ers\|ing)` | 30 | other 25, Finance (FinTech) 2, Software 1, Sales 1, Healthcare 1 |
| `content marketing` | 40 | Sales 39, Finance 1 |
| `technical writ(er\|ers\|ing)` | 190 | other 170, Software 17, Hardware 1, Healthcare 1, Finance 1 |

The first three rows are 60 open postings with 51 distinct titles (`s3_content_union.py`): 58 on Design and 2 on
Software, which Software's `platform` took. Copywriters, content writers, content marketers and content strategists
are marketing or editorial work. content_design holds UX writing, content and conversation design, "UX content
writer", and a content strategist only when the title names UX or product (1 in "other"). Copywriting and content
marketing are Sales & Growth's to design. That scope: D14.

### 3.4 Refinements of the starting filters

The brief starts each board with six filters (Part B §2). The censuses propose these changes.

Product's list is one decision, D16:
- **Five kept as they are:** product_management, technical_pm, apm_programs, product_ops and product_analytics.
  product_ops holds what it holds only if its titles move from Operations: D4.
- **growth_pm: fold into product_management, or keep it small.** It holds 76 titles on Product and 3 real growth-PM
  titles on Sales, and 74 of its hits are co-hits with product_management. If it stays, its `tie_priority` sits
  above product_management, and §5.6's `pm_internships` window and §7.2's group list keep it.
- **No product-strategy filter or word.** At banks it is card and deposit strategy, at Google and Disney biz-ops
  (141 open: Finance 56, other 50, Operations 22). Leaving it out keeps 36 Finance, 47 "other" and 22 Operations
  postings where they are.
- **No delivery filter.** `scrum masters?` (96), `agile (coach|coaches|delivery)` (27) and `release managers?` (30)
  are agile delivery and release roles, mostly defense and IT contractors: 117 of them in "other". They stay there.
- **No `program_management` filter.** technical_pm holds technical and engineering program managers. Plain program
  managers: D2.

apm_programs' scope is its own question: programs only, or programs plus every PM internship, co-op and new-grad PM
(the census's draft): D16.

Design's list is D16: six filters, with folds (open title hits, `s3_motion.py` and
`census_design.md` §2):
- Into visual_brand: motion design (`motion designers?` 28, all on Design; `motion graphics?` 14, Design 9 and
  other 5), illustration (`illustrat(or|ors|ion)` 13, 8 in "other") and art direction (`art directors?` 44, 28 in
  "other").
- Into product_design: service design (`service designs?` 6), design ops and design program managers.
- No accessibility filter or word (33 hits: accessibility specialists, DEI and IT accessibility) and no
  human-factors one (3.6).
- content_design as in 3.3 (D14).
- A seventh, `game_design`, exists only if the 107 game, level and narrative designers stay on Design:
  (D12).

### 3.5 Overlaps with other boards' filters

| Overlap | Open postings | Today | Proposed | Moves (open) |
|---|---|---|---|---|
| `product.product_analytics` ↔ `data_ml.analytics` | 252 product-analytics titles: Product 112, AI & Data 85, other 30, Finance 17, Software 5, Healthcare 3 | AI & Data's 85 are data scientists and engineers: "Data Scientist, Product Analytics" ×15 (Meta) → Data Science, "Data Engineer, Product Analytics" ×7, "Senior Product Data Scientist" ×4. Finance's 17 are finance roles (DRW "Risk Product Analyst" ×3). Healthcare's include "Drug Product Analytics" ×2 (CMC lab work) | product_analytics holds analysts only, `unless drug product`. `also_targets: ["data_ml.analytics"]`: D16 | 0 from AI & Data, Finance or Healthcare. 25 of the 30 in "other" ("Product Analytics Intern" ×5) by Product's words, §4.1 |
| Product's PM and program titles ↔ Software, AI & Data and Hardware filters | product_management's draft words: Software 717, AI & Data 82, Hardware 45. technical_pm's: Software 534, Hardware 142, AI & Data 51. apm_programs': Software 45, led by "Software Product Management Intern" and "… (Seattle)" ×8 each | Those boards are checked first. "Product Manager, API Platform" @ Glean → Software · Backend; "Confluent - Senior Product Manager, Cloud Networking" ×12 → Software · Infrastructure & DevOps; "Staff Product Manager, ML Foundations and GenAI" @ Stripe → AI & Data · ML Engineering; "Technical Program Manager-Post Silicon Development" @ AMD → Hardware · Chip Design & Verification | A PM or program occupation beats a topic word, by claims `pm_over_topic` and `program_over_topic` from those three boards, `unless` engineer, developer, scientist, architect, programmer, and with evidence (3.1): D3. False moves to fix: Eulerity "AI Intern, Office of CEO & Head of Product" (7), JPMorgan "Vice President Product Delivery Manager - …" | PM claim: Software 639, AI & Data 81, Hardware 46. The program claim adds Software 420, Hardware 130, AI & Data 40 |
| Design's designers ↔ Software filters | 62 `designer` titles on Software, mostly product designers | "Mobile Product Designer" @ robotics_autonomy → Software · Mobile; "Product Designer, Cloud Infrastructure" → Software · Infrastructure & DevOps; "Staff Content Designer, UX Platform" @ Etsy → Software | Design claim `design_occupation` from Software, AI & Data, Hardware, Healthcare and Finance, `unless` mechanical, electrical, hardware, firmware, FPGA, silicon, PCB, power electronics, asic, digital designer, and with evidence (3.1): D13 (§4.2.6) | Software 31 (23 product and UX designers, 3 UX engineers, 2 content designers, 3 others). Hardware 2, 1 wrong without the asic `unless` (Cisco "ASIC Engineering Digital Designer/ Leader") |
| `design.design_engineering` ↔ `software.frontend` | Frontend 908, 113 with a design word in the title (`ui` 78, `design` 18, `ux` 12, `user experience` 2, `creative` 2, `designer` 1). 0 Design postings match a Frontend title word. "Design Engineer" at software employers on Design: 48 | Frontend's description words already include `design systems?` and responsive design. "UI Engineer" @ enterprise_saas, "Frontend Engineer - Design Systems" @ Mercury (fintech) and ClickHouse "Senior Design Engineer - Design System & Platform UI" → Software · Frontend. "Design Engineer, III" @ GitHub (developer_tools) → Design | Frontend keeps UI and frontend engineers. Design keeps "Design Engineer" at software employers (about half are design engineering, judgement), "UX Engineer", "Design Technologist" and "Creative Technologist". Drop bare `ui`: D10. `also_targets: ["software.frontend"]`: D16 | 0 from Frontend. 3 UX engineers by the claim (row above). Dropping `ui` releases 37 UI programmers from Design: Software 19, other 18 |
| Design ↔ `software.game_dev` | 107 game, level and narrative designers on Design (89 at game studios). 18 game UI artists on Design. Off Design: `animat(or\|ors\|ion)` 145 (115 in "other"), `artists?` 161 (125 in "other") | "Senior Game Designer" @ Epic Games → Design. game_dev's title words name programmers, engineers and technical artists, not designers. "Animator" @ gaming → other | Keep game designers on Design in a `game_design` filter, or release them: D12. Animation, 3D, technical and UI artists and VFX stay off Design | Kept: 0. Released under the draft words: other 94, Operations 1, 12 stay. Game UI artists: other 17, 1 stays |
| Design ↔ Hardware filters (`chip_design`, `electrical`, `embedded_firmware`, `robotics_autonomy`) | On Design: 2,606 engineering "design" titles (chip and IC 1,029, mechanical, electrical and systems 1,031, plain "Design Engineer" 546), 73 mechanical product design engineers, 82 industrial designers. On Hardware: 31 with industrial, CMF or product-design words (10 in Electrical, 21 with no filter), 2 of them industrial | "Design Verification Engineer" @ semiconductors → Hardware · Chip Design & Verification (80), but "Digital Design Engineer" @ semiconductors → Design (9). "Product Design Engineer" @ big_tech → Design (8, Apple and Google), while Amazon's and Boeing's are on Hardware | Industrial, CMF and automotive design stay on Design; `cmf` only as "CMF design(er)" (bare `cmf` hits 9 CMF engineers on Software and 9 craniomaxillofacial sales roles): D14. Engineering "design" titles and mechanical product design engineers go to Hardware: D8. Hardware has no mechanical filter | Under D8's recommended variant (full): Design → Hardware 1,747, Design → Software 672, Software → Hardware 14, Product → Hardware 1. Industrial design: 0. Abbott's and Stripe's industrial titles stay on Hardware |
| Product ↔ Sales | Product marketing 782 (Sales 683). Growth titles 266 (growth marketing on Sales 226) | Product is checked before Sales: "Growth Product Manager" → Product, "Product Marketing Manager" ×62 → Sales. "Growth PM" @ elevenlabs and "VP of Product, Growth and Monetization" → Sales | Product and growth marketing stay Sales. Head, VP and director-of-product words carry `unless marketing`. growth_pm holds growth product managers only | The few growth PMs on Sales move by Product's words (§4.1). Without `unless marketing`, Product's draft words take 49 from Sales, mostly heads and directors of product marketing |
| Design ↔ Sales | 130 Design titles carry a Sales word. 156 Sales titles carry a visual, content or design word | Design is checked before Sales: "Creative Marketing Manager" and "Creative Strategy & Partnership Marketing Intern" ×5 → Design. Sales's 156 are marketing roles ("Content Marketing Manager", "Brand Marketing Intern") | Design takes graphic, brand, visual and motion design, art direction and illustration. Marketing creative goes to Sales or "other", and copywriting (30) and content marketing (40) stay: D10 | Sales → Design 1 (Snap "Art Director, SPECS Marketing"). Design → Sales 62 to 63 when narrowed (marketing creative 44) |
| Product and Design ↔ Operations | Product-operations titles 159 (Operations 123). Program-manager titles 5,244 (Product 3,743, Operations 45). 11 executive assistants on Product | "Product Operations Manager" ×10 → Operations. "Executive Assistant, VP, Product Management (Hybrid)" @ Cisco → Product: Operations' title words name executive assistants, but Product is checked first | D4, D2, D5. Product strategy and biz-ops ("Product Strategy and Operations", Google and Disney: 22 on Operations) get no Product word | `product (operations\|ops)`: Operations 119. Program managers under B1: Product → Operations 1,413, other → Operations 416, Finance → Operations 39, Software → Operations 14. The 11 open executive assistants, once Product's words skip them: Operations 10, Sales 1 (JFrog "Program Manager & Executive Assistant to the SVP of Sales"; `s3_unless_probe.py`). Narrowing Design: Design → Operations 42 to 45 (D8) |
| Product and Design ↔ People & Legal | Product counsel 31 (People & Legal 30). Recruiters and people partners naming Design: 12 on Design. Instructional designers: 119 on Design. Team-name program titles ("Early Career Program Manager"): 33 | "Product Counsel" ×10 → People & Legal. "Staff Recruiter, Design & Specialized Tech" @ Gusto and "People Business Partner, Product & Design" @ Harvey → Design (checked first). "People Program Manager" ×7 → Product | Head and director-of-product words carry `unless counsel`. Recruiters go to People & Legal: D11. Instructional designers leave Design: D11. People program managers follow (D2) | Design → People & Legal 8, Operations 2, other 2 (the 12 recruiters). Without `unless counsel`, Product's draft words take 7 from People & Legal, among them "Director of Product Counsel" @ Atlassian |
| Product ↔ Design | 80 Product postings carry a design word | "Design Program Manager", Instacart "Senior Design Program Manager II", "UX Program Manager" ×2 and "Lead Industrial Design Program Manager" → Product (checked first) | product_design holds design program managers and design ops when Design places them. Head and director-of-product words carry `unless design` | B1, B2 and C of (D2) move Product → Design 36. Without `unless design`, Product's draft words take 15 from Design, 6 of them heads and directors of product design ("Head of Product Design" ×2) |
| Finance | Product: Finance takes 121 program-manager, 20 technical-program, 10 product-analyst and 3 TPM titles despite Product's words. Design: 12 design roles move in from Finance, and 44 move onto Finance when `design` narrows | | §4.3 | §4.3 |

**`also_targets`** (`intel/scoring.py` ~99-102) lets a filter count another board's filter as its own target in
scoring. It moves no posting and adds no board to the profile. `match_resume` and the board views don't follow it, so
the other board's postings show and match only for a profile that also has that board. The two candidates above both
move 0 postings. AI & Data's product-analytics data scientists sit in `data_ml.data_science`, which the first one
doesn't name, so they keep scoring as AI & Data roles. Tests use software+design (in `MIXES`) and a product+data_ml
profile, which `MIXES` lacks today.

### 3.6 Healthcare's claims and title words

Healthcare is first in `_order` and holds the only claims. Two of its five list Product and Design in `from`:
`clinical_occupation` (no evidence) and `lab_quality` (a subject in the title). Both are `sole_occupation`: they skip
a title that names a tech or business occupation (`_TECH_OCCUPATION`, `_BUSINESS_OCCUPATION`).

| Case | Stored (open) | Examples | Proposed |
|---|---|---|---|
| A claim takes a P&D posting today | 1 (1) | "Family Physician - Care by Design" @ Nova Scotia Health (hospital): Design → Healthcare · Clinical Care by `clinical_occupation`. 0 from Product | Correct, unchanged |
| `sole_occupation` keeps the title on P&D | 156 (143): `lab_quality` on Product 84 (72) and on Design 65 (64), `clinical_occupation` on Product 7 (7) | "Quality Program Manager" @ Medtronic (medtech), "Sr. Staff Product Manager, Ads Quality Ranking" @ Pinterest, "Senior Design Quality Engineer" @ Philips (medtech), "Quality Designer Co-op (Summer 2027)" @ Electronic Arts, "(RN) Heart Transplant Program Manager" @ UC San Diego Health, "Pharmacist Program Manager" @ UnitedHealth Group | Unchanged for the other 149. The 7 clinical program managers: D5. A Product `unless` alone sends all 7 to "other" (D2's A) or Operations (B1, C), not Healthcare: there `_other_work` blocks Healthcare's claims and fallback words (`s3_unless_probe.py`) |
| `lab_quality` skips: no subject in the title | 17 (16): Design 16 (15), Product 1 (1) | "Director, Design Quality - Infusion Systems" @ Baxter (medtech), "QA Design Specialist" @ Danaher (diagnostics), "Design Quality Partner" @ Roche (pharma), "Technical Program & Quality Manager (System-in-Package)" @ Apple | Under `narrow`, 11 of the 15 open Design titles fall to "other" (Finance's review), since `lab_quality` doesn't take from "other". Danaher's "QA Design Specialist" goes to Operations, and 3 stay on Design: Zimmer Biomet "Product Design Quality Sr II" and "Sr III", Bayer "Solution Design Manager Quality DevSec O" (`s3_labq_narrow.py`). Part of (D8) |
| The claim's `from` lacks P&D | 38 (38): `life_science_research` on Design 29 and on Product 6, `life_science_regulatory` on Product 3 | "Principal Scientist siRNA Design" @ Roche, "Scientist I, Computational Protein Design" @ Generate Biomedicines, "Senior Quantum Chemistry Product Manager" @ PsiQuantum, "Regulatory Affairs Associate, Product Management" @ Teleflex (medtech) | Don't widen `from`. Narrowing `design` releases the science titles: of the 54 science and molecular design titles on Design, `narrow` sends 15 to Healthcare, 25 to "other" and 14 to Software |
| Claimed postings that broad P&D words would take | 86 stored (a title in both word sets counts twice): `life_science_research` 44 by product words and 25 by design words, `life_science_regulatory` 16, `health_policy` 1 | "Senior Scientist - New Product Development" @ Danaher, "Postdoctoral Researcher" @ McGill, "Associate Program Director, Commercial Regulatory Affairs (CORA)" @ Genentech, "Program Coordinator (Health Policy and Management)" @ Johns Hopkins | P&D takes no bare `products?`, `designs?`, `researchers?` or `program (directors?\|leads?\|coordinators?)`, so all 86 stay. `lab_quality` (3 "Drug Product", 1 "Quality by Design") and `clinical_occupation` (1) still take from P&D |

**Held by Healthcare's title words, not a claim.** Healthcare's "clinical" (71) and "medical" (32) place 103 stored
(98 open) postings whose titles name a P&D occupation:

| Occupation in the title | Stored (open) | Examples |
|---|---|---|
| program manag* | 56 (54) | "NP Clinical Program Manager - Multispecialty …" @ Mount Sinai Health System (hospital), "Clinical Research Program Manager" @ Mass General Brigham (hospital) |
| product manag* | 31 (29) | "Clinical Product Manager for Transcatheter Mitral Valve Therapy (f/m/d)" @ Siemens Healthineers (medtech), "Senior Product Manager - Veeva Clinical Operations" @ Veeva Systems (health_tech) |
| designer | 7 (7) | "Sr. Clinical DB Designer" @ IQVIA (cro_cdmo; 5 of the 7), "Associate Clinical Designer, Orthopedics" @ Johnson & Johnson (pharma) |
| product owner | 6 (5) | "Clinical Data Product Owner" @ Caris Life Sciences (diagnostics), "Medical Affairs Technical Product Owner" @ Johnson & Johnson (pharma) |
| illustrator, UI designer, product analyst | 1 (1) each | "Medical Illustrator, Osmosis" @ RELX, "Senior UI Designer (f/m/d) for medical software products" @ Siemens Healthineers (medtech), "Sr Product Analyst, PLM - Shockwave Medical" @ Johnson & Johnson |

Whether P&D takes any of them: D15.

**The brief's cases, and the tests they become** (`main`, title only, at the type where such titles show up):

| Title | Employer type | `main` places it | Why |
|---|---|---|---|
| Quality Product Manager | pharma | Product | `lab_quality` blocked by `sole_occupation` |
| Product Manager, Quality Systems (GxP) | pharma | Product | the same, though GxP is a subject |
| Quality Product Designer, GMP | pharma | Design | `designer` is a `_TECH_OCCUPATION` |
| Clinical UX Designer | health_tech | Healthcare | Healthcare's title word "clinical", no claim |
| UX Researcher, Clinical Trials | cro_cdmo | Healthcare · Clinical Research | title word "clinical" |
| Nurse Informaticist, Product Design | hospital | Healthcare · Clinical Care | `clinical_occupation` from Design ("product design" is no `_TECH_OCCUPATION`) |
| Design Quality Assurance Specialist, cGMP | pharma | Healthcare · Regulatory & Quality | `lab_quality` from Design |
| Registered Nurse, Design Unit | hospital | Healthcare · Clinical Care | `clinical_occupation` from Design |
| Human Factors Scientist | medtech | Healthcare · Lab Research | `life_science_research` from "other" (medtech employer) |
| Product Owner, Laboratory Quality | diagnostics | other | "product owner" is no Product word on `main`, and `_other_work` blocks the claims. With `products? owners?` (3.2) it moves to Product (§4.1), where `sole_occupation` keeps `lab_quality` off it |

Two rules follow:
- **No human-factors word on Design.** It would place "Human Factors Scientist" on Design before the claim could take
  it from "other". Human-factors titles: 45 open (Software 30, Design 7, other 7, Operations 1), mostly engineers at
  medtech and defense employers. Design keeps "UX and Human Factors Design" through `ux`.
- **`unless drug product` and `unless drug, device, regulatory`** on product_analytics and the product-intern words:
  "Drug Product Analytics" ×2 and J&J's "Onco Drug-Device Combo Products Intern" are lab and regulatory work.

**New packs.** §8's packs add health-adjacent employers (PointClickCare, Dialogue, Maple, Medline). Their PM and
designer titles that say "clinical" or "medical" go to Healthcare by its title words, as in the table above. The two
claims that take from P&D skip any title that names a P&D occupation (`sole_occupation`). Phase 2's title census on
each new source counts what lands where (§8.9).

### 3.7 Filter keys

- **No repeats.** None of the 12 proposed short keys (product_management, technical_pm, apm_programs, growth_pm,
  product_ops, product_analytics, product_design, ux_research, visual_brand, content_design, design_engineering,
  industrial_design) is a filter of any board (Healthcare 9, AI & Data 5, Software 10, Hardware 4), one of Finance's
  12 categories or 49 subcategories, a claim, an employer type, a skill group, a track or a pack group
  (`config_robots_keys_filterkeys.py`; `census_product_today.py` and `census_design_examples.py` agree). Nor are
  product_strategy, program_management, product_owner, motion_illustration, service_design, accessibility,
  design_ops, game_design or design_systems.
- **Alternates that repeat today:** `analytics` (`data_ml.analytics`), `frontend` (`software.frontend`), `strategy`
  (Finance's category), `consulting` (Finance's `strategy.consulting`, an employer type), `product`, `design` and
  `operations` (board names), `game_dev`, `ai_research`, `clinical_research`, `lab_research`, `equity_research` and
  `quant_research`.
- **Repeats with the boards planned next:** Sales plans growth and marketing (product, brand, content), Operations
  project and program management and consulting, People & Legal people analytics. So bare `growth`,
  `program_management`, `brand`, `content` and `analytics` would collide now or later. `growth_pm`, `technical_pm`,
  `visual_brand`, `content_design` and `product_analytics` don't.
- **Shared words:** `ux_research` shares "research" with six keys (equity, quant, economic, clinical, lab, ai). The
  four `*_design` keys share "design" with `hardware.chip_design`. `product_analytics` ~ `data_ml.analytics`,
  `growth_pm` ~ `private_markets.growth_equity`, `product_management` ~ `asset_management`, `portfolio_management`,
  `wealth_management`. A `LIKE '%research%'` script would mix them.
- So scripts, tests, targets and notes use the full `<board>.<filter>` key (`design.ux_research`), as scoring and
  profiles already do (`intel/scoring.py` 67, 122, 132, 156; `intel/profile.py` 140).
- Repeats outside P&D, left as they are: `infrastructure` (Finance's `private_markets.infrastructure` and
  `software.infrastructure`), `fintech`, `robotics_autonomy`, `security`, `public_health`, `accounting`, `markets`,
  `quant` and `hardware`.
- **Pack names.** Two of §8.5's draft packs, `apm_programs` and `industrial_design`, would repeat the filter keys the
  way `public_health` and `security` do today. §8.5 names the pack, and a name like `early_career_programs` avoids
  the repeat.

---

## 4. Title-move census

What was counted:
- **Every title word, on every open posting.** `main`'s six Product and six Design words and every candidate word in
  `E:\product-design-board\scripts\candidate_titles.json` (19 product, 39 design) were run title-only over all
  366,337 open postings (`status != 'closed'`) of the 410,486 titled postings in `census.db` (table `p`). Each word
  is wrapped by `intel.knowledge.fragment` and compiled `re.I`, as the app does, so plurals miss unless written.
- **On `main`'s placement.** The code is `598b525` (`E:\product-design-board\code-main`), and the stored facts are
  current (§2.1), so the stored field is `main`'s.
- **Variants, simulated.** Each variant is a copy of `main`'s config with an edited `taxonomy.json`
  (`phase1\sim\P1`…`P7` for Product, `phase1\census_design\` for Design), classified by `main`'s own `classify` with
  the stored employer type and the department and description from `live_copy.db` (read-only). A move is a posting
  whose field under the variant differs from the stored one, so every move count is exact for the variant simulated.

Self-checks, run before any count:
- Product: `census_product_extract.py` re-placed the 21,725 open postings whose title names a product word or that
  sit on Product. 0 differ from the stored field.
- Design: the 12,693 open postings with a design word. 0 differ (§4.2).
- Finance words (§4.3): 2,153 of 2,153 stored Finance postings with a P&D word, 571 of 571 P&D postings with a
  Finance word, the 447 Finance postings naming a claim word, and 7,067 of 7,067 postings for the `_TECH_OCCUPATION`
  run reproduce the stored placement (`finance_seniority.md`, "Reproduction checks").

Common to 4.1–4.3:
- Counts are open postings. §4.3 writes stored/open, as its report does. "Canonical" counts once a job that several
  sources carry.
- Samples are `source:job_id 'Title' @ Company` or `'Title' @ Company`, drawn with seed 20261031. Readings marked
  "(judgement)" are the census authors' reading of titles, departments and description openings, not counts.
- The word lists, claims and variants are drafts written to count moves. Phase 3 writes the real patterns with
  tests, and the placement check (§1) lists every posting they move.
- Every move into Product or Design, and every move out of Finance or "other", waits for your yes (§12). §14 numbers
  the decisions.
- Scripts and outputs: `E:\product-design-board\phase1\scripts\census_product_*.py`, `census_design_*.py` and
  `finance_seniority_*.py`; outputs in `phase1\census_product_*.txt`, `phase1\census_design\` and `phase1\data\`;
  this section's own checks in `phase1\plan\scratch\s4_check*.py` and `s4c_*.py`, each with its `.out.txt`.

### 4.1 Product

Counted by `E:\product-design-board\phase1\census_product.md`. Its universe is the 21,725 open postings above.

#### 4.1.1 The brief's title moves, at a glance

The variants are in 4.1.3. P2 adds occupation words, P3 a PM claim, P4 a program claim; P7 is P3 with plain program
managers on Operations unless the title or description shows tech work (B1, 4.1.6). P1–P4 move nothing off Product.

| From or to | Into Product: P2 / P3 / P4 / P7 | Out of Product: P5 / P6 / P7 | What moves | See |
|---|---:|---:|---|---|
| Software: technical PM | 64 / 703 / 1,123 / 689 | 0 / 0 / 0 | PM titles that name a Software topic, by the PM claim (639); program titles, by the program claim (420). Words alone move 64 | 4.1.5 |
| AI & Data: product analytics | 0 / 81 / 121 / 81 | 0 / 0 / 0 | Its 85 product-analytics titles are data scientists and engineers and stay. The moves are PM (81) and program (40) titles naming AI, ML or data | 4.1.2, 4.1.5 |
| Hardware | 0 / 46 / 176 / 46 | 0 / 0 / 0 | PM (46) and program (130) titles naming hardware, silicon or robotics. Industrial design is §4.2's | 4.1.5 |
| Sales: product marketing, growth | 49 / 49 / 49 / 48 | 76 / 76 / 76 | In: mostly heads and directors of product marketing, which the exclusions drop; 4 real growth PMs. Product marketing (683 on Sales) stays. Out: sales and marketing program managers | 4.1.4, 4.1.6 |
| Healthcare and its claims | 2 / 2 / 2 / 2 | 0 / 0 / 0 | Claims: 0 either way. The 2 are Pfizer "Drug Product Analytics", wrong | 4.1.9 |
| Finance | 170 / 170 / 170 / 131 | 0 / 0 / 0 | Product owners, bank PMO analysts, product strategy. P5–P7 also send 46 / 34 / 39 Finance postings to Operations. Titles with a Finance word: §4.3 | 4.1.4, §4.3 |
| "other" (Finance reviews) | 1,147 / 1,147 / 1,147 / 731 | 0 / 0 / 0 | `program management` 497 (P2–P4), product owners 354, leads, TPMs, interns, heads of product. P5–P7 send 497 / 312 / 416 to Operations | 4.1.4, 4.1.6 |
| Operations: product ops | 201 / 201 / 201 / 173 | 2,158 / 655 / 1,413 | In: all 123 product-ops titles, and 78 others. Out: plain program managers | 4.1.6, 4.1.8 |
| Design | 15 / 15 / 15 / 14 | 36 / 36 / 36 | In: heads of product design (wrong), product owners. Out: design program managers | 4.1.4, 4.1.6 |
| People & Legal | 7 / 7 / 7 / 7 | 0 / 0 / 0 | Product owners of HR and legal tools; "Director of Product Counsel" (wrong) | 4.1.4 |

Product has 9,011 open postings today (7,603 canonical). It would hold 9,639 under P1, 10,666 under P2, 11,432
under P3, 12,022 under P4, 8,543 under P5, 10,297 under P6 and 9,408 under P7.

#### 4.1.2 Product's words, hit by hit

Each word, title only, over all 366,337 open postings (`census_product_words.py`; six seeded samples and the 12 most
common titles per word and board are in `census_product_words.txt`). Blank is 0.

| Word | Open | Product | Design | Software | AI & Data | Hardware | Sales | Ops | P&L | Health | Finance | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`main`** `product manager` | 4,579 | 3,966 | | 510 | 45 | 28 | | | | 27 | 3 | |
| **`main`** `product management` | 1,359 | 1,202 | | 130 | 12 | 13 | | | | 2 | | |
| **`main`** `product coordinator` | 3 | 3 | | | | | | | | | | |
| **`main`** `program manager` | 4,337 | 3,615 | | 390 | 39 | 119 | | | | 53 | 121 | |
| **`main`** `technical program` | 1,750 | 1,444 | | 197 | 25 | 64 | | | | | 20 | |
| **`main`** `product analyst` | 122 | 110 | | | 1 | | | | | 1 | 10 | |
| `products? (managers?\|management\|owners?\|…\|scientists?)` (25 endings) | 9,064 | 5,297 | 688 | 817 | 148 | 93 | 737 | 159 | 10 | 73 | 362 | 680 |
| `heads? of products?` | 54 | 1 | 3 | 7 | 7 | | 11 | 4 | 1 | | 8 | 12 |
| `vp,? (of )?products?` | 28 | 11 | 2 | 5 | | | 3 | | | | 2 | 5 |
| `chief product officer` | 2 | | | | | | | 2 | | | | |
| `cpo` | 7 | | | | | | | 2 | | | | 5 |
| `apms?` | 18 | 2 | 1 | 8 | | | 1 | | | | 1 | 5 |
| `associate products?` | 155 | 101 | 6 | 17 | 2 | | 4 | 8 | 1 | 2 | 13 | 1 |
| `rotational products?`, `products? rotation(al)?` | 0 | | | | | | | | | | | |
| `programs? (managers?\|management\|leads?\|directors?\|coordinators?\|specialists?\|analysts?\|owners?)` | 5,691 | 3,724 | 3 | 455 | 41 | 131 | 25 | 59 | 16 | 133 | 278 | 826 |
| `technical programs?` | 1,755 | 1,444 | | 198 | 25 | 64 | | 1 | | | 22 | 1 |
| `tpms?` | 123 | 17 | 2 | 37 | | 6 | | 8 | | | 3 | 50 |
| `growth (managers?\|leads?\|pms?\|products?\|marketing\|analysts?\|strateg(y\|ist\|ists)\|hackers?)` | 266 | 12 | 6 | 2 | 5 | | 226 | | | | 15 | |
| `pm interns?` | 1 | | | | | | | | | | | 1 |
| `pms?` | 357 | 2 | | 29 | 2 | 13 | 4 | 20 | 3 | 57 | 20 | 207 |
| `scrum masters?` | 96 | | | 17 | 1 | | 1 | 1 | | | 2 | 74 |
| `agile (coach\|coaches\|delivery)` | 27 | | | 5 | | | | | | | 2 | 20 |
| `release managers?` | 30 | | | 5 | | | | 1 | | | 1 | 23 |
| `products?` (bare) | 15,320 | 5,392 | 791 | 3,593 | 372 | 330 | 969 | 618 | 134 | 235 | 1,044 | 1,842 |

`main`'s words have no hit on Sales, Operations, People & Legal or "other": Product is checked after Healthcare, AI &
Data, Software and Hardware and before the rest (`_order`), so a title with a Product word lands on an earlier
board, on Finance or on Product. Finance's share by word is in §4.3.

The forms and occupation words the drafts use (`census_product_explore.py`):

| Pattern | Open | Where they are today |
|---|---:|---|
| `product managers` (plural) | 4 | other 4: Microsoft "Principal + Senior Product Managers- …" ×3, Synechron "Product Managers" |
| `program managers` (plural) | 2 | Product 1, other 1 (Intel "Senior Program Managers") |
| `program management` | 773 | other 496, Product 115, Finance 62, Software 53, Operations 36, Hardware 6, 1 each Design, AI & Data, Sales, People & Legal, Healthcare |
| `technical programs` (plural) | 5 | Finance 2 (PayPal), Software 1, Operations 1, other 1 |
| `(tech(nical)? )?program mgr` | 11 | Software 4, Product 2, Sales 2, other 2, Hardware 1 |
| `products? owners?` | 565 | other 354, Finance 107, Software 62, AI & Data 14, Operations 6, Hardware 5, Sales 5, Healthcare 5, People & Legal 3, Product 2, Design 2 |
| `associate product manag(er\|ers\|ement)`, `apms?` | 122 | Product 100, Software 12, other 5, Healthcare 2, 1 each Design, Sales, Finance |
| `product (lead\|leads\|leader\|leaders)` | 111 | other 70, Finance 13, Software 13, Healthcare 7, Product 2, Operations 2, 1 each Design, AI & Data, Hardware, People & Legal |
| head, VP or director of product, CPO | 263 | Product 82, other 58, Sales 36, Software 32, Finance 18, AI & Data 15, Operations 9, Design 7, Hardware 3, People & Legal 2, Healthcare 1 |
| `products? (interns?\|internships?\|co ?ops?)` | 58 | other 44, Finance 10, AI & Data 2, Software 1, Healthcare 1 |
| `product (operations\|ops)` | 159 | Operations 123, Product 16, Software 6, Sales 5, Design 3, other 3, Finance 2, Hardware 1 |
| `product analytics` | 89 | AI & Data 50, other 25, Software 5, Finance 5, Product 2, Healthcare 2 |
| `product strateg(y\|ist\|ists)` | 141 | Finance 56, other 50, Operations 22, Sales 5, Software 4, AI & Data 3, Hardware 1 |
| `product specialists?` | 194 | other 91, Finance 37, Healthcare 22, Sales 13, Software 12, Hardware 7, People & Legal 6, Operations 4, Product 2 |
| `product market(ing\|er\|ers)` | 782 | Sales 683, Software 46, AI & Data 15, Finance 15, Hardware 10, Healthcare 6, Product 5, other 2 |
| `product (designers?\|design)` | 735 | Design 675, Hardware 29, Software 20, Product 6, AI & Data 2, Finance 2, other 1 |
| `product (engineers?\|engineering\|development engineers?)` | 873 | Software 763, Hardware 61, AI & Data 14, Design 11, Operations 9, other 6, People & Legal 3, Product 2, Sales 2, Healthcare 2 |
| `product security` | 270 | Software 230, other 27, Hardware 5, Product 4, Finance 2, Design 1, AI & Data 1 |
| `product counsel` | 31 | People & Legal 30, Software 1 |

**One word the census table missed.** The draft word `pm ?t` also matches "PMT", which no main or candidate word
does, so the 21,725 left out 48 open "PMT" titles: other 36, Finance 6, Software 3, Sales 2, AI & Data 1. Most are
Amazon PMs ("Senior PMT-ES, Amazon Aurora" ×3, "Sr. PMT, AWS EC2" ×3); Lockheed's "PMT Analyst - Weekend Shift" ×2
is not product work (`scratch\s4c_overlap2.py`). The variants' counts don't include them. With them, P2 moves 175
Finance postings, not 170 (`s4c_overlap.py`): 5 of the 6 move, all but Amazon "Principal PMT, Accounting Tech,
Accounting ATEAM" (`s4c_pmt_check.py`).

**Plurals ("Title words are whole words").** Title only on `main` (`scratch\s4_check8.py`): "Product Managers"
(unknown, big_tech), "Senior Program Managers" and "Product Analysts" all land in "other". "Technical Program
Managers" @ big_tech lands on Product only because `technical program` needs no word end after "program". Plurals
are tiny in stored postings: 4 + 2 + 5 above. The real gap is the -ment form, `program management` (773). Every
plural goes into the classifier tests, and the placement sample already carries the plural candidate words (§2.4).

**What the hits are** (judgement, from reading the hits; the false hits are in 4.1.11):
- Bare `products?` is unusable: Product Engineer (Software 763), Product Security (230), Product Designer (Design
  675), Product Marketing (Sales 683), Product Specialist (194, mostly pharma and medtech sales support), Product
  Counsel, "Product Development Scientist" (Healthcare), "Product Controller" (Finance).
- `product coordinator`: 1 of its 3 is hospital pharmacy (Children's National "Pharmacy Compliance & Sterile Product
  Coordinator").
- `associate products?`: Associate Product Engineer, Counsel, Marketing and Support. Only "associate product
  manager" is product work.
- `product strateg…`: at banks it is card and deposit strategy ("Credit Product Strategy - AVP", "Wholesale Credit
  Risk Associate - Product Strategy"); at Google and Disney it is biz-ops ("Product Strategy and Operations").
- `product analytics`: Pfizer "Drug Product Analytics" is CMC lab work. Of 252 open product-analytics titles
  (`product analytics|product analysts?|product insights?|product data scien…`: Product 112, AI & Data 85, other 30,
  Finance 17, Software 5, Healthcare 3), AI & Data's 85 are data scientists and engineers ("Data Scientist, Product
  Analytics" ×15 at Meta, "Data Engineer, Product Analytics" ×7, "Senior Product Data Scientist" ×4), which AI &
  Data's `data scientist` and `data engineer` claim first. No variant moves them, and none should (judgement). The 30
  in "other" ("Product Analytics Intern" ×5, "Data Intern - Product Analytics" ×4) are the only take; P2 moves 25.
- `growth …`: 226 of 266 are growth marketing on Sales. "Growth Product Manager" and "Senior Product Manager, Growth"
  are Product today, since Product is checked before Sales. Only growth titles with no PM word sit on Sales.
- `products? (interns?…)`: J&J "Onco Drug-Device Combo Products Intern", "Regulatory Products Intern" and "Tax
  Technology and Transformation Products Intern" are not PM internships. "Product Intern" (22: CoStar 5, Axos Bank
  3, Publicis 3…) mostly is.
- `scrum masters?`, `agile (coach…)`, `release managers?`: agile delivery and release roles, mostly at defense and
  IT contractors in "other" (74, 20, 23). Closer to project delivery than product management. No draft takes them
  (§3.4).
- `program manager` / `program management`: many are operations, defense, supply-chain, facilities, people, sales
  and clinical programs: 4.1.6.

#### 4.1.3 The variants

All are data, run on `main`'s code. Each adds to the one before unless it says otherwise.

| Variant | Product's title words and claims |
|---|---|
| P1 | Today's six with plural and -ment forms: `product manag(er\|ers\|ement)`, `product coordinat(or\|ors)`, `program manag(er\|ers\|ement)`, `technical programs?`, `product analysts?` |
| P2 | P1 + occupation words: `products? owners?`, `product (lead\|leads\|leader\|leaders)`, `(heads?\|vp\|vice president) (of )?products?`, `directors? of products?`, `chief product officers?`, `product (operations\|ops)`, `product strateg(y\|ist\|ists)`, `products? (interns?\|internships?\|co ?ops?)`, `product analytics`, `tpms?`, `growth pms?`, `pm ?t`, `tech program (manag(er\|ers\|ement)\|mgr)`, `program mgr`. No exclusions |
| P3 | P2 + claim `pm_over_topic` from Software, AI & Data and Hardware: product manager, associate PM, owner, lead, head, VP or director of product, CPO, product analyst, growth PM, PM-T; `unless` engineer, developer, scientist, architect, programmer |
| P4 | P3 + claim `program_over_topic` from the same boards: `program manag(er\|ers\|ement)`, `technical programs?`, `tpms?`, `program mgr`; the same `unless` |
| P5 | P3, but plain `program manag(er\|ers\|ement)` becomes an Operations title word. `technical programs?` and `tpms?` stay Product's |
| P6 | P5 + claim `program_tech_evidence` from Operations to Product: a tech subject in the title, a tech-track employer type (18 types), or 3 tech description phrases |
| P7 | P6 without employer types: a tech subject in the title or 3 tech description phrases |

`_claim` refuses any title from "other" that names tech or business work (`_other_work`, `intel/taxonomy.py`
~191-199), and `_BUSINESS_OCCUPATION` names product owners, leads and associates. So Product's occupation words must
be title words: a claim from "other" could not place a product owner, lead or associate.

#### 4.1.4 Moves into Product, by variant and origin

Open postings whose field under the variant differs from the stored one (`census_product_sim_P*.log`, summed in
`scratch\s4a_simtable.py`):

| Origin | P1 | P2 | P3 | P4 | P5 | P6 | P7 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **"other"** (Finance reviews) | 502 | 1,147 | 1,147 | 1,147 | 650 | 835 | 731 |
| **Finance** | 49 | 170 | 170 | 170 | 124 | 136 | 131 |
| Software | 37 | 64 | 703 | 1,123 | 666 | 703 | 689 |
| Operations | 37 | 201 | 201 | 201 | 165 | 181 | 173 |
| AI & Data | 0 | 0 | 81 | 121 | 81 | 81 | 81 |
| Hardware | 0 | 0 | 46 | 176 | 46 | 46 | 46 |
| Sales | 1 | 49 | 49 | 49 | 48 | 48 | 48 |
| Design | 1 | 15 | 15 | 15 | 14 | 14 | 14 |
| People & Legal | 1 | 7 | 7 | 7 | 6 | 7 | 7 |
| Healthcare | 0 | 2 | 2 | 2 | 2 | 2 | 2 |
| **Into Product** | **628** | **1,655** | **2,421** | **3,011** | **1,802** | **2,053** | **1,922** |
| canonical | 419 | 1,287 | 1,964 | 2,507 | 1,554 | 1,747 | 1,649 |

Out of Product, and moves that bypass it (P5–P7 only; P1–P4 move nothing off Product):

| Move | P5 | P6 | P7 |
|---|---:|---:|---:|
| Product → Operations | 2,158 | 655 | 1,413 |
| Product → Sales | 76 | 76 | 76 |
| Product → Design | 36 | 36 | 36 |
| **Out of Product** (canonical) | **2,270** (1,929) | **767** (669) | **1,525** (1,273) |
| "other" → Operations | 497 | 312 | 416 |
| Finance → Operations | 46 | 34 | 39 |
| Software → Operations | 37 | 0 | 14 |
| People & Legal → Operations | 1 | 0 | 0 |

Net change per board: Finance −49 under P1 and −170 under every later variant (P5–P7 by both routes); "other" −502,
then −1,147; Operations −37 (P1), −201 (P2–P4), +2,574 (P5), +820 (P6), +1,709 (P7); Software −37, −64, −703,
−1,123, then −703 (P5, P6, P7); AI & Data −81 from P3 on (−121 under P4); Hardware −46 (−176 under P4); Sales −49
under P2–P4 and +28 under P5–P7; Design −15 under P2–P4 and +22 under P5–P7; People & Legal −1 under P1, then −7;
Healthcare −2 from P2 on.

**P1, plural and -ment forms (628).**
- "other" 502: `program management` 497 (defense_tech 251, semiconductors 73, big_tech 39, hardware_devices 28,
  pharma 23), "Product Managers" 4, "Technical Programs" 1. Lockheed Martin "Program Management Mgr - L5" ×22 and
  "Program Management Stf - E4" ×19, L3Harris "Lead, Program Management" ×14, Docusign "Program Management Intern",
  Apple "Manager, Portfolio & Program Management Office (PMO), Finance Transformation".
- Finance 49 (Investment Banking 22, Risk 8, Corporate Finance 7, Strategy 7, FinTech 4, Public Markets 1):
  `program management` 47, `technical programs` 2. Citi "Program Management Lead Analyst" ×8, JPMorgan "Program
  Management Associate" ×3, Capital One "Manager, CRA Strategy & Program Management", PayPal "Sr Manager, Technical
  Programs".
- Operations 37: Lockheed "Supply Chain - Subcontract Program Management - Level 5", Microsoft "Business Program
  Management, Procurement", Snap "Lead Program Management, SMC Operations", Ford "Supply Chain Program Management & AI
  Tool Creation - Early Career Program, Advanced EV".
- Software 37: Apple "Manager, Engineering Program Management — Customer Systems" and "Engineering Program
  Management Undergrad Internships", Honeywell "Intern Master's - Engineering Program Management". Texas Instruments
  "Program Management Engineer" ×6 is an engineer: wrong.
- Design 1, Sales 1, People & Legal 1: GM "Studio Engineering & Design Project / Program Management", Novartis
  "Associate Director, Marketing Program Management", Uber "Sr Manager, Program Management, People".

**P2, occupation words (+1,027).** By the first word that matches (the per-word split is approximate where words
overlap; the totals are exact):
- **"other" 1,147:** `program management` 497, product owner 354, product lead 70, TPM 50, product strategy 47,
  product intern 44, director of product 31, product analytics 25, head or VP of product 14, PM-T 5, "Product
  Managers" 4, product ops 3, program mgr 2, technical programs 1. Employer types: defense_tech 285, unknown 138,
  pharma 136, big_tech 103, semiconductors 100, bulge_bracket 92.
  - "Product Owner" ×22 (Barclays 4, Manulife 3, GDIT 2, Leidos 2, Motorola Solutions 2, National Bank of Canada 2),
    "Product Intern" ×22, Citi "Citi Commerce, Product Lead" ×4, Bloomberg "Senior Data Management Professional -
    Data Product Owner (Data AI)", hp "SQA Integration TPM".
  - Wrong: J&J "Onco Drug-Device Combo Products Intern".
- **Finance 170** (Strategy 43, FinTech 39, Investment Banking 38, Risk 24, Corporate Finance 9, Public Markets 8,
  Private Markets 3, Markets 3, Wealth 2, Banking 1): product owner 56, `program management` 47, product strategy
  36, product lead 11, product intern 8, head or VP 6, technical programs 2, TPM 1, director of product 1, product
  analytics 1, product ops 1.
  - Barclays "Technical Product Owner" ×5 and "Technical Product Owner, Core Processor - AVP", BMO "Associate Product
    Owner - IVR (Remote)", Morgan Stanley "Product Owner, Quotes & Research (QNR) - Assistant Vice President", Dow Jones
    "Summer 2027 Internship Program – Business & Product Strategy Intern", Fidelity "VP, Product Strategy - Fidelity
    Digital Assets®".
  - Why they move: they sit on Finance only because the title names no board (`family == "other"` lets the
    description and employer prior decide, `is_finance` ~295). Once a Product word names the title, Finance needs a
    Finance title word. Bank product owners and PMO analysts are product and delivery work, but Finance profiles see
    them today; product strategy at banks is closer to Finance's strategy (judgement).
  - 79 of the 170 are also moves of the Finance claim V3 (§4.3.7).
- **Operations 201:** 4.1.8.
- **Software 64:** `program management` 37 (P1's), TPM 11, product lead 5, product owner 5, head or VP 2, director
  2, product analytics 2. Amazon "TPM, Fwd Deployed Engineer, Business Innovation and AI", Citi "Digital S/W
  Engineering Product Lead Analyst, Vice President" ×3. Wrong: RTX "Principal Cybersecurity Engineer – Product Owner"
  and Micron "Total Productive Maintenance (TPM) Engineer".
- **Sales 49:** director of product 15, head or VP 14, product owner 5, product ops 5, product strategy 5, program
  mgr 2, PM-T 1, growth PM 1, `program management` 1. Mostly wrong: "Head of Product Marketing" ×4 (Amplitude,
  Fireworks AI, Float…), "Director of Product Marketing" ×3 (Marvell, QuEra…), "Director, Head of Product Marketing"
  ×3 (Twitch), "Senior Director of Product Marketing" ×2, "Sales Ops Program Mgr" ×2. Real: "Director of Product, AI
  Growth", Amazon "Principal PM-T, Growth, Outbound Communications", ElevenLabs "Growth PM", Duolingo "VP of Product,
  Growth and Monetization". Robinhood's "Staff PM, International Growth & Expansion" stays on Sales under every draft.
- **Design 15:** head or VP 3, product ops 3, director 3, product owner 2, TPM 2, lead 1, `program management` 1.
  - The 6 head and director titles all name design: "Head of Product Design" at Glean, Amplitude and Shield AI,
    "Director of Product Design" at Poshmark and Workiva are design leaders (wrong); Oscar Health "Director of
    Product, Claims Design" is a product role, which `unless design` would also drop.
  - TikTok "Creative Product Operations Intern" ×2, Amazon "Principal TPM, AWS UX Design Team", Abbott "Senior Staff
    Digital Design & Product Owner", Sabre "Lead Product Owner – Agentic API Design & Governance".
- **People & Legal 7:** GSK "Associate Director, Product Owner - SAP HR S4, Strada and Mercans Payroll" and "…,
  Product Owner - Legal Ops", Manulife "People Services AI Product Lead", Brown & Brown "Policy Data Product Owner",
  Uber "Sr Manager, Program Management, People". Wrong: Atlassian "Director of Product Counsel", Citi "Head of Product
  Engineering, HR Total Rewards".
- **Healthcare 2:** Pfizer "Senior Manager, Drug Product Analytics" and "Director - Drug Product Analytics". Wrong.

**P3 and P4** add the claims over topic words: 4.1.5. **P5–P7** are the program-manager options: 4.1.6.

**The exclusions the census proposes were not simulated** (judgement, from reading the hits): head, VP and director of
product `unless` marketing, design, counsel, engineering, security; no `product strateg…`; `product analytics`
`unless drug product`; the product-intern words `unless` drug, device, regulatory, tax; no bare `pm`, `apm`, `cpo` or
`chief product officer`. They drop most of Sales' 49 (the 29 heads and directors), Design's 6 heads and directors,
People & Legal's 2 (Atlassian "Director of Product Counsel", Citi "Head of Product Engineering, HR Total Rewards"),
Healthcare's 2 and product strategy's 105 (Finance 36, "other" 47, Operations 22).
- Without product strategy, P2's Finance moves are 134, not 170 (Investment Banking 36, FinTech 34, Strategy 22, Risk
  20, Corporate Finance 9, Public Markets 7, Markets 3, Wealth 2, Private Markets 1; `scratch\s4c_combined.py`).
- Family title words have no `unless` on `main`: only claims and stage rules carry one (`intel/knowledge.py` ~300-303,
  `family_of` in `intel/taxonomy.py` ~162-184). A suffix exclusion ("Head of Product Marketing") can be a negative
  lookahead inside the pattern. A prefix one ("Executive Assistant, VP, Product Management") needs a pattern anchored
  at the title's start, or a family `unless`, which is a code change in shared `family_of`.

The census recommends adding the words with these exclusions, plus the plurals for correctness (5 postings), and of
the -ment forms only `technical` and `engineering program management`. On the Finance moves it recommends approving
the product owners and TPMs, and leaving product strategy and the banks' PMO analysts on Finance. Those two pull
apart: with B1 (4.1.6) the PMO analysts' plain `program management` titles go to Operations (39), and once any
board's word names them, Finance needs a Finance title word to keep them. Keeping them on Finance means no board
takes plain `program management` (judgement).

**(D1)**

#### 4.1.5 PM and TPM titles over topic words (D3)

**Why Product loses them.** `family_of` checks the boards in `_order`, and Software, AI & Data and Hardware come
before Product. So "Product Manager, API Platform" @ Glean lands on Software · Backend (Software's `platform`),
"Senior Product Manager, Cloud Networking" and "Technical Program Manager, Infrastructure" on Software ·
Infrastructure (title only, `scratch\s4_check8.py`). `_BUSINESS_OCCUPATION` stops only the domain words (Software's
cybersecurity and threat detection, AI & Data's ML, LLM and computer vision), so "Cybersecurity Product Manager" stays
Product (4.1.10).

Product-word titles on those boards (`census_product_filters.py`): PM titles on Software 717, AI & Data 82 and
Hardware 45; program titles on Software 534, Hardware 142 and AI & Data 51. 45 of Software's are "Software Product
Management Intern" titles. See also §3.5.

**PM titles: claim `pm_over_topic` (P3): Software 639, AI & Data 81, Hardware 46 (766 open).**
- Software: IBM "Confluent - Senior Product Manager, Cloud Networking" ×12, DigitalOcean "Staff Product Manager,
  Compute Platform" ×11, "Senior Product Manager, Mobile" ×10 (Mozilla 9, Sentry 1), "Software Product Management
  Intern" ×8 and "… (Seattle)" ×8. Apple "Product Manager - Experimentation Platform", Google "Group Product Manager,
  Agent Platform and Open Source", GitLab "Director of Product Management, Agentic Software Delivery".
- AI & Data: Stripe "Staff Product Manager, ML Foundations and GenAI", Apple "Product Manager, AI/ML - Apple Ads,
  Marketplace", Databricks "Sr. Product Manager, Data Engineering", Magna "Technical Product Manager, AI/ML Products".
- Hardware: Formlabs "Product Manager, Hardware", Hudson River Trading "Senior Hardware Product Manager", Oracle "Lead
  Principal Product Manager - Robotics", Qualcomm "Senior Director, Product Management - Customer Strategy & Solutions
  — Data Center Custom Silicon".
- Wrong: Eulerity "AI Intern, Office of CEO & Head of Product" (7 postings, an AI internship) and JPMorgan "Vice
  President Product Delivery Manager - Data Analytics Platform" ×2 (it matched "Vice President Product").

**Program titles: claim `program_over_topic` (P4 on top): Software 420, Hardware 130, AI & Data 40 (590 open).**
- Dell "Senior Program Manager - AI Infrastructure Services" ×10, Amazon "Technical Infrastructure Program Manager,
  Data Center Planning Delivery" ×6, Oracle "Program Manager - Oracle Cloud Transformation" ×6, Meta "Technical
  Program Manager, ASIC" ×4.
- Google "Technical Program Manager II, Hardware NPI, Google Cloud", AMD "Software Development Program Manager", KLA
  "Technical Program/Project Manager (Software)", Apple "Wireless SoC Silicon Validation Engineering Program Manager",
  Kodiak "Hardware Technical Program Manager", Amazon "Sr Technical Program Manager, AWS Generative AI & ML Servers".

**Words alone** (P1, P2) already move 64 from Software: `program management` 37 and TPM 11 among them, with the two
wrong engineers named in 4.1.4. P1–P4 move nothing from AI & Data or Hardware without a claim.

The occupation is the claim's evidence, so it needs no subject or employer type; its `unless` keeps the engineers.
Each posting it moves carries `pm_over_topic` or `program_over_topic` in `classification.rule`. Software profiles lose
these titles from their Software filters; a Software + Product profile still sees them, on Product.

The census recommends the PM claim (P3), and the program claim (P4) only if the program-manager decision keeps
technical program managers on Product (`technical_pm`). Finance moves none either way.

#### 4.1.6 Program manager (D2)

**How many.** Titles matching `program manag(er|ers|ement)`, `technical programs?`, `tpms?` or `(tech(nical)? )?program
mgr`: **5,244 open (4,385 canonical)** (`census_product_reverse.py`):

| | All | Product | other | Software | Finance | Hardware | Healthcare | Ops | AI & Data | Design | Sales | P&L |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| All | 5,244 | 3,743 | 550 | 486 | 188 | 131 | 54 | 45 | 40 | 3 | 3 | 1 |
| Title names tech¹ | 2,667 | 1,912 | 69 | 464 | 45 | 120 | 6 | 11 | 38 | 2 | | |
| Plain title | 2,577 | 1,831 | 481 | 22 | 143 | 11 | 48 | 34 | 2 | 1 | 3 | 1 |

¹ technical, tech, TPM, engineering program, software, hardware, silicon, ASIC, cloud, infrastructure, platform, data,
AI, ML, IT, systems, security, network, firmware, product(s), device(s).

- On Product, `program manager` places 3,614 postings and `technical program` 122 more: 3,736, 41% of the board's
  9,011.
- By employer group, all 5,244: software tech 2,170, hardware tech 846, unknown 726, defense 664, health and
  education 426, finance-type 288, fintech and quant 124.
- With a strict tech word (technical, tech, TPM, engineering), Product holds 1,694 (big_tech 735, unknown 273,
  semiconductors 133, bulge_bracket 113). Plain program-manager titles on Product: 2,049 (big_tech 525, unknown 315,
  defense_tech 312, semiconductors 210, hardware_devices 89, enterprise_saas 59, hospital 54, medtech 48, fintech 46;
  `scratch\s4_check2.py`).
- Title only on `main`, "Program Manager" @ hospital, @ defense_tech and @ big_tech all land on Product.

**Evidence outside the title is thin.** 2,076 of the 5,244 have a description under 200 characters: 1,732 have no
description in the copy and 344 a shorter one, 65 of them empty, so 1,797 have none (`scratch\s4_check3.py`). 3,234 have no department. Where a department
exists it helps: "Project/Program/Product Management--Technical" 493 (Amazon's), "Technical Program Management" 77
and 11 more as "Technical Program Management / Technical Program Management" (Microsoft's and Anthropic's),
"Operations and Supply Chain" 58 (Apple's), "Business Program Management" 35 (Microsoft's), "Program Management
(P&L)" 28 (Northrop Grumman's), "Customer Experience Program Mgmt" 11, "People : People Business Partners : People
Partners Programs" 9.

Tech evidence for the program titles on Product, "other" and Operations, the first that holds:

| Field | Title word | Tech employer type | 3+ tech description phrases | None |
|---|---:|---:|---:|---|
| Product (3,743) | 1,912 | 996 | 119 | 716: defense 253, health and education 240, unknown 190, finance-type 33 |
| "other" (550) | 69 | 160 | 10 | 311: defense 245, health and education 39, unknown 15, finance-type 12 |
| Operations (45) | 11 | 13 | 2 | 19 |

**A seeded sample of 40** from the 4,338 on Product, "other" and Operations, each read with its department and the
opening of its description (judgement; full lines in `census_product_reverse.txt`):
- **19 technical program management**, all on Product today but 2 in "other" (Applied Materials "Technical
  Project/Program Management III", Amazon "Sr. TPM – Antenna Development, Amazon Leo"): Anthropic "Technical Program
  Manager, Public Sector", Amazon "Senior SAP Technical Program Manager, Amazon Leo", JPMorgan "Lead Technical Program
  Manager" and "… - Enterprise Technology",
  Apple "Engineering Program Manager, Quality Assurance - Customer Systems", Oracle "Lead Principal Technical Program
  Manager" ×3, GitLab "Technical Program Manager" (Office of the CTO), ServiceNow "Technical Program Manager, Forward
  Deployed Engineering- Applied AI", Qualcomm "Customer Program Manager, Staff" (Engineering Services Group). 17 of
  the 19 say Technical, TPM or Engineering in the title; the 2 that don't are JPMorgan "Vice President, Data Lineage
  Program Manager" and Qualcomm's.
- **17 operations-type:** business programs, PMOs, supply chain, defense contracts, facilities, customer support and
  trust & safety. Micron "Global Facilities Senior Program Manager (PMO)", RTX and L3Harris "Material Program
  Manager", Oracle "Program Manager 5" and "Materials Lifecycle Program Manager", Lockheed "Program Management Mgr -
  L5", CACI "Deputy Program Manager", Robinhood "Customer Care, Program Manager", OpenAI "Senior Program Manager,
  Consumer Device Safety Operations".
- **4 other boards' work:** Sales 2 (Microsoft "Sr. Business Program Manager", Oracle "Principal Program Manager" in
  OCI Product Marketing), People 1 (Applied Materials "Internship Program Manager - B4"), Healthcare 1 (Omada Health
  "Senior Program Manager, Health Coaching").
- Employer type is weak evidence: 11 of the 21 non-product ones sit at types P6 counts as tech (Oracle 3, Microsoft
  2, Applied Materials 2, Micron, Robinhood, Benchling, Omada Health), and Waymo and OpenAI are untyped.

**The options** (`census_product_sim.py` P5–P7; each also carries P2's words and P3's PM claim, so the Product totals
include those):

| Option | What changes | Product → Operations | "other" → Operations | Finance → Operations | Other moves | Product after |
|---|---|---:|---:|---:|---|---:|
| **A. Keep** | Nothing | 0 | 0 | 0 | With P1's -ment form: "other" → Product 497, Finance → Product 47, Software → Product 37, Operations → Product 36 | 9,011 + the other decisions |
| **B1. Tech evidence: title subject or 3 tech phrases (P7)** | Plain `program manag…` becomes an Operations word; `program_tech_evidence` takes it back to Product with evidence | 1,413 | 416 | 39 | Product → Sales 76, → Design 36; Software → Operations 14. The claim takes back "other" 81, Software 23, Operations 8, Finance 7, People & Legal 1 | 9,408 |
| B2. As B1, and a tech employer type counts (P6) | | 655 | 312 | 34 | Product → Sales 76, → Design 36. The claim takes back "other" 185, Software 37, Operations 16, Finance 12, People & Legal 1 | 10,297 |
| **C. Plain program manager to Operations (P5)** | No claim; technical programs and TPM stay Product's | 2,158 | 497 | 46 | Product → Sales 76, → Design 36; Software → Operations 37, People & Legal → Operations 1 | 8,543 |

Who moves under each:
- **B1, Product → Operations 1,413** (1,173 canonical): big_tech 347, defense_tech 244, unknown 171, semiconductors
  150, hardware_devices 69, hospital 48, medtech 36, enterprise_saas 32. "Program Manager" ×99, "Senior Program
  Manager" ×40, "Principal Program Manager" ×20, "Material Program Manager" ×14, "Competitive Intelligence Program
  Manager" ×10. Micron "Global Facilities Quality Senior Program Manager", Lam Research "Quality Program Manager",
  Apple "Sr. Strategic Operations Program Manager, iPhone", J&J "Sr Program Manager Aseptic Manufacturing", Roblox
  "Senior Program Manager".
- **B2, Product → Operations 655**: defense_tech 244, unknown 171, hospital 48, medtech 36, university 29. Northrop
  Grumman "Program Manager 3 - OneSat", Leidos "Executive Protection Program Manager", Bruker "Materials Program
  Manager - BNSM", WuXi AppTec "(Senior) Program Manager - Toxicology".
- **C, Product → Operations 2,158** (1,829 canonical): big_tech 623, defense_tech 331, unknown 300, semiconductors
  240. It also sends "Engineering Program Manager" ×17 (Cisco 6, GlobalFoundries 2…), Apple "Engineering Program
  Manager - Camera & Depth" and Medtronic "Engineering Program Manager - Onsite" to Operations, unless `engineering
  program manag…` joins Product's words.
- **"other" → Operations** (all three): Lockheed and L3Harris program-management titles, Sierra Nevada and
  GlobalFoundries "Program Management Intern", CACI "Business Program/Management Analyst".
- **Finance → Operations** (B1 39: Investment Banking 19, Risk 8, Corporate Finance 5, Strategy 4, FinTech 2, Public
  Markets 1): Citi "Program Management Lead Analyst" ×8, "Program Management Intermediate Analyst", "Program
  Management Jr Analyst", JPMorgan "Program Management Associate" ×3, Capital One "Principal Associate, Benefits Plan
  Program Management". They sit on Finance only because the title names no board. Operations lacks
  `occupation_beats_finance`, but these titles carry no Finance word, so it makes no difference.
- **Product → Sales 76** (all three): "Regional Program Manager, Field Sales" ×4, "Sales Enablement Program Manager"
  ×4, Microsoft "Frontier Sales Operations Program Manager", Apple "Program Manager, WW Sales Business
  Transformation", Oracle "Principal Program Manager - OCI Product Marketing".
- **Product → Design 36** (all three): Instacart "Senior Design Program Manager II", "UX Program Manager" ×2, Oracle
  "Principal Program Manager (OCI Site Design)", Apple "Workplace Design Test Fit Program Manager". Wrong: Apple
  "iPhone Product Design Engineering Program Manager (PD EPM)" and "Apple Vision Product Design Engineering Program
  Manager" are engineering program managers.
- **Software → Operations** (B1 14): Texas Instruments "Program Management Engineer" ×6 and Aptiv's. The claim needs
  `unless engineers?`.
- **Taken back by the claim** (B1): Docusign "Program Management Intern", Applied Materials "Technical Project/Program
  Management V (E5)". Wrong: Applied Materials "Non-Technical Project/Program Management II - NPI Field Readiness
  Enablement" (the subject `technical` matches inside "Non-Technical"), FIS "VP, Head of Program Management &
  Strategic Initiatives" (from Finance). Under B2, Lockheed "Supply Chain - Subcontract Program Management - Manager -
  Level 5" comes back because defense_tech counts as a tech type.

Trade-offs:
- **A** keeps the board at 9,011, but about half its program managers are not product work (sample: 21 of 40), so a PM
  student's list fills with defense and facilities programs. Adding `program management` (497 from "other") makes that
  worse.
- **B1** matches the sample best: the title carries almost all the evidence, and descriptions are often empty. The
  simulated subject list is too loose: `products?`, `systems?`, `data` and `it` keep "Product Lifecycle New Product
  Program Manager" and "Supply Chain Systems Program Manager", and `technical` matches "Non-Technical".
- **B2** moves 758 fewer Product postings to Operations than B1 (1,413 − 655), but employer type is weak evidence
  (the sample above).
- **C** is simplest and needs no claim, but loses real technical program managers whose title lacks "technical",
  such as "Engineering Program Manager".
- Every option but A moves postings onto Operations, whose own board session hasn't run. Operations has no
  `occupation_beats_finance`, so program titles with a Finance word stay Finance either way (§4.3).
- The bare-level rule in §5.4 reads every program manager left on Product; this decision sets how many that is.

The census recommends B1 with a tighter subject (technical, tech, TPM, engineering, software, hardware, firmware,
silicon, ASIC, SoC, cloud, infrastructure, AI/ML, data center, network, platform, IT), Amazon's and Microsoft's
departments ("Project/Program/Product Management--Technical", "Technical Program Management") as `department`
evidence, and `unless engineers?`, and not adding bare `program management` to Product. "Non-Technical" needs an
`unless` too (from the P7 sample above). The tighter list was not simulated: Phase 3's placement check gives its
exact moves.

#### 4.1.7 Reverse moves: what leaves Product, and what it keeps

**What leaves.** Only the program-manager options move postings off Product: P5 2,270, P6 767 and P7 1,525 (4.1.6:
Operations, Sales and Design). Beyond them:
- The exclusions in 4.1.11 would send the 11 executive assistants to Operations (10) and Sales (1), and the 7 clinical program managers
  to Healthcare by a Healthcare claim. Not simulated as moves.
- Removing the product alternatives from `_BUSINESS_OCCUPATION` would send 33 to Software, 26 to AI & Data and 7 to
  Healthcare; removing them from `_TECH_OCCUPATION` would send 249 to Finance (4.1.10). Neither is proposed.

**What Product holds today** (9,011 open, 7,603 canonical; `census_product_reverse.txt`):
- By the first of `main`'s words that places it: product manager 3,966, program manager 3,614, product management
  1,196, technical program 122, product analyst 110, product coordinator 3.
- By employer group: software tech 3,497, unknown 1,706, finance-type 1,067, hardware tech 1,004, health and
  education 800, fintech and quant 496, defense 441.

| Flag | Count | Reading |
|---|---:|---|
| Plain program titles: operations, defense, supply-chain and clinical programs among them | 2,049 plain; 716 of the 3,743 program titles show no tech evidence | 4.1.6 |
| Program or product title with a non-tech context word | 887 (program manager 644, product manager 192, product management 40, technical program 6, product analyst 5) | "People Program Manager" ×7, "Supply Chain Program Manager" ×6, "Manufacturing Program Manager" ×5, "Program Manager, Data Center Construction" ×5. "Product Manager, Employee Experience & Productivity" ×9 is real PM. These follow 4.1.6 |
| Product-word title at a finance-type employer | 885 (bulge_bracket 402, commercial_bank 250, market_infrastructure 84, canadian_bank 56, asset_manager 45, insurance 19, global_bank 14…) | Bank product management: "Product Manager - Funds" ×3, "Senior Product Manager-Capital Management and Lending" ×3, Citi "Technology Product Management Senior Analyst - Assistant Vice President" ×7. Mostly genuine product management of banking products or bank tech (judgement), so they stay. Moving them back would undo `occupation_beats_finance` |
| Finance word in a Product title | 550 (finance-type 312, software tech 95, fintech and quant 87) | The same jobs. 249 are held off Finance only by `_TECH_OCCUPATION` (4.1.10, §4.3.3) |
| Pharmacy, sterile, legal or paralegal context | 21 | Mostly real PMs of pharmacy or legal products (Amazon Pharmacy, GSK "Director, Product Manager - Legal"). Clear non-product: Children's National "Pharmacy Compliance & Sterile Product Coordinator", Fidelity "Associate Legal Paralegal/Product Manager" |
| Executive assistants | 11 | 4.1.11 |
| Clinical program managers | 7 | 4.1.11 |

#### 4.1.8 Product ops from Operations (D4)

- 159 open product-ops titles: Operations 123, Product 16, Software 6, Sales 5, Design 3, other 3, Finance 2,
  Hardware 1. Title only on `main`, "Product Operations Manager" lands on Operations at every type (Operations'
  `operations`).
- P2's words move all 123 Operations ones (`scratch\s4_check5.py`, 123 of 123). The census attributes 119 to
  `product (operations|ops)` and the rest to a word earlier in the list ("Head of Product Operations").
  - "Product Operations Manager" ×10 (Twitch 4, Brex 2, JPMorgan, Checkr, Datadog, Notion), "Senior Product
    Operations Manager" ×6, "2027 Summer Internship - Product Operations" ×4, "Product Operations Specialist" ×4,
    "Product Operations Coordinator" ×4, "Product Operations & GTM Manager" ×3 (Fiserv).
  - Anduril "Product Operations Manager, Maritime", Ramp "Product Operations Specialist | Procurement", Mastercard
    "Specialist, Product Operations", Harvey "Senior Product Operations Manager, Integrations", "Head of Product
    Operations" (Ford, Zipline).
- P2 moves 78 more from Operations by other words: `program management` 36 (L3Harris and Lockheed supply-chain
  subcontract programs: wrong, and they stay on Operations under B1 and C), product strategy 22 (Google and Disney
  "Product Strategy and Operations Principal": biz-ops, dropped with product strategy), TPM 8 (Abbott "TPM QA
  Director" and "TPM QA Associate Director", Deutsche Bank "TPM Assessments Operations Expert" ×2: wrong; Amazon "Sr.
  Operations TPM, Leo Electronic Supply Chain": right), product owner 6, head or VP 4, lead 2, CPO 2 (executive
  assistants: wrong), PM-T 1 (Amazon "Principal PM-T, Customer Success Intelligence Team"), technical programs 1.
- The product_ops filter is these titles: 16 product-ops postings sit on Product today. The census recommends the
  move. Operations' own session hasn't run.

#### 4.1.9 Healthcare's claims

Open postings a Healthcare claim placed, and how many name a product or program word (`census.db`,
`scratch\s4_check2.py`):

| Claim | Placed | With `products?` or `programs?` | What they are |
|---|---:|---:|---|
| `clinical_occupation` | 292 | 0 | |
| `lab_quality` | 64 | 3 | QC and QA leads for "Drug Product" or "Sterile Product Manufacturing" (Nurix, Lonza, Biogen) |
| `life_science_research` | 3,336 | 49 | Scientists in "Product Development", Genentech "Product Technical Development" interns |
| `life_science_regulatory` | 387 | 16 | Regulatory affairs for "Biological products", IQVIA "Associate Program Director, Regulatory Affairs" |
| `health_policy` | 22 | 2 | Johns Hopkins "Program Coordinator / Sr. Program Officer (Health Policy …)" |

- None names a PM occupation (`product manag…`, owner, lead, analyst or `program manag…`: 0), so Healthcare's claims
  move **0** postings either way.
- "Quality Product Manager" @ pharma, @ medtech and @ unknown stays **Product**: `lab_quality` is `sole_occupation`,
  and the title names a product manager.
- The PMs on Healthcare come from its tier-1 title words, not claims: `product manager` 27, `program manager` 53 and
  `product management` 2 open hits sit there (Veeva "Product Manager - Vault Medical Connections", Flatiron "Lead
  Product Manager (Clinical Workflows)", "Clinical Program Manager"). They stay, as Healthcare's design says; §3.6
  lists all 103 stored and asks whether P&D takes any.
- P2's 2 Healthcare moves are Pfizer's "Drug Product Analytics", wrong (`unless drug product`).
- The 7 clinical program managers on Product: 4.1.11. Adding words to `_BUSINESS_OCCUPATION` would take 16 product
  specialists off Healthcare: 4.1.10.

#### 4.1.10 Shared code: `_TECH_OCCUPATION` and `_BUSINESS_OCCUPATION` (D7)

`census_product_shared.py` swapped the two module regexes in-process (`code-main` unedited) and re-classified the
candidate table, on `main`'s config and on P2's. Both are read only as `bool(search(title))`, so a posting can move
only when that bool changes; the script classified exactly those titles before and after.

**What they do today** (`intel/taxonomy.py`):
- `_BUSINESS_OCCUPATION` (~60-63: `product (manag…|owner|associate|analyst|lead|marketing)`, `program manag…`, sales,
  recruit…) is read in `family_of` (~162-184) and in `_other_occupation` / `_other_work` (~186-194). A title that
  names one:
  1. skips the domain words, so "Cybersecurity Product Manager" stays Product;
  2. stays Software when a Software title word matches, instead of `_software_or_hardware` making embedded or firmware
     titles Hardware;
  3. is skipped by Healthcare's `sole_occupation` claims and by the tier-2 fallback words, so "RN Program Manager"
     stays Product.
- `_TECH_OCCUPATION` (~20-24: `product (manag(er|ement)|coordinat(or|ion))`, engineer, developer, architect,
  designer…) is read at ~284. For a board with `occupation_beats_finance`, a match turns off Finance's title signal,
  so "Senior Product Manager, Payments" stays Product. It names no program manager, TPM, product owner or product
  analyst, and misses plurals ("managers").

**What depends on them** (removal edits; `main`'s config):

| Edit | Titles whose result changes | Moves |
|---|---:|---|
| Drop `product (…)` and `program manag…` from `_BUSINESS_OCCUPATION` | 11,508 | **139**: Software → Hardware 45 ("BMC Firmware Program Manager for AI Servers" ×3, "Staff Product Manager, Embedded" ×2), Product → Software 33 ("Cybersecurity Product Manager - AI & Security Operations" ×3, Mastercard "Product Manager, Payment Threat Intelligence" ×2), Product → AI & Data 26 ("Engineering Program Manager (ANE/ML/AI), Video Engineering" ×3), other → Healthcare 15 (GSK and Regeneron oncology program management), Product → Healthcare 7 (the clinical program managers), Software → AI & Data 6, Finance → AI & Data 3 (JPMorgan "Product Owner - AI and Large Language Models (LLM) - Associate"), other → Software 2, Finance → Software 1, other → AI & Data 1 |
| Drop only `product (manag…\|owner\|associate\|analyst\|lead)` | 6,602 | 65: Product → Software 22, Software → Hardware 18, Product → AI & Data 10, other → Healthcare 5, Software → AI & Data 4, Finance → AI & Data 3, other → Software 1, Finance → Software 1, other → AI & Data 1 |
| Drop `product (manager\|management\|coordinator)` from `_TECH_OCCUPATION` | 5,745 | **259 to Finance**: Product → Finance 249 (Risk 65, Banking 40, Markets 32, Wealth 31, Corporate Finance 30, Public Markets 21, Insurance 12, Private Markets 10, Investment Banking 8; Coinbase "Group Product Manager, Compliance Agent Experience", "Senior Product Manager-Capital Management and Lending" ×3), Software → Finance 10 (PayPal "Lead Product Manager, Risk Decisioning Platform – Data") |

So 249 Product postings stay off Finance only because of `_TECH_OCCUPATION`, and 66 (33 + 26 + 7) sit on Product
rather than Software, AI & Data or Healthcare because of `_BUSINESS_OCCUPATION`.

**Edits that would help Product:**

| Edit | Config | Titles changed | Moves |
|---|---|---:|---|
| Plurals `product manag(ers?\|ement)`, `coordinat(ors?\|ion)` in `_TECH_OCCUPATION` | `main` / P2 | 4 | 0 / 0 |
| + `program manag…`, `technical programs?`, `tpms?` in `_TECH_OCCUPATION` | `main` | 4,803 | Finance → Product **120** (Risk 73, Corporate Finance 15, Markets 13, Investment Banking 7, Wealth 5, Banking 4, Insurance 2, Public Markets 1); Finance → Healthcare 1, Finance → Software 1 |
| the same | P2 | 4,803 | Finance → Product **136** (Risk 81, Markets 16, Corporate Finance 15, Investment Banking 9, Banking 6, Wealth 5, Insurance 2, Public Markets 2); Finance → Healthcare 1, Finance → Software 1 |
| + `product (owners?\|analysts?)` in `_TECH_OCCUPATION` | `main` | 650 | Finance → Product 10 (DRW "Risk Product Analyst" ×3, BofA "Treasury Product Analyst - Payments") |
| the same | P2 | 650 | Finance → Product **57** (Wealth 16, Risk 13, Markets 10, Corporate Finance 6, Insurance 3, Quant 3…) |
| + `product (operations\|ops\|strategy\|specialist)`, `tpms?`, `technical programs?` in `_BUSINESS_OCCUPATION` | `main` and P2 | 452 | 19: **Healthcare → other 16** (Medtronic "Senior Product Specialist Robotic Surgical Technologies Iberia", Merck "Product Specialist, Vaccines (Kuching Based)": Healthcare's tier-2 fallback is then refused), Hardware → Software 3 (Amazon "Senior TPM - Embedded Software, Amazon Leo") |

- The program-manager Finance take (`main`): "Program Manager, People Risk & Assurance" ×5, Meta "Product Risk Program
  Manager" ×4, Google "Senior Energy Markets Program Manager" ×4, "Global Mobility Program Manager, Tax" ×3, JPMorgan
  "Lead Technical Program Manager - Risk Technology" ×3, "Compliance Program Manager" ×3, Citi "Wealth Growth Program
  Manager | West Coast", Robinhood "Futures Risk Program Manager". Only the technical ones are product roles
  (judgement); compliance and risk program managers are Finance Risk's compliance work, tax mobility is HR and wealth
  growth is sales. A code edit can't tell them apart; a claim with title words can (§4.3).
- **Sales and Operations: 0 moves in all 7 edits, on either config.** They have no `occupation_beats_finance`, so
  `_TECH_OCCUPATION`'s Finance gate never applies to them; their title words have no domain words for
  `_BUSINESS_OCCUPATION` to skip; and product-marketing and product-operations titles keep their board. The edits
  that would move them are to `_BUSINESS_OCCUPATION`'s other words (marketing, sales, customer success, recruit…),
  which no one proposes. The brief's "A code edit changes Sales and Operations too" doesn't hold for these edits.
- The edits do move Healthcare (−16 by the additions, +22 by the removals), Software, AI & Data, Hardware and Finance.
- `classify` also runs on resume lines (`intel/resume.py` ~495, `intel/resume_insights.py` ~177 and ~216), so any
  edit also changes resume parses. Not measured.

Both censuses recommend data only: keep `_BUSINESS_OCCUPATION` as it is (its product words keep 66 PMs on Product,
and adding to it costs Healthcare 16), and take the technical program titles on Finance with a Product claim
`"from": ["finance"]` (§4.3), not a `_TECH_OCCUPATION` edit.

#### 4.1.11 False hits, and titles Product holds that aren't product work (D5)

**Words to leave out** (from reading every hit; `census_product_words.txt`):
- **Bare `pms?`** (357): 207 sit in "other", nearly all shift times ("Material Handler I USA (D Crew/PM Shift)",
  "6:00 PM – 6:00 AM"), and Healthcare's 57 are weekend lab shifts, RN shifts and PM&R ("Physiatrist - Brain
  Rehabilitation (PM&R- …)"). On Finance, "PM" is often a portfolio manager ("Associate, Core PM - Fundamental
  Equities", "Junior Quant - PM Analytics"). Only `pm ?t` (Amazon's PM-T) and `pm interns?` read as product.
- **`apms?`** (18): Application Performance Monitoring (Datadog "Staff Product Designer, APM", Amazon "Software
  Development Engineer, APM Insights" ×2 and "…, Amazon, APM Twitch" ×4), asset performance management, J&J "Field
  APM", BD "Regional Director, Sales (APM)", Amazon "Senior Financial Analyst, APM Stores Verticals" (Finance), Sanofi
  "Customer Experience Specialist (APM Vacunas)". One real APM title: Salesforce "Associate Product Manager Intern
  (APM)". Use `associate product manag(er|ers|ement)`.
- **`cpo`** (7): GSK "Director, Privacy Operations R&D and CPO" and "CPO Capability Director", RTX "Chief Product
  Owner (CPO)" ×2, ServiceNow "Office of the COO/CPO", Headway "Executive Assistant to the CPO & CTO".
  **`chief product officer`** (2): both executive assistants (Uber, Western Digital), on Operations.
- **Head of Product Marketing.** The draft head, VP and director-of-product words take 29 Sales postings, nearly all
  product marketing ("Head of Product Marketing" ×4, "Director of Product Marketing" ×3, "Director, Head of Product
  Marketing" ×3), and 6 heads and directors of product design from Design. They need `unless` marketing, design,
  counsel, engineering and security. Eulerity's "AI Intern, Office of CEO & Head of Product" (7) is an AI internship.
- **`tpms?`** needs `unless` total productive, trusted platform, third party and QA: Micron "Total Productive
  Maintenance (TPM) Engineer", RTX "Total Productive Maintenance (TPM) Manager (Onsite)" ×2, "MGR,TPM(Total Productive
  Management)", Deutsche Bank "TPM Assessments Operations Expert", Abbott "TPM QA Director" (third-party
  manufacturing), "Facilities Technical Project Manager (TPM)" ×2. 35 of its 50 in "other" are at big_tech employers
  (Amazon 31), and those are technical program managers.
- Also left out: `product strateg…`, `product specialists?`, bare `products?`, `scrum masters?`, `agile …`, `release
  managers?` (4.1.2).

**Titles on Product today that aren't product work:**
- **Executive assistants: 11** (Cisco 7, Crusoe 2, JFrog 1, Unity 1). Cisco "Executive Assistant, VP, Product
  Management (Hybrid)" and "Executive Assistant: VP, Customer Experience Product Management (Hybrid)" ×3, Crusoe
  "Executive Assistant, Product Management" ×2, JFrog "Program Manager & Executive Assistant to the SVP of Sales",
  Unity "Project/ Program Manager (NonTech) Executive Assistant". Title only, "Executive Assistant, VP, Product
  Management" @ big_tech lands on Product and "Executive Assistant" on Operations. Operations' words name executive
  assistants (`(administrative|office|executive|clerical) (assistant|support|coordinator)`, `_SUPPORT_OCCUPATION`),
  but Product's `product management` matches first. Excluded from Product's words (4.1.4, how), 10 land on
  Operations and JFrog's on Sales (§3.2).
- **Clinical program managers: 7.** Nationwide Children's "RN Program Manager Abdominal Transplant", Stanford Health
  Care "Program Manager (RN), Cancer Destination Service Line", UC San Diego Health "(RN) Heart Transplant Program
  Manager" and "(RN) Lung Transplant Program Manager", Atlantic Health "RN Program Manager, Women's Health", TELUS
  "Bilingual Senior Program Manager - Nurse Practitioner Team Lead", UnitedHealth Group "Pharmacist Program Manager".
  - They sit on Product because `program manag…` is a `_BUSINESS_OCCUPATION`, so Healthcare's `sole_occupation` claim
    `clinical_occupation` skips them. Title only, "RN Program Manager" @ hospital lands on Product.
  - Excluding them from Product's words alone sends them to "other" (option A) or Operations (B1, C), not Healthcare:
    `_claim` and the tier-2 fallback both refuse a title from "other" that names business work, and
    `clinical_occupation` is `sole_occupation` (`intel/taxonomy.py` ~196-212, ~309-317). So the fix is a Healthcare
    claim that takes a nurse, NP or pharmacist program title from Product, not shared code. Dropping `program manag…`
    from `_BUSINESS_OCCUPATION` also moves them (4.1.10), with 132 other moves.
- **Two more:** Children's National "Pharmacy Compliance & Sterile Product Coordinator" (hospital pharmacy) and
  Fidelity "Associate Legal Paralegal/Product Manager" (4.1.7).

The census recommends leaving the words above out, excluding the executive assistants from Product's words, and
sending the RN program managers to Healthcare. It names a Healthcare claim change or a Product `unless` for RN and
nurse; by the reading above, only the Healthcare claim gets them there.

### 4.2 Design

Counted by `E:\product-design-board\phase1\census_design.md` and its scripts (`phase1\scripts\census_design_*.py`,
outputs in `phase1\census_design\`). Every count is of **open** postings (`status != 'closed'`, 366,337 of the 410,486
titled postings in `census.db`), title only, unless a line says otherwise. "Canonical" counts a posting that several
sources carry once. Samples are `source:job_id 'Title' @ Company [employer type]`, or a title and its employer.

- **Universe.** 12,693 open postings whose title carries one of `main`'s 6 Design words or one of the 39 design words
  in `E:\product-design-board\scripts\candidate_titles.json` (`ux` and `ui` are in both lists, so 43 words in all).
  Each word is wrapped by `intel.knowledge.fragment` and compiled `re.I`, as the app does.
- **Placement is `main`'s.** `classify` from `code-main` (`598b525`) re-placed all 12,693 with the stored employer
  type and the department and description from `live_copy.db` (read-only). Unchanged, it reproduces the stored field
  for all 12,693 (0 differ, `sim.txt` line 1). So every move below is a move against what `main` stores, and an exact
  count for the variant simulated.
- **Kinds are judgement.** Whether a title is a design role comes from ordered regex rules the census author wrote
  after reading the hits (`census_design_kinds.py`), not from the app. The author puts the noise below 5% (judgement).
  Known noise: the 9 JPMorgan "Payments-Digital & Design" product roles count as chip design.
- **Drafts, not proposals.** The narrowed word list, the Design claim, the Hardware words and the Hardware claim in
  4.2.5 were written to count moves. Phase 3 writes the real ones, and the placement check (section 1) lists every
  posting they move.
- **Two variants carry the numbers** (4.2.5): **`narrow`**, Design's words narrowed and nothing else changed, and
  **full**, the same plus a Design claim, extra Hardware words and a Hardware claim.

#### 4.2.1 The brief's title moves, at a glance

| From or to | Into Design (`narrow` / full) | Out of Design (`narrow` / full) | What moves | See |
|---|---:|---:|---|---|
| Software: design engineering | 0 / 31 | 2,182 / 672 | In: product, UX and content designers and 3 UX engineers, by the claim. Out: chip, mechanical and plain "Design Engineer" titles, among them the 48 at software employers, about half of them design engineering (judgement). 113 of 908 open Frontend postings carry a design word; 0 Design postings match a Frontend title pattern | 4.2.5, 4.2.6, §3 |
| AI & Data | 0 / 0 | 0 / 0 | Nothing either way (product analytics is Product's) | §4.1 |
| Hardware: industrial design | 0 / 2 | 12 / 1,747 | Industrial design moves 0 either way: its 82 designers are on Design already. 31 Hardware postings name industrial, CMF or product-design words; 29 are mechanical or electrical product design engineers, correct there | 4.2.5, 4.2.6 |
| Sales: product marketing, growth | 1 / 1 | 63 / 62 | Out: marketing "creative" roles. 130 Design titles carry a Sales word; 156 Sales titles carry a visual, content or design word | 4.2.4, 4.2.7 |
| Healthcare and its claims | 0 / 1 | 24 / 24 | Healthcare's claims hold 2 design-word titles, neither a design role. In: 1 UI designer. Out: molecule design, design-transfer scientists, arts therapists | 4.2.7, 4.2.12 |
| Finance | 3 / 12 | 44 / 44 | In: Quant 8, FinTech 3, Risk 1. Out: FinTech 21, Risk 6 and 7 more categories. Plus 1 Finance filter change | 4.2.5, 4.2.6, §4.3 |
| "other" (Finance reviews) | 46 / 46 | 1,005 / 877 | In: art directors, user researchers, illustrators. Out: mechanical, chip, marketing creative, game and instructional titles | 4.2.5, 4.2.6 |
| Operations | 0 / 0 | 45 / 42 | Out: design-QA engineers, creative operations | 4.2.7 |
| People & Legal | 0 / 0 | 12 / 12 | Out: recruiters and people partners | 4.2.7 |
| Product | 0 / 0 | 0 / 0 | Design program managers stay Product through `program manager` (80 Product postings carry a design word). Full moves 1 Product posting to Hardware | §4.1, 4.2.5 |

The Design board goes from **5,546** open postings to **2,209** under `narrow` (2,159 stay, 50 move in) and **2,159**
under full (2,066 stay, 93 move in).

#### 4.2.2 Design's words, hit by hit

Each word was run title-only over all 366,337 open postings (`census_design_words.py`). `main`'s six:

| Word | Open hits | Design | Hardware | Software | AI & Data | Product | Healthcare | Finance |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `designer` | 1,787 | 1,520 | 193 | 62 | 2 | 2 | 8 | 0 |
| `design` | 7,906 | 3,619 | 3,864 | 252 | 91 | 50 | 10 | 20 (Risk 9, Banking 3, Corp Fin 2, Wealth 2, Insurance 2, Public Markets 1, Markets 1) |
| `user experience` | 103 | 69 | 2 | 14 | 1 | 16 | 0 | 1 (Risk) |
| `ux` | 402 | 317 | 2 | 62 | 0 | 9 | 0 | 12 (Quant 11, Risk 1) |
| `ui` | 369 | 143 | 3 | 214 | 2 | 6 | 1 | 0 |
| `creative` | 401 | 342 | 0 | 33 | 14 | 8 | 0 | 4 (Corp Fin 2, Wealth 2) |

None of the six has a hit on Sales, Operations, People & Legal or "other": Design is checked after Healthcare, AI &
Data, Software, Hardware and Product and before the rest (`non_finance_families._order`), so a title with a Design word
lands on an earlier board, on Finance or on Design. The hits off Design:

- **`design`.**
  - Hardware 3,864, correct there: "Design Verification Engineer" 80, "Mechanical Design Engineer" 42, "Physical
    Design Engineer" 39.
  - Software 252: "AI Infrastructure DC Design Intern" 25, "R&D Software Design Intern" 7.
  - Finance 20. Most are right there: "Market Risk Stress Testing and Scenario Design" (State Street, Risk),
    "Client Segment Risk … Control Design" (Morgan Stanley, 2), "Equities & Digital Assets … Index Design" (S&P,
    Markets), Oscar's "Insurance Product and Benefit Design" 2 (Insurance).
  - Of the 20, JPMorgan's 2 "Experience Design … Business Banking" titles, Mercury's "Senior Design Manager -
    Business Banking & Investments" (Banking), ServiceNow's "Sr. Manager, Product Design, IT Asset Management" (Public
    Markets) and Capital One's "Product Design Director - Risk Design" (Risk) are design roles (4.2.6).
  - 3 are neither finance nor design (judgement; §15): NXP "Design of integrated logic controller for MTP Memory"
    (Corp Fin · Accounting), Inceptive "Computational design of biological experiments for model development" (Risk ·
    Model Risk) and a Roche "Industrial Placement Student - Data Expert, Compliance by Design…" (Risk · Operational
    Risk).
- **`designer`.** Hardware 193: mechanical, PCB, FPGA and RTL designers ("Mechanical Designer" 6, "GPU Top RTL
  Designer" 5, "PCB Designer (Starlink)" 3), correct there. Software 62: product designers whose title a Software word
  took first ("Senior Product Designer, Platform", "Mobile Product Designer"), plus "Software System Designer" 5 and
  instructional designers. Healthcare 8: 4.2.12.
- **`ui`.** Software 214: UI engineers and developers, correct.
- **`ux`.** Software 62: engineers on UX teams ("Senior Software Engineer, Fullstack (Repayments UX)"). Finance Quant
  11: "UX Researcher, Quantitative" 3 and like titles, which are design roles that Quant's words take (4.2.6).
- **`creative`.** Software 33: engineers on "Creative Apps" and "Creative Intelligence" teams.
- **`user experience`.** Product 16: "Product Management Intern, End User Experience" (1Password), correct on Product.

The 37 candidate words beyond `main`'s (`words.txt`; Rest is AI & Data, Product, Healthcare, Sales, Operations and
People & Legal):

| Candidate | Open | Design | "other" | Software | Hardware | Finance | Rest | Reading |
|---|---:|---:|---:|---:|---:|---|---|---|
| `designers?` | 1,790 | 1,521 | 2 | 62 | 193 | 0 | Healthcare 8, AI & Data 2, Product 2 | `designer` plus its plural: 3 more postings (4.2.9). Keep, with exclusions |
| `designs?` | 7,906 | 3,619 | 0 | 252 | 3,864 | 20 (as `design`) | AI & Data 91, Product 50, Healthcare 10 | Same hits as `design`: too broad (4.2.5) |
| `designing` | 1 | 0 | 0 | 1 | 0 | 0 | – | 1 hit, on Software (a Mastercard Java engineer). Not in the draft list |
| `ux/ui` | 34 | 23 | 0 | 11 | 0 | 0 | – | Design. Of Software's 11, 9 are UX/UI engineers and developers, who stay; Agilent's 2 "UX/UI Designer" titles move by the claim (4.2.6). Keep |
| `ui/ux` | 55 | 44 | 0 | 7 | 1 | 0 | Product 3 | As `ux/ui`; Software's 7 are all developers. Keep |
| `user (experience\|interface\|interfaces\|research\|researchers?)` | 132 | 71 | 13 | 21 | 2 | 8 (Markets 3, FinTech 2, Quant 1, Risk 1, IB 1) | Product 16, AI & Data 1 | Keep `user experience` and `user research(ers?)`. "User interface" alone also names Citi's 3 "User Interface Lead" postings on Markets |
| `interaction` | 62 | 23 | 17 | 6 | 6 | 0 | AI & Data 9, Product 1 | Too broad: research interns ("MSR AI Interaction and Learning"). Keep `interaction design(ers?)` |
| `usability` | 9 | 2 | 0 | 7 | 0 | 0 | – | Software's 7 are human-factors and usability engineers. Not in the draft list |
| `human factors` | 45 | 7 | 7 | 30 | 0 | 0 | Ops 1 | Human-factors engineers at medtech and defense. Leave them: no human-factors word on Design (§3.6). "UX and Human Factors Design" stays on Design through `ux` |
| `hci` | 0 | 0 | 0 | 0 | 0 | 0 | – | No hit |
| `human computer interaction` | 1 | 1 | 0 | 0 | 0 | 0 | – | 1 hit, on Design |
| `service designs?` | 6 | 5 | 0 | 0 | 0 | 0 | Product 1 | Design. Fold into `product_design` (§3) |
| `content (designers?\|strateg(y\|ist\|ists)\|writers?\|design)` | 89 | 42 | 28 | 3 | 0 | 10 (Public Markets 3, Wealth 2, IB 2, Strategy 2, FinTech 1) | Sales 5, P&L 1 | Split: content design yes, content strategy and writing no (4.2.11) |
| `ux (writers?\|writing)` | 9 | 9 | 0 | 0 | 0 | 0 | – | All Design. Keep |
| `illustrat(or\|ors\|ion)` | 13 | 2 | 8 | 1 | 0 | 0 | P&L 1, Healthcare 1 | Keep `illustrators?`, but not technical illustrators: 6 of the 8 in "other" are 5 "Technical Illustrator" titles and RTX's "Technical Writer & Illustrator" |
| `animat(or\|ors\|ion)` | 145 | 7 | 115 | 16 | 0 | 0 | AI & Data 4, P&L 2, Ops 1 | Too broad: game and film animation ("Gameplay Animator", Netflix Animation Studios rigging and CFX) |
| `motion` | 135 | 51 | 13 | 17 | 47 | 0 | AI & Data 3, Healthcare 2, Sales 2 | Too broad: "Motion Control", "Motion Planning" on Hardware. Keep `motion design(ers?)`, `motion graphics` |
| `art directors?` | 44 | 13 | 28 | 0 | 0 | 1 (FinTech 1) | Sales 1, AI & Data 1 | Keep. It also brings 9 game-studio art directors (4.2.6) |
| `art direction` | 4 | 2 | 2 | 0 | 0 | 0 | – | Keep |
| `creatives?` | 407 | 342 | 0 | 35 | 0 | 4 (Corp Fin 2, Wealth 2) | AI & Data 17, Product 9 | As `creative`: too broad (4.2.4) |
| `creative (directors?\|leads?\|producers?\|strateg(y\|ist\|ists)\|services\|technologists?)` | 126 | 124 | 0 | 0 | 0 | 1 (Wealth 1) | AI & Data 1 | Keep directors, leads and technologists. Producers and strategists are marketing |
| `visual` | 160 | 33 | 79 | 17 | 0 | 0 | AI & Data 23, Product 3, Healthcare 3, Sales 1, P&L 1 | Too broad: "Visual Merchandiser" 15, "Visual Inspection". Keep `visual design(ers?)` |
| `graphics?` | 350 | 116 | 25 | 154 | 19 | 1 (Strategy 1) | AI & Data 30, Product 3, P&L 1, Sales 1 | Too broad: "Graphics Software Engineer" on Software. Keep `graphic design(ers?)`, `motion graphics` |
| `brand (designers?\|identity\|design)` | 67 | 67 | 0 | 0 | 0 | 0 | – | All Design. Keep |
| `industrial designs?` | 44 | 41 | 0 | 0 | 1 | 0 | Product 2 | Design. Keep |
| `cmf` | 28 | 7 | 2 | 9 | 0 | 0 | Sales 9, Healthcare 1 | Only "CMF design(er)" (4.2.10) |
| `design (research\|researchers?\|systems?\|engineers?\|engineering\|technologists?\|ops\|operations\|program\|strateg(y\|ist\|ists)\|interns?)` | 4,110 | 1,817 | 0 | 102 | 2,146 | 0 | AI & Data 25, Product 18, Healthcare 2 | Split: design research, systems, ops and technologists yes; `design engineer` no (4.2.5) |
| `prototyp(e\|es\|er\|ers\|ing)` | 137 | 2 | 46 | 53 | 28 | 4 (IB 2, Strategy 2) | AI & Data 4 | Too broad: "Prototype Assembler", "Prototyping Specialist (CNC)" |
| `figma` | 10 | 1 | 3 | 2 | 0 | 0 | Ops 2, Sales 1, Product 1 | Titles at Figma the company ("Customer Success Manager - Figma Weave") |
| `3d artists?` | 4 | 0 | 4 | 0 | 0 | 0 | – | Game art. Leave in "other" |
| `artists?` | 161 | 25 | 125 | 3 | 0 | 1 (Markets 1) | Sales 6, Product 1 | Game art ("Technical Artist", "Lighting Artist"). Leave in "other" |
| `typograph(y\|er\|ers)` | 0 | 0 | 0 | 0 | 0 | 0 | – | No hit |
| `researchers?` | 1,235 | 49 | 331 | 177 | 20 | 440 (Quant 404, Public Markets 13, FinTech 11, Markets 5, Risk 3, Corp Fin 2, Insurance 1, Strategy 1) | AI & Data 175, Healthcare 39, Ops 2, Sales 1, P&L 1 | Too broad: Quant researchers |
| `user researchers?` | 8 | 0 | 7 | 0 | 0 | 1 (Quant 1) | – | Design. Keep |
| `ux researchers?` | 38 | 31 | 0 | 0 | 0 | 7 (Quant 7) | – | Design. Keep; the 7 on Quant are design roles (4.2.6) |
| `information architect(s\|ure)?` | 15 | 0 | 1 | 13 | 0 | 1 (Risk 1) | – | Data architects ("Data & Information Architect") |
| `accessibility` | 33 | 2 | 11 | 9 | 0 | 1 (IB 1) | Product 8, AI & Data 2 | Accessibility specialists, DEI and IT accessibility. Not a title word |

How the brief's "Read the hits of every candidate title word" is met:

- All 43 words were run over every open posting, not a sample, and their titles read: `words.txt` holds the top 25
  titles and 8 seeded samples per word and field, and `kinds_full.txt` every hit with its company.
- A word that also names other boards' roles is not added bare. A design title that sits on another board is taken by
  a named claim (`design_occupation`, 4.2.6). The engineering titles Design releases are taken by Hardware words and a
  Hardware claim (`engineering_design`, 4.2.5).
- Each posting a claim moves carries the claim's name in `classification.rule`: 43 carry `design_occupation` and 804
  carry `engineering_design` in the full variant (`sim_rows.json`).
- **Not yet met:** the simulated `design_occupation` has no `subject`, `employer_types` or `description`, so
  `needs_evidence` is false and it takes on its title words alone. The brief asks a claim for evidence. Phase 3 gives
  it evidence and recounts its 43 moves.
- `engineering_design` has evidence (engineering employer types or an engineering subject in the title), and its
  subject words (mechanical, electrical, analog…) are not its title words ("design engineer"…), as the brief asks.

#### 4.2.3 What the Design board holds today (judgement)

**The Design board is two-thirds non-design.** Of its 5,546 open postings, 1,807 (33%) are design roles and 3,458
(62%) are not; 214 are borderline and 67 name nothing (`kinds.txt`, `tables.md`). Most of the non-design ones are
chip, mechanical and plain engineering "Design Engineer" titles: 2,606.

| Kind (judgement) | Open | Canonical | What it is: top titles |
|---|---:|---:|---|
| **Design, 7 kinds** | **1,807** | **1,576** | |
| `d:product_ux` | 1,093 | 945 | "Senior Product Designer" 47, "Product Designer" 35, "Staff Product Designer" 24, "Senior UX Designer" 13, "Director, Product Design" 9, "Experience Design Vice President" 7 |
| `d:visual_brand_motion` | 387 | 341 | "Brand Designer" 15, "Graphic Designer" 10, "Senior Brand Designer" 7, "Motion Designer" 5, "Creative Director" 5, "Director, Head of Creative" 4 (Twitch) |
| `d:designer_generic` | 96 | 87 | "Designer" 7, "Designer Intern" 5, "Cartographic Designer, Apple Maps" 2 |
| `d:industrial_design` | 82 | 66 | "Spring 2027: Industrial Design Co-op" 5, "Industrial Designer" 4, GM and Ford interior, exterior and colour-and-material designers |
| `d:ux_research` | 58 | 53 | "Senior UX Researcher" 7, "UX Researcher" 6, "Staff Design Researcher, Identity" (Intuit) |
| `d:content_design` | 58 | 54 | "Senior Content Designer" 3, "Content Design Senior Associate" 3 (JPMorgan), "UX Writer, Apple Ads", "Conversation Designer" (Decagon) |
| `d:design_engineering` | 33 | 30 | "Creative Technologist" 4, "UX Engineer" 2, "Senior UX Engineer" 2, "Design Technologist (Murrysville, PA)" (Philips) |
| **Not design, 17 kinds** | **3,458** | **2,715** | |
| `nd:mech_elec_design` | 1,031 | 855 | "System Design Engineer" 17, "Camera Design Implementation Intern" 10 (Qualcomm), "Manufacturing Design Engineer" 8, Meta's data-center "Design, Engineering and Construction" roles 18 |
| `nd:chip_ic_design` | 1,029 | 782 | 673 at semiconductor employers: "Intern - Design Engineer, HBM" 21 (Micron), "IC Design Engineer" 15, "Senior Digital Design Engineer" 14, "DDR Design Engineer" 12 |
| `nd:engineering_other` | 546 | 371 | "Principal Design Engineer" 37, "Lead Design Engineer" 33, "Design Engineer" 21, "Technical Staff Engineer - Design" 5 (Microchip) |
| `nd:marketing_creative` | 166 | 135 | "Short Drama Creative Editor Intern" 6, "Creative Strategy & Partnership Marketing Intern" 5 (Disney), "Marketing Partnerships Creative Manager - Korea" (Netflix) |
| `nd:built_environment` | 134 | 109 | "Network Site Design Intern" 7, "Retail Store Design Intern" 5 (Disney), "Principal Data Center Design Manager" (Oracle) |
| `nd:instructional_learning` | 119 | 106 | "Instructional Designer" 18, "Associate Instructional Designer" 6, "Learning Experience Designer" 5, "Instructional Systems Designer" 5 |
| `nd:network_solution_systems` | 104 | 87 | "Principal/Senior Data Hall Designer" 11 (Oracle), "Sr. Network Designer" 2 (Rogers), "Security Solutions Designer" (Cisco) |
| `nd:business_program_design` | 92 | 76 | "Study Design Lead" 4 (Labcorp), "Sr. Analyst, Authorization Services Design & Configuration" 4 (Oscar), "Assessment & Design Lead Analyst" (Citi) |
| `nd:product_design_engineering` | 73 | 55 | Mechanical product design, 44 at big_tech (Apple, Google): "Product Design Engineer" 8, "Haptics Product Design Engineer" 4, "Product Design Engineer - iPhone" 3 |
| `nd:science_molecular_design` | 54 | 46 | "Co-Op, Protein Design" 3 (Moderna), "AI Scientist Intern, Computational Protein Design" 2 (Xaira) |
| `nd:ui_programming` | 37 | 25 | "Senior UI Programmer" (Epic Games), "UI Technical Lead (Angular, React, TypeScript) - VP" (Citi), "RPA UI Path Specialist" (KLA) |
| `nd:cad_drafting` | 36 | 31 | "CAD Designer" 5, "Designer/Drafter Co-Op" 3, "REVIT/CAD/BIM Facilities Designer" 2 |
| `nd:faculty_education` | 15 | 15 | University of Toronto sessional lecturers, "Adjunct Faculty - Art + Design" |
| `nd:recruiting_people_hr` | 12 | 12 | "Staff Recruiter, Design & Specialized Tech" (Gusto), "Design Recruiter" (Stripe), "Executive Assistant, Adobe Creative" |
| `nd:fashion_textile_travel` | 6 | 6 | "Luxury Travel Designer, Chase Travel" |
| `nd:health_therapy` | 3 | 3 | "Creative Arts Therapist" at 3 hospitals |
| `nd:cmf_engineering_or_cmf_sales` | 1 | 1 | "Advanced CMF and Brand Designer" (GM): a design role the rules mislabel |
| **Borderline, 6 kinds** | **214** | **194** | |
| `x:game_design` | 107 | 96 | 89 at game studios: "Senior Game Designer" 7, "Principal Narrative Designer" 3, "Level Design Intern" 3 |
| `x:design_engineer_generic_soft` | 48 | 42 | "Design Engineer" at software employers. About half are design engineering as Design means it (GitHub "Design Engineer, III", Arize AI "Senior Open Source Design Engineer", "Design Engineer, Brand Studio"), the rest hardware ("EMC Design Engineer" at Apple, "TFT Panel Design Engineer", "Module Design Engineer") (judgement) |
| `x:designer_generic_eng_employer` | 31 | 30 | Plain "Designer" titles at defense, medtech and pharma employers: "Designer II" (Sierra Nevada), "Senior Designer, Engineering" (Edwards) |
| `x:art_3d_game_art` | 18 | 17 | Game UI artists: "Senior UI Artist" (EA) |
| `x:human_factors` | 7 | 6 | "Human Factors UX Engineer" (Garmin), "UX and Human Factors Design" (Citi) |
| `x:sound_design` | 3 | 3 | "Sound Design Intern" (EA) |
| **Unnamed, 2 kinds** | **67** | **57** | |
| `?:design_other` | 48 | 44 | "Design Project Manager" 2, "Specialist, Design" 2, "AI Transformation Owner, Product & Design" 2 |
| `?:creative_other` | 19 | 13 | Sony's "Research Engineer Intern (Ethical Creative and Protective AI Lab)" 9, "Creative Video Producer" |
| **Design board** | **5,546** | **4,542** | |

Samples:
- `apple:200657989 'Timing Design Engineer' @ Apple [big_tech]` (chip)
- `google:88033579111457478 'Product Design Engineer, Pixel Hearables' @ Google [big_tech]` (mechanical product design)
- `github:5478 'Design Engineer, III' @ GitHub [developer_tools]` (borderline: design engineering)
- `duolingo:8722385002 'Senior Learning Designer, Indian Languages' @ duolingo` (instructional)
- `epic_games:6020030004 'Senior Game Designer' @ Epic Games [gaming]` (borderline: game)
- `epic_games:5658563004 'Senior UI Programmer' @ Epic Games [gaming]` (UI programming)
- `gusto:8279911 'Staff Recruiter, Design & Specialized Tech' @ Gusto` (recruiting)

Design is checked before Sales, Operations and People & Legal, which is why recruiters, marketing creative roles and
"Creative Arts Therapist" sit on Design today. §3.3 maps the 7 design kinds to the six filters.

#### 4.2.4 What each broad word brings

On the Design board, by kind (`kinds.json` `design_sig`, judgement). "Alone" means the title carries no other of
`main`'s six words.

| Word | Design postings with it | Alone | Alone: design | Alone: not design | Alone: borderline | Alone: unnamed |
|---|---:|---:|---:|---:|---:|---:|
| `design` (without `designer`) | 3,566 | 3,458 | 447 | 2,897 | 67 | 47 |
| `designer` | 1,520 | 1,250 | 792 | 335 | 123 | 0 |
| `creative` | 342 | 270 | 83 | 168 | 0 | 19 |
| `ui` | 143 | 59 | 5 | 37 | 17 | 0 |
| `ux` | 317 | 85 | 83 | 0 | 2 | 0 |
| `user experience` | 69 | 38 | 38 | 0 | 0 | 0 |

- **`design`: 2,902 of its 3,566 postings (81%) are not design.** Alone it brings 970 mechanical and electrical, 940
  chip and 536 plain engineering "design" titles, 115 built-environment, 92 business and program design, 73
  mechanical product design, 56 network and 54 science titles. Narrowing it is 4.2.5 and D8.
- **`designer`** brings the real designers (792 alone) and, alone, 335 non-design titles: instructional 91, chip 87,
  mechanical 60, network 43, CAD 26, built environment 16. Its 123 borderline are game designers 90, plain "Designer"
  titles at engineering employers 31, 1 game artist and 1 sound designer. These are 4.2.8.
- **`creative` alone brings 270:**
  - 168 not design: marketing and production "creative" roles 160, arts therapists 3, faculty 3, recruiting and HR 2.
  - 83 design: visual and brand roles 71, creative technologists 12.
  - 19 unnamed, 9 of them Sony's AI Lab research interns.
  - Narrowed, the marketing creative roles (166 in all) land in "other" 96, Sales 44, Operations 8, Finance 7
    (FinTech 6, Strategy 1), Software 1 and People & Legal 1; 9 stay on Design through a narrowed word.
- **`ui` alone brings 59:**
  - 37 UI programmers ("Senior UI Programmer" at Epic Games, "UI Scripter Intern", Citi's "UI Technical Lead
    (Angular, React…) - VP", KLA's "RPA UI Path Specialist"), 17 game UI artists, 5 designers.
  - Released, the 37 programmers land on Software 19 and in "other" 18, and the game UI artists in "other" (17 of
    the 18 on Design).
- **Bare `ui` and `creative`:** (D10). Both releases are counted inside the `narrow` variant, which
  narrows all three words at once.
- **`ux` and `user experience`** bring only design roles alone (83 and 38) and 2 borderline human-factors titles.
  They stay.

#### 4.2.5 Narrowing `design`, `ui` and `creative` (simulated)

`census_design_sim.py` placed the 12,693 postings with `classify` under five copies of `main`'s `taxonomy.json`. Each
changes only its own rows:

| Variant | What changes | Postings that change field |
|---|---|---:|
| `release` | Design has no title words. Shows where each title lands when no Design word takes it | 5,547 |
| **`narrow`** | Design's words become a draft list (below) | **3,438** |
| `narrow+claim` | Adds a Design claim `design_occupation` from Software, AI & Data, Hardware, Healthcare and Finance | 3,481 |
| `narrow+claim+hw` | Adds Hardware title words for engineering design phrases | 3,575 |
| **`narrow+claim+hw+hwclaim`** (**full**) | Adds a Hardware claim `engineering_design` from Software | **3,589** |

The drafts:
- **Narrowed Design words.**
  - `designers?`, with fixed-width lookbehinds for 57 words that make a "designer" something else: instructional,
    game, level, narrative, technical, CAD, network, solution, database, mask, layout, NAND, learning, mechanical,
    electrical, RTL, FPGA, IC, analog, sound, system, software, engineering… (`_NOT_BEFORE` in the script). Each
    skips only the word right before "designer", so "Learning Experience Designer" still matches.
  - `(product|ux|ui|user experience|user interface|interaction|experience|visual|graphic|brand|motion|communications?|
    content|conversation(al)?|service|industrial|packaging|web|digital|creative|cmf) design`, except before
    "engineer", "engineering" or "engr".
  - `design (systems?|ops|operations|research(ers?)?|technologists?|program managers?|strategy|managers?|directors?|
    interns?|co-ops?|staff)`, and `(head|director|vp|vice president|manager|lead) of design`.
  - `user experience`, `ux`, `ui/ux`, `ux/ui`, `ui design`, `user research(ers?)`, `creative (directors?|leads?)`,
    `art directors?`, `art direction`, `illustrators?` (not after "technical"), `motion graphics`,
    `ux (writers?|writing)`, `design technologists?`, `creative technologists?`.
- **`design_occupation`** (Design claim). Title words: product, UX, UI, interaction, experience, visual, graphic,
  brand, motion, content, conversation, service, industrial, web or digital designer(s); UX, user or design
  researcher(s); UX writer or engineer; design technologist; product design intern, manager, director or lead.
  `unless`: mechanical, electrical, hardware, firmware, FPGA, silicon, PCB, power electronics. No evidence fields.
- **Hardware words.** `(digital|ic|asic|soc|logic|circuit|memory|…|mechanical|thermal|electrical|…) design` and
  `design (verification|validation|evaluation|enablement|automation|…|for test) engineer`. Not plain "design
  engineer": Hardware is checked before Design and would take "UX Design Engineer".
- **`engineering_design`** (Hardware claim from Software). Plain "Design Engineer" titles, with evidence: an
  engineering employer type (semiconductors, defense_tech, hardware_devices, robotics_autonomy, climate_energy,
  medtech, quantum, diagnostics) or an engineering subject in the title. Not when the title names software, UX, UI,
  web, frontend, data, cloud, network or security.

**Why released titles land on Software.** A released "Digital Design Engineer" names no board's word, so
`family_of` returns "other". `classify` then files any title that matches `_CS_OCCUPATION` (`engineer`, `developer`…)
under Software, unless `_HARDWARE_OCCUPATION` matches (embedded, firmware, fpga, asic, rtl, pcb, analog, robotics,
perception, motion planning) (`intel/taxonomy.py` ~25-55, ~223-225). With no Design words at all (`release`), 5,547
postings change field: Design → "other" 2,821, Software 2,280, Finance 188, Sales 130, Operations 71, Healthcare 25,
People & Legal 19, Hardware 12, plus 1 Finance filter change.

Moves out of Design, by destination (`sim.txt`, `sim_rows.json`):

| Destination | `narrow` | Full | What moves (kinds, judgement) | Samples |
|---|---:|---:|---|---|
| **Software** | **2,182** | **672** | `narrow`: chip 738, mechanical 705, plain engineering 517, mechanical product design 68, "Design Engineer" at software employers 45, network 27, built environment 26, UI programmers 19. Full: mechanical 264, plain engineering 130, chip 102, mechanical product design 49, "Design Engineer" at software employers 36 | `narrow`: "Senior Digital IC Design Engineer" (Microchip), "Display Panel Design Engineer" (Apple), "Design Quality Engineer" (Philips). Full: "RFIC Design Engineer" (Apple), "Quantum Qubit Design Engineer" (Intel), "Design Certification Engineer 1" (Garmin) |
| **Hardware** | **12** | **1,747** | `narrow`: chip 12; the samples all name "analog". Full: chip 802, mechanical 511, plain engineering 387, mechanical product design 19; 957 by the Hardware words, 790 by `engineering_design` | `narrow`: "Senior Analog RF Design Engineer" (Ciena). Full: "IC Design Engineer" (Broadcom), "RF Design Engineer" (Skydio), "EMC Design Engineer, Air Dominance and Strike" (Anduril) |
| **"other"** (Finance reviews) | **1,005** | **877** | Mechanical 223 (full 162), chip 141 (full 74), marketing creative 96, game 94, instructional 82, business and program design 62, unnamed 47, built environment 41, network 38, product and UX 32 (the titles the draft list loses, below) | "Senior UI Artist" (EA), "Creative Strategy Lead" (Snap), "Manager, Evidence Generation Study Design & Execution Lead" (Takeda), "Piping Designer" (Leidos), "ORCA Learning Designer" (UBC) |
| **Finance** | **44** | **44** | FinTech 21, Risk 6, Corp Fin 4, IB 4, Insurance 3, Strategy 2, Wealth 2, Banking 1, Public Markets 1 (below) | "Payments-Digital & Design-Senior Product Associate" (JPMorgan → FinTech) |
| Sales | 63 | 62 | Marketing creative 44, business and program design 8, instructional 3 | "Creative Strategist, Brand Partnerships" (Substack), "A/V Creative - Apple TV Brand Creative Marketing" (Apple) |
| Operations | 45 | 42 | Design-QA and design-support engineers 22 (full 20), creative operations 8, instructional 3 | "Design Automation & Quality Assurance Engineer Intern" (Qualcomm), "Lead Creative Operations Manager" (Okta) |
| Healthcare | 24 | 24 | Science and molecular design 15, design transfer and design control 4, arts therapists 3 | "Scientist, Protein Design" (Moderna), "Creative Arts Therapist" (Hackensack Meridian Health) |
| People & Legal | 12 | 12 | Recruiters and people partners 8 | "Design Recruiter" (Stripe) |
| **Out of Design** | **3,387** | **3,480** | | |
| Into Design | 50 | 93 | 4.2.6 | |
| Moves that don't touch Design | 1 | 16 | Finance Markets → FinTech 1 in every variant; full adds Software → Hardware 14 and Product → Hardware 1 (below) | |
| **All changes** | **3,438** | **3,589** | | |

Where each kind lands (open postings on Design today; "same" = as `narrow`):

| Kind | Open | `release` | `narrow` | Full |
|---|---:|---|---|---|
| `d:product_ux` | 1,093 | "other" 918, Finance 91, Software 35, Sales 29, Ops 16, P&L 4 | Design 1,055, "other" 32, Software 4, Finance 2 | Design 1,054, "other" 32, Software 4, Finance 2, Hardware 1 |
| `d:visual_brand_motion` | 387 | "other" 332, Finance 26, Sales 24, Software 4, P&L 1 | Design 366, "other" 20, Sales 1 | same |
| `d:designer_generic` | 96 | "other" 81, Finance 6, Sales 5, Ops 3, Software 1 | Design 96 | same |
| `d:industrial_design` | 82 | "other" 82 | Design 75, "other" 7 | same |
| `d:ux_research` | 58 | "other" 56, Finance 1, Ops 1 | Design 56, "other" 2 | same |
| `d:content_design` | 58 | "other" 43, Finance 11, Sales 2, Ops 1, Healthcare 1 | Design 58 | same |
| `d:design_engineering` | 33 | "other" 17, Software 15, Finance 1 | Design 30, "other" 3 | same |
| `nd:mech_elec_design` | 1,031 | Software 709, "other" 293, Ops 22, Healthcare 4, Finance 3 | Software 705, "other" 223, Design 74, Ops 22, Healthcare 4, Finance 3 | Hardware 511, Software 264, "other" 162, Design 67, Ops 20, Healthcare 4, Finance 3 |
| `nd:chip_ic_design` | 1,029 | Software 761, "other" 238, Hardware 12, Finance 11, Ops 4, Sales 2, P&L 1 | Software 738, "other" 141, Design 125, Hardware 12, Finance 9, Sales 2, P&L 1, Ops 1 | Hardware 802, Software 102, "other" 74, Design 40, Finance 9, P&L 1, Sales 1 |
| `nd:engineering_other` | 546 | Software 525, "other" 18, P&L 1, Ops 1, Sales 1 | Software 517, "other" 16, Design 10, P&L 1, Ops 1, Sales 1 | Hardware 387, Software 130, "other" 16, Design 10, P&L 1, Ops 1, Sales 1 |
| `nd:marketing_creative` | 166 | "other" 100, Sales 49, Ops 8, Finance 7, Software 1, P&L 1 | "other" 96, Sales 44, Design 9, Ops 8, Finance 7, Software 1, P&L 1 | same |
| `nd:built_environment` | 134 | "other" 97, Software 26, Finance 5, Ops 4, Healthcare 1, Sales 1 | Design 59, "other" 41, Software 26, Finance 4, Ops 2, Healthcare 1, Sales 1 | Design 59, "other" 41, Software 17, Hardware 9, Finance 4, Ops 2, Healthcare 1, Sales 1 |
| `nd:instructional_learning` | 119 | "other" 102, Finance 8, Sales 5, Ops 3, Software 1 | "other" 82, Design 27, Ops 3, Finance 3, Sales 3, Software 1 | same |
| `nd:network_solution_systems` | 104 | "other" 71, Software 28, Finance 4, Ops 1 | "other" 38, Design 35, Software 27, Finance 3, Ops 1 | "other" 38, Design 35, Software 20, Hardware 7, Finance 3, Ops 1 |
| `nd:business_program_design` | 92 | "other" 67, Sales 9, Finance 8, P&L 3, Software 3, Ops 2 | "other" 62, Sales 8, Design 8, Finance 8, Software 3, Ops 2, P&L 1 | same |
| `nd:product_design_engineering` | 73 | Software 73 | Software 68, Design 5 | Software 49, Hardware 19, Design 5 |
| `nd:science_molecular_design` | 54 | "other" 25, Healthcare 15, Software 14 | same as `release` | "other" 25, Healthcare 15, Software 12, Hardware 2 |
| `nd:ui_programming` | 37 | Software 19, "other" 18 | Software 19, "other" 18 | same |
| `nd:cad_drafting` | 36 | "other" 32, Software 4 | Design 17, "other" 16, Software 3 | same |
| `nd:faculty_education` | 15 | "other" 13, Healthcare 1, Software 1 | "other" 12, Healthcare 1, Design 1, Software 1 | same |
| `nd:recruiting_people_hr` | 12 | P&L 8, Ops 2, "other" 2 | P&L 8, Ops 2, "other" 2 | same |
| `nd:fashion_textile_travel` | 6 | "other" 6 | "other" 5, Design 1 | same |
| `nd:health_therapy` | 3 | Healthcare 3 | Healthcare 3 | same |
| `nd:cmf_engineering_or_cmf_sales` | 1 | "other" 1 | Design 1 | same |
| `x:game_design` | 107 | "other" 105, Finance 1, Ops 1 | "other" 94, Design 12, Ops 1 | same |
| `x:design_engineer_generic_soft` | 48 | Software 46, "other" 2 | Software 45, "other" 2, Design 1 | Software 36, Hardware 9, "other" 2, Design 1 |
| `x:designer_generic_eng_employer` | 31 | "other" 30, Software 1 | Design 31 | same |
| `x:art_3d_game_art` | 18 | "other" 18 | "other" 17, Design 1 | same |
| `x:human_factors` | 7 | "other" 4, Software 3 | Design 5, "other" 2 | same |
| `x:sound_design` | 3 | "other" 3 | "other" 2, Design 1 | same |
| `?:design_other` | 48 | "other" 39, Finance 4, Sales 2, Ops 2, Software 1 | same as `release` | same |
| `?:creative_other` | 19 | Software 9, "other" 8, Finance 1, Sales 1 | same as `release` | same |

So without Design's words, 918 of the 1,093 product and UX designers fall to "other" and 91 to Finance; the draft list
keeps 1,055 of them on Design. **(D8)**

**Plain "Design Engineer" at software employers: 48, and 47 leave Design.** The draft list keeps no bare `design
engineer`. Under `narrow` they go to Software 45 and "other" 2; under full to Software 36, Hardware 9 and "other" 2
(`sim_rows.json`). About half are design engineering as Design means it (judgement), and those go to Software under
both variants. Among them: GitHub 4 ("Design Engineer, III", "Senior Design Engineer", "Staff Design Engineer", "Sr.
Dir, Design Engineering"), Stripe 3 ("Design Engineer, Brand Studio" 2, "Design Engineer, Expansion"), AlphaSense 2,
Microsoft 2, and Arize AI, Exa AI, Ramp, WorkOS, Sentry, Snap and League. The rest are hardware or engineering:
Apple's 8 EMC, panel and module design engineers and HPE's "Sr. EMC Design Engineer", the 9 the Hardware claim takes;
F5's 2 "Sr HW Design Engineer" and Magna's 6 automotive design engineers, which stay on Software. The
`design_engineering` filter (§3.3) needs a Phase 3 rule that keeps a plain "Design Engineer" on Design at software
employer types; it was not simulated (judgement).

**The 44 postings narrowing puts on Finance** (same under `narrow` and full).
- **Why.** Today the Design family shields them from Finance's weak categories: when a board's word names the title,
  FinTech and Strategy don't claim it (`intel/taxonomy.py` ~273-278). Released to "other", a title is Finance on its
  score alone, description words included (`is_finance` ~295). Krea AI's "Creative" goes to Insurance on "insurance",
  "premiums" and "FSA" in its description (`scratch\s4b_check7.py`).
- **By employer:**
  - JPMorgan 9: "Payments-Digital & Design" product roles, all → FinTech.
  - Citi 6: "Assessment & Design" and "… Methodology Design" → Risk 4, Wealth 2.
  - Mastercard 6: creative roles → FinTech 5 ("Creative Strategist, Advisors Creative Desk"), Strategy 1.
  - TD 3: "Manager, Design & Experience (US)" → Risk; "Solutions Design IT Specialist" 2 → FinTech.
  - Capital One 2: "Senior Associate, Special Projects Design | Retail Bank" → Strategy; an instructional designer →
    Banking.
  - KeyBanc 2 ("Specialty Design and Storytelling Intern") and Morgan Stanley 2 ("Business Analyst, Finance
    Automation – Data Design") → IB.
  - 14 with 1 each: Abbott, Cloudflare, OpenAI and Zoox (design and construction or design assurance) → Corp Fin;
    FIS and DriveTime instructional designers → FinTech and Insurance; Stripe "Workplace Design Coordinator", Visa
    "Senior Associate Solutions Designer, Automation", Mercury "Executive Producer - Brand Creative" and Global
    Payments "Design Lead, Java" → FinTech; Krea AI "Creative" and Manulife "Process Design Analyst" → Insurance; PNC
    "Design Associate - Corporate Workplace" → Risk; Fidelity "… Rewards Strategy and Design Leader" → Public Markets.

**One Finance filter change in every variant.** `sp_global 'Equities & Digital Assets R&D Associate Director, Index
Design' @ S&P Global [market_infrastructure]` is Finance · Markets · Equities on `main` and Finance · FinTech · Digital
Assets once "Index Design" names no board. A narrowed word `index design` keeps it on Markets · Equities, and keeps
S&P's "Index Design R&D Team Manager, Director" on Design, both as on `main` (`classify` on `code-main`,
`E:\product-design-board\phase1\plan\scratch\s4b_check6.py`, these 2 postings only). That this is the fix is
judgement. The 44 and this change are one question: **(D9)**

**Side moves of the full variant** (they don't touch Design):
- Software → Hardware 14, all by `engineering_design`: Intel "Platform Hardware Design Engineer" 5, Leidos "Mobile
  Radar Mechanical Design Engineer" 2, Anduril "Mechanical Design Engineer, Hardware Platform" 2, and 1 each at
  Cadence, GlobalFoundries, Lattice, SpaceX ("Electrical Design Engineer (Starlink Mobile)") and Amazon ("BIM Systems
  Engineer, DC Design Engineering").
- Product → Hardware 1: Tenstorrent "Technical Program Manager SOC & Digital Design", by the Hardware words (Hardware
  is checked before Product).

**What the full variant leaves on Design: 2,159**, of which 345 are still not design, borderline or unnamed
(judgement): mechanical 68 (Rocket Lab "Propulsion Design Intern", Oracle and CoreWeave data-center design managers),
built environment 59, chip 41 ("Substation Physical Designer", "Senior Printed Circuit Board (PCB) Designer"), network
35 (Oracle data-hall designers), plain "Designer" at engineering employers 31, learning experience designers 27, CAD
17, game 12, plain engineering 10, game art 10, marketing creative 9, business design 8 and 18 more.

**Design titles the draft list loses: 72** (design kinds that leave Design under full): product and UX 39, visual 21,
industrial 7, design engineering 3, UX research 2. They go to "other" 64, Software 4, Finance 2, Hardware 1 and Sales 1.
A few are kind noise ("Lead Design CNC Programmer/Operator", "UI Desktop Engineer", judgement). Samples:
- "Director, Design" 3 (eBay 2, OpenText), "Principal, Design" 2 (eBay), "Lead, Design" 2 (Nextdoor), "Design Lead"
  (DoorDash, Midjourney), "Design Leader, Emerging Products" (Asana), "Senior Director, Design" (Epic Games)
- "2027 Summer Intern - Human Interface Design" 3 (GM), "HI Design Producer" (Apple), "Design Producer - Human
  Interface" (Meta), "Director User Exp Design" (Honeywell)
- "Director, Head of Creative" 4 (Twitch), "Director of Integrated Creative" (Microsoft), "Director of Brand &
  Creative" (Contentsquare), "Video Design Lead: Multimedia" 2 (Citi), "Researcher, Figma Design" (Figma)

Phase 3's list needs leader-of-design patterns, "human interface design", "head of creative", "(brand|integrated)
creative" and "(print|news|opinion|video|multimedia) design".

**A limit of the mechanism.** `designers?` has to stay one of Design's own title words, with its exclusions. A
`fallback_title` word or a claim from "other" can't place a "designer" title: both skip titles that `_other_work`
reads as tech work, and `_TECH_OCCUPATION` names `designer` (`intel/taxonomy.py` ~20, ~191-212, ~317).

#### 4.2.6 Moves into Design, by origin (full variant, 93)

| From | n | How | Titles | Reading |
|---|---:|---|---|---|
| "other" | 46 | Narrowed words | 26 visual, brand or motion: "Art Director" 7 (Microsoft, OpenAI, S&P, StackAdapt, Target, NYT, ICF), "Senior Art Director" 4, "Lead Art Director" 2 (Pinterest, Salesforce), "Brand Art Director" (Okta), "Illustrator" and "Illustrator, Intern" (Duolingo), "Motion Graphics Specialist" (Qualtrics). 7 user researchers: "Staff User Researcher" (Coinbase, Harvey, Instacart 2), "Senior User Researcher" (Snowflake, Novartis), "User Researcher, Vice President" (JPMorgan). 1 plural: "Senior Product Designers" (FIS). Adobe "Group Manager - Motion Graphics & Editorial" | 35 design. 9 game-studio art directors (EA 2, Ubisoft 2, Scopely 3, Riot 2). 2 wrong: RTX "Aerospace Technical Writer & Illustrator" and Blue Origin "Senior Lunar Manufacturing Tooling Designers" |
| Software | 31 | `design_occupation` | 23 product and UX designers whose title a Software word took first (Platform, Mobile, Cloud, Developer, Software): "Senior Product Designer, Platform" (Coinbase, Clio), "Product Designer, Claude Developer Platform" (Anthropic), "Product Designer, Cloud Infrastructure" (Apple), "Mobile Product Designer" (Ford, Linear), "Senior UX Designer, Payments Platform Design System" (Google), "UX/UI Designer – Scientific Software" (Agilent). 3 UX engineers: "Senior UX Engineer, Cloud Learning Services" (Google), "Sr Full Stack UX Engineer" (Aurora), "Lead UX Engineer - Software Engineer Stf - E4" (Lockheed). 2 content designers (Etsy, Google). "Visual Designer, Android XR" (Google), "Lead Web Designer & Developer" (YipitData). "Staff Product Designer - UI Platform" (Okta) | All design |
| Finance · Quant | 8 | `design_occupation` | "UX Researcher, Quantitative" 3 (Meta), "Quantitative UX Researcher, Customer Engagement" (Google), "Quantitative User Researcher" (Apple), "Staff Quantitative UX Researcher" (Etsy), a Waymo "Quantitative UX Researcher" intern, Suno "Senior UX Researcher, Mixed Methods (Quant-Leaning)" | Design roles. Finance moves |
| Finance · FinTech | 3 | Narrowed words | "User Research Intern" 2 (Coinbase), "Senior Art Director (Contract)" (SoFi) | Design. A Design word now names the title, so the weak FinTech no longer claims it |
| Finance · Risk | 1 | `design_occupation` | `capital_one 'Product Design Director - Risk Design' @ Capital One [commercial_bank]` | Design |
| Hardware | 2 | `design_occupation` | `cisco:2013154 'ASIC Engineering Digital Designer/ Leader …'`; `siemens_canada:510688 'Frontend / UX Engineer - Robotics Data Operations'` | Cisco is wrong: the claim's `unless` needs "asic" and "digital designer". Siemens is borderline |
| Healthcare | 1 | `design_occupation` | `siemens_healthineers:P-100931 'Senior UI Designer (f/m/d) for medical software products' @ Siemens Healthineers [medtech]` | Design. Healthcare's title word "medical" holds it today (§3.6) |
| Sales | 1 | Narrowed words | "Art Director, SPECS Marketing" (Snap) | Design |

`narrow` alone moves 50 in: "other" 46, FinTech 3 and Sales 1, the rows above that need no claim.

Why the claim is needed:
- **From Software.** Software is checked before Design, so a Software word in the title ("Platform", "Mobile",
  "Cloud", "Developer") takes it first.
- **From Quant.** `occupation_beats_finance` keeps a Design title off Finance only when it matches
  `_TECH_OCCUPATION`, which names `designer` but not `researcher`. When Quant has a title word, Quant wins even then
  (`intel/taxonomy.py` ~284-291). Finance words inside Design titles in general are §4.3.

**Design-kind postings that stay on Finance under every variant: 26** (`sim_rows.json`):
- 5 product-design roles: JPMorgan "Experience Design, Business Banking Insurance - Vice President" and "Experience
  Design Vice President- Business Banking" (Banking), Mercury "Senior Design Manager - Business Banking &
  Investments" (Banking) and "Risk UX Specialist" (Risk), ServiceNow "Sr. Manager, Product Design, IT Asset
  Management" (Public Markets). The claim's words would need "experience design" and "product design manager".
- 4 PayPal "Staff/Senior Experience Researcher" (FinTech), and 4 "UX Quantitative Researcher" titles on Quant (Google
  2, Pinterest's intern 2). The claim's `(ux|user|design) researchers?` names neither "experience researcher" nor a
  title with "quantitative" between "UX" and "researcher".
- 7 content strategists (JPMorgan, Citi 2, William Blair, CIBC, Mastercard, Blackstone: "Investment Content
  Strategist" and like titles), which read as Finance marketing (judgement).
- 6 the kind rules count as design (judgement): Citi "Equities Middle Office - User Interface Lead (VP)" 3 (Markets),
  JPMorgan "Senior Product Associate - User Interface" (IB) and "Tech Risk and Controls Lead - … User Experience &
  Support" (Risk), Goldman Sachs "Asset & Wealth Management, Head of Creative / Integrated Marketing" (Wealth).

**(D13)**

#### 4.2.7 Reverse moves: Design to People & Legal, Healthcare, Sales and Operations

Counts are `narrow` / full; Software, Hardware, "other" and Finance are in 4.2.5.

- **People & Legal, 12 / 12.**
  - 8 recruiters and people partners: "Staff Recruiter, Design & Specialized Tech" (Gusto), "Senior Technical
    Recruiter, Product & Design" and "People Business Partner, Product & Design" (Harvey), "Staff Technical Recruiter,
    Design" (Headway), "Product & Design Recruiting, Vice President" (JPMorgan), "Lead Recruiter | Design" (Ramp),
    "Design Recruiter" (Stripe), "Senior HR Business Partner - Engineering, Product, and Design" (Decagon).
  - 4 more: "Director, People Partners - Product, Design & Engineering" (Figma), "Director & Counsel, Digital
    Innovation & Design" (American Express), "Head of Policy Design, Societal Harms" (Anthropic), "Manager, Campaign
    Creative and Content, Government Affairs and Public Policy" (Google).
  - Of the 12 recruiting and HR postings on Design (4.2.3), 8 go to People & Legal, 2 to Operations ("Executive
    Assistant, Adobe Creative"; Merck "Associate Director Creative Procurement") and 2 to "other" (EA "Senior Art &
    Design Career Manager"; Isomorphic Labs "Senior Finance Business Partner (Drug Design and Development)").
  - They are part of **(D11)** (4.2.8).
- **Healthcare, 24 / 24.**
  - 15 molecule, protein, drug and antigen design titles: Moderna "Scientist, Protein Design", Generate Biomedicines 2,
    Isomorphic Labs 2, Sanofi 3, BMS, Genentech, Roche, J&J, Illumina, Arc Institute, St. Jude.
  - 4 design-transfer and design-control scientists (Natera 3, Thermo Fisher).
  - 3 "Creative Arts Therapist" (Hackensack Meridian Health, CHOP, NewYork-Presbyterian).
  - Mayo Clinic "Faculty Position: … Novel Therapeutic Design Scientist", and Pfizer "Senior Manager, Laboratory
    Design & Space Planning".
  - No new rule: 18 move by Healthcare's existing `life_science_research` claim, which takes the released titles from
    "other", and 6 by Healthcare's own title words (the 3 therapists, Sanofi's 3 virology co-ops).
- **Sales, 63 / 62.** Marketing creative 44: "Creative Strategy & Partnership Marketing Intern" (Disney), "Creative
  Strategist, Brand Partnerships" (Substack), "Editorial Director, Brand & Creative Partnerships" (Stripe), "Senior
  Creative Producer, Video Studio - Vice President" (Goldman Sachs). Business and program design 8, instructional 3.
  Nidec's "Co-Op Custom Design Marketing" goes to Sales under `narrow` and to Hardware under full.
- **Operations, 45 / 42.**
  - Design-QA and design-support engineers 22 / 20: Qualcomm's "Design Automation & Quality Assurance Engineer
    Intern" 6, Boston Scientific and Teleflex "Design Quality Assurance Engineer", Abbott "QA Design Assurance
    Engineer" 2.
  - Creative operations 8: Okta, Qualcomm, Mastercard, Home Depot, Glossier, TikTok 3.
  - Instructional 3.
- **Product, 0.** Design program managers ("Design Program Manager", Instacart's "Senior Design Program Manager II")
  stay Product through `program manager`; that is the Product census's question (§4.1).

The overlaps behind these moves (Sales marketing creative, Frontend, Hardware) are filter questions in §3.5.

#### 4.2.8 Designer titles that are not product, UX or visual design

| Group (judgement) | On Design | Employers | No Design words (`release`) | `narrow` | Full |
|---|---:|---|---|---|---|
| Instructional and learning designers | 119 | unknown 21, defense_tech 12, university 12, enterprise_saas 11, bulge_bracket 10 | "other" 102, Finance 8, Sales 5, Ops 3, Software 1 | "other" 82, Design 27, Ops 3, Sales 3, Finance 3, Software 1 | same |
| Game, level, narrative and systems designers | 107 | gaming 89 | "other" 105, Finance 1, Ops 1 | "other" 94, Design 12, Ops 1 | same |
| Network, solution, data-hall and IT designers | 104 | big_tech 32, defense_tech 18, canadian_bank 13 | "other" 71, Software 28, Finance 4, Ops 1 | "other" 38, Design 35, Software 27, Finance 3, Ops 1 | "other" 38, Design 35, Software 20, Hardware 7, Finance 3, Ops 1 |
| CAD and drafting designers | 36 | defense_tech 13, unknown 7 | "other" 32, Software 4 | Design 17, "other" 16, Software 3 | same |
| Plain "Designer" at engineering employers | 31 | defense_tech 8, medtech 5 | "other" 30, Software 1 | Design 31 | same |
| Game UI artists | 18 | gaming 15 | "other" 18 | "other" 17, Design 1 | same |

- **Today all are Design.** `classify` at `598b525`, title only, puts each group's typical title on Design
  ("Instructional Designer" @ university, 18 stored; "CAD Designer", 5; "Network Designer" @ canadian_tech, 2): the
  near-misses of §3.3, which become classifier tests.
- **What the draft lookbehinds miss.** The ones still on Design under `narrow` carry a word the list doesn't skip:
  "Sr Learning Experience Designer" (Illumina), "Manager, Learning Experience Design" 3 (Capital One),
  "Drafter/Designer 5" 2 (Lam Research), "Senior Designer - CAD" (Stryker), "Principal Data Hall Designer" and
  "Lead Principal Data Hall Designer" 7 (Oracle), "Game Design Intern" 3 (Epic Games 2, EA).
- **Finance.** Released instructional and network designers put 3 + 3 postings on Finance (FIS, DriveTime, Capital
  One; Visa, TD 2), counted in the 44 of 4.2.5.
- **Game designers** are §3's `game_design` question: **(D12)**. The other groups, with the recruiters,
  arts therapists, faculty and travel designers of 4.2.3 and 4.2.7: **(D11)**.

#### 4.2.9 Plurals and -ing forms

- **Stored data: 4 open titles say "designers"** (`examples.txt` §2):
  - `fis 'Senior Product Designers' @ FIS [enterprise_saas]`: "other" today, Design under the narrowed words.
  - `blue_origin 'Senior Lunar Manufacturing Tooling Designers' @ Blue Origin [defense_tech]`: "other" today, Design
    under the narrowed words (wrong: it is tooling).
  - `apple:200600519 'Computational Designers: Industrial Design Group' @ Apple [big_tech]`: Design, through `design`.
  - `general_motors 'Engineering  Designers - Electrical Designer' @ General Motors [robotics_autonomy]`: Hardware.
  - `designing` matches 1 open posting, on Software.
- **`classify` at `598b525`, title only:** "Motion Designers", "Junior Product Designers", "Product Designers" @
  big_tech and "Graphic Designers" land in "other". "UX Designers" and "UX Researchers" land on Design only through
  `ux`. "Designing Experiences Intern" lands in "other".
- **The brief's three places for plural titles:**
  - The census ran `designers?`, `researchers?`, `art directors?`, `illustrat(or|ors|ion)` and the other plural forms
    of `candidate_titles.json`.
  - The placement sample's title words include them (section 2.4).
  - The classifier tests get them in Phase 3.
- **(D14)**

#### 4.2.10 `cmf`

28 open hits: 9 "CMF Engineer" titles on Software through `engineer` (Logitech 5, Garmin 3, Oura 1), 9
craniomaxillofacial sales roles on Sales (Stryker 5, J&J 4), 7 CMF designers on Design (GM 2, SpaceX, Anduril, Rivian,
Vast Space, Logitech), 2 in "other" (Logitech "CMF Technical Manager", J&J "Business Unit Lead: TECA, PT & CMF") and 1
on Healthcare (J&J "Clinical Specialist - Trauma & CMF"). Only "CMF design(er)" names design work, and Design already
holds the CMF designers. A bare `cmf` would take the 9 engineers, the 9 sales roles and the 2 in "other", since Design
is checked before Sales and before the engineer fallback (by the word order; not simulated). **(D14)**

#### 4.2.11 Content design vs copywriting

§3.3 has the table (`census_design.md` §6). In short, open postings:
- **UX writing, content design and conversation design: 60 open postings, 51 distinct titles**, the union of
  `ux (writers?|writing)` 9, `content design(ers?)?` 43 and `conversation(al)? design(ers?)?` 13
  (`scratch\s4b_check3.py`). 58 are on Design. The 2 on Software are there because Software's `platform` took them
  (Etsy "Staff Content Designer, UX Platform", Google "Staff Conversation and Content Designer, Google Cloud Business
  Platform"), and the Design claim moves both (4.2.6).
- **Copywriters, content writers, content marketers and content strategists** are marketing or editorial work. Almost
  none is on Design: 1 of 10 content writers (Nutanix "UX Content Writer"). Content strategists 36 ("other" 22, Finance
  7, Sales 5, People & Legal 1, Software 1), copywriters 30 ("other" 25), content marketing 40 (Sales 39).
- Beyond §3.3's rows: `content creat(or|ors|ion)` 38 ("other" 21, Software 8, Product 7, FinTech 1, Healthcare 1) and
  `editors?` 160 ("other" 106, Design 10, Sales 9, Markets 8, People & Legal 7, …).
- A content strategist belongs to `content_design` only when the title names UX or product: "Content Strategist,
  Product" (Figma, 1, in "other").
- Copywriting and content marketing are Sales & Growth's to design.
- **(D14)**

#### 4.2.12 Healthcare's claims on design words

§3.6 has Healthcare's claims, the titles its words hold and the brief's test cases. What concerns Design's words:
- **Claims.** Of the two claims that take from Design, `clinical_occupation` and `lab_quality` hold 2 open postings
  whose title carries a design word, neither a design role (judgement). Both stay:
  - `nova_scotia_health:538602917 'Family Physician - Care by Design' @ Nova Scotia Health [hospital]`, taken from
    Design by `clinical_occupation`.
  - `takeda:99824692576 'Associate Director, Analytical Quality by Design and Platform Analytical Method Lifecycle'
    @ Takeda [pharma]`, taken by `lab_quality` from Software: its "Platform" is a Software word, checked before
    Design (`family_of` on `main`, `scratch\s4b_verify4.py`).
  - A third, Moderna's "Sr. Research Associate, Protein Design", is held by `life_science_research` from Finance.
- **Family words.** Healthcare's own title words (clinical, medical…) place 8 designer or UX titles:
  - IQVIA "Clinical DB Designer" and "Clinical Database Designer", 5, correct there.
  - Premier Research "Clinical Operations Instructional Designer/Trainer Analyst II".
  - J&J "Associate Clinical Designer, Orthopedics".
  - Siemens Healthineers "Senior UI Designer (f/m/d) for medical software products", the one real UI designer. The
    Design claim moves it (4.2.6).
- **Narrowing makes no new claim.** The 24 Design → Healthcare moves of 4.2.7 are released titles that Healthcare's
  existing `life_science_research` claim (18) and title words (6) place.
- **Proposal:** leave Healthcare's claims as they are.

### 4.3 Finance words inside Product and Design titles

Counted by `E:\product-design-board\phase1\finance_seniority.md` Part 1 (scripts `finance_seniority_fin_words.py`,
`_fin_tables.py`, `_examples.py`, `_claims.py` and `_techocc.py`; outputs `phase1\data\finance_seniority_*`), on all
410,486 titled postings in `census.db`. Counts are **stored/open** (open: `status != 'closed'`). Each posting is
re-classified with its full description and listing note, department and stored employer type, and `main`
reproduces the stored placement for every row read (§4 intro). This section's own checks are in
`phase1\plan\scratch\s4c_*.py`: the Finance moves when Product's words and a claim apply together
(`s4c_combined.py`), their overlap (`s4c_overlap.py`), the brief's titles (`s4c_brief_titles.py`) and the claim
moves by kind (`s4c_claims.py`).

#### 4.3.1 How Finance takes a P&D title

In `classify` (`intel/taxonomy.py` ~214):
1. `family_of` (~162) picks the board from the boards' title words in `_order`: Healthcare, AI & Data, Software,
   Hardware, Product, Design, Sales, Operations, People & Legal. The first match wins.
2. Every Finance category and subcategory is scored on the title (pay line stripped), department, description and
   employer priors. `finance_title_hit` is true when a Finance category has a title word in the title. For a title
   with a board, FinTech and Strategy are `weak_title` and can't take it, and `ambiguous_title_hits` are dropped.
3. ~284: when the board has `occupation_beats_finance` (Healthcare, AI & Data, Software, Hardware, Product and
   Design) and the title matches `_TECH_OCCUPATION`, the Finance title signal is switched off. One exception: a title
   Quant has a title word for goes to Quant.
4. `is_finance` is a best score of at least 3 with a Finance title hit, or with no board at all.
5. A Finance posting then moves only by a claim with `"from": ["finance"]` (`_claim` ~196). Today only Healthcare's
   `life_science_research` has one.

`_TECH_OCCUPATION` (~20-24) names `designer`, `product manag(er|ement)` and `product coordinat(or|ion)` (and engineer,
developer, architect), but not program manager, technical program, product analyst, product owner, product
associate, `ux`, researcher or user experience. So the flag protects a Product title only when it says product
manager, management or coordinator (or names an engineering occupation), and a Design title only when it says
designer. Sales, Operations and People & Legal have no flag, so any Finance title word takes their titles.

`main`, title only, at unknown, big_tech, bulge_bracket, fintech and commercial_bank (all five agree for every title;
`data\finance_seniority_examples.txt`):

| Title | `_TECH_OCCUPATION` | `main` places it |
|---|---|---|
| Product Analyst, Credit Risk | no | Finance · Risk · Credit Risk |
| Program Manager, Risk | no | Finance · Risk |
| Program Manager, Compliance | no | Finance · Risk · Operational Risk |
| Technical Program Manager, Payments Risk | no | Finance · Risk |
| Technical Program Manager, Risk Technology | no | Finance · Risk |
| UX Researcher, Wealth Management | no | Finance · Wealth · Wealth Management |
| Product Owner, Wealth | no | Finance · Wealth |
| Head of Product, Lending | no | Finance · Banking · Lending |
| Senior Product Associate - Small Business Lending | no | Finance · Banking · Commercial Banking |
| UX Researcher, Quantitative · Quantitative UX Researcher | no | Finance · Quant |
| Product Manager, Credit Risk | yes | Product |
| Product Manager, Payments | yes | Product |
| Product Designer, Trading | yes | Design |
| UX Designer, Wealth Management | yes | Design |
| Product Manager, Quantitative Trading | yes | Finance · Quant · Quant Trading (the Quant exception) |
| Product Designer, Quant Research | yes | Finance · Quant · Quant Research (the Quant exception) |
| Product Analyst, Payments | no | Product ("payments" is FinTech's, a `weak_title` category) |
| Design Researcher, Banking | no | Design (no Finance title word) |

#### 4.3.2 P&D titles on Finance, by finance category

**2,153/1,844 of the 46,332 stored Finance postings name a P&D word**: one of `main`'s title words (Product's six,
Design's six) or a candidate word (`finance_seniority_fin_tables.txt`, T1). A posting counts once, in the first group
it hits.

| Finance category | `main`'s Product words | `main`'s Design words | Candidate words only, Product | Candidate words only, Design | Total |
|---|---:|---:|---:|---:|---:|
| Corporate Finance | 19/19 | 6/4 | 207/172 | 2/2 | 234/197 |
| Investment Banking | 12/8 | 0/0 | 249/225 | 5/5 | 266/238 |
| Risk | 88/76 | 11/11 | 168/136 | 4/4 | 271/227 |
| Banking | 4/4 | 3/3 | 53/47 | 2/0 | 62/54 |
| Wealth | 5/5 | 4/4 | 87/82 | 3/2 | 99/93 |
| Markets | 14/13 | 3/1 | 166/139 | 9/9 | 192/162 |
| Public Markets | 2/1 | 2/1 | 100/78 | 17/16 | 121/96 |
| Quant | 8/6 | 15/11 | 29/24 | 427/395 | 479/436 |
| FinTech | 0/0 | 0/0 | 225/175 | 19/15 | 244/190 |
| Strategy | 0/0 | 0/0 | 94/78 | 6/6 | 100/84 |
| Insurance | 3/3 | 2/2 | 46/35 | 0/0 | 51/40 |
| Private Markets | 0/0 | 0/0 | 34/27 | 0/0 | 34/27 |
| **Total** | **155/135** | **46/37** | **1,458/1,218** | **494/454** | **2,153/1,844** |

So the brief's count, the boards' own titles that land on Finance today, is **155/135 Product** and **46/37
Design**. What the words catch (T2; a posting counts under each word it names; the open split by category is from
`census_product_words.txt`):
- **`program manager`** 137/121. Open: Risk 74, Corporate Finance 15, Markets 13, Investment Banking 7, Wealth 5,
  Banking 4, Insurance 2, Public Markets 1. Read in full: compliance, risk, audit, tax and accounting program
  managers (Amazon, Meta, Stripe, Visa, Lam Research…), not product roles (judgement).
- **`technical program`** 23/20. Open: Risk 14, Banking 2, Insurance 2, Markets 1, Corporate Finance 1. Technical
  program managers on risk and compliance technology (JPMorgan, Google, Snap, Anthropic).
- **`product analyst`** 11/10. Open: Corporate Finance 4, Quant 3, Insurance 1, Investment Banking 1, Risk 1. Mixed:
  DRW "Risk Product Analyst" ×3, BofA "Treasury Product Analyst - Payments", Goldman Sachs "Global Banking & Markets
  - Transaction Banking - Channels Product Analyst - Dallas" ×2, Intuitive Surgical "Finance Data Product Analyst —
  FP&A" ×2, Fannie Mae, an insurer, GSK.
- **`product manager`** 4/3 and `product management` 1/0, all on Quant by the Quant exception (T1b): BlackRock
  "Senior Product Manager - Aladdin Trader, Vice President", JPMorgan "Credit Portfolio Group – Quantitative Product
  Manager - Associate" (3 sources), Honeywell "Senior Product Management Specialist, Fire Portfolio Strategy".
- **`ux`** 16/12: Quant 15, quantitative UX researchers at Meta, Google, Waymo, Pinterest, Etsy and Gusto (4.3.5);
  Risk 1, Mercury "Risk UX Specialist".
- **`design`** 25/20, mostly not design work: "Control Design", "Scenario Design", "Index Design", "Store Design &
  Renewal", "Data Center Infrastructure Design", "Benefit Design", "Learning Design". A few are real: JPMorgan
  "Experience Design Vice President- Business Banking", Capital One "Product Design Director - Risk Design",
  ServiceNow "Sr. Manager, Product Design, IT Asset Management", Mercury "Senior Design Manager - Business Banking &
  Investments".
- **`creative`** 4/4: Goldman Sachs "Head of Creative / Integrated Marketing", "Brand Marketing and Creative
  Strategy", Adobe "Creative Cloud" FP&A, a treasury manager. **`user experience`** 1/1 (Risk).
- **Candidate words** are mostly noise on Finance. Bare `products?` 1,250/1,044 ("Product Control", structured,
  card and payment products). `researchers?` 478/440, of which 440 stored are on Quant, nearly all "Quantitative
  Researcher". The real P&D ones are in `products? (owners?|leads?|associates?|…)` 431/362 (product owners and
  product associates at JPMorgan, Morgan Stanley, Barclays, BNY…), `heads? of products?` 11/8, `ux researchers?` 9/7
  (all Quant), `user researchers?` 1/1, `art directors?` 4/1 and `tpms?` 3/3 (Amazon's privacy and compliance TPMs).
  `programs? (managers?|…)` 323/278 is mostly the same compliance and PMO program titles (Risk 122 stored).

Samples (seed 20261031, T4a and T4b):
- `amazon_finance:10467825 'Risk Program Manager, Internal Audit - Professional Practices' @ Amazon (Finance · Risk)`
- `waymo:7939648 'Program Manager, Risk & Insurance' @ waymo (Finance · Risk)`
- `lam_research:1099555377878 'Compliance & Accountability Program Manager (all genders)' @ Lam Research (Finance ·
  Risk)`
- `jpmorgan:210712294 'Lead Technical Program Manager - Markets, Equities' @ JPMorgan Chase (Finance · Markets)`
- `mercury:6236623004 'Senior Design Manager - Business Banking & Investments' @ Mercury (Finance · Banking)`
- `goldman_sachs:181583 'Asset & Wealth Management, Head of Creative / Integrated Marketing, Senior Vice President' @
  Goldman Sachs (Finance · Wealth)`
- `american_express:26014544 'Total Rewards Product Associate' @ American Express (Finance · Risk)`
- `kkr:6150185004 'Product Specialist - Real Assets' @ KKR (Finance · Private Markets)`
- `mastercard_early:…R-291326-1 'Program Management Intern, Summer 2027 – Dublin, Ireland' @ Mastercard (Finance ·
  FinTech)`
- `tower_research:6679938 'Quantitative Researcher' @ Tower Research Capital (Finance · Quant)`: a noise word.

Design's side is also counted per word in §4.2.2 (open: `design` 20, `ux` 12, `creative` 4, `user experience` 1).
Narrowing Design's words puts 44 open postings onto Finance, which Design's words shield today (§4.2.5).

#### 4.3.3 What `occupation_beats_finance` protects

**571/488 stored P&D postings name a Finance title word** (T3: re-classified with `occupation_families` emptied):
- **310/263 stay on P&D only because of the flag and `_TECH_OCCUPATION`.** With the flag off they read as Finance.
  All 310 name a `_TECH_OCCUPATION` word. Product's share is 292/249: the 249 open match, category by category, the
  249 that dropping Product's alternatives from `_TECH_OCCUPATION` sends to Finance (4.1.10).
- **261/225 stay even without the flag.** Their only Finance words are FinTech's "payments" (211) or Strategy's
  "strategic initiatives" and "strategic planning" (34), `weak_title` categories that can't take a title with a
  board. 16 more (Risk 8, Corporate Finance 4, Investment Banking 2, Markets 1, Public Markets 1) stay for other
  reasons, an ambiguous title word or a score under 3, not checked one by one.

Where the 310 would go without the flag:

| Would-be Finance category | Product | Design |
|---|---:|---:|
| Risk | 80/65 | 9/7 |
| Banking | 45/40 | 1/1 |
| Corporate Finance | 37/30 | 5/3 |
| Wealth | 34/31 | 1/1 |
| Markets | 33/32 | 0/0 |
| Public Markets | 28/21 | 0/0 |
| Insurance | 13/12 | 0/0 |
| Private Markets | 13/10 | 0/0 |
| Investment Banking | 9/8 | 2/2 |
| **Total** | **292/249** | **18/14** |

Held only by the flag (T4c):
- `jpmorgan:210766566 'Chase Wealth Management, Product Manager, Vice President' @ JPMorgan Chase` → Wealth
- `stripe:8304725 'Product Designer, Risk' @ Stripe` → Risk
- `capital_one:…R1002634-1 'Manager, Product Manager- Tech Risk' @ Capital One` → Risk
- `goldman_sachs_tech:185197 'Transaction Banking, Channels Product Manager, Associate' @ Goldman Sachs` → Banking
- `alphasense:8379162002 'Sr. Product Manager, M&A Transactions and Valuations' @ AlphaSense` → Investment Banking
- `simplify_intern26:e1ba63cb-… 'Insurance Product Management Analyst Intern 3' @ NJM Insurance Group` → Insurance

Stay without the flag (T4d): Intuit "Principal Product Designer - Payments", FIS "Senior / Staff Product Manager –
Payments", Shopify "Sr. Staff Technical Program Manager - Payments (Canada )" (FinTech's "payments"), Applied
Materials "Operations Strategic Planning & Program Manager" (Strategy's "strategic planning").

This is why the brief's "Product Manager, Credit Risk" and "Product Designer, Trading" stay on P&D, and why the
program, owner, analyst and researcher titles in 4.3.1 don't.

#### 4.3.4 Claims from Finance: V1, V2, V3 and PGM (D6)

**How they were simulated** (`finance_seniority_claims.py`). Each variant's claims are appended to `kn.claims` after
Healthcare's (the order the boards put them), with no evidence: no subject, employer type or description words. Every
stored Finance posting whose title names a claim word, 447 in all, was re-classified with its full inputs. Nothing
moves to any board but the claim's own.

| Variant | Title words |
|---|---|
| V1 | `main`'s Product and Design title words, with plurals: `product managers?`, `product management`, `product coordinators?`, `program managers?`, `technical programs?`, `product analysts?`; `designers?`, `designs?`, `user experience`, `ux`, `ui`, `creatives?` |
| V2 | Product: `product manag(er\|ers\|ement)`, `product owners?`, `product leads?`, `heads? of products?`, `vp,? (of )?products?`, `chief product officer`, `product associates?`, `product analysts?`, `product operations`, `product ops`, `apms?`, `tpms?`, `technical program manag(er\|ers\|ement)`. Design: `designers?`, `ux`, `ui`, `user experience`, `user research(ers?)?`, `design research(ers?)?`, product, experience, interaction, service, visual and content `design`, `art directors?`, `creative directors?` |
| **V3** (recommended) | V2 without `product analysts?` and bare `apms?`, plus `technical programs?`, `(apm)` and `(tpm)`; Product `unless apm stores`, Design `unless controls?` |
| PGM | Bare `program managers?`, `unless technical` |

| Variant | Leave Finance (stored/open) | To Product | To Design |
|---|---:|---:|---:|
| V1 | 203/174 | 157/137 | 46/37 |
| V2 | 304/257 | 276/236 | 28/21 |
| **V3** | **293/247** | **266/227** | **27/20** |
| PGM | 115/102 | 115/102 | 0 |

By Finance category (Product and Design together, stored/open):

| Category | V1 | V2 | V3 | PGM |
|---|---:|---:|---:|---:|
| Investment Banking | 12/8 | 57/55 | 55/54 | 10/7 |
| Risk | 99/87 | 62/46 | 60/44 | 69/61 |
| FinTech | 2/2 | 50/41 | 52/43 | 0 |
| Wealth | 9/9 | 23/23 | 23/23 | 5/5 |
| Quant | 23/17 | 29/21 | 26/18 | 0 |
| Strategy | 0 | 17/15 | 17/15 | 0 |
| Markets | 17/14 | 16/14 | 16/14 | 13/12 |
| Public Markets | 4/2 | 14/12 | 14/12 | 2/1 |
| Banking | 7/7 | 13/9 | 13/9 | 2/2 |
| Corporate Finance | 25/23 | 12/12 | 7/7 | 14/14 |
| Insurance | 5/5 | 7/6 | 6/5 | 0 |
| Private Markets | 0 | 4/3 | 4/3 | 0 |

**What V2 and V3 take** (`scratch\s4c_claims.py`, by the first word that matches):
- Product under V2: product owner 134/107, product associate 69/68, TPM 26/23, product lead 14/13, head, VP or CPO of
  product 12/9, product analyst 11/10, product manager or management 5/3, product ops 4/2, `apm` 1/1 (Amazon "Senior
  Financial Analyst, APM Stores Verticals", an FP&A role).
- V3 drops 13 of V2's: the 11 product analysts, Amazon's "APM Stores" analyst and JPMorgan's "Tech Risk and Controls
  Lead - Citizen Development Governance User Experience & Support". It adds PayPal's "Manager, Technical Programs" and
  "Sr Manager, Technical Programs".
- V3's employers (stored): JPMorgan Chase 114, Morgan Stanley 15, Barclays 12, Citi 10, Bank of America 10,
  DriveWealth 8, Capital One 7, Google 7. Open: JPMorgan Chase 112 of the 247. Employer types (stored):
  bulge_bracket 164, fintech 23, unknown 23, canadian_bank 20, big_tech 17, commercial_bank 13.
- V3's Design moves, 27/20 (all 27 are design roles, judgement):
  - Quantitative UX researchers on Quant 16/12: Meta "UX Researcher, Quantitative" ×3, Google 4 ("Quantitative UX
    Researcher, Customer Engagement", "Staff UX Quantitative Researcher, Agentic AI Ad Sales", "UX Quantitative
    Researcher, Geo Makers", one closed), Pinterest "UX Quantitative Research Intern" ×3, Waymo's MS/PhD intern ×2,
    Apple "Quantitative User Researcher", Etsy "Staff Quantitative UX Researcher", Gusto, Suno.
  - Coinbase "User Research Intern" ×2, JPMorgan "Experience Design" Vice Presidents ×2, Capital One "Product Design
    Director - Risk Design", ServiceNow "Sr. Manager, Product Design, IT Asset Management", Mercury "Risk UX
    Specialist", art directors at Capital One ×2, SoFi and American Express.
- **V3 also takes 10/6 Product titles off Quant**: JPMorgan "Credit Portfolio Group – Quantitative Product Manager -
  Associate" ×3 and "Area Product Owner, Quantitative Risk Analytics" ×4, BlackRock "Senior Product Manager - Aladdin
  Trader, Vice President", Wells Fargo "Product Owner: Market Maker & Options Clearing (VP)", Honeywell's Fire
  Portfolio Strategy specialist. The claim runs after the Quant exception, which keeps "Product Manager, Quantitative
  Trading" on Quant on purpose. An `unless quant(itative)?` on the Product claim would keep these 10 there; it was not
  simulated.

**§4.2's Design claim agrees.** The 12 open postings that §4.2.6 moves from Finance (Quant 8, FinTech 3, Risk 1) are
all among V3's 20 open Design moves. V3 takes 8 more: Pinterest's 2 interns and Google's "Geo Makers" and "Agentic AI
Ad Sales" researchers (word orders §4.2's claim misses), Mercury "Risk UX Specialist", JPMorgan's 2 "Experience
Design" Vice Presidents and ServiceNow's design manager.

**The brief's titles** (title only, the same at unknown, big_tech, bulge_bracket and fintech;
`scratch\s4c_brief_titles.py`):

| Title | `main` | With V3 |
|---|---|---|
| Product Analyst, Credit Risk | Finance · Risk | Finance · Risk (V3 has no product-analyst word) |
| Program Manager, Risk · Program Manager, Compliance | Finance · Risk | Finance · Risk |
| Technical Program Manager, Payments Risk · … Risk Technology | Finance · Risk | Product, rule `product_from_finance_V3` |
| UX Researcher, Wealth Management | Finance · Wealth | Design |
| Product Owner, Wealth | Finance · Wealth | Product |
| Head of Product, Lending · Senior Product Associate - Small Business Lending | Finance · Banking | Product |
| UX Researcher, Quantitative · Quantitative UX Researcher | Finance · Quant | Design |
| Product Manager, Quantitative Trading | Finance · Quant | Product |
| Product Manager, Credit Risk · Product Designer, Trading | Product · Design | unchanged |

**A judgement sample of 40** of the 447 postings any of V1, V2 or PGM moves (seed 20261031; the reads are the
report author's, from title and employer):

| Group | Moved by | Sampled | Real P&D role? |
|---|---|---:|---|
| Product owners, associates, leads and ops at banks and payment firms: JPMorgan 12, Morgan Stanley 2, BMO, BNY, Capital One, Mastercard, Wells Fargo, American Express | V2, V3 | 20 | 19 yes, 1 borderline (Wells Fargo "Quantitative Analytics Senior Manager -Agentic AI Platform & Product Owner", half quant analytics) |
| Quantitative UX researchers: Meta 2, Google, Waymo, Suno | V1, V2, V3 | 5 | 5 yes |
| Goldman Sachs "… Channels Product Analyst - Dallas" | V1, V2 | 1 | yes |
| PayPal "Manager, Technical Programs", "Sr Manager, Technical Programs" | V1, V3 | 2 | 2 yes |
| Bare program managers in compliance, risk, tax, accounting and equities: Amazon 3, Stripe 2, Meta, Nidec, Anduril, Intuitive Surgical, JPMorgan, Robinhood | V1, PGM | 11 | 0 yes |
| S&P Global "Equities & Digital Assets R&D Associate Director, Index Design" | V1 | 1 | no (index design is Finance work) |

Tally: 27 yes, 1 borderline, 12 no. V2's 26 in the sample: 25 yes, 1 borderline. V3's 27: 26 yes, 1 borderline (it
drops the Goldman analyst and adds PayPal's 2). V1's 20: 8 yes, 12 no. PGM's 11: 0 yes.

The report's recommendation is V3 as two named claims, `product.claims.product_occupation_from_finance` and
`design.claims.design_occupation_from_finance`, with the title words in `title`, not `subject` (Part C: a claim's
`subject` must not repeat its `title` words), each moved posting carrying its rule in `classification.rule`. (The tables above show the
simulation's rule name, `product_from_finance_V3`.) Design's half can instead be §4.2's `design_occupation`, whose
`from` already includes Finance: one claim, not two (D13). It leaves out:
- **Product analysts on Finance** (11/10): about half are product roles (judgement), and the brief's "Product
  Analyst, Credit Risk" is of this kind. Decide them with the `product_analytics` and `data_ml.analytics` overlap
  (§3.5). V2 takes all 11.
- **Bare program managers on Finance** (115/102; Risk 69/61): 0 of 11 sampled are product roles. They stay Finance.
  V3 and PGM share no posting, so V3 with PGM would move 408/349.

V3's Design half and §4.2's Design claim from Finance are the same question (D13, with D6): answer them
together.

#### 4.3.5 Quantitative UX researchers on Quant

- **16/12 UX researchers sit on Finance · Quant** (all 16 are in V3's Design moves, 4.3.4). Their titles carry
  Quant's title word ("quantitative", "quant") and no `_TECH_OCCUPATION` word: "researcher" isn't one, and even
  "designer" yields to a Quant title signal (4.3.1, step 3).
- They are UX research roles that use quantitative methods, at product companies (Meta, Google, Pinterest, Waymo,
  Apple, Etsy, Gusto, Suno), not quant finance (judgement: all 5 sampled in 4.3.4 read as UX research).
- What takes them: V1, V2 and V3 all take the 16. §4.2's Design claim takes 8 open. Widening `_TECH_OCCUPATION`
  takes none, because the Quant exception still wins (4.3.6). Pinterest's "UX Quantitative Research Intern" and
  Google's "UX Quantitative Researcher" put "Quantitative" between "UX" and "Researcher", so a claim needs `ux` alone
  or both word orders.
- Taking them is a Finance move: Quant profiles stop seeing them.

#### 4.3.6 The code alternative: widen `_TECH_OCCUPATION` (D7)

- **`finance_seniority_techocc.py`** adds `(technical) program manager/management`, `product analyst/owner`,
  `(ux|user|design) researcher`, `ux` and `user experience` to `_TECH_OCCUPATION` and re-classifies all 7,067 stored
  postings, on any board, that name one. **153/134 move, all from Finance; 152/134 leave it**: Product 147/130,
  Design 2/2, Software 2/1, Healthcare 1/1. The other 1/0 stays on Finance, from Risk to Quant (Wells Fargo's Agentic
  AI product owner). By category moved (stored, Wells Fargo's included): Risk 91, Corporate Finance 19, Markets 14, Investment Banking 12,
  Wealth 5, Banking 4, Quant 3, Insurance 3, Public Markets 2 (`data\finance_seniority_techocc.txt`).
  - Nearly all of the 147 are the compliance, risk and accounting program managers 4.3.4 judged not product: Intuitive
    Surgical "Environmental Compliance Program Manager", Amazon "Accounting Program Manager, Digital Finance &
    Business Integration", Qualtrics "Senior Program Manager - Privacy Compliance & Data Governance", Nuro "Senior
    Program Manager, Compliance Reporting". Design's 2 are Mercury "Risk UX Specialist" and JPMorgan's tech-risk
    controls lead (wrong). Software's are HPE "Technical Program Manager - Software Compliance and Program Budgeting"
    and Fidelity "Program Manager, Compliance Platform Strategy"; Healthcare's is Blue Cross Blue Shield of
    Massachusetts "Program Manager, Clinical Compliance".
  - It misses the real product roles. "Product Owner" and "Product Associate" titles have no board on `main`, so the
    flag never applies to them, and the quantitative UX researchers still go to Quant by the Quant exception.
- **The census's narrower edits** (`census_product_shared.py`, open; 4.1.10): program, technical-program and TPM
  words take 120 off Finance on `main`'s config and 136 on P2's (mostly Risk: 73 and 81); product owner and product
  analyst take 10 on `main`'s and 57 on P2's, where owners have a board.
- **Beyond Finance.** No other board moved in the `finance_seniority` run, and 0 Sales or Operations postings moved
  in the census's 7 edits. The words also feed `_other_occupation` and `_other_work`, which gate every board's claims
  and tier-2 fallback words; the run measured them only on titles that name the new words. `classify` also runs on
  resume lines (4.1.10).
- Both reports recommend no code change: the V3 claim does the job with data, takes the product owners and the UX
  researchers the code edit misses, and leaves the compliance program managers on Finance.

#### 4.3.7 The Finance moves of each option

Open Finance postings that leave Finance. The rows with Product's words come from 4.1 (P2: words as simulated; P7:
B1 for program managers); "without product strategy" drops `product strateg(y|ist|ists)`, as the census recommends.
Combined rows were run together, not added (`scratch\s4c_combined.py`, on the census table's universe: 491 open
Finance postings, all reproduced by `main`).

| Option | Leave Finance | To | By category |
|---|---:|---|---|
| None | 0 | | |
| Product's words, P2 | 170 | Product 170 | Strategy 43, FinTech 39, Investment Banking 38, Risk 24, Corporate Finance 9, Public Markets 8, Private Markets 3, Markets 3, Wealth 2, Banking 1 |
| P2 without product strategy | 134 | Product 134 | Investment Banking 36, FinTech 34, Strategy 22, Risk 20, Corporate Finance 9, Public Markets 7, Markets 3, Wealth 2, Private Markets 1 |
| P7 (B1) | 170 | Product 131, Operations 39 | as P2 |
| P7 without product strategy | 134 | Product 95, Operations 39 | as P2 without product strategy |
| Claim V3 alone | 247 | Product 227, Design 20 | Investment Banking 54, Risk 44, FinTech 43, Wealth 23, Quant 18, Strategy 15, Markets 14, Public Markets 12, Banking 9, Corporate Finance 7, Insurance 5, Private Markets 3 |
| V1 · V2 · PGM alone | 174 · 257 · 102 | V1: Product 137, Design 37. V2: Product 236, Design 21. PGM: Product 102 | 4.3.4 (stored/open) |
| V3 + PGM | 349 | Product 329, Design 20 | |
| P2 + V3 | 338 | Product 318, Design 20 | Investment Banking 78, Risk 56, FinTech 55, Strategy 44, Wealth 23, Quant 18, Markets 16, Public Markets 14, Corporate Finance 14, Banking 10, Insurance 5, Private Markets 5 |
| **P7 without product strategy + V3** (both reports' recommendations together) | **303** | Product 244, Design 20, Operations 39 | Investment Banking 76, Risk 52, FinTech 51, Wealth 23, Strategy 23, Quant 18, Markets 16, Corporate Finance 14, Public Markets 13, Banking 9, Insurance 5, Private Markets 3 |
| Widen `_TECH_OCCUPATION` (`finance_seniority`) | 134 | Product 130, Design 2, Software 1, Healthcare 1 | Risk 91 stored, 4.3.6 |

- **The words and the claim overlap** (`scratch\s4c_overlap.py`). 79 of P2's 170 are also V3 moves. The words take
  only titles with no Finance title word (they sit on Finance because no board names them); V3 takes any Finance
  posting that names its words, Finance title word or not.
  - P2 alone, not V3 (91): Citi "Program Management Lead Analyst" ×8, JPMorgan "Program Management Associate" ×3,
    product-strategy internships ("Summer 2027 Internship Program – Business & Product Strategy Intern" ×4,
    "Residential Energy Product Strategy Intern" ×4, "Product Strategy Intern" ×3).
  - V3 alone, not P2 (148 Product): titles with a Finance word that the flag can't protect. JPMorgan "Senior Product
    Associate" ×9, "Payments XDLC Transformation- Senior Product Associate" ×4, "Lead Technical Program Manager -
    Risk Technology" ×3, "Product Owner - Wholesale Credit Risk – Vice President" ×3, "Wealth - Account Opening
    Product Owner - VP" ×3, "Credit Portfolio Group – Quantitative Product Manager - Associate" ×3.
- The 39 Finance → Operations under B1 are program-management analysts and associates, mostly Citi's and
  JPMorgan's (4.1.6). The program-manager option decides them, not a claim.
- The census table left out 6 "PMT" titles on Finance (4.1.2). 5 of them move (Mastercard "Senior PMT" ×2, Amazon
  "… PMT-ES, AWS Payments and Fraud Prevention" ×3), so P2 moves 175 (`scratch\s4c_pmt_check.py`).
- Every row but "None" takes postings away from Finance profiles, so each is a Finance move for your yes (brief,
  Target state item 1: "Each claim moves postings off Finance, so the user must approve it as a Finance move").

---

## 5. Career structure and levels

This section answers the brief's "Career structure is part of the design" (Phases, item 1), "The shared stage rules
are finance-shaped" (Target state item 1), "Program windows" (Target state item 5) and Part B §2's APM and
rotational programs. The web research covers Canada first (Toronto, Waterloo, Ottawa, Montreal, Vancouver), then US
hubs. The counts are from `E:\product-design-board\phase1\career_research.md` and `finance_seniority.md` Part 2, and
from their scripts' outputs (`phase1\scripts\*.out.txt`, `phase1\data\finance_seniority_*`).

- **Whose reading.** `finance_seniority_levels.py` runs `main`'s `detect_seniority` on all 16,682 stored Product and
  Design postings and reproduces the stored level, stage and label for 16,682 of 16,682. So every count here is
  `main`'s reading.
- **Stored and open.** "Stored" is every posting. "Open" is `status != 'closed'`. A pair is written all/open.
- **Today's placement.** The counts use today's placement. Postings that §3 and §4 move into or out of these boards
  change them, so `finance_seniority_rules.py` runs again on the branch's placement before Phase 3 is approved
  (§13).

### 5.1 How the fields hire

#### Product: level and program words
"`main` reads" is `detect_seniority(title)` with no description (`career_research_stage_check.py`). Stored stages
also apply the description's years rule. The rule names (PL1–PL11) are in 5.4.

| Title shape | What it is | `main` reads | Proposed |
|---|---|---|---|
| Product Manager Intern, Product Management Intern – Summer 2027, APM Intern, Product Owner Intern, PM Co-op (TD "L&H Product Management Intern/Co-op (Winter 2027)") | 10–12-week US summer internship, or a 4-, 8-, 12- or 16-month Canadian co-op | Intern / Co-op (internship) | no change |
| MBA Product Intern (Capital One "MBA Product Intern - Summer 2027"), Amazon PMT intern, Adobe MBA intern | Summer internship for MBA students | Intern; "MBA Intern" reads Summer Associate, with `post_mba` | no change; D18 |
| Associate Product Manager as a program: Google, Uber, Salesforce, Atlassian, Databricks "APM, New Grad (2027 Start)", Roblox "[2027] APM, Early Career", Figma, Disney, Robinhood, Visa | 12–24-month rotational program for new grads, 1–3 rotations | **Senior**, unless a new-grad word is present ("APM, New Grad 2027" reads New Grad). A year doesn't help: "Associate Product Manager (APM) - 2027 Start" reads Senior | New grad, "APM Program" (PL2, PL3 or the shared new-grad rule) |
| Rotational Product Manager (Intuit RPM, Meta RPM) | Rotational program | **Senior** | New grad, "APM Program" (PL2). Meta's 2026–27 posting asks 4+ years, so the years rule makes it Experienced |
| Product Development Program (Capital One PDP), Launch Program (Mastercard), PM Accelerator (Stripe), Associate Product Builder (LinkedIn) | The same shape under another name | PDP: New grad, from "development program". Launch Program: New grad only with "graduate" or a year | no change. 2 open Launch Program titles are on Product. PM Accelerator has 0 open titles |
| Associate Product Manager with no program word ("Associate Product Manager - AI" at Red Ventures, "Associate Product Manager, BMO Global Asset Management") | Entry rung of the PM ladder, 0–2 years | **Senior** | Entry, "Associate PM" (PL4) |
| Apprentice Product Manager (Shopify: 12 months, no degree needed), PM Apprentice (Pinterest, hourly) | Full-time early-career program for career switchers | Intern ("apprentice" is a shared intern word) | New grad, "Apprenticeship" (judgement; D18) |
| Product Manager, University Graduate / New Grad / Early Career; "Program Manager University Grad" (Microsoft); "2027 Early Career Technical Program Manager" (Anduril) | Campus hire, not a program | New Grad | no change |
| Product Analyst, Product Operations Associate, Product Coordinator | Entry analyst and ops roles | Analyst or Associate (entry); Coordinator: Unspecified | no change. career_research would read Coordinator as Entry (judgement); no simulated rule does |
| Product Manager I / PM 1 (Microsoft's PM 1, levels 59–60, is its new-grad level) | Entry PM | **Senior** | Entry, "Level I" (PL5) |
| Product Manager, with no level word | Mid-level at Google and Amazon; at banks, mid-level and often a VP corporate title | **Senior** | Experienced (PL7; judgement, below) |
| Product Manager II / PM 2 | Mid-level | **Senior** (`senior_ic` runs before `mid_ic`) | Experienced (PL7) |
| Technical Program Manager, Program Manager, Product Owner, with no level word | Mid-level execution and scrum roles | TPM and program manager: **Senior**. Product Owner: Unspecified (experienced) | Experienced (PL7). Product Owner: no change |
| Senior, Staff, Principal, Group or Lead PM; Director, Head, VP, CPO | Senior IC or people manager | Senior | no change of stage. New labels for Principal, Director and Head (PL9–PL11) |

**What a bare "Product Manager" means.**
- **Tech companies.** The ladder runs Associate PM → PM → Senior PM → Group PM → Director (Mind the Product,
  Product Leadership). APM is the entry rung, and a "Product Manager" owns an area.
- **Microsoft.** PM 1 is levels 59–60, and new-grad offers land at about L59 (levels.fyi, Simplify). So a bare
  "Product Manager" at Microsoft can be a new-grad job. But only 2 of Microsoft's 137 open product-manager titles have
  no level word (`career_research_teamwords.py`).
- **Banks.** A bank product manager owns a financial product's economics: pricing, P&L, risk and regulation. Many
  postings carry a corporate title: JPMorgan's "Product Manager – Vice President" asks 3+ to 8–10 years.
- **Counts** (open product-manager titles, `career_research_teamwords.py`):

  | Employers | Product-manager titles | With no level word | Of those, read Senior |
  |---|---|---|---|
  | Finance-type employers | 753 | 256 | 243 |
  | Amazon | 332 | 22 | 21 |
  | Microsoft | 137 | 2 | 1 |
  | Google | 79 | 25 | 24 |

- **Judgement:** Experienced is the best single reading for a bare "Product Manager" across these employers. Senior
  should come from Senior, Staff, Principal, Group, Lead, Director, Head or VP.

**"Associate" takes five shapes in these titles** (open Product and Design postings, `career_research_associate.py`;
the finance-type list is the report author's own):

| Shape | Meaning | Open | At finance-type employers | Stored stage today |
|---|---|---|---|---|
| Associate Product Manager / Management / Owner (prefix) | Entry PM, or a new-grad program | 102 | 1 | senior 52, internship 40, new_grad 9, entry 1 |
| Rank suffix: "…Product Management – Associate" (JPMorgan), "…Product Manager, Associate" (Goldman), "Associate, Private Equity Product Manager" (StepStone) | Corporate title after analyst, about 2–5 years (Analyst → Associate → VP) | 30 | 24 | senior 22, entry 7, experienced 1 |
| Senior Associate (JPMorgan "Experience Design, Senior Associate"; Capital One) | Corporate title, mid-level | 88 | 73 | experienced 87, new_grad 1 |
| Associate Director, Associate Creative Director, Associate VP | Senior | 49 | 0 | senior 49 |
| Associate Designer, Associate Product Designer | Entry designer | 29 | 0 | entry 26, new_grad 3 |

The shared rules give a finance "Associate" its category's `associate_stage`: experienced in IB, PE and S&T, entry
elsewhere. On Product, the prefix shape is entry and the bank rank suffix is experienced. Today the suffix shape mostly
reads Senior, because "manager" matches first.

#### Design: level and program words

| Title shape | What it is | `main` reads | Proposed |
|---|---|---|---|
| Product Design Intern, UX Design Intern, UX Research Intern, Industrial Design Intern, Design Co-op (Wealthsimple "Design Intern (Winter 2027)"; Manulife "Winter Co-op 2027 – Product Designer"; Scotiabank "UX/Product Design Internship/Co-op Winter 2027"; SharkNinja "Spring 2027: Industrial Design Co-op") | Internship or co-op | Intern / Co-op | no change |
| UX Research Intern, PhD / MS (Google: "User Experience Research Intern, PhD, Summer 2027", applications before Feb 26, 2027) | Internship for graduate students | Intern | no change |
| UX Design Apprenticeship (Google: 18 months, US, **excludes anyone with or studying for a design degree**, applications Sep 8–21, 2026 for a Feb 2027 start); Design Apprentice Program (Shopify: 12 months, two 6-month placements, remote, US or Canada) | Full-time early-career program | Intern ("apprentice") | New grad, "Apprenticeship" (judgement; D18) |
| Product Designer, University Grad (Meta); "2027 Early Career Associate Product Designer" (Anduril); "UX Designer, Early Career" (Google) | Campus hire | New Grad | no change |
| Design residency or rotational designer program (Method; Datadog's 12-month program, first cohort Jan 2026) | Early-career program | Unspecified ("UX Design Resident" reads experienced) | New grad, "Residency", guarded |
| Fellow, Digital News Design (The New York Times) | One-year early-career fellowship | Unspecified | New grad, "Fellowship", guarded: Northrop Grumman's "Fellow 1/2" is a senior technical rank |
| Associate Designer, Associate Product Designer, Junior Designer, Designer I | Entry | Associate: Entry. Junior: New Grad. Designer I: Unspecified | Designer I: Entry, "Level I" (DL6). Junior: D18 |
| Designer, Product Designer, UX Designer, Industrial Designer, Content Designer, with no level word | Mid-level at big tech; often 0–2 years at agencies and in-house teams (judgement) | Unspecified (experienced) | no change; D22 |
| Senior, Lead, Staff or Principal Designer; Design Manager; Design or Creative Director; Associate Creative Director | Senior IC or manager | Senior. "Principal" reads "Vice President" | no change of stage. New labels (DL2, DL8–DL10) |

#### APM and rotational programs, and where Foothold polls them
Part B §2 asks to check the big_tech sources first. Most program employers are polled already. "Polled by" is
`main`'s pack and source (reader), from `career_research_ats.py`. "Open P / D" counts the employer's open Product and
Design postings. The windows are the 2025–26 cycle, mostly from trackers (APMList, Simplify, Extern), not employers'
own pages.

| Employer | Program | Typical window | Polled by | Open P / D |
|---|---|---|---|---|
| **Canada** | | | | |
| Shopify | Apprentice Product Manager (12 months); Design Apprentice Program (12 months, remote, offices include Ottawa, Toronto, Montreal); internships; Dev Degree | DAP closed Oct 27, 2025 for a Jan 12, 2026 start; summer internships Aug–Sep, fall Jan–Mar | **none** (own site; 16 open postings reach Foothold through lists) | 3 / 0 |
| Wealthsimple | Design Intern (Winter 2027, 8 months, Toronto); PM internships in past terms | Rolling, per term | `shared/fintech` wealthsimple (ashby) | 0 / 3 |
| RBC | RBC Amplify (summer innovation program with design work); UX designer co-ops | Amplify 2027: Sep 7 – Oct 5, 2026 | `finance/canadian_banks` rbc, rbc_early (phenom), rbc_students (workday); `tech/bank_technology` rbc_tech | 13 / 0 |
| TD | L&H (life and health insurance) Product Management Intern/Co-op, Winter 2027 | Per co-op term | td, td_students, td_tech (workday) | 20 / 16 |
| BMO | Product management analyst co-ops (4 months) | Per co-op term | bmo, bmo_students, bmo_tech (workday) | 12 / 0 |
| Scotiabank | Canadian Banking UX/Product Design Internship/Co-op, Winter 2027 | Per co-op term | scotiabank_students, scotiabank_tech (successfactors) | 4 / 0 |
| Manulife | Winter Co-op 2027 – Product Designer; Summer Intern 2027 – Product Design; Summer Intern 2027 – Product Management & Risk Technology | Per term | `shared/pensions_insurance` manulife (workday) | 15 / 3 |
| Atlassian | APM (2 years, two 12-month rotations, remote across North America); APM intern | New grad Jan 17 – Mar 10, 2026; intern open since Sep 2, 2026 | `tech/enterprise_saas` atlassian (own reader) | 14 / 11 |
| Instacart | APM (18 months, 2 rotations, remote US and Canada) | Mar 9–20, 2026 | `shared/consumer_tech` instacart (greenhouse) | 10 / 4 |
| Uber (Toronto office) | APM (2 years, 3 rotations) | Sep 19–26, 2025 | `shared/big_tech` uber (jobs_api) | 36 / 11 |
| **US** | | | | |
| Google | APM and APM intern; UX Design Apprenticeship; UX Designer, Early Career; UX Research intern (BS/MS/PhD) | APM: Sep 22 – Oct 6, 2026 (London Oct 5 – Nov 12); apprenticeship Sep 8–21, 2026 | `shared/big_tech` google (own reader) | 200 / 57 |
| Meta | RPM (18 months, three 6-month rotations; **the 2026–27 posting asks 4+ years**, one source); Product Design Intern; Product Designer, University Grad | RPM: Sep 23 – about Oct 9, 2026 | LinkedIn search only (`tech/big_tech`) | 68 / 51 |
| Microsoft | PM internship; Program/Product Manager University Grad; APM paused | Aug–Oct, and a Jan–Mar wave | microsoft (own reader); microsoft_careers and microsoft_finance (eightfold) | 319 / 33 |
| Salesforce (Futureforce) | APM intern (12 weeks); APM (2-year rotational) | Intern: Jul 13–23, 2026. The 2026 full-time posting was for returning interns only | salesforce, salesforce_early (workday) | 34 / 27 |
| Intuit | Rotational Product Manager (interns feed it) | Intern open since Sep 14, 2026 | `shared/big_tech` intuit (radancy, which robots.txt disallows: the brief's open decision, §11) | 47 / 27 |
| Capital One | Product Development Program (2 years, 2 rotations); MBA Product Intern | Jul 6 – Sep 24, 2026 | capital_one, capital_one_early (workday) | 262 / 47 |
| Databricks | APM, New Grad | Open since Jul 16, 2026 | `shared/ai_infrastructure` databricks (greenhouse) | 51 / 7 |
| Visa | APM (2 years, 4 rotations) | 7 days: Sep 17–24, 2026; winter round Feb 17–23, 2026 | `shared/financial_services_tech` visa (workday) | 47 / 5 |
| Mastercard | Launch Program (its APM under another name) | Late Sep – Oct 6, 2026 | mastercard, mastercard_early (workday) | 138 / 26 |
| Robinhood · Roblox · Figma | APM; Roblox "APM, Early Career"; Figma APM (Early Career) and a product design intern | Robinhood Sep 14 – Oct 14, 2026; Roblox early Sep – Oct 30, 2026; Figma about 3 weeks in Sep 2025 | greenhouse | 11 / 8 · 14 / 10 · 8 / 13 |
| Disney · Stripe · Duolingo · Coinbase | APM; Stripe PM Accelerator (engineers into product); Duolingo APM and APM intern; Coinbase APM intern (no new-grad APM since 2023) | Disney since Sep 15, 2026; Stripe since Sep 15, 2026; Duolingo intern deadline Oct 7, 2026; Coinbase since Sep 9, 2026 | disney, disney_early (workday); others greenhouse | 13 / 52 · 58 / 25 · 14 / 7 · 18 / 3 |
| Pinterest · Block | PM Apprentice (hourly); Square APM (12 months, US only) | Pinterest 4 days: Jul 6–10, 2026; Square closed Feb 27, 2026 | greenhouse | 18 / 5 · 3 / 4 |
| TikTok | PM Graduate (rolling) | From Aug 3, 2026 | **none** (lists only) | 44 / 3 |
| LinkedIn | APM ended in 2025; Associate Product Builder, Sep 2–7, 2025 | n/a | no feed of its own | 0 / 0 |
| **Design employers** | | | | |
| Adobe | Design and UX research interns | No design internship posted as of Oct 9, 2026 | adobe, adobe_university (workday) | 24 / 13 |
| IBM Design | Designcamp for university hires (2015–16 sources) | n/a | LinkedIn search only | 16 / 1 |
| Apple | Industrial Design "accepting portfolios" (any time) | n/a | apple (own reader) | 302 / 250 |
| Logitech | Industrial Designer Intern (Logitech G) | Undated | `tech/devices_iot` logitech (workday) | 4 / 17 |
| GM Design, Ford Design | Interior, exterior and colour-and-materials internships | Undated (2021–22 listings) | general_motors (workday), ford_motor_company (radancy) | 24 / 70, 22 / 36 |
| MillerKnoll · Steelcase · SharkNinja | Product design / CMF & ID intern (12 weeks); ID co-op (Spring 2027); ID co-op (Spring 2027, Jan–Jun) | MillerKnoll Sep–Nov, closes within 45 days | **none** (Workday, SmartRecruiters, lists only) | 0 / 0 · 0 / 0 · 0 / 14 |
| IDEO, frog, Pentagram, R/GA, Wieden+Kennedy | Studio and agency internships | Nov–Dec | **none** | 0 / 0 |

- **No APM program found** at Clio, Lightspeed, 1Password, Cohere, Coveo or Wattpad (all polled; internships and
  co-ops per term), nor current ones at Twitter/X (dormant), Asana, Dropbox, Notion or DoorDash. The Toronto APM
  consortium (TWG, FreshBooks, Shopify, Wattpad, League, ecobee) ran in 2018, and no later intake was found.
- **No Canadian location** was found for Google APM, Meta RPM, Salesforce, Intuit RPM or Capital One PDP.
- **Canadian bank co-ops.** RBC's and Scotiabank's 2027 UX co-ops are on the web, but a stored-title query
  (`career_research_inline.py` part 3, 22 rows, any status) found neither. TD's L&H co-op and Manulife's design co-op
  and PM intern are stored. The query matches title substrings, so the gap is likely, not proven.
- **Program names don't last.** Meta's RPM now asks 4+ years, LinkedIn's APM ended in 2025, Microsoft's APM is
  paused and Coinbase has had no new-grad APM since 2023. So no window names a program as permanent (5.6).
- The packs for these employers are §8's.

#### Credentials
**Neither field is licensed, so there is no `licences` block** (D11).

Description counts are over open postings with a stored `job_text` row: 6,047 Product and 2,867 Design, some of them
empty (`career_research_creds.py`). In the census, 5,607 Product and 2,580 Design open postings have `desc_len > 0`.

| Credential | Product | Design | Reading |
|---|---|---|---|
| "portfolio" anywhere | 1,175 (19.4%) | 808 (28.2%) | In Product it is mostly a product or investment portfolio (judgement) |
| Asks to submit, include, link or share a portfolio | 12 (0.2%) | 133 (4.6%) | Design's real "portfolio required" signal |
| Case study / case studies | 24 (0.4%) | 25 (0.9%) | |
| Behance / Dribbble | 0 | 2 (0.1%) | Rare in postings: a resume signal instead (§9) |
| PMP | 317 (5.2%) | 17 (0.6%) | Project and program manager roles |
| CSPO / PSPO / SAFe POPM | 21 (0.3%) | 0 | Product Owner and bank or enterprise roles, "preferred" |
| CSM / scrum master | 42 (0.7%) | 2 (0.1%) | |
| Google UX certificate | 0 | 0 | |
| NN/g (Nielsen Norman) | 0 | 1 | |
| NCIDQ / ARIDO / registered interior designer | 1 | 5 (0.2%) | Interior design, a licensed building trade |
| MBA | 304 (5.0%) | 9 (0.3%) | MBA PM tracks |
| HCI | 10 (0.2%) | 117 (4.1%) | A UX degree word |
| Figma | 64 (1.1%) | 431 (15.0%) | A tool, not a credential |

- **The web agrees.** Agile certifications show as "preferred" in product-owner postings. UX certificates are not
  required: the portfolio and how the candidate explains it decide. BLS says graphic and industrial designers need a
  bachelor's degree and a portfolio. The norm is 2–3 end-to-end case studies for UX and product design, and 4–6
  projects for graphic design. Apple's industrial design team wants physical projects with process sketches.
- **Interior design is title-protected in Ontario.** Only ARIDO Registered members may use "Interior Designer", and
  NCIDQ is one route to it. It is a licensed building trade, not this board. 11 open Design titles say "interior
  designer", and some are vehicle interiors at GM ("Senior Interior Designer" in Shanghai), which is industrial
  design.
- **UX research interns are often graduate students.** Google's UXR intern tracks are PhD and MS, and MathWorks asks
  for master's level or above.

#### Recruiting calendar
Product hiring follows a fall calendar, with a head start in July and a second round in winter. Windows often last one
to four weeks, and some only days. All dates are the 2025–26 cycle's pattern.

| Window | Who | Source |
|---|---|---|
| Early July | Salesforce APM intern (Jul 13–23, 2026), Capital One PDP (Jul 6 – Sep 24), Databricks APM (from Jul 16), Pinterest PM Apprentice (Jul 6–10) | APMList |
| August | Microsoft PM intern (from Aug 3) and new-grad PM; TikTok PM graduate; Amazon and Capital One PM interns; Meta RPM in past years (Aug 18, 2025) | APMList, Simplify, Extern |
| September to mid-October (the peak) | Google APM and intern (Sep 22 – Oct 6), Meta RPM (Sep 23 – Oct 9), Uber APM, Visa (7 days), Mastercard, Robinhood, Roblox, Figma, Disney, Stripe, Intuit; Coinbase and Atlassian interns; Duolingo intern (deadline Oct 7) | APMList, Extern |
| August to October | Big-tech UX and product design internships (Google, Apple, Meta, Microsoft, Amazon, Spotify); Figma in September | Extern |
| September to November | Industrial design internships (MillerKnoll); Nike design roles (deadline about late September); game studios (Epic, Riot, EA, Ubisoft) | Extern |
| November to December | Studios and agencies (IDEO, frog, Pentagram, R/GA, W+K) | Extern |
| January to March | Winter APM round: Atlassian (Jan 17 – Mar 10, 2026), Square (closed Feb 27), Instacart (Mar 9–20), Visa (Feb 17–23), Microsoft's second wave; in-house brand design (Nike, Airbnb, Spotify); Google UXR PhD intern deadline Feb 26, 2027 | APMList, Simplify, Extern, Google |
| Canadian co-op | Winter term (Jan 11 – Apr 30, 2027): Waterloo cycle 1 applications Sep 17, interviews Sep 21 – Oct 6, 2026. Spring term (May 10 – Aug 20, 2027): applications Jan 19, interviews Jan 22 – Feb 9, 2027. Fall term (Sep 8 – Dec 23, 2026): recruits May–Aug. U of T PEY (12–16 months): postings from mid-September | Waterloo, U of T |
| Start dates | US summer internships May–June (10–12 weeks); APM July–September (Instacart early August, Salesforce August); Meta RPM March or September; Google UX apprenticeship February; Shopify DAP January | sources above |

- New-grad PM hiring follows the same fall cycle as APM. By November, returning interns have filled many of
  Microsoft's slots.
- Canadian design schools' work terms: Waterloo's Stratford GBDA has four co-op terms (Year 3 fall and spring, Year 4
  winter and spring). Carleton's Industrial Design has 5 co-op terms or a 12-week internship. Sheridan's Industrial
  Design has one May–August term after year 3 (360 hours). OCAD U has upper-year placements, not classic co-op.

#### Hours
- **Product is standard full-time.** 356 of 9,011 open Product postings carry any `facts.hours` value. 258 of them
  read `part_time`, and 251 of those 258 are Capital One's pay sentence ("Salaries for part-time roles will be
  prorated…"), not part-time jobs. Across all boards, 1,953 open Capital One postings read part-time this way
  (D45; §15).
- **Design is mostly full-time.** 175 of 5,546 open Design postings carry hours: 71 full-time, 54 part-time (44 of
  them Capital One's sentence) and 44 temporary.
- **Hours words in open titles** (`career_research_hours.py`):

  | Word | Product | Design |
  |---|---|---|
  | contract / contractor | 25 | 38 |
  | full-time | 13 | 3 |
  | fixed term | 8 | 11 |
  | maternity / parental cover | 6 | 2 |
  | part-time | 5 | 2 |
  | temporary / temp | 1 | 6 |
  | freelance | 0 | 2 |

- **Self-employment** is common among designers (BLS: 20% of graphic designers; Job Bank Nova Scotia: 34% of graphic
  designers and illustrators). But freelancers don't apply through ATS postings, so it barely shows in Foothold.
- **Judgement:** no hours work is needed for Product or Design. The Hours chips from Healthcare's design (its D15) already show Contract and
  Temporary.

### 5.2 Postings with no level word
**Product: 3,651 of 10,387 stored (35%), 3,248 of 9,011 open. Design: 2,049 of 6,295 (33%), 1,809 of 5,546 open.**
Together that is 5,700 of 16,682 stored (34%). On Healthcare it was 3,801 of 5,556 open postings (68%).

A title counts as having no level word when no `TITLE_RULES` word and no year is left after the occupation words are
neutralised: "product/program/project manager(s)/management", "product owner(s)" and "art director(s)"
(`finance_seniority_rules.py` §5).

| Board | No level word | `main` reads them | Years asked |
|---|---|---|---|
| Product | 3,651 / 3,248 | Senior (`senior_ic`) 3,540; Unspecified, experienced 95; Rotational Analyst, new_grad 12; Unspecified, Senior from years 4 | none 2,853; under 2: 67; 2–4: 253; 5+: 478 |
| Design | 2,049 / 1,809 | Unspecified, experienced 1,845; Unspecified, Senior from years 175; Senior (`senior_ic`) 20; Executive Director 9 | none 1,647; under 2: 57; 2–4: 162; 5+: 183 |

- **The two boards fail in opposite ways.** On Product, the word "manager" makes them Senior. 3,497 of 9,011 open
  Product postings (39%) are Senior only because the title says product, program or project manager
  (`career_research_nolevel.py`). Only 74 open Product postings carry level Unspecified. So a student profile on
  Product sees 8,050 of 9,011 open postings (89%) as Senior.
- **Design has Healthcare's problem.** 1,788 of 5,546 open Design postings (32%) carry level Unspecified: 1,502 read
  Unspecified (experienced), 134 Experienced from 2–4 years asked and 152 Senior from 5+ years. So for a student,
  1,502 open postings take the 8-point "Experience required" penalty only because no level word is there and under
  2 years are asked (D22).
- Samples: `stripe:8311067 'Program Manager, Go-to-Market Experience and Productivity' @ Stripe`,
  `zapply_newgrad27:f06ee278e295608b 'SEO Product Manager' @ Zillow`, `steris:55596 'Healthcare Designer' @ STERIS`,
  `aptiv:…J000703849-1 'Mold Designer' @ Aptiv`.

### 5.3 What `main` reads wrong today

**The mechanism.** `detect_seniority` (`intel/seniority.py` ~59) works in this order:
1. It strips `_TEAM_NAME`.
2. It tries the board's `stage_rules`. Product and Design have none.
3. It runs the shared `TITLE_RULES` in order, and the first match wins: spring_week, summer_associate,
   summer_analyst, off_cycle, co_op, intern, rotational, graduate_analyst, new_grad, managing_director,
   executive_director, vp, avp, senior_associate, senior_analyst, **senior_ic**, associate, analyst, mid_ic.
4. With no match, the years asked decide: 5+ is Senior, 2–4 is Experienced, and anything else is Unspecified at stage
   experienced.

**What a wrong stage costs.** The points come from `intel/scoring.py` ~162-185, for the default target stages
(internship and new_grad):

| Stage | Stage points (of 20) | Penalty for a student |
|---|---|---|
| internship, new_grad | 20 | none |
| entry | 16 | none |
| experienced | 4 | 8, "Experience required" |
| senior | 0 | 25, "Senior role" |

So a bare "Product Manager" read Senior instead of Experienced costs a student 21 points. An "Associate Product
Manager" read Senior instead of Entry costs 41.

**Stored stages today.** Product, open: senior 8,050, internship 670, experienced 160, new_grad 85, entry 46. Design,
open: senior 2,758, experienced 1,825, internship 798, new_grad 100, entry 65.

**The word that set each stored level** (all stored postings, `finance_seniority_levels.jsonl`):

| Board | Rule (stored) | Word: count |
|---|---|---|
| Product | `senior_ic` (7,538) | **manager 4,206**, senior 1,867, sr 704, staff 483, lead 265, distinguished 10, other 3 |
| Product | `vp` (1,158) | **principal 861**, vice president 233, vp 45, senior vice president 14, svp 5 |
| Product | `executive_director` (494) | director 401, senior director 83, executive director 10 |
| Product | `managing_director` (22) | head of 8, chief 7, **coo 5** (team names), managing director 1, cfo 1 |
| Product | `rotational` (26) | **development program 21**, management trainee 4, trainee 1 |
| Product | no rule (100) | Unspecified 99; New Grad from a year in the title 1 |
| Design | `senior_ic` (2,259) | senior 985, staff 349, lead 339, sr 285, **manager 248**, iii 49, iv 2, head 2 |
| Design | `vp` (458) | **principal 380**, vice president 51, vp 21, svp 3, senior vice president 3 |
| Design | `executive_director` (252) | director 230, senior director 15, executive director 7 |
| Design | no rule (2,043) | Unspecified 2,020; New Grad from a year in the title 23 |

**Every level that looks wrong** (stored, all/open; "wrong" is the report author's judgement of the title; the fix
names a rule in 5.4):

| Misread on `main` | Cause | Count | Samples | Fix |
|---|---|---|---|---|
| Product, program or project manager with no other level word reads **Senior** | `senior_ic` holds `\bmanager\b`, so the occupation is a level word | 3,614 Senior of the 3,631/3,247 that PL7 takes | `amd:91231 'Enterprise AI Product Manager' @ AMD`; `lowe_s:JR-02588583 'Product Manager-Global Merchandising' @ Lowe's`; `amazon_tech:10582353 'Technical Program Manager II, ICON' @ Amazon` | PL7 |
| Associate Product or Program Manager reads **Senior** | `senior_ic` runs before `associate` | 72 Senior, 1 Unspecified (the 73/59 PL4 takes). Open titles naming APM: 53 of 100 read Senior (51 through "manager", 2 through "principal"), 33 Intern, 9 New Grad, 4 Experienced, 1 Entry | `simplify_newgrad:6435e1ac-… 'Associate Product Manager' @ Abbott`; `zapply_newgrad27:906fe8726452a8c0 'Associate Product Manager - Battery Energy Storage Systems' @ Eaton` | PL4 |
| "Product/Program Manager I or 1" reads **Senior**; "II" reads Senior, not Experienced | `senior_ic` runs before `mid_ic` | PM I: 57/53 | `northrop_grumman:1340074883971 'Program Manager 1'`; `sierra_nevada:…R0030578-1 'Supply Chain Program Manager I'` | PL5; PL7 for II |
| A bank's "Product Manager, Associate" reads **Senior** | "manager" matches before `associate` | 24/22 (22 `senior_ic`, 2 `managing_director`) | `goldman_sachs:185197 'Transaction Banking, Channels Product Manager, Associate' @ Goldman Sachs` | PL6 |
| APM and rotational PM programs read **Senior** | Nothing reads "APM" or "RPM"; `rotational` needs analyst, program, associate or development program after it | 6 of the 8 PL2 takes | `disney:…10160554 'Associate Product Manager Program' @ Disney`; `vansh_newgrad27:2134170c-… 'Associate Product Manager Program' @ Perplexity` | PL2 |
| A dated PM title reads **Senior** | `main`'s "dated program in title" rule runs only when no level matched, and "manager" matches first | 2/2 | `amazon_tech:10490981 '2027 Amazon Leadership Accelerator (ALA) - Product Manager Full Time'`; `amazon_tech:10509770 'Product Manager Technical (PMT) - 2027'` | PL3 |
| "Development Program Manager" reads **Rotational Analyst** | `rotational` matches `\bdevelopment program(me)?\b` | 18 titles carry that level: 16 at new_grad, 2 at experienced from years asked. M&T Bank's 3 "Management Development Program" cohort titles read right | `lockheed_martin:996477030970 'Development Program Manager'`; `flex:…WD231326-2 'New Product Development Program Manager'` | PL7 takes 12, the only moves to a later stage. 6 with a senior word stay (D17) |
| Capital One's "Principal Associate" (a mid-level band) reads **Vice President / senior** | `vp` holds `\bprincipal\b` | 11/10 (4 product, 7 design) | `capital_one:…R242630-1 'Principal Associate, Product Management'`; `capital_one:…R244701-1 'Product Designer, Principal Associate Level'` | PL8, DL7 |
| Art Director reads **Executive Director / senior** (a mid-level occupation, judgement) | `executive_director` = `(senior )?director` | 9/5; Associate Art Director 2/2 | `apple:200671258 'Art Director, Design' @ Apple`; `jpmorgan:210794314 'Associate Art Director / Graphic Designer - Brand Team'` | DL5, DL3 |
| French and German intern words are unknown | `intern` knows only English words | 22/20 titles carry stage, stagiaire, alternance, alternant, werkstudent or praktik. `main` reads (stored) 9 Unspecified, 2 Senior, 7 Intern, 2 New Grad, 1 Experienced; the run lists 21 of the 22 | `ubisoft:744000157790349 'Stage Level Designer - 6 mois (F/H/NB)'`; `novartis:…REQ-10047858 'PRODUCT MANAGER (H/F) en alternance'` | PL1, DL1 take 15/14 (5 product, 10 design) and change 11 |
| "Designer/Researcher/Artist I or 1" reads Unspecified | no `TITLE_RULES` word for "I" | 12/9 (9 change) | `garmin:19863 'Product Designer 1' @ Garmin`; `electronic_arts:216314 'Experience Designer I - - EA SPORTS FC'` | DL6 |
| "associate intern" reads **Summer Associate** and sets `post_mba` (the 15-point "MBA / post-MBA program" penalty for an undergraduate, `scoring.py` ~316-322, and the note "Summer Associate programs usually target MBA students") | `summer_associate` holds `associate intern(ship)?` | 0 stored P&D titles. 1 candidate-word title in other: `'Product Strategy & Development Associate Intern' @ Cohen & Steers`. Title only: "Product Associate Intern" (other today) and "Design Associate Intern" (Design) | The 44 stored P&D Summer Associates are 40 "MBA Intern" titles (right), 2 Navy Federal "Summer Associate Internship - Technical Product Analyst" and 2 "Summer 2027 Associate" | PL1, DL1 |
| A level word that names a team: "Early Career Program Manager", "Internship Program Manager", "Campus - Full Time - Product Manager" | `new_grad` and `intern` read the team word as the level | 33 open Product titles hold such a word. In the output, 4 read New Grad wrongly (Notion's, Citi's two, Marvell's), 4 Applied Materials "Internship Program Manager" read Intern, 2 American Express campus hires read Senior. Roblox's and Anduril's early-career APM and TPM titles read right | `citi_early:…24811350 'Vice President, Asia Early Career Program Manager - Maternity Cover…' @ Citi` (New Grad); `american_express:26013779 'Campus - Full Time - Product Manager - 2027 (UK - London)'` (Senior) | D20 |
| Label only: Principal PM or Designer reads "Vice President" | `vp` holds `principal` | 860/775 product, 374/338 design | `amazon_tech:10522055 'Principal Product Manager - Technical, External Services, AWS, GenAIUX'` | PL11, DL10 |
| Label only: Director reads "Executive Director"; Creative Director too | `executive_director` | 484/411 product, 164/143 design; Creative Director 67/51 | `oracle:346036 'Senior Director, Product Management'`; `mercury:6225753004 'Creative Director - Brand Narrative'` | PL10, DL9, DL2 |
| Label only: Head of, Chief read "Managing Director" | `managing_director` holds `head of`, `chief`, `\bc[efio]o\b` | 8/7 product, 25/23 design | `bitgo:8842015002 'Head of Design, Product Design'` | PL9, DL8 |
| A team name "COO" reads Managing Director | `\bc[efio]o\b`; `_TEAM_NAME` strips only "office of the C[EFIOR]O", so "Office of the CPO" stays too | 5 product (PL6 fixes 2) | `jpmorgan 'Lead Technical Program Manager - GT COO Strategic Program Execution'` | 3 stay (D17) |
| The stage line says "entry level **in finance**" | `scoring.py` ~170 adds "in finance" to any entry level that isn't a board level; level `analyst` adds "Analyst is the entry level in finance" | 58 product + 78 design stored entry postings (`analyst` 41 + 9, `associate` 17 + 69) | | D44 |

These read right: Product Manager Intern, Design Intern and Co-op; New Grad PM; UX Researcher II (`mid_ic`); Senior,
Staff and Lead Designer; "MBA Intern" (Summer Associate). A bank's "VP, Product" and JPMorgan's "Product Manager - Vice
President" read `vp`, Vice President, stage senior: the bank's own title, and the stage `main` gives every finance VP.

### 5.4 Proposed `stage_rules`
The levels map onto today's five stages, as Healthcare's design did (its D13), with no sixth stage. They go in each board's
`stage_rules.levels` in `config/taxonomy.json`. They run before `TITLE_RULES`, only on that board's own postings, and
a level is skipped when its `unless` matches. The loader wraps each fragment in word boundaries, as for every taxonomy
pattern. The shared `TITLE_RULES` are not edited, as the brief says.

The rules and counts are `finance_seniority.md`'s (full JSON with every `unless`:
`E:\product-design-board\phase1\data\finance_seniority_proposed_stage_rules.json`). Two shorthands:
- `SENIOR` = senior, sr, staff, principal, lead(s), head(s), director(s), vp, svp, evp, avp, vice president, chief,
  group, distinguished, executive, iii, iv.
- `EARLY` = intern(s, ship, ships), co-op(s), new grad(uate)(s), graduate, junior, jr, entry level, early career,
  apprentice…, trainee, rotation(al), mba, summer, university, campus, student(s), fellow(ship), placement,
  off-cycle, work term.

A title with an `EARLY` word skips the board's PM rules and falls through to the shared intern and new-grad rules,
which read most of them right (one gap is listed below). career_research's draft (its §8) covers fewer titles. It
differs in three ways, each put to you: it adds apprenticeship, residency and fellowship levels; it reads Junior as
Entry; and its bank-rank rule is wider. Its extra levels are not simulated (marked below).

"Fires" is stored, all/open. "Stage changes" counts all stored postings.

**Product (`product.stage_rules.levels`), in order:**

| # | Level / stage / label | Title (unless) | Fires | Stage changes |
|---|---|---|---|---|
| PL1 | `intern` / internship / Intern | associate intern(s), stagiaire(s), (en) alternance, alternant(e), werkstudent, praktikum/praktikant, "stage … N mois", stage ingénieur (unless mba, summer associate) | 5/4 | 3 |
| PL2 | `apm_program` / new_grad / APM Program | "(APM)", "(RPM)", APM or RPM program, rotational product manager or management, product management rotation(al) program, associate product manager program (unless senior, sr, staff, principal, lead, director, head, intern, co-op) | 8/2 | 6 |
| — | `apprenticeship` / new_grad / Apprenticeship (career_research; **not simulated**) | apprentice product manager, product manag… apprentice(ship), PM apprentice (unless "manager, apprenticeships") | 1 open title (Liminal) | 1 open (Internship today) |
| PL3 | `new_grad` / new_grad / New Grad | a year 2025–2032 (unless `SENIOR` + `EARLY`): `main`'s own "dated program" rule, which "manager" blocks today | 2/2 | 2 |
| PL4 | `associate_pm` / entry / Associate PM | associate (technical) product, program or project manager(s); associate product owner or lead (unless `SENIOR` + `EARLY`) | 73/59 | 73 |
| PL5 | `pm_one` / entry / Level I | product, program or project manager I or 1 (unless `SENIOR` + `EARLY`) | 57/53 | 57 |
| PL6 | `pm_associate_band` / experienced / Associate | product, program or project manager, then ", - : – —", then associate: the bank band (unless `SENIOR` + `EARLY`) | 24/22 | 24 |
| PL7 | **`pm` / experienced / Experienced** | (technical) product, program or project manager(s) (unless `SENIOR` + `EARLY` + associate, manager of, managing, a year) | **3,631/3,247** | **3,626** |
| PL8 | `principal_associate` / experienced / Principal Associate | principal associate(s): Capital One's band | 4/4 | 4 |
| PL9 | `head` / senior / Head / Chief | head(s) of, chief (unless chief of staff, `EARLY`) | 8/7 | 0 (label) |
| PL10 | `director` / senior / Director | (associate, senior, sr or group) director (unless executive or managing director, `EARLY`) | 484/411 | 0 (label) |
| PL11 | `principal` / senior / Principal | principal (unless `EARLY`) | 860/775 | 0 (label) |

**Design (`design.stage_rules.levels`), in order:**

| # | Level / stage / label | Title (unless) | Fires | Stage changes |
|---|---|---|---|---|
| DL1 | `intern` / internship / Intern | as PL1 | 10/10 | 8 |
| DL2 | `creative_director` / senior / Creative Director | (associate, group, executive, senior or sr) creative director(s) | 67/51 | 0 (label) |
| DL3 | `associate_art_director` / entry / Associate Art Director | associate art director(s) (unless senior, sr, staff, principal, lead, head, vp, vice president, chief, group, executive) | 2/2 | 2 |
| DL4 | `senior_art_director` / senior / Senior Art Director | senior, sr, lead, principal, group or executive art director(s); "manager, (creative) art director" | 6/5 | 0 (label) |
| DL5 | `art_director` / experienced / Art Director | art director(s) (unless `EARLY`, the senior words, manager) | 9/5 | 9 |
| DL6 | `designer_one` / entry / Level I | designer(s), researcher(s), writer(s), artist(s) or illustrator(s) I or 1 (unless `SENIOR` + `EARLY`) | 12/9 | 9 |
| DL7 | `principal_associate` / experienced / Principal Associate | principal associate(s) | 7/6 | 7 |
| DL8 | `head` / senior / Head / Chief | as PL9 | 25/23 | 0 (label) |
| DL9 | `director` / senior / Director | as PL10 | 164/143 | 0 (label) |
| DL10 | `principal` / senior / Principal | as PL11 | 374/338 | 0 (label) |
| — | `apprenticeship`, `residency`, `fellowship` / new_grad (career_research; **not simulated**) | UX, product or design apprentice(ship) (unless engineer, engineering, CAD); design, UX or product design residency, design resident (unless resident engineer, residential, residency program manager); design fellow(ship), "Fellow, … Design" (unless a number or rank such as "Fellow 1/2", Senior or Technical Fellow, program manager) | Apprenticeship 0 (the 3 open design "apprentice" titles are Synopsys chip and CAD apprenticeships). Residency 0 (the 1 open title is HPE's "Resident Engineer"). Fellowship: The New York Times' design fellows | Fellowship: Unspecified → New grad |

- **The years rule still wins.** On an entry or new-grad level, 3+ years asked reads Experienced. So "3+ years" on an
  APM, or Meta RPM's "4+ years", reads Experienced.
- **Design's senior rules mostly fire on engineers.** Design's `principal` and `director` rules mostly fire on
  hardware engineers that the broad word "design" places on Design, for example `rtx:…01878732 'Principal Power
  Design Engineer'`. That is a placement problem, and §4.2 narrows the word.
- **Optional, text only:** board levels `associate` and `analyst` at entry would drop "in finance" from the stage line
  for 57 of 58 Product and 75 of 78 Design entry postings (D44).

**Stage before → after on all stored postings** (`finance_seniority_rules.py` §2):

| Board | Before → after | All/open |
|---|---|---|
| Product | senior → experienced | 3,657/3,270 |
| | senior → entry | 114/97 |
| | new_grad → experienced (the "Development Program Manager" misread) | 12/12 |
| | senior → new_grad | 8/4 |
| | senior → internship | 2/2 |
| | experienced → internship | 1/1 |
| | experienced → entry | 1/1 |
| | **total stage changes** | **3,795/3,387** |
| | unchanged | senior 5,435, internship 780, experienced 217, new_grad 102, entry 58 |
| Design | senior → experienced | 16/11 |
| | experienced → entry | 9/7 |
| | experienced → internship | 8/8 |
| | senior → entry | 2/2 |
| | **total stage changes** | **35/28** |
| Label only | Product 1,352/1,193 (principal 860, director 484, head 8); Design 636/560 (principal 374, director 164, creative director 67, head 25, senior art director 6) | |

- **Moves to a later stage.** The only ones are the 12 "Development Program Manager" postings that `main` misreads as
  Rotational Analyst / new_grad.
- **On Product, 15 of the senior Associate PM and PM I titles go to Experienced, not Entry.** PL4 and PL5 change 130
  stages, 129 of them from Senior (72 + 57). 114 land on Entry. The other 15 ask 3+ years, so the years rule makes
  them Experienced. That is why senior → experienced (3,657) is 15 more than the 3,642 that PL7, PL6 and PL8 move.
- **Titles that §4 may move in.** 7,335 candidate-word titles now on other boards were read with the rules of the
  board they name, without the candidate list's broad words. The board is guessed from the word; §4's census decides
  the real one.
  - 3,918 have product words. The rules fire on 956 (director 319, pm 307, principal 256, head 55, new_grad 6,
    associate_pm 5, pm_one 4, intern 2, principal_associate 2). Stage changes: senior → experienced 309, senior →
    entry 7, experienced → new_grad 1, new_grad → internship 1.
  - 3,417 have design words. The rules fire on 260. Stage changes: senior → experienced 22, experienced → entry 2,
    senior → entry 2, experienced → internship 1.
- **Badges.** `BOARD_LEVEL_BADGES` in `intel/scoring.py` is code, and lists only Healthcare's level keys. So the new
  levels show no badge, unless they reuse a Healthcare key or the dict gains entries (D21).
- **The decisions.** The bare-PM rule PL7 is D17. PL1–PL5 and DL1, DL6 are D18. PL6,
  PL8, DL3, DL5 and DL7 are D19. The label-only rules are D21. Apprenticeship,
  residency and fellowship are D18.

**PL7's alternatives** (D17). Of the 3,631 postings PL7 takes, 2,840 ask no years, 62 under 2, 268 ask 2 to 4 and
461/406 ask 5 or more. B, a code change in `intel/seniority.py`: a board level with no stage falls through to
`main`'s years path. Then 461 stay Senior, 268 read Experienced and 2,902 read Unspecified (stage experienced), so
3,170 get the stage they get under PL7. C: keep Senior.

**What these rules don't fix.** These come from the shared `TITLE_RULES` and `_TEAM_NAME`, which the brief says not to
edit for one board (D17):
- **6 "Senior … Development Program Manager" titles still read Rotational Analyst**, for example
  `snowflake:450d9669-… 'Sr. Certification Development Program Manager'` and `applied_materials:…R2627331 'Customer
  Service Development Program Manager IV - ETCH (E4)'`. PL7 skips them on the senior word.
- **3 "COO" team-name labels**, and "Office of the CPO", which `_TEAM_NAME` doesn't strip.
- **American Express's 2 "Campus - Full Time - Product Manager - 2027" titles still read Senior.** PL3 and PL7 skip
  them on "campus" (an `EARLY` word), and the shared new-grad rule knows only "campus hire" and "campus recruit".
  Taking "campus" out of PL3's `unless` would read them New grad (judgement; D20).
- **Bare "APM" and "RPM" are left alone on purpose.** In stored titles, "APM" also names Amazon's "APM Twitch/Insights"
  software teams, GE's "Asset Performance Management", Johnson & Johnson and Sanofi field roles, and Amazon's "APM
  Stores". "RPM" is remote patient monitoring in all 4 open titles (Tempus AI, Takeda, Johnson & Johnson). Only
  "(APM)", "(RPM)" and "APM program" are read.

### 5.5 Words that mean two things
"Open titles" are open Product / Design titles (`career_research_words.py`, `_teamwords.py`, `_programs.py`; samples
seed 20261031). "Stored" figures are all/open in stored P&D titles with `main`'s level (`finance_seniority_rules.py`
§6). The proposal is the mapping put to you.

| Word | Meanings | Counts | Samples | Proposal |
|---|---|---|---|---|
| **manager** | The occupation (product, program or project manager), not a level; or a people manager ("Manager, X", "Design Manager") | Stored occupation 8,657/7,606 (`main`: `senior_ic` 7,140, `vp` 1,048); people-manager forms 4,868/4,246 | `capital_one:…R1000678 'Manager, Product Design'` (a people manager) | The occupation reads Experienced (PL7); "Manager, X" and "manager of" stay Senior. Capital One's "Manager, Product Management" is a mid-level band and stays Senior |
| **program manager** | Microsoft's historical PM title; TPM (engineering execution); business, ops, supply-chain and HR program managers (talent, L&D, residency or fellowship program manager) | 3,713 open Product titles say it (41% of Product; 4.1.6 counts 3,743 program-manager titles of every form); TPM 1,325 | `amazon_tech:10543104 'Sr Technical Program Manager, Prime Video Advertising'`; `gdit:…RQ217057-1 'Help Desk Program Manager' @ GDIT`; `mount_sinai_health_system:3043674 'Residency Program Manager - Pulmonary'` | Where they belong is §4.1's program-manager decision; their level is PL7 |
| **program** | A cohort (APM, graduate, internship or development program); or the occupation | Stored cohort 73/66; program manager or management 4,155/3,719; technical program 1,609/1,444. "development program" is both (23/22) | M&T Bank "Management Development Program" (cohort); Lockheed "Development Program Manager" (occupation) | PL2 reads cohorts; PL7 reads the occupation |
| **associate** | APM entry rung; bank corporate rank (experienced); Associate Director or Creative Director (senior); Associate Designer (entry); Associate Intern | 259 / 148 open titles. Stored: Associate PM 151/117 (`main`: `senior_ic` 81, intern 41, new_grad 17, senior_associate 7); Senior or Principal Associate 121/98; Associate Director 39/36; Associate Creative or Art Director 16/14 | 5.1 | PL4 (entry), PL6 and PL8 (experienced), DL3 (entry); the rest unchanged |
| **early career, university, campus, internship program** (as a team) | The posting's level; or the team the job serves | 33 open Product titles | `citi_early:…24811350 'Vice President, Asia Early Career Program Manager…'` (New Grad, wrong); `applied_materials:…R2631565 'Internship Program Manager - B4'` (Intern, wrong) | D20 |
| **rotation, rotational** | A rotational program (new grad); "rotating shifts"; RPM as remote patient monitoring | 1 / 0 open titles; stored 2/1 | `mastercard:…R-292562-2 'Global Markets, Account Management & Product Management, Launch Program (Rotational) – 2027, Istanbul'` (New Grad, right) | PL2 reads "rotational product manager"; "RPM" alone is never read |
| **principal** | Senior IC (Principal PM or Designer), labelled "Vice President" today; Capital One's "Principal Associate" band (mid-level) | Stored 1,258/1,134 vs 11/10 | 5.3 | PL11 and DL10 relabel; PL8 and DL7 read the band Experienced |
| **lead** | Senior IC (Lead Designer, Lead PM, 361/317 stored); the owner of the product or design ("Product Lead", "Design Lead", 118/98); team lead (15/12) | 344 / 376 open titles; no "Lead Generation" in P&D titles | | Senior, unchanged |
| **staff** | Senior IC (Staff PM or Designer); Chief of Staff (8/8 stored, reads Managing Director) | 556 / 394 open titles; stored 1,097/950 | | Senior, unchanged; PL9 and DL8 skip "chief of staff" |
| **director** | Director of Product or Design (senior); Art Director (an occupation, mid-level, 19/13 stored); Creative Director (67/51); Associate Director (39/36) | stored, all/open | `apple:200671258 'Art Director, Design'` | DL5 reads Art Director Experienced; DL2 relabels Creative Director |
| **junior** | An entry-level job | 8 / 16 open titles say junior or jr; `main` reads "junior" as New Grad | | D18 |
| **apprentice** | A PM or design apprenticeship (early-career, full-time); a chip "Design Engineer Apprenticeship"; a program manager of apprenticeships | 2 / 3 open titles | `simplify_newgrad:eba5276d-… 'Product Management Apprentice' @ Liminal` (Intern); `synopsys:102251697520 'Digital Design Engineer Apprenticeship'`; `blue_origin:…R74560 'Senior Program Manager, Apprenticeships'` | D18 |
| **fellow** | An early-career fellowship (The New York Times); a senior technical rank (Northrop Grumman "Fellow 1/2"); a fellowship program manager | 4 / 5 open titles | `the_new_york_times:4740363005 'Fellow, Digital News Design'`; `northrop_grumman:1340073823806 'System Life Cycle Design & Integration- Fellow 2'` | D18 |
| **resident, residency** | A design residency; Resident Engineer; a residency program manager | 1 / 1 open titles | `hpe:…1204155 'Resident Engineer – Service Provider Routing and Switching Design Consultant'` (Design) | D18 |
| **stage** (French) | An internship ("Stage 6 mois"); English "stage" ("early-stage") | 22/20 stored titles carry a French or German intern word | `ubisoft:744000156028462 'Product Manager AI Assistant – Stage (6 mois) Janvier 2027'` | PL1 and DL1 read "stage" only with "N mois" or "ingénieur" |
| **APM, RPM** | Associate or Rotational Product Manager; Application or Asset Performance Management; Remote Patient Monitoring | APM: 2 / 1 open titles as a word | `datadog:7989348 'Staff Product Designer, APM'` | Only "(APM)", "(RPM)" and "APM program" are read |
| **MBA** | An MBA PM internship; a post-MBA PM role | 66 open Product titles | `capital_one_early:…R244815-1 'MBA Product Intern - Summer 2027'` sits on **Finance** | D18 |
| **product** | A software product; a financial product (cards, mortgages, deposits, insurance) | 99 / 0 open titles with a finance-product word | `bmo:…R260028844 'Senior Product Manager, Commercial Banking' @ BMO`; TD's "L&H Product Management Intern/Co-op" (insurance products) | Placement is §4.3's; no level change |
| **portfolio** | Design work samples; a product or investment portfolio | 19.4% of Product and 28.2% of Design descriptions | 5.1 | A resume signal only (§9); never a penalty |
| **designer** | Product, UX, visual or industrial; interior (building), fashion, instructional or learning, floral | 2 / 1,518 open titles (interior 11, fashion 1, instructional 81, floral 0) | `qualtrics:8283643 'Associate Instructional Designer'`; `booz_allen_hamilton:…R0249355 'Interior Design Architect'`; GM's "Senior Interior Designer" is a *vehicle* interior | Placement is §3's and §4.2's; D11 for interior design |
| **design engineer** | Chip, RF or mechanical engineering; design engineering (front end) | 0 / **1,418** open titles (26% of Design) | `intel:…JR0288306 'Logic Design Engineer'`; `rtx:…01877671 'Senior RF Design Engineer'` | Placement is §4.2's |
| **creative, UI, researcher, architect, producer, owner** | Creative director (ads) vs the adjective; UI designer vs UI programmer; UX researcher vs research scientist; information architect vs building or solutions architect; design producer vs game producer; Product Owner vs business owner | creative 8 / 342; UI 6 / 143; researcher 35 / 93; architect 6 / 64; producer 1 / 30; product owner 2 / 2 (open titles) | `epic_games:5658563004 'Senior UI Programmer'`; `cadence:…R48450 'Design Engineering Architect'`; `simplify_newgrad:8116df87-… 'Associate Product Manager / Associate Game Producer' @ Hard Rock Digital` | Placement is §3's and §4's; no level change |
| **Product Builder** | LinkedIn's Associate Product Builder program; a new hybrid title (Postman, Figma) | 34 open titles in all fields: other 18, design 6, software 4, people_legal 2, finance 1, data_ml 1 (the run names no field for the other 2) | `postman:JR1000038 'Product Builder' @ Postman` (other) | D1 |

### 5.6 Program windows
The windows go in each board's `program_windows`, in Healthcare's format: `key`, `title` saying "typically",
`month`, `day`, `when`, `note` and optional `filters`. They work like this:
- **Who sees them.** `intel/programs.py` adds them to Calendar only for profiles with the board. A window with
  `filters` shows when the profile chose one of those filters. A profile that chose no filter on the board sees every
  window.
- **No re-read.** The fingerprint leaves `program_windows` out (`intel/knowledge.py` ~559), so adding them needs no
  facts recompute. They are tested as `tests/app/test_program_windows.py` does.
- **Filter keys.** The keys below are the brief's starting filters, and they follow §3's final keys.

The dates come from 5.1's calendar. Each program sets its own date every year, so each title says "typically"
(D23).

**Product (`product`):**

| Key | Title | Date | When | Filters | Note (shown in Calendar) |
|---|---|---|---|---|---|
| `apm_early` | Early APM and product programs typically open | Jul 1 | July | `apm_programs`, `product_management` | Salesforce's APM internship, Capital One's Product Development Program, Databricks' APM and Pinterest's PM apprenticeship opened first in 2026; some windows last only days. |
| `pm_internships` | Summer product internships typically open | Aug 1 | August to November | `product_management`, `apm_programs`, `technical_pm`, `growth_pm` (if kept), `product_ops`, `product_analytics` | Microsoft from early August; Atlassian, Coinbase and Intuit in September; most close by mid-October. |
| `apm_fall` | APM programs typically open | Sep 1 | September to mid-October | `apm_programs`, `product_management` | Google, Uber, Visa, Mastercard, Robinhood, Roblox, Figma, Disney, Stripe and Intuit open for the next year's start; most windows last one to four weeks. |
| `apm_winter` | Winter APM round typically opens | Jan 15 | January to March | `apm_programs`, `product_management` | Atlassian, Instacart, Square and Visa's winter rounds, and Microsoft's second wave of new-grad hiring. |

**Design (`design`):**

| Key | Title | Date | When | Filters | Note |
|---|---|---|---|---|---|
| `design_internships` | Product and UX design internships typically open | Aug 15 | August to October | `product_design`, `ux_research`, `content_design`, `design_engineering` | Google, Apple, Meta, Microsoft, Amazon and Figma post the next summer's design internships; some fill within weeks. Have two or three case studies ready. |
| `design_apprenticeships` | Design apprenticeships typically open | Sep 1 | September to October | `product_design`, `ux_research` | Google's UX Design Apprenticeship (for people without a design degree) and Shopify's 12-month Design Apprentice Program take applications in the fall for winter starts. |
| `industrial_design_internships` | Industrial design internships typically open | Sep 15 | September to November | `industrial_design` | Furniture, consumer-product and automotive design teams post summer roles in the fall and close them within weeks. |
| `studio_internships` | Design studio and agency internships typically open | Nov 1 | November to December | `visual_brand`, `product_design` | Studios and agencies recruit later than big tech. |
| `brand_design_internships` | In-house brand and graphic design internships typically open | Jan 15 | January to March | `visual_brand`, `content_design` | Consumer brands' creative teams post graphic, web and brand design roles in winter. |

**Both boards: Canadian co-op terms** (no `filters`, so every profile on the board sees them):

| Key | Title | Date | When | Note |
|---|---|---|---|---|
| `coop_winter` | Co-op recruiting for the winter term typically opens | Sep 15 | September to November | For January–April work terms. Waterloo's first cycle takes applications in mid-September with interviews to early October; U of T's 12–16-month PEY postings open in mid-September. |
| `coop_spring` | Co-op recruiting for the spring/summer term typically opens | Jan 15 | January to March | For May–August work terms. Waterloo's first cycle takes applications in mid-January with interviews to early February. |
| `coop_fall` | Co-op recruiting for the fall term typically opens | May 15 | May to August | For September–December work terms. |

- **No country filter.** `program_windows` has none, so a US-only profile sees the co-op windows too. Their titles say
  "co-op".
- **Shown twice for Product + Design.** `intel/programs.py` loops over the profile's boards and doesn't de-duplicate
  by key, and `dashboard.py` ~1449 adds the items as they come. So if both boards carry the co-op windows, a
  Product + Design profile sees each one twice. This is from reading the code; it wasn't checked in the app.
- **Left out on purpose:**
  - Meta's RPM, which is no longer for new grads.
  - LinkedIn's APM, which ended.
  - Any single company's date, such as "Google APM closes October 6", which moves every year.
- **A candidate if you want bank programs:** RBC Amplify (Sep 7 – Oct 5, 2026), under `product_management`.

---

## 6. Track, employer types and companies

Counts are of stored postings unless marked open (status != 'closed'). They come from the census table and the DB
copy (section 2), through `views_track`, `sources_polling`, `employers_research` and `config_robots_keys` in
`E:\product-design-board\phase1\`, and from the entries placement check in `E:\product-design-board\exp-entries\`
(6.6). Counts read for this section alone are in `E:\product-design-board\phase1\plan\scratch\s6_*.out.txt`.

### 6.1 Track (D24)

**What a board's track decides.**
- **Skills.** A skill group with a track is read on the postings of that track's `skills_from` boards.
  `tech.skills_from` is every board but Finance, plus "other" (10 in all). So a P&D skill on tech is also read on
  Software, Healthcare, Sales and "other" postings. A P&D skill with no track would also change Finance postings'
  facts. Section 9.5 measured what that costs: "prototyping" reads on 27.7% of open Design postings with a
  description, and as a tech skill it would also read on 17.4% of Hardware's and 12.0% of AI & Data's. A
  tech-track Figma would read on 0.4% of Software's. The skills themselves and their final rates are Phase 3 work
  (section 13).
- **Employer types in Settings.** Settings shows a track's types under its `employer_heading` to the track's
  boards. Today "Tech employer types" shows 20 types to all five tech boards. A new P&D type on tech shows up in
  the Settings of Software, AI & Data and Hardware too.
- **Company points.** See the table below.
- **Resume vocabulary.** `tracks.<track>.resume` (`degree`, `signals`, `role_words`) opens the track for a resume.
  Tech has a `degree` regex, 19 `signals` (software 10, data_ml 5, hardware 4), no `role_words` and no P&D
  signals. A P&D signal on tech would be read on every resume that opens tech, CS resumes included.

**What tech holds today** (`scripts\views_track_inventory.out.txt`):
- `track_boards.tech`: data_ml, software, hardware, product, design.
- Skills: 60 of the 175 have `track: "tech"` (programming 10 of 19, web 9, cloud 9, data 7, ml 8, cs 9,
  hardware 8). 57 have no track and are read on every posting, Finance included. Healthcare's 58 are on its own
  track.
- Types: 22 list `tech`. 18 are tech-only, `research_lab` and `health_tech` also list healthcare, and `fintech`
  and `quant_firm` also list finance.

**Company points** (15 at most, `intel/scoring.py` 187-211). The first row that matches decides:

| Employer | Points | "Why" line in the fit breakdown |
|---|---:|---|
| On the watchlist | 15 | "‹name› is on your watchlist" |
| Type is one of the profile's target types | 12 | "‹Type› — a target employer tier" |
| Type in `FINANCE_TYPES` (`fintech` and `quant_firm` included), for any profile | 7 | "‹Type› — recognized finance employer" |
| One of the type's non-finance tracks is the track of one of the profile's boards | 7 | "‹Type› — ‹the track's `employer_noun`›", e.g. "recognized tech employer" |
| The type has non-finance tracks, none of them the profile's | 4 | "‹Type› — outside finance" |
| `consulting`, `accounting_advisory` | 6 | "‹Type›" |
| `unknown`, `corporate` | 4 | "Employer not in company intelligence" |

So the track question comes down to 7 points or 4, out of 15. On tech, a P&D-only profile gets 7 at every tech type.
On its own track, it gets 7 only at types that also list the P&D track, and 4 at the rest. Target types give 12
either way.

**What moves for a P&D-only profile** (`scripts\views_track_scoring.out.txt`). Profile (a) has no target types,
which is how onboarding without Finance leaves it. Profile (b) targets the four P&D types (big_tech,
consumer_tech, enterprise_saas, high_growth_startup), which is what a P&D resume proposes.

| Option | At the four P&D types | At the other 16 non-finance tech types | Product postings 7 → 4 | Design postings 7 → 4 |
|---|---:|---:|---|---|
| Keep tech | 7 | 7 | 0 | 0 |
| Own track, no type shared, profile (a) | 4 | 4 | 5,664 (54.5%), 5,167 open (57.3%) | 4,033 (64.1%), 3,655 open (65.9%) |
| Own track with the four types as `["tech","<pd>"]`; or profile (b) on any own track | 7 (12 for b) | 4 | 2,549 (24.5%), 2,301 open (25.5%) | 3,066 (48.7%), 2,761 open (49.8%) |

The 16 other types include `health_tech` and `research_lab`. The largest of them:
- Product: semiconductors 549, defense_tech 501, hardware_devices 290, health_tech 233, cybersecurity 211,
  robotics_autonomy 190.
- Design: semiconductors 1,354, defense_tech 704, hardware_devices 234, gaming 215, robotics_autonomy 209.

These stay the same under every option:
- Finance types score 7 for any profile: fintech has 653 Product and 183 Design postings, bulge_bracket 607 and
  205, and so on.
- Healthcare-only types score 4.
- `unknown` scores 4. That covers 3,533 P&D postings at 429 employers: Anduril 204, ServiceNow 121, Salesforce 101,
  Disney 93, HP 91, OpenAI 87, Intel 79, …, Adobe 52 (section 6.5).

**Other boards.**
- On an own track, the existing types keep `tech`, so Software, AI & Data and Hardware profiles score exactly as
  today. Finance and Healthcare profiles do too. `test_health_taxonomy.py:277` and `test_tech_taxonomy.py:169`
  hold.
- New P&D types have 0 stored postings today. A new type that lists `tech` scores 7 (+3) for every profile with a
  tech board. A P&D-only type scores 4 for them, the same as `unknown`; only the wording changes, from "Employer not
  in company intelligence" to "outside finance".
- Share of each board's stored postings at tech types (finance types aside): Product 55%, Design 64%, Software 57%,
  Hardware 73%, AI & Data 43%, Healthcare 21%, Finance 13%.

**Resumes on the shared track.** Two made-up resumes were parsed with `main`
(`scripts\views_track_resume_probe.out.txt`):
- **PM resume** (BA Cognitive Science, "Product Manager Intern", "Associate Product Manager Intern"):
  - It opens tech through its titles.
  - Interests: `product` 1.0. Skills: excel, sql, agile. Figma, Jira, Amplitude and Mixpanel aren't skills.
  - Applied: fields `["product"]`, targets `["product"]`, and the four types.
  - Tech signals fire on its bullets (`data_ml.analytics`, `data_ml.data_science`, `software.mobile`), but they
    stay below the family.
- **UX resume** (Bachelor of Design, "UX Designer Intern", "Visual Designer Co-op"):
  - Interests: `design` 1.0 and **`software.frontend` 0.62**, because "user interfaces", HTML and CSS are tech
    signals.
  - Applied: **fields `["design", "software"]`**, so the resume adds the Software board. Types: the four plus
    developer_tools.
- On its own track, a P&D title opens only the P&D track, and that entry's bullets are read with P&D signals only
  (`role_interests` ~229-232). The spill stops, unless the resume also has a CS degree.
- `_title_track` opens a track only when it has a `degree` or `signals`. A P&D track that lands without its resume
  data would read PM and UX resumes **as Finance**. So the track and its resume data go in together (section 9).
- Adding P&D role words to tech (owner, strategist, illustrator, director, writer, researcher, designer, manager,
  lead) changed none of the 7 existing fixtures. But 7 is a small set.

**Fingerprint and versions.**
- `tracks.*.resume` is outside `config_fingerprint`. A new track's other keys, and new types and skills, change the
  fingerprint. The P&D filters change it anyway, so the track choice adds no extra re-read.
- An own track is data only: `config/taxonomy.json` and `companies.json`, with no edit to `intel/scoring.py`. So
  `RULES_CODE` doesn't change and `test_rules_version.py` passes.
- The fit change still reaches every install. The new fingerprint makes every posting's facts stale. Writing a
  posting's facts sets `profile_version=NULL` (`intel_store.py` ~558-574), so each posting is re-scored as the
  release's one recompute reaches it.
- So the track needs no `RULES_VERSION` raise (judgement, from the code). Healthcare raised it 2 → 3 in its Phase 3
  commit (`f866c4c`), which also changed `intel/scoring.py` (the board badges and the entry-level wording); its
  design gives the company points as the reason (`healthcare-board.md` §8). A raise would re-score every install at
  once instead of as the recompute reaches each posting, and it is a Stop-and-ask item.

**Tests that change on an own track** (`views_track` §3.4):
- `tests/matching/test_boards.py`:
  - `:11` `TECH` and `:59` (`TECH == track_boards["tech"]`) become data_ml, software, hardware.
  - `:64` (`{*TECH, "healthcare"} == occupation_families`) must name product and design on their own, since they
    keep `occupation_beats_finance`.
  - `:62` holds while product and design stay in `tech.skills_from`.
- `web/tests/fields.test.js`:
  - `:75` (tracks `['tech','healthcare']`) gains the new key.
  - `:78` (`tech.boards`) drops product and design.
  - `:80` (20 types) holds if no tech type changes.
  - Add an assertion for the new track.
- `tests/matching/test_tech_taxonomy.py:181-182`: the allowed track tuples gain `("<pd>",)`, and `("tech","<pd>")`
  if the four types share the track. `:185` (20) holds.
- If big_tech and the other three share the track:
  - `tests/resume/test_resume_tech.py:155` (`type_tracks(t) == ["tech"]` for a Hardware resume's types, big_tech
    among them) fails.
  - `test_tech_taxonomy.py:191` holds: tech-only companies go from 452 to 307, still above 100
    (`scripts\views_track_misc.out.txt`).
- `tests/matching/test_health_taxonomy.py:290-291` holds if the P&D track's `skills_from` lists only product and
  design. Adding software (for design engineering) changes `:291`.
- `web/js/preview/meta.json` is regenerated. The filters change it anyway.
- On tech instead, `test_tech_taxonomy.py:185` and `fields.test.js:80` (20) rise with each new type, and every P&D
  type, skill and signal must also be checked against the three tech boards.

**Recommendation (judgement, `views_track` §3.5):** one shared Product & Design track for both boards, built the
way Healthcare's is.
- Product and design stay in `tech.skills_from`, so tech skills read on P&D postings exactly as today.
- P&D skills go on the new track, which reads them only on P&D postings (`skills_from`: product, design).
- The track gets its own `degree`, `signals`, `role_words`, `employer_heading` and `employer_noun`.
- The four P&D types join it as `["tech","<pd>"]`, as `research_lab` and `health_tech` joined Healthcare. P&D
  profiles keep 7 points there, and Canva, Miro and Intuit stay as they are (6.3).
- Each other tech type is a separate yes. The obvious candidates are gaming (215 Design, 88 Product) and
  hardware_devices (234 Design, 290 Product).

Its cost:
- 2,549 Product and 3,066 Design postings lose 3 points for P&D-only profiles.
- A P&D-only user can no longer pick the other 16 tech types in Settings, unless they share the track too.
- The test edits above.

Keeping tech means no fit change and fewer test edits. But the UX resume keeps adding Software, and every later P&D
type, skill and signal must be checked on the tech boards. Two tracks, one per board, aren't worth it: the boards
share employers and tools (judgement).

### 6.2 New employer types (D25)

The rules (brief, Target state item 2):
- A type that spans boards exists only once.
- A new type's `company_priors` name only P&D filters, never a finance category. A finance-category prior (such as
  `consulting`'s `strategy`) makes a generic title a Finance posting (`intel/taxonomy.py` ~297).
- No `companies.json` entry uses `unknown`.
- Every new type and company is simulated on stored postings with the branch's code on both sides, before and
  after the change.

A non-finance prior only changes the filter of a posting on the board it names (`specialty()`, `intel/taxonomy.py`
~297-322). It never moves a posting onto a board or onto Finance. The entries check (6.6) shows this: 88 filter
changes, 0 moves.

**Where the new employers' types come from** (`employers_research` §2 and §4; the candidates are in section 8):
- **Studios and agencies** (`design_studios`: 41 candidates, 17 in Canada; for example Metalab, Critical Mass,
  Thinkingbox, IDEO, Teague). No existing type fits them. The nearest, `consulting`, is on the finance track: it
  scores 6 for every profile (`intel/scoring.py` ~207), lends its HQ country (6.4), and its prior (`strategy` 1.5,
  `strategy.consulting` 1.0) turns generic titles into Finance postings. `employers_research` keeps an
  "agency/studio" type on these employers even if packs merge.
- **Industrial design employers** (`industrial_design`: 34 candidates, 10 in Canada). These are consumer-products
  makers: Spin Master, Arc'teryx, Canada Goose, lululemon, Bauer, CCM, BRP, SharkNinja and others.
  `employers_research` proposes a `consumer_products` group for them. The nearest existing type is
  `hardware_devices` ("Devices & IoT"), which carries a `hardware.embedded_firmware` 1.5 prior.
- **Canadian product and design shops** (34 candidates) and **APM programs** (27): existing types fit. Those are
  canadian_tech, enterprise_saas, consumer_tech, high_growth_startup and health_tech. Visa and Mastercard are typed
  already (`fintech`).

**Proposed** (judgement; the keys are placeholders):

| Type | Label | Track(s) | Priors | Lends HQ country | Examples |
|---|---|---|---|---|---|
| `design_studio` | Design Studio & Agency | the P&D track only | `design.*` and `product.*` filters only; weights set in Phase 3 from the simulation | no | Metalab, Critical Mass, Thinkingbox, IDEO, Teague |
| `consumer_products` | Consumer Products | the P&D track only | `design.industrial_design`; weight set in Phase 3 | no | Spin Master, Arc'teryx, Canada Goose, lululemon, Bauer |

- For scale, the existing priors run from 0.3 to 3.0: `gaming` → `software.game_dev` 3.0, `medtech` →
  `healthcare.medical_devices` 2.0, `ai_lab` → `data_ml.ai_research` 1.0.
- If the track stays tech (D24), they are `["tech"]` and give tech-board profiles +3 at their employers. On
  the P&D track alone they move no fit off P&D (judgement). Their sources sit in the P&D folder, which only P&D and
  the `everything` boards poll. Other boards meet these employers only through list postings that name them, and
  each such posting is a label change that the Phase 4 placement check lists.

**Payments and banking software** (D26). `employers_research` puts six candidates to you as
finance-type questions. Their stored rows match the company string on any source, mostly lists
(`plan\scratch\s6_payments.out.txt`):

| Candidate | Stored rows (all / open) | Of them Finance / "other" | Key they resolve to today |
|---|---|---|---|
| Clearwater Analytics | 39 / 38 (13 open Product) | 7 / 3 | `clearwater_analytics` |
| Interac | 8 / 4 | 2 / 4 | `interac` |
| Hiive | 2 / 2 | 1 / 1 | `clarity`: stored as "Clarity (formerly Hiive)" on `linkedin_canada`; check it before keying |
| nCino | 2 / 2 | 0 / 0 | `ncino` |
| Zafin | 0 | – | – |
| Helcim | 0 | – | – |

- With `fintech`:
  - They score 7 for every profile, so Finance profiles gain 3 company points at them.
  - Their HQ country fills in for postings that name no place.
  - Their prior (`fintech` 1.0, a finance category) can turn generic titles into Finance postings. Interac's
    "Product Intern, Money Movement (Winter 2027)" sits on "other" today. Each such move blocks the commit until you
    approve it.
- With a tech type (`enterprise_saas`, `canadian_tech`), nothing moves and no HQ country is lent. Finance sees only
  label changes (6.7) on these employers' postings, at 4 points as today.
- Fidelity Canada and EQ Bank were left out of the candidates as finance employers.

### 6.3 Existing employers keep their type

Canva, Miro and Intuit already have entries. They keep them, even where a P&D type would fit better. A new type would
move their stored postings through its priors, and change their label and company points on Finance and the tech
boards. Counts are for each company key on every source, stored / open (`scripts\config_robots_keys_employers.out`;
the board split is from `scripts\views_track_scoring.out.txt`):

| Employer | Type today | Its source | Postings (all sources) | P&D | Finance |
|---|---|---|---|---|---|
| Canva | `enterprise_saas` (AU) | `canva`, tech/enterprise_saas, SmartRecruiters (robots.txt disallows it, section 11) | 110 / 57 | 2 Product, 13 Design | 2 |
| Miro | `enterprise_saas` (US) | `miro`, tech/enterprise_saas, Greenhouse | 21 / 18 | 0 | 0 |
| Intuit | `big_tech` (US) | `intuit`, shared/big_tech, Radancy (robots.txt disallows it, section 11) | 721 / 636 | 52 Product, 29 Design | 128 |

- These are typed already too: Shopify (`canadian_tech`), Atlassian (`enterprise_saas`), Wealthsimple (`fintech`),
  the big tech names, Accenture (`consulting`) and Deloitte (`accounting_advisory`).
- If the four P&D types share the P&D track (6.1), Canva, Miro and Intuit give P&D profiles 7 points without a
  re-type.

### 6.4 HQ country, and postings that name no place

`resolve_company` (`intel/companies.py` ~49-58) uses a known employer's HQ country for a posting that names no place.
It does this only when the type's tracks include `finance`.
- Those are the 18 finance-track types: accounting_advisory, asset_manager, bulge_bracket, canadian_bank,
  commercial_bank, consulting, corporate, elite_boutique, fintech, global_bank, hedge_fund, insurance,
  market_infrastructure, middle_market_bank, pension_fund, private_equity, quant_firm, venture_capital.
- Every other type counts as hiring worldwide (country ""). An employer with no entry lends no country.
- The country sets the pay currency (`intel/facts.py` ~93) and the no-sponsorship penalty (`intel/scoring.py`
  ~343), not the stored location. So the placement check doesn't show it.

P&D postings by the tracks of their employer's type (`scripts\sources_polling_hq.out`, all / naming no country):

| Type's tracks | Lends HQ country | Product | Design |
|---|---|---|---|
| finance | yes | 1,947 / 531 | 536 / 130 |
| healthcare | no | 585 / 194 | 384 / 113 |
| healthcare and tech | no | 237 / 55 | 71 / 15 |
| tech | no | 5,427 / 913 | 3,962 / 920 |
| `unknown` | no | 2,191 / 281 | 1,342 / 177 |
| **All** | | **10,387 / 1,974** | **6,295 / 1,355** |

- **Today:**
  - 661 P&D postings at finance-track employers name no place, so they take the HQ country. For example, Capital
    One (`commercial_bank`) has 373 P&D postings, 336 of them with no place, and they read as US.
  - Counting every board, 13,516 postings at finance-track employers name no place (the sum of the per-board counts
    in `sources_polling_hq.out`): Finance 5,960, Software 2,341, other 2,028, Operations 898, AI & Data 707, Sales
    684, Product 531, People & Legal 220, Design 130, Hardware 10, Healthcare 7.
- **New P&D types lend no country** (6.2). A posting with no place gets no currency and no sponsorship country from
  HQ.
  - Studios and agencies are often single-office, like the brief's retail, law-firm and government cases. So any
    new source whose tiles show no place gets a `"location"` override.
  - This can only be checked per source in Phase 2, since these employers have no stored postings yet.
  - A multi-office agency should not get one override for all its offices (judgement).
- **Entries for the no-entry employers (6.5):**
  - A tech type changes nothing here: those employers count as worldwide, as their unknown postings do today.
  - A finance-track type (for example `fintech` for Gusto or Checkr) would start lending the HQ country to their
    postings with no place on every board, Finance included, and the placement check would not show it. So these
    entries take tech types.
- **Existing sources:** 51 sources have 10 or more P&D postings, half or more of them with no place. The largest are
  capital_one 336 of 373, blue_origin 88 of 149, l3harris_technologies 69 of 69, ge_vernova 54 of 64, nxp 52 of 77,
  salesforce 47 of 88, intel 42 of 73, hpe 33 of 58, adobe 32 of 46 and autodesk 32 of 48. A new source with
  numbers like these would need an override. Editing an existing source needs your yes ("Stop and ask before"),
  so these stay as they are.

### 6.5 Shared employers with no entry (D27)

**Who they are** (`sources_polling` §6, `scripts\sources_polling_employers.out`):
- In `shared/`, 121 sources have a `company_key`, 51 match an entry by source name, 19 are aggregators (lists,
  LinkedIn) and 128 have no entry. 112 of the 128 carry P&D postings. The other 16 carry none, Citadel Securities,
  GTS and Qube (`shared/quant_trading`) among them, so they aren't candidates here.
- The 112 are stored as `unknown` and show the source name as the company ("figma").
- Together they hold 41,009 postings at their own sources: 1,483 Product, 855 Design, 1,606 Finance and 10,332
  "other".
- Every non-aggregator `tech/` source has a `company_key`.
- An entry is matched through the source name, so it needs no edit to the source. Never add a `company_key` to the
  existing source.
- Company points, the P&D types and `company_priors` don't reach these postings today: they score 4, "Employer not
  in company intelligence".
- 66 have 10 or more P&D postings, and 64 of them are in the placement check (6.6).
- The other 48 hold 238 P&D postings at their sources, out of 9,150 in all.
  - target 41 (3,237 postings) and vanta 15 (101) were left out of the check (6.6).
  - Then: zoom 9 (178), notion 9 (161), 1password 9 (116), baseten 8 (127), hightouch 8 (93), dropbox 8 (54),
    mixpanel 7 (59), amazon_newgrad 6 (2,439), waabi 6, faire 6, amplitude 6, seatgeek 6, xai 5, nuro 5,
    commure 5, peloton 5, supabase 5, fastly 5, typeface 5, midjourney 5.
  - The last 26 have 4 P&D postings or fewer each, webflow 3 (23 postings) among them.

**Pack headings.** Installs carry no `_` headings (section 2.2), so `_SECTION_TYPES` never types a posting in the
installed app. 15 sources sit under the old `startups_fintech_consumer` heading in four `shared/` packs. 13 of them
carry P&D postings: oscar_health, samsara, gusto, checkr, hinge_health, flexport, faire, seatgeek, peloton,
commure, glossier, sweetgreen and abridge (1,776 postings: 166 Finance, 137 P&D). Gopuff and OpenEvidence carry
none.
- They are `fintech` only in a dev run that loads the packs.
- So an entry for one of them is a label change in the installed app but a re-type (a move) in a dev run.
- The placement check reads the installed `config.json`, so it sees `unknown`.
- 6 of the 13 are in the 64: Oscar Health, Samsara, Gusto, Checkr, Hinge Health and Flexport.

**What an entry does.**
- It is keyed by the slug the postings resolve to today. For all 112 that is `slug(<source name>)`, with one key
  per source.
- It renames ("figma" → "Figma") and types every stored posting whose company string or source name it matches, on
  every board. Anthropic's entry types 83 Finance postings (the brief counted 75).
- A type without priors gives label changes only. The types without priors include big_tech, enterprise_saas,
  consumer_tech, developer_tools, health_tech, high_growth_startup, canadian_tech and telecom.
- A type with priors can also change filters on other boards. Those types are ai_lab, ai_infrastructure,
  data_infrastructure, cybersecurity, gaming, defense_tech, hardware_devices, robotics_autonomy and semiconductors.
- A `fintech` type would add a Finance prior and lend the HQ country.

**Name-only or `=` alias** (`scripts\sources_polling_entry_sim.out`, company resolution only, all 112):

| Form | Postings typed | Finance | "other" | Company keys that move |
|---|---:|---:|---:|---:|
| Name only (it also matches as a whole word inside longer names) | 45,463 | 1,708 | 11,166 | 432 |
| `=` alias (the name matches only exactly) | 45,031 | 1,689 | 11,053 | 0 |

- The 432 key moves come from sibling feeds and longer names that a name-only entry swallows:
  - intel_early 148
  - disney_early 109, the_walt_disney_company 10 and walt_disney_animation_studios 1
  - palantir_technologies 71
  - salesforce_early 30
  - adobe_university 28
  - aurora_innovation 24
  - anduril_industries 7
  - perplexity_ai 3
  - asana_partners 1 ("Asana Partners" is a different firm)
- A key move is a company move, which blocks the commit. So every entry takes an `=` alias.
- With `=` aliases, the sibling feeds stay unlabelled unless they get entries keyed by their own slugs.
- One employer can carry two keys: Workday's list postings resolve to `workday`, and its source to `workday_hq`
  (`employers_research`).

**The employers P&D cares most about** (`=` form):

| Employer | P&D at its source (Product / Design) | Stored postings an entry types | Finance | "other" | In the check (6.6) |
|---|---|---:|---:|---:|---|
| ServiceNow | 75 / 37 | 1,312 | 62 | 283 | yes, `enterprise_saas` |
| Salesforce | 43 / 45 | 2,643 | 80 | 463 | yes, `big_tech` |
| Anthropic | 40 / 12 | 820 | 83 | 127 | yes, `ai_lab` |
| Adobe | 30 / 16 | 536 | 44 | 125 | yes, `big_tech` |
| Figma | 11 / 16 | 238 | 8 | 39 | yes, `enterprise_saas` |
| Airbnb | 13 / 6 | 297 | 15 | 105 | yes, `consumer_tech` |
| Duolingo | 9 / 8 | 105 | 1 | 10 | yes, `consumer_tech` |
| Asana | 11 / 5 | 148 | 7 | 28 | yes, `enterprise_saas` |
| Spotify | 12 / 4 | 118 | 4 | 19 | yes, `consumer_tech` |
| Notion | 6 / 3 | 209 | 9 | 38 | no (under 10 P&D) |
| Webflow | 2 / 1 | 23 | 0 | 0 | no (under 10 P&D) |

- Figma and Adobe aren't in the Companies view at all today (section 10.1).
- `sources_polling` recommends a short list (judgement). It takes the employers where P&D's types or the 7 track
  points matter: Figma, Adobe, Webflow, Notion, Duolingo, Asana, Airbnb and Spotify. Each gets an `=` alias and a
  type without priors, goes through the placement check, and goes to you with its counts.
- Those 8 type 1,674 stored postings: 88 Finance, 364 "other", 108 Product and 60 Design
  (`plan\scratch\s6_shortlist.out.txt`).
  - Typed by their pack groups, as the check types them, all 8 get one of the four P&D types (Adobe `big_tech`;
    Figma, Notion, Webflow and Asana `enterprise_saas`; Duolingo, Airbnb and Spotify `consumer_tech`). So they give
    P&D profiles 7 points on either track.
  - 6 of the 8 are in the check (6.6): label changes only, no filter change. Notion and Webflow have types without
    priors, so they are label-only by construction.

### 6.6 The entries check: 64 exact-alias entries on stored postings

**Inputs.** `E:\product-design-board\exp-entries\entries.json` holds one entry for each no-entry `shared/` employer
with 10 or more P&D postings at its source.
- Each entry is keyed by the slug, named by its display name, and has one `=` alias.
- Each takes the type its pack group names. That mapping is a judgement, from
  `E:\product-design-board\scripts\entries_experiment.py` `GROUP_TYPE`, with three overrides: Comcast `telecom`, HP
  `hardware_devices`, Disney `consumer_tech`.
- By type: consumer_tech 11, big_tech 7, enterprise_saas 7, developer_tools 6, ai_lab 5, high_growth_startup 5,
  ai_infrastructure 4, data_infrastructure 4, defense_tech 4, hardware_devices 3, robotics_autonomy 3,
  health_tech 2, gaming 1, semiconductors 1, telecom 1.
- They hold 2,100 P&D postings at their sources (1,351 Product, 749 Design), out of 31,859 postings there.
- Two were left out:
  - target (41 P&D): its pack group, consumer_tech, misleads. Target is a retailer, and 2,501 of its 3,237
    postings are "other".
  - vanta (15 P&D): the script picks no type for its group `security`.

**The run.**
- The sample is every stored posting an entry could re-resolve: 35,439 (27,045 open).
- `place` ran with `main`'s code and with a copy of `main` that adds the 64 entries (`exp-entries\code`). Both used
  the same DB copy and the installed `config.json` (`E:\product-design-board\scripts\rerun_baselines.sh` lines
  15-17). It took 446 s and 478 s. Both sides are the branch's code before and after the change, as the brief asks.
- `place-compare` reports:
  - missing 0, added 0, moved 0, stage changes 0
  - **35,350 label changes** (26,964 open), with 33,061 postings renamed
  - **88 filter changes, all on other boards**: Software 79, Hardware 8, AI & Data 1. The check fails on these.
- The first run (`exp-entries\superseded\`, an older `place-compare`) changed the same 35,350 and 88 postings.

**Label changes by board** (stored / open; the open counts are from `plan\scratch\s6_entries.out.txt`):

| Board | Labels | Board | Labels |
|---|---|---|---|
| Software | 12,072 / 9,592 | **Finance** | **1,512 / 1,076** |
| "other" (Finance reviews it) | 7,666 / 5,560 | Product | 1,462 / 1,085 |
| Sales | 4,609 / 3,387 | Design | 825 / 616 |
| Operations | 2,240 / 1,644 | People & Legal | 817 / 614 |
| AI & Data | 2,051 / 1,609 | Healthcare | 58 / 47 |
| Hardware | 2,038 / 1,734 | | |

- **Finance labels by new type:** big_tech 258, defense_tech 215, ai_lab 161, consumer_tech 157, hardware_devices
  131, enterprise_saas 117, ai_infrastructure 107, health_tech 100, data_infrastructure 68, developer_tools 67,
  high_growth_startup 42, robotics_autonomy 30, semiconductors 29, telecom 23, gaming 7.
- **By employer:** HP 112, Oscar Health 96, Anduril 90, Anthropic 83, Salesforce 80, SpaceX 78, OpenAI 62,
  ServiceNow 62, Crusoe 59, Disney 56, Adobe 44, …
- **Samples:**
  - Anthropic "Director, US International Tax", "Unclassified" → "AI Lab", "anthropic" → "Anthropic"
  - OpenAI "Manager, Revenue Accounting", "Unclassified" → "AI Lab"
- **P&D:**
  - 1,462 Product and 825 Design postings get a type.
  - 611 Product and 402 Design of them are at the four P&D types, and the rest at other tech types (851 and 423).

**Filter changes.** All 88 come from the new types' priors:

| Type (its priors) | Employer | Changes (stored) |
|---|---|---|
| `gaming` (`software.game_dev` 3.0) | Roblox | 46: 35 gain game_dev; 11 lose a filter (infrastructure 7, qa_test 2, systems 1, backend 1) |
| `ai_infrastructure` (`data_ml.ml_engineering` 1.0, `software.infrastructure` 1.0) | Crusoe 17, Databricks 8, Scale AI 4, Lambda Labs 1 | 30: no filter → infrastructure |
| `defense_tech` (`hardware.embedded_firmware` 1.0, `software.security` 0.5) | SpaceX | 5: 3 gain embedded_firmware, 2 lose electrical |
| `data_infrastructure` (`data_ml.data_engineering` 1.0, `software.systems` 1.0) | MongoDB | 3: 2 gain systems, 1 loses backend |
| `semiconductors` (`hardware.chip_design` 1.5) | Intel | 3: 2 electrical → chip_design, 1 loses electrical |
| `ai_lab` (`data_ml.ai_research` 1.0, `data_ml.ml_engineering` 0.5) | Cohere | 1: no filter → ai_research |

80 of the 88 are open. Samples:
- Roblox "Senior Software Engineer (C++)": no filter → game_dev.
- Databricks "Senior Software Engineer (Money)": no filter → infrastructure.
- Intel "GPU & AI Accelerator Hardware Design Undergraduate Intern": electrical → no filter.

**What it shows** (`plan\scratch\s6_table.out.txt`):
- **55 employers are label-only** on stored postings: 27,613 labels, 1,255 of them Finance.
  - 39 of them have a type with no priors, so they are label-only by construction: 16,411 labels, 764 Finance.
  - 16 have a type with priors but moved nothing: Anthropic, OpenAI, Perplexity, Suno, HP, Elastic, ClickHouse,
    Fivetran, Palantir, Anduril, Shield AI, Verkada, Samsara, Waymo, Aurora and Zoox. Their priors can still move
    later postings (judgement).
- **9 employers change other boards' filters**: Roblox, Crusoe, Databricks, SpaceX, Scale AI, MongoDB, Intel, Cohere
  and Lambda Labs. Their filters belong to the Software, Hardware and AI & Data boards (judgement).
- **Names.** The run named each entry by title-casing its slug ("Openai", "Hp", "Scale Ai", "Ebay", "Workday Hq").
  Real entries need the right names (OpenAI, HP, Scale AI, eBay, Workday). The name shows on 33,061 postings. A
  sibling feed's entry (`disney_early`) needs a name and alias that don't repeat its main employer's, or "Disney"
  would match two entries (judgement).
- **Fit.** These are what the labels do to points (6.1). The check compares placement, not fit.
  - Profiles with a tech board (Software, AI & Data, Hardware, and P&D while it is on tech) score every typed posting
    at 7 instead of 4.
  - On the recommended own track, P&D-only profiles gain 3 at the 30 employers with the four P&D types, and stay at
    4 at the other 34.
  - Healthcare profiles also gain 3 at the 2 `health_tech` employers: Oscar Health (341 labels) and Hinge Health
    (97).
  - Finance-only profiles score 4 either way.

The per-employer results (P&D postings at the source; postings labelled, stored with open in brackets; how many of
those are Finance and "other"; how many are renamed; filter changes):

| Employer (source) | Type tried | P&D | Labelled (open) | Finance | "other" | Renamed | Filter changes |
|---|---|---:|---:|---:|---:|---:|---|
| `anduril` | `defense_tech` | 192 | 3,308 (2,721) | 90 | 661 | 3,146 | – |
| `servicenow` | `enterprise_saas` | 112 | 1,312 (786) | 62 | 283 | 1,312 | – |
| `salesforce` | `big_tech` | 88 | 2,643 (1,849) | 80 | 463 | 2,338 | – |
| `openai` | `ai_lab` | 82 | 1,030 (842) | 62 | 185 | 1,030 | – |
| `hp` | `hardware_devices` | 81 | 1,497 (1,036) | 112 | 440 | 1,497 | – |
| `intel` | `semiconductors` | 73 | 1,461 (1,064) | 29 | 291 | 1,181 | Hardware 3 |
| `disney` | `consumer_tech` | 60 | 801 (432) | 56 | 314 | 631 | – |
| `shield_ai` | `defense_tech` | 57 | 837 (732) | 31 | 133 | 837 | – |
| `elastic` | `data_infrastructure` | 55 | 526 (414) | 10 | 42 | 519 | – |
| `databricks` | `ai_infrastructure` | 54 | 1,127 (950) | 32 | 98 | 1,060 | Software 8 |
| `netflix` | `big_tech` | 53 | 590 (421) | 37 | 196 | 572 | – |
| `anthropic` | `ai_lab` | 52 | 820 (694) | 83 | 127 | 800 | – |
| `autodesk` | `big_tech` | 48 | 583 (63) | 30 | 116 | 490 | – |
| `spacex` | `defense_tech` | 47 | 3,372 (3,021) | 78 | 1,352 | 3,372 | Hardware 5 |
| `adobe` | `big_tech` | 46 | 536 (380) | 44 | 125 | 418 | – |
| `ebay` | `big_tech` | 44 | 391 (259) | 34 | 102 | 391 | – |
| `datadog` | `developer_tools` | 42 | 558 (419) | 17 | 86 | 530 | – |
| `waymo` | `robotics_autonomy` | 39 | 698 (607) | 19 | 181 | 451 | – |
| `workday_hq` | `big_tech` | 36 | 614 (379) | 26 | 173 | 614 | – |
| `harvey` | `high_growth_startup` | 35 | 484 (404) | 17 | 83 | 456 | – |
| `pinterest` | `consumer_tech` | 33 | 307 (229) | 10 | 61 | 247 | – |
| `mongodb` | `data_infrastructure` | 32 | 500 (378) | 30 | 78 | 500 | Software 3 |
| `zoox` | `robotics_autonomy` | 30 | 307 (252) | 5 | 49 | 278 | – |
| `oscar_health` | `health_tech` | 28 | 341 (226) | 96 | 116 | 331 | – |
| `figma` | `enterprise_saas` | 27 | 238 (184) | 8 | 39 | 189 | – |
| `fivetran` | `data_infrastructure` | 26 | 234 (168) | 22 | 28 | 230 | – |
| `scale_ai` | `ai_infrastructure` | 26 | 233 (196) | 4 | 45 | 233 | Software 4 |
| `lyft` | `consumer_tech` | 25 | 358 (276) | 19 | 54 | 251 | – |
| `roblox` | `gaming` | 25 | 330 (261) | 7 | 27 | 281 | Software 46 |
| `doordash` | `consumer_tech` | 23 | 673 (523) | 25 | 212 | 673 | – |
| `samsara` | `hardware_devices` | 22 | 439 (366) | 10 | 125 | 397 | – |
| `cloudflare` | `developer_tools` | 21 | 572 (481) | 21 | 47 | 549 | – |
| `crusoe` | `ai_infrastructure` | 21 | 441 (339) | 59 | 123 | 424 | Software 17 |
| `glean` | `high_growth_startup` | 21 | 182 (137) | 4 | 27 | 165 | – |
| `airbnb` | `consumer_tech` | 19 | 297 (215) | 15 | 105 | 284 | – |
| `instacart` | `consumer_tech` | 19 | 165 (104) | 6 | 28 | 157 | – |
| `palantir` | `defense_tech` | 19 | 457 (419) | 16 | 70 | 333 | – |
| `verkada` | `hardware_devices` | 19 | 415 (362) | 9 | 30 | 388 | – |
| `reddit` | `consumer_tech` | 18 | 196 (166) | 9 | 18 | 193 | – |
| `decagon` | `high_growth_startup` | 17 | 167 (139) | 9 | 33 | 159 | – |
| `duolingo` | `consumer_tech` | 17 | 105 (91) | 1 | 10 | 69 | – |
| `gusto` | `enterprise_saas` | 17 | 128 (87) | 14 | 25 | 125 | – |
| `sierra` | `high_growth_startup` | 17 | 281 (242) | 6 | 39 | 254 | – |
| `asana` | `enterprise_saas` | 16 | 148 (115) | 7 | 28 | 143 | – |
| `checkr` | `enterprise_saas` | 16 | 73 (41) | 7 | 11 | 73 | – |
| `comcast` | `telecom` | 16 | 1,114 (713) | 23 | 227 | 1,096 | – |
| `gitlab` | `developer_tools` | 16 | 337 (262) | 6 | 34 | 337 | – |
| `smartsheet` | `enterprise_saas` | 16 | 122 (80) | 2 | 16 | 122 | – |
| `spotify` | `consumer_tech` | 16 | 118 (89) | 4 | 19 | 117 | – |
| `suno` | `ai_lab` | 16 | 89 (73) | 4 | 10 | 85 | – |
| `hinge_health` | `health_tech` | 15 | 97 (82) | 4 | 4 | 96 | – |
| `clickhouse` | `data_infrastructure` | 14 | 242 (212) | 6 | 14 | 242 | – |
| `disney_early` | `consumer_tech` | 14 | 109 (28) | 9 | 52 | 109 | – |
| `aurora` | `robotics_autonomy` | 13 | 140 (95) | 6 | 22 | 136 | – |
| `perplexity` | `ai_lab` | 13 | 163 (140) | 6 | 28 | 161 | – |
| `twilio` | `developer_tools` | 13 | 196 (133) | 12 | 25 | 195 | – |
| `lambda_labs` | `ai_infrastructure` | 12 | 109 (91) | 12 | 18 | 109 | Software 1 |
| `mercor` | `high_growth_startup` | 12 | 155 (132) | 6 | 29 | 131 | – |
| `nvidia` | `big_tech` | 12 | 959 (862) | 7 | 159 | 959 | – |
| `cohere` | `ai_lab` | 11 | 164 (134) | 6 | 44 | 147 | AI & Data 1 |
| `flexport` | `enterprise_saas` | 11 | 252 (196) | 17 | 70 | 248 | – |
| `discord` | `consumer_tech` | 10 | 56 (41) | 3 | 2 | 56 | – |
| `linear` | `developer_tools` | 10 | 39 (31) | 0 | 2 | 39 | – |
| `vercel` | `developer_tools` | 10 | 114 (100) | 11 | 12 | 105 | – |

Autodesk has 583 postings labelled but only 63 open. Its source lists 3 open of 490 after a read marked complete
(section 15).

### 6.7 What label-only changes look like to you

A label change gives a stored posting a known type where it was unknown. The posting keeps its board, filter,
company key and location, so it isn't a move (section 1). The tech work had 201 on Finance, and Healthcare had 3
with ICF; Healthcare wrote them down but didn't ask, and you wanted them explained first. So here they are, put to
you once. Each entry you approve, here or for a new employer in section 8, shows up in four places:

1. **The type tag in the posting detail** (`web/js/detail.js` ~165). It shows "Unclassified" today and the type
   after: "Enterprise Software" for Figma, "AI Lab" for Anthropic. The company name changes too ("figma" →
   "Figma"). In the 64-entry check, 35,350 postings get a tag and 33,061 a new name.
2. **The Employer type filter.**
   - Opportunities lists the types present in the results (`opportunities.js` ~533-555). These postings leave
     "Unclassified" and count under their type. A type new to the results is a new option.
   - The Companies view lists every type but `unknown` (`companies.js` ~56). So a new type, such as a studio type
     (6.2), is a new option there for every profile.
3. **The "Why" line** (the Company row of the fit breakdown, "How it adds up"):
   - Finance profile: "Employer not in company intelligence" becomes "Big Tech — outside finance", at 4 points
     both times.
   - Profile with a board on the type's track: "Big Tech — recognized tech employer", at 7 points instead of 4.
4. **The Companies list.**
   - The default view keeps Finance postings plus every posting at a typed employer (`dashboard.py` ~1061), and
     shows the first 400 employers. So a typed employer's row counts all its open postings, on every profile,
     Finance included.
   - With the 64 entries (`plan\scratch\s6_companies_entries.out.txt`; sorted by new in 7 days, then open roles,
     with the stored-fit key left out):
     - Today 62 of the 64 match the filter through their Finance postings only (1,012 open canonical postings),
       and 2 of them are in the first 400.
     - Typed, their rows count 23,501 open postings. 42 of them are in the first 400 (Salesforce 1,590 open,
       SpaceX 2,864, Anduril 2,505, HP 866, …), and 40 of today's first 400 drop out.
   - Option A′ in section 10.1 keeps today's filter for any profile that includes Finance, so these rows stay
     there. A P&D-only profile under A′ counts only its boards' postings.

What Finance sees from the 64 entries:
- 1,512 Finance postings (1,076 open) with a new tag, 1,462 of them with a new name.
- 7,666 "other" postings (5,560 open) that Finance reviews.
- The Companies rows above.
- Fit unchanged:
  - The company points stay at 4.
  - No HQ country is added, since every type tried is worldwide.
  - No Finance posting moves or changes filter.

Your answer to (D27) is your answer to these labels.

---

## 7. Sources and polling

Counts here are stored postings in `E:\product-design-board\census\census.db` (table `p`: 410,486 titled postings
with `main`'s stored placement, 0 stale; section 2.1). "Open" is `status != 'closed'`. The research is
`E:\product-design-board\phase1\sources_polling.md`. Its scripts are the `sources_polling_*.py` files in
`E:\product-design-board\phase1\scripts\`, each with its `.out` beside it. Two kinds of count:

- **Raw:** postings on Product or Design today (`field` product or design). They carry today's broad words
  (`design`, `ui`, `creative`, `program manager`; section 4).
- **Core:** raw postings whose title passes a narrow proxy the research wrote (judgement), in
  `E:\product-design-board\phase1\scripts\sources_polling_lib.py`. Product: product manager, management, owner,
  lead, director, analyst, ops or strategy; head, VP or chief of product; APM; group PM. No program manager, no
  TPM. Design: UX, UI, product, visual, graphic, brand, motion, interaction, industrial or game designer; user,
  UX or design research; art or creative director; design manager, lead, director, systems or ops; illustrator.
  No "design engineer", and no instructional, interior, layout or mechanical designer. Core is not the board's
  future title words (section 3). It shows which groups carry real P&D work.

### 7.1 How a board picks its sources
`intel/sources.py` (`groups_for` ~180, `_takes` ~198, `selected_packs` ~202, `polled_sources` ~230):

- A pack is `config/sources/<folder>/<group>.json`. In `config/sources/manifest.json`, `folders.<folder>.fields`
  is the folder's audience: a board polls a pack only if it is in that audience.
- `fields.<board>` names what the board polls:
  - `"groups": "*"` (Finance): every pack in every folder whose audience has the board, so finance/ and shared/.
  - `core` and `filters` (Software, AI & Data, Hardware, Healthcare): core always, plus the groups of the filters
    picked. With no filter picked, or the board itself as the target ("All of Software"), every filter's groups.
    A `"groups"` list is polled always, like core.
  - `"everything": true` (Sales, Operations, People & Legal): every pack in every folder, audience ignored. A
    profile with one such board polls everything.
- **Group names are global.** A named group selects that group in every folder whose audience has the board:
  P&D's `fintech` takes `tech/fintech` and `shared/fintech`.
- A mixed profile polls the union of its boards' selections. A source in no pack (one the user added) is always
  polled.
- Audiences today: finance/ {finance}; shared/ {finance, software, data_ml, hardware, product, design,
  healthcare}; tech/ {software, data_ml, hardware, product, design, healthcare}; health/ {healthcare}.

**Product and Design today.** Each lists the same 9 groups and nothing else (no `core`, no `filters`):
`big_tech`, `lists`, `enterprise_saas`, `sales_marketing_software`, `consumer_tech`, `developer_tools`, `ai_apps`,
`canadian_tech` and `fintech`.
- They select 16 packs: 8 in shared/ and 8 in tech/. `lists` exists only in shared/ and `sales_marketing_software`
  only in tech/.
- The packs hold 323 sources, 319 of them enabled: shared 130, tech 189, finance 0, health 0. The 4 disabled ones
  are in section 7.9.
- Product, Design and Product+Design poll the same 319 (bundle hash `307abf02da7972b4`, section 2.5).
  `sources_polling_profiles.py` reproduced every sample profile's list and hash from `main`'s code.
- 2 of the 319 are LinkedIn sources: the company searches `linkedin_us_hard_to_reach` and
  `linkedin_canada_hard_to_reach` in `tech/big_tech`. Product and Design have no LinkedIn search of their own.

### 7.2 Which existing groups carry P&D postings

Stored P&D postings by folder (`sources_polling_groups.out`, `sources_polling_core.out`):

| Folder | Product all / open | Design all / open | Core product / design (all) |
|---|---|---|---|
| shared/ | 6,275 / 5,157 | 3,675 / 3,126 | 3,869 / 1,040 |
| tech/ | 3,001 / 2,822 | 2,071 / 1,905 | 1,603 / 557 |
| finance/ | 561 / 489 | 196 / 167 | 435 / 77 |
| health/ | 550 / 543 | 353 / 348 | 306 / 78 |
| **Total** | **10,387 / 9,011** | **6,295 / 5,546** | **6,213 / 1,752** |

Per group, tech/ and shared/ together (what a group name in the manifest selects), sorted by core P&D
(`sources_polling_core.out`). "Sources" counts the sources in the group's packs, disabled ones included. The last
column names the options in section 7.3 that add the group; "E (P, D)" means both boards' option E lists take it.

| Group | Sources | Product all / open | Design all / open | Core product all / open | Core design all / open | Core P&D | Polled today, or added by |
|---|---|---|---|---|---|---|---|
| `big_tech` | 31 | 2,414 / 2,202 | 735 / 647 | 1,052 / 937 | 249 / 203 | 1,301 | today |
| `lists` | 15 | 1,385 / 1,232 | 933 / 865 | 1,073 / 930 | 169 / 163 | 1,242 | today |
| `financial_services_tech` | 17 | 774 / 562 | 130 / 96 | 660 / 485 | 64 / 48 | 724 | B, C, D, E (P, D) |
| `consumer_tech` | 57 | 556 / 457 | 317 / 247 | 423 / 350 | 172 / 137 | 595 | today |
| `enterprise_saas` | 52 | 334 / 253 | 177 / 130 | 235 / 184 | 118 / 82 | 353 | today |
| `fintech` | 40 | 243 / 207 | 112 / 95 | 182 / 157 | 84 / 74 | 266 | today |
| `health_tech` | 39 | 250 / 234 | 89 / 81 | 200 / 190 | 49 / 46 | 249 | B, C, D, E (P, D) |
| `devices_iot` | 23 | 289 / 260 | 235 / 210 | 151 / 132 | 82 / 71 | 233 | B, C, D, E (P, D) |
| `gaming` | 19 | 89 / 87 | 221 / 218 | 67 / 65 | 142 / 141 | 209 | B, C, D, E (P, D) |
| `security` | 43 | 212 / 183 | 47 / 39 | 171 / 149 | 33 / 27 | 204 | B, C, D, E (P, D) |
| `semiconductors` | 35 | 501 / 459 | 1,206 / 1,057 | 152 / 141 | 29 / 25 | 181 | B, D, E (P) |
| `defense_aerospace` | 34 | 591 / 493 | 769 / 698 | 88 / 68 | 86 / 79 | 174 | B, D, E (P, D) |
| `data_infrastructure` | 30 | 172 / 114 | 26 / 21 | 139 / 86 | 20 / 17 | 159 | B, D, E (P) |
| `robotics_autonomy` | 29 | 251 / 217 | 182 / 151 | 88 / 77 | 40 / 36 | 128 | B, D, E (P, D) |
| `developer_tools` | 37 | 135 / 112 | 54 / 40 | 99 / 78 | 26 / 19 | 125 | today |
| `ai_infrastructure` | 35 | 159 / 139 | 45 / 42 | 87 / 80 | 30 / 29 | 117 | B, D, E (P) |
| `canadian_tech` | 35 | 111 / 98 | 56 / 50 | 79 / 70 | 30 / 29 | 109 | today |
| `ai_apps` | 30 | 85 / 73 | 59 / 48 | 70 / 62 | 38 / 29 | 108 | today |
| `cloud_infrastructure` | 11 | 176 / 156 | 25 / 25 | 90 / 85 | 10 / 10 | 100 | B, D, E (P) |
| `ai_labs` | 25 | 142 / 120 | 74 / 62 | 54 / 47 | 39 / 34 | 93 | B, E (P, D) |
| `ratings_data` | 5 | 82 / 68 | 12 / 11 | 80 / 66 | 8 / 7 | 88 | B, E (P) |
| `bank_technology` | 12 | 83 / 69 | 34 / 21 | 62 / 49 | 15 / 11 | 77 | B, E (P, D) |
| `sales_marketing_software` | 26 | 60 / 56 | 37 / 33 | 43 / 41 | 27 / 23 | 70 | today (D drops it) |
| `asset_managers` | 4 | 59 / 34 | 16 / 11 | 55 / 32 | 12 / 8 | 67 | B, E (P) |
| `bulge_brackets` | 2 | 23 / 16 | 10 / 6 | 20 / 13 | 2 / 1 | 22 | |
| `climate_energy` | 16 | 41 / 33 | 68 / 61 | 16 / 13 | 6 / 5 | 22 | |
| `pensions_insurance` | 4 | 18 / 11 | 8 / 5 | 10 / 3 | 2 / 1 | 12 | |
| `telecom` | 2 | 7 / 4 | 17 / 12 | 3 / 2 | 9 / 5 | 12 | |
| `quantum` | 6 | 17 / 17 | 13 / 13 | 10 / 10 | 0 / 0 | 10 | |
| `private_markets` | 5 | 8 / 5 | 1 / 1 | 7 / 4 | 1 / 1 | 8 | |
| `quant_trading` | 28 | 7 / 6 | 2 / 1 | 5 / 4 | 2 / 1 | 7 | |
| `swe_lists` | 2 | 1 / 1 | 20 / 19 | 0 / 0 | 2 / 2 | 2 | |
| `ai_lists` | 1 | 1 / 1 | 0 / 0 | 1 / 1 | 0 / 0 | 1 | |
| `software_core` | 2 | 0 / 0 | 1 / 1 | 0 / 0 | 1 / 1 | 1 | |
| `canadian_banks` | 1 | 0 / 0 | 2 / 1 | 0 / 0 | 0 / 0 | 0 | |
| `hardware_core` | 2 | 0 / 0 | 13 / 13 | 0 / 0 | 0 / 0 | 0 | |
| **Total** | | **9,276 / 7,979** | **5,746 / 5,031** | **5,472 / 4,611** | **1,597 / 1,365** | **7,069** | |

What the table says:
- **Today's 9 groups miss about 40%.** They carry 5,323 of the 10,387 stored product postings (51%) and 2,480 of
  the 6,295 design postings (39%). On the core proxy they carry 3,256 of the 5,472 core product postings in tech/
  and shared/ (60%) and 913 of the 1,597 core design postings (57%). The other groups hold 2,216 core product and
  684 core design postings that a P&D-only profile never polls: 2,900 of 7,069 (41%).
- **The tail is long, unlike Healthcare's.** Healthcare took `lists` (299) and `health_tech` (859) because nothing
  else carried more than 27. Here 15 unpolled groups carry between 724 and 67 core P&D postings. Then the count
  drops to 22 (`bulge_brackets`, `climate_energy`) and below. The break is there.
- Today's weakest group, `sales_marketing_software`, carries 70 core postings on 26 sources (2.7 a source). Every
  group above the break carries more per source: `financial_services_tech` 42.6, `gaming` 11.0, `devices_iot`
  10.1, `cloud_infrastructure` 9.1, `health_tech` 6.4, `semiconductors` 5.2, `defense_aerospace` 5.1, `security`
  4.7 (the research's division of the table).
- **Raw counts mislead in two groups.** `semiconductors`' 1,206 raw design postings are chip work ("design
  engineer", "digital design engineer", "IC design engineer", "layout designer"), and 29 pass the core proxy.
  `defense_aerospace`'s 769 are mostly mechanical "design engineer" titles, and 86 pass. So option E never gives
  Design `semiconductors`.
- **Who carries the core postings** in the groups not polled today (top sources, `sources_polling_core.out`):

| Group | Top sources (core P&D, all) |
|---|---|
| `financial_services_tech` | `capital_one` 323, `mastercard` 170, `american_express` 49, `visa` 34, `paypal` 28 |
| `health_tech` | `veeva_systems` 70, `unitedhealth_group` 65, `oscar_health` 20, `intuitive_surgical` 18 |
| `devices_iot` | `motorola_solutions` 37, `garmin` 27, `siemens_us` 22, `verkada` 18 |
| `gaming` | `electronic_arts` 39, `epic_games` 29, `scopely` 26, `riot_games` 23, `ubisoft` 23, `roblox` 19 |
| `security` | `palo_alto_networks` 62, `okta` 29, `vanta` 12 |
| `semiconductors` | `qualcomm` 37, `micron` 18, `lam_research` 18, `amd` 16 |
| `defense_aerospace` | `anduril` 39, `booz_allen_hamilton` 19, `blue_origin` 16, `palantir` 13 |
| `data_infrastructure` | `elastic` 53, `mongodb` 25, `fivetran` 19, `snowflake` 15 |
| `robotics_autonomy` | `ford_motor_company` 34, `general_motors` 25, `applied_intuition` 13 |
| `ai_infrastructure` | `databricks` 32, `scale_ai` 17, `nebius` 14 |
| `cloud_infrastructure` | `hpe` 22, `cloudflare` 14, `netapp` 13 |
| `ai_labs` | `openai` 26, `anthropic` 21, `perplexity` 10 |
| `ratings_data` | `bloomberg` 38, `moodys` 24, `sp_global` 15 |
| `bank_technology` | `citi_tech` 20, `jpmorgan_tech` 18, `goldman_sachs_tech` 14 |
| `asset_managers` | `fidelity` 30, `blackrock` 23, `vanguard` 14 |

**Per filter.** `sources_polling_filter_groups.py` counted titles shaped like each starting filter, on any board,
per group (the research's regexes; the first matching bucket wins). Option E's per-filter lists come from it. Each
row gives the groups a filter adds beyond core, with that filter's titles in each (the sums are mine):

| Filter | Groups it adds (filter-shaped titles there) | Titles in them |
|---|---|---|
| `product.product_management` | `financial_services_tech` 731, `health_tech` 201, `security` 196, `devices_iot` 178, `data_infrastructure` 157, `cloud_infrastructure` 111, `ai_infrastructure` 108, `bank_technology` 93, `ratings_data` 78, `gaming` 74, `ai_labs` 62, `asset_managers` 58 | 2,047 |
| `product.technical_pm` | `health_tech` 43, `defense_aerospace` 23, `financial_services_tech` 21, `bank_technology` 19, `devices_iot` 15, `ratings_data` 14, `robotics_autonomy` 8, `semiconductors` 7, `cloud_infrastructure` 5, `ai_infrastructure` 4, `data_infrastructure` 1 | 160 |
| `product.apm_programs` | none: 633 of the 760 APM-shaped titles are in `lists` and 22 in `big_tech`, both core; plus the new APM pack (section 8) | – |
| `product.growth_pm` (if kept, D16) | `financial_services_tech` 1 | 1 |
| `product.product_ops` | `financial_services_tech` 26, `defense_aerospace` 19 | 45 |
| `product.product_analytics` | `security` 10, `financial_services_tech` 9, `data_infrastructure` 5 | 24 |
| `design.product_design` | `gaming` 84, `defense_aerospace` 61, `devices_iot` 54, `health_tech` 44, `bank_technology` 42, `financial_services_tech` 40, `robotics_autonomy` 34, `security` 32, `ai_labs` 27 | 418 |
| `design.ux_research` | `health_tech` 3, `financial_services_tech` 2 | 5 |
| `design.visual_brand` | `defense_aerospace` 33, `gaming` 21, `financial_services_tech` 17 | 71 |
| `design.content_design` | `financial_services_tech` 13 | 13 |
| `design.design_engineering` | none | – |
| `design.industrial_design` | `devices_iot` 30, `robotics_autonomy` 10, `defense_aerospace` 6; plus the new industrial design pack (section 8) | 46 |

- These lists are the research's suggestion (judgement). The filters themselves are section 3's, so the lists
  follow section 3's final set. A lone `growth_pm` adds one group, which holds 1 growth-shaped title;
  `defense_aerospace` holds 16. Because "All of Product" polls every filter's groups, the per-filter lists matter
  only to a profile that picks a filter.
- Industrial design is thin everywhere: 107 such titles in all, the most in `devices_iot` (30), `lists` (28),
  `big_tech` (13), `health/medtech` (11) and `robotics_autonomy` (10). So it needs its own pack.
- Program-manager titles (4,976 on any board, kept out of every bucket above) sit mostly in `big_tech` 1,792,
  `defense_aerospace` 530, `semiconductors` 401, `lists` 349 and `robotics_autonomy` 202. Whether they stay on
  Product is D2's question (§4.1.6); it changes which groups `technical_pm` needs.
- Software's and AI & Data's manifest entries list `bank_technology` with `bulge_brackets`, `canadian_banks`,
  `asset_managers`, `private_markets`, `pensions_insurance` and `ratings_data`; the manifest `_readme` says "The
  finance firms' shared groups sit in the tech filters beside bank_technology." Option E takes `bank_technology`,
  `ratings_data` and `asset_managers` only. The other four carry 22, 0, 8 and 12 core P&D postings. Adding them
  was not counted.

### 7.3 Polling options, and what each profile polls

`sources_polling_profiles.py` (options A–D) and `sources_polling_option_e.py` (option E). Product and Design get
the same groups in A–D. No option counts the new P&D packs yet (N sources, section 8).

- **A.** Today's 9 groups. No change.
- **B.** One flat list of 24 groups: today's 9 plus every group above the break (67 core or more):
  `financial_services_tech`, `health_tech`, `devices_iot`, `gaming`, `security`, `semiconductors`,
  `defense_aerospace`, `data_infrastructure`, `robotics_autonomy`, `ai_infrastructure`, `cloud_infrastructure`,
  `ai_labs`, `ratings_data`, `bank_technology` and `asset_managers`.
- **C.** Lean: today's 9 plus the 5 groups with 200 core or more (`financial_services_tech`, `health_tech`,
  `devices_iot`, `gaming`, `security`). 14 groups.
- **D.** Strict, 100 core or more: drops `sales_marketing_software` (70) and adds the 11 unpolled groups at 100
  or more (C's five plus `semiconductors`, `defense_aerospace`, `data_infrastructure`, `robotics_autonomy`,
  `ai_infrastructure` and `cloud_infrastructure`). 19 groups. It is shown to price a drop.
- **E (core + filters, like Software).** `core` = today's 9 plus the new P&D core packs, so a profile that picks
  one filter never polls less than today. Each filter adds the groups in section 7.2's per-filter table.
  "All of Product" names the same 24 groups as B. "All of Design" names 18: B's minus `semiconductors`,
  `data_infrastructure`, `ai_infrastructure`, `cloud_infrastructure`, `ratings_data` and `asset_managers`.

Sources polled by each sample profile (section 2.5's profiles, plus four mixes the research added). Existing
sources only:

| Profile | Today | A | B | C | D | E |
|---|---|---|---|---|---|---|
| product | 319 | 319 | 679 | 460 | 608 | 679 |
| design | 319 | 319 | 679 | 460 | 608 | 559 |
| product+design | 319 | 319 | 679 | 460 | 608 | 679 |
| finance+product | 536 | 536 | 759 | 629 | 710 | 759 |
| finance+design (not in `MIXES`) | 536 | 536 | 759 | 629 | 710 | not counted |
| software+product | 713 | 713 | 742 | 713 | 742 | 742 |
| software+design | 713 | 713 | 742 | 713 | 742 | 742 |
| data_ml+product (not in `MIXES`) | 560 | 560 | 725 | 645 | 725 | 725 (= B) |
| hardware+design (not in `MIXES`) | 466 | 466 | 705 | 584 | 634 | 620 |
| healthcare+product (not in `MIXES`) | 577 | 577 | 898 | 679 | 827 | 898 (= B) |
| finance, default | 347 | 347 | 347 | 347 | 347 | 347 |
| finance+software | 760 | 760 | 760 | 760 | 760 | 760 |
| software | 713 | 713 | 713 | 713 | 713 | 713 |
| data_ml, hardware, healthcare | 524, 191, 272 | same | same | same | same | same |
| finance+healthcare, software+healthcare, data_ml+healthcare | 595, 932, 743 | same | same | same | same | same |
| sales, operations, people_legal, finance+sales | 1,004 | 1,004 | 1,004 | 1,004 | 1,004 | 1,004 |

- **N comes on top.** Under every option, every profile with Product, Design or an everything board also polls the
  new folder's sources (N, section 7.4). Under E a P&D profile polls the new packs its core and filters name.
- Profiles without a P&D board poll the same sources under every option: a profile polls the union of its boards'
  own selections, and no other board's entry changes. The polling test proves it (section 1).
- "(= B)": E's All of Product names B's 24 groups, so a profile that adds it to another board polls what B gives.
  The option E script didn't run these two profiles. It didn't run finance+design either.

Option E for a single filter (no other filter picked):

| Profile | Today | E | Gained |
|---|---|---|---|
| `product.apm_programs` only | 319 | 319 | 0 |
| `product.product_management` only | 319 | 581 | 262 |
| `product.technical_pm` only | 319 | 589 | 270 |
| `design.product_design` only | 319 | 559 | 240 |
| `design.industrial_design` only | 319 | 405 | 86 |
| `design.ux_research` only | 319 | 375 | 56 |

What each option gains and loses in stored P&D postings. A posting counts only when no posting of its cluster
(`cluster_key`) sits at a source the profile polls both before and after. Raw all / open, then core:

| Profile | B gains (sources; postings) | C gains | D gains | D loses |
|---|---|---|---|---|
| product, design, product+design | 360; 6,715 / 5,751, core 2,721 | 141; 2,282 / 1,927, core 1,582 | 315; 6,229 / 5,370, core 2,409 | 26; 97 / 89, core 70 |
| finance+product, finance+design | 223 (all tech/); 2,127 / 1,968, core 759 | 93 (tech/); 732 / 695, core 483 | 200 (tech/); 2,083 / 1,927, core 731 | 26; 97 / 89, core 70 |
| software+product, software+design | 29; 414 / 350, core 121 | 0 | 29; 414 / 350, core 121 | 0 |
| data_ml+product | 165; 4,201 / 3,758, core 1,065 | 85; 1,063 / 974, core 630 | 165; 4,201 / 3,758, core 1,065 | 0 |
| hardware+design | 239; 2,856 / 2,339, core 2,043 | 118; 1,776 / 1,470, core 1,360 | 194; 2,370 / 1,958, core 1,731 | 26; 97 / 89, core 70 |
| healthcare+product | 321; 6,378 / 5,438, core 2,473 | 102; 1,945 / 1,614, core 1,334 | 276; 5,892 / 5,057, core 2,161 | 26; 97 / 89, core 70 |

- **Option E** gains exactly what B gains on Product's side (same groups). On Design's side All of Design gains
  240 sources; its postings were not counted. Hardware+Design gains 154 sources under E.
- **Mixed profiles gain and never lose under A, B, C and E.**
  - Finance+Product and Finance+Design gain only tech/ sources: Finance already polls every shared/ source.
  - Software+Product and Software+Design gain 29 under B, D and E. They are `robotics_autonomy`, the one B group
    Software doesn't poll. Under C they gain 0.
  - Finance, Finance+Software, Software and the everything boards don't change under any option.
- **Only D loses.** It drops 26 sources, all in `tech/sales_marketing_software`. They hold 97 stored P&D postings
  (89 open, 70 core) found nowhere else. Every profile with P&D loses them except Software+P&D and AI &
  Data+Product, whose other board polls that group. Section 7.8 has the sources and samples.
- **Raw gains overstate B.** Of B's 6,715 raw postings for a Product-only profile, 2,939 sit in `semiconductors`
  (1,643) and `defense_aerospace` (1,296), where most raw titles are chip or mechanical "design engineer" and
  program-manager titles. Those two groups hold 181 and 174 core P&D postings. Samples of B's raw gain:
  `qualcomm` 'Low Power Design/Methodology Engineer' (design), `lockheed_martin` 'Electronics Design Engineer
  II' (design), `anduril` 'People Program Manager' (product).
- What C adds for a Product-only profile (2,282 raw): `financial_services_tech` 882, `devices_iot` 506, `gaming`
  303, `health_tech` 337, `security` 254. Samples: `mastercard` 'Director, Product Management, Customer
  Acquisition and Engagement'; `capital_one` 'Manager, Product Management-Emerging Payments' and 'Principal
  Associate, Learning Experience Designer'; `palo_alto_networks` 'Senior Product Manager'; `kabam` 'Game Designer
  (Contract)'.
- Size: a P&D-only poll goes from 319 existing sources to at most 679, plus N. Software alone polls 713 today.
  LinkedIn time is separate (section 7.5).

**Recommendation (from the report's counts): E.** No profile polls less than today; each filter adds only the
groups its titles sit in; Design never takes `semiconductors`. B if Product and Design stay one flat list. C
leaves 1,139 of B's extra core postings unpolled. D is the only option that loses postings. (D28)

### 7.4 Folder and manifest

**Folder.** The new packs (studios, APM programs, industrial design, Canadian shops: section 8) and the LinkedIn
sources (section 7.5) need a folder. `finance/`, `tech/` and `health/` are closed to new sources, and `shared/`
needs your yes per employer (section 7.7).

| | One `product_design/`, audience `["product", "design"]` | `product/` {product} and `design/` {design} |
|---|---|---|
| Employers hiring for both boards (studios, product shops, Canadian P&D shops) | one source; each board names the packs it wants | a source is defined once, so the other board can't reach it: unless that folder's audience lists both boards (then it is the shared folder anyway), the employer needs two sources |
| LinkedIn | each board's pack in the one folder | one pack per folder |
| Finance | never polls it (not in the audience; `"*"` covers only finance/ and shared/) | same |
| Tech boards, Healthcare | don't poll it (not in the audience) | same |
| Everything boards | gain every new source (N) | same N |
| Test exemption | one folder | two folders |

**Recommendation (report): one `product_design/` folder, audience `["product", "design"]`.** Don't add the tech
boards to its audience now. It would change nothing until they named a group, and it keeps the new sources off
their polls. (D29)

**Manifest entry (option E).** New folder after `health` (pack order follows the manifest's folder order); the
other four folders are unchanged:

```json
"product_design": {"fields": ["product", "design"]}
```

```json
"product": {
  "core": ["big_tech", "lists", "enterprise_saas", "sales_marketing_software", "consumer_tech", "developer_tools",
           "ai_apps", "canadian_tech", "fintech", "product_core", "canadian_product_design"],
  "filters": {
    "product_management": ["financial_services_tech", "health_tech", "security", "data_infrastructure",
                           "devices_iot", "ai_infrastructure", "cloud_infrastructure", "ai_labs", "gaming",
                           "ratings_data", "asset_managers", "bank_technology"],
    "technical_pm":       ["semiconductors", "defense_aerospace", "robotics_autonomy", "devices_iot",
                           "cloud_infrastructure", "ai_infrastructure", "data_infrastructure", "health_tech",
                           "financial_services_tech", "bank_technology", "ratings_data"],
    "apm_programs":       ["apm_programs"],
    "growth_pm":          ["financial_services_tech"],
    "product_ops":        ["financial_services_tech", "defense_aerospace"],
    "product_analytics":  ["financial_services_tech", "security", "data_infrastructure"]
  }
},
"design": {
  "core": ["big_tech", "lists", "enterprise_saas", "sales_marketing_software", "consumer_tech", "developer_tools",
           "ai_apps", "canadian_tech", "fintech", "design_core", "canadian_product_design", "design_studios"],
  "filters": {
    "product_design":     ["financial_services_tech", "health_tech", "devices_iot", "gaming", "security",
                           "defense_aerospace", "robotics_autonomy", "bank_technology", "ai_labs"],
    "ux_research":        ["financial_services_tech", "health_tech"],
    "visual_brand":       ["gaming", "defense_aerospace", "financial_services_tech"],
    "content_design":     ["financial_services_tech"],
    "design_engineering": [],
    "industrial_design":  ["devices_iot", "robotics_autonomy", "defense_aerospace", "industrial_design"]
  }
}
```

- The existing groups are option E as counted. The filter keys are the brief's starting filters; section 3 sets
  the final ones.
- The new packs' names and contents are section 8's, and their names are working names until D33 (`apm_programs`
  would become `early_career_programs`). Where they sit here is judgement: `product_core` and
  `design_core` hold each board's LinkedIn sources; `canadian_product_design` is core for both boards;
  `design_studios` is core for Design; `apm_programs` and `industrial_design` serve their filters. If section 8
  widens `apm_programs` into early-career programs for both boards, Design names it too.

**What the manifest and its tests need** (from `intel/sources.py`, `Packs.__init__` ~51):
- Every named group must have a pack, or `Packs` raises. P&D's filter keys must equal the taxonomy's filters
  (the manifest test Healthcare extended).
- New group names must not be used by any existing folder, because group names are global. That rules out, for
  example, a `canadian_tech` pack in the new folder.
- At most 50 sources a pack, each source defined once.
- `_readme` gains the folder and its audience.
- `tests/sources/test_board_polling.py`: the folder joins the `health/` exemption the everything boards get
  (`kept` and `test_boards_that_poll_every_source_also_poll_health_packs`). Every other board stays pinned to
  `board_polling_v0_3_11.json`.
- New source names are checked against `config/source_defaults_history.json`. The retired names are
  `linkedin_us_tech` and `linkedin_canada_tech`; no new source may take them.
- Brief rules kept: no existing source moves or changes; no new source goes in `finance/`, `tech/` or `health/`,
  nor in `shared/` without your yes on that employer.

**What the everything boards gain.** Sales, Operations, People & Legal and every profile with one of them
(Finance+Sales) poll 1,004 sources under every option. They gain the new folder's N sources and nothing else:
section 8's packs (it sets minimums of 8, 10, 6 and 5 verified feeds for studios, Canadian shops, industrial design
and APM programs) and the LinkedIn sources: 4 in the recommended shape, about 18 minutes of LinkedIn lock time
(section 7.5). Finance, the tech boards and Healthcare gain nothing from the folder.

### 7.5 The boards' own LinkedIn sources

Product and Design get their own searches, modelled on `health/health_core.json` (`linkedin_us_health` and
`linkedin_canada_health`, 6 queries each). `linkedin_us` and `linkedin_canada` are not edited. The drafts are in
`E:\product-design-board\phase1\employers_research.md` §5, checked by
`E:\product-design-board\phase1\scripts\employers_research_linkedin.py` (output `employers_research_linkedin.txt`).

Each copies `linkedin_us_health`'s settings: `recency` `r2592000`, `pages` 5, `seed_recency` `r7776000`,
`seed_pages` 8, `min_interval` 1800, `group` "LinkedIn", `priority` 1, a `geography` and a `label`, no
`company_key`. For example:

```json
"linkedin_us_product": {"ats": "linkedin", "location": "United States", "recency": "r2592000", "pages": 5,
  "seed_recency": "r7776000", "seed_pages": 8, "min_interval": 1800,
  "queries": ["product management intern", "associate product manager", "product manager new grad",
              "growth product manager", "product operations intern", "product analyst intern"],
  "group": "LinkedIn", "priority": 1, "geography": "us", "label": "LinkedIn · United States · Product"}
```

The four drafts. The signal is open stored titles, from any source, holding every word of the query: in all
countries / in that country. It is a rough size signal only; LinkedIn's guest search matches more loosely.

| Source (pack) | Label | Queries | Signal (all / country) |
|---|---|---|---|
| `linkedin_us_product` (`product_core`) | LinkedIn · United States · Product | product management intern; associate product manager; product manager new grad; growth product manager; product operations intern; product analyst intern | 413/342; 195/103; 25/15; 102/72; 43/32; 40/31 |
| `linkedin_canada_product` (`product_core`) | LinkedIn · Canada · Product | product management intern; product manager co-op; associate product manager; technical product manager; product analyst co-op; product owner co-op | 413/34; 2/0; 195/22; 504/21; 3/2; 1/1 |
| `linkedin_us_design` (`design_core`) | LinkedIn · United States · Design | product design intern; UX designer intern; UX researcher intern; graphic design intern; content designer; industrial design intern | 74/64; 18/18; 3/3; 20/17; 23/13; 28/27 |
| `linkedin_canada_design` (`design_core`) | LinkedIn · Canada · Design | UX design co-op; product design intern; UX designer; user researcher; graphic designer; industrial design co-op | 2/0; 74/6; 179/9; 16/1; 80/4; 5/0 |

- **Checked against the 13 existing LinkedIn sources** for the same location (`linkedin_us`, `linkedin_canada`,
  `linkedin_quant`; the two Healthcare searches; the two `*_hard_to_reach` company searches; the data, hardware and
  software pairs): 0 exact repeats, 0 word-subset overlaps, and no repeat inside the draft for one location.
- Replaced while drafting: "technical product manager new grad" by "product manager new grad" (15 US titles), and
  "product manager intern" by "product management intern" (342 US). Rejected: "rotational product manager" (0);
  "design co-op" (102 US / 62 Canada) and "product co-op" (79 / 29), mostly engineering roles.
- The Canadian counts are low because stored data is US-heavy. The co-op wording is judgement, not count-backed.
- Misplacement risk (judgement): "product design intern" also returns mechanical "Product Design Engineering
  Intern" roles, and "industrial design intern/co-op" can return industrial-engineering roles. LinkedIn postings
  arrive without text, so the title words must place them; section 3's tests should cover both.
- **Lock time.** All LinkedIn requests take turns on one lock (`_linkedin_lock`, `watcher.py` ~713). Healthcare's
  two 6-query searches took 274 s and 272 s. At about 270 s each (an extrapolation, not measured):
  - a Product-only or Design-only profile adds two searches, about 9 minutes;
  - Product+Design, the everything boards and the GitHub Actions runner add all four, about 18 minutes.
  - The Phase 4 poll-time report gives LinkedIn time on its own line (section 13).
- **The other shape:** one 6-query search per country shared by both boards, in one pack both name. It adds
  about 9 minutes for any P&D profile, but each board gets fewer queries. **Recommendation (report): four
  sources**, as the brief models, so each board polls its own. (D30)

### 7.6 Employers a P&D-only profile never polls: finance/ and health/

A P&D-only profile polls 0 finance/ and 0 health/ sources, today and under every option (folder audiences). Their
P&D postings reach only profiles that also have Finance (finance/), Healthcare (health/) or an everything board.
`sources_polling_fin_health.out`; "copy" means a posting of the same cluster at a tech/ or shared/ source.

**finance/: 757 P&D postings at 21 sources** (561 product / 489 open, 196 design / 167 open; core 512). By employer:

| Employer (sources) | Product all / open | Design all / open | Core P&D | Copy in today's 9 groups | Copy at any tech/shared source |
|---|---|---|---|---|---|
| JPMorgan (`jpmorgan`, `jpmorgan_early`) | 293 / 290 | 91 / 89 | 225 | 19 | 64 |
| Citi (`citi`, `citi_early`) | 133 / 97 | 48 / 41 | 145 | 4 | 51 |
| Morgan Stanley (`morgan_stanley`, `morgan_stanley_early`) | 27 / 24 | 10 / 7 | 24 | 1 | 6 |
| TD (`td`, `td_students`) | 14 / 10 | 16 / 10 | 15 | 4 | 11 |
| Barclays (`barclays`) | 14 / 13 | 13 / 7 | 18 | 3 | 8 |
| RBC (`rbc`, `rbc_early`) | 20 / 9 | 1 / 0 | 18 | 0 | 8 |
| Goldman Sachs (`goldman_sachs`) | 12 / 12 | 3 / 2 | 14 | 0 | 12 |
| BMO (`bmo`) | 11 / 7 | 1 / 0 | 11 | 1 | 2 |
| CIBC (`cibc`) | 7 / 5 | 5 / 3 | 8 | 0 | 1 |
| Wells Fargo (`wells_fargo`) | 10 / 3 | 1 / 1 | 10 | 0 | 0 |
| Deutsche Bank (`deutsche_bank`) | 5 / 5 | 4 / 4 | 8 | 0 | 5 |
| StepStone, Apollo, PJT Partners | 5 / 4 | 0 / 0 | 5 | 0 | 0 |
| Finance's LinkedIn searches (`linkedin_quant`, `linkedin_canada`; not employers) | 10 / 10 | 3 / 3 | 11 | 1 | 2 |
| **Total** | **561 / 489** | **196 / 167** | **512** | **33** | **170** |

- By pack: `finance/bulge_brackets` 494 / 444 product (core 371) and 170 / 151 design (core 73);
  `finance/canadian_banks` 52 / 31 (core 49) and 23 / 13 (core 3); `finance/linkedin` 10 / 10 and 3 / 3;
  `finance/private_markets` 4 / 3; `finance/boutiques_middle_market` 1 / 1 (`sources_polling_hq.out`).
- Samples (seed 1219): `jpmorgan:210796319` 'Product Designer, Vice President - Legal Tech'; `jpmorgan:210787803`
  'Senior Associate, Product Manager – Open Banking'; `citi_early` 'UX Product Research and Strategy Lead';
  `goldman_sachs:182390` '2027 | Americas | New York City Area| AWM User Experience Design | Summer Analyst';
  `td` 'Job Posting Title L&H Product Management Intern/Co-op (Winter 2027)'; `barclays` 'UX Researcher'.
- What the broad words put there today (not core): `jpmorgan:210799138` 'AI Principal Technical Program Manager';
  `citi` 'Account Manager for Internal Creative Agency'; `td` 'Solutions Design IT Specialist (Java)'.

**The `bank_technology` route.** `tech/bank_technology` holds the banks' own tech feeds, which P&D can poll without
a new source (it is in B and E). They carry P&D postings of their own: 83 product / 34 design (core 62 / 15).
`jpmorgan_tech` 30 / 6, `citi_tech` 17 / 10, `goldman_sachs_tech` 13 / 1, `rbc_tech` 7 / 0, `scotiabank_tech` 5 / 0,
`morgan_stanley_tech` 4 / 1, `td_tech` 2 / 9, `barclays_tech` 2 / 2, `bmo_tech` 2 / 0, `deutsche_bank_tech` 1 / 4,
`cibc_tech` 0 / 1, `wells_fargo_tech` 0 / 0. And 169 of the 757 finance/ postings have a copy at a source in B's
or E's groups: `jpmorgan_tech` 49, `citi_tech` 47, `zapply_newgrad27` 26, `goldman_sachs_tech` 12, `td_tech` 8,
`rbc_tech` 8, `barclays_tech` 5, `morgan_stanley_tech` 5, `deutsche_bank_tech` 5, `zapply_ca_jobs` 5, `bmo_tech`
2, `cibc_tech` 1, and 1 each at `zapply_ca_intern`, `simplify_newgrad` and `simplify_intern26` (a posting can have
copies at several). The choice for these employers is in section 7.7.

**health/: 903 P&D postings at 131 sources** (550 product / 543 open, 353 design / 348 open; core 384). By pack
(`sources_polling_hq.out`):

| Pack | Product all / open | Core product | Design all / open | Core design |
|---|---|---|---|---|
| `health/pharma` | 190 / 187 | 155 | 96 / 91 | 18 |
| `health/medtech` | 154 / 151 | 99 | 124 / 124 | 31 |
| `health/diagnostics_labs` | 50 / 50 | 22 | 43 / 43 | 11 |
| `health/hospitals_us` | 52 / 52 | 4 | 18 / 18 | 6 |
| `health/research_institutes` | 39 / 38 | 3 | 43 / 43 | 3 |
| `health/payers` | 20 / 20 | 8 | 5 / 5 | 5 |
| `health/cro_cdmo` | 17 / 17 | 8 | 7 / 7 | 1 |
| `health/public_health` | 14 / 14 | 1 | 5 / 5 | 3 |
| `health/hospitals_canada` | 8 / 8 | 2 | 3 / 3 | 0 |
| `health/biotech` | 5 / 5 | 4 | 7 / 7 | 0 |
| `health/health_core` | 0 / 0 | 0 | 2 / 2 | 0 |
| `health/pharmacy_consumer` | 1 / 1 | 0 | 0 / 0 | 0 |
| **Total** | **550 / 543** | **306** | **353 / 348** | **78** |

- Top sources (product / design, all; core P&D): `gsk` 37 / 2 (37), `medtronic` 32 / 5 (17), `amgen` 26 / 11 (26),
  `stryker` 20 / 16 (19), `philips` 20 / 19 (20), `johnson_johnson` 22 / 6 (16), `merck` 22 / 3 (21),
  `thermo_fisher_scientific` 10 / 16 (1), `takeda` 7 / 16 (10), `eli_lilly` 7 / 15 (4), `roche` 11 / 9 (9),
  `siemens_healthineers` 6 / 12 (13).
- Hospitals and research institutes carry mostly "program manager" and academic "design" titles
  (`health/hospitals_us`: 52 raw product, 4 core).
- 21 of the 903 have a copy at a tech/ or shared/ source, all 21 in today's 9 groups.
- Industrial-design-shaped titles at `health/medtech`: 11. Medtech carries 130 core P&D postings.
- Samples (seed 1219): `philips` 'Product Design Internship – Philips Avent Experience Innovation'; `stryker`
  'Summer 2027 Internship - Interaction Design - Washington'; `becton_dickinson` 'Staff Industrial Designer';
  `gsk:450508` 'Senior, AI Product Manager (Process Development Science)'; `siemens_healthineers:P-100317` 'Sr. UX
  Research & Usability Professional'. Not core: `philips` 'Design Quality Engineer'; `amgen` 'Senior Program
  Manager'; `university_of_toronto` 'Sessional Lecturer ENG328H5S LEC0102 Writing for Games and Narrative Design'.

**Options for the health/ employers:**
- (a) Leave them Healthcare's. A P&D-only profile never sees pharma PMs or medtech industrial designers.
- (b) Add `product` and `design` to the health/ folder's audience, and name health groups in P&D's filters (for
  example `industrial_design` + `medtech`; `product_management` + `pharma`, `medtech`). No other board's polling
  changes: no other board names those groups, and the everything boards poll them already. But it ends "health/
  is Healthcare-only", and the manifest `_readme`, the folder test and the gate's exemption rule change with it.
- (c) New `product_design/` sources for those employers' design job families.

**Recommendation (report):** (a) for pharma, hospitals and research institutes; (b) only for medtech, and only if
you want industrial design there. (D32)

### 7.7 Employers that hire for both P&D and Finance

An employer that hires for both can't get a source in `shared/` without changing what Finance polls: Finance's
`"*"` polls every shared/ pack. So each one goes to you with its counts.

- **The finance/ banks** (section 7.6). JPMorgan 384 P&D postings (core 225), Citi 181 (core 145), Morgan Stanley
  37, TD 30, Barclays 27, RBC 21, Goldman Sachs 15, BMO 12, CIBC 12, Wells Fargo 11, Deutsche Bank 9, StepStone 3,
  Apollo 1, PJT Partners 1. Their existing sources never move.
- **Visa and Mastercard**, already `shared/` employers (`shared/financial_services_tech`). Section 8 proposes
  second sources on their early-career Workday sites, which carry the APM and PM-intern programs and finance
  programs too. Stored rows naming them, on any source (a company-name match, not distinct postings): Visa
  1,151 / 1,006 open (open product 47, design 5), Mastercard 1,886 / 1,107 (open product 138, design 26).
- **Existing shared/ employers** need nothing: Finance polls them already, so when P&D names their groups Finance's
  polling doesn't change. The largest are in `financial_services_tech` (core P&D: Capital One 323, Mastercard 170,
  American Express 49, Visa 34, PayPal 28).

| Option | Finance's polling | P&D | Trade-off |
|---|---|---|---|
| (a) Leave the banks as they are | unchanged | P&D-only profiles miss the 757 finance/ postings | none to build |
| (b) Reach the banks' tech feeds through `bank_technology` | unchanged | recovers 169 copies and the feeds' own 83 product / 34 design | no new source; already part of B and E |
| (c) A new `product_design/` source for an employer's product/design job family | unchanged | polled by P&D profiles only | a Finance+P&D profile polls the employer twice and stores both copies (clustered); Finance-only profiles don't see finance programs on such a source |
| (d) A new `shared/` source | **changes**: Finance polls it, and so does every other board that names its group | polled by P&D | needs your yes per employer |

**Recommendation (report):** (b), and (a) for the rest. Consider (c) only for JPMorgan and Citi, the two with real
volume. Visa's and Mastercard's early-career sites go in `product_design/` with the employer's `company_key` and a
`label`. No (d) without your yes. (D31)

### 7.8 Postings from sources a profile stops polling

**What happens to them.**
- Nothing closes them. `update_lifecycle` (`intel_store.py` ~172) closes a posting only when a poll misses it.
  They keep their last status and a frozen `last_seen`, their fit drifts down through freshness, and board views
  still show them.
- But `prune()` (`watcher.py` ~4369, every cycle) deletes every posting whose `last_seen` is more than
  `PRUNE_AFTER_DAYS` (90, `watcher.py:59`) days old unless it has an application. So they go about 90 days after
  the last poll that saw them.
- `plans/healthcare-board.md` (~528) and `plans/cs-tech-sources.md` (~225) say they are never deleted. That is
  wrong (section 15).

**Counts.**
- Options A, B, C and E stop polling nothing for any profile, so nothing is lost.
- Option D stops 26 sources for every profile with P&D except Software+P&D and AI & Data+Product. All 26 are
  tech/ (`tech/sales_marketing_software`); shared/, finance/ and health/ lose 0.
- They found 97 stored P&D postings (89 open, 70 core) that no source still polled has a copy of. Per source:
  `intercom` 15, `qualtrics` 12, `braze` 11, `zoominfo` 9, `klaviyo` 9, `similarweb` 8, `6sense` 6, `cresta` 5,
  `aircall` 3, `salsify` 3, `contentsquare` 3, `demandbase` 2, `five9` 2, `freshworks` 2, `amplemarket` 2, `gong` 1,
  `klue` 1, `walkme` 1, `loopio` 1, `outreach` 1. The other 6 sources have none.
- Samples: `klue` 'Staff Product Manager'; `similarweb` 'Senior Brand Designer'; `walkme` 'Product Designer';
  `klaviyo` 'Senior Product Designer'; `zoominfo` 'Senior Product Manager - SAP FICO'; `6sense` 'Sr. Content
  Designer'; `braze` 'Program Manager, Partnerships'; `qualtrics` 'Associate Instructional Designer'.
- Under D those 97 would be deleted about 90 days after their last poll, unless you applied to them. This is part
  of (D28).
- Under E, a profile that narrows from all filters to one stops polling the other filters' groups, and their
  postings go the same way. That is how Software's filters work today.

**Leaving `everything`: what applies.** Product and Design don't poll `everything` today, so leaving it costs
nothing:
- A P&D-only profile polls 0 finance/ sources today and under every option. The acceptance criterion already
  holds.
- No group brings finance/ (38 sources) or health/ (219) back. Their P&D postings, 757 and 903, are what a
  P&D-only profile never sees: sections 7.6 and 7.7.
- Postings that only the stopped sources found: 0 under A, B, C and E; 97 under D.

### 7.9 Disabled sources in P&D's groups

4 of the 323 sources in today's 16 packs are disabled; option B's and E's `ai_labs` pack adds a fifth. Installed
and shipped configs disable the same 10 (`E:\product-design-board\phase1\config_robots_keys.md` §1), and you
disabled or enabled none. None of the five has a stored posting.

| Source | Pack | ATS | Why, from its `_note` | Covered by |
|---|---|---|---|---|
| `microsoft` | `shared/big_tech` | microsoft (query "software engineer intern") | `gcsservices.careers.microsoft.com` serves a certificate that doesn't cover the host, so every TLS check fails | `microsoft_careers` (`tech/big_tech`, eightfold: 2,934 stored, 282 P&D) and `microsoft_finance` (`shared/big_tech`: 479 stored, 68 P&D) |
| `retool` | `shared/developer_tools` | ashby | apply links point at Gem (`jobs.gem.com/retool`); "watcher has no Gem adapter" | the lists. `watcher.py` now has a `gem` adapter (section 15) |
| `rippling` | `shared/enterprise_saas` | greenhouse | in-house ATS (`ats.rippling.com`), no public API | the lists |
| `simplify_intern27` | `shared/lists` | github_listings (`SimplifyJobs/Summer2027-Internships`) | "enable once this repo exists"; it 404s until then | the other lists |
| `deepmind` (B and E only) | `shared/ai_labs` | greenhouse | Google DeepMind routes openings through Google Careers; no separate board API | the lists |

- None of them changes in this work. Enabling one edits an existing source and changes what Finance, every other
  board that names its group and the everything boards poll, so it needs your yes.
- `retool` may be readable again through `gem`. That is unverified; section 15 records it.

---

## 8. Candidate employers and new packs

136 candidate employers for four new packs. Every ATS and identifier below was seen in a job or board URL that a
web search returned (about 80 searches). None was guessed. None was fetched with the app's reader: one careers page
was fetched (SOTI, it answered 404) and no Eightfold site. So nothing here is verified, and nothing ships until
Phase 4 fetches its feed whole (§13). The boards' own LinkedIn searches are §7.5's.

Counts are rows in `E:\product-design-board\census\census.db` (410,486 titled postings, `main`'s placement). "Open"
means status != 'closed'. Title patterns are the scripts' own regexes, so a count is a pattern count, not a filter
count. Report: `E:\product-design-board\phase1\employers_research.md`; scripts `employers_research_*.py` in
`E:\product-design-board\phase1\scripts\`, outputs beside the report.

### 8.1 What Foothold already reads (the dedupe base)
- **1,014 sources:** tech 438, shared 319, health 219, finance 38 (`employers_research_inventory.json`, one row per
  source with its feed). By ATS: greenhouse 301, workday 253, ashby 165, lever 39, and 39 others.
- **`watcher.py` `ADAPTERS`: 43 keys.** Three limits matter here:
  - `fetch_greenhouse` reads only `boards-api.greenhouse.io`. EU boards (`job-boards.eu.greenhouse.io`) are out.
  - `fetch_lever` has `region: "eu"`.
  - `fetch_taleo` reads Taleo Enterprise only. Taleo Business Edition (`*.tbe.taleo.net`) is a different product.
- Every candidate ATS that has an adapter also has a description path: `DETAIL_FETCHERS`, `PAGE_DETAIL_ATS`, or
  text in the listing (Lever, Ashby, Dayforce).
- **Many employers already read one feed through two or more sources,** each narrowed by `search`, `facets`,
  `categories` or `query` with one `company_key`: Amazon 4; Siemens, TD, CIBC, BMO, Citi, JPMorgan, Morgan Stanley,
  RBC, GE HealthCare, Cigna and CVS Health 3 each; Adobe, Salesforce, Mastercard, Capital One, Walmart and Nike 2
  each, among others.
- **13 LinkedIn sources:** `linkedin_us`, `linkedin_canada`, `linkedin_quant`; `linkedin_us_health`,
  `linkedin_canada_health`; `linkedin_us_hard_to_reach`, `linkedin_canada_hard_to_reach` (`companies` only: Meta,
  Tesla, IBM, Shopify); and the data, hardware and software US/Canada pairs.
- **How each candidate was deduped** (`employers_research_check.py`): its ATS and identifier against every source in
  every folder. The identifier is the token (Greenhouse, Lever, Ashby, SmartRecruiters), tenant + site (Workday),
  account (Workable, BambooHR, Recruitee), client + site (Dayforce) or host (Taleo, Paradox, Eightfold). The check
  also flags a Workday tenant read under another site, and any `companies.json` name or alias that matches.

### 8.2 Where Product and Design roles sit today, per filter
Open stored postings whose title matches each pattern, the sources that carry them, and what the new packs add.
"Lists" are the community GitHub lists (`github_md`, `github_listings`).

Coverage, as the brief asks (Canada first, then the US hubs and remote; 15–40 sources a filter; student roles
first):
- Each new pack serves the filters below and is 27 to 41 candidates long, Canada first in every table. The
  Canadian candidates: studios 17, Canadian shops 34, industrial design 10, APM programs 1.
- Student roles come through the early-career boards (8.4), the APM pack and the studios' internships.
- Four filters get no new candidates: technical PM, growth PM, content design and design engineering. Their roles
  are already on the existing groups (§7.2) and the LinkedIn searches (§7.5) (judgement).

| Filter | Open titles (pattern) | Sources | Largest carriers today | New candidates for it | LinkedIn drafts (§7.5) |
|---|---|---|---|---|---|
| `product.product_management` | 6,693 (product manager/management/owner/lead/director, head/VP of product) | 592 | `zapply_newgrad27` 380, `amazon_tech` 358, `capital_one` 282, `jpmorgan` 272, `derec4_newgrad27` 233 | `canadian_product_design` (34) | product management intern; product manager new grad; product owner co-op |
| `product.technical_pm` | 1,719 (technical program manager, TPM) | 229 | `amazon_tech` 410, `google` 116, `oracle` 94, `jpmorgan` 91, `anduril` 67 | none of its own (judgement: big tech, defense and chip employers already carry it) | technical product manager (Canada) |
| `product.apm_programs` | 92 distinct APM-only postings (120 rows); 701 PM-student rows | 70 (PM-student) | lists: `derec4_newgrad27` 230, `simplify_intern26` 204, `zapply_intern27` 44; direct: `american_express` 9, `databricks` 8 | `apm_programs` (27), early-career boards (8.4) | associate product manager; product manager co-op |
| `product.growth_pm` | not counted | | | none of its own | growth product manager |
| `product.product_ops`, `product.product_analytics` | 370 (product operations/ops/analyst/analytics) | 133 | `simplify_intern26` 30, `linkedin_us_hard_to_reach` 25, `derec4_newgrad27` 18, `simplify_newgrad` 14 | `canadian_product_design` | product operations intern; product analyst intern / co-op |
| `design.product_design` | 1,341 (product designer, UX, UI, interaction, experience, service, design systems) | 340 | `zapply_newgrad27` 55, `apple` 51, `google` 46, `derec4_newgrad27` 41, `jpmorgan` 35 | `design_studios` (41), `canadian_product_design` | product design intern; UX designer intern; UX designer; UX design co-op |
| `design.ux_research` | 55 (strict: UX/user/design researcher) | 41 | `zapply_newgrad27` 4, `linkedin_us_hard_to_reach` 4, `google` 3, then 1–2 per source | studios (IDEO and others) | UX researcher intern; user researcher |
| `design.visual_brand` | 211 (graphic, visual, brand, motion designer, illustrator, art director) | 110 | `booz_allen_hamilton` 14, `zapply_newgrad27` 12, `brex` 6, `salesforce` 6, `target` 5, `apple` 5, `scopely` 5 | `design_studios` (brand agencies) | graphic design intern; graphic designer |
| `design.content_design` | 41 (content designer, UX writer, content strategist) | 32 | `google` 5, then 1–2 per source | none of its own | content designer |
| `design.design_engineering` | 3,385 (design engineer, UX engineer, design technologist) | 195 | `apple` 308, `lockheed_martin` 205, `qualcomm` 169, `amd` 137: mostly chip and mechanical design engineers | none (§4.2 narrows the word first) | none |
| `design.industrial_design` | 77 (strict: industrial designer/design, CMF); 162 with "product design engineer" | 32 (46) | lists 26 (`zapply_intern27` 11, `derec4_newgrad27` 10, `zapply_newgrad27` 5); `garmin` 6, `anduril` 4, `amazon_tech` 3, `apple` 3 | `industrial_design` (34), plus IDEO and Teague (studios) | industrial design intern; industrial design co-op |

- **Lists carry most student and program roles.** Of the 92 distinct open APM-only postings, lists hold 52, direct
  sources 41 and LinkedIn 1. **50 reach Foothold only through lists.** Their stored field: product 96 rows,
  software 12, other 7, healthcare 2, design 1, finance 1, sales 1. The pattern also counts "APM" used as a team
  name (`amazon_newgrad:10578078 'Software Development Engineer, Amazon, APM Twitch'`).
- **PM-student titles (701 open rows) come from 166 employers:** TikTok 58, American Express 33, NVIDIA 23,
  Microsoft 18, GE Vernova 16, SOTI 16.
- **Strict industrial-design titles (77 open, 87 any status) come from 35 employers.** Stored field: design 72,
  product 3, hardware 2.
- **Which existing groups carry stored P&D postings, and which to poll, is §7.2.** The largest packs by open
  stored Product / Design: `shared/lists` 1,232 / 865, `tech/big_tech` 1,259 / 404, `shared/big_tech` 943 / 243,
  `shared/semiconductors` 313 / 681, `shared/defense_aerospace` 314 / 391 (`employers_research_existing.txt`).
  Much of today's stored `design` is engineering, so a design count per employer or pack overstates design roles
  (§4.2).

### 8.3 Employers already polled: big tech and program employers first
The brief asks to check `big_tech` first, because many APM programs are there. Open stored postings
(`employers_research_bigtech.py`); "APM" and "PM student" are the script's patterns, any status / open.

| Source | Open | Product | Design | APM titles | PM-student titles |
|---|---|---|---|---|---|
| `google` | 1,912 | 180 | 48 | 0 / 0 | 0 / 0 |
| `apple` | 3,676 | 227 | 241 | 0 / 0 | 0 / 0 |
| `microsoft_careers` | 2,934 | 249 | 33 | 0 / 0 | 6 / 6 |
| `amazon_tech` | 7,691 | 662 | 60 | 5 / 5 | 2 / 2 |
| `linkedin_us_hard_to_reach` (Meta, Tesla, IBM…) | 1,623 | 103 | 58 | 0 / 0 | 1 / 1 |
| `salesforce` / `salesforce_early` | 1,557 / 17 | 29 / 0 | 22 / 1 | 0 / 0 | 0 / 0 |
| `adobe` / `adobe_university` | 284 / 25 | 17 / 1 | 13 / 0 | 0 / 0 | 2 / 2 and 1 / 1 |
| `uber` | 775 | 36 | 11 | 0 / 0 | 0 / 0 |
| `intuit` | 605 | 45 | 27 | 0 / 0 | 2 / 2 |
| `workday_hq` | 379 | 24 | 1 | 0 / 0 | 0 / 0 |
| `atlassian` | 349 | 13 | 11 | 0 / 0 | 2 / 2 |
| `visa` | 837 | 37 | 5 | 0 / 0 | 1 / 1 |
| `mastercard_early` | 16 | 6 | 0 | 0 / 0 | 7 / 5 |
| `american_express` | 401 | 27 | 7 | 0 / 0 | 10 / 9 |
| `capital_one` | 2,039 | 255 | 46 | 1 / 1 | 0 / 0 |
| `databricks` | 902 | 47 | 5 | 1 / 1 | 10 / 10 |
| `veeva_systems` | 892 | 77 | 1 | 4 / 4 | 0 / 0 |

What this shows:
- **The big APM programs are mostly between seasons.** Google, Meta, Uber and Microsoft show no APM title open.
- **Salesforce's 2 open APM postings reach Foothold only through lists:** `zapply_intern27:10b3f3a72728b8a1`
  "Associate Product Manager (starting summer 2027)" and `sndsh_intern27:f4682d96fb69394f` "Associate Product
  Manager Intern (APM)". `salesforce` and `salesforce_early` read Salesforce's Workday site but hold neither. Why is
  not established; Phase 4 runs one `watcher.py --list` on `salesforce` to find out (§15).
- **Visa's APM postings sit on a second Workday site,** `Visa_Early_Careers`, which `visa` (site `Visa`) doesn't
  read. Stored: `simplify_newgrad:a80913f5-…` "Associate Product Manager New Grad" (London, open), and one 2026 New
  Grad APM posting on two lists, closed. Visa's 2027 APM program was also posted on site `Visa` (REF088601W, seen
  on the web), yet no Visa APM row is stored from `visa`; its window (Sept 17–24) may have closed between reads (not
  established).
- **Google's "Associate Product Manager Intern" is in London** (`derec4_newgrad27:0bdf40d53d6e1cf7`). `fetch_google`
  reads the United States and Canada only, so it is out of scope, not a gap.
- **`amazon_tech` reads 8 categories**, `project-program-product-management-technical` among them, but not Amazon's
  non-technical PM or design categories (judgement from the config; the category slugs are unconfirmed).
- **`walmart_global_tech` and `nike` read only listed `jobFamilyGroup` facets** (3 and 2 ids). Their design and
  product families are probably outside them (not verified; the ids' labels weren't read).
- **`rippling` is disabled** (in-house ATS, no public API) and has no stored rows, so Rippling's APM program isn't
  polled.
- **Programs already on boards Foothold reads:** Robinhood New Grad APM (`robinhood`), 2K Associate Product Manager
  (`2k`), Workiva PM intern (`workiva`), Patreon PM intern (`patreon`), Appian PM intern (`appian`), Gemini PM intern
  (`gemini`), KnowBe4 APM intern (`knowbe4`), GM Digital Product MBA intern (`general_motors`), DoorDash product
  design intern (`doordash`), Anduril product designer intern (`anduril`), StackAdapt product design intern
  (`stackadapt`). Salesforce's APM program is on `salesforce`'s site but stored only from lists (above).

**Employers the brief names** (`config_robots_keys_employers.py`, stored all / open; P&D = Product + Design):

| Employer | Source (pack, ATS) | Stored | P&D | Entry |
|---|---|---|---|---|
| Figma | `figma` (shared/enterprise_saas, greenhouse) | 189 / 140 | 27 / 20 | none |
| Adobe | `adobe`, `adobe_university` (shared/big_tech, one Workday feed) | 418 / 284; 28 / 25 | 46 / 30; 1 / 1 | none |
| Canva | `canva` (tech/enterprise_saas, smartrecruiters, robots-disallowed: §11.3) | 107 / 56 | 15 / 5 | `canva` |
| Miro | `miro` (tech/enterprise_saas, greenhouse `realtimeboardglobal`) | 21 / 18 | 0 / 0 | `miro` |
| Notion, Airbnb, Spotify, Duolingo, Webflow, Asana | one source each (shared/) | 161 / 148; 284 / 202; 117 / 89; 69 / 57; 23 / 20; 143 / 110 | 9 / 7; 19 / 12; 16 / 11; 17 / 16; 3 / 3; 16 / 14 | none |
| Salesforce | `salesforce`, `salesforce_early` (shared/big_tech, one Workday feed) | 2,338 / 1,557; 30 / 17 | 88 / 51; 3 / 1 | none |
| Intuit | `intuit` (shared/big_tech, radancy, robots-disallowed: §11.3) | 681 / 605 | 78 / 72 | `intuit` |
| Autodesk | `autodesk` (shared/big_tech, Workday site `Ext`) | 490 / **3** (§11.4) | 48 / 1 | none |
| Atlassian, Wealthsimple, Google, Uber | one source each | 392 / 349; 73 / 42; 2,384 / 1,912; 892 / 775 | 30 / 24; 7 / 3; 289 / 228; 51 / 47 | typed |
| Microsoft | `microsoft_careers`, `microsoft_finance` (one Eightfold feed); `microsoft` disabled (TLS cert) | 2,934 / 2,934; 479 / 413; 0 | 282 / 282; 68 / 54 | `microsoft` |
| Apple | `apple`, `apple_finance` | 3,676 / 3,676; 256 / 256 | 468 / 468; 59 / 59 | `apple` |
| Amazon | `amazon_tech`, `amazon_newgrad`, `amazon_finance`, `amazon` (one feed) | 7,691; 2,439; 989; 37 (all open) | 722; 6; 8; 0 | `amazon` |
| Lyft, Pinterest, Dropbox | one source each (shared/) | 251 / 170; 246 / 170; 54 / 24 | 25 / 19; 33 / 23; 8 / 0 | none |
| Meta, Shopify | no own source (they block their sites): `linkedin_us_hard_to_reach`, `linkedin_canada_hard_to_reach` | Meta 996 on the first; Shopify 9 on the second | 119; 3 | `meta`, `shopify` |
| LinkedIn (employer), Slack | none. Slack's roles are on Salesforce's Workday: 56 stored / 40 open titles name Slack, 2 P&D | | | none |
| 14 studios and agencies (IDEO, frog, Pentagram, Huge, R/GA, Fjord, Deloitte Digital, Thoughtworks, Myplanet, Rangle, Normative, Connected, Klick, Teehan+Lax) | none has a feed today; 8.5.1 lists those found | 0 for 10 of them. On lists: "Accenture" 54, "Deloitte" 23, Thoughtworks 8; frog 0 as frog (14 Capgemini rows) | | `accenture`, `deloitte` for the owners |

The 13 employers here with no `companies.json` entry (15 sources, 4,841 stored / 3,016 open, 359 P&D / 209 open)
are the brief's "Shared employers with no entry": §6.5.

### 8.4 Early-career boards of employers already polled
These are second boards of an employer Foothold already reads, or narrower reads of a feed it already reads, plus
the student sites of six employers it doesn't poll yet. Each new source keeps the employer's `company_key` (the key
its stored rows resolve to) and gets a `label` (brief, "Required fields").
- Visa's and Mastercard's sites carry finance programs too, so where they go is §7.7's decision.
- The second sources for Workday, Amazon, Loblaw, Samsara, Walmart and Nike: D34
- SOTI, CoStar, Zynga, ID.me, C3 AI and nCino aren't polled at all, so they are ordinary candidates of the APM pack
  (8.5.4).

| Employer | Board (ATS: identifier) | Existing source and what it reads | Stored rows (all / open; open P, D) | Note |
|---|---|---|---|---|
| Visa | workday `visa` / `Visa_Early_Careers` (wd5) | `visa` reads site `Visa` | 1,151 / 1,006 (47, 5); 953 from `visa`, which holds 242 Finance (213 open) | APM rotational program and APM interns are here |
| Mastercard | workday `mastercard` / `Campus` (wd1) | `mastercard`, `mastercard_early` read site `CorporateCareers` | 1,886 / 1,107 (138, 26); 1,800 from the two sources, which hold 564 Finance (342 open) | Launch Program (Associate Product Specialist) and PM interns seen |
| Workday | workday `workday` / `Workday_Early_Career` (wd5) | `workday_hq` reads site `Workday` (614 stored, 26 Finance) | 80 / 80 (8, 1), all through lists | Product Manager Intern 2027 seen. Its 80 list rows key `workday`; `workday_hq`'s own rows key `workday_hq` (§15) |
| Amazon | amazon_jobs categories `design`, `project-program-product-management-non-tech` | the four Amazon sources (same feed) | 11,707 / 11,626 (677, 74) | slugs unconfirmed (judgement from amazon.jobs) |
| Loblaw Companies | paradox `careers.loblaw.ca`, "Digital & Ecommerce" category | `loblaw_pharmacy` (health/pharmacy_consumer) reads category Pharmacy, Healthcare | 228 / 217 (0, 0); 210 from `loblaw_pharmacy` | category name from posting pages; confirm on the site's facet list |
| Samsara | greenhouse `recruitingprograms` | `samsara` reads token `samsara` | 439 / 366 (8, 11); 397 from `samsara` | only a 2023 APM posting seen; board may be retired |
| Walmart, Nike | their design and product job families | `walmart_global_tech` (3 `jobFamilyGroup` ids) and `nike` (2) read listed facets; `walmart_finance` and `nike_finance` read the same feeds | not counted | the ids' labels weren't read; not verified |
| SOTI | workday `soti` / `SOTI-Next-Gen` (wd3) | none (SOTI isn't polled) | 54 / 53 (16, 0), all through lists | 12-month interns; the main site `Careers` is in 8.5.2 |
| CoStar Group | workday `costar` / `Costar_Campus` (wd1) | none | 61 / 43 (1, 0), all through lists | main board is Eightfold (`costar.eightfold.ai`), not fetched |
| Zynga | greenhouse `zyngaearlycareers` | none (Take-Two reads `taketwo`, 2K reads `2k`) | 0 | 12-month Rotational Product Manager program |
| ID.me, C3 AI, nCino | greenhouse `idmeuniversityrecruiting`, `c3ascend`, `ncinoearlytalent` | none | 26 / 25 (2, 0); 22 / 22 (6, 0); 2 / 2 (0, 0) | ID.me Summer 2027 New Grad APM seen |

- None of these shares a feed with an existing source except Amazon and Loblaw, which read narrower categories of
  one. Workday tenants match for Visa, Mastercard and Workday, but the sites differ.
- **Programs are seasonal** (windows in §5). Visa's 2027 APM window was 2026-09-17 to 09-24; Cox's PM interns
  closed 2026-10-16; T-Mobile posts internships "late summer/early fall"; Shopify's APM applications open Nov 2 (all
  seen on the web). A verification fetch can return few or no program postings. A valid feed with zero roles is
  fine (brief).
- **Visa and Mastercard hire for Finance too,** and their early-career boards also carry finance programs. In the P&D
  folder (§7.4), only P&D profiles and the boards that poll every source would read them.

### 8.5 The four new packs
Working names from the brief. Each pack would sit in the new P&D folder (§7.4). "Readable" means on an ATS an adapter
reads, not blocked by robots.txt, not an unfetched Eightfold site, and not reachable only through LinkedIn or on a
board that may be retired. (D33)

| Pack | Candidates (Canada) | Readable today | Minimum verified feeds | Risk of coming up thin | If it falls below its minimum |
|---|---|---|---|---|---|
| `design_studios` | 41 (17) | 38 | **8**, at least 3 Canadian | Medium. Many feeds, but small boards, some at zero openings or freelance pipelines; almost no studio postings stored today | Canadian studios go to `canadian_product_design` with their type; US studios and the ID consultancies (IDEO, Teague) go to `industrial_design` or one merged studios-and-consultancies group |
| `canadian_product_design` | 34 (34) | 32 (Assent robots, Shopify blocked) | **10** | Low: 13 Greenhouse, 8 Lever and 5 Ashby boards | n/a |
| `industrial_design` | 34 (10) | 29 (BRP no adapter; Mattel, Steelcase robots; Whirlpool, John Deere unfetched Eightfold) | **6**, at least 2 Canadian | **High for postings, low for feeds.** 77 strict ID postings open in all stored data; the big boards carry a few ID roles among thousands | A consumer-products group (toys, apparel, sporting goods, appliances: Spin Master, Hasbro, Arc'teryx, Canada Goose, lululemon, Bauer, CCM, Umbra, SharkNinja, YETI…) or the studios; the filter keeps `devices_iot`, `robotics_autonomy`, `consumer_tech` and LinkedIn |
| `apm_programs` | 27 (1) | 21 (TikTok, T-Mobile no adapter; Etsy, NBCUniversal robots; LinkedIn only by search; Samsara's board may be retired) | **5** | **High.** 92 distinct APM-only postings open, 50 only through lists; programs post in windows; one Canadian candidate | The early-career boards stay as narrow second sources in the closest group by employer (Visa, Mastercard: a fintech-adjacent P&D group; SOTI: `canadian_product_design`); the filter is then served by lists, big tech and the LinkedIn APM queries |

Recommendation (judgement, the report's): plan four packs but expect to merge. Keep `canadian_product_design` as the
core Canadian pack. Run `apm_programs` as a wider early-career programs pack (APM, RPM, product and design
internship and apprenticeship boards: the boards in 8.4, plus Konrad's and Bridgeable's programs if their boards
verify), so it stays above 5. Fold `industrial_design` and the studios together if either verifies below its
minimum. A dropped pack is named in the report, and its employers keep their own employer type (brief, "Small
groups").

Pack names (judgement): `apm_programs` and `industrial_design` would repeat the proposed filter keys, as
`public_health` and `security` do today (§3). A name like `early_career_programs` avoids it.

The tables list every candidate. **Stored** counts rows in `census.db` whose company string matches the employer, on
any source (mostly lists): all / open, with open Product and Design in brackets, and the company key those rows
resolve to today. Canada comes first, then the US hubs, then global.

A new employer gets a `companies.json` entry keyed by the slug its stored rows already resolve to, so no company or
cluster key moves (brief, "Employers"). Their types are §6.2's decision. What the tables show for the entries:
- Only 7 candidates match an existing entry: Loblaw, Shopify, Visa, Mastercard, Amazon, Superhuman (for Grammarly)
  and Etsy. The other 129 have none.
- Six resolve to more than one key today: TikTok (`tiktok` 1,053 rows, `bytedance` 400, `tiktok_usds_joint_venture`
  16), Publicis (`publicis_groupe` 21, `publicis_sapient` 1), Arlo (`arlo` 3, `arlo_technologies` 1), Milwaukee
  Tool (`milwaukee_tool` 2, `techtronic_industries` 1), Solace (`solace_health` 8, `solace` 2) and Amazon (`amazon`
  9,087, `amazon_newgrad` 2,439, `amazon_com_services` 93). By the brief's rule an entry keeps only aliases whose
  matches already slug to its key, so the other keys stay as they are.
- Names that collide: "Jane" matches Jane Street (325 rows), and "OLIVER" matched the Oliver Wyman entry. Both need
  exact names or `=` aliases.

#### 8.5.1 `design_studios`: 41 candidates, 17 in Canada
| # | Employer | City | ATS: identifier | Stored · key | Note |
|---|---|---|---|---|---|
| 1 | Metalab | Victoria, BC / remote | greenhouse `metalab` | 0 | |
| 2 | Critical Mass | Calgary / Toronto | greenhouse `criticalmass` | 0 | |
| 3 | Thinkingbox | Vancouver / Toronto | lever `thinkingbox` | 0 | some postings on Breezy (no adapter); the Lever board has the design roles seen |
| 4 | Konrad Group | Toronto (also NYC) | greenhouse `konradgroup` | 2 / 2 (0, 0) · `konrad_group` | Associate UX/UI Designer graduate program |
| 5 | Orium (formerly Myplanet) | Toronto | greenhouse `orium` | 0 | |
| 6 | Apply Digital | Vancouver | lever `applydigital` | 0 | |
| 7 | Appnovation | Vancouver / Toronto / Montreal | greenhouse `appnovation` | 0 | |
| 8 | Mirego | Montreal / Quebec City | lever `mirego` | 1 / 0 (0, 0) · `mirego` | French titles: check text encoding |
| 9 | Osedea | Montreal | lever `osedea` | 0 | |
| 10 | Moment Factory | Montreal | lever `momentfactory` | 0 | only an HR posting surfaced |
| 11 | Bridgeable | Toronto | workable `bridgeable` | 0 | service design; ran a "Designership" summer internship (2023) |
| 12 | Steamclock Software | Vancouver | workable `steamclock` | 0 | |
| 13 | VML Canada | Toronto / Montreal | greenhouse `vmlcanadafr` | 2 / 2 (0, 0) · `vml` | French board only; the English board's token wasn't seen (not guessed) |
| 14 | Sid Lee | Montreal / Toronto | greenhouse `sidleeland` | 0 | "no current openings"; may not be its main board |
| 15 | lg2 | Montreal / Quebec City / Toronto | recruitee `lg2` | 0 | **no adapter** (8.7) |
| 16 | Domain7 | Vancouver | bamboohr `domain7` | 0 | "not hiring at this time" |
| 17 | Thoughtworks Canada (formerly Connected) | Toronto | workable `connected` | 8 / 1 (0, 0) · `thoughtworks` | board showed no openings |
| 18 | IDEO | San Francisco / Cambridge MA / Chicago | greenhouse `ideo` | 0 | also industrial design and design research roles |
| 19 | Huge | Brooklyn / remote US | greenhouse `hugeinc` | 0 | |
| 20 | Instrument | Portland / remote | lever `instrument` | 0 | mostly freelance pipelines |
| 21 | Code and Theory | New York / Baltimore | greenhouse `codeandtheory` | 0 | |
| 22 | Fantasy | New York / remote | lever `fantasy` | 0 | many "future freelance" pipelines |
| 23 | Active Theory | Los Angeles | lever `activetheory` | 0 | |
| 24 | Upstatement | Boston / remote | greenhouse `upstatement` | 0 | newer Designer postings on a second board, `upstatementrecruiting` |
| 25 | WillowTree (TELUS Digital) | Charlottesville / Durham / Columbus | greenhouse `willowtree` | 0 | |
| 26 | Viget | Falls Church VA / Boulder CO | lever `viget` | 10 / 10 (4, 0) · `viget` | paid summer internships |
| 27 | Fueled (with 10up) | New York / remote | greenhouse `fueledcareers` | 0 | |
| 28 | Prophet | New York / San Francisco | greenhouse `prophet` | 0 | design intern posting (London) seen |
| 29 | Landor | New York / San Francisco | greenhouse `landor` | 0 | |
| 30 | Wolff Olins | New York / London | workable `wolff-olins` | 0 | summer design internship (NY) |
| 31 | Big Spaceship | Brooklyn | workable `bigspaceship` | 0 | older internships under a second account, `big-spaceship` |
| 32 | AREA 17 | New York / Paris | workable `a17` | 0 | |
| 33 | OLIVER (North America) | US | greenhouse `oliverusa` | 0 | an entry needs exact aliases (`=oliver`): the bare name matched the Oliver Wyman entry |
| 34 | Teague | Seattle | greenhouse `teague` | 0 | ID consultancy (aviation interiors, UX); counts toward `industrial_design`, listed once here |
| 35 | Media.Monks | Toronto (global) | greenhouse `monks` | 0 | older Workable board also seen |
| 36 | DEPT | Toronto (global) | greenhouse `dept` | 0 | |
| 37 | ustwo | New York / London | workable `ustwo` | 0 | |
| 38 | Superside | remote | lever `superside` | 0 | |
| 39 | Designit (Wipro) | global | workday `designit` / `External` (wd3) | 0 | |
| 40 | frog (Capgemini Invent) | Munich and other EU studios | Greenhouse EU `capgeminideutschlandgmbh` | 0 | **no adapter** (EU host); German-speaking roles, low fit |
| 41 | Publicis Sapient / Publicis Groupe | Toronto / US (global) | smartrecruiters `PublicisGroupe` | 22 / 22 (4, 0) · `publicis_groupe`, `publicis_sapient` | **robots.txt** (8.7); a giant holding-company board |

- 39 of 41 are on an ATS an adapter reads. No candidate shares a feed with an existing source.
- Almost none appears in stored data, so these boards add mostly new postings. Most are small (a handful to a few
  dozen openings), and Sid Lee, Domain7 and Thoughtworks Canada showed none at search time (judgement from search
  snapshots).
- Student roles: Konrad (graduate program), Bridgeable ("Designership"), Wolff Olins and Prophet (design
  internships), Viget and Big Spaceship (summer internships), frog (EU interns).
- Not found (no board URL seen): R/GA, Work & Co, Pentagram, Collins, Smart Design, Ammunition, fuseproject, Rangle,
  Normative, Akendi, Nventive, Plank, Siegel+Gale.

#### 8.5.2 `canadian_product_design`: 34 candidates, all in Canada
| # | Employer | City | ATS: identifier | Stored · key | Note |
|---|---|---|---|---|---|
| 1 | Hootsuite | Vancouver / Toronto | greenhouse `hootsuite` | 0 | Associate Product Manager (Toronto) and co-op postings seen |
| 2 | Wave HQ | Toronto / remote Canada | lever `waveapps` | 0 | |
| 3 | PointClickCare | Mississauga | lever `pointclickcare` | 12 / 12 (0, 0) · `pointclickcare` | health IT: check Healthcare's claims on its titles |
| 4 | Unbounce | Vancouver | greenhouse `unbounce` | 0 | |
| 5 | Jane App | North Vancouver / remote | ashby `jane` | 0 | an entry needs an exact name: "Jane" matched Jane Street (325 rows); an older Lever board `janeapp` also seen |
| 6 | Procurify | Vancouver | ashby `procurify` | 0 | |
| 7 | TextNow | Waterloo / San Francisco | greenhouse `textnowinc` | 2 / 2 (0, 0) · `textnow` | |
| 8 | Vidyard | Kitchener / remote | greenhouse `vidyard` | 0 | |
| 9 | AppDirect | Montreal / SF | greenhouse `appdirect` | 0 | |
| 10 | Workleap (formerly GSoft) | Montreal / remote Canada | greenhouse `workleap` | 0 | older SmartRecruiters board also seen |
| 11 | Poka (IFS) | Montreal | greenhouse `poka` | 2 / 0 (0, 0) · `poka_labs` | |
| 12 | Potloc | Montreal | lever `Potloc` | 0 | |
| 13 | Dialogue Health Technologies | Montreal / Toronto | greenhouse `dialoguehealthtechnologiesinc` | 1 / 1 (0, 0) · `dialogue` | telehealth: check Healthcare's claims |
| 14 | Fullscript | Ottawa / Toronto | lever `fullscript` | 6 / 6 (0, 0) · `fullscript` | co-op postings |
| 15 | Achievers | Toronto | lever `achievers` | 1 / 1 (0, 0) · `achievers` | |
| 16 | Super.com | Toronto / remote Canada | lever `super-com` | 0 | 12-month Product Manager Intern seen |
| 17 | Knix | Toronto | lever `knix` | 0 | |
| 18 | Mejuri | Toronto | greenhouse `mejuri` | 0 | |
| 19 | AutoTrader.ca | Toronto | greenhouse `autotradercanada` | 0 | |
| 20 | 7shifts | Saskatoon / remote | greenhouse `7shifts` | 0 | |
| 21 | TobogganLabs | Montreal | greenhouse `tobogganlabs` | 2 / 2 (0, 0) · `tobogganlabs` | |
| 22 | Hiive (now Clarity) | Vancouver | ashby `hiive` | 2 / 2 (0, 0) · `clarity` | stored on `linkedin_canada` as "Clarity (formerly Hiive)": 'Analyst, Sales & Trading' and 'New Analyst Program'; check the key before an entry; finance-type question (§6.2) |
| 23 | sherpa° | Toronto | ashby `joinsherpa` | 0 | |
| 24 | Venn | Toronto | ashby `venn` | 0 | |
| 25 | Maple | Toronto | lever `getmaple` | 0 | telehealth; not the New York `maple` on Ashby |
| 26 | Zafin | Toronto / Vancouver | greenhouse `zafinlabsamericasinc` | 0 | banking software: finance-type question |
| 27 | Interac | Toronto | workday `interac` / `Interac` (wd3) | 8 / 4 (0, 0) · `interac` | payments: finance-type question; 3 PM-student list rows |
| 28 | SOTI | Mississauga | workday `soti` / `Careers` (wd3) | 54 / 53 (16, 0) · `soti` | students on `SOTI-Next-Gen` (8.5.4): two sites, two sources, one key |
| 29 | Loblaw Digital (Loblaw Companies) | Toronto | paradox `careers.loblaw.ca` | 228 / 217 (0, 0) · `loblaw_companies` | **same feed as `loblaw_pharmacy`**: a second source reads "Digital & Ecommerce" only (8.4) |
| 30 | ecobee (Generac) | Toronto | workday `generac` / `External` (wd5) | 127 / 124 (1, 1) · `generac` | Generac's whole board: needs a Toronto location narrowing |
| 31 | Helcim | Calgary | bamboohr `helcim` | 0 | payments: finance-type question |
| 32 | Fulfillment IQ | Toronto | workable `fiq` | 0 | |
| 33 | Assent | Ottawa | smartrecruiters `assent` | 0 | **robots.txt** (8.7) |
| 34 | Shopify | Ottawa / remote Canada | custom | 28 / 16 (3, 0) · `shopify` | **blocked**; read through `linkedin_*_hard_to_reach`; not researched again without a new adapter (brief) |

- Shopify runs an Apprentice Product Manager program (cohort 10 starts March 2027, applications from Nov 2) and a
  6-month Design Apprentice Program (seen on the web).
- Already polled, so not candidates: Wealthsimple, KOHO, Neo, FreshBooks, 1Password, Faire, Clio, Lightspeed, Coveo,
  Hopper, Thinkific, Visier, Trulioo, Benevity, Jobber, D2L, Top Hat, Wattpad, Ada, League, StackAdapt, Kinaxis,
  Geotab, ApplyBoard, Borrowell, Float, Clearco, Ritual, Absorb, Miovision, AlayaCare, Nuvei, Klue, Loopio, Dialpad,
  Cohere, Sanctuary AI, MDA, Behaviour, Kabam, Mistplay, Digital Extremes, Ubisoft, EA, Telus, Bell, Rogers,
  OpenText, BlackBerry, Canadian Tire, Magna.
- Seen but not listed, because they are finance employers: Fidelity Canada (`fil` / `fidelitycanada`, Software
  Product Designer seen) and EQ Bank (Lever `eqbank`).
- Not found: Later, Dapper Labs, Symend, Vena, Uberflip, Properly, Nulogy, Q4, Tulip, Axonify, Flinks, Busbud,
  MindBridge, Ceridian/Dayforce.

#### 8.5.3 `industrial_design`: 34 candidates, 10 in Canada
| # | Employer | City | ATS: identifier | Stored · key | Note |
|---|---|---|---|---|---|
| 1 | Spin Master | Toronto (also LA, NYC) | workday `spinmaster` / `SpinMaster_Careers` (wd3) | 0 | toy design; Sago Mini product roles on the same board |
| 2 | Arc'teryx (Amer Sports) | North Vancouver | lever `arcteryx.com` | 1 / 1 (0, 0) · `arc_teryx_equipment` | the token has a dot, as seen in the URL |
| 3 | Canada Goose | Toronto | workday `canadagoose` / `CanadaGooseCareers` (wd3) | 0 | design postings seen on SmartRecruiters (`CanadaGooseInc1`, robots.txt); which board is live is unchecked |
| 4 | lululemon | Vancouver | taleo `lululemon.taleo.net` section `dc` | 0 | check `dc` is the corporate section, not stores |
| 5 | Bauer Hockey | Blainville QC / Exeter NH | greenhouse `bauerhockeycascademaveriklacrosse` | 0 | designer/prototyper and apparel design internships |
| 6 | CCM Hockey | Montreal | dayforce `ccmhockey` / `CANDIDATEPORTAL` | 0 | |
| 7 | BRP (Ski-Doo, Sea-Doo, Can-Am) | Valcourt / Montreal / Sherbrooke | Taleo Business Edition `lde.tbe.taleo.net`, org `BRP2` | 1 / 1 (0, 0) · `brp` | **no adapter** (8.7) |
| 8 | Umbra | Toronto (Scarborough) | workable `umbra` | 0 | small board (2 openings seen) |
| 9 | Mattel (incl. Mega, Montreal) | Montreal / El Segundo | smartrecruiters `MattelInc` | 0 | **robots.txt** (8.7) |
| 10 | Harding Display | Toronto (Scarborough) | dayforce `hardingdis` / `CANDIDATEPORTAL` | 0 | industrial designer posting seen (expired) |
| 11 | SharkNinja | Needham MA | greenhouse `sharkninjaoperatingllc` | 48 / 47 (0, 14) · `sharkninja` | ID co-ops and interns every term |
| 12 | Stanley Black & Decker | Towson MD / various | workday `sbdinc` / `Stanley_Black_Decker_Career_Site` (wd1) | 174 / 172 (0, 14) · `stanley_black_decker` | large board: needs a design/engineering family narrowing |
| 13 | Polaris | Medina MN | workday `polaris` / `PolarisJobs` (wd5) | 46 / 45 (0, 7) · `polaris` | |
| 14 | Oshkosh Corporation | Oshkosh WI | workday `oshkoshcorporation` / `Oshkosh` (wd5) | 216 / 210 (5, 3) · `oshkosh` | large board: needs narrowing |
| 15 | Brunswick (Mercury Marine) | Fond du Lac WI | workday `brunswick` / `search` (wd1) | 150 / 146 (3, 2) · `brunswick` | large board: needs narrowing |
| 16 | MillerKnoll (Herman Miller, Knoll) | Zeeland MI | workday `millerknoll` / `MillerKnoll` (wd1) | 0 | |
| 17 | Steelcase | Grand Rapids MI | smartrecruiters `SteelcaseInc` | 1 / 1 (0, 0) · `steelcase` | **robots.txt** (8.7); 2027 ID intern and co-op seen |
| 18 | Hasbro | Pawtucket RI / LA | greenhouse `hasbro` | 4 / 4 (0, 0) · `hasbro` | |
| 19 | Bose | Framingham MA | workday `boseallaboutme` / `Bose_Careers` (wd503) | 53 / 50 (1, 0) · `bose` | the same site is also served from wd1 |
| 20 | YETI | Austin TX | workday `yeticoolers` / `YETI` (wd5) | 0 | |
| 21 | iRobot | Bedford MA | workday `irobot` / `iRobot` (wd5) | 0 | |
| 22 | Arlo | US | workday `arlo` / `External_Careers` (wd12) | 4 / 4 (0, 1) · `arlo`, `arlo_technologies` | |
| 23 | Milwaukee Tool (TTI) | Milwaukee WI | workday `tti` / `Milwaukee` (wd1) | 3 / 1 (0, 0) · `milwaukee_tool`, `techtronic_industries` | |
| 24 | Fender | Phoenix / LA | greenhouse `fender` | 0 | |
| 25 | Puffco | Los Angeles | greenhouse `puffco` | 0 | |
| 26 | PAX Labs | San Francisco | greenhouse `paxlabs` | 0 | |
| 27 | Hark | US | greenhouse `hark` | 0 | |
| 28 | Plaud | San Francisco | ashby `Plaud` | 0 | |
| 29 | Lasko Products | West Chester PA | greenhouse `laskoproducts` | 0 | |
| 30 | JetZero | Long Beach CA | greenhouse `jetzero` | 0 | 2027 Product & Design summer internship for ID students |
| 31 | Whirlpool | Benton Harbor MI | eightfold `whirlpool.eightfold.ai` | 0 | Eightfold: not fetched (8.7) |
| 32 | John Deere | Moline IL | eightfold `johndeere.eightfold.ai` | 36 / 28 (1, 0) · `john_deere` | Eightfold: not fetched; its ISG unit's Greenhouse `deeretechstack` showed no openings |
| 33 | 3M | Maplewood MN | workday `3m` / `Search` (wd1) | 2 / 2 (0, 0) · `3m` | giant board: needs a narrow search |
| 34 | Dyson | UK / Singapore | workday `dyson` / `dyson_careers` (wd3) | 0 | ID roles seen are in the UK and Asia: low fit |

- 33 of 34 are on an ATS an adapter reads (BRP isn't).
- **Giant mixed boards** carry a few ID roles among thousands: Stanley Black & Decker (174 stored rows, 14 open
  design), Oshkosh (216, 3), Brunswick (150, 2), Bose (53, 0), 3M, Milwaukee Tool. Each needs a design or
  engineering `jobFamily` facet or a search to be worth polling (judgement). Workday caps a search at 2,000.
- **Consumer-product makers with in-house ID and small boards:** SharkNinja, Polaris, YETI, iRobot, Arlo, Fender,
  Puffco, PAX Labs, Hark, Plaud, Lasko, JetZero, Hasbro, Spin Master, Bauer, CCM, Umbra, Arc'teryx.
- Already polled and carrying ID today, so not candidates: Apple, Garmin, Logitech, Sonos, Anduril, Amazon, Google,
  Waymo, SpaceX, Dell, HP, Whoop, Oura, Ford, GM, Rivian, Stryker, Philips, Zebra, Verkada, Skydio, Intuitive
  Surgical, Peloton, Nike.
- Not found: Kohler, Teknion, Keilhauer, Dorel, Danby, Smart Design, Ammunition, fuseproject, Bresslergroup,
  Priority Designs, Ziba, Design Concepts, Specialized, Traeger, Therabody, Tonal, Harley-Davidson.

#### 8.5.4 `apm_programs` (working name, D33): 27 candidates, 1 in Canada
Rows 1–10 are the early-career boards of 8.4; row 27 is the Amazon read in 8.4.

| # | Employer | City | ATS: identifier | Stored · key | Note |
|---|---|---|---|---|---|
| 1 | SOTI (Next Gen site) | Mississauga | workday `soti` / `SOTI-Next-Gen` (wd3) | 54 / 53 (16, 0) · `soti` | 16 open APM-intern rows reach Foothold only through lists |
| 2 | Visa (early careers) | SF / Austin / Foster City | workday `visa` / `Visa_Early_Careers` (wd5) | 1,151 / 1,006 (47, 5) · `visa` | same tenant as `visa` (site `Visa`); entry `visa` |
| 3 | Mastercard (Campus) | Purchase NY / O'Fallon / global | workday `mastercard` / `Campus` (wd1) | 1,886 / 1,107 (138, 26) · `mastercard` | same tenant as `mastercard`, `mastercard_early`; entry `mastercard` |
| 4 | Workday (early career) | Pleasanton CA / Vancouver | workday `workday` / `Workday_Early_Career` (wd5) | 80 / 80 (8, 1) · `workday` | same tenant as `workday_hq` (site `Workday`) |
| 5 | CoStar Group (Campus) | Richmond / Arlington VA / Sunnyvale | workday `costar` / `Costar_Campus` (wd1) | 61 / 43 (1, 0) · `costar_group` | 10 PM-student list rows |
| 6 | Zynga (early careers) | SF / US | greenhouse `zyngaearlycareers` | 0 | Rotational Product Manager program |
| 7 | ID.me (university recruiting) | Mountain View / McLean | greenhouse `idmeuniversityrecruiting` | 26 / 25 (2, 0) · `id_me` | |
| 8 | C3 AI (Ascend program) | Redwood City | greenhouse `c3ascend` | 22 / 22 (6, 0) · `c3_ai` | |
| 9 | nCino (early talent) | Wilmington NC | greenhouse `ncinoearlytalent` | 2 / 2 (0, 0) · `ncino` | banking software: finance-type question |
| 10 | Samsara (recruiting programs) | SF | greenhouse `recruitingprograms` | 439 / 366 (8, 11) · `samsara` | only a 2023 posting seen; may be retired |
| 11 | TikTok / ByteDance | San Jose / Seattle / NYC | custom `lifeattiktok.com` | 1,469 / 1,301 (49, 3) · `tiktok`, `bytedance`, `tiktok_usds_joint_venture` | **no adapter** (8.7) |
| 12 | T-Mobile | Bellevue WA / Frisco TX | unknown, `careers.t-mobile.com` | 71 / 67 (15, 0) · `t_mobile` | **no adapter known**: job URLs `/<slug>/job/<32 hex>`; one careers-page fetch would identify the ATS |
| 13 | Clearwater Analytics | Boise / NYC / London | workday `clearwateranalytics` / `Clearwater_Analytics_Careers` (wd1) | 39 / 38 (13, 0) · `clearwater_analytics` | finance-type question |
| 14 | Cox Enterprises | Atlanta / Austin / Draper | workday `cox` / `Cox_External_Career_Site_1` (wd1) | 52 / 44 (9, 0) · `cox` | large board: narrow by worker type or job family |
| 15 | Yahoo | NYC / Sunnyvale | workday `ouryahoo` / `careers` (wd5) | 4 / 4 (0, 1) · `yahoo` | no APM program posting found |
| 16 | Grammarly (Superhuman) | SF / Vancouver / NYC | greenhouse `grammarly` | 0 | entry `superhuman`; no APM posting found |
| 17 | Wayfair | Boston | greenhouse `wayfair` | 2 / 2 (0, 0) · `wayfair` | token seen in embed URLs; large board |
| 18 | Etsy | Brooklyn | smartrecruiters `Etsy2` | 28 / 27 (4, 2) · `etsy` | **robots.txt** (8.7); entry `etsy` |
| 19 | NBCUniversal | NYC / LA | smartrecruiters `NBCUniversal3` | 55 / 50 (4, 0) · `nbcuniversal` | **robots.txt** (8.7) |
| 20 | AppLovin | Palo Alto | greenhouse `applovin` | 5 / 4 (0, 1) · `applovin` | |
| 21 | Solace Health | Redwood City | ashby `solace` | 10 / 9 (1, 0) · `solace_health`, `solace` | College Grad 2027 APM seen |
| 22 | CDK Global | Portland / Austin | workday `cdk` / `CDK` (wd1) | 1 / 1 (0, 0) · `cdk_global` | |
| 23 | Dick's Sporting Goods | Pittsburgh | workday `dickssportinggoods` / `DSG` (wd1) | 5 / 4 (2, 0) · `dick_s_sporting_goods` | store roles: needs narrowing |
| 24 | Amplify Education | Brooklyn / remote | ashby `amplify` | 25 / 23 (3, 0) · `amplify` | Summer 2027 Product Design intern seen |
| 25 | Medline | Northfield IL | workday `medline` / `Medline` (wd5) | 3 / 3 (3, 0) · `medline` | medical supplies: check Healthcare's claims; large board |
| 26 | LinkedIn (the company) | Sunnyvale / NYC / Toronto | linkedin | 35 / 33 (0, 0) · `linkedin` | reachable only by a LinkedIn `companies` search (id not looked up). §5's research found LinkedIn ended its APM program in 2025 |
| 27 | Amazon (product and design categories) | Seattle / Vancouver / Toronto | amazon_jobs categories `design`, `project-program-product-management-non-tech` | 11,707 / 11,626 (677, 74) · `amazon`, `amazon_newgrad`, `amazon_com_services` | **same feed** as the four Amazon sources, narrower categories; slugs unconfirmed |

- Not found: an open APM program at Yahoo, Grammarly or Wayfair (their boards are listed); no board seen for Indeed,
  Vertiv or X/Twitter.

### 8.6 The sweep: employers seen only through lists or LinkedIn
The brief wants every major employer to end as a source or under "not added" with its reason
(`employers_research_listgaps.py`, `employers_research_distinct.py`). A direct source here is any non-list,
non-LinkedIn source's company key, plus every `company_key` in config: 1,039 keys.

- **365 employers** have P&D-relevant postings in lists or LinkedIn and no direct source. **310** of them have **845
  distinct open P&D postings** (stored field product or design, deduped on title and location).
- By title class (stored list rows, open in brackets; one posting can sit in several lists): APM and PM-student
  121 employers, 412 rows (345) (TikTok 56, Vertiv 16, SOTI 16, T-Mobile 15, Clearwater 14, Cox 14, BNY 10, CoStar
  10, ABB 7, Publicis 7); design student 64 employers, 228 rows (218); industrial design 6 employers, 17 rows (17)
  (SharkNinja 5, Stanley Black & Decker 4, Polaris 3, Oshkosh 2, Amazon.com Services 2, Meta 1).

The 22 with 6 or more distinct open P&D postings, and where each stands:

| Employer | Distinct open P&D (P, D) | Where it stands |
|---|---|---|
| Meta | 104 (56, 48) | read by `linkedin_us_hard_to_reach`; not researched again (brief) |
| TikTok | 36 (33, 3) | candidate, no adapter (8.7) |
| Tesla | 28 (19, 9) | read by the `*_hard_to_reach` LinkedIn sources |
| Vertiv | 18 (8, 10) | no board seen |
| IBM | 17 (16, 1) | read by the `*_hard_to_reach` LinkedIn sources |
| Parsons | 16 (8, 8) | not yet researched |
| Johnson Controls | 15 (8, 7) | not yet researched |
| Allstate | 11 (10, 1) | not yet researched |
| Astera Labs | 10 (1, 9) | its "design" rows are chip design (judgement) |
| Caterpillar | 10 (7, 3) | not yet researched |
| CACI | 10 (10, 0) | already a source, `caci_international`; its list rows key `caci` (§15) |
| Eversource Energy | 9 (3, 6) | not yet researched; its "design" rows look like engineering (judgement) |
| BNY | 8 (8, 0) | not yet researched |
| Workday Inc | 7 (6, 1) | candidate (`Workday_Early_Career`); its list rows key `workday`, the source `workday_hq` (§15) |
| Cox | 7 (7, 0) | candidate |
| SharkNinja | 7 (0, 7) | candidate |
| Altera | 7 (0, 7) | not yet researched; chip design (judgement) |
| Oshkosh | 6 (4, 2) | candidate |
| Clearwater Analytics | 6 (6, 0) | candidate |
| Schweitzer Engineering Laboratories, Carrier Global | 6 (0, 6); 6 (2, 4) | not yet researched |
| Etsy | 6 (4, 2) | candidate, robots.txt (8.7) |

Nine more have 5: Moog, Copart, HNTB, KeyBanc, Stanley Black & Decker, RELX, Guidehouse, Questrade and T-Mobile
(two of them candidates; `employers_research_distinct.txt`). The sweep isn't finished (judgement): Phase 4
researches the employers marked "not yet researched" and adds each as a source or under "not added".

### 8.7 Not added, by what blocks it
Grouped as the brief asks: each ATS no adapter reads first, then robots.txt, then sites not fetched. Stored rows as
in 8.5. Adding an adapter needs your yes. (D35)

| Block | Employers (pack) | Stored rows (all / open; open P, D) |
|---|---|---|
| **Recruitee** (no adapter) | lg2 (studios); also seen: Framestore (Montreal VFX, `framestore.recruitee.com`), Huawei Canada | lg2 0; the others not counted |
| **Greenhouse EU host** (`fetch_greenhouse` reads the US API only) | frog / Capgemini Invent (studios; German-speaking roles) | 0 |
| **Taleo Business Edition** (`fetch_taleo` is Enterprise only) | BRP (industrial design) | 1 / 1, through LinkedIn |
| **Custom career site** | TikTok / ByteDance (`lifeattiktok.com`; apm) | 1,469 / 1,301 (49, 3): lists 1,424, LinkedIn 45 |
| **ATS not identified** | T-Mobile (`careers.t-mobile.com`; apm) | 71 / 67 (15, 0): lists 70 |
| **Breezy HR** (a Lever board also exists) | Thinkingbox (studios) | 0 |
| **In-house ATS** (`rippling` is disabled) | Rippling's APM program | 0 rows from `rippling` |
| **Blocked career site** (brief: not researched again) | Shopify's APM and Design Apprentice programs | 28 / 16 (3, 0): lists 19, LinkedIn 9 |
| **robots.txt**: the SmartRecruiters API allows only LinkedInBot (§11.3) | Publicis Groupe (studios), Assent (Canadian), Mattel incl. Mega Montreal, Steelcase (ID), Etsy, NBCUniversal (apm); Canada Goose's design postings | Publicis 22 / 22 (4, 0); Etsy 28 / 27 (4, 2); NBCUniversal 55 / 50 (4, 0); Steelcase 1 / 1; Assent, Mattel 0 |
| **Eightfold, not fetched** (rule; the adapter exists) | Whirlpool, John Deere (ID); CoStar's main board (`costar.eightfold.ai`) | John Deere 36 / 28 (1, 0); Whirlpool 0 |

- TikTok is the largest PM-student employer Foothold sees only through lists: 56 APM and PM-student list rows, the
  most of any list-only employer.
- No new SmartRecruiters source can be added: the acceptance criteria need robots.txt to allow the path. Canada
  Goose's Workday board is listed in 8.5.3 instead. For a key blocked employer, the tested fallback is a LinkedIn
  `companies` search (brief, "robots.txt"); the Canadian ones are Mattel/Mega Montreal and Publicis Sapient Toronto.
  That is part of the robots.txt decision in §11.3 (D36).
- Whirlpool and John Deere would join the shared Eightfold spacing (`EIGHTFOLD_SPACING`, 1.5 s between requests to
  any Eightfold site, `watcher.py` 939). Phase 4 fetches them one at a time from one process, as the brief says.

### 8.8 LinkedIn
- **The boards' own searches are §7.5's:** four 6-query drafts from the same report (`employers_research.md` §5),
  their settings, the check against the 13 existing LinkedIn sources (0 exact repeats, 0 word-subset overlaps),
  the lock time and the four-or-two shape. None of the four names is a retired name (§11.1).
- **Employers Foothold reaches only through LinkedIn:** Meta (996 stored on `linkedin_us_hard_to_reach`) and Shopify
  (9 on `linkedin_canada_hard_to_reach`), which block their sites and aren't researched again (8.3). LinkedIn the
  company would need a `companies` search with its organization id, which wasn't looked up (8.5.4).
- **Blocked employers:** the `companies` fallback for Mattel/Mega Montreal and Publicis Sapient Toronto is part of
  §11.3's robots.txt decision (8.7).

### 8.9 What Phase 4 checks for each candidate
The brief's source rules, applied to this list:
- **Fetch the official feed whole** with the app's reader: postings read against the site's total, `complete`,
  `reason`, `total`, distinct ids. Confirm the board is the employer's: the ATS's own name and what the postings say.
- **Unconfirmed identifiers to settle first:** Amazon's two category slugs; Loblaw's "Digital & Ecommerce" category;
  lululemon's Taleo section `dc`; which Canada Goose board is live; VML Canada's English board; Upstatement's second
  board `upstatementrecruiting`; Big Spaceship's second account; Wayfair's token (seen in embed URLs); Samsara's
  `recruitingprograms` (may be retired); T-Mobile's ATS.
- **Giant boards are narrowed** by `jobFamilyGroup` or `jobFamily` facet ids, or a search, and the narrowed total is
  checked with `watcher.py --list`: Stanley Black & Decker, Oshkosh, Brunswick, Bose, 3M, Milwaukee Tool, Cox,
  Dick's, Medline and Wayfair. ecobee needs Generac's board narrowed to Toronto. (Publicis, also a giant board, is
  blocked by robots.txt: 8.7.)
- **Descriptions and locations:** for each ATS new to the board, three postings opened in the drawer (brief,
  "Descriptions and titles"); the location each row gets; a `"location"` override where tiles show no place (§6).
- **Text encoding:** French titles from Montreal and Quebec (Mirego, Osedea, Moment Factory, Potloc, Poka, Workleap,
  Appnovation, VML Canada's French board, CCM).
- **Healthcare's claims** on the health-adjacent employers: PointClickCare, Dialogue, Maple, Medline (§3).
- **A title census on each new source's live postings,** with the postings that land on Finance counted apart: they
  show only to profiles that also poll Product or Design.
- **Required fields:** `group`, `priority`, `geography`, `min_interval`, `company_key`; a `label` for every second
  source and LinkedIn search; the pack header's verification date; no pack over 50 sources (the largest here is
  41). "Not added", with reasons, goes into this plan and each pack's `note`.

---

## 9. Resume plan

A Product or Design resume must come back with this board's filters, skills, employer types and degree, not as
Finance or Software. Everything below ran on `main`'s code (`E:\product-design-board\code-main`, `598b525`) through
`JobwatchService.parse_resume`, as the resume preview runs it (`wrapped=False` only for a `.docx`), on a temp DB with
the clock frozen at 1793070000 (2026-10-27), as `tools/resume_record.py` freezes it. The scripts are
`E:\product-design-board\phase1\scripts\resume_degrees_*.py` and `views_track_resume_probe.py`. The `resume_degrees`
scripts print and don't save their output, so they were run again: the outputs are in
`E:\product-design-board\phase1\plan\scratch\out\`, beside three checks of my own (`combo_head2.txt`,
`portfolio_head2.txt`, `other_level.txt`). Every resume is invented. Posting counts are of open postings
(`status != 'closed'`).

### 9.1 What `main` reads today
Six invented P&D fixtures (9.9), each read in 6 forms (text, PDF, LaTeX PDF, `.docx` with no list, nested and flat).
Every fixture reads the same in all 6 forms (`resume_degrees_fixture_run.json`).

| Fixture | `main`, all 6 forms | Why |
|---|---|---|
| PM | product, no filter | P&D have no filters yet, so every P&D resume targets the whole board |
| UX designer | **refused** | the "Design Experience" heading isn't known, so both jobs are read as education (9.3) |
| UX researcher | **the default Finance targets**, level undergraduate | "Research Experience" isn't known; "M.S. in" sets no level, so the B.A. below it wins (9.2) |
| Visual designer | **refused** | "Advanced Diploma" sets no level (9.2) |
| Industrial designer | design, program `dustrial Design`, only skill **`options`** | the `_PROGRAM` bug (9.2) and a Finance skill (9.5) |
| CS with PM internships | Software and Product both open | as it should |

- 21 of 47 degree lines are refused (9.2). 0 of the 45 that are not CS open any track.
- 5 of 38 P&D skill terms have a skill in `skills.json` (9.5).
- P&D titles open the tech track, whose 19 signals are all Software, AI & Data and Hardware ones. They misread UX
  research as AI research and data science, and UX work as front-end (9.4).
- A "Portfolio" heading or line under Education reads as Asset Management (9.3).

### 9.2 Degrees and levels (`_DEGREES`, `_PROGRAM`: shared)
The preview refuses a resume whose education sets no level ("could not recognize education and experience or
skills"). The level comes only from `_DEGREES` (`intel/resume.py` ~334-343), which every board shares. One minimal
resume per degree line, the rest of it the same in all 47 (`resume_degrees_levels.py`, `resume_degrees_levels.json`):

| Degree lines | Lines | `main` | Should set |
|---|---:|---|---|
| Full names and "in" forms: Bachelor of Design (BDes), Interaction Design · Bachelor of Fine Arts, Graphic Design · Bachelor of Arts, Communication Design · Honours Bachelor of Interaction Design · Bachelor of Industrial Design · BA in Design · BA, Design · BSc in / B.S. in Human-Computer Interaction | 9 | undergraduate | undergraduate |
| Controls: Cognitive Science, Psychology, Marketing (BCom) and Computer Science, two forms each | 8 | undergraduate (only the 2 CS lines open tech) | undergraduate |
| Master of Design (MDes) · Master of Fine Arts, Design · Master of Human-Computer Interaction (with and without "(MHCI)") · MSc in HCI · MA in Interaction Design | 6 | masters | masters |
| MBA, Master of Business Administration (MBA) · PhD, Human-Computer Interaction | 3 | mba · phd | same |
| BDes, Industrial Design · B.Des. in Communication Design · BDes (Hons), Graphic Design · BFA, Graphic Design | 4 | **none: refused** | undergraduate |
| MDes, Interaction Design · MFA, Interaction Design · MHCI · MHCI, Human-Computer Interaction · M.S. in Human-Computer Interaction · MS, Human-Centered Design & Engineering · MA, Communication Design | 7 | **none: refused** | masters |
| BID, Industrial Design · MID, Industrial Design | 2 | **none: refused** | undergraduate · masters, but see the risk below |
| Advanced Diploma, Ontario College Advanced Diploma and Diploma, Graphic Design · Ontario College Graduate Certificate, User Experience Design · Graduate Certificate, UX Design · Certificate in UX Design · UX Design Diploma · Google UX Design Professional Certificate | 8 | **none: refused** | D38 |

- The brief's list holds (BDes, BFA, MDes, MFA, MHCI), and more set no level: US "M.S. in" and "MS,", "MA," with no
  "in", BID, MID, and every diploma and certificate.
- **A wrong level, not only a missing one.** With "M.S. in Human-Computer Interaction" above "B.A. in Psychology",
  `main` reads undergraduate from the B.A.
- **The level reaches the profile as set.** The brief's "~615" filter that keeps only undergraduate, masters, MBA and
  PhD is in `profile_suggestions` (~604), which no app code calls (only `tests/matching/test_health_licences.py`).
  `profile_from_resume`, which the preview and apply use, copies any level, and `validate_profile` doesn't check it.
  A level `other` gives `{'level': 'other', ...}` and 0 problems (`other_level.txt`), which is Settings' existing
  "Other: Diploma, certificate or other".
- **Scoring.** The "Graduate degree required" penalty applies only when the level is undergraduate (a missing level
  counts as undergraduate, `intel/scoring.py` ~314-318). An `other` profile gets no such penalty.

**Programs (`_PROGRAM`, ~344).** The optional `(?:,|in|–|-)?` matches the "In" of "Interaction", "Industrial",
"Information" and "International", since the regex ignores case, and a hyphen ends the capture:

| Degree line | Program on `main` | With PROG |
|---|---|---|
| Honours Bachelor of Interaction Design | `teraction Design` | `Interaction Design` |
| Bachelor of Industrial Design | `dustrial Design` | `Industrial Design` |
| Master of Human-Computer Interaction (with and without "(MHCI)") | `Human` | `Human-Computer Interaction` |
| Bachelor of Design (BDes), Interaction Design · Master of Design (MDes) | `Design` | unchanged |
| Bachelor of Fine Arts, Graphic Design · Master of Fine Arts, Design | `Fine Arts` | unchanged |

Other boards (`resume_degrees_prog_other.py`, 9 of 15 lines wrong): Bachelor of Information Technology
`formation Technology`, Master of Information Systems `formation Systems`, Master of Industrial Engineering
`dustrial Engineering`, Bachelor of International Business `ternational Business`, Master of International Affairs
`ternational Affairs`, Bachelor of Interior Design `terior Design`, Bachelor of Integrated Science `tegrated
Science`, Bachelor of Arts, Socio-Cultural Studies `Socio`, Master of Science in Human-Computer Interaction `Human`.
Tracks don't suffer, because `resume_tracks` also searches `degree_text`, which holds the whole line.

**What each change does** (`resume_degrees_patches.py` patches `main`'s `intel.resume` in memory and reruns the 48
existing recordings, the 47 lines and the P&D fixtures; `resume_degrees_stored.py` reads the stored resume on the DB
copy and prints field names only):

| Patch | What it adds | Existing recordings changed (of 48) | Degree lines changed (of 47) | Stored resume |
|---|---|---:|---|---|
| DEG | BDes/B.Des and BFA → undergraduate; MDes, MFA, MHCI, upper-case "M.S. in"/"MS," and a line-start "MA," → masters | 0 | 11, refused → read | no field changed |
| OTHER | (advanced, Ontario college) diploma and (graduate, professional) certificate → `other`, tried after the four levels | 0 | 8, refused → `other` | no field changed |
| PROG | "in" only as a whole word; hyphens kept inside a word | 0 | 4 programs fixed | no field changed |
| DEG + OTHER + PROG + HEAD2 (9.3) | all four | 0 (`combo_head2.txt`) | 23 | no field changed |

False positives of DEG (`resume_degrees_deg_falsepos.py`):
- Fine: "Boston, MA" on the school line, a school line ending ", MA," and "MS Excel" stay undergraduate.
- Wrong: "MA" at a line start as a state reads **masters**. With no Education heading the whole text is searched, so
  "Implemented MFA for 2,000 users." and "Migrated reports to MS, then..." each read **masters**.
- BID and MID: "bid" and "mid" are common words, and "Bachelor of Industrial Design" already works (judgement).

The patch regexes are illustrations, not the code to commit. Decisions: D37,
(D38), D37.

### 9.3 Headings (`_SECTION`: shared)
`_SECTION` (`intel/resume.py` ~328-331) knows Projects, Awards, "Work Experience" and "Professional Experience". It
doesn't know **Portfolio, Selected Work, Case Studies, Design Experience**, Relevant Experience, Research Experience,
Product Experience, UX Experience, "Selected Projects", "Design Projects", "Honors & Awards", "Awards & Recognition",
Tools, "Skills & Tools", Toolkit, Publications or Exhibitions. An unknown heading is read as a line of the section
above it (`resume_degrees_probes.py`).

Where the lines land on a sample resume with every heading in order:
- "Portfolio" and its link at the top stay in the contact block.
- "Design Experience" right after Education: the job under it (Beacon Labs, Product Design Intern) is read as
  **education**.
- "Relevant Experience", "Research Experience", "Selected Work" and "Case Studies" after an Experience entry are read
  as more experience. "Selected Work" and "Case Studies" become the **employer** of the next project, and the project
  counts as a job: `('experience', 'Selected Work', 'Transit Planner | Figma')`.

The same job under each heading:

| Heading | Right after Education | After an Experience entry |
|---|---|---|
| Experience | experience; tech opens; role and interest `design` | experience |
| Design / Relevant / Research Experience | **education**; no track; no role, no interest | experience |
| Portfolio | **education**; no track; interest **`public_markets.asset_management`** | experience |
| Selected Work / Case Studies | **education**; no track; nothing | experience; the heading becomes the employer |
| Projects | projects; tech opens; `design` | projects |
| Awards | **awards**; no track; nothing | awards; the design job is lost |

- **"Portfolio" reads as Asset Management.** The finance signal `portfolios?\b` (`intel/resume_insights.py:38`)
  reads the education text. A "Portfolio" heading or a "Portfolio: jordanavery.design" line under Education gives the
  interest `public_markets.asset_management` and the types asset_manager, pension_fund and hedge_fund
  (`resume_degrees_evidence.py`).
- In the fixtures, "Design Experience" makes the UX designer **refused in 6 of 6 forms**. "Research Experience" leaves
  the UX researcher on the default Finance targets (investment_banking, private_markets.private_equity,
  public_markets.asset_management, public_markets.equity_research).

**Options** (`resume_degrees_patches.py`, `resume_degrees_patches_head2.py`):
- **HEAD**: Design, Relevant, Research, Product and UX Experience → experience; Portfolio, Selected Work, Case
  Studies, Selected Projects and Design Projects → projects. It changes **6 of 48** recordings, all the CS fixture,
  which uses "Selected Projects" and reads it as experience on `main`: `cs/text`, `/pdf` and `/latex` (role interests,
  target roles, role weights) and the three `cs/docx` forms (role interests and the `software.infrastructure` weight).
- **HEAD2**: HEAD without "Selected Projects" and "Design Projects". It changes **0 of 48** and leaves the stored
  resume as it is. The UX designer goes from refused to `design`. The UX researcher goes from Finance to `design`,
  with `data_ml` from the tech signals (9.4).
- HEAD2 fixes the "Portfolio" heading, not the "Portfolio: <link>" line under Education: that one still reads
  Asset Management (`portfolio_head2.txt`). `_SECTION` needs the heading alone on its line.
- "Volunteer Experience" stays out, as Healthcare left it out: it would change how finance resumes are read.

**The test helper doesn't know these headings either.** `word_docx`'s `_HEADINGS`
(`tests/resume/test_resume_health.py:123`) is a fixed set. In its listed forms every line after "Education" up to the
next known heading is listed as an Education line, so employers become duties ("• Cobalt Cloud"). Under HEAD2 the UX
researcher's `docx-nested` and `docx-flat` forms read `data_ml.ai_research` at 0.91 against 0.6 in the other four
(`resume_degrees_patches_head3.py`). Give `word_docx` a headings parameter rather than growing the set: the CS
fixture's "Professional Experience", "Selected Projects" and "Technical Skills" aren't in the set either, so growing
it changes the CS fixture's Word documents, and `resume_record compare` fails on a changed document.

Decision: D39.

### 9.4 The track gate, role words and signals
`resume_tracks()` (`intel/resume_insights.py` ~173) opens a track when the program or degree line matches the
track's `resume.degree`, or when a job or project title is placed on one of its boards with confidence 0.45 or
more. A resume that opens no track is read with the finance vocabulary.

**Tech's resume block today** (`views_track_inventory.out.txt`): `degree` is `computer science|computing|software|
computer engineering|electrical|data science|artificial intelligence|machine learning|mechatronics|robotics|
information technology`; 19 `signals` (software 10, data_ml 5, hardware 4); no `role_words`. No design or HCI degree
matches it. Product and Design have no filters, so every P&D resume targets the whole board.

Titles (`resume_degrees_roles.py`; a one-job resume with a BA in Psychology, so only the title can open a track):

| Titles | Role line | `classify` | Track | Preview |
|---|---|---|---|---|
| Product Designer, Product Design Intern, UX Designer, UI/UX Designer, UX/UI Design Intern, Interaction, Visual, Graphic, Brand, Motion, Industrial, CMF, Content and Service Designer, Industrial Design Intern / Co-op, UX Researcher, UX Research Intern, Design Researcher, Design Engineer | yes | design 0.6 | tech | role, interest `design`, fields [design] |
| Associate Product Manager, Product Manager (+ Intern), Product Management Intern / Co-op, Technical Product Manager, Growth Product Manager, Product Analyst (+ Intern), **Program Manager, Technical Program Manager** | yes | product 0.6 | tech | role, `product`, [product] |
| UX Writer, Design Technologist, Creative Director, Design Lead | **no**: `_ROLE_WORD` lacks writer, technologist, director and lead | design 0.6 | tech | no role; `design`; [design] |
| User Researcher, Usability Analyst, Research Assistant (HCI Lab), Business Analyst, Product Specialist, Product Owner Intern (role lines); APM, Product Owner, Art Director, Illustrator, Content Strategist, Scrum Master (not) | mixed | **other 0.2** | none | **nothing: no role, no interest, profile unchanged** |
| Product Marketing Manager | yes | sales 0.6 | none (Sales has no track) | nothing |
| Product Operations Associate | yes | operations 0.6 | none | nothing |

- Edge titles (`resume_degrees_overlap_titles.py`): "Clinical UX Designer" and "UX Designer, Clinical Systems" read
  as Healthcare and open its track; "Medical Device Industrial Designer" reads as `healthcare.medical_devices`;
  "Quality Product Manager", "Data Product Manager", "AI Product Manager" and "Product Analyst, Data" read as
  product; "Human Factors Engineer" reads as Software; "Front End Designer" as `software.frontend`; "Mechanical
  Design Engineer" as Hardware; "UX Engineer", "Design Engineer Intern" and "Design Technologist Intern" as design;
  "Product Marketing Intern" and "Growth Marketing Intern" as sales.
- The 12 `other` titles are title words for the classifier (§4.1, §4.2), not resume code.

**What tech's signals do to P&D resumes.** When a P&D title opens tech, its bullets are read with tech's signals:
- The UX researcher fixture with known headings reads `design` 1.0, **`data_ml.ai_research` 0.6** and
  **`data_ml.data_science` 0.38**, and fields [design, data_ml], from "Graduate Research Assistant", "Publications"
  and "the data science team".
- A made-up UX resume (`views_track_resume_probe.out.txt`: Bachelor of Design, UX Designer Intern, Visual Designer
  Co-op) reads `design` 1.0 and **`software.frontend` 0.62** ("user interfaces", HTML, CSS). Applied, it gives
  **fields [design, software]**, targets `design` and `software.frontend`, and types the four P&D types plus
  developer_tools.
- A made-up PM resume (BA Cognitive Science) fires `data_ml.analytics`, `data_ml.data_science` and
  `software.mobile` on its bullets, but they stayed below the board: applied, fields [product], targets [product],
  types the four.

**The P&D track's resume data** (where it lives depends on (D24)). The track and its resume data land in one
commit: `_title_track` opens a track only when its `resume` block has a `degree` or `signals`, so a P&D track without one reads PM and UX
resumes as Finance.
- **`degree`**: interaction design, industrial design, graphic design, communication design, human-computer
  interaction and HCI (the brief's words). With a lookbehind such as `(?<!minor in )`, so "Minor in Design" opens
  nothing (9.6) (judgement). Product gets no degree words: PMs come from every degree, and an MBA word would open the
  board for every MBA finance resume (judgement). Matching on the program only, the report's other guard, would miss
  the abbreviation lines: they read no program, even with PROG.
- **`role_words`**: owner, writer, strategist, director, lead, illustrator, technologist and apm
  (`resume_degrees.md`); `views_track.md` adds artist. A role word makes the line a role line only; the title still
  needs a title word to be placed (§4). Role words also feed `_goes_on`, the wrapped-bullet check, so the fixtures
  test each one ("…the design\nlead." must not become a role) (judgement on the example).
- **`signals`**, one ordered list, appended in order (judgement, not run; the keys follow §3's filters): ux_research
  from usability tests, user interviews, diary studies, card sorting, personas, Qualtrics, Dovetail; product_design
  from wireframes, design systems, interaction design, Figma; visual_brand from brand identity, brand guidelines,
  typography, packaging, Illustrator, Photoshop, InDesign; industrial_design from SolidWorks, Rhino, KeyShot, CMF,
  injection moulding, design for manufacturing; product_analytics from Amplitude, Mixpanel, funnels, retention;
  product_management from PRDs, roadmaps, backlog, user stories.
- On an own track, a P&D title opens only that track, and its entry's bullets are read with that track's signals
  only (`role_interests` ~229-232). The spill into Software and AI & Data stops, unless the resume also has a CS
  degree.
- On tech, all of this is read for every resume that opens tech, CS resumes included. P&D role words tried on the tech
  track (`owner|strategist|illustrator|director|writer|researcher|designer|manager|lead`) leave all 7 existing
  fixture texts reading identically (`parse_resume` called directly: CS, mixed, finance, nursing, biology, pharmacy,
  biomedical), but 7 is a small set.

**Applying** adds the resume's boards and keeps the ones the user chose. A title placed on a board with no filter
targets the whole board, as for Healthcare; which titles carry a filter follows §3. `profile_from_resume` also
replaces `target_company_types`, `target_stages` and `languages`; the apply note's copy is in §10. No new profile key
is needed (9.7).

### 9.5 Skills
`resume_degrees_skills.py` runs `extract_skills` on 38 terms with every track open. **5 have a skill**: SQL → `sql`,
Tableau → `tableau` (Tableau and Power BI, not Looker), Jira → `agile`, Agile/Scrum → `agile`, HTML and CSS →
`html_css`. **33 are missing**: Figma, Sketch, Adobe Creative Cloud, Illustrator/Photoshop/InDesign, After Effects,
Adobe XD, Amplitude, Mixpanel, Google Analytics, Looker, Confluence, user research, usability testing, prototyping,
wireframing, A/B testing, experimentation, design systems, accessibility, roadmaps, PRDs, product strategy,
interaction design, information architecture, journey mapping, typography, motion graphics, Miro, Qualtrics,
SolidWorks, Rhino, KeyShot and CAD.

On the fixtures today: PM `excel, sql, agile`; UX designer (known headings) `html_css` only; visual designer (BDes)
none; UX researcher `r, sql, statistics`; industrial designer only **`options`**, a Finance Markets skill. Its label
"Options" is added to its pattern (`intel/knowledge.py` ~479-480, `config/skills.json:73`), so "Specified CMF options
with suppliers" matches it (`resume_degrees_probe_options.py`). Decision: D40.

**Where a new skill is read** (`views_track_inventory.out.txt`):
- 60 of 175 skills are on the tech track. Tech's `skills_from` is every family plus "other", so a tech skill is read on
  every posting that isn't Finance: Software, AI & Data, Hardware, Healthcare, Sales, Operations, People & Legal and
  "other".
- 57 skills have no track and are read everywhere, Finance postings included. A P&D skill must therefore have a track:
  with none it changes Finance postings' facts.
- Healthcare's 58 are on its own track. A P&D track with `skills_from` [product, design] reads P&D skills on P&D
  postings only (D24).

**Hit rates** on open postings with a description (`desc_len > 0`): every Product (5,607 of 9,011) and Design
(2,580 of 5,546) one, and 5,000 of each tech board at random (seed 7):

| Term | Skill today | Product | Design | Software | AI & Data | Hardware |
|---|---|---:|---:|---:|---:|---:|
| Figma | – | 1.1% | 16.7% | 0.4% | 0.2% | 0.0% |
| Sketch | – | 0.1% | 2.4% | 0.2% | 0.0% | 0.0% |
| Adobe Creative Cloud | – | 0.3% | 7.6% | 0.3% | 0.2% | 0.0% |
| Illustrator / Photoshop / InDesign | – | 0.0% | 5.5% | 0.0% | 0.0% | 0.0% |
| After Effects | – | 0.0% | 2.8% | 0.0% | 0.0% | 0.0% |
| Adobe XD | – | 0.0% | 0.2% | 0.0% | 0.0% | 0.0% |
| Amplitude | – | 0.4% | 0.2% | 0.0% | 0.1% | 0.0% |
| Mixpanel | – | 0.3% | 0.0% | 0.1% | 0.1% | 0.0% |
| Google Analytics | – | 0.1% | 0.1% | 0.1% | 0.1% | 0.0% |
| Looker | – | 0.6% | 0.2% | 0.1% | 1.6% | 0.0% |
| Tableau / Power BI | `tableau` | 4.5% | 0.8% | 1.5% | 9.1% | 0.7% |
| Jira | `agile` | 6.3% | 1.2% | 3.7% | 1.6% | 2.8% |
| Confluence | – | 3.5% | 0.3% | 1.7% | 0.5% | 1.0% |
| SQL | `sql` | 6.2% | 1.6% | 9.9% | 31.8% | 2.0% |
| user research | – | 3.4% | 8.7% | 0.3% | 0.2% | 0.1% |
| usability testing | – | 0.8% | 4.1% | 0.1% | 0.0% | 0.0% |
| **prototyping** | – | 7.5% | **27.7%** | 7.9% | **12.0%** | **17.4%** |
| wireframing | – | 0.6% | 4.5% | 0.0% | 0.0% | 0.0% |
| A/B testing | – | 1.6% | 1.1% | 0.4% | 2.5% | 0.0% |
| experimentation | – | 6.5% | 6.0% | 2.2% | 11.1% | 1.0% |
| design systems | – | 0.4% | 16.5% | 0.6% | 0.3% | 0.4% |
| accessibility (WCAG) | – | 5.7% | 10.6% | 8.5% | 8.3% | 2.5% |
| **roadmaps** | – | **43.6%** | 8.9% | 11.6% | 11.3% | 4.9% |
| PRDs | – | 1.7% | 0.1% | 0.2% | 0.1% | 0.1% |
| product strategy | – | 15.3% | 5.3% | 1.5% | 1.6% | 0.5% |
| interaction design | – | 0.1% | 8.7% | 0.1% | 0.1% | 0.0% |
| information architecture | – | 0.2% | 3.0% | 0.1% | 0.1% | 0.0% |
| journey mapping | – | 0.4% | 2.4% | 0.0% | 0.0% | 0.0% |
| typography | – | 0.1% | 7.0% | 0.0% | 0.0% | 0.0% |
| motion graphics | – | 0.0% | 5.1% | 0.0% | 0.0% | 0.0% |
| Miro | – | 0.3% | 0.4% | 0.1% | 0.0% | 0.0% |
| Qualtrics | – | 0.1% | 0.3% | 0.0% | 0.0% | 0.0% |
| SolidWorks | – | 0.0% | 3.3% | 0.6% | 0.0% | 6.2% |
| Rhino | – | 0.0% | 1.6% | 0.0% | 0.0% | 0.1% |
| KeyShot | – | 0.0% | 0.9% | 0.0% | 0.0% | 0.0% |
| **CAD** | – | 2.1% | **12.8%** | 4.6% | 3.1% | **18.1%** |
| HTML & CSS | `html_css` | 1.0% | 4.5% | 3.9% | 1.4% | 1.5% |
| Agile / Scrum | `agile` | 13.3% | 4.9% | 14.7% | 9.4% | 4.5% |

- **Too broad as written:** "prototyping" (27.7% of Design, and 17.4% of Hardware and 12.0% of AI & Data if it were a
  tech skill) and "roadmaps" (43.6% of Product). Narrow them before adding them and measure again; the report didn't
  try narrower forms.
- 12.8% of Design postings mention CAD. That is the mechanical "Design Engineer" postings on the Design board today
  (judgement), which §4.2's narrowing moves away. Measure CAD again after it.
- A tech-track Figma would read on 0.4% of Software postings: small.
- The brief's six tools: Figma, Sketch and Adobe CC are missing, Amplitude and Mixpanel are missing (and rare in
  postings: at most 0.4%), Jira reads as `agile`.
- Phase 3 reports every new skill's rate on Product and Design, and on Software, AI & Data and Hardware if
  (D24) keeps them on tech.

**Skill groups.** Product's groups are tools, programming and soft; Design's tools and soft. `tools` is the finance
tools (Excel, PowerPoint, VBA, Bloomberg, Capital IQ, FactSet, PitchBook, Refinitiv, Tableau), and onboarding without
Finance keeps the default skills Excel, Python, Bloomberg and Capital IQ for Product and Excel, Bloomberg and Capital
IQ for Design (`views_track_misc.out.txt`). New P&D groups go into both boards' `skill_groups`: design tools,
product analytics tools, research methods and industrial design tools (judgement on the split). Whether the finance
`tools` group stays on them, and onboarding's leftover defaults, are §10's.

**Credentials** in postings (`career_research_creds.py`, over the 6,047 Product and 2,867 Design `job_text` rows of
open postings, some empty): PMP 317 (5.2%) and 17 (0.6%); CSPO, PSPO or SAFe POPM 21 (0.3%) and 0; CSM 42 (0.7%) and
2; Google UX certificate 0 and 0; NN/g 0 and 1. Neither field is licensed (§5), so there is no `licences` block.
Whether PMP becomes a skill is measured with the others in Phase 3 (judgement). A certificate as the only education
line is D38.

### 9.6 Aspiring wording and weak evidence
Each variant added to the existing finance fixture (`tests.resume.test_resume_matching.RESUME`, which reads
`corporate_finance.treasury`, `private_markets.real_estate` and `corporate_finance.fpa` and opens no track;
`resume_degrees_probes.py`):

| Wording | Tracks | What changes |
|---|---|---|
| Summary "Aspiring product manager with a finance background." | none | nothing |
| Headline "Aspiring Product Manager \| Finance student" | none | nothing: the contact block isn't read for roles |
| Summary "Interested in UX design and user research." | none | nothing |
| "…, Minor in Design" on the degree line | none | nothing: `main` has no design degree words |
| **"…, Minor in Computer Science"** | **tech** | opens tech today; interests and fields unchanged |
| Coursework: Human-Computer Interaction | none | nothing |
| **Project "UX Design Course Project \| Figma 2025"** (a single course) | **tech** | **adds `design` 0.33; fields [finance, design]** |
| Certification "Google UX Design Certificate, 2025" | none | nothing |
| Leadership "Product Management Club Member" | none | nothing: leadership titles open no track |
| Bullet "• Shadowed the product manager on two launches…" | none | no product reading. The line becomes an extra untitled entry, so recency moves: real_estate 0.89 → 0.72, fpa 0.57 → 0.38 |

On the CS fixture, a "Product Management Course Project" or an "Aspiring PM" summary changes nothing.

Guards for the P&D track (judgement):
- `resume_tracks` reads `program + degree_text`, and `degree_text` is the whole line. A `degree` regex with "design"
  or "HCI" opens the track for "Minor in Design", as "Minor in Computer Science" opens tech today. The lookbehind of
  9.4 stops it in data.
- A single project titled with design words already adds Design at 0.33 through the title. P&D signals in project
  bullets would raise it. Changing how a project-only entry opens a track is shared reader code
  (D41).
- Every variant goes in the P&D test file, and the finance fixture must stay Finance-only in all of them except the
  course project, which is recorded as `main` reads it.

### 9.7 Portfolio lines (Behance, Dribbble)
- **Links are dropped.** No parsed field holds a Behance, Dribbble or personal-site link, and the preview keeps none.
  On apply the full text goes to kv `resume_text`, so cover letters still see the link.
- A link line between a role's duties and a second title at the same employer becomes **that entry's employer**:
  `('Case study: leahnguyen.design/booking', 'UX Design Intern')`. The existing finance fixture shows the same thing
  with a duty line: its second job reads the employer "Managed liquidity and cash positioning with Excel."
  (`resume_degrees_evidence.py`).
- "Portfolio: leahnguyen.design" as the first line is taken as the name in the raw parse. The preview doesn't return
  the name.
- A "Portfolio" heading or line under Education reads as Asset Management (9.3).
- In postings (same `job_text` rows as 9.5): "portfolio" in 1,175 Product (19.4%) and 808 Design (28.2%) descriptions,
  but in Product it is mostly a product or investment portfolio (judgement); asking to submit, include or link a
  portfolio 12 (0.2%) and 133 (4.6%); Behance or Dribbble 0 and 2; "case study" 24 (0.4%) and 25 (0.9%).
- Nothing in matching or scoring would read a portfolio link. Decision: D41.

### 9.8 Reader limits on design layouts
The same content (the UX designer with known headings) in the layouts design templates use, built with the tests'
`docx()` helper and `word_docx` numbering (`resume_degrees_layout_docx.py`, `resume_degrees_layout_extra.py`; the
files are `scripts\resume_degrees_layout_[A-E].docx`):

| Layout | What `main` extracts | Preview |
|---|---|---|
| E single column (control) | as written | design, 2 roles, `html_css` |
| A 2-column sidebar table (one row: sidebar cell, main cell) | the left column, then the right | same as the control |
| B table, one row per entry, dates and city in the left cell | dates on their own line above the title; one duty loses its bullet | **refused** |
| C header in a text box (Word's drawing plus its VML fallback) | the header **4 times**: twice run together on one line, then twice as lines | same as the control (only contact lines are in the box) |
| D text-box header and sidebar table | as A plus C | same as the control |
| F experience column in a text box | the experience **3 times** | **4 roles: each role twice** |
| PDF1 2-column PDF, written column by column | in order | same as the control |
| PDF2 2-column PDF, written row by row | left and right lines run together | **refused** |

Wrapped PDF bullets (`wrapped=True`): "…lead product\ndesigner.", "…team's\nUX researcher." and
"…product\nmanager." add no role, which is right. **"…lead\nProduct Designer." becomes a role `Product Designer.`**:
`_goes_on` joins only lower-case run-ons. "…lead\nproduct designer" followed by a dated title reads `product
designer` as a role, by design (as "backend developer co-op").

Against the brief's list of limits still on `main`: 2-column tables read right when the table is a sidebar (A) and
fail when each entry is a row (B); text boxes are read 3 to 4 times, not twice; dates on their own line come from B.
The other limits (typed bullets, numbered sub-lists, "eligible" after a licence) weren't probed for P&D.

Recommended: layout D as a fixture that must read as the single-column form, and B, F and PDF2 recorded as known limits,
not pinned as right. Decision: D41.

### 9.9 Fixtures to add
In a new `tests/resume/test_resume_pd.py` (the name is judgement), with `test_resume_health.py`'s `pdf`,
`latex_lines` and `word_docx` helpers, each fixture in all 6 forms. The texts are in
`scripts\resume_degrees_fixtures.py`, in `word_docx`'s conventions ("Title Mon YYYY – Mon YYYY", "Employer City,
ST"). "Today" is `main`; "With the patches" is DEG + OTHER + PROG + HEAD2 (`combo_head2.txt`), which shows what the
shared-code changes do alone; "Must parse to" assumes §3's filters and is judgement until they are decided. Every role
title, program, filter and skill is read by eye before it is pinned.

**1. PM** (`pm`): Honours Business Administration (HBA); Product Manager Intern, Product Analyst Co-op; Leadership "VP
Product"; Jira, Confluence, Figma, Amplitude, Mixpanel, SQL, Excel.
- Today and with the patches: undergraduate, program Business Administration, graduation 2027-04; both roles as
  `product` with no filter; interest `product` 1.0; fields [product]; skills `excel, sql, agile`. "VP Product" is no
  role.
- Must parse to: the same education. Roles product · product_management and product · product_analytics; interests
  led by product_management, then product_analytics; no Finance and no AI & Data; fields [product]; skills add
  Figma, Amplitude, Mixpanel, A/B testing, roadmaps and PRDs (in narrowed forms, 9.5).

**2. UX designer** (`ux_designer`): Bachelor of Design (BDes), Interaction Design; "Design Experience" and "Case
Studies" headings; a Portfolio line with a site, Behance and Dribbble.
- Today: **refused**. With the patches: undergraduate, program `Design`; Product Design Intern and UX/UI Design Co-op
  as `design`; fields [design]; skills `html_css`.
- Must parse to: program "Interaction Design" (no tested patch reads it: `_PROGRAM` takes the word after "of");
  both roles design · product_design; the case study a project; fields [design], not Software; skills Figma, Sketch,
  Adobe CC, prototyping, wireframing, user research, usability testing, design systems, accessibility, `html_css`;
  no link in any employer.

**3. UX researcher** (`ux_researcher`): "M.S. in Human-Computer Interaction" above "B.A. in Psychology, Minor in
Statistics"; "Research Experience" and "Publications"; UX Research Intern and Graduate Research Assistant.
- Today: accepted at **undergraduate**, no roles, no interests, the default Finance targets; skills `r, sql,
  statistics`. With the patches: masters; UX Research Intern as `design`; interests `design` 1.0,
  `data_ml.ai_research` 0.6 (0.91 in the two listed `.docx` forms, the helper's limit in 9.3) and
  `data_ml.data_science` 0.38; fields [design, data_ml].
- Must parse to: masters, program "Human-Computer Interaction"; UX Research Intern as design · ux_research; interests
  led by ux_research, **with no AI & Data**; fields [design]; skills keep `r, sql, statistics` and add user research,
  usability testing, survey design, Qualtrics and Figma.

**4. Visual or brand designer** (`visual`): Advanced Diploma, Graphic Design; Junior Graphic Designer and Brand
Design Intern; "Selected Work" and "Awards"; a Behance line.
- Today: **refused**. With the patches: level `other`, program none; both roles as `design`; fields [design]; no
  skills.
- Must parse to: accepted at the level (D38) sets; program "Graphic Design" (no tested patch reads a
  diploma's program); both roles design · visual_brand; "Selected Work" is no employer; fields [design]; skills Adobe
  CC, Illustrator/Photoshop/InDesign, After Effects, typography, motion graphics, Figma.

**5. Industrial designer** (`industrial`): Bachelor of Industrial Design; Industrial Design Intern and Product Design
Co-op; SolidWorks, Rhino, KeyShot; "Specified CMF options with suppliers".
- Today: undergraduate, program **`dustrial Design`**; both roles as `design`; fields [design]; skill **`options`**
  only. With the patches: program `Industrial Design`; the rest unchanged, `options` included.
- Must parse to: both roles design · industrial_design (the bullets decide the co-op); fields [design], and Hardware
  only if §3's overlap says so; skills SolidWorks, Rhino, KeyShot, CAD and prototyping (narrowed); **no `options`**
  if (D40) narrows it, else recorded as a known bug.

**6. CS with PM internships, two boards** (`cs_pm`): Bachelor of Computer Science (Co-op); Product Manager Intern and
Software Engineer Intern.
- Today and with the patches: interests `software.backend` 1.0, `software.frontend` 0.87, `product` 0.78,
  `software` 0.62; **fields [software, product]**; skills `sql, python, typescript, java, react, nodejs, apis, agile,
  software_testing`.
- Must parse to: both boards open; `product` becomes product · product_management; the Software interests unchanged.

**7. A design layout** (fixture 2's text as a `.docx` in layout D: header in a text box, sidebar table). Built from
the UX designer with known headings, layout D reads today as the single-column control (design, 2 roles,
`html_css`). It must read as fixture 2's single-column `.docx` does. Layouts B, F and PDF2 are added as recorded
readings of known limits, not as expected results.

Variants each set carries: the wrapped bullets of 9.8 ("designer." and the "Product Designer." case) and one per new
role word (9.4); the aspiring and minor variants of 9.6 on the finance fixture; each of the 47 degree lines in a
`subTest`; the PharmD fixture as it is (§2.6). The listed `.docx` forms need `word_docx` to know the P&D headings
(9.3). The P&D fixtures also go into `tools/resume_record.py`'s `FIXTURES`, so later boards prove them unchanged
(judgement).

### 9.10 Shared code: the rule and the proof
Every change to `_DEGREES`, `_PROGRAM`, `_SECTION`, `_ROLE_WORD`, `_goes_on`, the text extraction (`extract_text`,
the Word and PDF readers), `resume_insights` code or how `knowledge.py` builds skill patterns needs your yes first:
"changing a reader every board shares" (brief, Stop and ask). Data on the P&D track (`tracks.<pd>.resume`, skills
with that track) is read only when that track is open, and needs only (D24). Each shared change is proved
like this:

1. **One commit per change**, with its own tests. Each new test fails without its change: run it on `main`, or break
   the guard in a scratch copy.
2. **Existing fixtures byte-identical.** `python -m tools.resume_record record --code <branch checkout> --out
   <new.json>`, then `python -m tools.resume_record compare E:/product-design-board/baseline/resumes_main.json
   <new.json>` must pass. The baseline holds 384 readings: the 8 fixtures in 6 forms with no saved profile, and each
   again under 7 saved first-run profiles (finance, software, product, design, healthcare, finance+product,
   software+design). `compare` exits 1 when a result or the document it was read from differs.
3. **The stored resume.** Parse and apply the DB copy's stored resume with `main` and with the branch, compare field
   by field, and print only field names (`resume_degrees_stored.py` is the model). On `main` it is accepted and sets
   a level; none of DEG, OTHER, PROG, HEAD2 or all four together changes a field.
4. **Through the service.** Tests and the recorder parse through `JobwatchService.parse_resume`, or pass
   `wrapped=False` for a `.docx`. `parse_resume(text, kn)` defaults to `wrapped=True`.
5. **The numbers here are previews.** They come from regexes patched in memory. The committed regex is measured
   again on the 48 recordings, the 47 degree lines and the stored resume, and its numbers go in the Phase 3 report.

Bugs these probes found on `main` (the `_PROGRAM` "In" bug, the CS fixture's `.docx` reading 2 interests where its
text reads 4, text boxes read 3 to 4 times, and the rest) are listed in §15 and left as they are.

---

## 10. Views and copy

The counts come from `views_track` §1-2 and its scripts in `E:\product-design-board\phase1\scripts\`
(`views_track_views.py`, `views_track_misc.py`, `views_track_sources_note.py`, each with a `.out.txt`), and from
`E:\product-design-board\phase1\plan\scratch\s10_noskills.out.txt`. They were taken on the DB copy at its newest
`jobs.last_seen`, 2026-10-31 15:37:51 UTC, so they are what the app showed at that moment. Views count canonical
postings. "Open" means status != 'closed'.

Stored fit was scored for this install's profile (Software and Hardware), not for a Product-only or Design-only
one. So every fit-based number is left out: High fit, Closing soon, Top opportunities, the Analytics high-fit
splits, and the second sort key of the Companies view and the Analytics source table.

### 10.1 Views that count Finance only (D43)

None of these queries reads the profile. A Product-only profile (`fields` `["product"]`, `target_roles` `[]` or
`["product"]`) and a Design-only profile see the same numbers as every other profile. Only one thing depends on the
profile: where the New today card's link goes. With `["product"]` it opens the Product postings. With `[]` it opens
every board, because `interestsFromTargets([])` returns `[]`, which means all.

**What a Product-only and a Design-only profile see today, and on their own boards:**

| View (`dashboard.py` on `main`) | What it counts | Product-only and Design-only today | On the profile's boards: Product | Design |
|---|---|---|---|---|
| Today, New today (`overview` ~943; "finance roles, last 24h", `overview.js:78`) | Finance postings posted in the last 24 h | **112** | **89** | **31** |
| The New today link (`#/opportunities?posted=today`) | the profile's own boards | about 89 Product or 31 Design postings, so card and list disagree | 89 | 31 |
| Analytics, posted in 7 / 30 / 90 days ("finance roles", `analytics.js:33-36`) | Finance | 3,346 / 18,066 / 29,172 | 1,132 / 4,035 / 6,286 | 596 / 2,346 / 3,615 |
| Analytics, open now ("finance inventory") | Finance | 30,372 | 7,603 | 4,542 |
| Analytics, heatmap of discoveries (30 days) | Finance | 18,882 | 2,661 | 1,309 |
| Analytics, open roles by category | Finance categories | 12 bars: corporate_finance 6,830, investment_banking 4,332, risk 4,055, wealth 3,263, … | 1 bar (`product` 7,603) until the filters exist | 1 bar (`design` 4,542) |
| Analytics, open roles by city | Finance | New York 3,330, India metro 1,341, Toronto 1,109, … | San Francisco 935, New York 631, Seattle 504, India metro 319, London 197 | San Francisco 458, New York 299, India metro 257, Seattle 123 |
| Analytics, most active employers (30 days; tip "finance roles posted") | Finance | JPMorgan Chase 2,195, TD 1,207, Bank of America 1,001, … | Google 198, Microsoft 134, JPMorgan Chase 122, Capital One 120, Mastercard 96, Apple 87, Oracle 82, Amazon 63, Cisco 61, ServiceNow (`unknown`) 59 | Micron 76, RTX 61, Google 53, Blue Origin 53, Boeing 52, Qualcomm 49 |
| Analytics, source table (column "Finance", `analytics.js:53`) | every source; sorted by stored high fit, then Finance | 40 rows, holding 4,222 of the 16,682 stored P&D postings; the "Finance" column means nothing to P&D | an "In your boards" count | an "In your boards" count |
| Companies (`companies` ~1060; "Hiring activity across banks, funds and finance employers.", `companies.js:19`) | Finance postings plus **every** posting at a typed employer; 400 of 1,742 employers | 214,399 open roles: 25,217 Finance, 5,615 Product, 3,252 Design. 41 of the 400 have no P&D posting | 826 employers, 7,603 postings | 645 employers, 4,542 postings |
| Market tape (`activity` ~1487, 14 days) | every discovered posting | 53,311: 6,709 Finance, 2,472 P&D | no change needed | no change needed |

What the Companies view leaves out today:
- Product: 1,472 of 7,603 open postings (19%), at 296 employers that are `unknown` or `corporate`.
- Design: 875 of 4,542 (19%), at 219 employers.
- Figma (`unknown`, 153 open postings, 20 of them P&D) and Adobe (`unknown`, 297 open, 34 P&D) aren't listed at
  all. Canva and Miro (`enterprise_saas`) are.
- Its top rows (new in 7 days, stored fit left out) are whole-company counts:
  - UnitedHealth Group: 6,195 open, 48 Product, 13 Design
  - Northrop Grumman: 4,486 open, 79 Product, 74 Design
  - Amazon: 7,460 open, 627 Product, 57 Design
  - Quest Diagnostics: 578 open, 4 Product, 0 Design
- Software and Healthcare profiles get the same list:
  - Software: 15,844 of 68,739 open Software postings (23%) sit at unclassified employers and are left out. 785 of
    the 2,589 employers hiring for Software are typed.
  - Healthcare: 1,000 of 33,426 (3%) are left out. 265 of its 577 employers are typed.

On the profile's boards, Design's busiest employers are semiconductor and defense firms (Micron, RTX, Blue Origin,
Boeing, Qualcomm). That suggests the broad `design` title word sends engineering "design" roles to Design. It is a
title-word question for section 4, not a view question (judgement).

**Options for New today and Analytics.** The model is already in the code: `sources()` (~1640) and `calendar()`
(~1425) build `" OR ".join("i.is_finance=1" if f == "finance" else "i.family=?" for f in profile_fields(...))`.

| Option | What a P&D profile sees | Finance-only | Other boards | Cost |
|---|---|---|---|---|
| **A. The profile's boards**, in `new_today`, `posted`, `inventory` and the heatmap. The source table's `finance` column becomes `yours` ("In your boards", as the Sources view says it), sorted `(-high_fit, -yours)`. "Open roles by category" shows a board by filter (`category, subcategory`) | Product 89 new today; 1,132 / 4,035 / 6,286 posted; 7,603 open. Design 31; 596 / 2,346 / 3,615; 4,542 open. One bar per filter once the filters exist | identical: 112; 3,346 / 18,066 / 29,172; 30,372 | New today becomes Software 506, Software + Hardware (this install) 601, Healthcare 322, AI & Data 110, Hardware 95 | a small SQL edit, plus copy built from the boards ("‹boards› roles", with the Sources view's `boardText`) |
| B. Every board | 2,229 new today, for everyone | changes: 112 → 2,229 | the same 2,229 for all | meaningless as "new for you" |
| C. Copy only ("finance roles", said plainly) | still Finance's 112 and Finance's market | identical | none | P&D users still see Finance's numbers |

**Options for Companies:**

| Option | P&D profile | Finance-only | Notes |
|---|---|---|---|
| A. The profile's boards only | Product 826 employers and 7,603 postings; Design 645 and 4,542; Product + Design 991 and 12,145. Figma and Adobe appear. 253 (Product) and 220 (Design) of the first 400 are in today's 400 | **changes**: the typed employers' other postings drop out, so Amazon goes from 7,460 open to its 698 Finance postings | – |
| **A′. The profile's boards, and a profile that includes Finance keeps today's filter as well** | as in A | identical | `(boards) OR (finance in fields AND typed)`. The copy names the boards, and "Open roles" counts the roles you can apply to |
| B. The boards, or any typed employer | adds the unclassified P&D employers, but keeps whole-company counts (Northrop Grumman 4,486) | identical (a superset) | still mostly noise for P&D |
| C. Copy only: "Hiring activity at the employers Foothold knows, plus finance roles anywhere" | the same numbers, with honest copy | identical | still leaves out 19% of P&D postings, and Figma and Adobe |

Entries for the no-entry employers (6.5) change this list too, under today's filter and under A′ for any profile
that includes Finance: with the 64 tested entries, 42 of those employers enter the first 400 and 40 of today's
rows drop out (6.7).

Why Finance-only stays identical under A and A′:
- `profile_fields` returns `["finance"]` for a profile with no boards and no targets.
- `tests/app/test_dashboard.py` (~133-144, ~281-300) runs on the default finance profile, so its assertions hold.
- None of this is in `RULES_CODE` (scoring, matching, `cycle.window_status`, `sources.role_field` and
  `profile_fields`, `hours`), so no `RULES_VERSION` question comes up.

**Recommendation (judgement, `views_track` §1.3):**
- A for New today and Analytics, and A′ for Companies.
- Copy built from the profile's boards, as the Sources view's `boardText` does it.
- The Market tape stays as it is. It has no board filter and already shows P&D postings.

These fixes are board-agnostic. Software, AI & Data, Hardware and Healthcare profiles get them too, and that is why
they are yours to decide, not a P&D-only edit. Finance-only stays identical.

**Building and testing it** (brief, Target state item 7):
- The SQL is in `dashboard.py`. `tests/app/test_dashboard.py` gains a Product-only and a Design-only profile next
  to its finance one, and checks that the finance numbers don't change.
- The board names in the copy come from one pure function. `boardText` is private to `web/js/views/sources.js`
  today (line 9). Export it from `web/js/fields.js` and test it in `web/tests/fields.test.js`, since web tests run
  with no DOM (judgement).
- No new control or color (`PRODUCT.md`): the cards, charts and tables stay; only their counts and words change.
- Each view is checked in a browser as a Product-only and a Design-only profile in Phase 6 (section 13).

### 10.2 Copy that is wrong for P&D (D44)

Each place was re-read against what P&D will poll and what applying a resume does (brief, Target state item 7).

| Place | What a P&D profile gets today | Change | Who else it touches |
|---|---|---|---|
| **Today's headline** (`overview.js:73`; `DEFAULT_PROFILE.headline` and the `config.json` profile) | "2027 finance recruiting · Toronto & New York". `setupProfile` (`welcome.js`) spreads `...profile` and never sets `headline`, so onboarding keeps it | Set or clear `headline` in `setupProfile` on a first run without Finance, and make the fallback ("Finance recruiting") board-neutral. Don't change `DEFAULT_PROFILE`: `profile_version()` hashes the whole profile, so every install would re-score | every first run without Finance: Software and Healthcare too (read from the code, not checked in a browser) |
| **Resume apply note** (`web/js/resume.js` ~114) | "Applying replaces your skill list with the skills found here, updates education and recruiting cycles, and sets your target roles from your experience, adding any field they belong to." `profile_from_resume` also replaces `target_company_types` (the made-up PM resume sets the four P&D types), `target_stages` and `languages` | Name what else is replaced, for example "Applying replaces your skills, employer types, career stages and languages with what this resume shows, …" (judgement on the words). The made-up UX resume also adds the Software board (6.1): that is the track's question (D24), not the note's | every board |
| **The "Why" line wording** (`intel/scoring.py`) | "‹Type› — outside finance" (~206) at every type off the profile's tracks: on an own track, "Semiconductors — outside finance". "No finance skills detected" (~283) on a posting with a description and no skills: 1,373 open Product postings (24.5% of those with a description) and 483 open Design (18.7%) | Board-neutral words, such as "outside your boards" and "No skills detected" (judgement). The edit changes `RULES_CODE`, but no fit, badge or deadline moves, so the new hash is recorded under the current `RULES_VERSION`, with the reason in the commit (brief, Target state item 5; `views_track` §4). Stored "Why" lines (`fit_detail`) change as each posting is re-scored, and the release's one recompute re-scores them all (judgement). Section 5's "entry level in finance" (~170) is the same kind of edit and can share the commit | every board: a Healthcare profile reads "Big Tech — outside finance" today, and 5,272 open Software postings (11.0%) read "No finance skills detected" |
| Smaller copy (optional) | "Interviews: OA to superday" (`overview.js:82`). Headline placeholder "2027 finance recruiting · Toronto" (`settings.js:298`). "Product · Field outside finance" under Your targets (`settings.js:501`), which goes once P&D has filters. The `FIELD_INFO` notes (`fields.js`: "Product management"; "Product, UX and visual design") | Plain copy. Refine the notes once the filters are fixed (technical, growth and APM; content and industrial design) | mixed |
| Sources view note (`sources.js:91`) | "Dimmed: not polled for your boards · Sales & Growth, Operations, People & Legal poll every source". A P&D-only profile polls 319 sources from 16 packs today; section 7.3's options change that count, not the note | None while P&D isn't an `everything` board. The new P&D folder's packs name their boards themselves (`pack_boards`) | – |

**The specialty sentence** (`welcome.js:145`; Settings `settings.js:336`). It isn't shown yet, because P&D have no
filters. Once they do, onboarding and Settings say "Foothold checks the employers that hire for your picks, and
their other roles still show up, lower down."
- That is true only if the board's manifest entry has `core` and per-filter groups. Today P&D's entry is a flat
  `groups` list of 9.
- Section 7.3's option E gives P&D `core` and per-filter groups, so the sentence holds. Under a flat list (options A
  to D there) it is wrong for P&D, and the sentence would have to depend on the board.
- So it follows the groups decision in section 7.3 and needs no answer of its own.

**Skills** (D42). Section 9.5 has the P&D skills and their hit rates. This is what onboarding and
Settings show (`views_track_misc.out.txt`):
- A first run without Finance keeps the default skills that sit in the chosen boards' `skill_groups`
  (`setupProfile`, `welcome.js` ~69-75). So Product keeps Excel, Python, Bloomberg and Capital IQ, and Design keeps
  Excel, Bloomberg and Capital IQ.
- Settings shows Product Tools & Data (the 9 finance tools: Excel, PowerPoint, VBA, Bloomberg, Capital IQ, FactSet,
  PitchBook, Refinitiv, Tableau), Programming (19) and Client & Communication (4). Design gets Tools & Data and
  Client & Communication. No P&D skill exists yet.
- A skill sits in one group (`config/skills.json`), so Tableau can't join a P&D group without leaving Tools & Data,
  which Finance shows.

| Option | First run, P&D only | Settings for P&D | Other boards |
|---|---|---|---|
| A. The new P&D groups replace `tools` in both boards' `skill_groups`; Product keeps `programming` and `soft`, Design `soft` | Product keeps Python. Excel, Bloomberg and Capital IQ go | the P&D groups, Programming (Product) and Client & Communication. No Excel, PowerPoint or Tableau (Tableau / Power BI is in 4.5% of open Product postings with a description) | none. A profile with Finance keeps `tools` through Finance's groups |
| B. Add the P&D groups and keep `tools` | Excel, Bloomberg and Capital IQ stay, as today | the P&D groups plus the 9 finance tools | none |

**The intro.** `ROLES` (`web/js/intro-opening.js` ~20-26) shows "Product Manager Intern" at fit 85, which classifies
as `product`, and "UX Designer, New Grad" at fit 49, which classifies as `design`. The fits are decorative, and
`web/tests/intro.test.js:72-74` pins the board order and distinct fits. Step 1 of the intro (`views/intro.js`
~40-43) names Finance, Software, AI & Data and Healthcare & Science ("Finance, Software, Healthcare and more").
Neither changes. Re-check both titles once section 4 narrows the title words (`ux`, `design`).

Settings also shows employer types under each track's `employer_heading`. On their own track, P&D get one heading of
their own (6.1).

**Recommendation (judgement, `views_track` §2 and §5 item 3):**
- Fix the headline in `setupProfile` and make the fallback board-neutral.
- Fix the apply note for every board.
- Make the two "Why" lines board-neutral, with the new `RULES_CODE` hash under the current `RULES_VERSION`.
- Let the specialty sentence follow section 7.3: option E keeps it true.
- Skills: option A, with the P&D groups from section 9.5, in Phase 3. `views_track` says the finance defaults must
  go, and A is the data-only way that drops them.
- Leave `ROLES` and the intro choices as they are.

### 10.3 Badges for APM levels (D21)

The stage rules are section 5's, and this is the badge half of its level-labels decision. Section 5's Product level
PL2 is `apm_program`, at stage new_grad, labelled "APM Program". It fires on 8 stored postings (2 open) and changes
the stage of 6 (`data\finance_seniority_rules.txt`). The reach is larger than that:
- 67 of the 130 stored "associate product manag…" Product postings read as senior today (50 open;
  `scripts\views_track_seniority.out.txt`).
- 92 distinct open postings have APM-only titles, and 50 of those come only through lists
  (`employers_research_distinct.txt`).

A board's level shows a badge only when its key is in `BOARD_LEVEL_BADGES` (`intel/scoring.py` 33-35 and ~414-417).
Those keys are extern, summer_student, student_worker, new_grad_program, residency, fellowship and postdoc. The
level's `label` comes from the data, and it is what the stage line shows ("APM Program — target career stage").

| Option | Badge on the posting | Change |
|---|---|---|
| 1. Key `apm_program`, as section 5 proposes | none | data only |
| 2. Key `new_grad_program`, label "APM Program" | NEW GRAD PROGRAM | data only. The key does nothing else in the code: `scoring.py:34` and Healthcare's nurse residencies (`taxonomy.json:232`) are its only uses |
| 3. A new `BOARD_LEVEL_BADGES` entry, such as `apm_program` → "APM PROGRAM" | APM PROGRAM | a `scoring.py` edit that moves a badge, so `RULES_VERSION` goes up and every install re-scores once: Stop and ask |

Section 5 puts the same choice for apprenticeships, residencies and fellowships. Recommendation (`views_track` §4
and §5 item 4): option 2, data only. Option 1 is section 5's key as it stands, and it shows no badge.

---

## 11. Installed config, upgrade test and robots.txt

Counts come from `E:\product-design-board\phase1\config_robots_keys.md` §1, §2 and "Surprises", and its scripts
in `E:\product-design-board\phase1\scripts\` (`config_robots_keys_installed.py`, `config_robots_keys_robots.py`,
`config_robots_keys_oneoffs.py` and its `.out`). The installed and robots scripts have no saved output, so I ran
them again, read-only; their output is in `E:\product-design-board\phase1\plan\scratch\out\s11_installed.txt` and
`s11_robots.txt`, and matches the report line for line. Posting counts are stored postings in table `p` of
`E:\product-design-board\census\census.db`; "open" means status != 'closed'. Nothing was changed: no source, no
setting, nothing in `%LOCALAPPDATA%\Jobwatch`.

### 11.1 The installed `config.json`
Compared: the copy `E:\product-design-board\installed-config\config.json` (in a folder of its own, away from any
DB copy), `clean_config(_tag_config("v0.3.14"))` built with the worktree's `tools/source_history.py` and
`tools/build_windows.py`, `clean_config(load_config(...))` at HEAD (`598b525`, which is v0.3.14), and
`__shipped__` in `config/source_defaults_history.json`. Only key and source names were printed, never a webhook
URL, healthcheck URL or profile value.

| Check | Result |
|---|---|
| Sources: installed / v0.3.14 cleaned / HEAD cleaned / `__shipped__.names` | **1,014 / 1,014 / 1,014 / 1,014** |
| Names only in the install, or only in the tag | none, none |
| Boards hash: installed / v0.3.14 cleaned / HEAD cleaned | `f5dd3640f5c29200` on all three |
| `__shipped__` | version 11, hash `f5dd3640f5c29200`: **the installed hash equals it** |
| `sources_version`: installed / clean config | 11 / 11 |
| Sources whose settings differ from the tag (user edits the upgrade would keep) | **0** |
| Disabled / enabled by you (against the tag) | none / none |
| Source keys outside `BOARD_FIELDS` | none |
| Top-level keys | the same 12 on both sides, every value equal, `profile` and `filters` included |
| The tag's `boards` equal HEAD's | yes |

- **User edits: 0.** The install is exactly `clean_config` of the v0.3.14 bundle. The upgrade has no source
  setting of yours to keep, so every P&D source change reaches this install as a shipped default.
- **Its `profile` is `clean_config`'s placeholder.** Your profile (section 2.1) isn't stored in `config.json`, so
  the upgrade test below uses a synthetic one.
- **Installs carry no `_` headers** (section 2.2), and the polled hash of an install differs from the bundle's
  until both sides are cleaned. Section 2.5 records both hashes for every sample profile.
- **10 sources are disabled**, the same 10 as the tag: `citadel`, `citadel_sec`, `deepmind`, `gts`, `microsoft`,
  `nwfintech_quant27`, `retool`, `rippling`, `simplify_intern27`, `two_sigma`. All 10 are in `shared/`. Four sit in
  the groups P&D polls today (`microsoft` in `big_tech`, `retool` in `developer_tools`, `rippling` in
  `enterprise_saas`, `simplify_intern27` in `lists`), and `deepmind` in `ai_labs` (options B and E). Section 7.9
  gives each one's reason and what covers it.
- **History.** `__since__` has 1,016 names: the 1,014 shipped and 2 retired, `linkedin_canada_tech` and
  `linkedin_us_tech` (`config_robots_keys_oneoffs.out` §3). No new P&D source may take either name: the brief's
  `__since__` trap would count it as deleted by you and never add it (section 7.4).

### 11.2 How the upgrade test runs
The brief's acceptance check: from v0.3.14, 0 sources removed and 0 postings deleted, and `record_release` accepts
`sources_version` 12. It runs in Phase 2 and again after the first pack commit (section 13).

**What exists on `main`** (`tests/install/test_portable.py`):
- `test_upgrading_a_0_3_7_install_keeps_every_source_and_posting_and_adds_tech_ones` and
  `test_upgrading_a_0_3_11_install_keeps_every_source_setting_and_posting`. The second reads its install from a
  committed fixture, `tests/sources/v0_3_11_sources.json`, and checks it equals the bundle's sources of those names.
- Each pins the folders an upgrade may add: line 210 asserts `{"tech", "shared", "health"}` exactly, and line 255
  asserts nothing outside `{"health"}`.

**The new test**, `test_upgrading_a_0_3_14_install_keeps_every_source_setting_and_posting`, built like the 0.3.11
one:
1. The install's sources are `clean_config(_tag_config("v0.3.14"))["boards"]`: 1,014 sources, boards hash
   `f5dd3640f5c29200`, equal to the installed config (11.1). They are saved once as
   `tests/sources/v0_3_14_sources.json`, as 0.3.11's are, so the test doesn't need git tags (judgement).
2. A synthetic install in a temporary folder: that file with `sources_version` 11, one source disabled, one source
   of its own, and a profile with Finance and Product (synthetic, not yours). One posting per source in a small
   synthetic DB, with its facts, and one application.
3. `upgrade_sources(app, data)` on a staged app (`stage_sources`), with the branch's bundle and history.
4. It asserts:
   - every installed source keeps every setting, the disabled one and the install's own one included;
   - the sources added are exactly the bundle's minus the install's, so **0 are removed**;
   - every added source is in the P&D folder (section 7.4 names it);
   - the profile is unchanged;
   - `jobs`, `job_intel`, `job_fts` and `applications` keep every row, so **0 postings are deleted**;
   - every shipped source is in a pack.

**Two things the code decides** (read from it):
- While the bundle stays at `sources_version` 11, `upgrade_sources` returns before it reads anything: an install at
  11 is already current (`portable_start.py` ~37-39). So in Phase 2, with no new source, the new test passes
  without exercising the upgrade. It does the real work from the first pack commit, which raises
  `sources_version` to 12 (`tools/build_windows.py:117`), and it is run again then and at the end (section 13).
- Lines 210 and 255 fail only once the P&D folder holds a source, because both compare the folders of the added
  sources. So their edit (each gains the P&D folder) goes in the first pack commit. Phase 2 lists them (section
  13), and the report names each changed test and why.

**Then the history** (brief, "sources_version"): with the first pack commit, `sources_version` 11 → 12 and
`record_release` records it. After each pack commit, and after the last merge of `main`,
`config/source_defaults_history.json` is restored from `main` and 12 recorded again. The diff may add only the new
sources, their `__since__` entries (12) and the `__shipped__` line. The last step is a `record_release` dry run
that accepts the bundle and saves nothing.

### 11.3 robots.txt for the five sources P&D polls (D36)
Five existing sources in groups P&D polls read a path robots.txt disallows. Nothing about them changes in this work.

**What each reader requests** (`watcher.py`):

| Source | Pack | ATS | Identifier | Listing request | Description request |
|---|---|---|---|---|---|
| `sap` | `shared/big_tech` | smartrecruiters | token `SAPITBusinessSysteme` | `GET https://api.smartrecruiters.com/v1/companies/<token>/postings?limit=100&offset=N` (`fetch_smartrecruiters`, ~309) | `GET …/v1/companies/<token>/postings/<id>` (`detail_smartrecruiters`, ~2750) |
| `servicenow` | `shared/enterprise_saas` | smartrecruiters | token `ServiceNow` | the same API | the same |
| `canva` | `tech/enterprise_saas` | smartrecruiters | token `Canva` | the same API | the same |
| `freshworks` | `tech/sales_marketing_software` | smartrecruiters | token `freshworks` | the same API | the same |
| `intuit` | `shared/big_tech` | radancy | host `jobs.intuit.com`, no `lang`, so `en` | `GET https://jobs.intuit.com/en/search-jobs/results?…&CurrentPage=N&RecordsPerPage=100` (`fetch_radancy`, ~1350) | the posting page, `/en/job/…` (`radancy` is in `PAGE_DETAIL_ATS`, ~2978) |

**The robots.txt files** (fetched once each on 2026-10-31, saved in `E:\product-design-board\phase1\robots\`):
- `api.smartrecruiters.com` (72 bytes): `User-agent: LinkedInBot` / `Allow: /v1/companies/`, then `User-agent: *` /
  `Disallow: /`. The reader sends a browser `User-Agent` (`UA`, `watcher.py` 57), so the `*` group applies, and
  `Disallow: /` covers the listing and the detail path.
- `jobs.intuit.com` (39 bytes): `User-agent: *` / `Disallow:/search-jobs/`. By the letter, `/en/search-jobs/` isn't
  covered. The brief counts it as disallowed where `/en/` is only an alias. The careers home page (fetched once,
  `robots\intuit_home\index.html`) links only to the bare path: 5 × `href="/search-jobs"` and the search form's
  `action="/search-jobs"`, no `/en/search-jobs` link. So `/en/` is an alias here, and **Intuit's listing is
  disallowed**. Its detail pages, `/en/job/…`, are not.
- Stored URLs can't settle an alias: every Radancy source stores `/en/job/…` hrefs because they echo the request's
  prefix. Only American Cancer Society (`lang: ""`) stores bare paths (`config_robots_keys_oneoffs.out` §1).

**Stored postings** (all / open). Every last poll was ok on 2026-10-31, with 0 failures.

| Source | Stored | Product | Design | Finance (stored) | Largest fields (stored) |
|---|---|---|---|---|---|
| `sap` | 510 / 391 | 11 / 9 | 5 / 5 | 16 | other 227, software 98, sales 48 |
| `servicenow` | 1,247 / 731 | 75 / 53 | 37 / 25 | 58 | software 454, other 278, sales 162 |
| `canva` | 107 / 56 | 2 / 0 | 13 / 5 | 2 | sales 34, other 26, design 13 |
| `freshworks` | 137 / 125 | 2 / 2 | 0 / 0 | 5 | sales 44, software 43, other 28 |
| `intuit` | 681 / 605 | 49 / 45 | 29 / 27 | 128 | software 166, finance 128, other 111 |
| **Five** | **2,682 / 1,908** | **139 / 109** | **84 / 62** | | |

- P&D at the five: 223 stored, 171 open. That is 1.2% of the 14,557 open P&D postings (9,011 Product + 5,546
  Design; `config_robots_keys_oneoffs.out` §8).
- Samples (seed 20261031): `servicenow:744000147155135 'Director, UX Research'` (design),
  `intuit:101748803232 'Staff Product Manager, Done-For-You Payroll Workflows'` (product),
  `canva:6000000001497054 'Senior Performance Creative'` (design), `sap:744000157920459 'CFA Agentic AI Product
  Manager - People Solutions, People & Organization Growth'` (product), `freshworks:744000150936730 'Staff Product
  Manager'` (product).
- **The same rules cover other boards' sources.** All 12 SmartRecruiters sources hold 4,426 stored / 3,498 open. The
  18 Radancy sources hold 21,959 / 20,953. Of those 18, American Cancer Society has no such rule and Evotec really
  lives under `/en/`. The other 16 are the alias case per Healthcare's plan, about 21,794 / 20,788 (the 18 minus
  those two). Only Intuit and Hackensack were checked by their own links, plus Cedars-Sinai and Northwestern,
  which aren't sources. Healthcare's plan left the same rule open for all 12 SmartRecruiters sources and 17 of the
  18 Radancy sources (`plans/healthcare-board.md` §15, "Left out: three, by robots.txt").

**Options** (the report's):
1. Keep the five as they are.
2. Disable them and cover their employers through a P&D or Healthcare LinkedIn search with `companies`. That is a
   shipped-default change at `sources_version` 12, and no source is removed. Descriptions would come from
   LinkedIn.
3. For Radancy, a sitemap reader like `hopkins_medicine`. That is a new adapter. Intuit's sitemap wasn't checked;
   its robots.txt names none and doesn't disallow `/sitemap`.
4. For SmartRecruiters, the public pages at `jobs.smartrecruiters.com`. That host's robots.txt wasn't fetched.

**Recommendation (report):** leave all five unchanged in this board, as the brief says. Put it to you as one
cross-board decision with Healthcare's 12 + 17, because it is one rule and P&D's share is small. Add no new
SmartRecruiters or alias-Radancy source to the P&D packs: the acceptance criteria need robots.txt to allow the path.
The P&D candidates this rule blocks (Publicis, Assent, Mattel, Steelcase, Etsy, NBCUniversal, and Canada Goose's
SmartRecruiters board) are in section 8.7. For a key one, the tested fallback is a LinkedIn `companies` search.

### 11.4 Also found
- **Autodesk lists 3 open of 490 stored.** `autodesk` (`shared/big_tech`, Workday `autodesk` / site `Ext`) holds 48
  P&D postings (1 open) and 30 Finance. Its last read, 2026-10-31 15:17 UTC, was marked `complete: true` with
  `fetched` 3 and `reported_total` 3. `job_state` shows 177 postings closed on 2026-10-31 and 121 on 2026-10-22
  (`config_robots_keys_oneoffs.out` §6; the full day list is in `scratch\out\s11_checks.txt`). Either the site now
  lists 3, or a short read marked complete closed live postings (brief, "Complete reads"). The site wasn't
  fetched. 583 stored postings on 12 sources name Autodesk, 490 of them at `autodesk`
  (`config_robots_keys_employers.out`). Nothing here changes it; section 15 lists it.
- **Retool is disabled for a reason that no longer holds.** `retool` (`shared/developer_tools`, `ats: ashby`) says
  "watcher has no Gem adapter". `watcher.py` now has `gem` (`ADAPTERS`, line 2711), which `freshbooks`
  (`tech/enterprise_saas`) uses with `account`. Whether Retool reads through it is unverified. Enabling it edits an
  existing source in a group Finance polls, so it needs your yes (sections 7.9 and 15).

---

## 12. Where your word overrides the brief

| Brief | Now | Why |
|---|---|---|
| "Moves into your board are the point" (the guarantee): moves into Product and Design pass, and only other moves, lost postings and changes through "other" block | Every move into Product or Design from another board is listed for your yes, as an `--allow` you approve with its count (section 14). A move from Finance or "other" is marked "changes what Finance shows". Until you approve a move, the placement check fails on it. | Your rule: "no role of another board may land in a different board, filter, company or location, and none may go missing." A Software or Operations role that moves to Product is a role of another board landing in a different one. |
| Compare family, category, subcategory, `is_finance`, company key, employer type and location | The same fields, plus the company name, every country and city in a posting's list, and career stage (stage off the P&D boards is listed but doesn't block). An employer type that changes from one known type to another blocks. | Your rule names board, filter, company and location; the brief adds employer type. The check keeps both, so it is the stricter of the two. |
| robots.txt: "That decision is still open with the user. Report it; don't change them." | Reported in section 11 and numbered as a decision (section 14), with no change to the five sources in this work | You listed robots.txt among the decisions to number. |

---

## 13. Phases and proofs

Each phase ends with its proof, and I stop where the brief says to. Every approval of section 14 goes into this
file in its own commit, with its date and the moves or counts it allows. The placement check's `--allow` list comes
from that record.

1. **This design.** Committed; I stop for your approval.
2. **Machinery and packs, no new sources.**
   - The `product_design/` folder and its audience (D29).
   - Product's and Design's manifest entries (D28). Option E's `filters` need Phase 3's subcategories,
     because the manifest test checks a board's filters against the taxonomy. So Phase 2 gives each board a flat
     `groups` list equal to its "All of" selection, which is what a profile with no filter polls under E. Phase 3
     splits it into `core` and `filters`, and a profile with no filter picked polls the same sources before and
     after the split.
   - The tests that name folders and boards (brief, Phase 2): `test_source_packs.py` (~99, ~184, ~204),
     `test_portable.py` (~210, ~255) and `test_board_polling.py` (~36, ~79). Each change is listed with its reason
     in the Phase 2 report.
   - Proofs:
     - `polled` on the branch, then `polled-compare` against `baseline\polled_main_bundle.json` and
       `polled_main_installed.json`, each with `--expect` for product, design, product+design, finance+product,
       software+product and software+design. Every other profile keeps its list and both hashes.
     - the polled count for each sample profile (section 7.3's table, re-taken)
     - the upgrade test: 0 sources removed and 0 postings deleted, from `clean_config(_tag_config("v0.3.14"))`
       on a small synthetic DB (section 11)
     - the placement check on the baseline ids: no change
   - I stop and show the output.
   - **Done on 2026-11-07** (`E:\product-design-board\phase2\`):
     - `polled-compare`, bundled and installed config: passed. Product 319 → 679, Design 319 → 559,
       Product + Design 319 → 679, Finance + Product 536 → 759, Software + Product and Software + Design 713 → 742,
       as section 7.3 counted for option E. Every other profile polls the same list with both hashes unchanged, and
       no profile loses a source.
     - Upgrade: the new `test_upgrading_a_0_3_14_install_keeps_every_source_setting_and_posting` passes, but at
       `sources_version` 11 `upgrade_sources` returns early (11.2). Run once from an install at 10, on the same
       synthetic install, the upgrade went to 11 and removed 0 sources, changed 0 settings, added 0 and kept every
       row (1,015 postings, 1 application).
     - Placement on the 73,863 baseline ids, `main` against the branch: no change. 73,863 → 73,863, missing 0,
       added 0, moved 0, changed 0, label changes 0, stage changes 0 (432 s).
     - Tests changed: `test_board_polling.py` (Product and Design leave the 0.3.11 pin; a new test checks their
       groups and that they keep every 0.3.11 source with its settings; `product_design/` joins `health/` in the
       everything boards' exemption), `test_source_packs.py` (`product_design/` packs need a verified date),
       `test_dashboard.py` (the Sources view lists Product and Design on `tech/gaming` and `shared/ai_labs`) and
       `test_portable.py` (the 0.3.14 upgrade test, with `tests/sources/v0_3_14_sources.json`). Lines 210 and 255
       of `test_portable.py` change with the first pack commit (11.2).
     - Suites: Python 806 tests OK, JS 116/116, `watcher --check` OK (1,014 sources).
     - `main` moved to `1758343` after the branch point: software QA titles, compliance titles to Operational Risk,
       senior and experienced resumes, workforce scoring, and Oracle, Phenom and iCIMS teasers. It changes
       `config/taxonomy.json`, `config/skills.json`, `intel/resume.py`, `intel/resume_insights.py`,
       `intel/scoring.py` and `watcher.py`, and no file under `config/sources/`, so Phase 2 doesn't depend on it.
3. **Filters, employer types, skills, stage rules and claims,** as approved in section 14, with classifier tests.
   Each test is a realistic title or a near-miss from another board. No existing test's expected value changes
   except the counts the design changes. Each changed test is named in the report, with why it changed and what it
   still checks.
   - **Re-sample first.** The sample must hold every posting whose title matches the old or the new title words, so
     it is taken again with both checkouts' words, and `main` is placed again on the new ids. Then the branch is
     placed, and the two are compared with `--board product --board design` and one `--allow` per approved move.
   - The stage-rule counts of section 5 are taken again on the branch's placement (`finance_seniority_rules.py`).
   - Each new employer type and entry is simulated with the branch's code on both sides, before and after it. Its
     moves are checked against the approved list before they are reported (brief, Target state item 2).
   - Every new skill's hit rate on Product and Design postings, and on the other boards of its track.
   - The fingerprint changes here, so the release re-reads every stored posting once (D46).
   - **Done on 2026-11-08** (`E:\product-design-board\phase3\`), after merging `main` at `937bbc2`. The commits:
     Product's words, filters and claims (`236f44f`); Design's, with Hardware's design engineers (`649deb4`); the
     levels (`67f57e1`); D27's 8 employers and the source filters (`7349d89`); the track, types and skills
     (`f16ef39`); the resume skill change (`6449cad`); and the records in this file.
     - Sample: 73,917 ids, taken with both checkouts' words, and `main` placed again on them.
     - Placement, `main` against the branch (`main_vs_d24.txt`): 73,917 → 73,917, missing 0, added 0, **0 moves
       outside 14.7**. 9,050 allowed moves, 2,494 of them change what Finance shows (to or from Finance or
       "other"). Inside Product and Design, 10,762 filter or rule changes. Off them, 418 label changes (D27's 8
       employers only, name and type) and 6 stage changes (14.7's JPMorgan postings). The track, types, skills
       and resume change add nothing to the placement: the comparison is identical to the one before them.
     - Open postings per move (`open_pairs.py`): `design:hardware` 2,212, `product:operations` 1,533,
       `software:product` 1,105, `design:other` 719, `other:product` 693, `other:operations` 435,
       `finance:product` 244, `design:software` 192, `hardware:product` 176, `operations:product` 141,
       `data_ml:product` 112, `product:sales` 76, `design:sales` 61, `finance:operations` 40, `other:design` 38,
       `design:operations` 36, `software:design` 36, `design:healthcare` 24, `finance:design` 19,
       `sales:product` 18, `design:product` 16, `product:design` 15, `software:operations` 15,
       `software:hardware` 14, `design:people_legal` 12, `people_legal:product` 7, `product:healthcare` 7, and
       1 each for `sales:design`, `healthcare:design` and `product:software`. `data_ml:design`'s one is closed.
       Each is within 14.7.
     - Stage rules: section 5's counts taken again on the branch's code (`sliceC\measure.txt`), in `67f57e1`.
     - D27: 1,674 stored postings typed and 1,404 renamed, nothing else (`sliceD\entries_compare_final.txt`).
     - D24's points, for a P&D profile with no target types: on the stored placement, 2,549 Product and 3,066
       Design postings go from 7 to 4, as 6.1 counted; on the branch's placement 2,415 and 763, since D8 sends the
       chip and mechanical design engineers to Hardware. For finance+product, 3,354 Finance postings too (14.7).
     - D42's skills on open postings with a description (`sliceD\skill_rates_v3.txt`): Figma and design systems
       32.4% of Design, interaction design 18.2%, user research 18.0%, prototyping 17.4%; product strategy 22.8% of
       Product and roadmaps 20.9%. They read on no other board's postings. A P&D skill falls past the 24-skill
       limit on 1 posting.
     - Resumes: `resume_record compare` against the record before slice D: 384 of 384 unchanged. The new fixtures
       (`test_resume_product_design.py`) read a UX, PM, CS+PM, HCI and role-word resume on the track.
     - Polled: all 20 sample profiles poll what Phase 2 recorded, bundled and installed config.
     - Existing tests changed: `test_tech_taxonomy.py` and `test_resume_tech.py` (D3's claim takes "Product
       Manager, Embedded Payments" from Software; an illustrator intern is a Design role now, D14; a Hardware
       resume's types are tech's, Big Tech also on the P&D track), `test_boards.py` and `fields.test.js` (tech's
       boards are Software, AI & Data and Hardware; the P&D track and its sections and skill groups),
       `test_board_polling.py` (core and filters), and `test_resume_record.py` (main now reads the PharmD
       fixture, `0c0485c`).
     - Left for later: the facts recompute's time (D46, Phase 6), and `web/js/preview/meta.json`'s cities, kept
       as they were (no city marked target).
4. **Sources, one filter at a time:** research, verify, add, commit, with the placement check before each commit.
   - Up to 4 research agents at once, one per filter. They don't fetch Eightfold sites: I fetch those one at a time.
   - With the first pack commit, `sources_version` goes to 12. After each pack commit,
     `config/source_defaults_history.json` is restored from `main` and 12 is recorded again with `record_release`.
   - A title census on each new source's live postings. Postings that land on Finance are counted apart.
   - After the per-filter research, the sweep of the top employers (section 8).
   - The per-profile poll time, before and after, with LinkedIn's time on its own line.
   - **`canadian_product_design`, 2026-11-08** (`E:\product-design-board\phase4\`): 24 sources, core for both
     boards. Each feed was read once with the app's reader, complete (read equals total where the ATS gives one),
     and saved to `phase4etch\`. robots.txt allows every request path: Kula, Gem and Jobvite were checked by
     hand, and Gem's robots.txt answers 403, read as no rules, as Ashby's 401 is.
     - Live postings (`cand\canadian_final.census.json`, with the new types): 505. 24 land on Product and 14 on
       Design: Product Management 19, Technical PM 4, APM & Programs 1; Product Design 9, Visual & Brand 2, Design
       Engineering 2, Content Design 1. 28 land on Finance, about 6 of them misreads: Relay Financial's three
       "Account Executive (Accounting & Bookkeeping)" and its "Manager, Channel Sales (Accounting & Bookkeeping)",
       AppDirect's "Gestionnaire principal(e), stratégie Web et expérience IA" (Quant) and Zafin's "Market
       Research Analyst" (Equity Research). No markup and no test titles; every posting has a place, and the French
       titles read cleanly.
     - Employers: 24 entries with `=` aliases, keyed by the slug their stored postings resolve to. Types:
       enterprise_saas 18, consumer_tech 5, high_growth_startup 1 (TobogganLabs), all on the P&D track. Interac,
       Zafin, Relay Financial and Venn take enterprise_saas, D26's tech type, not canadian_tech, because that type
       is on the tech track only. Every alias is exact (`=`), so an entry's name, being one of them, matches only
       a company string that is exactly it. Where the short name is another employer's too, the entry is longer:
       "Relay Financial" (12 stored postings say exactly "Relay", a Raleigh firm), "Paper Education" and "Jane
       App".
     - Entries check (`entries\canadian_*.json`): the 75 stored postings the entries match, all from lists (SOTI
       54, Interac 8, Bree 7, Poka 2, TextNow 2, TobogganLabs 2): 0 moves, 75 label changes (Software 42, Product
       19, AI & Data 8, Operations 3, "other" 2, Finance 1), 3 renamed ("Interac Corp." on one Finance posting,
       "Poka Labs" on two Software postings).
     - Placement, `main` against the pack (`place\main_vs_p4a.txt`): as Phase 3's, missing 0, 0 moves outside
       14.7, 9,050 allowed; label changes 418 → 423. Against Phase 3's placement: 0 moves, 24 label changes.
     - Source history: sources_version 12, hash `14de9babb3856036`, 1,038 sources; the diff adds only the 24 names.
     - Tests: 962 and 116 pass. The folder test (`test_board_polling.py`) holds every non-LinkedIn employer in
       `product_design/` to the P&D track.
     - The 11 Lever boards joined after the pause (below): Wave HQ, PointClickCare, Potloc, Fullscript, Achievers,
       Maple, Caseware, ShyftLabs, Magnet Forensics, Smile.io, Plooto. The pack holds 35 sources.
     - Not added, by what blocks it:
       - No adapter: Dialogue (Rippling), Vena (Pinpoint), Ratehub and Mogo (JazzHR).
       - robots.txt: Assent (SmartRecruiters). Blocked: Shopify (its careers site can't be read).
       - Another board's employer, your call: Questrade, a finance employer (Dayforce `qfg`: 79 read, 20 Finance,
         8 P&D), whose home would be `shared/`. Loblaw Digital: a second source on `loblaw_pharmacy`'s Paradox
         feed, narrowed to `cf_req_bu` "Loblaw Digital" (16 read, 3 P&D), is verified, but Loblaw Companies is
         `pharmacy_consumer` on the Healthcare track, so it can only go in `shared/`.
       - Few P&D roles: Mejuri (189 read, 1 P&D, 185 store roles), Knix (40 read, 2), Clarity, formerly Hiive
         (trading and analyst roles only).
       - Misreads: Fulfillment IQ (15 of its 29 roles are warehouse "solution design" leads that land on Design,
         and Workable lists a role once per location: 54 rows, 29 ids).
       - No working board: Super.com, 7shifts, Helcim. Name clash: Solace (Ottawa) with Solace Health. Already
         polled: Mila, BenchSci.
   - **`design_studios`, 2026-11-08**: 25 sources, core for Design only (7.4), 11 of them Canadian (D33 asks
     for 8 and 3). Each feed was read once, complete; each Greenhouse and Workable board's name is the studio's.
     Bridgeable, Steamclock Software, Wolff Olins and ustwo had no openings. VML is read through its Canadian
     English board and OLIVER through its North American one, each with a label.
     - Live postings (`cand\studios_final.census.json`): 916; 142 land on Design (Visual & Brand 49, Product
       Design 41, Design Engineering 4, Content Design 2, Industrial Design 1, no filter 45) and 23 on Product.
       12 land on Finance, about 3 of them misreads: Rethink's "Directeur.trice de la stratégie (médias sociaux)"
       and Landor's "Stage planning stratégique" (Quant), and a Media.Monks "HR Generalist | Vaga Temporária …"
       (Wealth). No markup and no test titles, every posting has a place; French, German, Portuguese and Japanese
       titles read cleanly. Rethink's French "Directeur.trice artistique" stays on "other": Design's art director
       words are English.
     - `art_direction` (Design's claim, 3.x) names every employer type but `gaming`, except the two D25 added. With
       a `design_studio` type, 4 live art directors left Design (VML, Big Spaceship, Media.Monks, DEPT). The claim
       now names `design_studio` and `consumer_products`; no stored posting had either type before this phase.
       Adding them to `design_occupation` changes no studio posting, so it is left as it is.
     - Employers: 25 entries, type `design_studio`, every alias exact, so a name matches only exactly (the
       review read `_load_companies`). "DEPT Agency", "OLIVER Agency" and "Rethink Canada" are the studios' longer
       names: "Dept", "Oliver" and "Rethink" alone are other employers' too.
     - Entries check (`entries\studios_*.json`): 11 stored list postings (TribalScale 7, Konrad Group 2, VML 2):
       0 moves, 11 label changes, 0 renamed.
     - Placement, `main` against the pack (`place\main_vs_p4d.txt`): as before, missing 0, 0 moves outside 14.7,
       9,050 allowed. Against the Canadian pack's placement: 0 moves, 1 label change (TribalScale's "AI Product
       Designer", on Design).
     - Tests: 962 and 116 pass. `test_board_polling.py`: Design names 20 groups, Product 25, and
       `design_studios` is the one Design has that Product lacks.
     - The 9 Lever boards joined after the pause (below): Thinkingbox, Apply Digital, Mirego, Osedea, Instrument,
       Fantasy (no openings), Active Theory, Viget, Superside. The pack holds 34 sources, 15 of them Canadian.
   - **The Lever pause and its 20 boards, 2026-11-08** (your yes): api.lever.co and api.eu.lever.co ask for
     `Crawl-delay: 1`. Every Lever request, listings and the postings opened for list links, now takes its turn
     through one lock, a second after the one before (`628e3e7`, as Eightfold's requests do). What each Lever source
     reads is unchanged; when many Lever boards are due at once, up to all 10 poll workers can wait their turn, and
     the poll-time measurement counts it.
     - Live postings (`cand\lever_final.census.json`): 351. The 11 Canadian boards: 26 on Product, 5 on Design, 6
       on Healthcare (PointClickCare), 30 on Finance. The 9 studios: 32 on Design (Visual & Brand 25), 2 on Product,
       1 on Finance. Of the 31 Finance landings about 10 are misreads: Caseware's sales and solutions roles
       ("Strategic Account Manager", "Head of Canadian Solutions", "Product Domain Specialist" and 4 more) read as
       Accounting, ShyftLabs' "Technical Lead" as Underwriting, and Plooto's "IT Administrator" and "Staff
       Customer Experience Strategist" as Payments. No markup, no test titles, every posting has a place.
     - Employers: 20 entries, `=` aliases. "Maple (telehealth)" has no bare "Maple" alias: two stored postings
       name Maple Leaf Sports & Entertainment, and New York's Maple is another employer.
     - Entries check (`entries\lever_*.json`): 63 stored list postings (Magnet Forensics 19, ShyftLabs 14,
       PointClickCare 12, Viget 10, Fullscript 6, Achievers 1, Mirego 1): 0 moves, 63 label changes (Software 31,
       AI & Data 13, Finance 6, Product 4, "other" 4, Sales 3, Design 1, Operations 1), 0 renamed.
     - Placement, `main` against the packs (`place\main_vs_p4e.txt`): missing 0, 0 moves outside 14.7, 9,050
       allowed; label changes 423 → 425. Against the studios commit's placement: 0 moves, 7 label changes.
     - Source history: 1,083 sources; against the last commit it adds only the 20 names.
   - **`industrial_design`, 2026-11-08**: 33 sources, the Design filter Industrial Design's own group (7.4), 8 of
     them Canadian (D33 asks for 6 and 2). Type `consumer_products`, and `design_studio` for Teague. Each feed was
     read once, complete. Stanley Black & Decker and Brunswick are read through a "designer" search, Milwaukee Tool
     (TTI's Milwaukee site) and 3M through an "industrial design" search, MillerKnoll through 9 design and product
     job families; each narrowed read has a label. Nanoleaf had no openings.
     - Live postings (`cand\industrial_final.census.json`): 1,933; 91 land on Design (Visual & Brand 25, Product
       Design 20, Industrial Design 19, no filter 23, 4 others) and 33 on Product. 59 land on Finance, about 14 of
       them misreads: Arc'teryx's "Assistant Store Manager | West Edmonton, AB" and a transportation manager (FP&A),
       Milwaukee's two "Commodity Manager – Packaging" (Commodities), 3M's "USAC Area Portfolio Manager",
       SharkNinja's "Manager, Media Investment Strategy" and Weber's "Asset Management and Production Specialist"
       (Asset Management), Hasbro's "Digital Asset & Workflow Systems Specialist" (Digital Assets), Polaris' "Quality
       Auditor" (Accounting), and product-compliance roles at Stanley Black & Decker, Brunswick, Bose and Polaris
       (Operational Risk). No markup and no test titles; every posting has a place.
     - Adding `consumer_products` to `design_occupation` changes none of these postings, so the claim is left as
       it is (`art_direction` names the type since the studios pack).
     - Employers: 33 entries with `=` aliases. "Brunswick" matches only "Brunswick" and "Brunswick Corporation",
       not Brunswick Group or the University of New Brunswick; "Specialized" not Textron Specialized Vehicles;
       "Arlo" takes no "Arlo Technologies" alias, whose one stored posting keeps its key.
     - Entries check (`entries\industrial_*.json`): 483 stored list postings (Stanley Black & Decker 174,
       Brunswick 150, Bose 53, SharkNinja 48, Polaris 46, and 12 more): 0 moves, the type's Industrial Design prior
       included; 483 label changes ("other" 251, Software 61, Hardware 49, AI & Data 32, Sales 22, People & Legal
       22, Design 21, Operations 12, Finance 7, Product 6); 3 renamed ("Stanley Black & Decker, Inc.", "Brunswick
       Corporation", "Arc'teryx Equipment").
     - Placement, `main` against the packs (`place\main_vs_p4f.txt`): missing 0, 0 moves outside 14.7, 9,050
       allowed; label changes 425 → 442. Against the Lever commit's placement: 0 moves, 61 label changes, 1 renamed.
     - Source history: 1,116 sources; against the last commit it adds only the 33 names. Tests: 963 and 116 pass;
       `test_board_polling.py`: Design names 21 groups, two of them (`design_studios`, `industrial_design`) not
       Product's.
     - Not added: Canada Goose and Trek (store and factory boards: 2 of 96 and 0 of 207 roles in product or
       design); Whirlpool and John Deere (Eightfold, read whole, 10 a page: 4 and 0 product or design roles of 216
       and 288); Galvion and JetZero (no product or design role; defence helmets and aircraft); Dorel Home (not on
       Dayforce's job search); Oshkosh (its "designer" search returns welders); Dyson (its design roles are in the UK
       and Asia); lululemon (a store-led Avature board); Harley-Davidson (a store-and-dealer SuccessFactors board,
       not narrowed); Solo Brands (UKG on a host `fetch_ukg` doesn't read); Delve and Design Concepts (JazzHR),
       Priority Designs (YourPayrollHR), Therabody (corporate board not found); Kohler, Teknion, Keilhauer, Danby,
       Smart Design, Ammunition, fuseproject, Ziba and Lee Valley (no board an adapter reads); Brompton (UK).
     - Eightfold's robots.txt (Whirlpool, John Deere) begins `Disallow: /` and then allows `/api/apply` and
       `/api/pcsx`. Python's `robotparser` lets the first rule win and calls those paths disallowed; RFC 9309, where
       the longest rule wins, allows them. Both sites were read once, alone.
     - Not added: Human Agency (its board posts one fund-manager role per city); Thoughtworks Canada (Workable
       `connected`: a software consultancy with no openings, whose entry would retype 8 stored Thoughtworks
       postings); Moment Factory (Cegid HR), lg2 (Recruitee), Siegel+Gale (Breezy) and frog (Greenhouse's EU host,
       which `fetch_greenhouse` doesn't read): no adapter; Publicis (robots.txt); WillowTree and nventive
       (group-wide boards of TELUS Digital and Wepoint), Designit (Wipro's board, no site found), Domain7 (merged
       into Versett); Sid Lee (no openings, main board unconfirmed); and 13 studios with no board an adapter reads
       (the pack's note lists them). Teague goes to `industrial_design`.
   - **`early_career_programs`, 2026-11-08**: 7 sources, the group of Product's APM & Programs filter; Design
     names it under Product Design and UX Research (D33's "Design names it too": where its design interns land).
     SOTI's Next Gen site, Visa's and Mastercard's early-career sites and Workday's are second sources, each with
     a label (D34); CoStar Group's Campus site, ID.me's university board and C3 AI's Ascend board are new
     employers. Each was read once, whole (20 / 20, 42 / 42, 24 / 24, 10 / 10, 1 / 1, 9, 3), with distinct ids.
     - Live postings (`cand\early_career_final.census.json`): 109; 14 land on Product (APM & Programs 12, Product
       Management 2), 1 on Design (Product Design: Workday's UX Designer Intern). 43 land on Finance: Visa's 28
       (Consulting & Analytics, Issuing, client services and controllership interns and graduates) and
       Mastercard's 15 (consulting, implementation and account-management Launch programs), as `visa` and
       `mastercard` place the same kinds of roles today. No markup and no test titles; every posting has a place.
     - 16 of Mastercard Campus's 24 postings are also on its CorporateCareers site, which `mastercard` reads (same
       title and place); 6 of Visa's 42 share a title and place with a posting `visa` stored, and 2 of Workday's
       10 with one `workday_hq` stored (support and sales; its product and design interns are only on this site).
       A direct posting's company string is its source's name, so these are not folded into one alert by
       company, title and place.
     - Visa and Mastercard are `fintech`: the folder test names their two boards as exceptions (14.7).
     - Employers: CoStar Group (`consumer_tech`, as Zillow and Compass), ID.me, C3 AI and Workday
       (`enterprise_saas`), each with `=` aliases from its stored names ("CoStar Group"; "ID.me"; "C3.ai" and
       "C3 AI"; "Workday" and "Workday Inc"). Workday's is your yes of 2026-11-08 (D27, 14.7); `workday_hq`, which
       has no `company_key`, is not edited, so its 614 stored postings keep their own key.
     - Entries check (`entries\early_*.json`): 113 stored list postings (CoStar 61, ID.me 26, C3 AI 26): 0 moves;
       113 label changes (Software 54, Product 21, AI & Data 15, "other" 12, Hardware 11); 22 renamed ("C3.ai").
       Workday's (`entries\workday_p4*.json`): 80 stored list postings, already keyed `workday`: 0 moves; 80 label
       changes (Software 26, AI & Data 17, Sales 17, Product 9, "other" 5, People & Legal 3, Operations 2, Design 1);
       42 renamed ("Workday Inc").
     - Placement, `main` against the packs (`place\main_vs_p4h.txt`): missing 0, 0 moves outside 14.7, 9,050
       allowed; label changes 442 → 443. Against the industrial commit's placement: 0 moves, 22 label changes
       (Product 21, Software 1), 6 renamed. With Workday (`place\main_vs_p4i.txt`): the same against `main`;
       against the pack's first commit, 0 moves, 10 label changes (Product 9, Design 1), 6 renamed.
     - Source history: records the bundle's 1,123 sources; against the industrial commit it adds only the 7
       names (the file also keeps 2 retired names). Tests: 963 and 116
       pass; `test_board_polling.py`: Product names 26 groups and Design 22, and APM & Programs polls core and
       this pack.
     - Amazon (D34) was read too: its `design` category (307 / 307: Design 157, Hardware 64, Software 52) and a
       "product manager" search of `project-program-product-management-non-tech` (163 / 163: Product 140). The
       whole non-tech category is 1,090 postings, 200 on Product, 445 on Operations and 89 on Finance; the 60
       Product postings the search leaves out are program managers (data centres, logistics). An amazon.jobs
       search is read to its last match and never marked complete, as for Amazon's four sources. Both are
       Amazon's own design and product roles, not early-career boards, so they go in the Big Tech pack with D34's
       Walmart and Nike reads.
     - Not added: Samsara's recruiting-programs board (no openings; D34 drops it); Zynga's early-careers
       board (one opening, not in product or design; a gaming employer); nCino's early-talent board (one opening,
       not in product or design; banking software, `fintech`); TikTok (D35); T-Mobile (ATS not identified); Etsy and
       NBCUniversal (robots.txt); LinkedIn (only through a LinkedIn company search; its APM program ended in 2025).
       Clearwater Analytics, Cox, Yahoo, Grammarly, Wayfair, AppLovin, Solace Health, CDK Global, Dick's Sporting
       Goods, Amplify and Medline have no early-career board: their main boards go to the sweep (8.6).
   - **`big_tech` and `consumer_tech`, 2026-11-08** (D34): 3 second sources, each with a label, in groups Product
     and Design core already poll (a pack's group is its file's name, as for `tech/` and `shared/`), so the
     manifest is unchanged. Amazon's two read amazon.jobs, as its four sources do; Nike's reads the Design job
     family of its `nke` Workday site, which `nike` (technology families) and `nike_finance` don't read.
     - `amazon_design`: the `design` category, 307 / 307 to its last match. Design 157 (Product & UX Design 99;
       Visual, Brand & Motion 28; Design Engineering 12; UX Research 6; Industrial Design 1; Content Design 1;
       no filter 10), Hardware 64 and Software 52 (design engineers for data centres, warehouses, robotics and
       networks), "other" 23 (civil engineers, video and creative roles), Operations 5, Product 4, Sales 2; none
       on Finance.
     - `amazon_product`: a "product manager" search of `project-program-product-management-non-tech`, 163 / 163.
       Product 140 (Product Management 119, Technical PM & TPM 18, APM & Programs 2, Product Operations 1),
       "other" 10, Operations 7, Finance 3 (two compliance roles and a payments product manager), Sales 2,
       Software 1. The whole category is left out for its 445 Operations and 89 Finance postings (item 4, above).
     - `nike_design`: the `jobFamilyGroup` facet for Design, 70 / 70, complete. Design 48 (Product & UX Design
       19; Visual, Brand & Motion 18; Industrial Design 3; no filter 8), "other" 19, AI & Data 2, Healthcare 1;
       none on Finance. 11 of the 19 are apparel designers: Design's title rule leaves out apparel and fashion
       design (`nd:fashion_textile_travel`, section 4.2), so they stay on "other". 2 are colour-design leads
       ("Director, Core Studio Color Design"), whose titles the rule doesn't take either; the other 6 are
       footwear research, materials and innovation roles and a production artist.
     - Not added (D34): Nike's Product Development Group (59 postings, 5 in product or design: footwear and
       apparel product creation); Walmart's product and design job families (112 postings: 97 in the Technology
       category `walmart_global_tech` reads; the other 15 are product-marketing, photo-studio and creative
       roles, 2 of them designers).
     - No employer entry changes, so there is no entries check. Placement, `main` against the packs
       (`place\main_vs_p4j.txt`): the same as for the Workday commit (missing 0, 0 moves outside 14.7,
       9,050 allowed, label changes 443). Against the Workday commit: no change at all.
     - Source history: records the bundle's 1,126 sources; against the Workday commit it adds only the 3 names,
       and no existing source's history changes. Tests: 963 and 116 pass.
   - **`product_core` and `design_core`, 2026-11-08** (D30): the four LinkedIn searches of section 7.5, with its
     queries and `linkedin_us_health`'s settings, no `company_key`. Product's core names `product_core` and
     Design's `design_core`, so a Product-only profile polls two of them and a Design-only profile the other two.
     Checked again against the 13 LinkedIn sources: no query repeats one for the same location (the two
     `*_hard_to_reach` company searches have an empty keyword). Each was read once with the app's reader; a
     LinkedIn search is never complete, and no query request failed. Postings are distinct by id.
     - `linkedin_us_product`, 265 in 154 s: Product 217 (APM & Programs 120, Product Management 75, Product
       Analytics 12, Technical PM & TPM 5, Product Operations 5), "other" 18, AI & Data 12, Operations 9,
       Finance 6, Sales 2, Software 1.
     - `linkedin_canada_product`, 214 in 108 s: Product 112 (Product Management 55, Technical PM & TPM 36, APM &
       Programs 19, Product Analytics 2), "other" 49, Finance 21, AI & Data 12, Operations 8, Software 6, Sales
       5, Healthcare 1. The co-op queries match loosely: the rest are general co-op and intern postings.
     - `linkedin_us_design`, 256 in 89 s: Design 224 (Product & UX Design 91; Visual, Brand & Motion 50; Content
       Design 41; Industrial Design 27; UX Research 12; no filter 3), "other" 22, Sales 3, Finance 2, Software 2,
       Operations 1, AI & Data 1, Hardware 1.
     - `linkedin_canada_design`, 236 in 101 s: Design 141 (Product & UX Design 69; Visual, Brand & Motion 48; UX
       Research 11; no filter 10; Industrial Design 2; Content Design 1), "other" 33, Hardware 23 (mechanical
       design co-ops), Software 20, Finance 9, Product 3, Sales 2, People & Legal 2, Healthcare 1, AI & Data 1,
       Operations 1.
     - No posting that lands on Product or Design lacks a product or design word, and none is an engineering,
       interior or marketing role (`linkedin\off_board.txt`).
     - New to Foothold (`linkedin\overlap.txt`, against the live copy, last polled 2026-10-31): of the 694 that
       land on their own board, 508 match no stored LinkedIn id and no open posting with the same title and
       employer (US Product 127 of 217, Canada Product 83 of 112, US Design 174 of 224, Canada Design 124 of
       141). Many of the rest are postings the new-grad and intern lists also carry.
     - Finance landings: 38 (RBC Amplify business analysts, American Express campus programs, insurance and
       banking product internships). Seven are research roles Finance's rules take first: "UX Quantitative
       Research Intern" 3 times (quant research), "User Research Analyst" twice and "Customer Experience
       Research Analyst" (equity research), and "Customer Researcher, Payments" (payments). Finance stays as
       it is (section 14), so they are left there.
     - Design roles that land on "other": French titles Design's words don't read ("Stagiaire, design
       industriel", "Stagiaire, en design graphique", "Graphiste débutant(e)", "Concepteur des interfaces
       utilisateurs"), and "Experience Researcher" and "Player Experience, Research II". Not changed here.
     - LinkedIn lock time, measured: Product's two 263 s, Design's two 190 s, all four 452 s (section 7.5
       extrapolated about 9 and 18 minutes). The poll-time report gives LinkedIn its own line.
     - Placement, `main` against the packs (`place\main_vs_p4k.txt`): the same as for the Amazon and Nike
       commit (missing 0, 0 moves outside 14.7, 9,050 allowed, label changes 443). Against that commit: no
       change.
     - Source history: records the bundle's 1,130 sources; against the Amazon and Nike commit it adds only the
       4 names, and no existing source's history changes. Tests: 963 and 116 pass; `test_board_polling.py`:
       Product names 27 groups and Design 23.
   - **The sweep of list-only employers (8.6), 2026-11-08**: `product_design/enterprise_saas.json` (OpenSesame,
     Clearwater Analytics) and T-Mobile in `product_design/consumer_tech.json`, each with an entry: your yes on
     each (D27, 14.7).
     - Ranking (`scripts\sweep_rank.py`, on the branch's placement and the live copy): 274 employers have open
       Product or Design postings only through lists or LinkedIn, 735 distinct by title and place. 42 have 4 or
       more; the other 232 have 1 to 3 (336 postings), which the lists carry.
     - `opensesame`: Greenhouse, 20 / 20. Product 2 (AI Product Builder Intern; Product Manager, Strategy &
       Growth), Sales 11, "other" 4, AI & Data 1, Operations 1, Software 1.
     - `clearwater_analytics`: Workday `clearwateranalytics.wd1` / `Clearwater_Analytics_Careers`, the site
       cwan.com's own job feed uses, 277 / 277. Product 23 (Product Management 13, APM & Programs 7, Technical
       PM & TPM 3), Design 4, Finance 21 (investment-accounting roles), "other" 130, Software 59, Operations 19,
       Sales 13, People & Legal 4, AI & Data 4; 3 postings carry no place.
     - `t_mobile`: Workday `tmobile.wd1` / `External` (about 2,400 postings, 2,234 of them retail sales),
       narrowed by `Job_Family_Group` to Product Management Technical, Product Management, Product Development
       and Intern: 60 / 60. Product 22, Design 4 (a UX design internship, a UX researcher, two content
       designers), Software 16, "other" 6, Sales 5, AI & Data 4, Finance 2, People & Legal 1; 1 posting carries
       no place. careers.t-mobile.com answers 403; the Workday host reads.
     - Employers (`entries\sweep_*.json`): OpenSesame and Clearwater Analytics `enterprise_saas` (as SS&C, FIS
       and Workiva), T-Mobile `telecom` (as Verizon and AT&T), each with one `=` alias from its one stored
       name. They type 119 stored list postings (T-Mobile 71, Clearwater 39, OpenSesame 9): 0 moves, 0
       renames. Typed `fintech`, Clearwater would move 3 stored "Data Management & Reporting Intern" postings
       from "other" to Finance, so it isn't. T-Mobile is off the P&D track: the folder test names it beside
       Visa and Mastercard.
     - Not added (`sweep\report.md`; the `enterprise_saas` note lists them): Meta, IBM and Tesla (the LinkedIn
       company searches read them); TikTok and Tencent (no reader for their own sites); Etsy, NBCUniversal and
       Publicis Groupe (SmartRecruiters, robots.txt); Cox (jobs.coxenterprises.com renders its list in the
       browser; the Radancy paths answer 404); Copart (a bot wall); Fox (a custom site, ATS not identified);
       Questrade (its `shared/` decision is open); CACI (already read as `caci_international`, section 15).
       Off the P&D track, their rows mostly technical PM and engineering designers: Vertiv (Oracle HCM, readable),
       Parsons, Johnson Controls, Caterpillar, Schweitzer Engineering Laboratories, Cummins, Symbotic, Emerson,
       AspenTech, Guidehouse, Credence, Thornton Tomasetti and Oshkosh. Finance employers, whose source would
       change what Finance polls or keep their Finance roles behind Product and Design: Allstate, BNY, KeyBanc,
       State Street, M&T Bank, PNC, Travelers, Brown & Brown, D. E. Shaw, LSEG and DriveWealth. RELX and Nelnet:
       small, off the track.
     - Placement, `main` against the packs (`place\main_vs_p4l.txt`): missing 0, 0 moves outside 14.7, 9,050
       allowed, label changes 443, as before; inside the boards 29 more type labels (223). Against the LinkedIn
       commit: 0 moves, 37 label changes on Product (`enterprise_saas` 21, `telecom` 16), 0 renamed.
     - Source history: records the bundle's 1,133 sources; against the LinkedIn commit it adds only the 3
       names, and no existing source's history changes. Tests: 963 and 116 pass.
   - **Poll time, 2026-11-08** (`tools/poll_time.py`, tested in `tests/sources/test_poll_time.py`): every enabled
     source (1,123) read once with the app's reader, LinkedIn, Lever and Eightfold each one source at a time on a
     thread of their own; then each sample profile's full poll (every source due) replayed on 10 threads in poll
     order, `main` (`9e9201b`, its packs as at `937bbc2`) against the branch. One fetch run gives every number here.

     ```
     python -m tools.poll_time time --config config.json --out E:\product-design-board\phase4\poll\timings.jsonl
     python -m tools.poll_time simulate --before E:\product-design-board\code-main-9e9201b --after . --timings E:\product-design-board\phase4\poll\timings.jsonl --json E:\product-design-board\phase4\poll\simulate.json
     ```

     | Profile | Sources | Full poll, min (lower bound) | LinkedIn, min |
     |---|---|---|---|
     | Product | 319 → 729 | 16.0 → 62.6 (13.9 → 26.9) | 0.9 → 4.6 |
     | Design | 319 → 676 | 16.0 → 49.1 (13.9 → 25.6) | 0.9 → 5.0 |
     | Product + Design | 319 → 798 | 16.0 → 62.6 (13.9 → 26.9) | 0.9 → 8.7 |
     | Finance + Product | 536 → 809 | 26.0 → 64.3 (20.3 → 30.4) | 7.9 → 11.6 |
     | Software + Product | 713 → 792 | 62.6 → 62.6 (27.1 → 27.2) | 2.6 → 6.3 |
     | Software + Design | 713 → 859 | 62.6 → 62.6 (27.1 → 27.2) | 2.6 → 6.7 |
     | Everything boards, Finance + Sales, the Actions runner | 1,004 → 1,123 | 70.3 → 70.3 (30.6 → 30.6) | 16.9 → 24.7 |

     Every other sample profile polls what it did, in the same time (`poll\simulate.txt`).
     - Why Product and Design rise: Eightfold. Every Eightfold request waits 1.5 s after the last, on any site,
       so its sources add up: Product's Eightfold time goes 16.0 → 62.5 min, Design's 16.0 → 49.1. The new ones
       are Lockheed Martin (21.3 min), Northrop Grumman (9.2), Qualcomm (7.8), Lam Research (3.6), GlobalFoundries
       (1.7) and their finance boards, in `defense_aerospace` (Product's Technical PM and Product Ops filters,
       Design's Product Design, Visual & Brand and Industrial Design) and `semiconductors` (Technical PM). A board
       with no filter picked polls every filter's groups. No Phase 4 source is an Eightfold one.
     - They are due every 1 to 6 hours (`min_interval` 3,600 to 21,600 s), so a full poll is the first one and
       the ones they are due in; in those, sources due every 5 to 15 minutes wait for the poll to end, as they
       already do for Software (62.6 min).
     - What they give (`poll\whatif.txt`, open postings on the live copy): the Eightfold sources above 189 Product
       and 28 Design postings. Dropping whole groups: Product without `defense_aerospace` polls in 29.5 min and
       loses 346 open Product postings, without `semiconductors` 49.2 min and 453, without both 16.1 min and 799
       (of 9,891); Design without `defense_aerospace` 16.0 min and 138 (of 2,384). D28's groups stay: your
       answer, 2026-11-08 (14.7).
     - The bounds: LinkedIn holds its lock through each request, so its share is exact. Lever and Eightfold only
       space their requests' starts and let them run together: serialising their sources is the upper bound,
       letting them run freely the lower. Which is closer depends on how long their requests take, not measured.
     - Reads that failed in the run, all existing sources, reported and not changed: `old_mission` (Greenhouse
       404), `aircall` (Lever 404), `jpmorgan_tech` (Oracle pagination repeated a page), `blackstone` and
       `blackstone_campus` (Workday 401), `nxp` (Workday 422). Every source this branch adds read.
     - `main` is now `9e9201b`, the 0.3.15 release (`version.py` and the release notes only), so the What's new
       draft is for the next version.
   - **Chip and board designers from Design to Hardware, 2026-11-08** (your yes): Design's `designer` words held
     72 open postings (61 titles) that are chip, circuit-board, RF, photonics or substation design, all placed by
     title words and no claim ("Memory Designer", "SoC Physical Designer", "Senior PCB Designer", "Substation
     Physical Designer"). Two Hardware claims take them from Design only, so no other board's posting can move:
     - `hardware_designer`: a design title that names a chip, board, RF, photonics or substation subject (IC
       but not "(IC)", SoC, CPU, DRAM, PHY, DFT, PCB, printed wiring board, RF, mmWave, antenna, laser
       designer, photonic, optical, SOI, FBAR, CMOS, lead frame, substation and more), at any employer: 60.
     - `designer_at_chipmaker`: "Digital Designer", "Memory Designer", "Designer, Layout" and filter, packaging
       and system design, which are chip roles only at a semiconductor employer: 12.
     - Neither takes a title with a design occupation's word (UX, UI, user, interaction, visual, graphic, brand,
       creative, product designer, industrial, CMF, game, design systems, research and others), so "Senior
       Manager (IC), Product Designer", "HW UX/UI Design Co-op", "Digital Designer" at a retailer and "Senior
       Digital Designer, Design Systems" stay on Design. A reviewer's run found "Level", "Media" and "Video"
       in that list blocked chip titles only ("Media SoC Designer"); they are out.
     - Placement check against the sweep's commit: 72 design → hardware and nothing else; against `main` the
       moves that change what Finance shows stay 2,494. In Hardware they land in Chip Design 11, Electrical 12,
       Robotics 1 and no filter 48: Hardware's filter words name "design" and "engineer", not "designer". Left
       for the rule review, with what stays on Design: titles that could be either ("Sr. Design Lead" at AMD,
       "Director - Design Manager" at Qualcomm), the construction and facilities design managers at Intel and
       Micron (to "other" changes what Finance shows), and Intel's "ADCE Packaging Design Architect": Intel and
       Skyworks have no company entry, so no employer type.
5. **Resume reading, matching and Calendar,** with the fixtures of section 9.
   - `resume_record compare` against `baseline\resumes_main.json` passes: the existing fixtures read
     byte-identically under every saved profile.
   - Each shared-reader change has your yes and its own commit (section 9.10).
   - The stored resume is compared field by field, `main` against the branch, and only field names are printed.
   - Program windows are tested as `tests/app/test_program_windows.py` does.
   - The placement check runs again.
6. **Onboarding, Settings, Sources view and docs.**
   - A What's new draft for the version after 0.3.15 (which `main` released on 2026-11-07), with every claim and
     count checked against the final packs. `version.py` is not touched.
   - Merge `main`, and take the placement check's `main` side again if `main` changed what the check reads.
   - Restore the source history from `main`, record 12 again, and end with a `record_release` dry run.
   - Both full suites and `watcher.py --check`.
   - The UI in a browser, as a Product-only and as a Design-only profile.
   - The final report, and the lessons in Part C of the brief.

**The commands** (from the worktree, each as `PYTHONUTF8=1 uv run --no-project --with-requirements requirements.txt
python -m …`; `E:` is `E:/product-design-board`; `<branch>` is an export of the branch, with uncommitted files copied
over as the brief's "Run it on exports" says):

```
tools.board_gate polled --code <branch> --config <branch>/config.json --out E:/phase2/polled_branch_bundle.json
tools.board_gate polled-compare E:/baseline/polled_main_bundle.json E:/phase2/polled_branch_bundle.json --expect product --expect design --expect product+design --expect finance+product --expect software+product --expect software+design
tools.board_gate sample --db E:/live_copy.db --out E:/phase3/ids.json --words E:/code-main --words <branch> --board product --board design --title-file E:/scripts/candidate_titles.json
tools.board_gate place --code E:/code-main --db E:/live_copy.db --config E:/installed-config/config.json --ids E:/phase3/ids.json --out E:/phase3/placed_main.db
tools.board_gate place --code <branch> --db E:/live_copy.db --config E:/installed-config/config.json --ids E:/phase3/ids.json --out E:/phase3/placed_branch.db
tools.board_gate place-compare E:/phase3/placed_main.db E:/phase3/placed_branch.db --board product --board design --allow <from>:<to> … --json E:/phase3/changes.json
tools.resume_record record --code <branch> --out E:/phase5/resumes_branch.json
tools.resume_record compare E:/baseline/resumes_main.json E:/phase5/resumes_branch.json
```

The full gate (`snapshot`/`compare`, hours) runs only if you ask for it.

---

## 14. Decisions

Each decision gives its counts, the trade-off and my recommendation, so you can answer "as recommended", or name the
ones you want otherwise. Counts are open postings unless they say stored. Under your rule (section 12), every move
of another board's posting needs your yes with its count. A move from or to Finance or "other", which Finance
profiles review, is marked in bold. The section column points to the detail. A few options and counts come from
the research run behind a section rather than its text; those rows say "not simulated" or "judgement" where the
run did.

You approved all 46 as recommended on 2026-11-07. Section 14.7 records what that allows; the rows below stay as
they were put to you.

### 14.1 Title words and moves (sections 3 and 4)

| # | Question | Recommendation | § |
|---|---|---|---|
| **D1** | **Product's new title words.** Product owners and leads, head/VP/director of product, TPM and PM-T, product interns, product analytics, plurals and the -ment forms. As drafted, with no exclusions, they move 1,655 into Product: **"other" 1,147**, Operations 201 (123 of them product ops, D4), **Finance 170**, Software 64, Sales 49, Design 15, People & Legal 7, Healthcare 2. The census's exclusions drop the false moves: head/director of product marketing or design, product strategy (**Finance 36**, **"other" 47**, Operations 22), bare pm/apm/cpo, and drug product analytics. The plural and -ment forms (P1) move 628, nearly all of it `program management` (**497 from "other"**); plurals alone are about 5. The census table left out 48 "PMT" titles ("other" 36, Finance 6); with them P2 moves **175** from Finance. Also "product builder": 34 open titles, of which **"other" 18**, Design 6, Software 4, People & Legal 2, **Finance 1** and AI & Data 1. | **Add the words with the exclusions and the plurals.** Of the -ment forms, take only technical/engineering program management. **Finance −134** together with D2's B1 (Product 95, Operations 39), plus 5 PMT titles. Add "product builder", guarded against Amazon's "Application Builder", counted in Phase 3 | 4.1, 5.5 |
| **D2** | **Plain program managers.** 3,743 open program-manager titles are on Product, 41% of the board. In a sample of 40, 19 were technical program management, 17 operations-type and 4 other boards' work (judgement). A: keep them. B1: plain "program manag…" becomes an Operations word, and a Product claim takes back titles with tech evidence in the title or description: Product → Operations 1,413, **"other" → Operations 416**, **Finance → Operations 39** (PMO analysts, mostly Citi's and JPMorgan's), Software → Operations 14. B2: as B1, but a tech employer type counts as evidence: 655 / **312** / **34**. C: all plain program managers go to Operations: 2,158 / **497** / **46**. B1, B2 and C also move Product → Sales 76 and Product → Design 36. TPM and technical-program titles stay on Product in every option. | **B1,** with a tighter subject list (technical, tech, TPM, engineering, software, hardware, firmware, silicon, ASIC, SoC, cloud, infrastructure, AI/ML, data center, network, platform, IT), Amazon's and Microsoft's technical departments as evidence, and `unless` engineers and "non-technical". No bare "program management" on Product. Operations hasn't had its own session yet | 3.4, 4.1 |
| **D3** | **PM and TPM titles that tech boards take by topic word.** A Product claim for PM titles takes Software 639, AI & Data 81 and Hardware 46 ("Senior Product Manager, Cloud Networking"). A program claim adds Software 420, Hardware 130 and AI & Data 40. Two known false moves to fix first: Eulerity's "AI Intern, Office of CEO & Head of Product" (7) and JPMorgan's "Product Delivery Manager" (2). Your own Software + Hardware lists lose these titles. | **The PM claim, and the program claim,** since D2's B1 keeps TPMs on Product. Both get evidence fields, as 3.1 proposes (4.1.5 holds that the occupation alone is evidence enough; the Phase 3 recount shows which), and `unless` engineer, developer, scientist, architect and programmer | 3.1, 3.5, 4.1 |
| **D4** | **Product ops from Operations.** 123 "Product Operations Manager/Specialist" titles are on Operations. Moving them also takes Sales 5, Design 3, **"other" 3** and **Finance 1**. Without the move, `product_ops` holds 16. | **Move them**: they are the filter's whole content | 3.2, 4.1 |
| **D5** | **Titles on Product that aren't product work.** 11 executive assistants (Cisco 7, Crusoe 2, JFrog 1, Unity 1) and 7 nurse and pharmacist program managers ("RN Program Manager Abdominal Transplant"). A Product exclusion sends the assistants to Operations (10) and Sales (1). The 7 clinical program managers reach Healthcare only through a Healthcare claim change; a Product exclusion alone puts them in **"other"** (D2's A) or on Operations (B1, C). Also 2 more: a pharmacy coordinator and a paralegal. | **Exclude the assistants; send the 7 to Healthcare with a Healthcare claim** (an edit to Healthcare's data, which needs this yes). Anchoring the assistant exclusion may need a family-level `unless` in shared `family_of`: I'll show it before writing it | 3.2, 4.1 |
| **D6** | **Product and Design claims from Finance.** Finance holds 2,153/1,844 stored/open postings naming any P&D word, most of them noise ("Product Control"). Claim V3 moves 293/247 (Product 266/227, Design 27/20; JPMorgan 114/112): product owners, product associates, TPMs, heads of product and quantitative UX researchers (16/12 of them on Quant). In a sample of its 27, 26 were real P&D roles and 1 borderline (judgement). V1 (main's words) moves 203/174, 12 of 20 sampled wrong. V2 adds product analysts (304/257). A bare program-manager claim moves 115/102, 0 of 11 sampled product roles. | **V3, as two named claims,** approved as a **Finance move of 247 open** (Investment Banking 54, Risk 44, FinTech 43, Wealth 23, Quant 18 and the rest). With D1 and D2: **Finance −303 open** (Product 244, Design 20, Operations 39), before the 5 PMT titles and product builder's 1. No product-analyst or bare program-manager claim | 4.3 |
| **D7** | **Shared code: edit `_TECH_OCCUPATION` / `_BUSINESS_OCCUPATION`, or work through data only.** Program/TPM words in `_TECH_OCCUPATION` take 120 Finance postings, mostly compliance and risk program managers, and still miss product owners and quant UX researchers. Dropping the product alternatives sends 259 to Finance. The `_BUSINESS_OCCUPATION` edits move 0 Sales or Operations postings, but cost Healthcare 16. `classify` also reads resume lines. | **Data only.** Both regexes stay as they are; D6's claims do the job | 4.1, 4.3 |
| **D8** | **Design's bare `design`.** 3,566 Design postings carry `design` without `designer`, and 2,902 of them aren't design work (judgement: chip 940, mechanical 970, plain engineering 536 among those with no other word). Keep it: the board stays 62% non-design. Narrow Design's words only: 3,438 change field (3,437 board moves and S&P's Finance filter change), among them Software +2,182 and **"other" +1,005**. Narrow, add the Design claim (D13), Hardware title words and a Hardware claim: 3,589 change field (3,588 board moves and the same S&P change). Hardware +1,747, **"other" +877**, Software +672, Sales 62, **Finance 44** (D9), Operations 42, Healthcare 24, People & Legal 12, and side moves Software → Hardware 14 and Product → Hardware 1. Design goes from 5,546 to 2,159. The moves out include the 44 that D9 keeps and the 95 game designers that D12 keeps; Phase 3 recounts with D9 to D14 in. | **Narrow, with Hardware's words and claim.** In Phase 3, widen the Hardware words until Design → Software is near 0, add patterns for the 72 real design titles the draft loses, and keep a plain "Design Engineer" on Design at software employers. Then show you the remainder. This edits Hardware's title words and claims | 4.2.5 |
| **D9** | **The 44 postings that narrowing puts on Finance** (FinTech 21, Risk 6, Corporate Finance 4, IB 4 …: JPMorgan's "Payments-Digital & Design", Citi's "Assessment & Design", Mastercard creative), plus 1 Finance filter change (S&P "Index Design"). Keeping them keeps on Design the 7 marketing creative roles that D10 drops elsewhere, the 3 instructional and 3 network designers that D11 releases, and JPMorgan's 9 product roles. | **Keep them on Design** with a Design claim from Finance on the old bare words, with an `unless` for Finance's subjects, so **Finance stays identical**. Add `index design` for S&P. Revisit when the Product and Sales sessions add their words | 4.2.5 |
| **D10** | **Bare `ui` and `creative`.** `ui` alone brings 59: 37 UI programmers (→ Software 19, **"other" 18**), 17 game UI artists (→ **"other"**) and 5 designers. `creative` alone brings 270, 160 of them marketing and production roles. Narrowed, the 166 marketing creative roles in all go to **"other" 96**, Sales 44, Operations 8, **Finance 7** (inside D9's 44), Software 1 and People & Legal 1, and 9 stay. | **Drop both,** and keep `ui/ux`, `ux/ui`, `ui design(ers)`, creative director/lead, head of creative, brand/integrated creative and creative technologist | 4.2.4 |
| **D11** | **Titles that aren't design work, and interior design.** Instructional designers 119 (→ **"other" 82**, **Finance 3**; 27 stay), network and solution designers 104 (→ **"other" 38**, Software 20, Hardware 7, **Finance 3**; 35 stay), CAD 36 (→ **"other" 16**, Software 3; 17 stay), recruiters 12 (→ People & Legal 8, Operations 2, **"other" 2**), arts therapists 3 (→ Healthcare), faculty 15. Architectural interior designers: Ontario protects the title (ARIDO), so it is a licensed building trade. 11 open titles say "interior designer"; vehicle interiors are industrial design. Neither field has a licence. | **Release instructional, CAD, network and architectural interior designers, and fix the lookbehinds that keep 27 learning-experience, 17 CAD and 35 network titles; move the recruiters** (reverse moves). Keep a plain "Designer" at engineering employers (31). No `licences` block | 4.2.7–4.2.8, 5.1 |
| **D12** | **Game, level and narrative designers.** 107, 89 of them at game studios. Keep them on Design in a `game_design` filter, which moves nothing. Release them: **"other" +94**, Operations +1. Or give them to `software.game_dev`, which needs new Software words (not simulated). | **A `game_design` filter** (judgement; the census leaves this to you) | 4.2.8 |
| **D13** | **Moves into Design.** 93: **"other" 46** (art directors, illustrators, motion designers, user researchers), Software 31 (product and UX designers whose title names Platform, Mobile or Cloud), **Finance 12** (Quant 8 UX researchers, FinTech 3, Risk 1; all inside D6's 20), Hardware 2 (1 wrong), Healthcare 1 and Sales 1. | **Approve the Software, Healthcare, Sales and "other" moves, but not the 9 game-studio art directors, RTX's "Technical Writer & Illustrator" or Blue Origin's tooling designers (D14). Approve the 12 Finance moves as Finance moves.** Fix the claim's `unless` (asic, digital designer), give it evidence fields, add "experience design" and "product design manager" (they reach JPMorgan's 2 "Experience Design" roles on **Finance**, already among D6's V3 moves), and recount in Phase 3 | 4.2.6 |
| **D14** | **Design word details.** Plurals (`designers?`, `researchers?`, `art directors?`, `illustrators?`), with "tooling" excluded: 1 FIS posting from **"other"**. `cmf` only as "CMF design(er)": 0 moves (bare `cmf` would take 9 Software engineers and 9 Sales roles). `content_design` = UX writing, content design, conversation design, "UX content writer": 1 Figma content strategist from **"other"**; copywriting and content marketing stay with Sales and "other". | **All three as described** | 4.2.9–4.2.11 |
| **D15** | **PM and designer titles Healthcare holds** through "clinical" and "medical": 103/98 stored/open ("Clinical Product Manager" at Siemens Healthineers). A P&D claim from Healthcare could take about 35 open PM, product-owner and UX titles (29 + 5 + 1; not simulated). | **Leave them on Healthcare,** as its approved design says; a Healthcare + Product profile sees them | 3.6 |
| **D16** | **The filters.** Product: product_management, technical_pm, apm_programs, product_ops and product_analytics, with growth_pm folded into product_management (76 titles on Product; 74 of its 169 hits on all boards also match product_management). No strategy, delivery or program_management filter. apm_programs as programs plus every PM internship, co-op and new-grad PM (628 hits, `related` to product_management), or programs only. Design: product_design, ux_research, visual_brand (with motion, illustration and art direction), content_design, design_engineering and industrial_design (plus game_design under D12). No accessibility or human-factors filter. `also_targets`: product_analytics counts `data_ml.analytics`, design_engineering counts `software.frontend`; this moves 0 postings and changes scoring only for profiles that also have AI & Data or Software. | **As listed, with apm_programs as programs plus internships.** The filter keys repeat nothing on another board or in Finance (3.7) | 3 |

### 14.2 Levels and calendar (section 5)

| # | Question | Recommendation | § |
|---|---|---|---|
| **D17** | **A bare Product, Program or Project Manager reads Senior**, because the shared `senior_ic` reads "manager" as a level. 89% of open Product postings read Senior. A board rule reads it Experienced: 3,631/3,247 stored/open fire, and 3,626 stored stages change: 3,614 Senior → Experienced, each worth 21 fit points to a student, and 12 misread "Development Program Manager" titles New grad → Experienced. B: a code change lets years decide (461 stored stay Senior). C: keep Senior. | **The board rule (data only).** Optional: one more rule for 6 "Senior … Development Program Manager" titles still misread. The rest of the shared misreads are reported in §15 | 5.3–5.4 |
| **D18** | **Early-career levels** (stored/open). APM and rotational programs → New grad (8/2). Associate PM → Entry (73/59; 53 of 100 open APM titles read Senior today). PM I → Entry (57/53). Dated PM titles → New grad (2/2). French and German intern words → Internship (15/14). Designer, Researcher or Artist I → Entry (12/9). Apprenticeships, design residencies and fellowships → New grad, with guards (not simulated, under 10 open). 66 open Product titles say "MBA"; today only "MBA Intern" titles set `post_mba`, through Summer Associate, and "MBA Product Intern" reads plain Intern. | **Adopt,** with a plain Associate PM at Entry and Junior left at New Grad. The MBA rule only as a `summer_associate`-keyed board level with a full-time guard (not simulated), else leave it | 5.1, 5.4 |
| **D19** | **Bank and agency bands** (stored/open). "Product Manager, Associate" (24/22), Capital One's "Principal Associate" (11/10) and Art Director (9/5) read Senior today → Experienced. Associate Art Director (2/2) → Entry. | **The narrow, simulated rules** | 5.4 |
| **D20** | **Level words that name a team.** 33 open Product titles, among them Citi's "Asia Early Career Program Manager" (read New Grad) and Applied Materials' "Internship Program Manager" (read Intern). American Express's 2 "Campus - Full Time - Product Manager - 2027" read Senior. | **Route the HR and program-admin titles out with D2**, add an `unless` so a team word right before "program manager" isn't read as a level (not drafted), and read "campus" as New grad by taking it out of PL3's `unless` | 5.3, 5.5 |
| **D21** | **Level labels and badges.** Labels only, with no stage or fit change: Principal (not "Vice President"), Director, Head / Chief, Creative Director, Senior Art Director. That is 1,352/1,193 stored/open Product and 636/560 Design postings. Badges: the new levels show none, because `BOARD_LEVEL_BADGES` lists Healthcare's keys only. Reuse Healthcare's keys in data (`new_grad_program` for APM programs and apprenticeships, `residency`, `fellowship`), or add new badges, a `scoring.py` edit that needs `RULES_VERSION`. | **Adopt the labels** (you can change the words). **Badges through Healthcare's keys**, data only: an APM program shows NEW GRAD PROGRAM with the label "APM Program" | 5.4, 10.3 |
| **D22** | **Design postings with no level word.** 2,049/1,809 stored/open (33%). 1,502 open ones read Unspecified (Experienced) with under 2 years asked, so a student takes the 8-point penalty. A Healthcare-style entry rule needs a code change in `intel/seniority.py`, because `entry_to_practice`'s note is written for licensed occupations. | **Keep them as they are.** "Product Designer" is a mid-level title at big tech, and no licence marks it as entry | 5.1, 5.2 |
| **D23** | **Program windows.** 12 windows that say "typically": Product 4 (Jul 1, Aug 1, Sep 1, Jan 15), Design 5, and 3 Canadian co-op windows on both boards. A US-only profile sees the co-op windows too. A Product + Design profile sees each co-op window twice, because `intel/programs.py` doesn't de-duplicate by key (from reading the code). | **Add all 12, and show each key once per profile** (a small `intel/programs.py` change; it changes nothing for Healthcare, whose keys are distinct) | 5.6 |

### 14.3 Track, employer types and companies (section 6)

| # | Question | Recommendation | § |
|---|---|---|---|
| **D24** | **Track.** Keep tech: no fit change, but every P&D skill is also read on every other non-Finance board's postings, and every P&D type and resume signal applies to Software, AI & Data and Hardware, and a UX resume keeps opening Software (`software.frontend` 0.62). Or one Product & Design track like Healthcare's, with big_tech, consumer_tech, enterprise_saas and high_growth_startup shared as `["tech", "<pd>"]`. Its cost for P&D-only profiles: 2,549 Product and 3,066 Design stored postings fall from 7 to 4 company points, and the other 16 tech types leave their Settings. Tests change: `test_boards.py`, `fields.test.js`, `test_tech_taxonomy.py`, and `test_resume_tech.py` if big_tech shares. Tech, Finance and Healthcare profiles: 0 points move. | **One Product & Design track,** with its resume data in the same commit. Each further type that should share it (gaming: 215 Design postings; hardware_devices: 234) is a yes of its own | 6.1, 9.4 |
| **D25** | **New employer types** for new employers only: `design_studio` ("Design Studio & Agency", 41 candidates) and `consumer_products` (34 industrial-design candidates). They go on the P&D track, with priors only on design.* and product.* filters, and lend no HQ country. 0 stored postings are at these employers' types today. | **Both** (keys and labels are placeholders). Each is simulated before it lands | 6.2 |
| **D26** | **Payments and banking-software candidates** (Clearwater Analytics 39 stored rows, Interac 8, Hiive, nCino, Zafin, Helcim). With `fintech`, Finance profiles gain 3 points, HQ country fills in, and the prior can pull generic titles onto **Finance**. With a tech type, Finance sees labels only. | **A tech type** (enterprise_saas; canadian_tech for the Canadian ones). A fintech type can come with Finance's own work (judgement) | 6.2 |
| **D27** | **Entries for shared employers with no entry** (Figma, Adobe, ServiceNow and 109 more; 112 sources, all "Unclassified" at 4 points). Name-only entries move 432 company keys, so they are out. Checked with the placement check on 35,439 stored postings, the 64 with 10+ P&D postings give 0 moves and 0 missing. They give 35,350 stored label changes (Finance 1,512, "other" 7,666) and 33,061 renames, plus 88 filter changes on other boards (Software 79, Hardware 8, AI & Data 1) from 9 employers' type priors (Roblox 46, Crusoe 17 …). The short list of 8 (Figma, Adobe, Webflow, Notion, Duolingo, Asana, Airbnb, Spotify), each with an `=` alias, its right name and a prior-free type, types 1,674 stored postings (Finance 88, "other" 364, Product 108, Design 60) with 0 filter changes. What you would see: the type tag in the posting detail, new options in the Employer type filter, the "Why" line, and these employers in the Companies list (6.7). | **The short list of 8,** label changes only. Others one at a time, each with its counts | 6.5–6.7 |

### 14.4 Sources and polling (sections 7, 8 and 11)

| # | Question | Recommendation | § |
|---|---|---|---|
| **D28** | **Which existing groups Product and Design poll.** Today's 9 groups carry 51% of stored Product and 39% of Design postings. The groups not polled today hold 2,900 of 7,069 stored core P&D postings (41%), 15 of them with 67 or more. A: today's 9 (319 sources). B: one flat list of 24 groups (679). C: 14 groups (460). D: 19 groups (608), which drops `sales_marketing_software`, the only option that loses postings: 97 stored postings found nowhere else, which `prune()` deletes 90 days after their last poll. E: core (today's 9 plus the new core packs) plus per-filter groups; All of Product = B's 24 groups (679), All of Design 18 (559, no `semiconductors`). Mixed profiles gain and never lose under A, B, C and E: finance+product 536 → 759 (tech/ only), software+product and software+design 713 → 742. Finance-only, Software-only, Healthcare-only and the everything boards don't change under any option. | **E.** No profile polls less than today, each filter adds only the groups its titles are in, and Design never polls chip-design groups. The per-filter lists are re-cut once D16 fixes the filters | 7.2–7.3, 7.8 |
| **D29** | **Folder.** One `product_design/` with audience `["product", "design"]`, or `product/` and `design/`. With two folders, an employer both boards want needs two sources. Finance, the tech boards and Healthcare poll neither. The everything boards gain the new sources either way. | **One `product_design/` folder.** The tech boards stay out of its audience | 7.4 |
| **D30** | **The boards' own LinkedIn searches.** Four 6-query sources (`linkedin_us_product`, `linkedin_canada_product`, `linkedin_us_design`, `linkedin_canada_design`). They repeat none of the 13 existing LinkedIn sources' queries. They add about 9 min of LinkedIn lock time to a one-board profile and 18 min when all four run: Product + Design, the everything boards and the Actions runner (extrapolated from Healthcare's 274 s). Or two shared searches: about 9 min, fewer queries per board. | **Four sources,** as the brief models. `linkedin_us` and `linkedin_canada` are not edited | 7.5 |
| **D31** | **Employers that hire for both P&D and Finance.** 757 stored P&D postings sit at 21 finance/ sources, which a P&D-only profile never polls (JPMorgan 384, Citi 181, Morgan Stanley 37 …). (b) Option E's groups, `tech/bank_technology` among them, hold a copy of 169 of them (most at the banks' tech feeds, the rest at lists), and the feeds hold 83 product and 34 design stored postings of their own. (c) A new `product_design/` source per employer's product/design family; a Finance + P&D profile then polls that employer twice. (d) A new shared/ source, which changes what Finance polls. Visa's and Mastercard's early-career Workday sites carry their APM and PM-intern programs. | **(b) for the banks,** and (c) only for JPMorgan and Citi if you want them. **Visa's and Mastercard's early-career sites in `product_design/`.** No shared/ source | 7.6–7.7 |
| **D32** | **P&D postings at health/ sources** (903 stored, mostly pharma PMs and medtech designers), which a P&D-only profile never polls. Adding Product and Design to health/'s audience changes no other board's polling. But health/ would no longer be Healthcare-only, and the manifest, the folder test and the gate's exemption change with it. | **Leave them Healthcare's.** Open health/medtech to Design's industrial_design only if you want medtech designers there | 7.6 |
| **D33** | **The new packs and their minimums.** design_studios: 41 candidates (17 Canadian), at least 8 verified feeds, 3 of them Canadian. canadian_product_design: 34, at least 10. industrial_design: 34 (10 Canadian), at least 6, 2 of them Canadian. APM programs: 27, at least 5. Studios and industrial design are thin in postings: 77 strict industrial-design titles open across all stored data. | **Four packs with these minimums.** Widen the APM pack into `early_career_programs` (APM, RPM, and product and design internship and apprenticeship boards; Design names it too). Fold a pack that verifies below its minimum into the closest group; each employer keeps its type | 8.5 |
| **D34** | **Second sources at employers already polled:** Workday's early-career site (80 stored rows, all from lists), Amazon's design and non-tech PM categories (Amazon's four sources hold 736 P&D postings), Loblaw Digital & Ecommerce, Samsara's recruiting-programs board, and Walmart's and Nike's design and product families. 50 of 92 open APM-only postings reach Foothold only through lists. | **Add each one that verifies**, in `product_design/`, with the key the employer's stored postings already use. No existing source is edited. Drop Samsara's if it is retired | 8.4 |
| **D35** | **New readers** (Stop and ask: a new ATS adapter). TikTok (lifeattiktok.com: 1,469 stored rows, lists 1,424 and LinkedIn 45, the biggest list-only PM-student employer), Taleo Business Edition (BRP), Recruitee (lg2) and Greenhouse's EU host (frog). Not adapter questions: T-Mobile (71/67, ATS not identified) and Thinkingbox (its Lever board is readable). | **Ask in Phase 4 for TikTok and Taleo BE first**, then Recruitee. Skip Greenhouse EU: it would touch the reader of all 301 Greenhouse sources. Identify T-Mobile's ATS with one careers-page fetch in Phase 4 | 8.7 |
| **D36** | **robots.txt.** Five sources in groups P&D polls read paths robots.txt disallows: SAP, ServiceNow, Canva and Freshworks (SmartRecruiters API) and Intuit (Radancy). They hold 223 stored / 171 open P&D postings (1.2% of open P&D) and Finance postings (SAP 16, ServiceNow 58, Intuit 128). The same rule covers 12 SmartRecruiters and 16 of the 18 Radancy sources on every board. | **Change none of them in this work**, and decide the rule once across boards. No new SmartRecruiters or alias-Radancy source in the P&D packs. Blocked candidates go under "not added" | 11.3 |

### 14.5 Resume reading and skills (section 9)

D37 to D39 change shared reader code (Stop and ask), so each needs your yes, gets its own commit, and is proved with
`resume_record compare` (384 readings identical) and the stored resume. D40 and D41 record bugs, and D42 is data.

| # | Question | Recommendation | § |
|---|---|---|---|
| **D37** | **Degree reading.** 21 of 47 P&D degree lines are refused. BDes, BFA, MDes, MFA and MHCI, US "M.S. in", "MS," and "MA," set no level, and "M.S. in HCI" above a B.A. reads undergraduate. `_PROGRAM` reads "Interaction Design" as `teraction Design`, and 9 of 15 other boards' lines are wrong: 7 by the same "In" bug ("formation Technology"), 2 by hyphens. The patches change 0 of the existing recordings and leave the stored resume unchanged. | **Add the abbreviations case-sensitively,** only inside Education, without BID and MID, and without a bare line-start "MA,". **Fix `_PROGRAM`** in its own commit | 9.2 |
| **D38** | **Diplomas and certificates** (8 lines, all refused: Advanced Diploma, Ontario college certificates, the Google UX certificate). A new level `other` reads them all. Settings already has "Other". It changes 0 recordings, and scoring gives `other` no graduate-degree penalty. | **Level `other`,** scored as today. Whether `other` should take undergraduate's penalties is a scoring change I'd leave | 9.2 |
| **D39** | **Headings.** Right after Education, "Design Experience" turns the jobs into education, so the UX fixture is refused in 6 of 6 forms. "Research Experience" leaves the UX researcher on Finance targets, and "Portfolio" reads Asset Management. Option 1 (HEAD2 in 9.3) adds Design, Relevant, Research, Product and UX Experience, Portfolio, Selected Work and Case Studies: 0 of 48 readings change. Option 2 (HEAD) also adds "Selected Projects" and "Design Projects": 6 of 48 change, all the CS fixture. | **Option 1** (without "Selected Projects" and "Design Projects"), and a headings parameter for the tests' `word_docx` | 9.3 |
| **D40** | **Finance's `options` skill matches any "options"** (labels are added to patterns): an industrial designer's only skill is `options`. A fix changes Finance postings' skill facts (not measured). | **Record it as a known bug now;** measure a narrower `options` before deciding | 9.5 |
| **D41** | **Reader limits and portfolio links.** Text boxes are read 3 to 4 times. A row-per-entry table and a row-by-row 2-column PDF are refused. "…lead\nProduct Designer." becomes a role. A portfolio link line can become an employer. No parsed field holds a portfolio link. Whether a project-only entry opens a track (9.4) is shared reader code too. | **Record them**: one text-box-and-sidebar fixture that must read as the single-column form, the rest recorded as `main` reads them. **No portfolio profile key**, and project entries open tracks as today (judgement) | 9.4, 9.7–9.8 |
| **D42** | **Skill groups.** P&D boards list Finance's tools group, so a P&D-only first run keeps Excel, Bloomberg and Capital IQ. | **Replace `tools` with the new P&D groups** on both boards (data only) | 9.5, 10.2 |

### 14.6 Views, copy and the release (sections 10 and 13)

| # | Question | Recommendation | § |
|---|---|---|---|
| **D43** | **Views that count Finance only.** Every profile's New today shows Finance's 112, but its link lists the profile's boards (Product 89, Design 31). Analytics shows Finance's 3,346 / 18,066 / 29,172 posted. Companies leaves out 19% of open Product and Design postings, Figma and Adobe among them. A: the profile's boards, the clause the Sources view uses. A′ for Companies: the profile's boards, and a profile with Finance keeps today's filter too. B: every board, which changes Finance. C: copy only. Software and Healthcare profiles get the same fix (Software's New today becomes 506). | **A for New today and Analytics, A′ for Companies.** Finance-only stays identical | 10.1 |
| **D44** | **Copy that is wrong for every board without Finance.** The first-run headline "2027 finance recruiting · Toronto & New York". The apply note, which doesn't say that types, stages and languages are replaced. "No finance skills detected" (1,373 open Product postings) and "— outside finance" in Why lines. "Entry level in finance" (58 Product, 78 Design stored entry postings). | **Fix all four.** The headline goes in `setupProfile`, not `DEFAULT_PROFILE`. The wording edits in `scoring.py` move no fit, so they record a new `RULES_CODE` hash under the current `RULES_VERSION` | 10.2, 5.3 |
| **D45** | **Capital One's pay sentence reads as part-time** on 1,953 open postings across every board, Finance included (251 Product, 44 Design). | **A separate change, outside this work** (it is a shared reader and needs `FACTS_VERSION`) | 5.1, 15 |
| **D46** | **One facts recompute.** The taxonomy, companies and skills edits change the fingerprint, so the first start after the release re-reads all ~410k stored postings once: about 1.5 h with `main`'s facts pool, the estimate in `plans/efficiency-review.md` (0.3.13 took about 7.4 h on one core, before the pool). Everything that postings read lands in one release. | **Accept it, and let me run a first start on a DB copy on E: in Phase 6** (about 1.5 h, with a resume applied and a poll during the re-read) and report the measured time | 13 |

### 14.7 Approved on 2026-11-07

You approved every decision as recommended ("Approve all"). This is what that allows.

**Moves the placement check allows** (`--allow <from>:<to>` in Phase 3 and later). The counts are the design's open
counts. They come from variants that were not simulated together, so Phase 3 recounts them with every decision in.
A move outside these pairs, or a pair whose count comes out well above the design's, comes back to you before the
commit.

| Allow | Decisions | Design's count (open) |
|---|---|---|
| `other:product` | D1, D2 (B1's claim), D4 | 731 (P7), less what the exclusions drop |
| `operations:product` | D1, D4 | 173 (P7), the 123 product ops among them |
| `finance:product` | D1, D6 | 244 (P7 without product strategy, with V3), plus 5 PMT titles and 1 product builder |
| `software:product` | D1, D3 | 689 (P7), plus up to 420 through the program claim |
| `data_ml:product` | D3 | 81, plus up to 40 |
| `hardware:product` | D3 | 46, plus up to 130 |
| `sales:product` | D1, D4 | 48, less the 29 heads and directors the exclusions drop |
| `design:product` | D1, D4 | 14, less 6 heads and directors |
| `people_legal:product` | D1 | 7, less 2 |
| `product:operations` | D2, D5 | 1,413 (B1), and 10 executive assistants |
| `product:sales` | D2, D5 | 76, and 1 (JFrog's assistant) |
| `product:design` | D2 | 36 |
| `product:healthcare` | D5 | 7 clinical program managers, through a Healthcare claim |
| `product:hardware` | D8 | 1 |
| `other:operations` | D2 | 416 |
| `finance:operations` | D2 | 39 |
| `software:operations` | D2 | 14 |
| `design:hardware` | D8 | 1,747 |
| `design:other` | D8, D10, D11 | 877, less the 94 game designers D12 keeps |
| `design:software` | D8, D10, D11 | 672 |
| `design:sales` | D8, D10 | 62 |
| `design:operations` | D8, D10, D11 | 42, less 1 game designer |
| `design:healthcare` | D8, D11 | 24, the 3 arts therapists among them |
| `design:people_legal` | D8, D11 | 12, the 8 recruiters among them |
| `software:hardware` | D8 | 14 |
| `other:design` | D13, D14 | 35 (46, less the 9 game-studio art directors and the 2 wrong titles) |
| `software:design` | D13 | 31 |
| `finance:design` | D6, D13 | 20 (D13's 12 among them) |
| `healthcare:design` | D13 | 1 |
| `sales:design` | D13 | 1 |

**Not allowed:**
- `design:finance` (D9 keeps the 44 on Design), and S&P's Finance filter change (D9's `index design`). No Finance
  posting changes filter.
- `hardware:design` (D13 approves no Hardware move) and `healthcare:product` (D1's exclusions drop both; D15).
- Filter changes on any other board (D27's 8 entries make none).
- D5's two other titles, a hospital pharmacy coordinator and a Fidelity paralegal: no decision covers them, so they
  stay on Product as on `main`.

**Other changes allowed:**
- Stages and labels on Product and Design (D17 to D22), with D17's optional rule for the 6 "Senior … Development
  Program Manager" titles. No stage change on another board.
- The label changes of D27's 8 entries: 1,674 stored postings typed (Finance 88, "other" 364, Product 108, Design 60).
- What profiles poll: only product, design, product+design, finance+product, software+product and software+design
  change (D28 to D30). Every other profile keeps its list and both hashes.
- Other boards' data: Operations' title words take plain program managers (D2), Hardware gets title words and a
  claim (D8), and Healthcare gets a claim for clinical program managers (D5). Each is named in its commit.
- Code: `intel/programs.py` shows each window key once (D23); the degree and `_PROGRAM` fixes (D37), level `other`
  (D38) and the headings (D39), each in its own commit, proved with `resume_record compare`; the views (D43); the
  copy (D44), under the current `RULES_VERSION`. One facts recompute (D46), measured on a DB copy in Phase 6.

**Still asked before it is done:**
- D5: a family-level `unless` in `family_of`, if the assistant exclusion needs one. I show it first.
- D8: the remainder that still goes to Software once Hardware's words are widened, and the 15 side moves.
- D18: the MBA rule is taken only if it works as a `summer_associate`-keyed level with its full-time guard.
- D24: each further type that should share the track. D27: each entry beyond the 8.
- D31's (c) for JPMorgan and Citi, and D32's medtech option, only if you ask.
- D35: each new adapter, in Phase 4. D40: a narrower `options` skill, once measured. D45 stays outside this work.
- Everything else on the brief's "Stop and ask before" list.

**Added on 2026-11-07, from Phase 3's Product and Design slices** (your answers; open postings, from the slices'
simulations):
- `product:software` 1: Apple's "Program Manager, Quality Data & Testing Lead, BPR: Supply Chain", which Software's
  QA claim takes once D2 sends it off Product.
- D2's tech subjects gain "technology" (JPMorgan's "Lead Technology Program Manager" stays on Product). With it,
  `product:operations` is about 1,523, above the design's 1,423, because the tighter list was never simulated.
- D8: `design:hardware` up to 2,212 (the widened Hardware words), and the remainder `design:software` 192 stays on
  Software. Typing those employers is D27's "one at a time", later.
- `design:product` 6: program managers that sit on Design today through bare "design".
- `software:design` up to 35 and `design:operations` up to 45, a few above the design's 31 and 41.

**Added on 2026-11-08, from the placement check of slices A to C** (your answers; open postings, counted on the
sample against `main` 937bbc2):
- `data_ml:design` 1: ServiceNow's "Sr. Staff Product Designer, AI/ML" (closed, so 0 open). D13's designer claim
  takes it; Phase 1 found no designer on AI & Data, so the pair was never listed.
- Pairs a little above the counts above, allowed as measured: `product:operations` 1,533, `other:operations` 435,
  `finance:operations` 40, `other:design` 38, `software:design` 36 and `software:operations` 15.
- Stages off Product and Design: the 6 JPMorgan "Program Management Associate" postings D2 sends from Finance to
  Operations (`finance:operations`) go from Experienced, a bank rank on Finance, to Entry there. These 6 are the only
  stage changes off the two boards. About 30 "Development Program Manager" and "Internship/Early Career Program
  Manager" titles D2 sends from Product to Operations keep `main`'s misreads there. Both are left to Operations
  (section 15.1).

**Added on 2026-11-08, from slice D (D24, D25, D42)** (your answers):
- Code: `intel/taxonomy.py` `_claim` lets a claim on the P&D track take tech work from "other", as a tech board's
  claim does. Only Product's and Design's claims are affected. Without it, 5 stored GM and Ford vehicle interior
  designers fall from Design to "other".
- Shared resume reader: a resume that opens the P&D track also reads tech-track skills, as P&D postings do (a
  track's `resume.skills_also`). Only P&D resumes change; the 384 recorded readings don't.
- Fit: a finance+product profile scores Finance postings at the 16 tech types the P&D track doesn't share 4 company
  points instead of 7, as a Finance-only profile does: 3,354 stored (2,977 open). Placement is unchanged.

**Added on 2026-11-08, in Phase 4** (your answers):
- Lever: every request waits its turn, a second after the one before, as api.lever.co's robots.txt asks
  (`628e3e7`).
- The folder test's exceptions: Visa's and Mastercard's early-career boards (`visa_early_careers`,
  `mastercard_campus`) sit in `product_design/` though both employers are `fintech`, a type off the P&D track.
- A Workday entry (`enterprise_saas`, `=workday`), so its early-career site joins `early_career_programs` (D27).
- From the sweep (D27): OpenSesame and Clearwater Analytics (`enterprise_saas`, in `product_design/`; Clearwater
  there, not in `shared/`), and T-Mobile (`telecom`, a folder-test exception beside Visa and Mastercard).
- Poll time: Product and Design keep `defense_aerospace` and `semiconductors` (D28), with the Eightfold sources
  that make their full poll about an hour, as Software's is.

---

### 14.8 The rule review, 2026-11-08 (your request: "a huge review on all the rules we set in place")

Nine reviewers read every placed open posting (73,917, placement `phase4\place\placed_p4n.db` after the chip
designers' commit) in nine slices: Product in five (product_management and technical_pm in halves, the other
filters with Product's rules), Design whole with its rules, and three slices of other boards' postings whose titles
name a product, design or program word (Software, AI & Data, Healthcare, Finance and People & Legal; Operations,
Sales and "other"; Hardware). Each counted its patterns from the data and checked the cause by running the
classifier; I re-ran the headline cases (24 probes) and each reproduced. Reports: `phase4\review\reports\`.
Counts are open postings, from a slice unless they say board-wide; each fix is recounted by the placement check
before its commit, and a count well above the one here comes back to you. **Bold** marks a fix that changes what
Finance shows (a posting onto or off Finance or "other").

What holds: Product's own PM and TPM words, `pm_over_topic`, and Design's product, UX, visual, content, research
and game words place their titles well; D2, D8, D10 and D11 hold; nothing claimable is left on Finance. What
doesn't: two program claims take non-technical program managers, Product's level words let common forms fall to
the shared rules (which read "Manager" as Senior), the filters miss word orders ("Product Manager - Technical",
"Designer, Brand"), and Design's generic words still pull in engineering, building and business titles.

#### Product: board

| # | Finding | Fix (recommended) |
|---|---|---|
| R1 | `program_tech_evidence` and `program_over_topic` take non-technical program managers into Technical PM: supply chain, logistics, procurement, GTM, channel, marketing, HR, finance, legal, EHS, data-center construction and facilities. About 245 (178 in the first half, 67 in the second). `program_tech_evidence`'s 3 description phrases ("cloud", "infrastructure", "jira") are met by almost any program manager at a tech employer (106 of its 233 in the second half got in on the description alone), and its title subjects ("data center", "network", "technology") and `program_over_topic`'s ("Cloud", "Hardware") name the employer's org, not the work | An `unless` of non-technical program words on both claims, guarded so a title that says technical stays (a trial on `program_tech_evidence` alone moved 127 board-wide, all to Operations); and an Operations claim from Software, Hardware and AI & Data for supply-chain, logistics, procurement and facilities program titles, so they don't fall back to Software. Not Finance |
| R2 | The `unless` word "developers?" in `pm_over_topic` and `program_over_topic` blocks "Developer Experience / Platform / Tools / Velocity": 64 PMs and TPMs stay on Software | Fire it only at the end of a segment (simulated: 64 Software → Product, 62 to Technical PM; Citi's "Product Manager/Developer" stays). Not Finance |
| R3 | Product titles no word or claim reads: product line managers (board-wide 58: "other" 47, Hardware 4, Finance 1), "Product Director", "Director, Product", "Manager, Digital Product", "Member of Product Staff" ("other" about 50, Software 6, Finance 19), "Product Mgr / Mgmt", typos and "Product Feature Owner" ("other" about 50, Finance 4 to 10), "Product and Program/Initiative Management" (13), "Programme" (5), HW / SW / chipset TPMs and "Prog Mgr" (11), "Product Associate" (7), product ops, associate and builder over a tech topic (10) | **Claims from "other", Sales, Operations and the tech boards** (and `pm_over_topic` for the topic ones), not Product title words, so Finance keeps its 25 to 30 such titles: about 190 leave **"other"** |
| R4 | Titles on Product that aren't product work: pharma and medtech brand, field and downstream marketing "Product Manager" (about 45), drug-development product leads (CMC, labeling, LCM: about 16), Anduril's "Product Operations" field deployment (17), NPI and manufacturing product operations (13), non-PM jobs that name the PM team (7: an administrative business partner, an HR manager, engineers), design program managers (3) | A Healthcare claim for the pharma marketing and drug-development titles (as "Brand Manager, Oncology" at a pharma employer is Healthcare's today); an Operations claim for Anduril's and NPI product operations; exclusions for the rest. Not Finance |
| R5 | `product_occupation_from_finance` misfires both ways: it takes Amex's "Total Rewards Product Associate", BofA's "Product Associate - Business Finance Control" and 3 BofA "Treasury Product Associate" (5), and misses Visa's "Technical Product/Project Management Intern" (4), which D31 names as Product's | **Send the 5 back to Finance** (where `main` has them) and **take Visa's 4**. Leave Vanta's "Director of Product, Governance & Compliance" and GSK's compliance product analyst on Finance |

#### Product: filters

| # | Finding | Fix (recommended) |
|---|---|---|
| R6 | Technical PM misses the qualifier after the title: "Product Manager - Technical / Tech / (PMT)" (board-wide 279, Amazon and Mastercard; identical Amazon titles split by team name), "Technical Product Owner" (62) and Cisco's and Flex's "Engineering Product Manager" (37) | Add all three to Technical PM |
| R7 | APM & Programs misses student roles not titled "product manager": owner, builder and coordinator interns, Graduate, Trainee, Junior, alternance, early career, French "stage" (about 92, mostly in Product Management); it holds "Senior Associate Product Manager", a PM band (8); TPM interns sit in Technical PM (50) | Widen it (anchored, so it wins wherever the word sits), drop "Senior Associate", and put TPM interns in APM & Programs (D16 calls it "PM internships") |
| R8 | Smaller: business "network" words put PMs in Technical PM ("Media Network", "Payment Network": 13); two overlapping Product Management words score one title twice and beat Technical PM's topic word (14); enterprise-app product analysts (Workday, Salesforce: 15) sit in Product Analytics; PMs of product operations (3) | Exclusions in Product's filter words (not the shared scoring, which every board uses); the analysts to Product Management |

#### Product: stages (Product's own stage rules, so no other board's or Finance's stage changes)

| # | Finding | Fix (recommended) |
|---|---|---|
| R9 | Forms that slip past Product's level words fall to the shared rules, where "manager" reads Senior and "Assistant Vice President" reads VP: "Manager, Product Management" and "Product Management Manager" (139 in one half), "Product Operations Manager" (32), a bare Product Owner (54 read Senior by years) and "Product Owner I" (14), "Assistant Vice President" (about 45; "AVP" reads Experienced), "Associate" not next to the occupation and the bank band's trailing "Associate" (about 50), "Group" as a team name (19), numbered levels ("Manager 4/5/6", "V (E5)": 65 read Experienced while III and IV read Senior), and singles ("summer" starts, "Dir", "CVP", "Principle", "Snr", "Manager-in-Training", "Jr", "Working Student") | Product levels for each, read as D17 reads a bare PM (Experienced), with "Product Owner I" Entry, AVP Experienced, numbered 3 and up Senior (as III), JPMorgan's "Senior Product Associate" Experienced (D19's band), and the "group" exclusion narrowed to "Group Product Manager" |

#### Every board: shared stage words (`intel/seniority.py`, shared code)

| # | Finding | Fix (recommended) |
|---|---|---|
| R10 | The shared rules miss the plural "Internships" (53 board-wide, none on Finance), "New College Grad" and "NCG" (13 Product, 24 Hardware, about 9 elsewhere, none on Finance) and TI's "Career Accelerator Program" (10), and read "Development Program Manager" as a new-grad program (22 on Operations, Regeneron's oncology directors among them). "Working Student", "Engineering Student" and "Stage Ingénieur" read Experienced, and 3 Finance postings carry them | Fix the first four in the shared rules (stage only, on every board; no Finance posting carries them); put the student words in Product's and Design's own levels only, so Finance's 3 keep their stage |

#### Design: board

| # | Finding | Fix (recommended) |
|---|---|---|
| R11 | Engineering designers and engineering design leads and interns on Design: "Electronics Designer", "Controls Systems Designer", "Tool Designer", "HVAC Designer", "F135 Compressor Design Intern", Eli Lilly's 8 "Engineer - Design Lead", Apple's "iPhone Product Design Lab Manager" | Extend `hardware_designer`'s subjects (controls, HVAC, electronics, tooling, molds, fixtures, propulsion, compressors, test stands and others; simulated: 84 Design → Hardware, no false moves). D11's plain "Designer" at engineering employers stays. Not Finance |
| R12 | Building design on Design: data-center design managers, architectural designers, store, workplace and lounge design (64), and the construction and facilities design managers at Intel and Micron (about 4) | **Release them to "other"** (about 68) until the AEC board takes them |
| R13 | Business design on Design through Design's own words: study, policy, compensation, contract, process and plan design (38) | **Release them** (to "other"). The 44 non-design titles `design_words_from_finance` keeps stay, as D9 decided, so Finance stays identical; most sit in no filter |
| R14 | Other non-design titles on Design: Target's apparel and home designers (13, against Nike's precedent), assistants, a sourcer and lecturers (9), engineers `design_occupation` takes (4: "UI/UX Lead Software Engineer", "Robot Interaction Engineer"), and Magna's engineers through its `canadian_tech` type (6) | **Target's to "other"**, the 9 to their boards, the 4 to Software and Hardware; retype Magna (an existing entry, so your yes: 6 → Hardware, its 35 Finance postings unchanged) |
| R15 | Design work held elsewhere: "Product Researcher" and Apple's and Figma's researchers (10, "other"), "Industrial Design Engineer" (8, "other"), "DesignOps" (the pattern `design ops` needs a separator, so it never matches), "Illustration", "Human Centered Design" and "Role, Team Design" (10, "other"), game designers and "UX ... Designer" on Software (6), UX roles that name hardware on Hardware (4), design engineers at software employers with a design department (about 5), SoFi's art director on AI & Data (1) | Add the words and claims; **about 28 leave "other"** |
| R16 | Employers with no entry, so no employer type: ServiceNow, Netflix, Pinterest, Linear, Baseten and Samsara (their designers stay on Software and Finance), Intel and Skyworks (their chip designers) | Run the entries check for these 8 and bring each to you with its counts (D27) |

#### Design: filters and stages

| # | Finding | Fix (recommended) |
|---|---|---|
| R17 | Game-studio systems, technical and gameplay designers in no filter (47) and game-studio design directors in Product & UX Design (10); "Designer, Brand / Motion / Advertising", production and presentation designers in no filter (43); vehicle-studio and consumer-goods designers outside Industrial Design (30); UX research and CMF word orders (12); EA's 7 "Quality Designers" are game QA | A gaming employer prior for Game Design, reversed-order Visual words (guarded so "Senior Product Designer, Marketing Tools" stays), industrial words, the research and CMF orders; EA's QA designers to Software's QA. Bare "Lead Designer" at software employers (21) needs a code default: later |
| R18 | Stages: "Senior Associate, Art Director" reads Senior (D19's band inverted: 2), HNTB's "Returning New Grad ... (for interns ONLY)" reads Intern (5), "Jr.", "Assoc" and "Ausbildung" read nothing (4) | Design levels for each |

#### Hardware (found by the review; Hardware's data, touched by this work)

| # | Finding | Fix (recommended) |
|---|---|---|
| R19 | 465 chip and board designers that came from Design sit in no Hardware filter: the filter words say "design" and "engineer", not "designer", and lack IC, memory, layout, mask, RFIC and PCB-designer words | Add them to Chip Design and Electrical. Any posting Hardware held on `main` that changes filter comes back to you before the commit |
| R20 | `engineering_design` takes non-hardware titles (7: an administrative business partner, an instructional systems designer, an interior design architect, solution designers) | Exclusions; they go back to Software. Not Finance |
| R21 | Outside this work, reported only: Hardware has no level words ("Engineer I" reads Experienced: 89), "Design Control Engineer" lands in Robotics (4), Leidos's 3 "Mobile Radar Mechanical Designer" sit on Software, and Hardware's topic words place business roles on Hardware (product marketing, Stryker's robotics product specialists, recruiters) | A separate change |

**Order of work, if approved:** one commit per group, each with the placement check, both suites and a reviewer:
first what changes no Finance view (R1, R2, R4, R6 to R9, R11, R17 to R20, and the parts of R3 and R15 that come
from tech boards), then the bold ones (R3, R5, R12 to R15), then the shared stage words (R10, shared code), and the
entries one at a time (R16).

## 15. Problems noticed, not fixed

These are on `main`, found while gathering this design's counts. The first group is shared behaviour that this
design fixes only on Product and Design, through board data, because the brief says to leave the shared rules
alone. Every other board keeps it. The rest is left as it is in this work. Each item names its evidence.

### 15.1 Shared rules this design works around on Product and Design only

- **`senior_ic` reads the occupation word "manager" as Senior.** It runs before `associate`, `analyst` and `mid_ic`,
  so "Associate Product Manager" and "Product Manager II" read Senior. On Product, 4,206 of 7,538 stored `senior_ic`
  levels are set by "manager" (`phase1\data\finance_seniority_levels.jsonl`). Fixed for P&D by D17 to D19; Sales,
  Operations and People & Legal titles with "manager" keep it.
- **`rotational` reads "Development Program Manager" as Rotational Analyst / new_grad**: 18 stored Product titles
  (Lockheed Martin, Flex). D17 fixes 12; 6 with a senior word stay.
- **"associate intern" reads Summer Associate and sets `post_mba`** (a 15-point penalty for an undergraduate):
  "Design Associate Intern" and "Product Associate Intern", title only (`finance_seniority_examples_after.txt`).
- **The "dated program in title" new-grad rule never fires once a level word matched**, so "[2027] Associate
  Product Manager" reads Senior.
- **French and German intern words** (stage, stagiaire, alternance, Werkstudent) are not read: 22/20 stored P&D
  titles (Ubisoft, Novartis).
- **Finance-shaped labels.** Principal reads "Vice President", Director "Executive Director", and Head of or Chief
  "Managing Director". A team name "COO" sets Managing Director (5 stored Product), and `_TEAM_NAME` doesn't strip
  "Office of the CPO".
- **Level words that name a team** ("Early Career Program Manager", "Internship Program Manager") are read as the
  posting's level. A real campus hire, "Campus - Full Time - Product Manager", reads Senior (D20).
- **Program managers D2 sends to Operations are read with Operations' levels**, which D17 to D20 don't change. On the
  sample, 6 JPMorgan "Program Management Associate" postings that leave Finance go from Experienced to Entry, and
  about 30 "Development Program Manager" and "Internship/Early Career Program Manager" titles that leave Product keep
  the misreads above (Rotational Analyst, Intern, New Grad) (`E:\product-design-board\phase3\main_vs_abc.txt`). You
  chose to leave them to Operations on 2026-11-08.
- **Plural titles land in "other"**, which Finance reviews, on every board whose words have no plural:
  "Product Managers" (Microsoft ×3), "Senior Program Managers" (Intel), "Senior Product Designers" (FIS). Title only:
  "Motion Designers", "Graphic Designers", "Product Analysts", and the brief's "Recruiters", "Paralegals" and "Account
  Executives".
- **`_TECH_OCCUPATION` names only product manager/coordinator and designer.** So Finance words take program-manager,
  TPM, product-owner, product-analyst and UX-researcher titles: "Technical Program Manager, Payments Risk" reads Risk,
  "UX Researcher, Wealth Management" Wealth, and "UX Researcher, Quantitative" Quant (D6).
- **Tech boards' topic words take PM and designer titles,** because those boards are checked first ("Product Manager,
  API Platform" reads Software · Backend; "Mobile Product Designer" Software · Mobile) (D3, D13).
- **Product's words hold non-product titles**: 11 executive assistants, 7 clinical program managers (which
  `_BUSINESS_OCCUPATION` keeps out of Healthcare's `sole_occupation` claim), a hospital pharmacy coordinator and a
  paralegal (D5). Plain program managers in defense, facilities and supply chain (D2).
- **The Design board is two-thirds non-design** (1,807 of 5,546 design, judgement): chip and mechanical "Design
  Engineer" titles, UI programmers, marketing creative roles, instructional designers, recruiters and 3 arts
  therapists (D8 to D11).

### 15.2 Placement and sources

- **Capital One's pay sentence reads as part-time.** "Salaries for part-time roles will be prorated…" marks 1,953 open
  Capital One postings `part_time` on every board, Finance included (`career_research_inline.out.txt`) (D45).
- **Capital One's "MBA Product Intern - Summer 2027" is on Finance,** not Product (`career_research_programs.out.txt`).
  D6's claim doesn't take it; D18's MBA rule would read it only once it is on Product.
- **Finance holds 3 titles with "design" that are neither finance nor design work** (judgement): NXP's chip-design
  title under Accounting, and Inceptive's and Roche's science titles under Risk (`plan\scratch\s4b_verify10.out.txt`).
  Changing them would change Finance.
- **Pack headings type postings in a dev run but not in the installed app.** `_SECTION_TYPES` reads the old
  `startups_fintech_consumer` heading as `fintech` (15 sources) and `qube_rt` as `quant_firm`, but installs carry no
  `_` keys (`tools/build_windows.py` `clean_config`). So a dev run places these employers' postings differently from
  an install.
- **Autodesk lists 3 open postings of 490 stored after a read marked complete** (`source_coverage:autodesk`: fetched 3,
  reported_total 3, complete; 177 closed on 2026-10-31 and 121 on 2026-10-22). Either the Workday site lists 3 now,
  or a short read was taken as complete and closed live postings. The site wasn't fetched. P&D (48 stored) and
  Finance (30) rely on it.
- **Retool is disabled for a reason that no longer holds.** Its note says the watcher has no Gem adapter, but
  `watcher.py` now has one (`fetch_gem`), which `freshbooks` uses. Enabling it edits a shared/ source Finance
  polls, so it needs your yes; it has 0 stored postings.
- **One employer, two company keys.** List postings for CACI resolve to `caci` and its own source to
  `caci_international`. Workday's list postings resolve to `workday` and `workday_hq`'s own postings to `workday_hq`.
  This can split clusters and Companies rows (judgement).
- **Salesforce's 2 open APM postings are stored only from lists.** Neither `salesforce` nor `salesforce_early` holds
  them. One `watcher.py --list` in Phase 4 would tell why.
- **Two plans say postings from sources a profile stops polling are never deleted:** `plans/healthcare-board.md`
  (~528) and `plans/cs-tech-sources.md` (~225). `prune()` (`watcher.py` ~4369) deletes them 90 days after their last
  poll unless they have an application. Section 7.8 states what happens. The two plans aren't edited here.

### 15.3 Views and copy

- **New today's card counts Finance** ("112 finance roles") for every profile, while its link opens the profile's
  boards. Analytics shows Finance's numbers and a "Finance" column to every profile (D43).
- **The Companies view says "banks, funds and finance employers"** but counts whole companies at any typed employer
  (Amazon 7,460), and leaves out untyped employers' other postings: 23% of open Software, 19% of Product and Design
  (D43).
- **Every first run without Finance keeps the finance headline** and, on boards whose skill groups include `tools`,
  Excel, Bloomberg and Capital IQ (from reading `web/js/views/welcome.js`; not checked in a browser) (D42, D44).
- **Why lines say "finance" to profiles without Finance**: "No finance skills detected" on 5,272 open Software
  postings, and "Big Tech — outside finance" for a Healthcare profile (D44).
- **The resume apply note leaves out** that applying replaces employer types, career stages and languages (D44).
- **"Entry level in finance"** on 58 Product and 78 Design stored entry postings, and the same text on every other
  non-finance board's shared entry levels (D44).

### 15.4 Resume reader

- **`_PROGRAM` eats the "In" of Interaction, Industrial, Information, International, Interior and Integrated**, and
  stops at hyphens. "Bachelor of Information Technology" reads `formation Technology` (D37).
- **US "M.S. in", "MS," and "MA," set no level**, and "M.S. in" above a B.A. reads undergraduate (D37).
- **Unknown headings right after Education turn jobs into education.** "Selected Work" and "Case Studies" become
  employers after an Experience entry (D39).
- **"Portfolio" under Education reads as Asset Management** through the finance signal `portfolios?\b` (D39 fixes
  the heading, not a "Portfolio: <link>" line).
- **Finance's `options` skill matches any "options"**, because each skill's label is added to its pattern (D40).
- **The CS fixture's `.docx` forms read 2 role interests where its text, PDF and LaTeX forms read 4**
  (`resume_degrees_main_record.json`).
- **Word text boxes are read 3 to 4 times**, not twice as the brief's list says, and experience in a text box doubles
  every role (D41).
- **A row-per-entry table and a row-by-row 2-column PDF are refused** (D41).
- **A line between a role's duties and a second title at the same employer becomes that entry's employer**: a
  portfolio link on a design resume, and a duty line in the existing finance fixture.
- **A wrapped bullet ending "…lead\nProduct Designer." becomes a role**, since `_goes_on` joins only lower-case
  run-ons.
- **The test helper `word_docx` lists employers as duties under headings it doesn't know**
  (`tests/resume/test_resume_health.py:123`).
- **The pharmacy fixture is refused in all 48 readings** (PharmD sets no level), as section 2.6 records.

### 15.5 The board gate's existing code

- **`_ro` builds its `file:` URI without percent-encoding,** so a path with `#` or `?` opens the wrong file or fails.
  `snapshot`, `compare` and the new `place` all open copies through it. No path in this work has those characters.
- **`snapshot` leaves workers running when one fails.** `any(p.wait() for p in procs)` stops at the first failure,
  and the other workers keep writing. The new `place` waits for every worker, and stops the rest when one fails. I
  left `snapshot` as it was, since it works for the runs it is used for.

---

## 16. Copies on E:

Everything is in `E:\product-design-board\` (4.7 GB). Nothing here is needed by the app. I delete nothing on E:
without your yes.

| Path | Size | What it is |
|---|---|---|
| `live_copy.db` | 4.1 GB | The DB copy (section 2.1), taken through `mode=ro` and the backup API, then migrated by `main`'s `db_migrations` (a no-op at schema 8). Every placement and census reads it. |
| `installed-config\config.json` | 260 KB | A copy of the installed `config.json`, in a folder of its own, away from the DB copy |
| `code-main\` | 6.3 MB | `git archive 598b525`: `main` as the placement check and the recorder run it |
| `baseline\` | 86 MB | Section 2's baselines: `ids.json` (the sample), `placed_main.db`, `placed_stored.db`, `stored_vs_main.txt/.json`, `polled_main_bundle.json`, `polled_main_installed.json`, `resumes_main.json`, `resumes_worktree_check.json`, `resumes_compare.txt`. `superseded\` (39 MB) holds the first run's files, taken before the review fixes |
| `census\census.db` | 246 MB | Table `p`: every titled posting's stored placement, level and description length, read from the copy; the census and the reports count from it |
| `exp-entries\` | 62 MB | The entries experiment (section 6.6): `code\` (`main` plus 64 entries), `entries.json`, `ids.json`, both placements, `compare.txt`, `changes.json`, `breakdown.txt`; `superseded\` (27 MB) is its first run |
| `phase1\` | 100 MB | The nine research reports (`*.md`), their scripts and outputs (`scripts\`, `data\`, `census_design\`, `sim\`, `robots\`), `summaries.json`, and this design's section drafts (`plan\`) |
| `scripts\` | 49 KB | The copy, census and baseline scripts, among them `copy_db.py`, `check_copy.py`, `build_census.py`, `candidate_titles.json` and `rerun_baselines.sh` |
| `review\` | 58 MB | The tool review's probes, and the diff the simplify pass read |
| `baseline_py_tests.txt`, `baseline_js_tests.txt`, `phase1_*_tests*.txt` | < 100 KB | Test-suite output before any edit and with the Phase 1 tools (section 2.3) |
| `phase1_tools.diff` | 52 KB | The tools diff as first reviewed |
