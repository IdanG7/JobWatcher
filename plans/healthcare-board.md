# Healthcare & Science board: design (Phase 1)

Status: **approved** on 2026-10-27, D1–D12 as recommended and then D13–D16 (section 3.4) as recommended.
Phases 2 and 3 are done (section 11). Branch `feat/healthcare-board`, worktree
`.claude/worktrees/healthcare-board`. It was created from `main` at `9c6724b` (v0.3.11). It was then
fast-forwarded to `main` at `6c7112c`, because the three description fixes landed on `main` during this
session. The brief is `plans/board-expansion-prompt.md` in the main checkout: Part A, Part B §1 and the
lessons in Part C. This repeats the tech work in `plans/cs-tech-sources.md` (commits `04ff8fd`..`c71d603`).

This is the first of five boards, so it also makes the board machinery board-agnostic (section 9). After
this work, Product & Design, Sales & Growth, Operations and People & Legal should need only data and tests.

## Terms

| Your word | Meaning | In the code |
|---|---|---|
| **Board** | A field picked in onboarding: Finance, Software, Healthcare & Science… | `profile.fields`; `non_finance_families` in `config/taxonomy.json` |
| **Source** | One polled feed: a Workday site, a Greenhouse board, a LinkedIn search | an entry of `config["boards"]` |
| **Filter** | A subcategory inside a board: Healthcare · Clinical Research | a target role such as `healthcare.clinical_research` |
| **Pack** | A file of sources | `config/sources/<folder>/<group>.json` |
| **Track** (new) | Boards that share employer types, skills and resume vocabulary: tech = Software, AI & Data, Hardware, Product and Design | `"track"` on a board (section 9) |

---

## 1. The guarantee

A profile whose only board is Finance, Software, AI & Data, Hardware, Product or Design sees exactly what it
sees today:
- the same postings;
- the same fit and order;
- the same sources, with the same settings, at the same rate.

Sales, Operations and People & Legal show the same postings too. They still poll every source, so they also
poll the new Healthcare packs (section 6). Healthcare itself is the board being built.

**How the storage enforces it.** New sources go into a new folder, `health/`, which only Healthcare polls
(plus the boards that poll every source). Finance and the tech boards never poll `health/`. No existing source
moves or changes.

**How the classifier enforces it.** Healthcare gains new title words in a second tier. Those words only claim
a title that no board and no finance rule places today. Such titles sit in the family `other`, which no board
shows (section 3.2). Moving a posting off an existing board needs your yes: the moves are D1 and D2 in
section 12. The gate lists every such posting.

**How it's proven:** the baseline below, recorded before any edit, and the gate tool (section 2.4), run before
each commit that touches taxonomy, companies, skills, sources or scoring.

---

## 2. Baseline (recorded before any edit)

Everything here was read from files, from a command, or from a read-only copy of your database in this
session's scratchpad (`…\scratchpad\gate\install.db`). Nothing in `%LOCALAPPDATA%\Jobwatch` was written.

### 2.1 The install
- **Version:** 0.3.11 (`instance.json`), `sources_version` 10, DB schema 6.
- **Sources:** 795. They equal the bundle's sources key for key once cleaned by `clean_config`, with the
  packaged hash `99184ec16a625ce7`. That is `__shipped__` for `sources_version` 10.
- **Postings:** 294,571. All carry `FACTS_VERSION` 10 and the config fingerprint `fdc7124ccfed`, which is
  `main`'s, so the stored facts are this code's.
- **Your profile:** Software and Hardware. Targets: Hardware · Embedded & Firmware, Hardware · Robotics &
  Autonomy, Software · Infrastructure. Your resume is on.
- **The DB copy:** taken with SQLite's backup API from a read-only connection while the app ran. The newest
  posting in it was first seen at 2026-10-27 02:58 UTC.

### 2.2 Polled sources for each sample profile
A sample profile is what onboarding saves on a first run:
- the board, or the default finance areas when Finance is picked;
- for a board without Finance, no employer types and the default skills in that board's skill groups;
- "default" is a fresh install with no saved profile;
- "user" is your saved profile.

"Bundle hash" hashes the polled sources' settings as the packs list them. "Packaged hash" hashes them as an
install stores them (`clean_config`). Both use `tools/source_history.boards_hash`.

| Profile | Boards | Sources | By folder | Bundle hash | Packaged hash |
|---|---|---|---|---|---|
| default | finance | 347 | finance 38, shared 309 | `1a3363eaef933c0f` | `bc20951ee09def58` |
| finance | finance | 347 | finance 38, shared 309 | `1a3363eaef933c0f` | `bc20951ee09def58` |
| software | software | 713 | shared 300, tech 413 | `384408b2e846d59c` | `2d215bdd1a94fd29` |
| data_ml | data_ml | 524 | shared 236, tech 288 | `a94546615cd95e7e` | `6e4aaac107859b5f` |
| hardware | hardware | 191 | shared 97, tech 94 | `eddb558e9d2af4a4` | `54d5e4448e179f74` |
| product | product | 319 | shared 130, tech 189 | `307abf02da7972b4` | `5f3094df2d5d5f5e` |
| design | design | 319 | shared 130, tech 189 | `307abf02da7972b4` | `5f3094df2d5d5f5e` |
| sales | sales | 785 | finance 38, shared 309, tech 438 | `8710ae63df269b4f` | `1761150699fd46e6` |
| operations | operations | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| people_legal | people_legal | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| healthcare | healthcare | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| finance+healthcare | finance, healthcare | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| software+healthcare | software, healthcare | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| data_ml+healthcare | data_ml, healthcare | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| finance+software | finance, software | 760 | finance 38, shared 309, tech 413 | `0b6788b94cc8fbbf` | `f06c9b4e36cda9b7` |
| finance+sales | finance, sales | 785 | (every enabled source) | `8710ae63df269b4f` | `1761150699fd46e6` |
| user | software, hardware | 428 | shared 192, tech 236 | `7529d12c5da3adf9` | `1e44a2c768d38cf3` |

The GitHub Actions alert runner has no profile and polls all 785 enabled sources. 64 packs: 6 `finance/`,
31 `shared/`, 27 `tech/`. The description fixes on `main` don't touch sources or packs, so `9c6724b` and
`6c7112c` give the same lists. Saved as `…\scratchpad\gate\baseline_polled.json`, with every list in full.

### 2.3 Posting snapshot
Taken with the prototype of the gate tool (section 2.4), once with `main` (`6c7112c`) and once with 0.3.11
(`9c6724b`, the `v0.3.11` tag, which is what you run). Each used its own working copy of `install.db`.
- **Clock:** frozen at 1793070000 (2026-10-27 03:00 UTC), so posting age is the same in every run.
- **Facts:** each checkout's own `build_facts` in 10 worker processes (23 minutes), fed to its real
  `IntelStore.facts_pass`. Canonical rows were then re-picked everywhere.
- **Fit:** the real `score_pass` for each of the 17 sample profiles. Resume matching is on for all of them and
  reads your stored resume.
- **Board view:** what Opportunities lists by default for that profile. That is canonical, titled, not closed
  (posting status and window), not hidden, on the profile's boards, ordered by fit and then posting date.
  "Digest" hashes the whole ordered list: posting, fit, category, filter, cluster, company, type, fit detail,
  resume match, window, urgency and badges.

**`main` (`6c7112c`), the baseline every later gate compares against:**

