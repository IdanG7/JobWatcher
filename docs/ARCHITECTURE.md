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
               │ score_pass: intel.score_job()    — Fit Score 2.0, rescored when the profile changes
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
| `intel/knowledge.py` | Loads and validates `config/*.json`, compiles regex fragments, matches companies and fingerprints the config so facts recompute when knowledge changes. |
| `intel/taxonomy.py` | Hierarchical classification: category, subcategory, secondary categories and confidence, with evidence. |
| `intel/seniority.py` | Finance-aware levels. Analyst is entry level. Associate depends on the category (IB/PE post-MBA or post-analyst vs. entry at banks/asset managers). Stated years of experience can override it. |
| `intel/cycle.py` | Recruiting cycle (`summer_2027`, `new_grad_2027`, off-cycle), graduation windows, deadline extraction with confidence, rolling detection and window status. |
| `intel/eligibility.py` | Degree, GPA, work authorization, sponsorship, citizenship, languages and experience. Fields stay `None` ("Not specified") unless the text states them. |
| `intel/compensation.py` | CAD/USD/GBP parsing. Keeps the original text and labels annualized hourly or monthly pay as an estimate. |
| `intel/skills.py` | Skill extraction with synonym normalization (`DCF` → Valuation, `CapIQ` → Capital IQ). |
| `intel/profile.py` | Candidate profile defaults, merge and validation, and the version hash that triggers rescoring. |
| `intel/scoring.py` | Fit Score 2.0: subscores, penalties, reasons, urgency and badges. |
| `intel/resume.py` | Local PDF/DOCX/TXT extraction, bounded document decoding, structured facts and profile proposals. |
| `intel/matching.py` | Resume shortlist decisions, explicit conflicts and unknown requirements for review. |
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
Private resume data is excluded from portable state and CSV. Cover letters remain
independent, editable per-job drafts.

## Fit Score 2.0

| Subscore | Max | Signal |
|---|---|---|
| Role | 25 | Category/subcategory vs. `target_roles` (with `role_weights`) |
| Stage | 20 | Level/stage vs. `target_stages` |
| Company | 15 | Employer type vs. `target_company_types`, plus a watchlist bonus |
| Location | 10 | Target cities > target countries > remote (if open) |
| Cycle | 10 | `target_cycles`, plus a year match with the graduation year |
| Skills | 10 | Overlap of extracted skills with profile skills |
| Freshness | 10 | Steep decay for competitive categories, gentle decay for others |

Penalties apply only to explicit evidence:

- Seniority: senior −25, experienced −8.
- Geography: −10.
- Cycle year: −10.
- Graduation window: −12.
- Degree: −10 to −20.
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

Schema v4 adds `cover_letters`, keyed by the posting's `board:job_id`. It stores
the letter, candidate-supplied name/background/motivation, and creation/update
timestamps independently of application status. `intel/cover_letter.py` generates
offline templates from supplied facts and posting metadata without reading profile
defaults as candidate experience. There are no external generation calls.

- `GET /api/jobs/:key/cover-letter` returns the saved letter, or `null` when absent.
- `POST /api/jobs/:key/cover-letter/generate` accepts `candidate_name`, `background`
  and optional `motivation`; it returns a preview without storing it.
- `PUT /api/jobs/:key/cover-letter` upserts `content` plus those inputs. Content is
  required; input limits are 160/20,000/3,000/30,000 characters respectively for
  name/background/motivation/content. Unknown jobs return 404.

The drawer escapes saved text, confirms replacement of editor content, disables
editing during requests, and ignores responses for detached drawers. Copy and
UTF-8 text downloads use the current editor. These private records never enter
`state.json`, notification payloads, or opportunity CSV exports.

## Closure detection

Closure detection only runs for sources that return a complete listing: Greenhouse, Lever, Ashby, the Jane Street and Marqeta adapters, GitHub listing repos, and boards marked `"complete_listing": true`.

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
