# Tech/CS sources in per-field packs: design (Phase 1)

Status: **design for approval.** No code has changed. Branch `feat/tech-sources`, worktree
`.claude/worktrees/tech-sources` (the app did not create one for this session, so I made it from `main` at
`be75c30`, which is v0.3.7).

The brief is `plans/cs-tech-sources-prompt.md` in the main checkout. Section 10 lists the decisions I need
from you before Phase 2. Each has a recommended default.

---

## 1. What the repo and a real install show

Each fact below comes from a file, a command or a copy of the installed database. The database and
`config.json` were copied read-only from `%LOCALAPPDATA%\Jobwatch` to the session scratchpad. Nothing in the
data folder was written.

1. **The installed config equals the bundle.** The install is at `sources_version` 9 with 256 boards.
   `clean_config(config.json)["boards"]` equals the installed boards key for key. Its hash is
   `ddb8d7057c16c87e`, the same as `__shipped__.hash` in `config/source_defaults_history.json`. Phase 2 can
   therefore prove the split is byte-identical by hashing the boards flattened from the packs.
2. **Installed configs carry no `_section` headers.** `clean_config` (tools/build_windows.py:114-123) drops
   every `_` key. So `board_sections()` (intel_store.py:58) and section-based type inference
   (`intel/companies.py::_SECTION_TYPES`) only work in a source checkout. On an install, a board's employer
   type comes from `company_key`, from the posting's company name or from the board name.
3. **Pack moves do not re-rank anything.** Facts are recomputed when `FACTS_VERSION` changes or when
   `config_fingerprint()` changes (intel/knowledge.py:386). The fingerprint hashes only `taxonomy.json`,
   `companies.json`, `skills.json` and `locations.json`, so files under `config/sources/` are not part of it.
   **Phases 3 and 4 do edit `taxonomy.json` and `companies.json`, so the first start after that update
   recomputes facts for every stored posting once (about 129k on this install), without any
   `FACTS_VERSION` bump.** This is the same cost as the 45-minute re-rank seen in 0.3.2. See decision D9.
4. **The upgrade deletes a board in one case only.** `upgrade_sources()` (portable_start.py:31-87) retires a
   board when it appears in `__since__`, is missing from the bundled boards, and still has its shipped
   identity. Every board name keeps shipping in this plan, so the retired list is empty.
5. **Reusing a 0.3.0 board name is a trap.** The 49 tech boards 0.3.0 added (okta, micron, geotab,
   `linkedin_us_tech`, …) are still in `__since__` with version 7. An install at version 9 doesn't have them.
   If a later bundle ships `okta` again, `upgrade_sources` sees `since 7 <= installed 9` and treats it as
   deleted by the user, so the board is never added. Section 4.3 fixes this in `record_release`.
6. **Real finance/tech mix per board.** Measured on the installed copy (`job_intel`, 128,954 postings):
   - Quant firms are 24–70% finance and 22–70% tech. Fintech is 10–46% finance and 13–61% tech. Both are
     genuinely shared.
   - Banks are 41–100% finance. JPMorgan alone has 1,962 tech postings, which is why bank technology needs
     its own boards (decision D3).
   - Some boards in today's tech sections add finance postings that no finance board finds (counted as
     finance postings in clusters with no finance-board member). Capital One adds 444, Mastercard 401,
     PayPal 147 and Nasdaq 41. Community lists add 674 (zapply_newgrad27), 367 (derec4_newgrad27),
     269 (simplify_intern26), 185 (zapply_intern27), 123 (zapply_ca_jobs) and 35 (sndsh_intern27). For this
     install's finance profile, 32 postings from five of those lists score fit ≥ 75: zapply_intern27 11,
     derec4 10, zapply_ca_jobs 5, zapply_newgrad27 4 and sndsh_intern27 2. simplify_intern26 adds 2 more.
     See decisions D1 and D2.
   - Some current "tech" boards are barely tech. Target is 3% tech (101 of 2,729 postings), sweetgreen 2%,
     glossier 0%, gopuff 1% and disney_early 2%. See decision D6.
7. **The onboarding specialties step already exists.** `web/js/views/welcome.js:113-141` adds a
   "Which specialties?" step for every family that has subcategories, and
   `web/tests/specialties.test.js` already covers how specialties become targets. It's hidden today only
   because `Knowledge.family_tree()` returns empty subcategories. Settings has the matching cards
   (settings.js:335).
8. **The GitHub Actions alert runner** (`.github/workflows/jobwatch.yml`, `python watcher.py --once` for the
   subscribers in `subscribers.json`) has no saved profile. Under "no profile polls finance only" it would
   stop polling the tech boards its subscriber watches. See decision D4.
9. **`stash@{0}`** (CS resume matching) imports `intel.sources.profile_fields`, `TECH_FIELDS` and
   `role_field`. The new `intel/sources.py` keeps those names and signatures so the stash can be applied
   later with little conflict. It's still not applied.

---

## 2. Pack layout

```
config/sources/
  manifest.json                 fields -> packs (the only selection logic in data)
  finance/canadian_banks.json   finance/bulge_brackets.json   finance/boutiques_middle_market.json
  finance/private_markets.json  finance/asset_managers.json   finance/pensions_insurance.json
  finance/ratings_data.json     finance/linkedin.json
  shared/quant_trading.json     shared/fintech.json           shared/financial_services_tech.json
  shared/lists.json             shared/linkedin.json  (Phase 2 only, emptied by the LinkedIn split)
  tech/big_tech.json  tech/lists.json  tech/software_core.json  tech/data_core.json  tech/hardware_core.json
  tech/ai_labs.json  tech/ai_infrastructure.json  tech/ai_apps.json  tech/research_labs.json
  tech/developer_tools.json  tech/data_infrastructure.json  tech/cloud_infrastructure.json  tech/security.json
  tech/enterprise_saas.json  tech/consumer_tech.json  tech/gaming.json  tech/health_tech.json
  tech/canadian_tech.json  tech/bank_technology.json
  tech/semiconductors.json  tech/robotics_autonomy.json  tech/defense_aerospace.json  tech/devices_iot.json
```

