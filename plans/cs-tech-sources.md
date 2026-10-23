# Tech/CS sources in per-field packs: design (Phase 1, revised)

Status: **revised design for approval. No code has changed.** Branch `feat/tech-sources`, worktree
`.claude/worktrees/tech-sources`, created from `main` at `be75c30` (v0.3.7). The brief is
`plans/cs-tech-sources-prompt.md` in the main checkout.

**What changed in this revision:** your rule is that the Finance board must show exactly what it shows today.
Nothing may go missing, and the tech work stays out of it. That rule overrides the brief where the two
conflict. Section 11 lists every point where the brief yields.

## Terms

| Your word | Meaning | In the code |
|---|---|---|
| **Board** | The field someone picks in onboarding: Finance, Software, AI & Data, Hardware… | `profile.fields`; `FIELD_INFO` in `web/js/fields.js` |
| **Source** | One site or feed that Foothold polls: a Greenhouse board, a Workday site, a GitHub list, a LinkedIn search | an entry of `config["boards"]` (the code's name is misleading) |
| **Filter** | A subcategory inside a board: a finance area (Investment Banking · M&A) or a tech specialty (Software · Backend) | a target role such as `software.backend` |
| **Pack** | A small file of sources, grouped by employer type | `config/sources/<folder>/<group>.json` |

---

## 1. The Finance board guarantee

**Definition.** Take a profile whose only board is Finance. What it shows today must still be there after
every phase of this work:

- **Same postings:** the same finance postings in Opportunities.
- **Same fit and order:** the same fit score and order for each.
- **Same sources:** the same sources polled, with the same settings and at the same rate.

Today that is 21,951 open postings on this install. The tech work may add new boards, filters and sources
around the Finance board but never inside it.

**How the storage enforces it.** A source's folder decides which boards may poll it:

| Folder | Polled by | What goes there |
|---|---|---|
| `finance/` | the Finance board only | banks, boutiques, private markets, asset managers, pensions, ratings, the finance LinkedIn searches |
| `shared/` | Finance **and** the tech boards | every other source the Finance board polls today: quant firms, fintech, today's tech employers and community lists |
| `tech/` | the tech boards only | every new source this work adds |

- The Finance board has no filters yet, so it polls all of `finance/` and `shared/`. Those two folders hold
  exactly today's 256 sources.
- A new source goes into `tech/`, so it can never reach the Finance board.
- A tech board polls only the `shared/` and `tech/` groups its filters ask for, never `finance/`.

**How it's proven.** Each step has a check you can see:

1. **Same sources (checked now).** The design script selects exactly today's 246 enabled sources for a
   Finance-only profile. The settings of the 256 sources it covers hash to `ddb8d7057c16c87e`, the same as
   v0.3.7's shipped hash. Phase 2 turns both into tests.
2. **The bundle is unchanged.** Today's sources keep their settings byte for byte. No metadata is added, and
   the LinkedIn queries aren't split (section 11). The upgrade therefore leaves every source and every
   posting where it is (section 5).
3. **Finance postings, fit and order stay the same.** This is a gate for Phases 3 and 4. I saved the Finance
   board as you see it now: 21,951 postings with their fit, category, company name and cluster, taken from
   a read-only copy of your database. Before Phase 3 or Phase 4 is committed, the new code and knowledge
   recompute facts and scores on a copy of that database for your profile. Any finance posting whose
   presence, fit, category, cluster or canonical row differs blocks the commit until it's fixed. The diff
   (expected empty) goes in the report.
4. **What may differ.** Two labels can change without any job going missing (decision B):
   - The Employer type filter may name an employer that is "Unclassified" today, for example "AI Lab"
     instead of "Unclassified".
   - A posting's "Why" line may name that employer's type.

   Neither changes a job, a fit score or the order: an employer outside finance still scores 4 company
   points for a finance profile (`intel/scoring.py:170-174`).

---

## 2. What the repo and your install show

Each fact below comes from a file, a command or a copy of the installed database. The database and
`config.json` were copied to the session scratchpad. Nothing in `%LOCALAPPDATA%\Jobwatch` was written.

1. **The installed config equals the bundle.** The install is at `sources_version` 9 with 256 sources.
   `clean_config(config.json)["boards"]` equals the installed sources key for key, and its hash
   `ddb8d7057c16c87e` equals `__shipped__.hash` in `config/source_defaults_history.json`.
2. **The Finance board today.** Opportunities defaults to the profile's boards. For Finance that means
   `i.is_finance=1` (`job_query.py:118-126`): 21,951 open postings on this install, 1,767 at fit ≥ 55 and
   119 at fit ≥ 75.
3. **Finance postings come from everywhere.** 1,474 finance postings (3 of them at fit ≥ 75) are found only
   by sources the first draft made tech-only, such as Simplify lists, HP, Oscar Health and Disney. More than
   1,000 others come only from Capital One, Mastercard, PayPal and Nasdaq, and more than 1,300 only from the
   zapply/derec4/sndsh lists. That's why every one of today's sources stays on the Finance board.
4. **Installed configs have no `_section` headers.** `clean_config` drops them (tools/build_windows.py:114).
   On an install, an employer's type comes from `company_key`, the posting's company name or the source name.
5. **Pack files don't trigger recomputes.** Facts are recomputed when `FACTS_VERSION` changes or when
   `config_fingerprint()` changes. The fingerprint hashes only `taxonomy.json`, `companies.json`,
   `skills.json` and `locations.json` (intel/knowledge.py:386). **Phases 3 and 4 edit `taxonomy.json` and
   `companies.json`, so the first start after the update recomputes facts once for every stored posting
   (about 129k), without a `FACTS_VERSION` bump.** That's the ~45-minute re-index seen in 0.3.2. The gate in
   section 1 proves the recompute leaves the Finance board identical.
6. **The upgrade deletes a source in one case only.** `upgrade_sources()` (portable_start.py:31-87) retires a
   source when it's in `__since__`, missing from the bundle, and unedited. Every one of today's sources keeps
   shipping, so nothing is retired.
7. **0.3.0 names are a trap.** The 49 tech sources 0.3.0 added (okta, micron, geotab…) are in `__since__`
   with version 7. If a later bundle ships one of them again, an install at version 9 treats it as deleted by
   the user and never adds it. Section 5.3 fixes this.
8. **The onboarding filter step already exists.** `welcome.js:113-141` shows "Which specialties?" for every
   board with subcategories, and `web/tests/specialties.test.js` covers it. It's hidden only because
   `Knowledge.family_tree()` returns no subcategories today.
9. **The GitHub Actions alert runner** (`watcher.py --once` with the subscribers in `subscribers.json`) has
   no saved profile (decision D4).
10. **`stash@{0}`** imports `intel.sources.profile_fields`, `TECH_FIELDS` and `role_field`. The new module
    keeps those names, and the stash stays unapplied.

---

## 3. Layout

```
config/sources/
  manifest.json                      folders -> boards that may poll them; boards -> groups and filters
  finance/  canadian_banks  bulge_brackets  boutiques_middle_market  private_markets  asset_managers
            pensions_insurance  ratings_data  linkedin
  shared/   quant_trading  fintech  financial_services_tech  lists  swe_lists  ai_lists  big_tech
            ai_labs  ai_infrastructure  ai_apps  developer_tools  data_infrastructure  cloud_infrastructure
            security  enterprise_saas  consumer_tech  gaming  health_tech  semiconductors
            robotics_autonomy  defense_aerospace  devices_iot
  tech/     (Phase 4, new sources only) the same group names where they apply, plus
            software_core  data_core  hardware_core  canadian_tech  research_labs  bank_technology
```

A group can have a pack in both `shared/` and `tech/`. For example, `shared/ai_labs.json` holds Anthropic,
which Finance has always polled, and `tech/ai_labs.json` holds Mistral, which is new. The Software
board's Backend filter asks for the group `ai_labs` and gets both. The Finance board gets only the shared
one. The file name is the employer group, and the folder is who may poll it. Nothing is duplicated, and no
source carries a per-source flag.

### 3.1 Pack file

Here are two packs. A shared pack lists today's sources exactly as they are now:

```json
{
  "title": "AI labs",
  "verified": "2026-10-10",
  "note": "Sources the Finance board has polled since 0.2.5. They stay on it so it never loses a posting, and tech boards poll them too.",
  "boards": {
    "anthropic": {"ats": "greenhouse", "token": "anthropic"},
    "openai":    {"ats": "ashby", "token": "openai"}
  }
}
```

A new tech pack (Phase 4) adds full metadata, and each feed is fetched before it ships:

```json
{
  "title": "AI labs",
  "verified": "2026-10-23",
  "note": "Tech boards only. Feeds fetched successfully on the verified date.",
  "boards": {
    "mistral": {"ats": "lever", "token": "…", "company_key": "mistral", "group": "AI Labs", "priority": 2, "geography": "global", "min_interval": 1800}
  }
}
```

(The key is `"boards"` because the code already calls sources that; the manifest and docs say "sources".)

A pack can also list some of its sources under the config.json heading they had before packs, as
`"sections": {"startups_fintech_consumer": ["peloton", …]}`. The name of a heading sets the company type of
employers that are missing from companies.json (`intel/companies.py`). A repository run (the Actions alert runner)
still reads those headings. Without this, 15 consumer and health employers would change from "fintech" to
"unknown", and 138 of their postings would drop off a repository run's Finance board. Installed copies never had
headings, so they see no change either way. Found and fixed in Phase 2, and guarded by a test.

### 3.2 Manifest

```json
{
  "version": 1,
  "folders": {
    "finance": {"fields": ["finance"]},
    "shared":  {"fields": ["finance", "software", "data_ml", "hardware", "product", "design"]},
    "tech":    {"fields": ["software", "data_ml", "hardware", "product", "design"]}
  },
  "fields": {
    "finance":  {"groups": "*"},
    "software": {"core": ["big_tech", "lists", "swe_lists", "software_core"],
                 "filters": {"backend": ["ai_labs", "…"], "game_dev": ["gaming"], "quant_dev": ["quant_trading", "fintech", "bank_technology"]}},
    "data_ml":  {"core": ["big_tech", "lists", "ai_lists", "data_core"], "filters": {"…": []}},
    "hardware": {"core": ["big_tech", "lists", "hardware_core"], "filters": {"…": []}},
    "product":  {"groups": ["big_tech", "lists", "enterprise_saas", "consumer_tech", "developer_tools", "ai_apps", "canadian_tech", "fintech"]},
    "design":   {"groups": ["…same as product…"]},
    "sales": {"everything": true}, "operations": {"everything": true},
    "people_legal": {"everything": true}, "healthcare": {"everything": true}
  }
}
```

The Finance board's `"groups": "*"` means every pack in the folders it may poll (`finance/`, `shared/`). Later,
finance filters (narrowing by area) can be added as a `filters` map keyed by finance category, with no code
change. A future board (healthcare, design…) needs only a folder audience, its packs and a manifest entry.

**Rules that tests enforce:**
- Every source is defined once.
- No pack has more than 50 sources.
- Every group the manifest names has at least one pack.
- For Software, AI & Data and Hardware, the filter keys equal that board's taxonomy subcategories.
- `finance/` ∪ `shared/` is exactly the v0.3.7 source set, with identical settings.
- `shared/` gains no source in this work.

---

## 4. Selection

```
profile_fields(profile)        -> profile.fields plus the board of each target role; ['finance'] when empty
                                  (mirrors fields.js profileFields())
groups_for(field, profile)     -> "*" | core + the groups of the chosen filters, or of every filter when
                                  none is chosen or the whole board is itself a target ("All of Software")
selected_packs(profile)        -> packs whose folder lets the field poll and whose group is in groups_for;
                                  "everything": every pack
polled_sources(config, profile) -> enabled sources in config["boards"] whose pack is selected,
                                   plus enabled sources in no pack (your own: always polled)
```

- `config["boards"]` stays the universe; selection never adds a source the install's config doesn't have.
- **No saved profile:** the default profile is Finance, so it polls today's 246 sources, as it does today.
- The profile is read from the database on every poll, so a change in Settings or a re-run of setup applies
  on the next poll without a restart. A newly selected source is seeded silently, as any new source is
  today.
- Sources outside the profile's boards are not polled and never deleted. Their postings stay.

### 4.1 Polled sources (today's 256 sources; Phase 2 reproduces these in tests)

| Profile | Sources polled | From `finance/` |
|---|---|---|
| today, any profile | 246 | – |
| **Finance only** | **246 (identical set)** | 58 |
| Software only | 182 | 0 |
| AI & Data only | 162 | 0 |
| Hardware only | 41 (Phase 4 adds hardware employers) | 0 |
| Finance + Software | 246 | 58 |
| Software, Game dev filter | 30 | 0 |
| Software, Backend + Infrastructure filters | 147 | 0 |

### 4.2 Changes in each file that reads `config["boards"]`

| File | Change |
|---|---|
| `intel/sources.py` (new) | `load_packs()` (manifest + packs, cached by modification time, validated), `load_config()`, `profile_fields()`, `groups_for()`, `selected_packs()`, `polled_sources()`, `source_pack()`. Keeps `TECH_FIELDS` and `role_field` for the stash. |
| `watcher.py:3270` `main()` | `load_config(args.config)`. Without a `boards` key (the repo after Phase 2), it assembles sources from the packs, putting a `_<folder>/<group>` header before each pack so `board_sections()` keeps working. |
| `watcher.py:2767` `cycle()` | `cycle(config, con, progress=None, sources=None)`. By default it uses `polled_sources()` with the profile from the database. |
| `watcher.py:1555` `enrich_descriptions`, `:1639` `enrich_linkedin` | take the cycle's selection. For a Finance-only profile, the selection is today's set, so behavior is identical. |
| `watcher.py:2731` `repair_workday_posted` | unchanged (database only) |
| `watcher.py:3083` `cmd_check` | also validates packs and the manifest (the rules in 3.2) |
| `--verify`, `--list`, `--test` | unchanged: they check every source |
| `dashboard.py:238` | `load_config()` |
| `dashboard.py:876` home stats | counts sources polled for the current profile (246 for Finance-only, unchanged) |
| `dashboard.py:1523` `sources()` | adds `pack`, `pack_title`, `boards` (the boards that poll it), `polled`, `own` |
| meta `families` | `family_tree()` with filters and notes (turns on the onboarding filter step) |
| `intel_store.py`, `job_intelligence.py` | unchanged |
| `portable_start.py::upgrade_sources` | **unchanged code** |
| `tools/build_windows.py` | `load_config()`; copy `config/sources/**`; `sources_version` 10 when Phase 4 adds sources |
| `tools/source_history.py` | the tag rebuild reads packs for tags after the split; `record_release` revives returning names (5.3) |
| tests reading `config.json` sources (`tests/sources/test_source_coverage.py:202`, `tests/install/test_portable.py:112,178`) | read through `load_config()`; no test removed |

---

## 5. Upgrades: no source or posting is deleted

1. **Phase 2:** today's 256 sources move into packs unchanged. The flattened bundle hashes to v0.3.7's
   `ddb8d7057c16c87e`, so `upgrade_sources` sees the same bundle, retires nothing and deletes nothing.
2. **Phase 4:** only new sources are added (in `tech/`), with `__since__` 10 and `sources_version` 10, so a
   v9 install adds them. Today's sources aren't edited, so nothing about them changes on an install. A guard
   test fails if any v0.3.7 source is missing from the packs or has different settings.
3. **Returning 0.3.0 names:** `record_release` stores the shipped source names in `__shipped__`. A source
   that ships again after being absent gets `__since__` set to the new version, so installs add it. For this
   release, "absent" means not in v0.3.7. A test upgrades a v9 config and checks that `okta` is added.
4. **Acceptance test:** a temporary folder with `app/` (the bundle built from the packs) and
   `data/config.json` (v0.3.7's `config.json`, cleaned, `sources_version` 9). It also holds a synthetic
   database with postings, intel, FTS rows and an application on all 256 v0.3.7 sources. `upgrade_sources`
   must remove 0 sources and delete 0 postings, and every v0.3.7 source must keep identical settings.

---

## 6. Tech taxonomy (filters for the tech boards)

Each tech board gets subcategories in the finance style: title, department and description patterns, a
label, a note and a tie priority. They use 0.3.0's `specialty()` scorer:
- The title's head counts most.
- A filter the title names beats one only the description suggests.
- `min_specialty_score` = 3 is the evidence threshold.
- A filter read from the description alone needs 4 distinct phrases and a lead of at least 2.

Finance classification runs first and isn't touched. The existing finance tests must pass unchanged, and
section 1's gate checks every finance posting on your database.

| Board · filter | Example titles | Groups (beyond core) |
|---|---|---|
| **Software** · backend | Backend Engineer, Payments · Software Engineer, API Platform · Java Developer | AI, dev tools, data, cloud, SaaS, consumer, Canadian, health, bank tech, fintech, financial services |
| · frontend | Frontend Engineer · UI Engineer, Design Systems · React Developer Intern | AI apps, dev tools, SaaS, consumer, Canadian, fintech |
| · full_stack | Full-Stack Engineer · Software Engineer, Full Stack (New Grad) · Full Stack Developer Co-op | frontend's + health |
| · mobile | iOS Engineer · Android Developer Intern · Mobile Engineer, React Native | consumer, Canadian, health, devices, fintech |
| · infrastructure | Site Reliability Engineer · DevOps Engineer · Cloud Platform Engineer | AI infra, cloud, dev tools, data, SaaS, bank tech, financial services |
| · systems | Distributed Systems Engineer · Compiler Engineer · Database Kernel Engineer | data, cloud, AI infra, semiconductors, quant |
| · security | Security Engineer, Application Security · Detection & Response Engineer · Penetration Tester | security, cloud, defense, bank tech, fintech |
| · game_dev | Gameplay Programmer · Game Engine Developer · Graphics Engineer, Rendering | gaming |
| · quant_dev | Quantitative Developer · Software Engineer, Low-Latency Trading · Trading Systems Developer | quant, fintech, bank tech |
| · qa_test *(D11)* | Software Engineer in Test · QA Automation Engineer · Test Developer Co-op | SaaS, consumer, Canadian, bank tech |
| **AI & Data** · ml_engineering | Machine Learning Engineer · ML Infrastructure Engineer · Applied AI Engineer, LLMs | AI labs, AI infra, AI apps, robotics, consumer, SaaS |
| · ai_research | Research Scientist, Reinforcement Learning · Research Engineer, Pretraining · AI Resident | AI labs, AI infra, research labs, robotics, quant |
| · data_science | Data Scientist, Product · Decision Scientist · Data Science Intern, Experimentation | consumer, SaaS, health, Canadian, bank tech, fintech, financial services |
| · data_engineering | Data Engineer · Analytics Engineer · Big Data Developer (Spark) | data, consumer, SaaS, Canadian, bank tech, fintech, financial services |
| · analytics | Data Analyst · Business Intelligence Developer · Data Analytics Co-op, Tableau | consumer, SaaS, Canadian, bank tech, fintech, financial services |
| **Hardware** · embedded_firmware | Embedded Software Engineer · Firmware Engineer Intern · Embedded Systems Developer (RTOS) | devices, robotics, defense, semiconductors |
| · chip_design | ASIC Design Engineer · Design Verification Engineer · FPGA Engineer | semiconductors |
| · electrical | Electrical Engineer, Power Electronics · Hardware Engineer, PCB Design · Analog Circuit Design Intern | semiconductors, devices, defense, robotics |
| · robotics_autonomy | Robotics Software Engineer · Perception Engineer · Motion Planning Engineer | robotics, defense |

- **Hardware occupation words come first (D7).** Today, "Embedded Software Engineer" and "Firmware Engineer"
  land on Software. A short list of hardware occupation words is checked before Software: embedded,
  firmware, fpga, asic, rtl, pcb, analog, robotics, perception, motion planning. Only non-finance postings
  move. If any finance posting moved, section 1's gate would catch it.
- **Quant developer (D8).** Phase 3 found that a title naming the developer ("Quantitative Developer",
  "Quant Dev Analyst") is already Software in 0.3.7, even at a quant firm, so it now lands in `quant_dev`
  and nothing moves on the Finance board. `quant.quant_developer` holds the finance postings whose title
  names no developer but whose description is trading systems (62 on your install). The Software filter
  `quant_dev` also targets those when scoring, and polls the quant and fintech groups. Picking it doesn't add
  the Finance board to the profile.
- **"Analytics Co-op" stays where it is.** At a bank it's a finance posting today, so AI & Data doesn't claim a
  bare "Analytics" title; "Data Analytics Co-op" is the example instead.
- **`FACTS_VERSION` stays as it is.** If anything turns out to need a bump, I'll stop and ask.

## 7. Tech employer types

These are added to `config/companies.json`. Each type gets a `track` (finance, tech or both). Settings shows
finance types to Finance profiles and tech types to tech profiles. A Finance-only profile sees exactly
today's list, because every type that exists today is finance, or both for fintech and quant firms.

| Type | Label | Track | Examples |
|---|---|---|---|
| big_tech | Big Tech | tech | Amazon, Microsoft, Nvidia, Salesforce, Adobe, Netflix |
| ai_lab | AI Lab | tech | Anthropic, OpenAI, xAI, Cohere, Mistral |
| ai_infrastructure | AI Infrastructure | tech | Databricks, Scale AI, Together AI, CoreWeave |
| developer_tools | Developer Tools | tech | Vercel, Linear, Supabase, GitLab, Datadog |
| data_infrastructure | Data Infrastructure | tech | MongoDB, Snowflake, ClickHouse, Fivetran |
| cybersecurity | Cybersecurity | tech | CrowdStrike, Zscaler, Okta, 1Password |
| enterprise_saas | Enterprise Software | tech | ServiceNow, Workday, Notion, Figma |
| consumer_tech | Consumer Tech | tech | Airbnb, DoorDash, Pinterest, Spotify |
| semiconductors | Semiconductors | tech | Intel, AMD, Qualcomm, Broadcom, Micron |
| robotics_autonomy | Robotics & Autonomy | tech | Waymo, Zoox, Aurora, Waabi |
| defense_tech | Defense & Aerospace | tech | Anduril, Shield AI, SpaceX, Palantir |
| gaming | Gaming | tech | Roblox, Epic Games, Riot Games |
| high_growth_startup | High-Growth Startup | tech | Cursor, Sierra, Decagon, Harvey |
| canadian_tech | Canadian Tech | tech | Geotab, StackAdapt, Wattpad, Clio |
| research_lab | Research Lab | tech | Vector Institute, Mila, AI2 |
| hardware_devices | Devices & IoT | tech | Samsara, Verkada, Garmin |
| health_tech | Health Tech | tech | Oscar Health, Hinge Health, Abridge |
| fintech, quant_firm | (exist) | both | shared |
| every other existing type | (unchanged) | finance | |

- **Priors** for tech types point only at tech filters (for example gaming → `software.game_dev`). Finance
  categories never see them.
- **Scoring:** a recognized tech employer earns 7 company points only for a profile with a tech board. A
  Finance-only profile keeps 4 points for these employers, exactly as today.
- **New company keys** equal the company slugs postings resolve to today, so cluster keys don't move. The gate
  in section 1 checks this.

## 8. New sources (Phase 4, all in `tech/`)

Legend:
- ◇ shipped in 0.3.0 (re-fetch to verify)
- ○ new, with the ATS I **expect**; `?` marks a guess

Nothing ships unless its feed is fetched successfully in Phase 4. Apple, Google, Meta, Uber, Shopify, Tesla
and Hugging Face have no feed an existing adapter reads. They go to "not added" unless you approve an adapter.

- **big_tech:** ○oracle (oracle_hcm) · ○cisco (phenom?) · ○sap (successfactors?) · ○intuit (radancy?) ·
  ○ibm (avature?) · ○dell, ○snap (workday?) · ◇thomson_reuters (workday)
- **canadian_tech:** ◇stackadapt, ◇geotab, ◇ritual (greenhouse) · ◇wattpad (lever) · ◇benevity (ashby) ·
  ○clio, ○league, ○applyboard (lever?) · ○ada, ○tophat, ○vidyard, ○thinkific (greenhouse?) · ○d2l,
  ○kinaxis, ○opentext, ○hootsuite (workday?) · ○lightspeed, ○coveo, ○hopper (lever/ashby?)
- **ai_labs:** ○mistral (lever?) · ○thinking_machines, ○world_labs, ○magic, ○contextual_ai
  (ashby/greenhouse?) · ○stability_ai (greenhouse?)
- **research_labs:** ○ai2 (greenhouse?) · ○vector_institute · ○mila. The group is dropped if fewer than three
  feeds verify.
- **ai_infrastructure:** ◇coreweave (greenhouse) · ◇anyscale, ◇pinecone (ashby) · ○fireworks_ai, ○snorkel,
  ○labelbox, ○weights_and_biases (greenhouse/lever?) · ○langchain, ○deepgram (ashby?)
- **ai_apps:** ○cognition, ○hebbia (ashby?)
- **developer_tools:** ◇replit, ◇sentry, ◇temporal, ◇posthog (ashby) · ◇grafana_labs, ◇new_relic,
  ◇pagerduty (greenhouse) · ○netlify, ○circleci, ○sourcegraph, ○docker (greenhouse?) · ○render, ○neon
  (ashby?)
- **data_infrastructure:** ◇snowflake (ashby) · ◇dataiku (greenhouse) · ○confluent (ashby?) · ○dbt_labs,
  ○redis, ○singlestore, ○sigma_computing (greenhouse?) · ○hex, ○airbyte (ashby?)
- **cloud_infrastructure:** ◇pure_storage, ◇rubrik (greenhouse) · ◇hpe (workday) · ○nutanix, ○netapp,
  ○akamai (workday?) · ○digitalocean (greenhouse?)
- **security:** ◇okta, ◇zscaler (greenhouse) · ◇crowdstrike (workday) · ○palo_alto_networks, ○fortinet,
  ○tenable (workday?) · ○wiz, ○snyk, ○sentinelone, ○arctic_wolf, ○abnormal_security, ○chainguard, ○tanium
  (greenhouse?)
- **enterprise_saas:** ◇box, ◇miro (greenhouse) · ◇zapier (ashby) · ○hubspot, ○zendesk, ○grammarly,
  ○benchling (greenhouse?) · ○docusign (workday?) · ○atlassian (?) · ○canva (lever?)
- **consumer_tech:** ◇nextdoor, ◇roku, ◇coursera (greenhouse) · ◇quora (ashby) · ◇zillow (workday) ·
  ○etsy, ○thumbtack (greenhouse?) · ○whatnot (ashby?)
- **gaming:** ◇epic_games, ◇riot_games, ◇twitch (greenhouse) · ○ubisoft (smartrecruiters?) · ○unity
  (workday/greenhouse?) · ○ea (avature?) · ○take_two, ○niantic, ○scopely, ○bungie (greenhouse?) ·
  ○behaviour_interactive (smartrecruiters?) · ○mistplay (lever?)
- **semiconductors:** ◇micron, ◇applied_materials, ◇analog_devices, ◇cadence, ◇broadcom, ◇marvell (workday)
  · ○amd, ○texas_instruments, ○arm, ○lam_research, ○kla, ○nxp, ○microchip, ○globalfoundries (workday?) ·
  ○qualcomm (eightfold?) · ○synopsys (?) · ○tenstorrent, ○cerebras, ○groq, ○sambanova, ○lightmatter
  (greenhouse?) · ○etched (ashby?)
- **robotics_autonomy:** ○applied_intuition, ○kodiak, ○skydio, ○figure, ○wayve, ○motional, ○zipline
  (greenhouse/lever?) · ○physical_intelligence (ashby?) · ○boston_dynamics (workday?) · ○sanctuary_ai (lever?)
- **defense_aerospace:** ○saronic (ashby?) · ○epirus, ○rocket_lab, ○relativity_space, ○astranis, ○planet
  (greenhouse?) · ○blue_origin, ○mda_space (workday?)
- **devices_iot:** ◇motorola_solutions, ◇ciena (workday) · ○garmin, ○sonos, ○lucid (workday?) · ○ecobee,
  ○whoop, ○oura (greenhouse?)
- **bank_technology (D3):** tech-only sources filtered by search, sharing `company_key` with the finance
  bank sources: ○rbc_tech (phenom `query`) · ○td_tech, ○bmo_tech, ○cibc_tech, ○morgan_stanley_tech,
  ○citi_tech, ○barclays_tech, ○wells_fargo_tech, ○deutsche_bank_tech (workday `search` or a Technology
  facet) · ○jpmorgan_tech, ○goldman_sachs_tech (oracle_hcm `query`) · ○national_bank_tech (avature?) ·
  ○scotiabank_tech (successfactors?)
- **software_core / data_core / hardware_core:** a U.S. and a Canada LinkedIn source for each tech board
  (`linkedin_us_software`, `linkedin_canada_software`, and the same for data and hardware). Each carries
  3-4 tech queries. All LinkedIn requests already share one rate-limited lock.
- **fintech (tech folder):** ◇koho, ◇neo_financial (ashby) · ◇toast (greenhouse) · ○wealthfront, ○carta,
  ○addepar (greenhouse?) · ○questrade (?)
- **financial_services_tech (tech folder):** ○bloomberg (avature?) · ○american_express, ○visa (workday?)

### 8.1 What Phase 4 shipped (fetched 2026-10-22)

181 candidate feeds were fetched once each with the app's own adapters. Four research agents found the
identifiers on the employers' careers pages, without calling ATS APIs. 164 feeds ship in 22 `tech/` packs,
all 47 of the 0.3.0 employers among them:

| Pack | Sources | Pack | Sources | Pack | Sources |
|---|---|---|---|---|---|
| canadian_tech | 17 | robotics_autonomy | 10 | fintech | 6 |
| semiconductors | 15 | big_tech | 7 | ai_labs | 6 |
| security | 13 | enterprise_saas | 7 | defense_aerospace | 6 |
| developer_tools | 12 | consumer_tech | 7 | devices_iot | 6 |
| gaming | 12 | data_infrastructure | 6 | cloud_infrastructure | 4 |
| bank_technology | 11 | ai_infrastructure | 9 | ai_apps, financial_services_tech, software_core, data_core, hardware_core | 2 each |

Changes from the list above:
- **No `research_labs` pack.** Only Ai2 has a feed an adapter reads (Vector Institute uses ADP, Mila uses
  Workable), so Ai2 is in `tech/ai_labs` with the employer type Research Lab.
- **Bank technology** reads the finance sources' own endpoints. The Workday banks are filtered by their
  technology and data job families, read from each bank's facet list. JPMorgan, Goldman Sachs and RBC use a
  keyword. Bank of America, National Bank and Scotiabank are left out, because their adapters can't filter.
- **companies.json** gains 139 tech employers, only for the new sources. Each key is the slug its
  postings already had, so cluster keys don't move. The entries for Micron ("Micron Technology") and
  HPE (no `=hpe` alias) were adjusted because finance postings used those names.
- **A tech employer's HQ never stands in for a posting's location** (`intel/companies.py`). Without
  this, 39 finance postings at Cisco, Oracle, Kinaxis and others would have gained a country and moved
  in fit. The country stays in companies.json for the Companies view.
- **Existing shared tech employers are not in companies.json yet.** Anthropic's postings show "anthropic",
  the source name, today. An entry would rename them on the Finance board (75 postings), so it's a
  follow-up for you to decide.
- Not added, with reasons: see `tech-sources-phase4.md` in the session notes. Examples: Apple, Google and Meta have
  no adapter. Grammarly, Whatnot, Redis and Cerebras returned 404 tokens. Qualcomm, Lam Research and
  GlobalFoundries returned Eightfold 403s. The Atlassian, Docusign, AMD and Garmin iCIMS pages are unreadable,
  as are the EA and Bloomberg Avature pages. Arm and NetApp (Radancy) list postings with no titles.

## 9. Where today's 256 sources go (settings unchanged)

Fin and Tech are open postings on your install classified finance or as a tech board.

| Pack | Sources | Fin | Tech | Members |
|---|---|---|---|---|
| `finance/canadian_banks` | 11 | 4,719 | 556 | rbc, rbc_early, rbc_students, td, td_students, bmo, bmo_students, cibc, cibc_students, scotiabank_students, national_bank |
| `finance/bulge_brackets` | 12 | 15,901 | 5,428 | jpmorgan, jpmorgan_early, morgan_stanley, morgan_stanley_early, citi, citi_early, barclays, wells_fargo, goldman_sachs, bank_of_america_students, bank_of_america, deutsche_bank |
| `finance/boutiques_middle_market` | 10 | 453 | 24 | moelis, pjt_partners, houlihan_lokey_campus, houlihan_lokey, piper_sandler, william_blair, evercore_students, evercore, lazard, jefferies_campus |
| `finance/private_markets` | 7 | 474 | 81 | stepstone, blackstone_campus, blackstone, kkr, carlyle, apollo, brookfield |
| `finance/asset_managers` | 4 | 951 | 487 | blackrock, fidelity, vanguard, man_group |
| `finance/pensions_insurance` | 7 | 529 | 187 | cpp_investments, otpp, cdpq, cdpq_students, manulife, sun_life, sun_life_students |
| `finance/ratings_data` | 4 | 352 | 214 | moodys, sp_global, msci, msci_us |
| `finance/linkedin` | 3 | 1,261 | 810 | linkedin_us, linkedin_canada, linkedin_quant (queries unchanged) |
| `shared/quant_trading` | 28 | 949 | 1,153 | jump_trading, hrt, citadel, citadel_sec, point72, sig, imc, optiver_us, akuna, drw, two_sigma, tower_research, five_rings, pdt_partners, voleon, gts, virtu, old_mission, flow_traders, geneva_trading, vatic_labs, squarepoint, schonfeld, qube_rt, aqr, jane_street, worldquant, nwfintech_quant27 (off: citadel, citadel_sec, two_sigma, gts, nwfintech_quant27) |
| `shared/fintech` | 19 | 682 | 1,043 | stripe, plaid, ramp, brex, affirm, chime, robinhood, coinbase, wealthsimple, mercury, sofi, block, gemini, fireblocks, marqeta, lithic, alloy, betterment, upstart |
| `shared/financial_services_tech` | 6 | 1,254 | 1,684 | capital_one, capital_one_early, mastercard, mastercard_early, paypal, nasdaq |
| `shared/lists` | 15 | 2,942 | 17,684 | zapply_newgrad27, zapply_intern27, zapply_ca_jobs, derec4_newgrad27, sndsh_intern27, simplify_newgrad, simplify_intern26, simplify_intern27, vansh_intern26, vansh_intern27, vansh_newgrad27, cvrve_newgrad, canada_intern26, offseason_fall26, zapply_ca_intern (off: simplify_intern27) |
| `shared/swe_lists` | 2 | 65 | 1,626 | speedy_swe, zapply_swe_newgrad |
| `shared/ai_lists` | 1 | 28 | 176 | speedy_ai |
| `shared/big_tech` | 14 | 307 | 4,291 | amazon, amazon_newgrad, microsoft, nvidia, salesforce, salesforce_early, adobe, adobe_university, netflix, ebay, autodesk, workday_hq, zoom, hp (off: microsoft) |
| `shared/ai_labs` | 14 | 158 | 1,146 | anthropic, openai, xai, deepmind, cohere, perplexity, character_ai, midjourney, poolside, runway, imbue, suno, elevenlabs, cartesia (off: deepmind) |
| `shared/ai_infrastructure` | 9 | 101 | 1,078 | databricks, scale_ai, together_ai, baseten, modal, crusoe, lambda_labs, runpod, assemblyai |
| `shared/ai_apps` | 11 | 39 | 461 | cursor, sierra, decagon, mercor, glean, harvey, writer, typeface, braintrust, heygen, descript |
| `shared/developer_tools` | 10 | 45 | 377 | vercel, linear, supabase, retool, gitlab, postman, launchdarkly, warp, browserbase, datadog (off: retool) |
| `shared/data_infrastructure` | 10 | 76 | 792 | mongodb, elastic, cockroach_labs, clickhouse, planetscale, starburst, fivetran, hightouch, amplitude, mixpanel |
| `shared/cloud_infrastructure` | 3 | 28 | 330 | cloudflare, fastly, twilio |
| `shared/security` | 2 | 7 | 78 | 1password, vanta |
| `shared/enterprise_saas` | 14 | 108 | 750 | servicenow, notion, figma, airtable, asana, smartsheet, calendly, webflow, attio, dropbox, rippling, gusto, checkr, flexport (off: rippling) |
| `shared/consumer_tech` | 20 | 176 | 1,316 | airbnb, doordash, pinterest, reddit, lyft, instacart, discord, duolingo, spotify, squarespace, peloton, seatgeek, gopuff, faire, sweetgreen, glossier, target, comcast, disney, disney_early |
| `shared/gaming` | 1 | 5 | 217 | roblox |
| `shared/health_tech` | 5 | 100 | 122 | oscar_health, hinge_health, abridge, commure, openevidence |
| `shared/semiconductors` | 2 | 25 | 644 | intel, intel_early |
| `shared/robotics_autonomy` | 5 | 32 | 623 | waymo, zoox, nuro, aurora, waabi |
| `shared/defense_aerospace` | 4 | 202 | 3,675 | anduril, shield_ai, spacex, palantir |
| `shared/devices_iot` | 3 | 20 | 283 | samsara, verkada, neuralink |

That's 256 sources: 58 in `finance/`, 198 in `shared/` and 0 in `tech/` until Phase 4. The largest pack has
28. A script checked the assignment against `config.json`: every source appears once.

## 10. Phases and proofs

1. **This design.** Committed, then I stop for approval.
2. **Packs, selection and upgrade, with no new sources.**
   - New: `intel/sources.py`, the manifest and the packs. Root `config.json` loses its sources.
   - Rewired: `load_config()` everywhere, `cycle(sources=)` and the enrichers.
   - The build copies the packs; `--check` validates them.
   - Tests:
     - `finance/` ∪ `shared/` equals the v0.3.7 sources with the hash `ddb8d7057c16c87e`.
     - A Finance-only profile polls exactly today's 246.
     - No source defined twice, and no pack over 50.
     - The profile counts in 4.1.
     - With a test `tech/` pack: Finance-only polls 0 tech-only sources, Software-only polls 0 finance-only
       sources, Finance + Software polls the union with each shared source once.
     - Filter narrowing, the "All of Software" switch, and no profile means Finance.
     - Your own sources are always polled, and a Settings change applies on the next poll.
     - The upgrade test (5.4).
   - I stop and show you the counts and the test output.
3. **Tech taxonomy, filters and employer types.** Classifier tests for each filter, the finance suite
   unchanged, and the **Finance board gate** (section 1) run on a copy of your database.
4. **New sources in `tech/`, one group at a time.** Each feed is fetched once. Then the `companies.json`
   entries, the 0.3.0 name revival, `sources_version` 10 and the Finance board gate again.
5. **UI and docs.**
   - The Sources view groups by pack. Each row says which boards poll it, and rows not polled for your
     boards are dimmed. No new colors or buttons.
   - The onboarding filter step appears through `family_tree()`.
   - `PRODUCT.md` replaces "Every profile polls the same sources" with the folder rule and the Finance board
     guarantee. `docs/ARCHITECTURE.md` gets a Sources section.
   - Then the full test suites and the final report.

## 11. Where your rule overrides the brief

| Brief | Now | Why |
|---|---|---|
| Move the 0.2.5 tech sources and community lists into tech packs | They go to `shared/`: the Finance board keeps polling them, and tech boards poll them too | At least 1,474 finance postings (3 at fit ≥ 75) are found only by these sources (section 2.3) |
| Give each moved tech source `company_key`, `group`, `priority`, `geography` and `min_interval` | Today's sources keep their settings byte for byte. New sources get all five. The Sources view takes the group from the pack, and the employer comes from `companies.json`. | `min_interval` would slow polls the Finance board relies on, and any edit changes what installs receive |
| Split the LinkedIn sources so finance packs carry no software queries | `linkedin_us` and `linkedin_canada` keep their queries (5 of them software). The tech boards get their own LinkedIn sources with tech queries only. | Software queries also surface finance-classified roles such as quant-developer internships |
| A Finance-only profile must not poll a tech-only source | Holds: `tech/` is never polled by Finance | – |
| No saved profile polls finance only, as it does today | Holds, and it literally polls today's 246 sources | – |

## 12. Decisions left

| # | Question | Recommendation |
|---|---|---|
| A | A profile with Finance **and** a tech board also polls the new `tech/` sources. A finance role at a new tech employer (say, FP&A at Mistral) would then show on that person's Finance board as an addition. Nothing goes missing. Allow additions, or hide finance postings from `tech/` sources on the Finance board? | **Allow.** A Finance-only profile is unaffected either way. |
| B | Labels only: the Employer type filter and the "Why" line may name an employer type that's "Unclassified" today. No posting, fit or order changes. | **Accept.** |
| D3 | Bank technology for tech boards as separate search-filtered sources in `tech/` (the finance bank sources stay untouched). | **Yes.** |
| D4 | The GitHub Actions alert runner has no profile: poll every pack, including `tech/`, or only Finance's 246? | **Every pack**, because subscribers' filters decide alerts there. |
| D7 | Embedded, firmware and robotics titles move from the Software board to Hardware (non-finance postings only, checked by the gate). | **Yes.** |
| D8 | The Software filter `quant_dev` also targets finance `quant.quant_developer`, without adding the Finance board. | **Yes.** |
| D9 | One full facts recompute (about 45 min) on the first start after the update. The gate proves the Finance board comes out identical. | **Accept**, and ship Phases 3 and 4 in one release so it happens once. |
| D10 | Product and Design poll the tech and shared groups listed; Sales, Operations, People & Legal and Healthcare poll everything. | **As stated.** |
| D11 | Add the Software filter `qa_test` (SDET and QA automation)? | **Yes.** |
| D12 | Re-use 0.3.0 names (okta, micron…) with the `__since__` revival? | **Yes.** |