| Profile | Postings | Fit ≥ 55 | Fit ≥ 75 | Resume matches | Digest |
|---|---|---|---|---|---|
| default | 27,471 | 511 | 0 | 21,174 | `fd9b2b1bce17caa8` |
| finance | 27,471 | 2,083 | 4 | 19,624 | `e18f44329a8eaa2c` |
| software | 62,739 | 45,586 | 971 | 51,860 | `b1d9cec662dffa69` |
| data_ml | 10,698 | 8,196 | 230 | 8,921 | `40131b3e07eec26c` |
| hardware | 12,939 | 9,571 | 116 | 11,635 | `cba0dcf15db792cf` |
| product | 6,822 | 5,299 | 123 | 5,956 | `e0cc0d380b79dd75` |
| design | 3,979 | 3,169 | 78 | 3,466 | `7abc6a7360c3298f` |
| sales | 16,216 | 9,988 | 160 | 12,286 | `bb92be2bfe75f3f3` |
| operations | 11,389 | 6,967 | 142 | 9,161 | `a3a72e4e58f661ee` |
| people_legal | 3,034 | 1,943 | 29 | 2,498 | `0e6391f478e0d494` |
| healthcare | 1,260 | 1,072 | 21 | 1,206 | `63d62589733e4aed` |
| finance+healthcare | 28,731 | 3,153 | 24 | 20,830 | `ee66af25e7be4f2b` |
| software+healthcare | 63,999 | 47,108 | 1,180 | 53,066 | `9e2325b045f121ff` |
| data_ml+healthcare | 11,958 | 9,376 | 327 | 10,127 | `1e249e8826b8bd4d` |
| finance+software | 90,210 | 47,055 | 880 | 71,484 | `398c5e662413f51b` |
| finance+sales | 43,687 | 12,029 | 155 | 31,910 | `34da6abcf7d82c7e` |
| user | 75,678 | 5,201 | 251 | 8,678 | `72e62457459b3255` |

**0.3.11 → `main`.** This is `main`'s own change, from before this work, and is recorded so it isn't blamed on
Healthcare later.
- **Facts:** identical for all 294,571 postings. So are the cluster keys, and each cluster still has exactly
  one canonical row.
- **Representative rows:** the schema-7 migration moves 16,586 community-list notes into `job_notes`, which
  leaves those list rows with an empty description. In 306 duplicate clusters the other copy of the same job
  now represents the cluster, mostly a `derec4_newgrad27` row in place of a `simplify_intern26` or
  `vansh_intern26` one.
- **Board views:** 0 to 231 rows swap per profile: 140 for Finance, 91 for Software, none for Design or
  People & Legal. Every posting listed on both sides keeps the same fit, detail and match. No cluster changes
  board.
- **Counts:** they move by at most 2, because the new row's status or window differs. Finance gains 1, and
  Healthcare loses 1 ("Medical Intelligence Co-op": the new row's window is closed).

**Runtime:** facts 23 minutes; the store's facts pass 53 minutes; scoring 100 to 190 seconds per profile;
about 2 hours per snapshot; `compare` 1.5 minutes. Outputs: `…\scratchpad\gate\snap_main.db`,
`snap_rel0311.db`, `cmp_main.txt`, `cmp_rel0311.txt`, `cmp_rel0311_main.txt`.

### 2.4 The gate becomes a tool (Phase 2)
The tech work's gate lived in a scratchpad and is gone. This one is committed as `tools/board_gate.py`, with
`tests/sources/test_board_gate.py`. The scratch scripts that took the baseline above are its prototype.
- **`snapshot --code <checkout> --db <copy> --config <config.json> --epoch <t> --out <file>`** runs one
  checkout's own code on its own working copy of the database:
  1. Copies the database and runs that checkout's `db_migrations.migrate`, as the app does when it opens.
  2. Freezes the clock: `time.time` and `datetime`/`date` in the app's modules, so posting age can't move fit.
  3. Computes facts in parallel worker processes with that checkout's `build_facts`. One process reads 23
     postings a second, so 294,571 postings take 3.5 hours; 10 workers take 23 minutes. Each run takes
     about 2 hours and needs about 5 GB free.
  4. Feeds those facts to the checkout's real `IntelStore.facts_pass`, then re-picks canonical rows
     everywhere. A check refuses facts computed with other source settings.
  5. Scores every sample profile with the real `score_pass`, resume matching included.
  6. Writes one row per posting (board, family, category, filter, Finance flag, company, type, cluster,
     canonical flag, status, hidden, facts hash) and one row per posting and profile (fit, urgency, window,
     badges, deadline, posted reference, hashes of the fit detail and the resume match).
- **`compare <old> <new>`** derives each profile's boards view the way Opportunities does: canonical,
  not closed, not hidden, the profile's boards, ordered by fit then posting date. It reports:
  - postings missing or added;
  - any changed fit, order, category, filter, cluster or canonical row;
  - any changed fit detail or resume match.

  It also counts what changed outside the profile's boards. Approved label changes (employer type from
  "Unclassified" to a new type, and the "Why" line naming it) are listed separately. Anything else exits
  non-zero.
- **Runs:** `main` (exported with `git archive`) against the branch, on the same copy and the same epoch.
  Profiles: the 17 above.
- **Test:** a small synthetic database. The same code gives an empty diff. A knowledge change that moves a
  posting gives a diff naming it. A label-only change is reported as a label change.

---

## 3. Filters

### 3.1 The nine filters
"Today" is where the current classifier puts each example title (title only, unknown employer). It was
checked by running `intel.taxonomy.classify` on `main`.

| Filter | Holds | Example titles | Today |
|---|---|---|---|
| `clinical_care` · Clinical Care | Nursing, allied health, pharmacy practice | Registered Nurse, Medical-Surgical · Pharmacy Intern · Physiotherapy Assistant (Summer Student) | Healthcare · other · other |
| `clinical_research` · Clinical Research | Trial coordinators, associates, clinical data, study start-up | Clinical Research Coordinator · Clinical Research Associate II · Clinical Trial Assistant (Co-op) | Healthcare · **Finance (Equity Research)** · Healthcare |
| `lab_research` · Lab Research | Research associates and technicians, lab scientists | Research Associate, Cell Biology · Laboratory Technician · Co-op Student, Analytical Chemistry | **Finance (Equity Research)** · other · other |
| `bioinformatics` · Bioinformatics & Biostatistics | Computational biology, genomics, biostatistics, statistical programming | Bioinformatics Scientist · Computational Biologist · Biostatistician | other · other · Healthcare |
| `regulatory_quality` · Regulatory & Quality | Regulatory affairs, GMP quality, pharmacovigilance, medical writing | Regulatory Affairs Co-op · Quality Assurance Specialist, GMP · Pharmacovigilance Associate | other · **Operations** · other |
| `medical_devices` · Medical Devices | Biomedical and device engineering, field clinical, applications | Biomedical Engineering Intern · R&D Engineer, Medical Devices · Field Clinical Engineer | Healthcare · Healthcare · Healthcare |
| `public_health` · Public Health | Epidemiology, health promotion, health policy, global health | Epidemiologist · Health Promotion Specialist · Health Policy Analyst | other · other · **People & Legal** |
| `health_admin` · Health Administration | Patient access, health information, clinic and hospital operations | Patient Access Representative · Health Information Management Co-op · Hospital Administration Intern | other · other · other |
| `medical_affairs` · Medical Affairs & Commercial | MSL, medical information, market access, HEOR, medical and pharma sales | Medical Science Liaison · Market Access Analyst · Pharmaceutical Sales Representative | Healthcare · other · Healthcare |

Each filter gets title, department and description patterns in the finance and tech style, a label, a note
and a `tie_priority`. More specific filters win ties: medical_devices and bioinformatics 5;
clinical_research and regulatory_quality 4; medical_affairs and public_health 3; lab_research and
health_admin 2; clinical_care 1.

Related filters earn the related-specialty credit (14 points), as Full-Stack does next to Backend:
- clinical_research ↔ regulatory_quality
- lab_research ↔ bioinformatics
- clinical_care ↔ health_admin

The evidence threshold is the shared `min_specialty_score` 3. A filter read from the description alone needs
4 distinct phrases and a lead of at least 2, as for the tech filters. Every filter gets classifier tests with
realistic titles, including the near-misses in 3.3.

### 3.2 How a title reaches Healthcare
Healthcare is checked first among the job families today, on five title words: clinical, medical, biomedical,
pharmaceutical, biostatistics. That is why "Software Engineer, Medical Imaging", "Data Scientist, Clinical
Analytics" and "Product Manager, Clinical Workflows" are on the Healthcare board today, not Software, AI &
Data or Product. Nothing about that changes.

1. **Tier 1, the board's `title` words:** today's five, checked first as today. The 1,481 stored Healthcare
   postings (1,260 of them open and listed on `main`) stay there. They gain filters.