Finance is split more finely than today's sections (private markets, asset managers, pensions and insurance,
ratings and data) so finance can be narrowed by area later. That needs only manifest edits.

### 2.1 Pack file

A pack holds a title, the verification date, a note and an ordered `boards` object. A board's settings are
exactly today's settings; the pack adds nothing to a board. Here is an example of a shared pack as it would
look after Phase 4 (Phase 2 keeps today's bare settings):

```json
{
  "title": "Fintech",
  "verified": "2026-10-22",
  "note": "Fintech employers hire finance and software graduates alike, so Finance, Software and AI & Data profiles all poll these official Greenhouse/Ashby feeds (complete listings).",
  "boards": {
    "stripe":  {"ats": "greenhouse", "token": "stripe",  "company_key": "stripe",  "group": "FinTech", "priority": 1, "geography": "global", "min_interval": 0},
    "plaid":   {"ats": "ashby",      "token": "plaid",   "company_key": "plaid",   "group": "FinTech", "priority": 2, "geography": "us",     "min_interval": 0},
    "wealthsimple": {"ats": "ashby", "token": "wealthsimple", "company_key": "wealthsimple", "group": "FinTech", "priority": 1, "geography": "ca", "min_interval": 0}
  }
}
```

`stripe` is defined once, in this file. The manifest lists `shared/fintech` under Finance and under several
Software and AI & Data specialties, so the board is shared without being copied. A finance-plus-software
profile polls it once, because the selected boards are a set of names.

### 2.2 Manifest

```json
{
  "version": 1,
  "fields": {
    "finance":  {"core": ["finance/canadian_banks", "...every finance pack...", "shared/quant_trading", "shared/fintech",
                          "shared/financial_services_tech", "shared/lists"],
                 "specialties": {}},
    "software": {"core": ["tech/big_tech", "tech/lists", "tech/software_core", "shared/lists"],
                 "specialties": {"backend": ["tech/ai_labs", "..."], "game_dev": ["tech/gaming"],
                                 "quant_dev": ["shared/quant_trading", "shared/fintech", "tech/bank_technology"]}},
    "data_ml":  {"core": ["tech/big_tech", "tech/lists", "tech/data_core", "shared/lists"], "specialties": {"...": []}},
    "hardware": {"core": ["tech/big_tech", "tech/lists", "tech/hardware_core", "shared/lists"], "specialties": {"...": []}},
    "product":  {"core": ["tech/big_tech", "tech/lists", "shared/lists", "tech/enterprise_saas", "tech/consumer_tech",
                          "tech/developer_tools", "tech/ai_apps", "tech/canadian_tech", "shared/fintech"]},
    "design":   {"core": ["...same as product..."]},
    "sales": {"core": "*"}, "operations": {"core": "*"}, "people_legal": {"core": "*"}, "healthcare": {"core": "*"}
  }
}
```

Section 7.2 has the full specialty-to-pack map. Rules that tests enforce:
- Every board key is defined in exactly one pack.
- No pack holds more than 50 boards.
- Every pack the manifest references exists, and every pack is referenced by at least one field.
- For software, data_ml and hardware, the specialty keys equal that family's taxonomy subcategories. A
  specialty may map to `[]`, meaning the core packs only.
- A later field (healthcare, product, …) needs only its pack files and its manifest entry.

### 2.3 Assembling `config["boards"]`

`intel/sources.py::load_config(path)` reads `config.json`. If the file has a `boards` key (every install, and
any local config that keeps its own boards), those boards are used as they are. If it doesn't (the repo's
`config.json` after Phase 2), the boards are assembled from the packs in manifest order, with one
`_<pack id>` header before each pack's boards (for example `"_finance/canadian_banks": "<note>"`). This keeps
`board_sections()`, the `quant`, `fintech`, `canadian_bank`, `bulge` and `boutique` type needles and
`job_intelligence.board_tags()` working in a source checkout.

The build flattens the packs into the bundled `app/config.json` exactly as today, and ships
`config/sources/**` beside the other knowledge files.

---

## 3. Selection contract

`config["boards"]` is the universe. Packs only filter it, and selection never adds a board that isn't in the
install's own config.

```
profile_fields(profile, kn)       -> ordered list: profile.fields plus the field of each target role;
                                     ['finance'] when that is empty. Mirrors web/js/fields.js profileFields().
chosen_specialties(profile, field) -> 'software.backend' -> backend; a finance target's category for finance.
selected_packs(profile, kn)        -> for each field:
                                        entry missing or core == "*"  -> every pack
                                        else core + (narrowed ? packs of the chosen specialties
                                                              : packs of every specialty)
                                     narrowed = specialties chosen AND the whole field is not itself a target
                                     (Settings' "All of Software" switch keeps everything).
polled_boards(config, profile, kn) -> enabled boards in config["boards"] whose pack is selected,
                                     plus enabled boards that are in no pack (your own sources: always polled).
```

- With no saved profile, `load_profile` returns the default finance profile, so only Finance packs are
  polled.
- `cycle()` loads the profile from the database on every run, so a change in Settings or a re-run of setup
  takes effect on the next poll with no restart. A board selected for the first time is seeded silently, as
  any new source is today.
- Boards outside the profile's fields are skipped. They are never deleted, and their postings stay.
- Finance today: `finance.specialties` is `{}`, so a finance profile polls every finance and shared pack
  whatever finance areas it picked. Narrowing finance later means moving packs from `core` into area lists
  keyed by category (`investment_banking: [...]`), with no code change.

### 3.1 Changes in each file that reads `config["boards"]`

