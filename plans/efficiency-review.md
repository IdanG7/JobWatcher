# Foothold efficiency review: work repeated after updates, and work that runs all the time

Measured 2026-10-30 on copies of the live database on E:, with the installed 0.3.13 code (`09091d6`).
Nothing in the app was changed. The live database was read only through `mode=ro` and the backup API.

## 1. Summary

The app is busy almost all the time. Most of that work changes nothing anyone sees.

- **After an update:** the knowledge-file fingerprint sends every posting back to be read again. On this
  install that is 398,326 postings. 0.3.13 is doing it right now: it started at 16:11, the worker has
  used about 94% of one core since, and it will take about **7.4 hours**. The 0.3.13 change is one
  pharmacist resume pattern, and no posting reads it. Rebuilding facts for 20,000 postings with 0.3.13
  gave byte-identical facts.
- **Every day:**
  - Each worker pass costs ~13 s even when nothing changed. It runs every ~73 s, and after almost every
    source a poll finishes.
  - Every posting is re-scored every hour. About 94% of those re-scores change nothing shown.
  - Each poll spends ~18 s on whole-table scans that find nothing.

Ranked by the computer time each saves on this install (healthcare profile, resume on, 398k postings, a
poll every 5 minutes). "One core" means one of the 12 CPU threads kept fully busy.

| # | Fix | Where | Time saved | Output change | Effort | Risk |
|---|---|---|---|---|---|---|
| 1 | Fingerprint only the parts of the knowledge files that postings read, from parsed JSON | `intel/knowledge.py:546` | Per update like 0.3.13: the whole re-read, **~7.4 h of one core** (~5.2 h without a resume) | none | S | low–medium |
| 2 | Index the backlog, pending-count and score-selection queries (same rows, found through indexes) | `intel_worker.py:45`, `intel_store.py:335`, `:473`, `db_migrations.py` | A pass with nothing to do: 12.9 s → ~1.4 s. **~2.4 h of one core/day** for timer passes alone, up to ~10 h/day counting the passes sources set off (estimated). Plus ~13 s per poll, ~1 h/day | none | S–M | low |
| 3 | Make a needed re-read cheaper: score each batch's own postings, list the backlog once per pass, build facts in several processes | `intel_store.py:307-330`, `intel_worker.py:56` | Per full re-read (FACTS_VERSION bump, real knowledge change): **7.4 h → ~1.5 h** (first two measured per batch, parallel part estimated) | none | M (parallel: L) | low–medium |
| 4 | Re-score a posting when something shown about it can change, not every hour | `intel_store.py:513-530`, `intel/scoring.py:295-418` | **~70 min of one core/day**, **~95 GB/day** less written to the SSD, no 2.5 GB memory spike each hour | changes output: timing only (below) | M | medium |
| 5 | Prune orphans only when a poll deleted postings | `watcher.py:4659-4670` | 4.5 s per poll, **~22 min/day** | none | S | low |
| 6 | Re-pick clusters only when a source's rank changes, not when any source is added | `intel_store.py:435` | Per release that adds sources (0.3.8, 0.3.12): the recluster (55 s), a full re-score (200 s) and a 1.6–1.8 GB WAL | none, once gap 5.8 is fixed | S | low |
| 7 | Cheaper resume-backlog count and nav count | `dashboard.py:1696`, `:699`, `web/js/app.js:171` | 4.5 s per data change → <0.5 s; nav count 3.2 s → ~0.5 s (estimated). Matters while the window is open during polls and re-ranks | none | S–M | low |
| 8 | Polls: conditional requests for GitHub listing files; rewrite only postings that changed | `watcher.py:550`, `:4442-4460` | Estimated **~17 GB/day** of writes (this profile) to ~39 GB/day (Finance only); the GitHub list files downloaded every 5 minutes | changes output: `last_seen` (not shown) in hour steps, if taken that far | M | medium |
| 9 | DB settings: `journal_size_limit`, `PRAGMA optimize` | `watcher.py:3267`, `dashboard.py:311`, `intel_worker.py:56` | ~1.5 GB back on C: after each big write; Overview and Analytics ~25% faster (one run each) | none for the size limit; optimize may reorder postings with equal sort keys, so check it with the board gate | S | low |

Fixes 2, 4 and 5 shrink each other's costs. Fewer pointless commits also mean fewer dashboard
recomputes (section 4.3), which I didn't count separately.

## 2. Measured baseline

**Machine.**
- Windows 11 Pro 10.0.26300, Intel family 6 model 167 (12 threads), 32 GB RAM.
- Copies on E: (Samsung 980 NVMe; it had 151 GB free after the user freed space during this session).
- Python 3.12.12 through uv, with SQLite 3.50.4. The app runs Python 3.14.8 with the same SQLite 3.50.4,
  so absolute times may be 10–20% lower in the app.

**The copy.**
- `c1`: live DB backed up at 16:52 through the backup API from a `mode=ro` connection (16.6 s).
  - DB 4,192,559,104 bytes, WAL 199,807,672 bytes at copy time.
  - 398,329 jobs, 398,326 job_intel, 231,969 job_text, 19,605 job_notes, 1,000 runs.
  - `job_intel` 1.75 GB, `job_text` 1.08 GB, `job_fts` 336 MB, `resume_matches` 167 MB.
  - Free pages: 5,134 (20 MB), so VACUUM would gain nothing.
- Profile: healthcare (the test resume `nadia-ferreira-rn.pdf`), resume matching on.
  - 272 of 1,014 sources polled.
  - All postings first seen between 2026-10-10 and 2026-10-30.
- `c2`: a file copy of `c1`, after its WAL was checkpointed, for the update simulation.
- Both copies use the installed app's code, copied to `E:\efficiency-review\app`. Its knowledge files
  hash to `2ca05a78664b`, the same bytes the live app hashes (installed `config/`, CRLF).
  - At copy time the live DB held 44,472 postings at `2ca05a78664b` and 353,854 still at 0.3.12's
    `f842896753da`. The 0.3.13 re-read was under way.
  - On `c1` those 353,854 were relabelled to `2ca05a78664b` (22.4 s; `prep_copies.py`). That is what
    the re-read will leave. Section 3.1 proves the facts it writes are the same.

**Caveats on timing.**
- The c1 and c2 runs overlapped, and the live app's re-read ran on C: throughout.
- Times are on a busy machine. Repeated timings agree within ~15%.

