# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Job seekers comparing openings, tracking applications, and preparing application material. The current user wants matching to adapt to their uploaded resume, including computer science and software roles.

## Product Purpose

Foothold collects openings from employer and listing sources, helps users find relevant jobs, and keeps applications and deadlines organized. Success means the user can trust the extracted resume facts, understand recommendations, and act on relevant openings quickly.

## Operating Context

A local Python service runs in the background on Windows and serves a browser interface. Existing workflows include Opportunities, Applications, Companies, Calendar, Analytics, Sources, and Settings. Users upload PDF, DOCX, or text resumes and review proposed profile changes.

## Capabilities and Constraints

- Resume extraction and deterministic parsing run locally.
- Cover letters are written on this computer by a model that Ollama serves on localhost (Foothold reads the graphics card and memory, suggests the best model that fits, and can download it). No API key, and the posting, resume and past letters never leave the machine. The user keeps up to 10 past letters; for each posting the closest one, by role type and wording, is adapted with as few changes as it takes (company, role, team, recipient, date, the why-this-firm sentences), and a change box under the letter applies one requested edit at a time. Without past letters, a letter is written from the resume.
- The current taxonomy, defaults, and many screen queries favor finance. The user has confirmed that the product should adapt to the uploaded resume, including software roles.
- Keep applications, resume data, explicit geography and authorization preferences, source settings, and update behavior intact.
- Retain the existing Python and browser JavaScript stack.
- Existing light and dark themes and keyboard navigation are part of the interface.
- No requirement for separate CS and finance profiles has been established.

## Brand Commitments

The product is named Foothold (renamed from Jobwatch on 2026-10-16; tagline "Get a foothold."). The interface, Start menu entry, shortcuts, launcher, Discord messages and generated PDFs say Foothold. The data folder (%LOCALAPPDATA%\Jobwatch) and its log file, the setup file name (Jobwatch-Setup-*.exe), the installer's AppId and the sign-in start entry keep the Jobwatch name so existing installs upgrade in place and keep their data; on-screen copy names those literally where the user has to find them.

Identity: a step mark (a ledge) in paper on an ink tile, used for the favicon, the Windows icon and the header lockup, with a lowercase condensed "foothold" wordmark.

Visual direction (2026-10-16): paper and ink in both themes. Selected and active states invert to ink. Green marks good fit, new roles and positive states, amber marks deadlines and warnings, and red marks failures. The user rejected a highlighter-yellow accent, so don't use highlight bands or yellow. Instrument Sans for text (condensed widths for headings and large figures) and JetBrains Mono for figures that line up (fit, dates, counts). Hierarchy comes from type, rules and whitespace. Today is unboxed, with ruled sections like a printed brief, while data tables, settings, the board and the calendar keep light containers.

Controls stay quiet: at most one primary (ink) action per view. Secondary actions go in a single menu (View or ⋯), and row actions appear on hover or focus. Collection progress lives in a hover card on the header's Live button rather than a banner. Settings and Sources aren't tabs: the gear sits beside the theme toggle, and Sources is linked from the Live card. Settings works like an app's settings window, not a long page: a sidebar of sections (Profile, Alerts, App) shows one section at a time (`#/settings?tab=…`), and each section is titled cards of rows with the label on the left and its control on the right. Long multi-select lists are toggle chips with a filter. One floating save bar covers profile edits across sections, and a dot marks sections with unsaved changes.

The posting panel shows only what is known. The facts that decide whether to apply (deadline, pay, level, work model, cycle, when it was posted) sit in one strip under the header, and anything the posting doesn't state is left out rather than listed as "Not specified". Requirements appear only when stated, with the posting's own words cut at whole words. Confidence scores, internal source names and setup jargon never appear in the panel. Cover letter, application PDF and contacts sit together under Prepare, and where the listing came from is small print at the end.

Fields tailor the app. A first run (no saved profile) opens a short setup at `#/welcome` that asks for fields (finance and/or job families such as software or AI & data), finance areas if finance was picked, study stage, graduation and cycles, and where to work. The chosen fields are stored as the profile's `fields` and decide what Settings shows: finance areas and finance employer types only for finance, and skill groups that fit the fields. Fields never hide saved choices, and setup can be re-run from Settings without losing the rest of the profile. Each profile polls the sources its boards need (a board is a field picked in setup). Sources live in packs under `config/sources/`, and a pack's folder decides which boards may poll it: `finance/` only Finance, `tech/` only the tech boards (Software, AI & Data, Hardware, Product, Design) and `shared/` both. The Finance board polls every `finance/` and `shared/` pack: every source it polled in 0.3.7 with the same settings, plus employers whose feeds carry finance roles too (a tech employer with 10 or more finance postings, or a finance search of a big tech career site), so it keeps everything it showed and only gains postings; before a release that touches sources or classification, a gate recomputes a copy of a real database and compares the Finance board posting by posting. A tech board polls its core groups plus the groups of the filters picked (Software → Backend…), or of every filter when none is picked. Sales, Operations, People & Legal and Healthcare poll every source, and a source the user added is always polled. Tech filters and tech employer types (shipped in 0.3.0, taken out in 0.3.1) are back: a tech employer type may label a finance posting at that employer, but never changes its fit or where it is placed. An upgrade adds the sources a release adds, including the 0.3.0 tech employers, which count as new again, and removes a source the bundle no longer ships (unless the user re-pointed it) with its postings, keeping any with an application. Resume matching for tech resumes is kept on the `cs-tech` branch and in a git stash.

Standing preferences: a modern, intuitive, professional work tool with real UI elements and its own identity rather than an AI-generated template look. Avoid stock indigo or purple accents, Inter, rounded bordered cards around everything, rows of buttons, unlabeled status dots and greeting headlines. No themed or conceptual worlds. Light and dark themes are equal citizens. Keep the redesigned Opportunities layout and behavior.

## Product Principles

- Recommendations must follow supported resume evidence and user preferences.
- Explain inferred facts and allow review before applying profile changes.
- Prioritize finding, reviewing, and tracking relevant opportunities over collection statistics.
- Keep collection health transparent without overwhelming routine work.
- Preserve local operation and existing user data.