| File | Today | Change |
|---|---|---|
| `intel/sources.py` (new) | none | `load_packs()` (manifest + packs, cached by modification times, validated), `load_config()`, `profile_fields()`, `chosen_specialties()`, `selected_packs()`, `polled_boards()`, `board_pack()`, `pack_fields()`. Keeps `TECH_FIELDS`/`role_field` for the stash. |
| `watcher.py:3270` `main()` | `json.loads(config)` | `load_config(args.config)` |
| `watcher.py:2767` `cycle()` | every enabled board | `cycle(config, con, progress=None, boards=None)`. With `boards=None` it uses `polled_boards()` with the profile from the database. The CLI alert loop passes its own set (decision D4). |
| `watcher.py:1566` `enrich_descriptions`, `:1649` `enrich_linkedin` | every enabled board | take `boards=` from the cycle's selection, so no requests go to unpolled boards |
| `watcher.py:2742` `repair_workday_posted` | all Workday boards | unchanged (database only, no network) |
| `watcher.py:3083` `cmd_check` | validates boards | also validates packs and the manifest: duplicates, sizes, references, specialty coverage, `company_key` |
| `watcher.py:3169` `--verify`, `:3281` `--list`, `--test` | all boards | unchanged: tools that check every board |
| `dashboard.py:238-239` | `json.loads(config)` | `load_config(self.config_path)` |
| `dashboard.py:876` home stats `enabled` | enabled boards | polled boards for the current profile |
| `dashboard.py:1523` `sources()` | section from header order | adds `pack`, `pack_title`, `fields` (labels of the fields that poll it), `polled`, `own` (no pack). Polled sources sort first; the response also returns the profile's fields. |
| meta (`families`) | `family_tree()` without subcategories | `family_tree()` with specialties and notes (shows the onboarding step) |
| `intel_store.py:58,258` | headers in `config["boards"]` | unchanged; works because `load_config` emits pack headers |
| `job_intelligence.py:45` `board_tags` | headers | unchanged |
| `portable_start.py::upgrade_sources` | bundled flat boards | **unchanged code** (section 4) |
| `tools/build_windows.py:133` `stage_app` | `json.loads(config.json)` | `load_config()`; copy `config/sources/**`; `sources_version` 10 when boards change (Phase 4) |
| `tools/source_history.py` | `git show tag:config.json` | for tags after the split, assemble from `tag:config/sources/**`; `record_release` revives returning names (4.3) and records the shipped board names |
| tests that read `watcher.CONFIG` boards (`tests/sources/test_source_coverage.py:202`, `tests/install/test_portable.py:112,178`) | raw `config.json` | read through `load_config()` (no test is removed) |

---

## 4. Upgrade plan: why no board or posting is deleted

### 4.1 Phase 2 (split only)
- The flattened pack boards hash to `ddb8d7057c16c87e`, which equals v9's `__shipped__`. Phase 2's test
  asserts this, so the bundle is byte-identical and `record_release` needs no version bump.
- `upgrade_sources` sees the same bundled boards. The retired list is empty, and `forget_postings` is never
  called.

### 4.2 Phases 3-5 (new boards, LinkedIn split, metadata)
- `sources_version` goes to 10. New board names get `__since__` 10, so a v9 install (installed 9 < 10) adds
  them.
- Metadata added to moved boards (`company_key`, `group`, …) is applied to unedited installed boards the way
  any changed default is. A board the user edited keeps their values. Identity keys (ats, token, host, …)
  don't change, so nothing counts as "pointed elsewhere".
- The LinkedIn split changes the `queries` of `linkedin_us` and `linkedin_canada` to finance-only queries,
  which updates unedited installs. The software, data and hardware queries move to new boards. No board
  disappears, and postings already collected stay.
- A guard test fails if any board shipped at v9 (from `git show v0.3.7:config.json`) is missing from the
  packs. A missing pack file can then never become a silent retirement.

### 4.3 Reusing a 0.3.0 name (okta, micron, …)
`record_release` stores the shipped board names in `__shipped__` (`"boards": [...]`). When a board ships that
the previous release did not, its `__since__` is set to the new version. For this first release, the
"previous" set is v0.3.7's boards. A test upgrades a v9 config and checks that a returning name such as
`okta` is added. `upgrade_sources` itself does not change.

### 4.4 The acceptance test
A temporary folder holds `app/` (the bundle built from the packs, its history and its `config/sources`) and
`data/config.json` (from `git show v0.3.7:config.json` through `clean_config`, `sources_version` 9). It also
holds a synthetic `jobwatch.db` with postings, intel rows, FTS rows and an application on boards from every
pack, including all 256 v9 boards. `upgrade_sources` must remove 0 boards and delete 0 postings: the board
set before is a subset of the board set after, and the `jobs`, `job_intel`, `job_fts` and `applications`
counts are unchanged.

---

## 5. Tech taxonomy

Each family gets `subcategories` in the finance style: title, department and description regex fragments, a
`label`, a `note`, a `tie_priority` and an optional `related`. I'll reuse 0.3.0's `specialty()` scorer from
`5f834cd`:
- Title words before the first separator count most.
- A specialty the title names beats one that only the description suggests.
- `weights.min_specialty_score` = 3 is the evidence threshold.
- A specialty read from the description alone needs a full description cap (4 distinct phrases) and a lead
  of at least 2.

Finance classification runs first and is untouched, so the existing finance tests must pass unchanged.

