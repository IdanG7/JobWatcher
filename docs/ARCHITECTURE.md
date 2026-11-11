# Jobwatch architecture

Jobwatch is local-first. The only runtime dependency is `requests`. The server uses
the Python standard library, the database is SQLite, and the dashboard is plain
ES-module JavaScript with no build step.

```
            ┌────────────── config/*.json (taxonomy, companies, skills, locations)
            │
 ATS APIs ──► watcher.py adapters ──► jobs / job_details (unchanged legacy tables)
 GitHub        │  record_changes ─────► job_changes (title/location/comp/link/description)
 LinkedIn      │  update_lifecycle ───► job_state (active → possibly_closed → closed / reopened)
               │  store_description ──► job_text (+ background enrichment, --enrich)
               ▼
          intel_store.IntelStore
               │ facts_pass: intel.build_facts()  — profile-independent, cached by input hash
               │ score_pass: intel.score_job()    — Fit Score 3.0, rescored when the profile changes
               ▼
          job_intel (+ job_fts FTS5) ──► job_query.build_where() ──► dashboard.py JSON API ──► web/
               │
               └──► watcher fit-mode alerts (urgent / high / digest, cooldowns) + saved-search alerts
```

## Modules

| Module | Responsibility |
|---|---|
| `watcher.py` | Adapters, polling loop, dedupe gate, notifications, CLI. The original adapters and the delivery flow are unchanged. Finance hooks run inside `cycle()`. |
| `db_migrations.py` | Versioned migrations through `PRAGMA user_version`. v1 is the original schema. v2 adds the intelligence, CRM and alert tables. Each migration is additive and idempotent. |
| `intel/knowledge.py` | Loads and validates `config/*.json`, compiles regex fragments, matches companies and fingerprints the config so facts recompute when knowledge changes. Boards are defined here from data (see Boards). |
| `intel/taxonomy.py` | Hierarchical classification: category, subcategory, secondary categories and confidence, with evidence. Finance decides first; a board's `claims` and `fallback_title` place what it leaves. |
| `intel/seniority.py` | Finance-aware levels. Analyst is entry level. Associate depends on the category (IB/PE post-MBA or post-analyst vs. entry at banks/asset managers). Stated years of experience can override it. |
| `intel/cycle.py` | Recruiting cycle (`summer_2027`, `new_grad_2027`, off-cycle), graduation windows, deadline extraction with confidence, rolling detection and window status. |
| `intel/eligibility.py` | Degree, GPA, work authorization, sponsorship, citizenship, languages and experience. Fields stay `None` ("Not specified") unless the text states them. |
| `intel/compensation.py` | CAD/USD/GBP parsing. Keeps the original text and labels annualized hourly or monthly pay as an estimate. |
| `intel/skills.py` | Skill extraction with synonym normalization (`DCF` → Valuation, `CapIQ` → Capital IQ). A skill with a track (`"track": "tech"` or `"healthcare"` in `skills.json`) is read only from the boards its track's `skills_from` names and from resumes on that track. |
| `intel/hours.py` | Employment type, shifts and on-call a posting states (`facts.hours`, every board). They cost fit only through the profile's `hours` preference. |
| `intel/licences.py` | Licences and certifications a board's postings require (`facts.licences`, Healthcare only) and a resume shows held or expected. |
| `intel/programs.py` | A board's yearly program windows (PhORCAS, AIFA, NGG…, APM rounds, design internships, co-op terms) as Calendar items, for profiles with that board; a window two of the profile's boards list shows once. |
| `intel/profile.py` | Candidate profile defaults, merge and validation, and the version hash that triggers rescoring. |
| `intel/scoring.py` | Fit Score 3.0: subscores, penalties, reasons, urgency and badges. |
| `intel/resume.py` | Local PDF/DOCX/TXT extraction, bounded document decoding, structured facts and profile proposals. A resume with a track's job or project titles, degree or signals (tech, healthcare) is also read for that track's specialties, skills and licences, and proposes its fields; any other resume is read with the finance vocabulary alone. |
| `intel/matching.py` | Resume shortlist decisions, explicit conflicts and unknown requirements for review. Roles outside the profile's fields are excluded; finance roles stay eligible only when Finance is one of them. |
| `intel/sources.py` | Source packs and selection: which sources each profile's boards poll (see Sources). |
| `intel_store.py` | Incremental facts and score passes, clustering and canonical selection, FTS, change and lifecycle tracking. |
| `job_query.py` | One SQL filter builder shared by the API, CSV export and saved-search alerts. |
| `dashboard.py` | `JobwatchService` (business logic) and a hardened stdlib HTTP handler. |
| `web/` | The single-page dashboard (hash router, views, drawer, command palette). |

