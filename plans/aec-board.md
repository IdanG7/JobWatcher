# Architecture, Engineering & Construction board: design (Phase 1)

Status: **Approved 2026-11-10 (D1–D14 as recommended); built on branch `feat/aec-board`** (section 13 lists where the
build differs from this design). Branch `feat/aec-board`,
worktree `.claude/worktrees/aec-board`, cut from `main` at `4fc1599` (the Product & Design merge, 0.3.16 unreleased).
The brief is `plans/board-expansion-prompt.md` Part A; the research is `plans/architecture-engineering-board.md` and
`plans/architecture-engineering-sources.json` (2026-11-07). Product & Design (`plans/product-design-board.md`) is the
model: boards are data, so this board is mostly `config/` plus tests, and each code change is listed in section 8.

**How to read it.** Section 11 lists every open decision with my recommendation; each names the section with the
evidence. Counts come from a copy of your database on E: (466,962 postings) and from fresh reads of every source
on 2026-11-10. Scratch work is in `E:\aec-board\` (section 12).

## What you already decided (2026-11-10)

| Question | Your answer |
|---|---|
| Scope | A full board like Tech and Finance: co-op and intern through new grad, experienced, licensed and senior roles |
| Board and filters | As proposed: **Architecture, Engineering & Construction** (`aec`), filters Architecture, Structural, Civil & Infrastructure, Building Systems (MEP), Building Science & Sustainability, Construction & Project Delivery |
| Employers whose career sites refuse robots (AECOM, Ramboll, CIMA+, KPFF, Chandos, HH Angus, Pinchin, Salas O'Brien, Perkins&Will) | Read through LinkedIn company searches |
| Jibe sites asking for `Crawl-delay: 5` | Add the 5-second pause between pages (it also slows multi-page reads of the 11 Jibe sources polled today) |
| New readers | All four: AtkinsRéalis, HDR, Tetra Tech and Arup, Turner Construction |

---

## 1. The guarantee

Same as Product & Design: no posting of another board may land in a different board, filter, company or location,
and none may go missing; fit and order may change.

1. **Polling (a test).** Every board other than AEC polls the same sources with the same settings
   (`tests/sources/test_board_polling.py`). Sales, Operations and People & Legal poll every source today, so they
   gain the new `aec/` packs and nothing else (D13).
2. **Placement (on your postings).** `tools/board_gate.py place` / `place-compare` on the DB copy, `main` against
   the branch. Moves onto AEC are allowed only where you approve them (section 4, `--allow <from>:aec`). Any other
   move, a posting that goes missing, or a move from or to Finance or "other" that you didn't approve blocks the
   commit.

**Finance.** The board adds no Finance source and changes no Finance source setting. Its rules can take a posting
*off* Finance only where you approve it (D1: 25 construction jobs in the sample, all listed in 4.2). Nothing
moves *onto* Finance or onto "other".

---

## 2. Filters

Live postings are the 45,194 postings read on 2026-11-10 from the 120 sources this design keeps (section 7; Kimley-Horn
is read after the Jibe pause lands), placed with the draft rules: 29,238 (65%) land on the board.

| Filter | Holds | Typical titles | Live |
|---|---|---|---|
| `aec.architecture` · Architecture | Architects, intern architects, architectural designers and technologists, BIM/VDC, interiors, landscape and urban design | Intern Architect, Architectural Technologist Co-op, Project Architect, BIM Coordinator, Interior Designer (at a firm) | 1,537 |
| `aec.structural` · Structural | Buildings, bridges, foundations; structural EITs, designers, detailers | Structural EIT, Bridge Engineer, Steel Detailer, Senior Structural Engineer, P.Eng. | 2,427 |
| `aec.civil` · Civil & Infrastructure | Civil, geotechnical, transportation, traffic, water and wastewater, municipal, land development, survey | Civil Engineering Co-op, Water Resources Engineer, Traffic Signal Designer, Land Surveyor | 6,478 |
| `aec.building_systems` · Building Systems (MEP) | Mechanical, electrical, plumbing, fire protection, lighting, controls, commissioning in buildings | MEP Engineering Intern, Electrical Designer (at a consultancy), Commissioning Agent, Fire Protection Engineer | 3,973 |
| `aec.building_science` · Building Science & Sustainability | Envelope and facade, energy modelling, LEED and decarbonisation, acoustics, wind, restoration | Building Envelope Consultant, Energy Modeller, Acoustic Consultant | 152 |
| `aec.construction` · Construction & Project Delivery | Project and field engineers, project managers, superintendents, estimators, schedulers, project controls, construction safety | Field Engineer, Assistant Project Manager, Superintendent, Estimator, Project Controls Specialist | 9,691 |
| (no filter) | AEC-employer roles that fit none of the six: generic "Engineer I" or "Associate" at a firm, process and mining engineering at an engineering consultancy (D4) | Engineer I, Associate Principal, Process Engineering Intern | 5,026 |

Filter counts include the 46 board postings of the six sources left out (D6).

A filter is scored like the other boards' specialties: title words count most, then department, then description
phrases (Revit, ETABS, Civil 3D, HEC-RAS, ASHRAE, Procore, P6…), with tie priorities Building Science 6,
Structural 5, Building Systems 5, Architecture 4, Civil 3, Construction 2. French titles from Quebec employers are
read (génie civil, structure, mécanique du bâtiment, CVAC, chargé de projets, surintendant, estimateur, stagiaire).

---

## 3. How a posting reaches the board

`family_of` reads boards in order; AEC goes **last**, so a title another board's words already name stays there.
Then named rules (claims) take titles another board or "other" placed, on evidence.

### 3.1 Title words (any employer)
Unambiguous AEC titles: architectural…, intern/project/licensed architect, landscape architect, urban designer and
planners; structural EIT/designer/technologist/detailer; bridge engineer; civil (not civil rights, litigation,
service, commitment…); geotechnical; water resources, drainage, stormwater; highway, roadway, rail, transit,
tunnel, municipal, land development engineers; land surveyors; EIT **with** a built-environment word ("Civil EIT",
not Rockwell's bare "Engineer in Training"); MEP, HVAC, plumbing, fire protection (not service trades or software);
mechanical/electrical engineer **with** "buildings / MEP / HVAC"; commissioning agents; building science, envelope,
facade, energy modelling, LEED, acoustics consultants; `construction` (not loans, insurance, legal, sales, sourcing,
fiber/connectivity, research, analysts…); estimators, quantity surveyors, preconstruction, superintendents,
schedulers, design-build. Bare "superintendent", "foreman", "estimator" and "project executive" are fallback words:
they place a title only when nothing else did, and not for utility line, plant, retail or fleet work.

### 3.2 Named rules (claims)

| Rule | Takes from | When | Example |
|---|---|---|---|
| `engineer_at_aec_firm` | Software, other | A plain engineer's title at an engineering consultancy, architecture firm, contractor, owner or public infrastructure owner; not software, data, systems, sales, test, building-operator titles | "Engineer I" at HNTB, "Project Engineer" at a contractor, "Ingénieur(e) électrique" at AtkinsRéalis |
| `architect_at_aec_firm` | Software, other | An architect's title at those employers naming no IT word | "Junior Architect" at WSP, "Architecture Intern" at an architecture firm |
| `building_engineer` | Hardware | Mechanical/electrical/plumbing/lighting/energy engineers, designers, CAD technicians at those employers or with a building word; not power, utility or product work | "Electrical Designer" at EXP, "Mechanical Engineering Intern - Buildings" at Stantec |
| `structural_civil_engineer` | other, Software, Hardware | "Structural Engineer", structural interns, environmental/transportation/water/site engineers, transport planners, hydrologists, with an AEC employer, a building subject in the title, or three AEC phrases in the description | "Structural Engineer (Starship Infrastructure)" at SpaceX; not "Structural Engineering Co-op" at RTX |
| `designer_at_aec_firm` | Design, other | A designer at an AEC firm, not UX, visual, brand, product or industrial | "Designer II" at an architecture firm |
| `aec_role_at_firm` | other, Finance, Operations | Project managers/coordinators/directors, a firm's Associate and Associate Principal, drafters, surveyors, estimators, planners, schedulers, project controls, cost and contracts roles, AEC-subject technicians, inspectors and team leads, at consultancies, architecture firms, contractors and public owners; not admin, HR, finance, IT, marketing, biology/archaeology, trades | "Project Controls Analyst" at WSP, "CEI Inspector" at HNTB, "Associate" at an architecture firm |
| `safety_at_contractor` | other, Operations | Construction safety / HSE roles at a contractor | "Student HSE Coordinator" at Bird |
| `project_role_at_owner` | other, Operations | Project and construction managers at owners, developers and property-services firms; not leasing, IT, PMO, transformation | "Senior Development Manager, Project & Development Services" at Cushman & Wakefield |
| `building_systems_maker` | Software, Hardware, other | Engineers, project managers and designers at a building-systems maker whose title names HVAC, controls, fire, BAS/BMS, elevators, commissioning | "Controls Project Manager" at Johnson Controls; not "Material Planner" at Carrier |

One code change makes these rules reach engineering titles left in "other": `_claim` in `intel/taxonomy.py`
lets claims of tracks `tech` and `product_design` take tech-work titles from "other"; `aec` joins that tuple
(section 8). It changes no other board, since only AEC's own claims are added.

### 3.3 What stays where it is (guards)
- **Software and IT architects** ("Solutions Architect", "Enterprise Architect … Architecte" at HPE) stay Software.
- **Aerospace structures** ("Structural Engineering Co-op" at RTX, Sierra Nevada, Northrop: 22 in the sample) stay
  "other"; a bare "Structural Engineer" at an unknown employer stays "other" unless its description has building
  evidence (D8).
- **Power and utility engineering** (substations, transmission, protection & control, renewables) stays on
  Hardware where Hardware's words place it today (D3).
- **Service trades** (HVAC/fire alarm/controls technicians, installers, journeymen) and **property operations**
  (building operators, facility managers, porters) stay off the board.
- **Project controls read as cost accounting.** A claim never takes a Finance posting whose description has two
  or more Finance phrases (today's Finance safeguard), so e.g. AtkinsRéalis's "Project Controls Specialist" stays
  Finance.
- **Bank construction lending** ("Construction Loan Officer", CIBC's "Analyst/Associate, Lead Geotechnical
  Specialist") stays Finance.

---

## 4. Placement on your stored postings

`E:\aec-board\scripts\harness.py`: the 88,604-posting placement sample (every source's postings plus every stored
title with a candidate AEC word), classified with `main` and with the draft. Nothing moves anywhere but onto AEC.
It approximates `board_gate place` (same `classify`, but the employer is matched by its stored name and location is
not recomputed); the real `place` / `place-compare` run comes after approval (section 10).

### 4.1 Moves

| From | Postings | By title words | By rule |
|---|---|---|---|
| "other" | 1,641 | 1,343 | `engineer_at_aec_firm` 165, `aec_role_at_firm` 64, `structural_civil_engineer` 43, `building_systems_maker` 19, `architect_at_aec_firm` 3, `designer_at_aec_firm` 3, `safety_at_contractor` 1 |
| Software | 227 | 149 | `engineer_at_aec_firm` 69, `building_systems_maker` 8, `architect_at_aec_firm` 1 |
| Hardware | 158 | 0 | `building_engineer` 155, `building_systems_maker` 2, `structural_civil_engineer` 1 |
| Finance | 25 | 21 | `aec_role_at_firm` 4 |
| Design | 8 | 2 | `designer_at_aec_firm` 6 |
| Operations | 2 | 0 | `aec_role_at_firm` 2 |
| Healthcare | 1 | 1 | – |

AEC postings in the sample: 2,062 (2,062 moved, none left another board for anywhere but AEC).
Filters: construction 809, building_systems 418, civil 389, structural 219, (none) 115, architecture 91, building_science 21.
Stages: experienced 902, internship 591, senior 437, entry 79, new_grad 53.

Every move is onto AEC; no posting moves between other boards, and nothing moves onto Finance or onto "other".
The 88,604-posting sample holds 2,062 AEC postings, so these counts are the stored postings the rules touch, not
the board's size (section 2 has the live size).

### 4.2 Off Finance (D1)

25 sample postings, all construction or engineering work that Finance placed by description words or employer
(FP&A, accounting, operational risk); none names a finance occupation:

| Title | Employer | Finance placed it in | AEC filter |
|---|---|---|---|
| Construction Quality Manager (×5) | Microsoft | Accounting | Construction |
| Construction Project Manager; Senior/Principal Construction (Project) Manager (×5) | Anduril | FP&A | Construction |
| Principal Construction Project Manager | Microsoft | FP&A | Construction |
| Area Project Controls Manager, Data Center Construction | Meta | FP&A | Construction |
| Director, Construction Project Control | GlobalFoundries | FP&A | Construction |
| Construction Chemical / Gas Staff Engineer (×2) | Micron | Operational Risk | Construction |
| Assistant Director, Construction | General Motors | Operational Risk | Construction |
| Senior EHS Engineer — Construction & Contractor Compliance | Blue Origin | Operational Risk | Construction |
| Project Controls, Vice President, Construction Management | Morgan Stanley | Accounting | Construction |
| Postdoctoral Research Associate, Civil and Environmental Engineering (×2) | Carnegie Mellon | Equity Research | Civil |
| MGM HVAC & Controls | Johnson Controls | Corporate Strategy | Building Systems |
| Project Manager Multimodal, Freight and Economics | HNTB | Economic Research | Construction |
| Environmental Compliance Field Inspector - Rail and Transit | Parsons | Operational Risk | Civil |
| Document Controller (×2) | Stantec, Parsons | Accounting | (none) |

21 move by AEC's title words (Finance had no title word for them), 4 by `aec_role_at_firm`. CIBC's
"Analyst/Associate, Lead Geotechnical Specialist" and "Construction Loan Officer" titles stay Finance.

### 4.3 Off "other", which Finance profiles review (D2)

1,641 sample postings move from "other" (no board) onto AEC. Finance profiles review "other", so this changes
what they see there: these roles leave it.
- By title words, 1,343: data-centre, fab and launch-site construction, facilities MEP and civil (SpaceX 105, WSP 82,
  Stantec 76, Tesla 61, Johnson Controls 60, Micron 56).
- `engineer_at_aec_firm` 165 (Stantec 68, WSP 38, Thornton Tomasetti 33): structural, water, traffic, and the
  process, mining and I&C engineering of D4.
- `aec_role_at_firm` 64 (Parsons 23, HNTB 15, WSP 12): project managers and coordinators, project controls,
  planners, inspectors.
- `structural_civil_engineer` 43 (Blue Origin 11, Fehr & Peers 8, SpaceX 6, Tesla 4): facilities structural
  engineers and transportation engineers with building evidence.
- `building_systems_maker` 19 (all Johnson Controls: fire, controls and security project managers), and 7 more by
  the architect, designer and safety rules.

### 4.4 Off Software, Hardware, Design, Operations, Healthcare

- **Software 227.** Title words 149 (Parsons 45 drainage/roadway/bridge interns, Meta 17 data-centre construction,
  SpaceX 14 fire protection and site development, WSP 11 MEP interns); `engineer_at_aec_firm` 69 ("Engineering
  Internship/Co-op", "Engineer I - Roadway" at HNTB, Parsons, WSP, Granite: the bare word "engineer" had sent them
  to Software); `building_systems_maker` 8 (Carrier and JCI controls field engineers); "Junior Architect" at WSP.
- **Hardware 158.** `building_engineer` 155: mechanical and electrical engineers, designers and interns at WSP 38,
  Stantec 29, Parsons 16, Syska Hennessy 9, SpaceX facilities 8 ("Electrical Designer" at EXP, "Mechanical
  Engineering Intern - Buildings" at Stantec); 2 Carrier HVAC project managers; GE Vernova's "Civil/Structural
  Engineering Manager - Electrical Substations".
- **Design 8.** Designers at Parsons, WSP, HNTB, Stantec ("Project Designer", "Water Resources Engineer/Designer");
  "Director, Global Design & Construction" (Cloudflare) and "Project Manager, Design and Construction - R&D/Lab
  Buildouts" (OpenAI).
- **Operations 2.** "Design Support Technician" (WSP), "Deputy Program Manager/Construction Services Manager"
  (Parsons).
- **Healthcare 1.** "Pharmacy Construction and Infrastructure Project Manager" (Dana-Farber).
- **AI & Data, Product, Sales, People & Legal: none.**

### 4.5 Label-only changes
Of the 146 employers planned (polled and LinkedIn-only), only two match an entry today, Brookfield (private equity)
and OMERS (pension fund), and both sources are left out (D6). So no employer is retyped. Postings at the new
employers get a type label where they had "Unclassified". For the 45 employers in the draft so far, that is 2,518
sample postings (the other ~95 add more of the same kind; the real gate run counts them all): "other" 1,380, Software 417, Hardware 298, Sales 130,
**Finance 96** (JLL 23 capital-markets internships, Carrier 16, HNTB 14, Parsons 10, WSP 7, Trane 7), Operations 83,
AI & Data 64, Design 26, Product 12, People & Legal 9, Healthcare 3. Placement is unchanged by the label (the
comparison above already uses the new types); the Companies view and the employer-type facet show and count the
new label (D14).

---

## 5. Career levels

The board's own `stage_rules` run before the shared rules, for AEC postings only.

| Level | Stage | Titles | Why |
|---|---|---|---|
| Intern (stagiaire) | Internship | stagiaire, stage en/de | French co-op titles |
| Intern Architect | Entry | intern architect, architect in training, graduate architect | A graduate working toward licence, not a student |
| Engineer in Training | Entry | EIT, E.I.T., engineer in training | Graduate engineer before P.Eng./PE |
| Level I | Entry | Engineer I, Designer 1, Technologist, Level I | Consultancies' first grade |
| Field Engineer | Entry | field engineer, project coordinator, assistant project engineer | Contractors' first grade |
| Assistant PM | Experienced | assistant project manager, assistant superintendent, assistant estimator | The shared rules would read "manager" as Senior |
| Associate | Senior | Associate, Associate Principal, Associate Director (alone or after a comma) | A firm's rank, not "associate engineer" |
| Experienced | Experienced | project/construction/design manager, superintendent, estimator, project engineer, job captain | No level word |
| Licensed | Experienced | P.Eng., PE, SE, OAA, AIA, licensed architect | Licence with no level word |
| Senior | Senior | project executive/director, general superintendent, chief estimator, discipline/practice lead, studio director | Construction and firm leadership |

Live stage mix: Experienced 13,194 · Senior 11,075 · Internship 2,233 · New grad 1,492 · Entry 1,290. Senior roles
are well covered; early-career roles (internship, new grad, entry) are 17%.

---

## 6. Employers

**Track** `aec` with six employer types, all new (no type of today's overlaps):

| Type | Label | Examples |
|---|---|---|
| `engineering_consultancy` | Engineering Consultancy | Stantec, WSP, Hatch, AtkinsRéalis, Arcadis, HDR, GHD, Dewberry, Sargent & Lundy, Thornton Tomasetti |
| `architecture_firm` | Architecture Firm | DIALOG, B+H, HOK, NBBJ, HKS, Corgan, KPF, Sasaki |
| `contractor` | Contractor & Builder | PCL, EllisDon, Pomerleau, Bird, Ledcor, Aecon, Turner, Kiewit, Clark, Mortenson, DPR |
| `owner_developer` | Owner, Developer & Property Services | Minto, Cushman & Wakefield, JLL, BGIS |
| `building_systems` | Building Systems | Johnson Controls, Carrier, Trane, Daikin Applied |
| `public_infrastructure` | Public Infrastructure Owner | Metrolinx, Infrastructure Ontario |

About 140 company entries: the 112 employers polled, plus the LinkedIn-only employers so their postings get a
type. None exists today (checked by key and by name match), so no posting's employer is retyped (4.5). Each entry
records its HQ country, but like the tech types, AEC types don't lend it to a posting with no location
(`intel/companies.py`): WSP, Stantec, GHD and AtkinsRéalis hire worldwide. The track's resume vocabulary is in
section 9.

---

## 7. Sources

### 7.1 Packs (`config/sources/aec/`, polled only by AEC)

Read whole on 2026-11-10 with Foothold's own readers, one at a time; every URL each reader requested was checked
against that host's robots.txt with RFC 9309 rules (longest match wins). All pass.

| Pack | Sources | Postings | On the board |
|---|---|---|---|
| `consultancies` | 49 | 27,904 | 19,077 (68%) |
| `contractors` | 38 | 12,188 | 7,486 (61%) |
| `building_engineers` (structural, MEP, building science firms) | 10 | 1,809 | 1,439 (80%) |
| `architecture_firms` | 13 | 1,020 | 694 (68%) |
| `owners_operators` | 6 | 1,332 | 421 (32%) |
| `building_systems` | 4 | 941 | 121 (13%) |
| `linkedin` | 4 | partial window | |

121 sources. Readers: Workday 34, iCIMS 22, Oracle 13, Greenhouse 11, Dayforce 10, SuccessFactors 7, ADP 3,
Eightfold 3, Lever 3, Jobvite 3, Workable 2, Jibe 2, Phenom, Avature, BambooHR, plus five sources on the four new
readers (AtkinsRéalis on Connect, Turner on Cornerstone, HDR on faceted Taleo, Tetra Tech and Arup on SelectMinds).

**Read notes.**
- Kimley-Horn's iCIMS site is now `Disallow: /`; it moved to a Jibe host (1,363 postings, `Crawl-delay: 5`), so it
  is read there with the 5-second pause (section 8).
- Incomplete reads kept with the reader's own "incomplete" flag (missing postings are never closed): GHD 639/640
  (Oracle), Rosendin 370/371, HNTB careers 593 and Parsons 750 (Workday, one malformed row each), PCL 426/427
  (SuccessFactors).
- Black & Veatch reads whole when read alone (857/857, 276 s); it gets a 3-hour interval like the other slow sites
  (Arcadis 191 s, WSP 171 s, Fluor 99 s, DPR 80 s, Sargent & Lundy 68 s).
- Canada: Stantec 718, WSP 721, PCL 183, Hatch 270, AtkinsRéalis, Pomerleau, EllisDon, Bird, Aecon, Ledcor, GHD 248,
  Clark Builders, Minto… Canada counts for US sources are approximate (a "CA" state code reads as Canada).

**Left out for fit (D6):** Brookfield Properties (3 of 192 on the board; it would also resolve to Brookfield's
private-equity entry), Oxford Properties (0 of 54; resolves to a pension-fund entry), QuadReal (2 of 46), Tridel
(2 of 5), Comfort Systems (41 of 159, mostly trades) and Otis (1 of 25).

**Not added (sweep, 163 employers):** no reader 30 (Associated Engineering on Elevate, Smith + Andersen, Populous,
Hensel Phelps, Whiting-Turner, Gensler and Jacobs on Avature…), robots.txt disallows 37 (UKG `JobBoardView`,
SmartRecruiters API, Radancy `/search-jobs/`, iCIMS `Disallow: /`), blocked 10 (Mott MacDonald, Burns & McDonnell,
CBRE, SOM…), already covered 9, size or fit 9, reader fails 2 (Calgary, TransLink), no feed 66. The list goes into
`plans/architecture-engineering-sources.json`.

### 7.2 Today's shared groups that carry AEC postings
Stored postings the draft places on AEC, by the group of their source: `shared/lists` 886,
`shared/defense_aerospace` 269, `tech/big_tech` 179, `shared/semiconductors` 113, `tech/defense_aerospace` 63,
`shared/big_tech` 61, `shared/devices_iot` 61, `shared/swe_lists` 43 (data-centre and fab construction, facilities
MEP and civil at SpaceX, Meta, Microsoft, Micron, Blue Origin; internship lists). D10 decides which of these
the board polls.

### 7.3 Manifest
`folders.aec = {"fields": ["aec"]}`; `shared` (and `tech`, if D10 says so) gain `aec` in their `fields`.
`fields.aec.core` = the always-polled groups; `fields.aec.filters` maps each filter to its packs:

| Filter | Packs |
|---|---|
| Architecture | architecture_firms, consultancies, building_engineers |
| Structural | building_engineers, consultancies, contractors |
| Civil & Infrastructure | consultancies, owners_operators, contractors |
| Building Systems | building_engineers, consultancies, building_systems, contractors |
| Building Science | building_engineers, architecture_firms, consultancies |
| Construction | contractors, owners_operators, consultancies |

### 7.4 LinkedIn
- `linkedin_canada_aec`, `linkedin_us_aec` (verified 2026-11-07: 234 and 287 postings in a 30-day window), with
  senior queries added beside the co-op ones: structural engineer, civil engineer, project manager construction,
  superintendent, estimator, architect, mechanical engineer buildings, building envelope.
- `linkedin_aec_firms_canada` and `linkedin_aec_firms_us`: company searches (`companies`, LinkedIn's `f_C`, already
  supported by the reader) for the employers whose own sites refuse robots: AECOM 15656, Ramboll 165649, CIMA+ 33258,
  KPFF 17755, Chandos 3528550, HH Angus 134152, Pinchin 222051, Salas O'Brien 495856, Perkins&Will 9491, plus
  Associated Engineering 314533, Smith + Andersen 1011922, Mott MacDonald 7253, Burns & McDonnell 12902, Hensel
  Phelps 21743, Whiting-Turner 455780, Graham 622180, Gensler 5812, SOM 166050, Jacobs 4025, Terracon 17132,
  RWDI 38054, Buro Happold 14167, COWI 163233, Henderson 290678 (not HKS, now on its own Workday feed, nor TYLin,
  which posts on Introba's). Each id was confirmed by the
  company page and a guest search returning only that employer. Queries: engineer, architect, project manager,
  intern / co-op, superintendent, estimator, technologist.

---

## 8. Code changes

| Change | Where | Effect on other boards |
|---|---|---|
| `aec` joins the tracks whose claims may take tech-work titles from "other" | `intel/taxonomy.py` `_claim` | None: only AEC's claims are added |
| Four readers: AtkinsRéalis (Connect), Turner (Cornerstone), HDR (faceted Taleo), Tetra Tech and Arup (SelectMinds), with 32 tests | `watcher.py`; branches `feat/aec-readers-a` (`b8896c8`) and `feat/aec-readers-b` (`b11a9ab`, `9135203`) | None: new `ats` values. HDR's completeness check is made strict (the branch allowed a gap of 3) |
| 5-second pause between Jibe pages when the host asks for `Crawl-delay: 5` | `watcher.py` Jibe reader | The 11 Jibe sources polled today read their pages 5 s apart; single-page reads unchanged. Poll-time impact measured with `tools/poll_time.py` |
| AEC mixes in the placement and polling checks | `tools/board_gate.py` `MIXES` | None |
| Board name, icon (`building`) and note in onboarding | `web/js/fields.js` | None |
| What's new (0.3.16, beside Product & Design) | `web/js/release-notes.js` | None |

Everything else is data: `config/taxonomy.json` (board, filters, claims, levels, licences, program windows,
track), `config/companies.json` (6 types, ~140 employers), `config/skills.json` (3 groups), the `aec/` packs and
manifest, `config/source_defaults_history.json`, and docs (`README.md`, `docs/ARCHITECTURE.md`).

---

## 9. Resumes

The track reads an AEC resume the way Healthcare and Product & Design do:
- **Degree** opens the track: architecture (B.Arch, M.Arch, BAS, B.E.D.), civil/structural/environmental/
  geological/mechanical/electrical/architectural engineering (B.A.Sc., B.Eng., B.S.C.E.), construction management,
  building technology, architectural/civil engineering technology diplomas, urban planning, landscape architecture.
- **Role words** for experience lines: engineer in training, intern architect, technologist, drafter, estimator,
  superintendent, field engineer, project coordinator.
- **Signals per filter**: Revit/Rhino/SketchUp/Enscape → Architecture; ETABS/SAP2000/RISA/Tekla/RAM → Structural;
  Civil 3D/HEC-RAS/SWMM/Synchro → Civil; HVAC/ASHRAE/load calcs/Trane TRACE/HAP → Building Systems; IES VE/eQUEST/
  EnergyPlus/WUFI/LEED → Building Science; Procore/P6/Bluebeam/takeoffs/RFIs/submittals → Construction.
- **Skills** (3 new groups, ~45 skills): `aec_design` (Revit, AutoCAD, Civil 3D, MicroStation, Rhino, SketchUp,
  Navisworks, BIM 360/ACC, Enscape, Lumion), `aec_analysis` (ETABS, SAP2000, SAFE, RISA, RAM, Tekla Structural
  Designer, STAAD, HEC-RAS, SWMM, Synchro, IES VE, eQUEST, EnergyPlus, OpenStudio, WUFI, THERM, AGi32/DIALux,
  Trane TRACE/HAP), `aec_delivery` (Procore, Primavera P6, MS Project, Bluebeam, On-Screen Takeoff/PlanSwift, Sage
  Estimating, OSHA 30, Gold Seal), plus today's tools and soft skills.
- **Licences** (read only for AEC postings): P.Eng., EIT, PE, FE/EIT (US), SE, licensed architect (OAA, AIBC, OAQ,
  AAA, NCARB), CET/C.Tech, LEED AP/GA, PMP, Gold Seal, OSHA 30. A licence the posting requires and the profile
  doesn't hold costs fit, as on Healthcare; EIT eligibility counts as pending.
- **Program windows** (Calendar): Canadian co-op terms (Winter term recruiting Sep–Oct, Summer Jan–Feb, Fall
  May–Jun), US summer internships recruited Sep–Nov, new-grad hiring Sep–Nov, and the EIT application at graduation.
- Fixture resumes: a civil co-op student, a structural EIT, an intern architect, a construction PM (senior), a
  French civil engineer, recorded with `tools/resume_record.py`.

---

## 10. Checks before commit
- Python and web test suites (baselines in `E:\aec-board\baseline`: py and js).
- New tests: filters and claims (positive and guard titles from sections 3–4), levels, employers, packs and
  manifest, polling per profile (AEC alone, Finance + AEC, Software + AEC), readers (32), the Jibe pause, resume
  fixtures.
- `board_gate place` / `place-compare` on the DB copy with `--allow` for the approved moves; report every move off
  Finance and "other".
- `tools/poll_time.py` per profile.

---

## 11. Decisions

| # | Decision | Recommendation | Evidence |
|---|---|---|---|
| D1 | 25 construction and engineering postings move off Finance (sample) | **Move them**: Finance placed each by description words or employer, none names a finance occupation. Keeping them on Finance would need a code change in `classify` (AEC's title words leave Finance no title signal), so the alternative costs code | 4.2 |
| D2 | 1,641 sample postings move off "other" onto AEC, which changes what Finance profiles see in "other" | **Accept**: giving these roles a board is the point of the board | 4.3 |
| D3 | Power and utility engineering (substations, transmission, protection & control, nuclear electrical) at AEC employers | **Stays on Hardware** where Hardware's words place it today: 2,628 live postings from AEC sources stay there, mostly this work (Sargent & Lundy 655, WSP 176, Black & Veatch 121, AtkinsRéalis 107, Kiewit 105, HDR 96). AEC takes such a title only when Software had it by the bare word "engineer" ("Transmission Line Engineering Intern" at WSP) or it was in "other". Alternative: AEC takes all power work at AEC employers (a data change: about 1,000 of those 2,628 move to AEC) | 3.3 |
| D4 | Engineering at AEC employers outside the six filters (process, mining, metallurgy, pipeline, I&C at Stantec, WSP, Hatch) | **On the board with no filter**: today they are on no board. Alternative: leave them in "other" | 4.3 |
| D5 | Building-systems makers (Johnson Controls, Carrier, Trane, Daikin Applied): 13% of their postings are AEC; the rest is product engineering for Hardware/Software | **Keep the four** in their own pack, polled only for the Building Systems filter and when no filter is picked | 7.1 |
| D6 | Six sources left out for fit (Brookfield Properties, Oxford Properties, QuadReal, Tridel, Comfort Systems, Otis) | **Leave out** | 7.1 |
| D7 | Primoris (256 of 747 on the board) and Rosendin (197 of 370): trade-heavy contractors | **Keep**; they are large US civil/electrical builders with field-engineer and PM roles | 7.1 |
| D8 | Bare "Structural Engineer" or structural internship at an employer of unknown type with no building evidence | **Stays "other"** (22 aerospace structures internships in the sample would otherwise land on AEC) | 3.3 |
| D9 | Ship in 0.3.16 beside Product & Design (both unreleased) | **Yes**; one release-notes entry | 8 |
| D10 | Which of today's groups AEC polls besides its own packs | **Core: `shared/lists`.** Construction, Building Systems and Structural also poll `shared/big_tech`, `tech/big_tech`, `shared/semiconductors`, `shared/defense_aerospace`, `tech/defense_aerospace` (data-centre, fab and facilities work: ~680 stored postings). `tech` gains `aec` in its folder fields | 7.2 |
| D11 | Six filters; 17% of board postings (5,026) fit none | **Keep six**; no seventh "Power & Energy" filter (D3 keeps power on Hardware) | 2 |
| D12 | LinkedIn: 2 keyword searches with senior queries, 2 company searches (24 employers) | **As listed** | 7.4 |
| D13 | Sales, Operations and People & Legal poll every source, so they gain the `aec/` packs (121 sources) | **Accept**, as with Product & Design | 1 |
| D14 | Postings at the ~140 new employers get an AEC type label where they had "Unclassified" (sample: 2,518, of them 96 on Finance, mostly JLL capital-markets internships) | **Accept**: placement is unchanged; the label is true. JLL's Finance internships show "Owner, Developer & Property Services" | 4.5 |

Approved 2026-11-10: "Approve all".

---

## 12. Scratch (E:\aec-board)
`live_copy.db` (copy of your database, 466,962 postings), `code-main` (`git archive 4fc1599`), `code-draft`
(scratch copy with the draft rules), `scripts/` (`aec_taxonomy.py` the draft, `harness.py`, `live_census.py`,
`try_titles.py`, `moves.py`, `verify_sources.py`, `robots_check.py`, `pack_totals.py`), `verify*/` (fresh reads),
`readers-a/`, `readers-b/`, `research/` (the sweep), `baseline/` (test baselines, placement and census outputs).

---

## 13. Build notes (where the build differs from the design)
- **Consultancies split in two.** A pack holds at most 50 sources (`intel/sources.py` `MAX_PACK`), and
  consultancies came to 53, so the US civil, water, transport and power firms (28) are
  `aec/infrastructure_consultancies.json`; every filter that names `consultancies` names it too, so polling is as
  designed. Packs: consultancies 25, infrastructure_consultancies 28, contractors 40, architecture_firms 13,
  building_engineers 10, owners_operators 6, building_systems 4, aec_core 4 (LinkedIn): 130 sources.
- **Five more Jibe sources.** With the 5-second pause, the sweep's Jibe sites that ask for `Crawl-delay: 5` are read
  too: Bowman, Mead & Hunt, TRC (infrastructure consultancies), Haskell, Brasfield & Gorrie (contractors), each
  read whole on 2026-11-10 and each with a company entry.
- **D10's groups are file names.** The manifest names groups, not folder/group paths, so Construction, Building
  Systems and Structural poll `big_tech`, `semiconductors` and `defense_aerospace` in every folder AEC may read:
  `tech/semiconductors` (21 sources) comes along with `shared/semiconductors`.
- **What's new.** The 0.3.16 card holds at most four items, so the AEC entry replaced Product & Design's "Over 100
  more employers' job sites", and its resume and Calendar lines now cover both boards.
- **HDR closes postings by job number.** Its Taleo total counts 3 postings the pager never lists, so every read
  is incomplete by the reader's strict check, and an incomplete read closed nothing (a closed posting stayed active
  until the 90-day prune). Checked on 2026-11-10 (2,319 counted, 2,316 listed; 2,331 and 2,328 at 13:50): the 3 are
  hidden requisitions, not duplicates or a location filter. Every sort order lists the same 2,316, with no row
  repeated and every page full but the last (16 rows where the total implies 19), and no search lists them (German,
  multi-line, all six sorts). Every facet and filter counts them as the total does: one each in Bridges (part-time,
  Orlando FL), Water (San Diego CA) and Highway + Road (Walnut Creek CA), all US and posted over 28 days ago; every
  other field, country and date window lists in full. No count the site sends leaves them out, so the strict check
  stays (accepting the shortfall would be a tolerance again). Instead the keyword field, which matches a whole job
  number (a listed posting counts 1, each of the 21 postings that closed between the two reads counts 0), confirms
  each stored posting missing from a read that ended short: the poller gives Taleo readers their open postings
  (`_open_ids`), the reader looks the missing ones up (at most 100 a read, after a listed one confirms the lookup
  works) and returns those counted 0 as `listing.gone`, and only those are missed toward closing, as a complete
  read's would be. The Sources page then says "Detects removals". One real poll on a scratch database (2026-11-11,
  127 s) looked up the 20 stored postings missing from the read and found all 20 gone; 3 of the previous day's closed
  numbers were listed again (HDR re-posts), which the three-miss rule allows for. Unverified: that one of the 3
  hidden postings counts 1 (none of their numbers is known); a posting the site still lists does.
- The sweep's employers left out, with why, are in `plans/architecture-engineering-sources.json` (`not_added`).
- **Precision fixes found while writing tests** (each takes postings back off the board that the approved draft moved):
  a bare estimator no longer comes in when the title says collision, damage, auto, appraisal, material or cost (Tesla
  body shops, Allstate, defense proposal pricing: 20 of the sample's 57 estimator moves; a cost estimator at an AEC
  firm still comes in through `aec_role_at_firm`); `civil` skips registry, records, status, unions and partnerships
  ('Civil Registry Associate', 14); the construction phrase skips surveillance ('Construction Surveillance Technician',
  a security role, 18); and only a construction scheduler is the board's by title (a defense 'Project Scheduler', 10,
  stays where it was; one at an AEC firm comes in by the firm claim).
- **Licences.** P.Eng. is also read from 'Professional Engineer (PE) license' and 'Registered with PEO as a P.Eng.'.
  The EIT Calendar item reads 'EIT applications ... typically follow graduation', like every Calendar program title.
- **Senior resumes.** A construction resume's titles ('Project Manager', 'Superintendent', 'Estimator') reach the board
  only through the employer's type, which a resume doesn't give, so `work_years` (intel/resume_insights.py) also counts
  a job whose title the open track's role words name, and the AEC role words gain project manager/director/engineer,
  construction and site manager and their French forms. Only resumes that open the AEC track read them: all 672
  readings of the 14 existing fixture resumes are unchanged (tools/resume_record compare against main).
- **Slow readers.** Arup (140 s), Tetra Tech (106 s) and HDR (104 s) read for over a minute, so they poll every 3 hours
  like the other slow sites.
- **Employer keys.** As for Product & Design, each new employer is keyed by the slug its stored postings already
  resolve to, so no company or cluster key moves (checked on all 466,962 stored postings: 0 move; 2,547 only gain an
  AEC type, D14). Ten entries take their stored slug (`atkinsr_alis`, since slugs drop the é; `trc_companies`,
  `syska_hennessy_group`, `aecon_group`, `zachry_group`, `michael_baker_international`, `bowman_consulting_group`,
  `kci_technologies`, `vanasse_hangen_brustlin`, `langan_engineering_environmental_services`), and the spellings
  postings use for one employer get entries of their own with exact names: Carrier / Carrier Global, GFT / Gannett
  Fleming, JLL / Jones Lang LaSalle, WSP / WSP in Canada / WSP in the U.S. A source's `company_key` is the key most
  of the employer's stored postings carry (Carrier: `carrier_global`; GFT: `gannett_fleming`), so its postings
  cluster with the lists' copies.
- **Skills.** Tech skills are read on every posting outside Finance ('other' included), so the tech track's
  `skills_from` names `aec` and the postings moving off 'other' keep reading them; Product & Design's names it too
  (Rhino, SketchUp, Adobe). An AEC resume reads both, as AEC postings do (`skills_also`: product_design, tech).