| Family · specialty | Example titles | Packs (beyond core) |
|---|---|---|
| **Software** · backend | Backend Engineer, Payments · Software Engineer, API Platform · Java Developer | AI, dev tools, data, cloud, SaaS, consumer, Canadian, health, bank tech, fintech |
| · frontend | Frontend Engineer · UI Engineer, Design Systems · React Developer Intern | AI apps, dev tools, SaaS, consumer, Canadian, fintech |
| · full_stack | Full-Stack Engineer · Software Engineer, Full Stack (New Grad) · Full Stack Developer Co-op | as frontend + health |
| · mobile | iOS Engineer · Android Developer Intern · Mobile Engineer, React Native | consumer, Canadian, health, devices, fintech |
| · infrastructure | Site Reliability Engineer · DevOps Engineer · Cloud Platform Engineer | AI infra, cloud, dev tools, data, SaaS, bank tech, financial services |
| · systems | Distributed Systems Engineer · Compiler Engineer · Database Kernel Engineer | data, cloud, AI infra, semiconductors, quant |
| · security | Security Engineer, Application Security · Detection & Response Engineer · Penetration Tester | security, cloud, defense, bank tech, fintech |
| · game_dev | Gameplay Programmer · Game Engine Developer · Graphics Engineer, Rendering | gaming |
| · quant_dev | Quantitative Developer · Software Engineer, Low-Latency Trading · Trading Systems Developer | quant, fintech, bank tech |
| · qa_test *(proposed, D11)* | Software Engineer in Test · QA Automation Engineer · Test Developer Co-op | SaaS, consumer, Canadian, bank tech |
| **AI & Data** · ml_engineering | Machine Learning Engineer · ML Infrastructure Engineer · Applied AI Engineer, LLMs | AI labs, AI infra, AI apps, robotics, consumer, SaaS |
| · ai_research | Research Scientist, Reinforcement Learning · Research Engineer, Pretraining · AI Resident | AI labs, AI infra, research labs, robotics, quant |
| · data_science | Data Scientist, Product · Decision Scientist · Data Science Intern, Experimentation | consumer, SaaS, health, Canadian, bank tech, fintech, financial services |
| · data_engineering | Data Engineer · Analytics Engineer · Big Data Developer (Spark) | data, consumer, SaaS, Canadian, bank tech, fintech, financial services |
| · analytics | Data Analyst · Business Intelligence Developer · Analytics Co-op, Tableau | consumer, SaaS, Canadian, bank tech, fintech, financial services |
| **Hardware** · embedded_firmware | Embedded Software Engineer · Firmware Engineer Intern · Embedded Systems Developer (RTOS) | devices, robotics, defense, semiconductors |
| · chip_design | ASIC Design Engineer · Design Verification Engineer · FPGA Engineer | semiconductors |
| · electrical | Electrical Engineer, Power Electronics · Hardware Engineer, PCB Design · Analog Circuit Design Intern | semiconductors, devices, defense, robotics |
| · robotics_autonomy | Robotics Software Engineer · Perception Engineer · Motion Planning Engineer | robotics, defense |

Two classifier decisions follow from this list (D7, D8):
- **Embedded, firmware and robotics titles move to Hardware.** Today "Embedded Software Engineer" and
  "Firmware Engineer" land in Software, because `software.title` contains `embedded` and `firmware` and
  Software is checked before Hardware. For `hardware.embedded_firmware` and `hardware.robotics_autonomy` to
  receive anything, Hardware gets a short list of occupation words checked before Software (`embedded`,
  `firmware`, `fpga`, `asic`, `rtl`, `pcb`, `analog`, `robotics`, `perception`, `motion planning`). Those
  words leave `software.title`.
- **`quant_dev` overlaps `quant.quant_developer`.** Finance classification wins first, so "Quantitative
  Developer" stays `quant.quant_developer` (no finance test changes). `software.quant_dev` gets the
  software-family postings that name trading systems or low latency. In the taxonomy,
  `software.quant_dev` declares `"also_targets": ["quant.quant_developer"]`, and `_target_match` honours it.
  A Software profile that picks Quant developer therefore ranks both kinds as targets and polls the quant
  and fintech packs. Picking it doesn't add Finance to the profile's fields.

Classifier tests: at least 3 realistic titles per specialty, a description-only case, below-threshold cases
(an evidence-free "Engineer" gets no specialty), the routing cases above, and the full finance suite
unchanged. `FACTS_VERSION` stays at its current value (section 1.3). If anything ends up requiring a bump,
I'll stop and ask.

---

## 6. Tech employer types

Added to `config/companies.json` `types`. Every type gains a `track`: `finance`, `tech` or `both`. Settings
shows a type when its track matches the profile's fields:
- `finance`: the profile has Finance.
- `tech`: the profile has Software, AI & Data, Hardware, Product or Design.
- `both`: either of those.

Profiles with only fields like Operations see every type.

| Type | Label | Track | Examples |
|---|---|---|---|
| big_tech | Big Tech | tech | Amazon, Microsoft, Nvidia, Salesforce, Adobe, Netflix, Oracle |
| ai_lab | AI Lab | tech | Anthropic, OpenAI, xAI, Cohere, Mistral |
| ai_infrastructure | AI Infrastructure | tech | Databricks, Scale AI, Together AI, CoreWeave, Crusoe |
| developer_tools | Developer Tools | tech | Vercel, Linear, Supabase, GitLab, Datadog, Sentry |
| data_infrastructure *(added)* | Data Infrastructure | tech | MongoDB, Snowflake, ClickHouse, Confluent, Fivetran |
| cybersecurity *(added)* | Cybersecurity | tech | CrowdStrike, Zscaler, Okta, 1Password, Palo Alto Networks |
| enterprise_saas | Enterprise Software | tech | ServiceNow, Workday, Notion, Figma, Atlassian |
| consumer_tech | Consumer Tech | tech | Airbnb, DoorDash, Pinterest, Reddit, Spotify |
| semiconductors | Semiconductors | tech | Intel, AMD, Qualcomm, Broadcom, Micron, Cadence |
| robotics_autonomy | Robotics & Autonomy | tech | Waymo, Zoox, Aurora, Waabi, Applied Intuition |
| defense_tech | Defense & Aerospace | tech | Anduril, Shield AI, SpaceX, Palantir |
| gaming | Gaming | tech | Roblox, Epic Games, Riot Games, Ubisoft |
| high_growth_startup | High-Growth Startup | tech | Cursor, Sierra, Decagon, Harvey, Glean |
| canadian_tech | Canadian Tech | tech | Geotab, StackAdapt, Wattpad, Clio, Ada |
| research_lab | Research Lab | tech | Vector Institute, Mila, AI2 |
| hardware_devices *(added)* | Devices & IoT | tech | Samsara, Verkada, Garmin, ecobee |
| health_tech *(added)* | Health Tech | tech | Oscar Health, Hinge Health, Abridge |
| fintech | FinTech | **both** | exists; shared |
| quant_firm | Quant / Trading Firm | **both** | exists; shared |
| every other existing type | unchanged | finance | banks, PE, asset managers… (`corporate`, `unknown`: both) |