2. **Tier 2, new `fallback_title` words:** for example nurse, pharmacist, pharmacy, physiotherapist,
   therapist, laboratory, biology, epidemiologist, public health, patient, hospital, regulatory affairs,
   pharmacovigilance, GMP, market access and scientist. They apply only after the finance decision and after
   every other board's title words and fallbacks, and only when the result is still `other`.
   - A Finance posting is decided exactly as today, so tier 2 never takes a role off Finance or any other
     board.
   - `fallback_title` is a generic mechanism. A later board can claim titles from `other` the same way
     without touching any board.
3. **Tier 3, cross-board rules you approve (D1, D2):** the few cases where today's placement is plainly
   wrong. Each is a named rule with tests. The gate lists every stored posting it moves.

**As built (Phase 3).** A title-only pass over your copy's 214,196 open postings showed that some tier 2 words
also name engineering, physics, banking or hardware work:
- "Regulatory Affairs" at JPMorgan, Moody's, Visa and Brex;
- national-lab postdocs in quantum devices and thin films;
- drone and semiconductor lab technicians;
- "AI Scientist" and "Security Scientist";
- "Health, Safety and Environment", "Industrial Hygienist" and "Radiological Control Technician".

So:
- **Tier 2 (`fallback_title`)** keeps only clinical occupations, life-science disciplines and health-service
  phrases: nurse, pharmacist, phlebotomist, microbiology, epidemiology, "patient access", "public health"….
  It never claims a title that names tech or business work: an engineer, developer, recruiter, marketer or
  analyst of data, AI, security or software.
- **Generic science words need life-science evidence:** laboratory, lab technician, scientist, chemist,
  postdoc, research associate or assistant, and regulatory affairs. These are named rules (`claims`):
  `life_science_research` and `life_science_regulatory`. The evidence is one of:
  - a life-science subject in the title ("Scientist I, Analytical Development");
  - a life-science employer type ("Laboratory Technician" at a diagnostics company);
  - three lab or clinical phrases in the description.

  Phase 4's employers carry those types, so their lab postings place themselves.
- **The cross-board rules** are `life_science_research` (D1, from Finance), plus `clinical_occupation`,
  `lab_quality` and `health_policy` (D2). Each posting they move carries its rule in `classification.rule`.

On your copy, 2,971 open postings in `other` carry a health word in the title. 2,282 of them are at UnitedHealth
Group, whose whole feed Healthcare already polls. Tier 2 brings them onto the Healthcare board, and no other
board loses anything.

### 3.3 Overlaps with other boards

| Overlap | Today | Proposed | Stored postings that move |
|---|---|---|---|
| bioinformatics ↔ AI & Data | "Data Scientist, Genomics" and "ML Scientist, Drug Discovery" are AI & Data | A data or ML occupation keeps AI & Data (tier 2 never overrides). "Bioinformatics Scientist" and "Computational Biologist" (`other` today) become Healthcare | 0 |
| medical_devices ↔ Hardware/Software | Titles with "medical"/"biomedical" are Healthcare already; "Design Quality Engineer" is Design | Unchanged | 0 |
| medical_affairs ↔ Sales | "Pharmaceutical/Clinical Sales Representative" is Healthcare; a plain "Sales Representative" at a pharma company is Sales | Unchanged | 0 |
| lab/clinical research ↔ Finance (Equity Research) | Finance's `research (analyst\|associate)` claims "Research Associate I", "Research Associate, Cell Biology" and "Clinical Research Associate II" | **D1:** a generic research title with life-science evidence becomes Healthcare. The evidence is a life-science subject in the title, a life-science employer type, or 3+ lab or clinical phrases and fewer than 2 finance phrases in the description | About 14 open Finance postings, all Equity Research but one: Wash U postdocs, Natera, AbbVie, Eurofins, BillionToOne. The gate gives the exact list |
| regulatory_quality ↔ Operations | Operations' "quality assurance/control" words claim "Quality Assurance Specialist, GMP" and "Quality Control Chemist" | **D2:** a quality title naming a life-science object (GMP, GxP, microbiology, chemist, laboratory, sterility, biologics…) becomes Healthcare | 4 Operations postings, for example "Quality Control Microbiologist" |
| clinical occupations ↔ Software/Product/Sales/Operations | "Pharmacy Technician Backend-PT" is Software · Backend; "Registered Nurse- AL Hospice Care Mobile" is Software · Mobile | **D2:** a clinical occupation in the title (nurse, pharmacist, pharmacy technician, physician, therapist, paramedic…) beats topic words | 7: Software 4, Product 1, Sales 1, Operations 1 |
| public_health ↔ People & Legal | People & Legal's "policy" claims "Health Policy Analyst" | **D2:** "health policy" and "public health policy" become Healthcare · Public Health; other policy titles stay | 0 on your copy |
| Finance stays | "Healthcare Investment Banking Analyst", "Actuarial Analyst, Health Insurance", "Biostatistician, Quantitative Epidemiology" (Quant), "Summer 2027 AHN Physician Org Undergraduate Finance Intern" | Unchanged: Finance is decided first | 0 |

The counts come from title scans of the stored facts in the DB copy (`…\scratchpad\gate\overlap.py`). Phase 3's
gate replaces them with the exact lists.

### 3.4 Career stages, hours and licences (proposed after Phase 1; D13–D16)
Healthcare careers don't follow the internship → new grad → analyst ladder. They have externships,
residencies, fellowships, rotations, shift patterns and on-call work, and most clinical jobs have no level
word at all, because the licence is the level.

**How the stored postings read today.** Measured on the `main` snapshot, over 5,556 open postings: Healthcare,
plus `other` postings with a health word in the title.
- **No level word.** 3,801 (68%) have none, so they become "Unspecified": the Experienced stage, 4 of 20
  stage points and an 8-point "Experience required" penalty for a student. "Registered Nurse", "Patient
  Care Technician" and "Pharmacy Technician" are all scored as experienced hires.
- **Hours.** 433 titles say casual, per diem or PRN, and 259 say part-time, full-time or temporary.
  "Per Diem Days, 8a-4p", "Nights, 7 PM-7 AM" and "12 Hour Shifts" sit in titles too. None of these is read.
- **Misread programs:**
  - "Summer 2027 Nurse Extern Program" is New Grad, from the year in the title. Externs are students
    between their junior and senior years.
  - "Summer Student, Research" is Unspecified.
  - "Postdoctoral Fellow" and "Physician Resident" are Experienced.
- **Words with several meanings:**
  - "resident" is a trainee, a job for current residents ("Physician Resident Pathways") or a patient in
    long-term care ("Resident Care Aide").
  - "rotation" is a new-grad rotation program, a student's clinical rotation or rotating shifts.
  - "on-call" is an employment status in a hospital, and an SRE duty in tech.

**How the pathways work.**
- **Nurse externships:** paid summer programs of 8–10 weeks for nursing students who have finished their
  junior year. Applications open in October.
- **New-graduate nurse residencies:** 12-month programs. Applicants apply in their final semester, with or
  without the NCLEX passed, depending on the program. Cohorts start in spring and fall.
- **Ontario's Nursing Graduate Guarantee:** covers nurses within 12 months of CNO registration.
- **PGY1 pharmacy residencies:** run through the ASHP Match. PhORCAS applications are due in early January,
  and Phase I results come out in mid-March.
- **Post-PharmD industry fellowships:** open in October, with first offers on the AIFA date of December 12.
- **Hospital summer research programs:** run May to August, for undergraduates who return to school.