**Scripts.** All in `E:\efficiency-review\scripts\`, with JSON results in `results\` and run logs in
`logs\`.

| Script | Measures |
|---|---|
| `copy_live.py`, `prep_copies.py` | The copies and their counts (`c1\copy-info.json`, `results\prep_copies.json`) |
| `bench.py` | Shared helpers: per-statement SQL timing, commit count, memory, disk I/O, peak WAL |
| `update_sim.py` | Update simulation on c2: `catchup`, `stale`, `resume`, `noresume`, `compare`, `fullscore`, `fullscore_nr`, `backlog` |
| `recluster.py` | A changed source-rank signature on c2 |
| `steady.py` | Steady state on c1: `passes`, `queries`, `dashboard`, `poll` (offline, network blocked) |
| `whatif.py` | Proposed indexes and queries on c1, rolled back after |
| `pages.py` | Each slow page's SQL, before and after ANALYZE |
| `pragmas.py` | Connection settings |
| `polls.py` | Polling volume from config, `runs` and `source_coverage` |
| `kb_history.py`, `rank_history.py`, `posting_fingerprint.py` | Release history from git |

The live progress and CPU readings in section 3.1 came from one-off read-only queries and Windows
process-time reads. They are quoted where used.

**Hot queries: plans and timings** (3 runs each, nothing pending; `results\steady_queries.json`,
`whatif_stale0.json`):

| Query | Plan today | Time today | With the proposed indexes |
|---|---|---|---|
| Facts backlog SELECT (`intel_store.py:335`) | SCAN jobs, 4 PK lookups per row, TEMP B-TREE for ORDER BY | 3.2–3.9 s (2.6–3.7 s at any backlog size from 0 to 398k) | 0.45 s, same rows in the same order |
| `count_pending_facts` (`intel_worker.py:45`) | SCAN jobs, PK lookup into job_intel | 1.9–2.6 s | 0.42–0.47 s, same count |
| `score_pass` selection (`intel_store.py:521`) | SCAN job_intel, 5 PK lookups and 2 correlated `MIN()` per row | 4.1–5.1 s | 0.000 s, same rows |
| `_resume_status` COUNT (`dashboard.py:1710`) | SCAN jobs, 2 PK lookups | 4.1–4.6 s | 4.8 s; the indexes don't help, it needs rewriting (fix 7) |
| Prune, 5 × `DELETE … NOT EXISTS` plus FTS `NOT IN` (`watcher.py:4662-4669`) | 5 table scans with correlated lookups, FTS scan | 0.5, 0.6, 0.03, 1.7, 0.5, 1.1 s (4.5 s); deletes 0 rows | fix 5 skips them |
| `jobs()` `INSERT INTO _match` (`dashboard.py:722`) | SCAN job_intel with joins, correlated `resume_matches` lookup | 2.8 s (default list), 8.5 s (all boards) | not proposed |
| `repair_workday_posted` / `repair_list_titles` | Searches by board | 0.12 / 0.07 s | — |
| `config_fingerprint()` | — | 1–2 ms | — |
| `IntelStore()` | — | 1.4 s first, 2–3 ms after | — |

Each new index costs 7.5 s to build once and 30 MB in all. There is no `sqlite_stat1`: ANALYZE has never
run. `journal_size_limit` is -1 (none). `cache_size` is the default 2 MB. `mmap_size` asks for 2 GiB.
Asking for 16 GiB still gives 2 GiB, because this SQLite build caps it, so it can't be raised.

## 3. Between updates

### 3.1 The knowledge-file fingerprint (what started this)

**Anchor.** `intel/knowledge.py:546` `config_fingerprint`, read by `_facts_rows` (`intel_store.py:335`,
`i.kb_version != ?`).

**What happens.**
- The fingerprint is a SHA-1 of the raw bytes of `taxonomy.json`, `companies.json`, `skills.json` and
  `locations.json`.
- Any changed byte makes every posting stale, on every board. That includes line endings: the shipped
  builds hash CRLF bytes.
  - I reproduced all four fingerprints the live DB has carried from git with CRLF: v0.3.9
    `fdc7124ccfed`, v0.3.12 `f842896753da`, v0.3.13 `2ca05a78664b`.
  - The working tree hashes to `bc2f3be9d1d7`, because it has 71 LF lines among CRLF lines.
- Each stale posting gets:
  - its facts rebuilt;
  - 33 `job_intel` columns rewritten;
  - its FTS row deleted and re-inserted;
  - `profile_version=NULL`, so it is re-scored.

**What each release changed, by key path** (`kb_history.py`):

| Release | Changed in the knowledge files | Full re-read needed? |
|---|---|---|
| 0.3.8 | 500 companies, 78 types, tech families' subcategories, priors | yes: postings read companies and subcategories |
| 0.3.9 | 60 skills, 6 skill groups | yes: postings read skills |
| 0.3.10, 0.3.11 | nothing | no re-read happened |
| 0.3.12 | Healthcare family, 209 companies, 58 skills, licences, program windows, tracks | yes; FACTS_VERSION 10→11 too |
| 0.3.13 | one leaf: the pharmacist licence's `resume` patterns | **no**: only resume reading reads it |

**Measured cost.**
- **Live, the real 0.3.13 update** (read-only `SELECT kb_version, COUNT(*)` on the live DB):
  - 44,472 postings re-read by 16:52 and 59,991 by 17:15:39, after a 16:11 start.
  - That is 15.6 postings/s on average, and 11.0/s while my copies were also busy.
  - The worker has used 3,833 s of CPU in about 68 minutes (~94% of a core). In the same time the
    server used 1,325 s (32% of a core), recomputing pages as the data changed (section 4.3).
- **Simulation** on c2, every posting marked stale (`update_sim.py stale` then `resume`): 20,000
  postings, the worker's own path with the resume on.
  - 1,341 s wall, 1,164 s CPU: **14.9 postings/s**.
  - 193 commits (33.8 s in commits), peak WAL 57 MB, peak private memory 63 MB.
  - It processes Finance postings first: `ORDER BY is_finance DESC`.
  - Where the time went:

    | Step | Time | Per posting |
    |---|---|---|
    | `build_facts` | 871 s | 43.5 ms |
    | Backlog SELECT, run 40 times | 187 s | 4.7 s each |
    | Whole-table score selection after every batch, 41 times | 210 s | 5.1 s each |
    | Scoring and resume matching for 26,207 postings | 2.3 s | — |
    | FTS writes, `job_changes` scans, commits | ~51 s | — |
  - Batches alternate between ~23 s and ~40 s. The 40 s ones are those where the score pass found work.
- **Extrapolated to 398,326 postings** (sample × 19.9, a sample was taken as the brief asks):
  - with the resume: **~26,700 s ≈ 7.4 h**;
  - without it: 20,000 in 924 s, 856 s CPU (21.7 postings/s), so **~5.1 h**. Batches take 12–33 s.
    (`update_noresume.json`)
- Then one full re-score of every posting:
  - with the resume: 200 s, 160 s CPU, 801 commits, peak private memory 1.78 GB, **peak WAL 1.75 GB**
    (`update_fullscore_resume.json`);
  - without it: 142 s, 121 s CPU, peak private memory 1.59 GB, peak WAL 1.75 GB
    (`update_fullscore_noresume.json`).

**By design?** Partly.
- Facts do depend on these files, so a change that postings read must re-read them.
- Hashing bytes rather than content, and hashing parts no posting reads, is not by design. Those parts
  are: every `_readme`; `tracks.*.resume`; each board's `program_windows` (Calendar only); and each
  licence's `resume` and `degree` patterns (resume reading only, `intel/licences.py:102-131`).

**Proposed change.**
- Compute the fingerprint from parsed JSON (`json.dumps(sort_keys=True)`), leaving out exactly the paths
  above. The prototype is `posting_fingerprint.py`. It gives:
  - 0.3.7 `827f481919ce`;
  - 0.3.8 `b6bd64facaaa` (changed);
  - 0.3.9 `d17a65c22931` (changed);
  - 0.3.10 and 0.3.11 unchanged;
  - 0.3.12 `4407d7a29fea` (changed);
  - **0.3.13 `4407d7a29fea`, unchanged**.

  So it re-reads exactly when 0.3.8, 0.3.9 and 0.3.12 needed it, skips 0.3.13, and no longer depends on
  line endings.
- Installs already on 0.3.13 hold `2ca05a78664b`. The change must store the new kind of fingerprint
  without one more re-read.
  - A one-time migration rewrites `kb_version` to the new value for rows at the old one.
  - That costs one UPDATE of every row: 22–25 s measured here, holding the write lock (see gap 5.5).
  - It is safe only because the old fingerprint's inputs and the new one's agree on what postings read.
  - Better: keep `kb_version` as is, and add a `kv` entry that maps "old raw fingerprint → posting
    fingerprint". A posting is stale only if its mapped posting fingerprint differs. No rows are written.

**Why output stays identical.**
- Facts are a function of the posting, the source settings and the parts of the knowledge files postings
  read. Leaving out parts no posting reads can't change a posting's facts.
- Measured for 0.3.13 (`update_sim.py compare`, `results\update_compare.json`):
  - 20,000 postings rebuilt with 0.3.13's code and knowledge on c2 were compared with what the live app
    had stored: 0.3.12's facts for all but those the live re-read had already done.
  - Result: `facts` JSON, `input_hash` and all 33 facts columns are identical on all 20,000.
  - `is_canonical` and `cluster_key` are identical, and `resume_matches` are identical on all 20,000.
  - Only score-time fields differ, because c2 scored later:
    - `posting_age_hours` on 19,999;
    - freshness or reason text on 858 and 195;
    - "UPDATED" badges on 90, as the 48-hour change window moved;
    - fit on 3, one freshness step each.
  - The 20,000 are the first by the code's own order, so all Finance postings come first.

**Tests that would prove it.**
- A unit test that mutates each left-out path in a copy of `config/` and asserts:
  - the posting fingerprint is unchanged;
  - `build_facts` gives identical facts for a fixed set of postings from every board.
- A test that mutates any other leaf and asserts the fingerprint changes.
- The board gate (`tools/board_gate.py snapshot` + `compare`) on a copy: Finance's 21,951-posting
  baseline and every other sample profile must come back identical.

### 3.2 Making a needed re-read cheaper

**Anchors.**
- `intel_store.py:325`: after every 500-posting facts batch, an unscoped `score_pass` runs if a resume
  exists.
- `intel_store.py:335-353`: `_facts_rows` re-runs the full backlog SELECT for every batch.
- `intel_worker.py:56`: everything runs in one process.

**What happens and measured cost** (per batch, from the 20k sample):
- The score selection scans all of `job_intel`, with two correlated `MIN()` per row, to find ~500 rows:
  5.1 s × 797 batches ≈ **70 min per full re-read** with a resume.
- The backlog SELECT scans and sorts all of `jobs` to take the next 500: 3.4–4.7 s × 797 ≈ **45–62 min
  per full re-read**. That holds whatever the backlog size (`update_backlog.json`).
- `build_facts` runs in one process: 43.5 ms per posting, **4.8 h per full re-read**, on one of 12 threads.

**By design?** No. The 500-posting batches are for lock fairness, and none of these costs is needed for that.

**Proposed change.**
- (a) After each batch, call `score_pass(keys=batch)`, and leave the one unscoped `score_pass` at the end
  of `refresh` (`intel_store.py:616`).
- (b) Read the ordered backlog keys once per pass. Then fetch each batch's columns by key, with the same
  batches in the same order.
- (c) Build facts in N worker processes, as `tools/board_gate.py` already does (`--workers`), and keep the
  writes in the worker's single connection.

With fix 2's indexes, (a)'s selection drops to ~0 anyway.

**Saved (estimated, from the measured per-batch costs).**
- (a) −70 min and (b) −45–60 min per full re-read with a resume.
- (c) With 6 processes: 4.8 h → ~55–65 min, assuming per-process overhead of ~10% (not measured).
- Together: 7.4 h → **~1.5 h**.

**Why output stays identical.** The same `build_facts` and `score_job` run on the same inputs, in the
same batch order.
- (b) still picks up postings that arrive mid-pass on the next pass. The poll scores its own new postings
  at once (`watcher.py:4532`), so alerts don't wait.
- (c) changes only which process computes a facts dict. The dict is written by the same code.

**Test.** The board gate before and after on a copy with every posting stale, including the Finance
baseline. Also diff `job_intel` and `resume_matches` row by row, timestamps aside.

### 3.3 Source-rank signature

**Anchor.** `intel_store.py:435` `recluster_if_ranks_changed`.

**What happens.** The signature lists every source's rank. Adding or removing any source changes it, and
then every cluster is re-picked and every posting re-scored (`:444`, one UPDATE of every row).

**Measured cost.**
- History (`rank_history.py`): 0.3.8 added 541 sources and 0.3.12 added 219. **No existing source changed
  rank in either.**
- Re-picking every cluster on c2: **54.8 s wall, 40.1 s CPU, peak WAL 1.76 GB** (`recluster.py`,
  `update_recluster.json`). That's 308,912 clusters.
- The re-score after it: 200 s with the resume (3.1).
- The `UPDATE … SET profile_version=NULL` over 398k rows: 23 s with the write lock held, and a 1.56 GB
  WAL (measured for the same-sized UPDATE in `update_sim.py stale`).
- Today this was always masked: both releases also re-read every posting. Fix 1 unmasks it.

**By design?** The aim is by design: re-pick canonical rows when a rank changes. Re-picking for added
sources is not. A new source has no postings at upgrade time, so it can't move a canonical flag.

**Proposed change.** Keep the stored signature as {source: rank}. Re-pick only the clusters holding
postings from sources whose rank differs from the stored map, or that are gone from it. Re-score only
those clusters' postings.

**Why output stays identical.** A cluster with no posting from a changed source has members whose
`rank()` keys are all unchanged, so `max(rows, key=rank)` picks the same row, **if the stored picks are
current**. They aren't quite.
- The full re-pick on c2 moved 496 canonical flags.
- A read-only check on c1 (`canonical_drift.py`) found 246 clusters (492 flags) whose stored pick
  differs from a fresh one. In 238 of them, the stored canonical posting is "possibly closed" while an
  active duplicate exists.
- That is gap 5.8. Today's full re-picks quietly repair it. Fix gap 5.8 first, and fix 6 is identical.

**Test.** On a copy, add a source to the config. Assert no `is_canonical` changes, nothing is set to
re-score, and the board gate is identical. Change one source's `indirect_links`, and assert only its
clusters are re-picked, matching a full re-pick.

### 3.4 Profile version, RULES_VERSION and FACTS_VERSION

**Anchors.** `intel/profile.py:158` `RULES_VERSION`, `:161` `profile_version`; `dashboard.py:331`
`_prune_profile`; `intel/facts.py:25` `FACTS_VERSION`.

**What happens.**
- `profile_version` hashes the merged profile: `DEFAULT_PROFILE`, config `profile` and saved choices,
  plus `RULES_VERSION`. Any change re-scores every posting.
- From git, v0.3.7 to v0.3.13:
  - `DEFAULT_PROFILE` and `merge_profile` never changed.
  - `RULES_VERSION` was added in 0.3.11 (re-score only) and raised to 3 in 0.3.12.
  - `_prune_profile` changes the profile only when a release removes an option the profile picked. No
    release in this range did that for this profile.
- FACTS_VERSION 10→11 in 0.3.12 re-read every posting. That is by design: facts carry `"v"`, and every
  facts dict changed.

**Measured cost.** A score-only full re-score is 200 s with the resume, 1.78 GB peak memory and a 1.75 GB
WAL. This is small next to re-reads.

**Proposed change.** None for speed. For FACTS_VERSION, fix 3.2 makes the needed re-read ~5× cheaper.

Limiting a FACTS_VERSION bump to some boards isn't safe as the code stands. The version is global, and
the facts code doesn't record which boards a change affects. A per-board facts version would be its own
design, so I'm not proposing it. Fix 3.2's "write only if changed" variant is the safe way to spare
unchanged postings:
- compare the new facts, without `"v"`, to the stored ones;
- if they're equal, update only `facts_version`/`kb_version` and keep the fit (no re-score, no FTS
  rewrite).

That would have spared Finance's postings in 0.3.12-like releases. Effort M.

**Test.** For write-only-if-changed: the board gate, and assert that a stored row with unchanged facts
keeps `fit`, `fit_detail` and `resume_matches` byte for byte.

### 3.5 The score-only re-score shows no progress

**Anchor.** `intel_worker.py:45-53` and `:67-75`.

**What happens.**
- `count_pending_facts(fits=True)` counts facts work, plus `fit_detail IS NULL`. A RULES_VERSION bump or
  a recluster sets `profile_version=NULL`, but leaves `fit_detail` filled. So the count is 0 and the bar
  shows nothing.
- With the resume on, `_resume_status` shows its own pending count. Without one, nothing does.

**Measured cost.** 200 s with no countdown on this install.

**Proposed change.** Count `profile_version IS NULL OR profile_version != current` too. With fix 2's
`profile_version` index, that's ~0 s.

**Why output stays identical.** It only reports, nothing else reads it.

**Test.** Set `profile_version=NULL` on a copy, then assert `/api/status` reports `ranking.total` =
row count and that it counts down.

## 4. Steady state

### 4.1 Ranking passes

**4.1a A pass when nothing changed.**
- **Anchor.** `intel_worker.py:168` `Worker.run`, which runs a pass every 60 s and on every kick.
  `dashboard.py:2589` kicks after every source that finishes OK.
- **What happens.** Each pass:
  - counts pending twice: `refresh_database` counts first, then `report(0)` sees `0 >= 0` and counts again
    (`intel_worker.py:74`);
  - runs the backlog SELECT;
  - runs the score selection.

  All of these are whole-table scans.
- **Measured** (`steady.py passes`, pass 2): **12.9 s wall, 11.0 s CPU, 3.7 GB read through the file
  system, 0 rows.**
  - count ×2: 4.6 s;
  - score selection: 4.6 s;
  - backlog: 3.5 s.
- **Passes per day** (estimated from the copy's last 288 `runs` rows, at 12.9 s per pass): ~762 timer
  passes. Polling takes 36% of the time, and during it sources finish faster than a pass ends, so passes
  run back to back: up to ~2,540 more. Total ~760–3,300 passes, **~2.7–11.8 h of one core per day**.
- **Proposed change (fix 2).** Indexes on `job_intel(kb_version)`, `(facts_version)`,
  `(profile_version)`, `(scored_at)`, plus partial indexes `WHERE input_hash IS NULL` and
  `WHERE fit_detail IS NULL`. Write the three queries as a UNION of index lookups, as in `whatif.py`.
  - Skip the second count when the first was 0.
  - The "jobs without a job_intel row" branch still scans `jobs`: 0.44 s.
  - A trigger-fed queue table would make it ~0. It's optional.
- **Measured with the proposal** (`whatif.py`, rolled back):

  | Query | Today | Proposed |
  |---|---|---|
  | Backlog SELECT, nothing pending | 3.2–3.9 s | 0.45 s |
  | Backlog SELECT, 20k pending | 4.3–4.9 s | 1.1 s |
  | Pending count | 2.0 s | 0.45 s |
  | Score selection | 4.1 s | 0.000 s |

  A pass drops to ~1.4 s, so the timer passes alone save ~2.4 h of one core per day.
- **Why output stays identical.**
  - `whatif.py` checked each proposed query against today's on the same data: same rows, in the same
    order for the backlog, and the same count. I checked with nothing pending and with 20,000 pending.
  - `kb_version < ? OR kb_version > ?` keeps `!=`'s NULL behaviour.
  - Lists don't filter on these columns, so the new indexes can't change their plans or the order of ties.
- **Test.**
  - A property test on a temp DB with rows in every state (no intel row, `input_hash` NULL, old
    `facts_version`, old `kb_version`, `fit_detail` NULL, `profile_version` NULL or old, `scored_at` old,
    with and without recency). Assert the old and new queries return identical rows in identical order.
  - Then the board gate on a copy.

**4.1b The hourly re-score.**
- **Anchor.** `intel_store.py:513-530`: `scored_at < now-3600` with `posted` in the last 32 days, OR
  `first_seen` in the last 32 days, OR a deadline ahead.
- **What happens.** `first_seen` is when this install first saw a posting. The install is 20 days old, so
  **all 398,326 postings** meet the hourly condition, including 203,697 posted more than 32 days ago.
  Each hour every posting is re-scored at once, about an hour after its last re-score.
- **Measured** (`steady.py passes`, passes 1 and 3; pass 3 has the clock an hour on):

  | | Pass 1 (catch-up) | Pass 3 (an hour later) |
  |---|---|---|
  | Postings re-scored | 345,668 | 398,326 |
  | Wall / CPU | 184 s / 141 s | 186 s / 146 s |
  | Commits | — | 802 |
  | Written to disk | — | **4.2 GB** |
  | Peak private memory | 1.55 GB | **2.46 GB** |

  - Per day: **~74 min of one core and ~100 GB written**.
  - Of the 398,326 re-scored in pass 3, 25,427 (6.4%) changed anything other than `posting_age_hours`.
    Those changes were:
    - freshness or reason text: 24,012;
    - badges: 2,904;
    - fit: 1,122;
    - `posted_ref`: 21.
  - Another 307,007 changed only `posting_age_hours`. It isn't shown anywhere. It is read only by
    `alert_tier` (`watcher.py:3864`), for postings scored moments before.
  - 65,892 changed nothing at all.
- **By design?** Fits do change with time, so re-scoring is by design. Re-scoring every posting every
  hour to catch the 6% whose shown values move is not.
- **Proposed change (fix 4).**
  - Have `score_job` also return `rescore_at`: the earliest time any shown value can change. That is the
    next of:
    - the freshness curve's next step (`STEEP`/`GENTLE`);
    - the `_age_text` boundary (hourly under 48 h, then daily);
    - the NEW/TODAY/48H badge ages (24 h, 48 h);
    - urgency's 12 h and 48 h;
    - the stale penalty at 45 days;
    - the next UTC midnight when a deadline or `days_left` applies;
    - the UPDATED badge's 48-hour window ending.
  - Store `rescore_at` with an index, and select `rescore_at <= now` in place of the hourly and daily
    branches. Keep a daily full pass as a safety net.
- **Saved (estimated, from pass 3's changed rows).** ~25k re-scores an hour instead of 398k: ~12 s/h
  instead of 186 s/h, ~70 min of one core/day, ~95 GB/day fewer writes. The hourly 2.5 GB spike goes,
  along with the ~12 rounds of page recomputes each hourly pass triggers (4.3).
- **Changes output: timing only.**
  - Each shown value (fit, badges, urgency, window, reasons, subscores) updates within one pass (≤ ~73 s)
    of its boundary. Today the lag is up to an hour.
  - `posting_age_hours` in `fit_detail` (not shown) refreshes only when the posting is re-scored.
  - The score function and every fit are unchanged at any moment they are computed.
- **Test.**
  - For a sample of stored postings and clock offsets from 1 minute to 61 days: whenever
    `now < rescore_at`, `score_job(now)` must equal the stored result except `posting_age_hours`.
  - The board gate at a fixed `--epoch`.

**4.1c The resume backlog count.**
- **Anchor.** `dashboard.py:1696` `_resume_status`.
- **What happens.** It recounts whenever `PRAGMA data_version` moved, which is after any commit from
  another connection. So during a pass or a poll, nearly every `/api/jobs` recounts.
- **Measured.**
  - The count itself: **4.1–4.6 s**.
  - `jobs()` default: 3.3 s with the count cached and 7.7–8.6 s when it recounts.
  - The nav count: 3.2 s and 7.6–8.2 s.
- **Proposed change.** Count with indexed branches:
  - `resume_matches` rows whose `profile_version` differs (the existing index `resume_matches_filter`
    leads with it);
  - `job_intel` rows with `profile_version` NULL or different (fix 2's index);
  - `facts_version` different (fix 2's index);
  - jobs with no `job_intel` row.

  Estimated <0.5 s, not measured.
- **Why output stays identical.** It's the same count. Assert it equals today's query on copies in every
  state.

### 4.2 Polls

**Anchors.** `dashboard.py:556` `auto_poll`, `watcher.py:4366` `cycle`.

**Measured** (`polls.py`; `steady.py poll`):
- **Cadence** (`runs`, last 1,000 polls, 2026-10-25 to 30): a poll every 300 s (median), 288 a day lately.
  Median duration 154 s, 90th percentile 555 s, 36–49% of all time spent polling. Median ~20 sources OK
  per poll lately, with ~250 not due.
- **Sources and listing requests per hour.** Estimated: pages per listing come from each fetcher's page
  size and the source's last fetched count. Workday 20, Eightfold 10, Dayforce 25. Oracle 25, iCIMS 20,
  SuccessFactors 25 and Avature 20 are guesses. Greenhouse, Ashby, Lever and GitHub lists take one
  request.

  | Profile | Sources | `min_interval` 0 / 300–900 / 1,800 / 3,600+ | Listing requests/h | Postings rewritten/h |
  |---|---|---|---|---|
  | This copy (healthcare) | 272 | 5 / 14 / 206 / 47 | ~4,400 | ~307k |
  | Finance only | 347 | 146 / 39 / 123 / 39 | ~10,300 | ~704k |
  | Every board | 1,004 | 146 / 39 / 714 / 105 | ~17,600 | ~897k |

  The biggest are JPMorgan (Oracle, 7,263 postings, ~580 requests/h) and Citi (Workday, 4,115, ~410/h).
  Plus up to 60 description fetches per poll (`description_budget`).
- **One offline poll** (`steady.py poll`): 200 sources due, every listing replayed as stored (no
  changes), network blocked, descriptions and alerts stubbed.
  - **25.7 s, 21.0 s CPU, 212 commits, 189 MB written**, peak WAL 17 MB.
  - Of the 25.7 s: two whole-table score selections 10.4 s, backlog SELECT 3.5 s, prune 4.5 s. That's
    ~18 s of scans that found nothing.
  - Writing 80,655 unchanged postings back took ~3 s of SQL, but 2.3 KB of disk writes each.

**4.2a The poll's fixed scans.**
- **Anchors.** `watcher.py:4533` and `:4613-4614`: an unscoped `score_pass` after the new postings, then
  backlog `facts_pass(5000)` and `score_pass`.
- **Measured.** 13.9 s per poll (score selections 10.4 s, backlog 3.5 s), **~67 min/day** at 288 polls.
- **Change.** Fix 2's indexes make them ~0.5 s: ~13 s saved per poll, ~1 h/day. The same queries, so the
  output is identical.

**4.2b The prune (fix 5).**
- **Anchor.** `watcher.py:4659-4670`.
- **What happens.** Every poll runs `DELETE … NOT EXISTS` over five tables and `DELETE FROM job_fts
  WHERE rowid NOT IN (…)`.
- **Measured.** 4.5 s per poll, 0 rows deleted, **~22 min/day**.
- **By design?** Only orphans need deleting.
  - Orphans appear when `jobs` rows go: here, the 90-day `DELETE FROM jobs`.
  - `forget_boards` (`intel_store.py:151`) cleans its own.
- **Change.** Run the five deletes and the FTS delete only when the `DELETE FROM jobs` above them
  removed rows. Delete by those keys, not by scanning. Keep a full sweep once a day as a safety net.
- **Why output stays identical.** Child rows can only be orphaned by deleting `jobs` rows. Grep shows
  only `cycle` and `forget_boards` do that.
- **Test.** On a copy, run a cycle with and without the change, after ageing some postings past 90 days.
  Assert both copies are identical, table by table.

**4.2c Unchanged listings are downloaded and written back in full.**
- **Anchors.**
  - `watcher.py:550` `fetch_github_listings`, and every fetcher: no `If-None-Match` or
    `If-Modified-Since` anywhere.
  - `watcher.py:4436-4460`: the `jobs` and `job_details` UPSERTs rewrite every posting of a due source,
    since `last_seen` always changes. That also moves the `jobs_last_seen` index entry.
- **Measured.** 189 MB written for 80,655 unchanged postings (2.3 KB each). Estimated from the
  rewritten-per-hour table: **~17 GB/day** for this profile, ~39 GB/day Finance only, ~50 GB/day for every
  board.
- **Proposed change.**
  - (a) Send `If-None-Match` with the stored ETag for GitHub raw files (and sources that send ETags). On
    304, treat the listing as unchanged: update `last_poll`/`last_ok` and skip the posting writes.
  - (b) Add `WHERE` clauses to the UPSERTs so unchanged rows aren't rewritten. Update `last_seen` only
    when it is ≥ 1 h old. Lifecycle closure needs `CLOSE_AFTER_HOURS=24`, and the prune needs 90 days.
- **Output.**
  - (a) is identical: a 304 means the same bytes, which give the same postings.
  - (b) **changes output**: `last_seen` in `/api/jobs` JSON (not shown on screen or in CSV) moves in
    steps of up to an hour. Closure timing can lag by up to an hour.
  - Without the `last_seen` step, (b) saves only the `job_details` rewrites.
- **Test.** Replay a poll twice on a copy. Assert the second writes ~0 rows and that every table
  matches the first run's, except `last_seen` within an hour.

### 4.3 Dashboard

**Anchors.**
- `dashboard.py:475` `keep_ready`; `:699` `jobs()`; `:932` `overview()`; `:1530` `analytics()`.
- `web/js/app.js:461`: `refreshStatus` every 2 s and `refreshNav` every 120 s, neither checking
  `document.hidden`.
- `app.js:227`: the current view refreshes every 30 s while busy.

**Measured, one page on a cache miss** (`steady.py dashboard`, `pages.py`; resume count cached unless
noted):

| Page | Time | Where it goes |
|---|---|---|
| Opportunities, default | 3.1–3.6 s (7.7–8.6 s when the resume count recounts) | `_match` INSERT 2.8 s; facets ~0.3 s |
| Nav count (per page 1, no facets) | 3.1–3.3 s (7.6–8.2 s) | the same `_match` INSERT over every candidate |
| Opportunities, all boards | 9.7–10.3 s | `_match` 8.5 s |
| Narrow search ("registered nurse", Toronto) | 0.26–0.29 s | — |
| Overview | 7.8–15.6 s | five COUNTs 8.8 s; pending count 2.2 s |
| Analytics (30 days) | 17.7–19.2 s | one CTE 7.8 s; three COUNTs 4.4 s |
| Companies | 5.2–5.3 s | one GROUP BY |
| Sources | 3.4–4.0 s | one GROUP BY over `job_intel` |
| `/api/status` | 1 ms (also during a 272-source poll) | — |
| `JobwatchService()` start-up | 1.45 s | — |

**What happens.**
- After any background commit, `keep_ready` recomputes every page asked for in the last 10 minutes and
  older than 15 s, newest first. One round of the main pages is ~40 s, so during polls and re-ranks it
  runs back to back.
- The page timers keep the nav count and the current page "asked for" while the window is open.
- Live, since the update: the server process used 1,325 s of CPU in ~68 min (32% of a core).

**By design?** Keeping pages ready is by design (d39e39c). Recomputing them for commits that changed no
score is the waste, so fixes 2 and 4 cut it at the source.

**Proposed change.**
- Fix 7: the cheaper resume count (4.1c).
- `refreshNav`: ask for a count-only answer instead of building `_match` over every candidate. A
  `count=1` flag would run `SELECT COUNT(*)` with the same WHERE. Estimated ~0.5 s.
- Skip `refreshStatus`/`refreshNav` while `document.hidden`. The `overview` timer already checks it.
- Not proposed: lengthening `CACHE_REFRESH_SECONDS`. That changes how fresh pages are.

**Why output stays identical.** The same WHERE gives the same count. The hidden check delays a hidden
window's nav count until it is shown again, then refreshes it at once.

**Test.** Assert `jobs({..., count: 1}).total == jobs({...}).total` across the saved searches and the
board gate's profiles.

### 4.4 Database

**Measured** (`steady.py queries`, `pragmas.py`, `pages.py`):
- No `sqlite_stat1`. `ANALYZE` took 2.2 s on c1. After it (one run each): Overview 15.6 → 11.6 s,
  Analytics 19.0 → 13.9 s, Companies 5.3 → 4.6 s, Sources 3.8 → 3.1 s, all-boards list 9.2 → 10.4 s.
  That's noise or slightly worse.
- `journal_size_limit` -1: the WAL never shrinks after a peak. One 398k-row UPDATE made a 1.56 GB WAL. A
  full re-score made 1.75 GB. The live WAL was ~1.5 GB before (brief) and 200 MB at my copy.
- `mmap_size` is capped at 2 GiB by this SQLite build. The 4.2 GB file means 3.7 GB of `read()` per idle
  pass, which is file-cache copies, not disk.
- A 64 MB `cache_size`: 0–10% on the pass's scans.
- Free pages 0.5%: VACUUM is not worth it.

**Proposed change (fix 9).**
- `PRAGMA journal_size_limit=67108864` on every connection that writes (`db_open`, `connect`,
  `refresh_database`). After a checkpoint the WAL truncates to ≤64 MB, giving ~1.5 GB back on C:, which
  is 95% full.
- `PRAGMA optimize` once a day and at close.

**Output.**
- The size limit is identical: only the WAL file's size changes.
- `optimize`/`ANALYZE` returns the same rows, but the planner may then order postings with equal sort
  keys differently, e.g. the same fit and same `posted_ref`. **Run the board gate's order compare before
  taking it.** If ties move, add a final tiebreak (`i.rowid`) to `SORTS` first. That itself changes the
  order of tied postings once.

**Test.** The board gate compare (order included) before and after ANALYZE on a copy.

**Bigger, not proposed now.** `job_intel` rows average 3.3 KB, because `facts` (1.8 KB) and `fit_detail`
(1.1 KB) sit in each row. So every list, count and facet reads 1.75 GB. Moving those two to a side table
would cut those scans ~10×. That's estimated, from 1.75 GB → ~150 MB. It's a migration (L), so it belongs
after fixes 2 and 4.

## 5. Correctness gaps found along the way

1. **Source settings that feed facts are in neither hash.**
   - `company_key`, `company_type` and `ats` (`intel/companies.py:40-61`) and the `_section` header
     (`intel_store.py:367`) feed `build_facts`. They are in neither `input_hash` (`intel/facts.py:38`)
     nor `kb_version`.
   - When `upgrade_sources` (`portable_start.py:32`) changes one, stored facts stay stale.
   - Release history: no release from 0.3.8 to 0.3.13 changed them. `source_defaults_history.json`
     shows 54 sources whose `company_key` changed earlier (22,684 postings on this copy), and 2 whose
     `ats` changed.
   - Today the full re-reads hide it. **Fix 1 removes that cover.**
   - Fix: hash each source's fact-relevant settings into a per-source fingerprint, stored in `kv`. A
     changed source re-reads only its own postings.
2. **Scoring and matching changes depend on remembering RULES_VERSION.**
   - `scoring.py` changed in 0.3.8 and `matching.py` in 0.3.8, 0.3.9 and 0.3.11. RULES_VERSION first
     existed in 0.3.11.
   - Only the knowledge re-reads re-scored those installs. With fix 1, a forgotten bump leaves fits and
     `resume_matches` stale.
   - Fix: a test that hashes the source of `intel/scoring.py` and `intel/matching.py` (and what they
     import for scoring), and fails unless `RULES_VERSION` changed with it. Or put that hash in
     `profile_version`.
3. **A licence-pattern change doesn't re-read the saved resume.**
   - 0.3.13 changed resume patterns, which matter for resume reading. The stored resume
     (`candidate_resume.parsed`) is only read at upload, so the change takes effect on the next upload.
   - Meanwhile every posting was re-read for it.
   - Fix (separate): re-parse the stored resume text when the resume-side fingerprint changes.
4. **The fingerprint depends on line endings.** A build or checkout with different git `autocrlf` gives
   a new fingerprint for the same content, and a full re-read. The working tree here hashes
   `bc2f3be9d1d7`, against the build's `2ca05a78664b`. Fix 1 removes it.
5. **One-statement whole-table UPDATEs hold the write lock past the poll's busy timeout.**
   - `recluster_if_ranks_changed` (`intel_store.py:444`) and the `score_pass` repair (`:508`) run
     `UPDATE job_intel SET profile_version=NULL` over every row. That took 23 s here.
   - `db_open`'s `busy_timeout` is 15 s, so a poll writing during it can fail with "database is locked".
     Not reproduced.
   - Fix: update in chunks of ~20k rows with commits between.
6. **Score-only re-scores show no progress** (3.5).
7. **`posting_age_hours` is written for every posting every hour**, but read only for new postings'
   alerts (4.1b).
8. **Canonical picks go stale when a member's status changes.**
   - `update_lifecycle` (`intel_store.py:170`) marks postings possibly closed, closed or reopened. It
     re-scores them, but never re-picks their cluster. Only a facts re-read or a full re-pick does.
   - On c1, 238 clusters show their "possibly closed" copy while an active duplicate from another source
     sits hidden as non-canonical (`canonical_drift.py`).
   - When that copy turns closed, the list filter (`job_query.py:98`) hides the whole cluster, though an
     active duplicate exists. There are 0 such clusters on this copy. The full re-reads after each update
     have been repairing them, and fix 1 removes that.
   - Fix: collect the cluster keys of postings whose status changed in `update_lifecycle`, and
     `recluster()` them, as `_facts_rows` does for its batch.

## 6. Not checked, or unsure

- **No live network poll.** As the brief asked, I sized polling from code, config and `runs` instead.
  Page sizes for Oracle, iCIMS, SuccessFactors and Avature are guesses. So are the GitHub list files'
  sizes (the code comment says ~11 MB) and how many sources send ETags.
- **Passes set off by finished sources** (~2,540/day) come from a model of the `runs` rows: passes run
  back to back while polls run, at the measured 12.9 s each. Not measured on the live app. Timer passes
  (~760/day) use the same costs.
- **Parallel facts building** (fix 3c) is estimated. I didn't build it.
- **The `rescore_at` saving** (fix 4) is estimated from one hour-on pass: 25,427 rows with shown changes.
  Hours near midnight UTC (deadline day changes) or many fresh postings would be higher.
- **The cheaper resume count** (4.1c) and the nav count (4.3) are estimated, not prototyped.
- **The Finance gate** (`tools/board_gate.py`) was not run. Nothing here changes knowledge files or code.
  The 20,000-posting facts comparison (3.1) is the evidence for 0.3.13. Every fix above names the gate as
  its proof.
- **The browser side** (rendering, JS memory) wasn't profiled. Only the requests it makes were.
- **Python version.** Python 3.12 (uv) here, against the app's 3.14.8. Same SQLite (3.50.4).
- **Contention.** Measurements overlapped each other and the live app's re-read. Medians of 3 runs are
  quoted where repeated.

## 7. Fixes 1–6 built on `perf/efficiency`: measured

Fixes 1–6, with gaps 1, 2, 8 and 9 (found on the way, below), are in the `perf/efficiency` worktree. Each
has tests; the suite passes (790). Measured
2026-10-30 23:00 on a fresh copy of c1 with the branch's code, against the 0.3.13 numbers above. Four
unrelated processes held ~4 of the 12 cores during both sets of numbers.

| What | 0.3.13 | perf/efficiency |
|---|---|---|
| First start after the update from 0.3.13 | — | migration 8 s; then one 223 s pass: the one-time input check re-reads the **750** postings with stale facts (gap 9) and every posting is re-scored once |
| A pass with nothing to do | 12.9 s | **1.2 s** |
| The pass an hour later | 186 s, all 398,326 re-scored | **22 s**, 53,392 re-scored |
| Offline poll | 25.7 s: 200 sources, 80,655 postings | 14.3 s: 272 sources, 136,796 postings, including the once-a-day orphan sweep (4.4 s); an earlier run took 23.1 s, its sweep 8.5 s |
| Re-reading postings | 14.9 postings/s | **68 postings/s** (6 worker processes; 39,404 postings) |

**Placement** (no role in the wrong board, category, filter or place).
- 39,404 postings, up to 50 from each of the 980 sources, re-read through the branch's worker processes,
  against the facts the live app built (c1): **no board, category, filter, Finance flag or company
  changed.**
- 54 got a different input hash. For 53 of them, main's own `input_hash()` of the stored inputs gives the
  branch's value, never c1's. Their c1 facts are from inputs they no longer have (gap 9 below). 35 of
  those lost a salary the listing no longer states.
- 46 changed `is_canonical`: the one-time duplicate repair (gap 8).

**rescore_at on real data.** Clock frozen 9 h after the newest score (13:04 UTC, past a UTC midnight): a
normal pass re-scored the 168,474 postings due, then all 398,326 were re-scored at the same instant.
**Nothing shown differed** (fit, fit detail without `posting_age_hours`, urgency, window, badges,
deadline, posting date, resume match).

**Scoring rules.** `intel/scoring.py` changed only by adding `rescore_at`; no fit, badge or deadline
reads it. The new rules hash is recorded under RULES_VERSION 3, without the board gate: the user asked
for placement proof, not score identity.

**Output changes, all intended.**
- Once, on the first start: the duplicate repair (~240 clusters on c1 showed a possibly closed copy over
  an active one) and one full re-score (`rescore_at` starts empty).
- Reopened postings are re-scored; clusters are re-picked after status changes and prunes.
- A posting is re-scored when something it shows can change, and at least daily, instead of hourly.
  Postings older than 61 days are now re-scored daily (they weren't before).

**Not done:** gap 5 (whole-table `UPDATE … profile_version=NULL` holding the write lock), gaps 3, 6 and
7, fixes 7–9.

**Gap 9, found by the placement check and fixed: blank-value changes left facts stale.**
- `record_changes` (`intel_store.py:117`) marks a posting for a facts re-read only when a field changes
  from one non-blank value to another. A salary or location that appears or goes blank is skipped, and
  company, posting date and department aren't compared at all.
- On c1, 750 postings (29 sources, 556 of them Quest Diagnostics) have facts built from inputs they no
  longer have. Rebuilt with main's code: 689 give the same facts, 58 drop a salary the listing no longer
  gives, and 3 Johns Hopkins postings gain Baltimore, US (they are missing from location filters today).
  `stale_facts.py`.
- Every update's full re-read repaired these. Fix 1 removes that cover, so they now last until the next
  real knowledge change.
- Fixed (`tests/store/test_input_changes.py`):
  - Two triggers in migration v8 send a posting back for facts when its title, location, company,
    salary or posting day changes, blank or not. The change log keeps its rule for what counts as news.
  - Once, on the first start, `IntelStore.reread_stale_inputs` compares every posting's input hash with
    its stored inputs and sends the stale ones back.
  - On a fresh copy of c1, it found the 750 and re-read them (~42 s of the first pass). Afterwards,
    0 of 398,326 postings had facts from inputs they no longer have.
  - The poll's two writes that carry the triggers took 1.4 s and 1.5 s, against 1.8 s and 1.9 s
    without them.