- **Priors.** `company_priors` gains tech types that point at specialties. They apply only when the posting
  already has a title signal in that family, the same rule finance priors follow. For example: gaming →
  `software.game_dev` +2, semiconductors → `hardware.chip_design` +2, ai_lab → `data_ml.ai_research` +1,
  robotics_autonomy → `hardware.robotics_autonomy` +2, quant_firm → `software.quant_dev` +2.
- **Scoring.** A recognized tech employer earns the same 7 company points as a recognized finance employer,
  but **only for a profile with a tech field**. A test keeps finance-only scores unchanged.
- `prune_profile` keeps working: unknown types are dropped as they are today.

---

## 7. Sources

### 7.1 Candidate employers by pack (Phase 4 verifies every one)

Legend:
- ✓ already ships (moved as is)
- ◇ shipped in 0.3.0 with a known setting (re-fetch to verify)
- ○ new candidate, with the ATS **I expect**, unverified

A `?` marks a guess about the ATS. Nothing ships unless its feed is fetched successfully in Phase 4. Apple,
Google, Meta, Uber, Shopify, Tesla and Hugging Face (Workable) have no feed an existing adapter reads, so
they go to "not added" unless you approve an adapter.

- **tech/big_tech** (core): ✓amazon, ✓amazon_newgrad (amazon_jobs) · ✓microsoft (off; re-check Eightfold?)
  · ✓nvidia, ✓salesforce(+early), ✓adobe(+university), ✓ebay, ✓autodesk, ✓workday_hq, ✓zoom, ✓hp
  (workday) · ✓netflix (eightfold) · ○oracle (oracle_hcm) · ○cisco (phenom?) · ○sap (successfactors?) ·
  ○intuit (radancy?) · ○ibm (avature?) · ○dell (workday?) · ○snap (workday?) · ◇thomson_reuters (workday)
- **tech/canadian_tech**: ◇stackadapt, ◇geotab, ◇ritual (greenhouse) · ◇wattpad (lever) · ◇benevity
  (ashby) · ○clio, ○league, ○applyboard (lever?) · ○ada, ○tophat, ○vidyard, ○thinkific (greenhouse?) ·
  ○d2l, ○kinaxis, ○opentext (workday?) · ○lightspeed, ○coveo, ○hopper (lever/ashby?) · ○hootsuite
  (workday?)
- **tech/ai_labs**: ✓anthropic, ✓xai (greenhouse) · ✓openai, ✓cohere, ✓perplexity, ✓character_ai,
  ✓midjourney, ✓poolside, ✓runway, ✓suno, ✓elevenlabs, ✓cartesia (ashby) · ✓imbue (greenhouse) ·
  ✓deepmind (off) · ○mistral (lever?) · ○thinking_machines, ○world_labs, ○magic, ○contextual_ai
  (ashby/greenhouse?) · ○stability_ai (greenhouse?)
- **tech/research_labs**: ○ai2 (greenhouse?) · ○vector_institute (?) · ○mila (?). This pack is dropped if
  fewer than three feeds verify.
- **tech/ai_infrastructure**: ✓databricks, ✓scale_ai, ✓together_ai (greenhouse) · ✓baseten, ✓modal,
  ✓crusoe, ✓lambda_labs, ✓runpod (ashby) · ✓assemblyai · ◇coreweave (greenhouse) · ◇anyscale,
  ◇pinecone (ashby) · ○fireworks_ai, ○snorkel, ○labelbox, ○weights_and_biases (greenhouse/lever?) ·
  ○langchain, ○deepgram (ashby?)
- **tech/ai_apps**: ✓cursor, ✓sierra, ✓decagon, ✓mercor, ✓harvey, ✓writer, ✓braintrust (ashby) ·
  ✓glean, ✓typeface, ✓heygen, ✓descript (greenhouse) · ○cognition, ○hebbia (ashby?)
- **tech/developer_tools**: ✓vercel, ✓gitlab, ✓launchdarkly, ✓datadog (greenhouse) · ✓linear,
  ✓supabase, ✓warp, ✓browserbase (ashby) · ✓postman (workday) · ✓retool (off) · ◇replit, ◇sentry,
  ◇temporal, ◇posthog (ashby) · ◇grafana_labs, ◇new_relic, ◇pagerduty (greenhouse) · ○netlify,
  ○circleci, ○sourcegraph, ○docker (greenhouse?) · ○render, ○neon (ashby?)
- **tech/data_infrastructure**: ✓mongodb, ✓elastic, ✓cockroach_labs, ✓planetscale, ✓starburst,
  ✓fivetran, ✓mixpanel (greenhouse) · ✓clickhouse, ✓hightouch, ✓amplitude (ashby) · ◇snowflake (ashby)
  · ◇dataiku (greenhouse) · ○confluent (ashby?) · ○dbt_labs, ○redis, ○singlestore, ○sigma_computing
  (greenhouse?) · ○hex, ○airbyte (ashby?)
- **tech/cloud_infrastructure**: ✓cloudflare, ✓fastly, ✓twilio (greenhouse) · ◇pure_storage, ◇rubrik
  (greenhouse) · ◇hpe (workday) · ○nutanix, ○netapp, ○akamai (workday?) · ○digitalocean (greenhouse?)
- **tech/security**: ✓1password, ✓vanta (ashby) · ◇okta, ◇zscaler (greenhouse) · ◇crowdstrike
  (workday) · ○palo_alto_networks, ○fortinet, ○tenable (workday?) · ○wiz, ○snyk, ○sentinelone,
  ○arctic_wolf, ○abnormal_security, ○chainguard, ○tanium (greenhouse?)