**Proposal: four parts, all scoped to the Healthcare board.** The gate proves every other board unchanged.
1. **Levels in data, mapped to today's five stages (D13).** A board can carry its own level rules
   (`stage_rules` in its taxonomy entry), checked before the shared ones. They apply only to postings on that
   board.

   | Level | Stage | Title evidence |
   |---|---|---|
   | Extern | Internship | extern, externship |
   | Summer Student | Internship | summer student, research summer student |
   | Student Worker | Internship | nursing or pharmacy student, student pharmacist, undergraduate nursing employee |
   | New Grad Program | New grad | nurse or RN residency, graduate nurse (GN), transition to practice, NGG, new grad RN |
   | Residency | New grad | PGY1 or PGY2, pharmacy, dietetic or PT residency, "Resident" next to a training word |
   | Fellowship | New grad | research, clinical, industry or postdoctoral fellowship or fellow |
   | Postdoc | New grad | postdoc, postdoctoral |

   - **Stages stay as they are.** No new stage is added, so filters, saved profiles and Finance stay
     unchanged. The label shows the real name, for example "Residency — target career stage".
   - **Words with other meanings never count:**
     - "Resident" means a patient in long-term care.
     - "rotating shifts" is a schedule, not a rotation program.
     - Clinical rotations in a description are not a level.
2. **Entry to practice (D14).** On the Healthcare board, a licensed entry-to-practice occupation with no
   level word reads as Entry, labelled "Entry to practice". The occupations are RN, RPN or LPN, pharmacist,
   pharmacy technician, MLT, RRT, PT, OT, dietitian, paramedic, PSW or CNA, patient care technician and
   medical assistant.
   - The rule that years of experience decide still wins: "3+ years acute care" stays Experienced.
   - Physicians, NPs, PAs and CRNAs stay Experienced.
   - About 1,711 stored postings move from Experienced to Entry. All of them are on the Healthcare board.
3. **Hours as facts, not a stage (D15).** Facts gain `hours`:
   - the employment type: full-time, part-time, casual, per diem or PRN, temporary or contract;
   - the shifts: days, evenings, nights, rotating, 12-hour or weekends;
   - whether the job is on call.

   They're read from the title and the description. They show as chips on the posting and as an Opportunities
   filter. They add no fit points unless you set a preference in Settings ("Hours I can work", "No nights").
   Every board's facts gain the field, but no board's fit changes. It is a code change to `build_facts`, so it
   needs `FACTS_VERSION` 10 → 11 in the same release as the taxonomy change. That costs no extra recompute.
4. **Licences and credentials (D16, with Phase 5).**
   - **What a posting asks:** the registration it requires (RN or CNO, RPN, OCP, CPhT, CSMLS, BLS…), and
     whether it takes pending licensees ("eligible for registration", GN status, "new graduates welcome",
     NGG).
   - **What you hold:** the profile gains "Licences & certifications", read from the resume's certifications
     section.
   - **The penalty:** "Licence required", applied the way the degree penalty is. It applies when a posting
     requires a licence you neither hold nor expect.
   - **Deadlines:** program windows go to Calendar as deadlines: the PhORCAS deadline, AIFA December 12, the
     externship and summer research windows, and NGG.

**As built (Phase 3).**
- **Levels:** `stage_rules` in the Healthcare entry of `taxonomy.json`. They're read only for postings on the
  Healthcare board, and such a level carries `board_level` with a badge: EXTERN, RESIDENCY, FELLOWSHIP,
  POSTDOC…. Its Career stage line says "entry level", not "entry level in finance".
- **Entry to practice** applies when no level word matched and under two years of experience are asked. Two
  years or more read as before, so "2+ years" stays Experienced.
  - The shared years reader only reads "N years of experience…" phrasings.
  - "3 years of acute care experience" isn't read, today or now. Widening it would change postings on
    every board, so it's left for a separate change.
- **Hours** are in the facts on every board (`facts.hours`). They show in the posting's details ("Hours: Casual ·
  Nights · Rotating shifts") and as the Hours filter in Opportunities. That filter reads the facts JSON, and
  only when it is set: about 2 s over all 228k postings and well under a second for one board, with no schema
  change.
- **The hours preference** in Settings ("Hours I can work", "No nights"), the only part of D15 that could add
  fit points, comes with the Settings work in Phase 6.

---

## 4. Employer types

All new types are on the healthcare track. Existing employers are never re-typed. A new type would change the
label and the company points of their postings on the Finance and tech boards.

| Type | Label | Track(s) | Examples |
|---|---|---|---|
| `hospital` | Hospital & Health System | healthcare | UHN, SickKids, Sunnybrook, Hamilton Health Sciences, The Ottawa Hospital, Mass General Brigham |
| `pharma` | Pharma | healthcare | Pfizer, Merck, Novartis, Sanofi, AstraZeneca, Apotex |
| `biotech` | Biotech | healthcare | Moderna, AbCellera, Zymeworks, STEMCELL, Ginkgo Bioworks |
| `medtech` | Medical Devices | healthcare | Medtronic, Stryker, Boston Scientific, BD, Kardium |
| `cro_cdmo` | CRO & CDMO | healthcare | IQVIA, ICON, Parexel, Syneos, Charles River, Lonza |
| `diagnostics` | Diagnostics & Lab Tools | healthcare | LabCorp, Quest, LifeLabs, Dynacare, Illumina, Thermo Fisher |
| `payer` | Health Insurer | healthcare | Centene, Blue Cross plans, GreenShield, Medavie (D5) |
| `public_health_agency` | Public Health Agency | healthcare | Public Health Ontario, Toronto Public Health |
| `university` | University | healthcare | University of Toronto, McMaster, UBC, McGill |
| `pharmacy_consumer` | Pharmacy & Consumer Health | healthcare | Shoppers Drug Mart, Rexall, Walgreens, Kenvue, Haleon |
| `research_lab` (exists) | Research Lab (unchanged) | tech **and** healthcare | Ai2 today; adds Broad Institute, Fred Hutch, OICR, Arc Institute (D10) |
| `health_tech` (exists) | Health Tech (unchanged) | tech **and** healthcare | CVS Health, Humana, UnitedHealth Group, Elevance, Cigna, GE HealthCare, Intuitive, Epic, Veeva (D4) |

- **Payer vs insurance (D5).** Finance's `insurance` type (Manulife, Sun Life…) stays as it is. Health
  insurers already in companies.json stay Health Tech. New health insurers get `payer`. Their actuarial and
  finance roles are still Finance postings, because the classifier decides finance first.
- **Priors** point only at Healthcare filters. Tech priors work the same way, and a prior never makes a role
  finance. For example: `medtech` → medical_devices 2; `cro_cdmo` → clinical_research 2;
  `public_health_agency` → public_health 3; `hospital` → clinical_care 2, health_admin 1. A prior on
  `research_lab` or `health_tech` names only `healthcare.*` filters, so their tech postings are unaffected.
- **HQ as location:** as for tech employers, a healthcare employer's HQ never stands in for a posting's
  location. Without that, finance postings at newly listed employers could gain a country and move in fit.
- **New company keys** equal the slugs those employers' stored postings resolve to today, so cluster keys don't
  move. The gate checks this. A new entry that would re-type a stored Finance posting shows in the gate's
  label list.
- **As built (Phase 3):**
  - The types, their priors and the shared Research Lab and Health Tech types are in.
  - Healthcare employers themselves come in Phase 4, each with its sources. Until then the new types have no
    employers.
  - In Settings, a Healthcare profile sees "Healthcare & Science employer types": the 10 new types plus the
    two shared ones.

---

## 5. Sources: folder, groups and manifest

### 5.1 Layout

```
config/sources/
  health/   health_core  hospitals_canada  hospitals_us  pharma  biotech  medtech  diagnostics_labs
            cro_cdmo  research_institutes  public_health  payers  pharmacy_consumer
```

- `health_core` holds the two LinkedIn sources: `linkedin_us_health` and `linkedin_canada_health`. Each has
  4–6 student queries and the settings of `linkedin_us_software`, and all LinkedIn requests share one lock.
  `linkedin_us` and `linkedin_canada` are not edited.
- **Employers already polled for tech** (CVS, Humana, Elevance, Cigna, GE HealthCare) get new sources for
  their clinical, pharmacy and research job families, with the same `company_key`. They go in the pack of
  their type: CVS in `pharmacy_consumer`, the insurers in `payers`, GE HealthCare in `medtech`. Their
  existing sources are untouched. UnitedHealth Group's whole feed is already in `shared/health_tech`, which
  Healthcare polls.
- Packs are split by count in Phase 4 (for example `hospitals_ontario`), so none holds more than 50. Never
  `finance/`, `shared/` or `tech/`.