Resume matching uses schema v5 side tables: singleton `candidate_resume` stores
structured matching facts, enabled state and the authoritative profile version;
`resume_matches` stores a decision and explanation per job. Apply/profile/watchlist
mutations update that version in the same transaction as the corresponding change.
Scoring workers never advance it, so an older worker cannot revive stale matches.
List/detail queries require matching profile versions and current facts versions.
Resume indexing scores and commits batches, prioritizing existing finance postings;
Opportunities refreshes while unchecked postings remain. Missing job facts also
count toward the pending indicator.

`GET /api/resume` returns saved facts/status. `POST /api/resume/parse` previews a
`{text}` or `{filename,data}` (base64) input without saving. `POST /api/resume`
reparses that input, applies the proposed profile and enables matching. `PATCH`
toggles `{enabled}`; `DELETE` removes resume facts/matches without reverting the
profile. The two POST routes allow bounded file payloads; other routes retain
their normal request cap. PDF parsing uses the documented
[pypdf decompression guards](https://pypdf.readthedocs.io/en/6.10.0/user/security.html).
Private resume data is excluded from portable state and CSV.

## Sources

A source is one feed Foothold polls (`config["boards"]` in the code). Sources live in packs,
`config/sources/<folder>/<group>.json`, each with a `title`, a `verified` date, a `note` and its
`boards`. The folder decides which boards (the fields picked in setup) may poll a pack:

| Folder | Polled by | Holds |
|---|---|---|
| `finance/` | Finance | Banks, boutiques, private markets, asset managers, pensions, finance LinkedIn searches (0.3.7 sources only) |
| `shared/` | Finance, the tech boards, Healthcare and Architecture, Engineering & Construction (AEC) | Employers with both kinds of role: 0.3.7 sources tech boards want too (quant, fintech, lists, big tech, finance firms with 15+ tech postings), and tech employers whose feeds carry 10+ finance postings |
| `tech/` | Software, AI & Data, Hardware, Product, Design, Healthcare and AEC | Tech-only employers and the banks' technology feeds, each fetched before it shipped (`verified`) |
| `health/` | Healthcare | Hospitals, pharma, biotech, medtech, CROs, labs, research institutes, public health, insurers, pharmacies and the healthcare LinkedIn searches |
| `product_design/` | Product and Design | Design studios and agencies, industrial and product design employers, Canadian product and design employers, early-career programs, the boards' LinkedIn searches, and design and product reads of employers polled elsewhere (Amazon, Nike) |
| `aec/` | AEC | Engineering and infrastructure consultancies, structural/MEP/building-science firms, architecture firms, contractors, owners and public infrastructure, building-systems makers (Building Systems filter only), and the board's LinkedIn keyword and company searches (employers whose own sites refuse robots) |

Each board polls only the groups the manifest names for it, so adding a board to a folder's audience
changes no other board (Healthcare polls `shared/lists` and the health tech groups, nothing else there;
AEC polls `shared/lists`, and for Construction, Building Systems and Structural the big tech, semiconductor
and defense groups, whose feeds carry data-centre, fab and facilities work).

An employer whose whole listing is slow to read (Apple, Microsoft, Qualcomm, Siemens) reads it on the tech boards
only, and gives the Finance board a finance search of its site (`query`) instead, since a poll waits for
its slowest source.

`config/sources/manifest.json` names each board's groups (pack file names, which may repeat across
folders): Finance polls every pack it may (`"groups": "*"`); a tech board or Healthcare polls its `core`
groups plus each picked filter's groups (every filter's when none is picked); `everything` boards (Sales,
Operations, People & Legal) poll every pack, `aec/` included.
`intel/sources.py` turns a profile into polled sources: `profile_fields` → `groups_for` →
`selected_packs` → `polled_sources`. A source in no pack (one the user added) is always polled, and a
disabled one never. `watcher.cycle` polls a profile's sources; the CLI alert runner, which has no
profile, polls every enabled source. The Sources view groups rows by pack and names the boards that poll
each (`pack_boards`); rows the profile's boards don't poll are dimmed.

**The Finance board guarantee.** `finance/` ∪ `shared/` holds every 0.3.7 source, setting for setting
(`tests/sources/test_source_packs.py` checks their packaged hash, `ddb8d7057c16c87e`); sources added
since go to `shared/` only, each with its employer (`company_key`) and a verified fetch. Finance
classification runs first, and tech filters only refine postings it leaves outside finance (the finance
tests and the gate check this). A tech employer type (track `tech` in `companies.json`) only labels a posting: its priors point
at tech filters, and its HQ country never stands in for a posting's location. Before a release that
changes sources or knowledge, a gate recomputes every posting on a copy of a real database, at a frozen
time, with the old and the new code, and compares every board posting by posting: `python -m
tools.board_gate snapshot` (once per checkout, each from its own export) and `compare`, for one sample
profile per board, mixed profiles and the user's own. Only an employer-type label going from Unclassified
to a new type passes without the user's yes.