- **tech/enterprise_saas**: ✓servicenow (smartrecruiters) · ✓notion, ✓attio (ashby) · ✓figma, ✓airtable,
  ✓asana, ✓smartsheet, ✓calendly, ✓webflow, ✓dropbox, ✓gusto, ✓checkr, ✓flexport (greenhouse) ·
  ✓rippling (off) · ◇box, ◇miro (greenhouse) · ◇zapier (ashby) · ○hubspot, ○zendesk, ○grammarly,
  ○benchling (greenhouse?) · ○docusign (workday?) · ○atlassian (?) · ○canva (lever?)
- **tech/consumer_tech**: ✓airbnb, ✓doordash, ✓pinterest, ✓reddit, ✓lyft, ✓instacart, ✓discord,
  ✓duolingo, ✓squarespace, ✓peloton, ✓seatgeek, ✓faire, ✓sweetgreen, ✓glossier (greenhouse) · ✓spotify,
  ✓gopuff (lever) · ✓target, ✓comcast, ✓disney(+early) (workday) · ◇nextdoor, ◇roku, ◇coursera
  (greenhouse) · ◇quora (ashby) · ◇zillow (workday) · ○etsy, ○thumbtack (greenhouse?) · ○whatnot (ashby?)
- **tech/gaming**: ✓roblox · ◇epic_games, ◇riot_games, ◇twitch (greenhouse) · ○ubisoft (smartrecruiters?) ·
  ○unity (workday/greenhouse?) · ○ea (avature?) · ○take_two, ○niantic, ○scopely, ○bungie (greenhouse?) ·
  ○behaviour_interactive (smartrecruiters?) · ○mistplay (lever?)
- **tech/health_tech**: ✓oscar_health (greenhouse) · ✓hinge_health, ✓abridge, ✓commure, ✓openevidence
  (ashby)
- **tech/semiconductors**: ✓intel(+early) (workday) · ◇micron, ◇applied_materials, ◇analog_devices,
  ◇cadence, ◇broadcom, ◇marvell (workday) · ○amd, ○texas_instruments, ○arm, ○lam_research, ○kla, ○nxp,
  ○microchip, ○globalfoundries (workday?) · ○qualcomm (eightfold?) · ○synopsys (?) · ○tenstorrent,
  ○cerebras, ○groq, ○sambanova, ○lightmatter (greenhouse?) · ○etched (ashby?)
- **tech/robotics_autonomy**: ✓waymo, ✓nuro (greenhouse) · ✓zoox, ✓waabi (lever) · ✓aurora (ashby) ·
  ○applied_intuition, ○kodiak, ○skydio, ○figure, ○wayve, ○motional, ○zipline (greenhouse/lever?) ·
  ○physical_intelligence (ashby?) · ○boston_dynamics (workday?) · ○sanctuary_ai (lever?)
- **tech/defense_aerospace**: ✓anduril, ✓spacex (greenhouse) · ✓shield_ai, ✓palantir (lever) ·
  ○saronic (ashby?) · ○epirus, ○rocket_lab, ○relativity_space, ○astranis, ○planet (greenhouse?) ·
  ○blue_origin, ○mda_space (workday?)
- **tech/devices_iot**: ✓samsara, ✓verkada, ✓neuralink (greenhouse) · ◇motorola_solutions, ◇ciena
  (workday) · ○garmin, ○sonos, ○lucid (workday?) · ○ecobee, ○whoop, ○oura (greenhouse?)
- **tech/bank_technology** (tech-only boards that share `company_key` with the finance boards; decision D3):
  ○rbc_tech (phenom `query`) · ○td_tech, ○bmo_tech, ○cibc_tech, ○morgan_stanley_tech, ○citi_tech,
  ○barclays_tech, ○wells_fargo_tech, ○deutsche_bank_tech (workday `search` or a Technology `facets` id) ·
  ○jpmorgan_tech, ○goldman_sachs_tech (oracle_hcm `query`) · ○national_bank_tech (avature?) ·
  ○scotiabank_tech (successfactors category?)
- **tech/software_core**: ✓speedy_swe, ✓zapply_swe_newgrad · ○linkedin_us_software,
  ○linkedin_canada_software
- **tech/data_core**: ✓speedy_ai · ○linkedin_us_data, ○linkedin_canada_data
- **tech/hardware_core**: ○linkedin_us_hardware, ○linkedin_canada_hardware
- **shared/fintech**: today's 19 boards (section 8) · ◇koho, ◇neo_financial (ashby) · ◇toast
  (greenhouse) · ○wealthfront, ○carta, ○addepar (greenhouse?) · ○questrade (?)
- **shared/financial_services_tech**: today's 6 boards · ○bloomberg (avature?) · ○american_express,
  ○visa (workday?)

The six new LinkedIn boards (a U.S. and a Canada board for each tech field) ask for at most 3-4 queries each
(software intern, new grad, co-op; ML/data science/data engineer; hardware/embedded/FPGA intern). `_linkedin_get` already spaces every LinkedIn
request through one lock, so more boards make a poll longer, not more aggressive.

### 7.2 Specialty-to-pack map (with Phase 2 polled counts)

The full map is the "Packs" column in section 5. The core packs are added for every tech field. The counts
below are from a script over today's 256 boards with the Phase 2 manifest (packs that only exist after
Phase 4 left out). Phase 2 re-prints them from the real code.

| Profile | Polled (enabled) | Finance-only boards | Tech-only boards |
|---|---|---|---|
| today, any profile | 246 of 256 | – | – |
| finance only | 111 | 56 | 0 |
| software only | 184 | 0 | 134 |
| data_ml only | 164 | 0 | 113 |
| hardware only | 41 | 0 | 38 |
| finance + software | 240 | 56 | 134 |
| software, game_dev only | 32 | 0 | 27 |
| software, backend + infrastructure | 149 | 0 | 122 |