### 5.2 Manifest

```json
"folders": {
  "finance": {"fields": ["finance"]},
  "shared":  {"fields": ["finance", "software", "data_ml", "hardware", "product", "design", "healthcare"]},
  "tech":    {"fields": ["software", "data_ml", "hardware", "product", "design", "healthcare"]},
  "health":  {"fields": ["healthcare"]}
},
"fields": {
  "healthcare": {
    "core": ["lists", "health_tech", "health_core"],
    "filters": {
      "clinical_care":      ["hospitals_canada", "hospitals_us", "pharmacy_consumer", "payers"],
      "clinical_research":  ["cro_cdmo", "pharma", "biotech", "research_institutes", "hospitals_canada", "hospitals_us"],
      "lab_research":       ["biotech", "pharma", "research_institutes", "diagnostics_labs", "cro_cdmo"],
      "bioinformatics":     ["biotech", "research_institutes", "diagnostics_labs", "pharma"],
      "regulatory_quality": ["pharma", "biotech", "medtech", "cro_cdmo", "diagnostics_labs"],
      "medical_devices":    ["medtech", "diagnostics_labs"],
      "public_health":      ["public_health", "research_institutes", "hospitals_canada"],
      "health_admin":       ["hospitals_canada", "hospitals_us", "payers", "pharmacy_consumer"],
      "medical_affairs":    ["pharma", "biotech", "medtech"]
    }
  }
}
```

- **Why these core groups:**
  - `lists` (the shared community lists) carries 299 of today's healthcare postings: zapply new-grad,
    derec4 and zapply Canada.
  - `health_tech` (its `shared/` and `tech/` packs) carries 859.
  - Nothing else carries more than 27 (Oracle Health in `big_tech`), so no other tech group is added.
- Adding `healthcare` to the `shared/` and `tech/` audiences changes no other board, because a board polls only
  the groups it names.
- The `_readme` gains the `health/` folder and the rule that a board polls only what it names.
- The existing manifest test extends to Healthcare: its filter keys must equal its taxonomy filters, and every
  group must have a pack.

### 5.3 Every new source
- **Fields:** each has `company_key`, `group`, `priority`, `geography` and `min_interval`, plus `label` when
  the employer has other sources ("CVS Health pharmacy roles").
- **Verification:** each pack header records the verification date. Each source's feed is fetched once in
  Phase 4 with the app's own adapter. Each board is checked by the name the ATS shows for it and by what its
  postings say.
- **Descriptions and titles:** for every ATS used, three postings are opened to check that the drawer shows
  the real description, not a metadata line, an empty text or a department alone, and that titles carry no
  markup.
- **Slow listings:** each source's fetch time is measured. Hospitals and giants with thousands of postings read
  only their healthcare job families (Workday facets, a Phenom or Eightfold query).
- **Keys:** checked against all 797 names in `config/source_defaults_history.json`. The only retired names
  are `linkedin_us_tech` and `linkedin_canada_tech`, which aren't reused.

---

## 6. What each profile polls, before and after

"After Phase 2" means the machinery and the manifest are in place, with no new sources yet. N is the number of
new `health/` sources Phase 4 verifies; the target is 15–40 per filter.

