# Plan — Jobwatch → Finance Recruiting Command Center

## Current architecture (as found, commit 9de2c4e)

| Concern | Where | How it works today |
|---|---|---|
| Ingestion | `watcher.cycle()` | `ThreadPoolExecutor` runs one adapter per board (`ADAPTERS[cfg["ats"]]`). Each returns `{id,title,location,url,company?,posted?,salary?}`. `min_interval` throttles big feeds. |
| Normalization | adapters + `fetch_board` | Minimal: company defaults to board name, `posted` → epoch via `_posted_epoch`. |
| Storage | `watcher.db_open()` | SQLite `jobs` (identity + first/last seen), `job_details` (company/salary/posted), `boards` (health), `alerted`, `pending`, `recent`, `sends`, `kv`, `applications`, `runs`. No migrations: `CREATE TABLE IF NOT EXISTS` only. Jobs are **deleted** 90 days after last_seen. |
| Dedupe | `dedupe_keys()` | Alert-level: canonical URL + `company|title` keys (exact + normalized company) in `alerted` for 90 days; direct boards sorted ahead of LinkedIn. The dashboard dedupes in memory again by URL / company+title. |
| Descriptions | — | **Not fetched at all** (Greenhouse is called with `content=false`). All classification is title-only. |
| Classification | `job_intelligence.role_track/seniority` | First regex match over 10 broad tracks. "finance" is a single bucket. `Analyst` is treated as `experienced`. |
| Scoring | `job_intelligence.analyze_job` | Additive weights starting at 25, clamped to 0–100, up to 5 reason strings. Freshness uses a log decay in days. |
| Alerts | `deliver()`, `flush_feeds()` | Regex subscriber filters → loud capped "apply now" pings for watchlist companies + quiet feed digests. |
| Pipeline | `applications` | One row per `board:job_id`, 6 statuses, notes/next step/due date. |
| Dashboard | `dashboard.py` + `web/` | Stdlib `ThreadingHTTPServer`; the service loads and scores **every** job into memory and filters in Python; 4 views. |
| Actions mode | `.github/workflows/jobwatch.yml` | Fresh DB per run; `state.json` (ids + last_seen + alert keys) on a force-pushed `state` branch. Private data must never land there. |

## Constraints / technical debt

1. No descriptions → description-based taxonomy/eligibility/skills/deadlines need an enrichment step that respects rate limits.
2. Title-only, first-match classification, and `Analyst` is treated as senior-ish.
3. Whole-DB-in-memory dashboard won't scale to 100k+ rows; no SQL pagination.
4. No schema versioning; schema changes must be forward-only `ALTER`s on existing user DBs.
5. Truncated sources (Workday 300 newest, Phenom 100, LinkedIn 24h, Eightfold 100, SmartRecruiters 100, Amazon 100) mean "missing from a poll" ≠ "closed". Closure detection must be limited to complete listings.
6. Imported Actions state has empty titles, so change detection must ignore blank previous values.
7. Mutating endpoints accepted any content type (CSRF from a malicious page via `text/plain`), with no Host check (DNS rebinding).

## Design decisions

- **Keep** the stdlib server, `requests`-only runtime, the adapters, the polling loop, state.json and the alert pipeline. No framework migration: a small router is enough.
- **New `intel/` package** (pure functions, no I/O): taxonomy, companies, seniority, recruiting cycle, eligibility, compensation, skills, locations, scoring. `job_intelligence.py` stays as a compatibility facade.
- **Data-driven config** in `config/`: `taxonomy.json`, `companies.json`, `skills.json`, `locations.json`. Boards remain in `config.json` (Actions + `--check` depend on it) with new optional metadata (`group`, `company`, `priority`, `geography`, `finance`).
- **Precompute, then query in SQL.** `job_intel` stores classification + extraction + fit + explanation per job. It is recomputed when the input hash changes, when the profile version changes, and hourly for jobs whose freshness can still move. Dashboard lists are SQL `WHERE … ORDER BY … LIMIT/OFFSET`.
- **Clusters for cross-source dedupe**: `cluster_key` (company identity + normalized title + geo) plus `is_canonical` (direct ATS > bespoke > repo > LinkedIn; then has description; then earliest). `discovered_from` = the members of the cluster.
- **Migrations** via `PRAGMA user_version` in `db_migrations.py`; forward-only, idempotent, and tested on a v0 database.
- **Closure detection** only for complete-listing adapters: missing once → `possibly_closed`, missing ≥3 polls and ≥24h → `closed`. Reappearing → `active` plus a `reopened` change event. Saved applications are never pruned.
- **Fit 2.0**: 7 capped subscores (role 25, stage 20, company 15, location 10, cycle 10, skills 10, freshness 10) plus explicit penalties. Every point carries a detail string.
- **Profile** stored locally in `user_profile` (DB, gitignored), seeded from `config.json` `profile`. Actions uses the config profile.
- **Alerts**: a new `alert_mode: "fit"` subscriber mode with urgent / high / digest tiers, a per-company cooldown (`alert_log`) and a finance card format. Legacy regex subscribers are unchanged.
- **Frontend**: vanilla ES modules, hash router with state in the URL, SVG charts, no external assets (CSP `self`).

## Steps

1. `db_migrations.py` + tests (v0 → v2 on a legacy DB).
2. `config/*.json` data + `intel/*` modules + unit tests per module.
3. `intel_store.py`: refresh/score/cluster/closure/change detection + tests.
4. Watcher integration: descriptions from list payloads, detail enrichment budget, change/closure tracking, tiered alerts.
5. New finance sources (verified with `--verify`) + source groups.
6. Dashboard API (router, endpoints, CSRF/Host guard) + API tests.
7. Frontend rebuild (8 views, command palette, shortcuts, themes).
8. Seed real data (`--once`), manual browser verification, screenshots.
9. README + architecture docs.