## Boards

A board is a field picked in setup. Finance's vocabulary is in code; every other board is data, so a new
one needs no code:

- `config/taxonomy.json` → `non_finance_families.<board>`: label, title words, filters (each with title,
  department and description rules, `tie_priority` and `employer_types`; one evidence threshold,
  `weights.min_specialty_score`, serves every board), its `track`, `fallback_title`, `claims`,
  `occupation_beats_finance`, `skill_groups` and `employer_types`. Healthcare adds `stage_rules` (levels
  such as Residency and Entry to practice), `licences` and `program_windows`, read only for its postings and
  profiles; AEC has the same three (EIT, P.Eng and architect licences, LEED and PMP certifications, co-op
  terms and the EIT application after graduation).
- `taxonomy.json` → `tracks`: what a track's boards share (Settings heading, the "Why" line's employer
  noun, resume degree, role words and signals, `skills_from`).
- `config/companies.json`: each employer type's `tracks` (and a finance type's Settings `section`).
- `config/skills.json`: each skill's `track`.
- `config/sources/<folder>/` packs and the manifest's entry for the board.

`/api/meta` passes tracks, board tracks, skill groups and licences to the browser, so Settings and setup
show each board's parts only to profiles with that board.

**Configs and upgrades.** The repository's `config.json` lists no sources; `load_config` assembles them
from the packs (`Packs.flat()`, with `_<pack>` headings, and a pack's `sections` keep the old
config.json headings that type employers missing from `companies.json`). The Windows build copies the
packs and writes the sources into the install's `config.json` (`clean_board` keeps `BOARD_FIELDS`).
`config/source_defaults_history.json` records every value each release shipped, the version that first
shipped each source (`__since__`) and the last release's version, hash and names (`__shipped__`). On
upgrade (`portable_start.upgrade_sources`), unedited settings take new defaults, a source newer than the
install is added, and one the bundle stopped shipping is removed with its postings unless the user
re-pointed it. A source shipped again after a release without it counts from the new version, so
installs that lost it get it back. Raise `sources_version` in `tools/build_windows.py` whenever source
defaults change; the build refuses otherwise.

## Fit Score 3.0

What every eligible posting shares (a target stage, a target country, a cycle) is worth little; what tells
one posting from the next (the specialty, the skills it asks for, the city) is worth most. Until 0.3.16
stage and cycle were 30 of the 100 points and skills 10, so most of a board scored 65–75.

| Subscore | Max | Signal |
|---|---|---|
| Role | 35 | Category/subcategory vs. `target_roles` (with `role_weights`). A targeted specialty or finance area 35; a related specialty 24; a posting naming no specialty 20, and another specialty 12, when the profile targets specialties in that board |
| Skills | 20 | Share of the posting's skills (up to 4) on the profile; 6 with no description yet |
| Location | 15 | Target city 15 > remote 11 > target country 6 (11 when no city is picked) > unknown 2 |
| Company | 10 | Employer type vs. `target_company_types`, plus a watchlist bonus |
| Stage | 8 | Level/stage vs. `target_stages` |
| Freshness | 8 | Steep decay for competitive categories, gentle decay for others |
| Cycle | 4 | `target_cycles`, plus a year match with the graduation year |

## The short list

`intel.match_resume` returns a tier, stored in `resume_matches.matched`: 0 ruled out, 1 eligible, 2 short
list. Tier 2 is an eligible posting whose role is a specialty the person picked or the resume shows
(`matching._specific`: a board picked with no specialty in it counts whole; otherwise a posting in another
specialty or in none needs a related specialty or most of its skills on the resume) and whose location is
known to be in a target country, or remote. A posting that requires citizenship, residency or a clearance
the profile's work authorization leaves unknown stays at tier 1 until the person says they have it. What time decides is checked when a list is asked for
(`job_query.SHORTLIST_RECENT`): seen on its source within 7 days, and posted within 30 or with a deadline
still ahead, so no rescore is needed for a role to age off. `resume_params` makes the short list the default
wherever the resume match is on (`shortlist=0` asks for every eligible role); Today
(`dashboard.shortlist_clause`) and fit alerts (`watcher.alert_tier`) use it too. `match["off_list"]` holds
the reasons a posting is eligible but off the list, for the posting panel. A new resume replaces the
targets an earlier resume added (`profile["resume_targets"]`); targets picked by hand stay, and a profile
saved before the note existed keeps every target.

## How lists stay fast