| Profile | Today | After Phase 2 | After Phase 4 |
|---|---|---|---|
| Finance, default | 347 | 347, same list and hashes | 347 |
| Software / AI & Data / Hardware | 713 / 524 / 191 | same, same hashes | same |
| Product, Design | 319 | same | same |
| user (Software, Hardware) | 428 | same | same |
| Finance + Software | 760 | same | same |
| Sales, Operations, People & Legal, Finance + Sales | 785 | 785 | 785 + N |
| **Healthcare** | 785 | **53** (lists, health_tech) | 53 + N; picking filters narrows to core + their groups |
| **Finance + Healthcare** | 785 | **376** (Finance's 347 + `tech/health_tech`) | 376 + N |
| **Software + Healthcare** | 785 | **713** (Software already polls `health_tech`) | 713 + N |
| **AI & Data + Healthcare** | 785 | **524** | 524 + N |
| Alert runner (no profile) | 785 | 785 | 785 + N |

**Mixed profiles (D3).** Today any profile with Healthcare polls every source. After this change, a mixed
profile polls the union of its boards' own selections, so Finance + Healthcare stops polling `tech/`. On your
copy (`…\scratchpad\gate\mixed.py`, with 0.3.11's stored facts, canonical and not closed; `main`'s counts
differ by at most 2 per board, see section 2.3):

| Profile | Sources it stops polling | Its board postings from only those sources |
|---|---|---|
| Healthcare only | 732 (shared 285, tech 409, finance 38) | 104 of 1,261 Healthcare postings (3 also listed by a source still polled) |
| Finance + Healthcare | 409 (all `tech/` except `tech/health_tech`) | 1,277: 1,263 Finance, 14 Healthcare (26 also listed elsewhere) |
| Software + Healthcare | 72 (finance 38, shared 9, tech 25) | 5,298: 5,283 Software, 15 Healthcare (2,497 also listed elsewhere) |
| AI & Data + Healthcare | 261 (finance 38, shared 73, tech 150) | 2,589: 2,531 AI & Data, 58 Healthcare (492 also listed elsewhere) |

**What happens to those stored postings:**
- They aren't deleted, and they stay on the board with their last status.
- Nothing closes them: closing needs a poll that misses them (`update_lifecycle`), and no rule ages postings
  out.
- Their fit falls slowly as they age, through the freshness points, so they drift down the list.
- A Finance-only profile on your copy already shows the same 1,263 Finance postings from `tech/` sources
  without polling them. After the change, Finance + Healthcare behaves exactly like Finance alone for them.

---

## 7. Candidate employers, with the ATS I expect

Legend: ○ new, with the ATS I **expect**. `?` marks a guess. ◇ means the employer already has a tech or
finance source, and a healthcare job-family source is added beside it. Nothing ships unless its feed is
fetched in Phase 4. Canada comes first, then the US hubs (Boston/Cambridge, Bay Area, San Diego, NJ/NY, Research
Triangle, Philadelphia, Seattle), then remote. Groups serve the filters listed in 5.2.

- **hospitals_canada:**
  - Toronto: ○UHN, ○SickKids, ○Sunnybrook, ○Sinai Health, ○Unity Health Toronto, ○CAMH, ○Women's College,
    ○North York General, ○Michael Garron, ○Humber River, ○Trillium Health Partners, ○William Osler,
    ○Scarborough Health Network, ○Mackenzie Health (workday? taleo? successfactors?).
  - Elsewhere in Ontario: ○Hamilton Health Sciences, ○St. Joseph's Hamilton, ○The Ottawa Hospital, ○CHEO,
    ○Kingston Health Sciences, ○London Health Sciences, ○Ontario Health (workday?).
  - Other provinces: ○Vancouver Coastal / PHSA / Providence Health Care (successfactors?), ○Alberta Health
    Services (taleo?), ○Nova Scotia Health (?), ○McGill University Health Centre (?).
  - Quebec's CIUSSS portals and HealthForceOntario are likely unreadable.
- **hospitals_us:** ○Mass General Brigham, ○Boston Children's, ○Dana-Farber, ○Beth Israel Lahey,
  ○Mayo Clinic, ○Cleveland Clinic, ○Johns Hopkins, ○NYU Langone, ○Mount Sinai, ○Penn Medicine, ○CHOP,
  ○Duke Health, ○UNC Health, ○UCSF Health, ○Stanford Health Care, ○Kaiser Permanente, ○Providence,
  ○Seattle Children's (mostly workday?, some taleo/oracle_hcm or icims?).
- **pharma:** ○Pfizer, ○Merck/MSD, ○Johnson & Johnson, ○AbbVie, ○Bristol Myers Squibb, ○Eli Lilly,
  ○Novartis, ○Roche/Genentech, ○Sanofi (incl. Sanofi Pasteur Toronto), ○AstraZeneca, ○GSK, ○Novo Nordisk,
  ○Bayer, ○Takeda, ○Amgen, ○Gilead, ○Regeneron, ○Vertex, ○Biogen, ○Moderna, ○Teva, ○Sandoz (mostly workday?;
  novo_nordisk successfactors?) · ○Apotex, ○Bausch Health, ○Sanis/Sandoz Canada (successfactors? workday?).
- **biotech:**
  - Canada: ○AbCellera, ○Zymeworks, ○STEMCELL Technologies, ○Xenon, ○Aspect Biosystems, ○Notch
    Therapeutics, ○Deep Genomics, ○Repare, ○BenchSci (greenhouse/lever/workday?).
  - US: ○Ginkgo Bioworks, ○10x Genomics, ○Twist Bioscience, ○Generate:Biomedicines, ○Relay, ○Beam,
    ○Intellia, ○CRISPR Therapeutics, ○Mammoth, ○Altos Labs, ○Calico, ○Denali, ○Sana, ○Arsenal Bio, ○Eikon,
    ○Dyno, ○Absci, ○Freenome, ○GRAIL, ○Guardant, ○Alnylam (greenhouse/lever/ashby?, workday for the larger
    ones?).
- **medtech:** ○Medtronic, ○Stryker, ○Boston Scientific, ○Abbott, ○BD, ○Baxter, ○Edwards, ○Zimmer Biomet,
  ○Philips, ○Dexcom, ○ResMed, ○Hologic, ○Insulet, ○Smith+Nephew (workday?) · ○Siemens Healthineers (avature,
  like Siemens?) · ◇GE HealthCare clinical families (workday facets) · ○Kardium, ○Synaptive, ○StarFish
  Medical, ○Profound Medical (greenhouse/lever?).
- **diagnostics_labs:** ○LabCorp, ○Quest, ○Exact Sciences, ○Illumina, ○Thermo Fisher, ○Danaher companies
  (Cepheid, Beckman Coulter), ○Agilent, ○Bio-Rad, ○Revvity (workday?) · ○LifeLabs, ○Dynacare (?).
- **cro_cdmo:** ○IQVIA, ○ICON, ○Parexel, ○Syneos, ○Fortrea, ○Charles River, ○Lonza, ○Catalent (workday?) ·
  ○Medpace (icims?) · ○Altasciences, ○BioVectra (?).
- **research_institutes:**
  - Institutes: ○Broad Institute, ○Fred Hutch, ○Dana-Farber research, ○Allen Institute, ○HHMI Janelia,
    ○Jackson Laboratory (workday?) · ○Arc Institute, ○CZ Biohub (greenhouse/ashby?) · ○OICR (?).
  - Universities: ○University of Toronto (taleo/successfactors?), ○McMaster, ○UBC, ○McGill (workday?),
    ○Waterloo, ○Ottawa, ○Western (?).
  - Vector (ADP) and NIH (USAJobs) have no adapter.
- **public_health:** ○Public Health Ontario (workday?), ○City of Toronto / Toronto Public Health
  (successfactors?), ○CIHI, ○Canadian Cancer Society, ○Heart & Stroke (?), ○PATH, ○Partners In Health
  (greenhouse?).
  - PHAC and Health Canada (GC Jobs), the CDC (USAJobs) and state health departments (NEOGOV) have no adapter.
  - The group is dropped, and its filter served by LinkedIn, research institutes and hospitals, if fewer
    than 5 feeds verify. That is the tech `research_labs` precedent.
- **payers:** ◇Humana, ◇Elevance, ◇Cigna clinical families (workday facets) · ○Centene, ○Molina, ○Blue
  Shield of California, ○Highmark (workday?) · ○GreenShield, ○Medavie Blue Cross, ○Pacific Blue Cross (?).
- **pharmacy_consumer:** ◇CVS pharmacy and clinical families (workday facets) · ○Shoppers Drug Mart/Loblaw,
  ○Kenvue, ○Haleon (workday?) · ○Walgreens, ○Rexall, ○London Drugs (?).
- **health_core:** `linkedin_us_health` (nursing student, pharmacy intern, clinical research coordinator,
  research assistant biology, regulatory affairs intern, public health intern) and `linkedin_canada_health`
  (nursing co-op, pharmacy student, clinical research coordinator, research assistant, regulatory affairs
  co-op, biomedical engineering co-op).

Phase 4 runs up to 4 research agents at once, one per filter. They return identifiers found on careers pages
or in job URLs, never guessed. I write and verify the packs myself, and anything an existing adapter can't read
goes to "not added" with the reason. I'll ask before any new adapter (D11).

---

## 8. Resume reading

Commit `b9c9b1d` is the model. A Healthcare resume must come back with Healthcare filters, skills, employer
types and degree, not as Finance or Software.

- **The track gate.** `tech_resume()` becomes `resume_tracks()`. A track opens when the degree matches the
  track's degree words, or when a job or project title is classified on one of the track's boards
  (confidence ≥ 0.45). Healthcare's degree words include nursing, pharmacy, biology, biochemistry, biomedical,
  life sciences, health sciences, kinesiology, neuroscience, microbiology, immunology, genetics, public health,
  epidemiology, medical laboratory, physiology, pharmacology, nutrition, physiotherapy and occupational
  therapy.
  - A resume that opens no track is read exactly as today, with the finance vocabulary.
  - Tech's gate is today's, moved into data.
- **When the Healthcare track is open:**
  - the track's resume signals (data, section 9) are read: GCP, IRB and protocols point at
    clinical_research; PCR, ELISA and cell culture at lab_research;
  - Healthcare skills are read;
  - Healthcare employer types are proposed;
  - healthcare role words (nurse, technician, technologist, coordinator, therapist, extern, aide) join the
    role-line words, for this track only, so a finance resume's lines are read as today.
  - Finance work counts for finance roles and healthcare work for healthcare roles.
  - Quant Research reads only quantitative-finance terms, as for tech resumes, so Python and statistics in a
    bioinformatics resume don't point at Quant.
- **Generic titles.** A title placed on the board with no filter ("Research Assistant" at a hospital) targets
  the whole board. Decision D7: whether "Registered Nurse" targets Clinical Care or the whole board.
- **Degrees.**
  - BScN, BHSc and BKin read as undergraduate; MPH and MSN as masters.
  - PharmD and MD set no level: nothing is guessed, because the levels are undergraduate, masters, MBA and
    PhD.
- **Applying a resume** adds Healthcare to the boards and keeps the boards you chose, as for tech.
- **Fixtures:** in `tests/resume/test_resume_health.py`, three invented resumes, each as text, a PDF and a
  LaTeX PDF (font codes, as the CS fixture has):
  - a nursing student (→ Clinical Care);
  - a biology co-op student with lab and bioinformatics work (→ Lab Research, Bioinformatics);
  - a pharmacy or regulatory co-op student (→ Regulatory & Quality, Medical Affairs).

  A biomedical engineering resume checks that Hardware and Healthcare both open. Finance and tech fixtures
  must parse and apply byte-identically: their outputs from `main` are recorded and compared.
- **Matching and Calendar** (`c71d603`). Profiles without Finance treat a role no board places as "doesn't
  name a field you recruit in". Tiers 2 and 3 place Healthcare roles on the board, so they stay resume matches
  and Calendar entries for Healthcare users. `RULES_VERSION` goes to 3, because the company points for
  Healthcare employers change for Healthcare profiles.

---

## 9. Board-agnostic machinery

### 9.1 One definition per board, in data

- **`config/taxonomy.json` → `non_finance_families.<board>`** is the board's definition. It already holds the
  label, the title words and the filters. It gains:
  - `track`;
  - `fallback_title` (tier 2);
  - `occupation_beats_finance`, which replaces the hard-coded set in `intel/taxonomy.py:247`;
  - `skill_groups`, which replaces `FIELD_SKILLS` in `web/js/fields.js`;
  - `employer_types`: what a resume on this board proposes. It replaces the non-finance keys of
    `COMPANY_TYPES` in `intel/resume_insights.py`.

  Each filter gains `employer_types`. Finance gets a small top-level `finance` entry with its `track` and
  `skill_groups`.
- **`taxonomy.json` → `tracks`** holds what a track's boards share:
  - `label`;
  - the Settings heading ("Tech employer types");
  - `employer_noun` for the "Why" line ("recognized tech employer");
  - resume `degree`, `role_words` and `signals`, which replace `TECH_SIGNALS`. The signals are one ordered
    list per track, `[filter, weight, pattern]`, not a list on each filter: the order they're read in
    settles ties between specialties, so a resume's targets stay byte-identical (Phase 2);
  - `skills_from`: the boards whose postings read the track's skills. Tech keeps today's rule: every
    non-finance posting, listed board by board. Healthcare reads only Healthcare postings (D9).

  A track without `degree` or resume signals doesn't take part in resume reading. Sales, Operations and People
  & Legal stay exactly as today until their sessions add data.
- **`config/companies.json`:** each type gets a `tracks` list in place of `track`. finance → `["finance"]`,
  tech → `["tech"]`, both → `["finance", "tech"]`. Finance types gain `section` ("Banks", "Investing"…),
  replacing `EMPLOYER_SECTIONS` in `fields.js`. The order and keys stay identical, so Settings shows the same
  four finance sections.
- **`config/skills.json`:** `"track"` stays a string per skill: `tech` or `healthcare`. New Healthcare groups
  are clinical, lab techniques, regulatory & quality and health data (SAS, SPSS, Stata, REDCap, Medidata).
  Existing skills don't change.

### 9.2 Code changes

| File (re-check lines) | Today | After |
|---|---|---|
| `intel/knowledge.py` ~331, families loader | `Skill.tech` boolean; families without track | `Skill.track`; tracks, board tracks, type tracks, resume data compiled once |
| `intel/skills.py` | `extract_skills(..., tech=bool)` | `extract_skills(..., tracks=…)`: a skill with a track is read only when that track is open |
| `intel/facts.py:95` | `tech=not is_finance` | the tracks whose `skills_from` names the posting's board; identical for every existing board |
| `intel/companies.py:52` | HQ hidden for `track == "tech"` | hidden for types whose tracks exclude finance; identical for every existing type |
| `intel/scoring.py:193` | 7 points for a tech type only with a tech board, else 4 | 7 when the type shares a track with one of the profile's boards, else 4, with the track's noun in the text. Byte-identical text and points for every existing type and profile. `FINANCE_TYPES` stays the finance tier list |
| `intel/taxonomy.py` ~247, `classify` | hard-coded board set for "a technical occupation beats finance"; no tier 2 | the set from `occupation_beats_finance`; `fallback_title` after the finance decision; D1/D2 rules if approved |
| `intel/resume_insights.py` ~19, 63–137, 216–299 | `TECH_FIELDS`, `TECH_SIGNALS`, `_TECH_DEGREE`, tech `COMPANY_TYPES` | `resume_tracks()`, signals and employer types from data; finance `SIGNALS` and finance `COMPANY_TYPES` stay in code as the Finance board's vocabulary |
| `intel/resume.py` ~25, 363, 374, 513 | `TECH_FIELDS` in role lines and valid targets | open tracks; role words per open track; whole-board targets for boards on resume tracks |
| `intel/sources.py:31` | `TECH_FIELDS` (kept for `stash@{0}`) | removed from code. `stash@{0}` stays untouched and unapplied |
| `dashboard.py` meta ~2309 | families, company types, skills | plus `tracks`; each board's track and skill groups; each type's tracks and section |
| `web/js/fields.js` | `TECH_FIELDS`, `FIELD_SKILLS`, `EMPLOYER_SECTIONS` | read from meta: `skillGroupsFor(fields, meta)`, `employerSections(meta)` returns one group per track. `FIELD_INFO` (icons and notes for all ten boards) stays |
| `web/js/views/settings.js` ~330 | "Tech employer types" for `TECH_FIELDS` | one "‹track› employer types" group per track, shown only to that track's boards. Finance's group and copy unchanged |
| `web/js/views/welcome.js` | `skillGroupsFor(fields)` | `skillGroupsFor(fields, meta)`; the "Which specialties?" step appears for Healthcare through `family_tree()` with no change |
| `web/js/preview/*` | sample meta | sample meta with tracks, so the preview harness keeps working |

### 9.3 What still knows boards in code
Reported for later sessions, and not changed unless a board needs it:
- the classifier's occupation regexes in `intel/taxonomy.py`: `_TECH_OCCUPATION`, `_CS_OCCUPATION`,
  `_PHYSICAL_ENGINEERING`, `_HARDWARE_OCCUPATION`, `_BUSINESS_OCCUPATION`, `_SUPPORT_OCCUPATION`;
- `family_of`'s two special cases: public affairs → People & Legal, and support → Operations;
- finance's `FINANCE_TYPES`, `SPECIALIST`, `SIGNALS` and finance `COMPANY_TYPES`;
- `FIELD_INFO` (UI copy).

Later boards will probably meet `_BUSINESS_OCCUPATION` and `_SUPPORT_OCCUPATION`. If one must change, that
session reports it, as the brief asks.

### 9.4 What a later board adds
- its taxonomy entry: track, filters, `fallback_title`, `skill_groups` and `employer_types`, and its
  track's resume signals;
- types in `companies.json` and skills in `skills.json`;
- its folder, packs and manifest entry, plus the folder's audience;
- tests.

No Python or JS changes. A test enforces this: every board in `FIELD_INFO` has a taxonomy entry, and every
track's boards, skill groups and types resolve.

---

## 10. Upgrade and versions
- **Sources:** `upgrade_sources()` keeps its code. Every existing source keeps shipping unchanged. New
  sources get `__since__` 11, and `sources_version` goes 10 → 11 (`tools/build_windows.py:115`), so
  `record_release` accepts the bundle.
- **Upgrade test:** from `git show v0.3.11:config.json` plus that tag's packs, and from `main`'s schema-7
  layout, each with a small synthetic database: 0 sources removed, 0 postings deleted, every setting kept.
- **One recompute.** Editing `taxonomy.json`, `companies.json` and `skills.json` changes `config_fingerprint()`.
  The first start then recomputes facts for every stored posting, once.
  - Measured here: `build_facts` reads 23 postings a second in one process, 3.5 hours for your 294,571
    postings. The store's facts pass then needs another 53 minutes to write them, even with the facts
    precomputed: the query that picks each batch of 500 scans and sorts every pending posting, descriptions
    included. That is about **4½ hours** in all. 0.3.8 took about 60 minutes for 129k.
  - Finance postings go first (`ORDER BY is_finance DESC`): about 41k in about 45 minutes. Until a posting
    is recomputed, it keeps its old facts and score.
  - Taxonomy, companies, skills and the new sources land in one release (D6).
- **Versions:** `FACTS_VERSION` goes 10 → 11 for hours (D15), in the same release as the taxonomy change, so it
  costs no second recompute. `RULES_VERSION` goes 2 → 3. Both were done in Phase 3. No schema change (7 comes
  from `main`).

---

## 11. Phases and proofs
1. **This design.** Committed; then I stop for approval.
2. **Machinery and the manifest, no new sources.**
   - The data model of section 9 with today's values, and `tools/board_gate.py` with its test.
   - Tests:
     - every existing board's polled list and hashes equal section 2.2 (fixture
       `tests/sources/board_polling_v0_3_11.json`);
     - the boards that poll every source gain only `health/` sources;
     - no source is defined twice, and no pack holds more than 50;
     - a Finance-only profile polls 0 `health/` sources, and Healthcare polls 0 `finance/` sources;
     - picking filters narrows Healthcare to core plus their groups.
   - The upgrade test.
   - The gate: an empty diff for all 17 profiles.
   - I stop and show the output.
   - **Done.** The gate on the copy, epoch 1793070000, compared `main` (`6c7112c`) with this branch:
     - all 17 profiles showed identical board views: postings, fit, order, fit detail and resume match;
     - facts were identical for all 294,571 postings;
     - no posting changed board.

     Polling: every existing board polls the lists and hashes of section 2.2. Healthcare polls 53 sources,
     Finance + Healthcare 376, Software + Healthcare 713 and AI & Data + Healthcare 524. Every resume text in
     the test suite, and your stored resume, parse and apply byte-identically against `main`.