Hardware polls little in Phase 2 because today's sources have almost no hardware employers. Phase 4's
semiconductors, devices, robotics and defense packs fix that.

---

## 8. Where today's 256 boards go

Every board is defined once and its settings are unchanged in Phase 2. "Fin" and "Tech" are postings on
this install classified as finance or as a tech family.

| Pack | Boards | Fin | Tech | Members |
|---|---|---|---|---|
| `finance/canadian_banks` | 11 | 4,719 | 556 | rbc, rbc_early, rbc_students, td, td_students, bmo, bmo_students, cibc, cibc_students, scotiabank_students, national_bank |
| `finance/bulge_brackets` | 12 | 15,901 | 5,428 | jpmorgan, jpmorgan_early, morgan_stanley, morgan_stanley_early, citi, citi_early, barclays, wells_fargo, goldman_sachs, bank_of_america_students, bank_of_america, deutsche_bank |
| `finance/boutiques_middle_market` | 10 | 453 | 24 | moelis, pjt_partners, houlihan_lokey_campus, houlihan_lokey, piper_sandler, william_blair, evercore_students, evercore, lazard, jefferies_campus |
| `finance/private_markets` | 7 | 474 | 81 | stepstone, blackstone_campus, blackstone, kkr, carlyle, apollo, brookfield |
| `finance/asset_managers` | 4 | 951 | 487 | blackrock, fidelity, vanguard, man_group |
| `finance/pensions_insurance` | 7 | 529 | 187 | cpp_investments, otpp, cdpq, cdpq_students, manulife, sun_life, sun_life_students |
| `finance/ratings_data` | 4 | 352 | 214 | moodys, sp_global, msci, msci_us |
| `finance/linkedin` | 1 | 562 | 295 | linkedin_quant (linkedin_us and linkedin_canada join after the split) |
| `shared/quant_trading` | 28 | 949 | 1,153 | jump_trading, hrt, citadel, citadel_sec, point72, sig, imc, optiver_us, akuna, drw, two_sigma, tower_research, five_rings, pdt_partners, voleon, gts, virtu, old_mission, flow_traders, geneva_trading, vatic_labs, squarepoint, schonfeld, qube_rt, aqr, jane_street, worldquant, nwfintech_quant27 (off: citadel, citadel_sec, two_sigma, gts, nwfintech_quant27) |
| `shared/fintech` | 19 | 682 | 1,043 | stripe, plaid, ramp, brex, affirm, chime, robinhood, coinbase, wealthsimple, mercury, sofi, block, gemini, fireblocks, marqeta, lithic, alloy, betterment, upstart |
| `shared/financial_services_tech` | 6 | 1,254 | 1,684 | capital_one, capital_one_early, mastercard, mastercard_early, paypal, nasdaq (D2) |
| `shared/lists` | 5 | 2,239 | 7,229 | zapply_newgrad27, zapply_intern27, zapply_ca_jobs, derec4_newgrad27, sndsh_intern27 (D1) |
| `shared/linkedin` | 2 | 699 | 515 | linkedin_us, linkedin_canada (Phase 2 only: mixed queries until the split) |
| `tech/big_tech` | 14 | 307 | 4,291 | amazon, amazon_newgrad, microsoft, nvidia, salesforce, salesforce_early, adobe, adobe_university, netflix, ebay, autodesk, workday_hq, zoom, hp (off: microsoft) |
| `tech/lists` | 10 | 703 | 10,455 | simplify_newgrad, simplify_intern26, simplify_intern27, vansh_intern26, vansh_intern27, vansh_newgrad27, cvrve_newgrad, canada_intern26, offseason_fall26, zapply_ca_intern (off: simplify_intern27) |
| `tech/software_core` | 2 | 65 | 1,626 | speedy_swe, zapply_swe_newgrad |
| `tech/data_core` | 1 | 28 | 176 | speedy_ai |
| `tech/ai_labs` | 14 | 158 | 1,146 | anthropic, openai, xai, deepmind, cohere, perplexity, character_ai, midjourney, poolside, runway, imbue, suno, elevenlabs, cartesia (off: deepmind) |
| `tech/ai_infrastructure` | 9 | 101 | 1,078 | databricks, scale_ai, together_ai, baseten, modal, crusoe, lambda_labs, runpod, assemblyai |
| `tech/ai_apps` | 11 | 39 | 461 | cursor, sierra, decagon, mercor, glean, harvey, writer, typeface, braintrust, heygen, descript |
| `tech/developer_tools` | 10 | 45 | 377 | vercel, linear, supabase, retool, gitlab, postman, launchdarkly, warp, browserbase, datadog (off: retool) |
| `tech/data_infrastructure` | 10 | 76 | 792 | mongodb, elastic, cockroach_labs, clickhouse, planetscale, starburst, fivetran, hightouch, amplitude, mixpanel |
| `tech/cloud_infrastructure` | 3 | 28 | 330 | cloudflare, fastly, twilio |
| `tech/security` | 2 | 7 | 78 | 1password, vanta |
| `tech/enterprise_saas` | 14 | 108 | 750 | servicenow, notion, figma, airtable, asana, smartsheet, calendly, webflow, attio, dropbox, rippling, gusto, checkr, flexport (off: rippling) |
| `tech/consumer_tech` | 20 | 176 | 1,316 | airbnb, doordash, pinterest, reddit, lyft, instacart, discord, duolingo, spotify, squarespace, peloton, seatgeek, gopuff, faire, sweetgreen, glossier, target, comcast, disney, disney_early (D6) |
| `tech/gaming` | 1 | 5 | 217 | roblox |
| `tech/health_tech` | 5 | 100 | 122 | oscar_health, hinge_health, abridge, commure, openevidence |
| `tech/semiconductors` | 2 | 25 | 644 | intel, intel_early |
| `tech/robotics_autonomy` | 5 | 32 | 623 | waymo, zoox, nuro, aurora, waabi |
| `tech/defense_aerospace` | 4 | 202 | 3,675 | anduril, shield_ai, spacex, palantir |
| `tech/devices_iot` | 3 | 20 | 283 | samsara, verkada, neuralink |