A posting's row in `job_intel` holds its facts (kilobytes), so anything that reads a column of every posting
in a board reads hundreds of megabytes. Measured on a database of 471,000 postings (0.3.15 â†’ 0.3.16, cold):
the default Opportunities list 8.3 s â†’ 0.5 s, every eligible role 7.6 s â†’ 1.5 s, Today 11.6 s â†’ 0.8 s.

- `intel_list` (schema v9) is one index holding what a list filters, counts and groups by. The pass that
  builds a list (`dashboard.jobs`, into the temporary `_tiers` table) reads it instead of the rows, joins
  only the tables its filter names (`job_query.scan_from`), and keeps the facet columns, so the sidebar
  counts never go back to `job_intel`.
- The short list starts from the resume's verdicts (`job_query.shortlist_from`, `dashboard.shortlist_clause`):
  a few thousand rows through `resume_matches_filter`, not a verdict looked up for every posting in a board.
  That pass therefore has no count of eligible or ruled-out roles; `resume_matching.eligible_total`,
  `unfiltered_total` and `excluded_total` are null on the short list and filled with `shortlist=0`.
- How many postings the resume hasn't read (`dashboard._count_pending`) is four index counts, not a join
  over every posting.
- Where the planner picks a worse index, the query says so: `CROSS JOIN` fixes a join order (the short list,
  the market tape), and a unary plus on `is_canonical` (`dashboard.by_deadline`) sends a deadline range to
  the deadline index. Check a new list query with `EXPLAIN QUERY PLAN` on a real-size database; tests use a
  handful of postings and cannot show a slow plan.

Penalties apply only to explicit evidence:

- Seniority: senior −25, experienced −8.
- Geography: −10.
- Cycle year: −10.
- Graduation window: −12.
- Degree: −10 to −20.
- Licence required (Healthcare postings): −20 when the profile holds none of the licences the posting asks
  for.
- Hours, only once the profile sets them: −10 for a posting that states only other employment types, −10
  for night shifts.
- No sponsorship when you need it: −15.
- Citizenship, language and GPA.
- Closed: −40.
- Deadline passed: −30.
- Stale: −5.

The drawer's **Why 91?** panel shows every line. The scores in this section are illustrative. Weights live in `intel/scoring.py`.

## Data model (v2 additions)

- `job_intel`: one row per posting. It holds the facts JSON, denormalized filter columns, fit, `fit_detail`, urgency, badges, `eff_deadline` (your override, then the application deadline, then the extracted one), `cluster_key` and `is_canonical`.
- `job_state`: lifecycle status, miss counter, `last_seen` and `closed_at`.
- `job_text`: descriptions, department, source, fetch attempts and back-off.
- `job_changes`: an append-only change log, which feeds the market tape and the drawer history.
- Applications: the existing `applications` table plus `applied_date`, `deadline`, `resume_version`, `cover_letter_status`, `referral`, `networking_status`, `next_action_date`, `interview_date`, `outcome`, `category`, `company_key` and `fit`. `application_events` records every status move.
- Networking: `contacts` and `contact_log`.
- User settings: `company_prefs` (watchlist and notes), `saved_searches`, `events` (custom calendar entries), `job_overrides` (deadline correction and hide) and `user_profile`.
- `alert_log` drives per-company cooldowns.

## Closure detection

Closure detection only runs for sources that return a complete listing: Greenhouse, Lever, Ashby, the Jane Street and Marqeta adapters, GitHub listing repos, a paged adapter (Workday, Eightfold, Jibe, UKG, Apple, Google…) that read every posting up to the total its site reported, the whole-listing pages (Atlassian, Workable, Kula, Gem, Jobvite, XML feeds), and boards marked `"complete_listing": true`.

1. One miss marks a role `possibly_closed`.
2. Three misses spanning at least 24 hours mark it `closed`.
3. Seeing the role again marks it `reopened`.

Windowed sources never close roles: these are capped Workday or Oracle result pages, LinkedIn searches and paged APIs.

## Dedupe

The `cluster_key` is `company|normalized title|geo`. Within a cluster, the canonical posting is chosen in this order:

1. Active over closed.
2. Direct ATS over GitHub listings, and GitHub listings over LinkedIn.
3. A posting with a description.
4. The earliest seen.

Lists show only canonical rows. The drawer lists every source as "discovered from".

## Security

- The server binds to loopback by default.
- A Host-header allowlist blocks DNS rebinding.
- Mutations require `Content-Type: application/json` and a same-origin `Origin`. This forces a CORS preflight that the server never approves.
- Request bodies are capped at 200 KB, and static file serving guards against path traversal.
- A strict CSP is set (`script-src 'self'`) and no third-party assets are loaded.
- Binding to a non-loopback address prints an authentication warning.
- Private data (applications, notes, contacts, profile, events) lives only in `jobwatch.db`, which is git-ignored. `state.json` exports only job IDs, alert keys and digest queues.