3. **Filters, employer types and skills, plus career stages and hours (D13–D15).**
   - Classifier tests for each filter and each healthcare level, including the near-misses in 3.4. Every
     existing test stays unchanged.
   - The gate: only approved moves (D1, D2), stage changes on the Healthcare board (D13, D14) and label
     changes.
   - **Done.** The gate on the copy, epoch 1793070000, compared `main` (`6c7112c`) with this branch:
     - **Boards without Healthcare:**
       - each lost only postings that moved to Healthcare: Finance 18, Software 5, Operations 10 and
         Sales 1;
       - nothing was added and nothing else changed (fit, detail, match, badges, urgency), and the order
         stayed the same;
       - Hardware, Product, Design, AI & Data and People & Legal were identical.
     - **Healthcare** grew from 1,260 to 5,274 postings:
       - 4,868 came from no board and 36 from other boards;
       - 817 changed filter;
       - stage changes were only on this board: 2,082 entry to practice, 18 residency, 14 postdoc, 2
         fellowship, 2 student worker and 1 extern;
       - in Finance + Healthcare, two D1 postings lost Finance's recruiting-cycle urgency.
     - **Fix from the first run:** it moved The Aerospace Corporation's "Research Associate – Non-Destructive
       Evaluation" off Finance on the description words microscopy, specimens and laboratories. Those three
       words no longer count as life-science evidence. The same change keeps five medtech and pharma postings
       with no employer type yet (Baxter, BD, Danaher, Zoetis, J&J) off the board until Phase 4 types their
       employers.
     - **Approved** on 2026-10-27: the 34 open moves the gate listed (Finance 18, Operations 10, Software 5,
       Sales 1).
     - **Tests:** three existing ones changed for the new track or the gate's output:
       - the tech type count in `test_tech_taxonomy.py`;
       - the field tracks in `fields.test.js`;
       - the move listing in `test_board_gate.py`.