That's 256 boards in total: 56 finance, 60 shared and 140 tech. The largest pack has 28. The assignment was
checked by a script against `config.json`: every board appears once.

---

## 9. Phases and proofs

1. **This design.** Committed. I stop here for approval.
2. **Packs, selection and upgrade, with no new sources.**
   - New: `intel/sources.py`, the manifest and the packs. Root `config.json` loses `boards`.
   - Rewired: `load_config()` everywhere, `cycle(boards=)` and the enrichers.
   - The build copies the packs; `--check` validates them.
   - Tests in `tests/sources/test_source_packs.py`:
     - The union of the packs equals `git show v0.3.7:config.json` boards.
     - The flattened hash equals `ddb8d7057c16c87e`.
     - No board is defined twice, and no pack has more than 50 boards.
     - Manifest references are valid.
     - The five profile counts.
     - Finance-only polls 0 tech-only boards, and software-only polls 0 finance-only boards.
     - Finance plus software is the union, with each shared board once.
     - Specialty narrowing, and the "All of Software" switch.
     - No profile means finance.
     - A boards outside every pack is always polled.
     - A Settings change applies on the next cycle (mocked fetch).
   - The upgrade test in `tests/install/` (section 4.4).
   - I stop and show you the counts and the test output.
3. **Taxonomy, specialties and employer types.** Classifier tests per specialty (section 5). The finance
   suite runs unchanged. Settings type filtering, plus a score-unchanged test for finance profiles. Commit.
4. **Sources, one subfield at a time.** Each research subagent returns candidates with the feed URL it
   fetched; I write the packs myself. Each board is fetched once with
   `watcher.py --list <board>` (through uv, as the brief describes). I record the date in the pack, add
   `companies.json` entries, then the LinkedIn split, the revival of 0.3.0 names, and
   `sources_version` 10. Commit per subfield.
5. **UI and docs.**
   - The Sources view groups by pack title. Each row shows "Finance · Software" in small type, and rows
     that aren't polled are dimmed with "Not polled for your fields". The segmented filter becomes All ·
     Polled · Issues. No new colors or buttons.
   - Onboarding gets the specialties step through `family_tree()`.
   - `PRODUCT.md`: the line "Every profile polls the same sources…" is replaced by the field-pack rule.
     `docs/ARCHITECTURE.md` gets a Sources section (packs, manifest, selection, upgrade).
   - Then the full `python -m unittest`, the node suite and the final report.

---

## 10. Decisions for you

| # | Question | Recommendation |
|---|---|---|
| D1 | Community lists with real finance yield: `zapply_newgrad27`, `zapply_intern27`, `zapply_ca_jobs`, `derec4_newgrad27` and `sndsh_intern27` (1,384 unique finance postings, 32 at fit ≥ 75 for your profile). Make them shared, or tech-only as the brief says? | **Shared.** Making them tech-only drops those 32 high-fit finance postings. The SWE-specific lists (Simplify, vansh, cvrve, speedy, zapply SWE/CA-intern, canada_intern26, offseason) go to tech. |
| D2 | Capital One, Mastercard, PayPal and Nasdaq (+early boards) sit in today's tech sections but add over 1,000 unique finance postings (444 + 401 + 147 + 41). Make them shared? | **Shared** (`shared/financial_services_tech`), so finance keeps them. |
| D3 | Bank technology for tech profiles: separate search-filtered boards (`rbc_tech`, `jpmorgan_tech`, …) in a tech pack, or make the full bank boards shared? | **Separate boards.** A software profile shouldn't page through JPMorgan's 9k postings to find 2k tech ones, and finance boards stay untouched. |
| D4 | The GitHub Actions alert runner (`watcher.py --once` and the loop) has no profile. Should it poll every pack, or follow "no profile means finance"? | **Every pack** for the CLI loop, since subscribers' filters decide alerts there. The desktop app follows the profile. |
| D5 | Shared boards that lack metadata (the 28 quant and 19 fintech boards): add `company_key`, `group`, `priority` and `geography`, and `min_interval: 0`, which keeps today's every-cycle cadence? This changes finance-polled boards' settings. | **Yes, with `min_interval: 0`.** Polling cadence stays the same. |
| D6 | Near-zero-tech boards (target 3%, sweetgreen 2%, glossier 0%, gopuff 1%, disney_early 2%): keep them in `tech/consumer_tech` unchanged, or disable them? (Disabling is a settings change; nothing gets deleted.) | **Keep them for now**, and list them in the final report for a separate call. |
| D7 | Embedded, firmware and robotics titles move from the Software family to Hardware, as the brief's specialty list implies. | **Yes.** |
| D8 | `software.quant_dev` as a real specialty that also targets `quant.quant_developer`, without adding Finance to the profile's fields. | **Yes.** |
| D9 | The taxonomy and companies changes recompute facts for every stored posting once (about 129k, roughly 45 min, with the header's progress count). This happens without a `FACTS_VERSION` bump. | **Accept it**, and ship Phases 3 and 4 in one release so it happens once. |
| D10 | Fields without packs of their own: Product and Design use the tech employer packs; Sales, Operations, People & Legal and Healthcare poll every pack. | **As stated.** A later healthcare pack is a manifest edit. |
| D11 | Add a `software.qa_test` specialty (SDET and QA automation, common co-op entry points)? | **Yes.** It maps to the core packs plus SaaS, consumer, Canadian and bank tech. |
| D12 | Re-use 0.3.0 names (okta, micron, …) with the `__since__` revival in `record_release`, or use new names? | **Revival.** It keeps natural names, and installs at 7 or 8 that still have those boards keep their postings. |
| D13 | Postings from boards a profile no longer polls stay in the database, but they never close, because closure needs a poll. Opportunities already filters to the profile's fields. | **Leave them.** Optionally hide them later. |