4. **Sources, one filter at a time.** Research, verify, write packs, commit; the gate again. Then the
   per-profile poll time, before and after, including the alert runner.
   - **Clinical Care** (2026-10-27): 45 sources, each fetched once with the app's adapter, and 38 employers.
     - `health_core`: the two LinkedIn searches.
     - `hospitals_canada`: 16 sources (Ontario, BC, Nova Scotia).
     - `hospitals_us`: 16. The giants read only their clinical and research job families.
     - `payers`: 10, among them the clinical families of Humana, Elevance Health and Cigna.
     - `pharmacy_consumer`: 1, CVS Health's pharmacy and clinical families.
     - Each pack's note lists what wasn't added and why: Taleo, PeopleSoft, Dayforce, Njoyn or Paradox,
       feeds the adapters can't read, and Walgreens's 22,585 mostly store postings.
     - `sources_version` 11, history recorded. The manifest names all nine filters; groups that don't exist
       yet are added with their packs.
   - **Clinical Research** (2026-10-27): 79 sources and 79 employers.
     - `pharma`: 20, full listings (each was under 2,000).
     - `biotech`: 29.
     - `cro_cdmo`: 15. IQVIA reads only its clinical, lab and quality families.
     - `research_institutes`: 15, the institutes and universities.
     - Each was fetched once, and each pack's note lists what wasn't added.
     - The Kula adapter now reads its payload as UTF-8: 10x Genomics' Japanese titles came out as mojibake.
       Sanctuary AI, the only other Kula source, has no non-ASCII titles, stored or live.
     - The new employers on stored postings, simulated with this code (`…\scratchpad\phase4\new_employer_effects.py`):
       - one move off a board: Moderna's "Research Associate, Analytical Technical Operations", from
         Finance to Healthcare by the life_science_research rule, for your yes;
       - no company key changes;
       - otherwise only employer-type labels, 31 of them on Finance postings, at the same fit.
5. **Resume reading, matching, licences (D16) and Calendar,** with the fixtures in section 8; the gate again.
6. **Onboarding, Settings, the Sources view and the docs** (`PRODUCT.md`, `docs/ARCHITECTURE.md`, the
   manifest `_readme`).
   - What's new items drafted in `web/js/release-notes.js`, with no version bump.
   - Merge `main`, run the gate again, run both full suites, and write the final report.
   - Add my lessons to Part C of the brief in the main checkout.

---

## 12. Decisions for you

All sixteen were approved as recommended on 2026-10-27.

| # | Question | Recommendation |
|---|---|---|
| **D1** | Life-science research titles that Finance files as Equity Research: "Research Associate I", "Clinical Research Associate II". About 14 open Finance postings on your copy (Natera, AbbVie, Wash U postdocs…). Move them to Healthcare? If not, every lab RA and CRA from the new sources also lands on Finance for Finance + Healthcare profiles, and Healthcare misses them. | **Move**, with the gate's exact list for your yes in Phase 3 |
| **D2** | Clinical occupations and GMP lab-quality titles beat topic words on other boards: 5 Operations, 4 Software, 1 Product and 1 Sales postings ("Pharmacy Technician Backend-PT", "Quality Control Microbiologist"). "Health policy" titles leave People & Legal (0 on your copy). | **Move**, with the gate's list |
| **D3** | Healthcare leaves "every source". Mixed profiles then poll the union of their boards' selections; Finance + Healthcare stops polling 409 `tech/` sources. Nothing is deleted, and those postings stay but stop refreshing (section 6). | **Yes** |
| **D4** | Health Tech employers (CVS, Humana, UnitedHealth, Intuitive, Epic…) also count for Healthcare: 7 company points instead of 4 for Healthcare profiles. For Finance + Healthcare, finance postings at those employers gain 3 points. Finance-only and tech profiles are unchanged. | **Yes** |
| **D5** | Health insurers: a new `payer` type for new employers. Finance's `insurance` and the existing Health Tech insurers stay as they are. | **Yes** |
| **D6** | One facts recompute on the first start after the release: about 4½ h on your database, Finance first (about 45 minutes). Taxonomy and sources ship together. | **Accept**. A faster facts pass (batch selection that doesn't re-sort every pending posting) could be its own follow-up |
| **D7** | A "Registered Nurse" resume targets Healthcare · Clinical Care. The brief's example says the whole board; with the whole board, lab and regulatory roles would rank level with nursing roles. | **Clinical Care**; the whole board for titles no filter names |
| **D8** | Sales, Operations and People & Legal keep polling every source, so they gain the `health/` packs (+N) until their own sessions. | **Yes** |
| **D9** | Tech skills keep being read from every non-finance posting, Healthcare's included, as today. Healthcare skills are read only from Healthcare postings and Healthcare resumes. | **Yes**, so no other board's facts change |
| **D10** | `research_lab` (Ai2 today) also counts for Healthcare and takes biomedical institutes; its label stays "Research Lab". Universities get their own `university` type. | **Yes** |
| **D11** | No new adapters are planned. Employers whose ATS no adapter reads go to "not added", and I'll ask then. | **As stated** |
| **D12** | The alert runner (no profile) keeps polling every pack, including `health/` (+N; its added time is reported in Phase 4). | **Yes** |
| **D13** | Healthcare levels (Extern, Summer Student, Student Worker, New Grad Program, Residency, Fellowship, Postdoc) as board-specific `stage_rules` in data, mapped to today's five stages. The alternative is a sixth stage, "Residency & fellowship". | **Map to today's stages**, in Phase 3 |
| **D14** | On the Healthcare board, a licensed entry-to-practice occupation with no level word ("Registered Nurse") reads as Entry ("Entry to practice"), not Experienced. Years asked still decide. About 1,711 stored postings change. | **Yes**, in Phase 3 |
| **D15** | Hours (employment type, shifts, on-call) become facts, chips and a filter, with no fit points unless you set a preference. This needs `FACTS_VERSION` 10 → 11 in the same release, so no extra recompute. | **Yes**, in Phase 3 |
| **D16** | Licences: what a posting requires and whether it accepts pending licensees; "Licences & certifications" in the profile; a "Licence required" penalty; program windows in Calendar. | **Yes**, in Phase 5 |
