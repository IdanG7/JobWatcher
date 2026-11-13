# Foothold

Your private career command center: broad job-market coverage, focused daily
ranking, fast alerts, and a lightweight application CRM.

Foothold was called Jobwatch. The repository, the setup file
(`Jobwatch-Setup-<version>.exe`), the program and data folders, the database and the
update files keep that name, so existing installs keep updating and keep their data.

Foothold continuously checks configured sources across company ATSs,
startup boards, quant firms, banks, big tech, LinkedIn, and community listing
repos. It indexes every role it sees, ranks each one against a transparent
profile, and only interrupts you for the matches that meet your notification
rules.

The source configuration includes a sample 2027 finance profile for Canadian
and U.S. recruiting; personalize it in Settings. Windows releases start with
a clean profile. The product also indexes software, quant, AI/data, hardware, product,
design, finance, sales, operations, people/legal, healthcare, architecture/engineering/construction,
and uncategorized roles are
all searchable.

## Start using it

### Install on Windows

Download **Jobwatch-Setup-<version>.exe** from [the latest release](https://github.com/IdanG7/JobWatcher/releases/latest)
and run it. It installs for the current user only (no administrator rights) into
`%LOCALAPPDATA%\Programs\Jobwatch` and adds Foothold to the Start menu. The installer
is not code-signed yet, so Windows may show **Windows protected your PC**: choose
**More info**, then **Run anyway**. Python and the dependencies are included; no API
key or account is required. Foothold opens in a window of its own (your default browser's
app mode, in Chrome, Brave, Edge or Vivaldi; other browsers open it in a tab; links to
postings open in your usual browser) and fetches
jobs automatically in the background, even with the window closed (Settings > Background
can start it at sign-in or stop it). Open it again any time from the Start menu.

**Updates download automatically.** Foothold checks for a new release every six hours
and downloads it in the background. When it is ready, a banner offers **Restart to
update**: when installation finishes, the page reloads on the new version, with your data
and settings kept. An update is installed only if it is signed with the
release key built into the app, matches its release and is newer than the running
version. To uninstall, use **Settings > Apps** in Windows; it asks whether to keep
your data (the default) or delete it.

The portable **Jobwatch-Windows.zip** is still published for 0.2.0, from before the
rename: extract it and double-click **Start Jobwatch.bat**. Its update banner installs
the app into Programs, which takes over the same data; the old folder can then be
deleted. Later releases ship the installer only. Copies from 0.1.13 or earlier need a
manual upgrade: stop the old copy in Settings > Background, run Setup, and open Foothold
from the Start menu. It uses the same data folder; delete the old extracted folder once
you have checked that your data is there.
Upgrading replaces the old **Jobwatch** Start menu entry with **Foothold**; pin it again if
you had pinned it to Start.
Internet access is needed to fetch postings. The first fetch can take several minutes.
The dashboard shows live collection progress, active sources and failures while
you use any tab. Results refresh as sources finish; **Sources** shows individual
source status and error details.

With a resume on, lists open on your short list: roles in a specialty you picked or your
resume shows, in a place you can work, still listed and posted in the last 30 days.
A role that requires citizenship or a clearance you haven't confirmed in Settings waits with the eligible ones.
Every other eligible role is one switch away. Explicit eligibility conflicts exclude roles; missing
requirements stay visible with review notes. Canada includes Canadian remote and
multi-country postings. Finance filters distinguish engineering and clinical QA
from financial audit and assurance, including at banks and trading firms.

Sources reports fetched versus reported counts, partial search windows, and
whether removals can be detected. Workday, Oracle and Phenom paginate within a
configurable safety limit; partial reads never close missing postings. Official
student feeds cover RBC, TD, BMO, CIBC and Scotiabank, plus National Bank's public
Avature board. LinkedIn guest search supplements these feeds with finance queries
and a 30-day rolling / 90-day initial lookback; its page limits and rate limits
mean it cannot guarantee every LinkedIn posting. LinkedIn lists postings without
their text, so Foothold fetches a description when you open the posting, and in the
background for the best-fitting ones, six every ten minutes, so their fit and pay
are read from the full text (`linkedin_description_budget` and
`linkedin_description_minutes` in config.json).

The bundle starts with a clean profile and no notification accounts. It excludes
the sender's database, resume, subscriber configuration, letters and portable state.
Recipient settings and private data live in `%LOCALAPPDATA%\Jobwatch`, apart from
the program, so updates and reinstalls keep them. Stop Foothold (Settings > Background)
before backing up that data folder.
Updated source defaults are merged on upgrade while preserving customized sources,
deleted defaults, private preferences and notification settings.
The package targets Windows 10/11 on x64 PCs.

To rebuild and verify the distribution on Windows (the installer needs
[Inno Setup 6](https://jrsoftware.org/isinfo.php); pass `--iscc` or set `ISCC` if it is
not in a standard location):

```powershell
python tools/build_windows.py --installer
python tools/verify_windows_bundle.py dist/Foothold-Windows.zip
python tools/verify_windows_installer.py dist/Jobwatch-Setup-<version>.exe
python tools/verify_windows_update.py      # version N updates itself to N+1 (throwaway key)
```

After 0.2.0, build with `--installer --no-zip` and skip the ZIP verifier.
The installer and update verifiers use a temporary installation and temporary
`%LOCALAPPDATA%`, and always uninstall afterwards. The ZIP verifier also uses
temporary app and data folders, so a copy you already run is not touched. The
installer verifier does use this account's real Start menu: it replaces a **Jobwatch**
or **Foothold** entry there and removes it on uninstall.
Each release adds its entry to `web/js/release-notes.js`: two to four one-line changes
that the app shows once, in a What's new card, after the install or update. The
JavaScript tests fail until the version in `version.py` has an entry.
Releases are built by CI from a `v<version>` tag matching `version.py`. CI signs
the update manifest with the `JOBWATCH_UPDATE_KEY` secret (an ed25519 key whose
public half is in `update_key.py`) and refuses to publish without it.
The maintainer sets the secret once from Git Bash:

```bash
gh secret set JOBWATCH_UPDATE_KEY --repo IdanG7/JobWatcher < ~/.jobwatch/update-signing-key.pem
```

Keep a secure backup of that private key outside the repository. Existing apps
trust its public half; losing the key requires a manual reinstall to trust a
replacement. This update signature is separate from Windows code signing, so
SmartScreen may still appear on the first install.

The builder downloads the [official Python embeddable distribution](https://www.python.org/downloads/release/python-3148/),
verifies its published SHA-256 checksum, bundles dependency wheels with license
notices, and records per-file checksums in `manifest.json`. It uses explicit file
and configuration allowlists. Build artifacts are ignored by Git.

### Run from source

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Populate the local database. The first run seeds alerts silently.
python watcher.py --once

# Open the daily dashboard at http://127.0.0.1:8787
python watcher.py --serve
```

The dashboard opens automatically and provides:

- a morning briefing with fresh, high-fit roles;
- explainable 0–100 fit scores and score reasons;
- full-text search and filters for role family, stage, location, startup,
  freshness, and minimum fit;
- a private application pipeline for saved, applied, interview, offer,
  rejected, and archived roles;
- notes, due dates, and next actions;
- source health and the last polling-run status;
- one-click CSV export.

Application notes live only in `jobwatch.db`. They are never sent to Discord,
included in `state.json`, or committed by the included workflow. The web server
binds to loopback by default and has no authentication, so do not expose it to
the public internet.

## The daily workflow

1. Open `python watcher.py --serve` and review **Worth your attention**.
2. Use **Discover** to narrow the full market to SWE, quant, startups, or any
   other family. A score is a sorting aid; every reason is visible.
3. Save promising roles to **Pipeline**, record the next action, and move them
   through the process.
4. Let Discord or Telegram handle time-sensitive postings between reviews.
5. Check **Sources** if coverage looks quiet; failures are visible instead of
   silently shrinking the search.


## Resume parsing & automatic matching

Install `requirements.txt` for PDF support, then open **Settings → Resume & matching**.
Upload PDF, DOCX or TXT (up to 5 MB), or paste the complete resume. Choose
**Preview extracted facts** to review education, graduation, GPA, skills, experience
and proposed profile changes. **Apply & enable matching** keeps your saved career
targets and adds resume experience, replaces demo skills with extracted skills,
and updates education and recruiting cycles. Save any profile edits before applying.
Geography and work authorization remain under your control; correct extracted
fields in the profile form below and choose **Save profile & rescore**.

While matching is enabled, Opportunities has a three-way switch. **Short list** (the
default) shows eligible roles in a specialty you picked or your resume shows, whose
location is known to be in your countries or remote, seen on their source in the last
7 days and posted in the last 30 (or with a deadline still ahead). A role in another
specialty, or one that names none, joins it when your resume's skills are most of what
the posting asks for. **Eligible** shows every role your resume does not rule out, and
**All roles** ignores the resume. Pause matching in Settings to turn it off everywhere.
Clear role/stage/geography and explicit eligibility conflicts are excluded regardless of
fit score. Preferred qualifications do not exclude a posting. Unknown requirements stay
visible with review notes in the job drawer, which also says why a role is off the short
list; matching is not a guarantee of eligibility. Today, Discord alerts, saved views and
CSV exports use the short list too (a saved view keeps the list it was saved on).
Results appear in batches during indexing.

Matching uses only structured facts. The resume's text is kept on this computer for
cover letters, and a resume uploaded as a PDF is kept as a file so the posting panel's
"One PDF to upload" can start with it; neither is exported or sent anywhere. Removing
the saved resume removes both, stops matching and leaves applied profile fields editable.

Settings › Resume also keeps up to five resumes as PDFs ("Resumes to send"): the main
one, which Foothold reads, and others that are only sent. The one that went into a
posting's PDF is written on that application. Under it, the resume check lists what a
rule can see (bullets that open with a duty or have no number, length for your career
stage, mixed date forms, missing contact details or headings), each with the lines it
is about and no score. On a posting's Apply tab, "What to tweak in your resume" shows
what the posting stresses most and whether your resume says it in those words, in
other words, or not at all. "Suggest wording" asks the model on this computer to reword
one line; a rewording that adds a number, a name or a claim the line doesn't have is
refused. Suggestions are text to copy into your own file: Foothold doesn't edit it, and
never suggests a line for work the resume doesn't show.
Incomplete/unreadable replacements preserve the saved resume. PDF extraction is
limited to 10 pages and 60,000 characters, with a 2 MB limit per decoded stream;
scanned PDFs need pasted text. DOCX XML is bounded before decompression.


## Cover letters

Letters are written on your computer by a free local model, with no account or
API key. Install [Ollama](https://ollama.com/download), then open
**Settings → Cover letters**. Foothold reads your graphics card and memory (on the
computer; nothing is sent) and suggests the best model that fits, a 2–17 GB
download, once. Any other model Ollama has can be picked there instead.

Add your past cover letters (PDF, DOCX, TXT or Markdown, up to 10). Open a job and
choose **Write letter**: Foothold takes the past letter closest to the posting, by
role type and wording, and adapts it. The past letter is your story: what you say
about yourself and your work at each company, in your words and layout, stays. Your
resume says what is true today, and the posting decides what changes: the date,
recipient, company, role and team, and the few sentences about why that firm or that
kind of role. Without past letters, a letter is written from your resume. A letter
takes 20–60 seconds with a graphics card. It's written in the background: the panel
shows each step, you can open other jobs meanwhile, and Foothold tells you when it's
ready. Opening the job again shows the letter in progress rather than starting a
second one.

The letter leans toward the posting. Before writing, the model picks the three
things the posting stresses most, in the posting's words, and the experience on
your resume that shows each. A requirement your resume doesn't show is left out.
The why-this-role sentences are written around those requirements. The paragraph
about the matching experience gets one added sentence that names the requirement,
and the rest of that paragraph stays as it was. Under the letter, **The posting asks
for** lists them, checked when the letter mentions them; click one that isn't to
turn it into a change request.

A past letter can be months old. Once per resume, the model reads it for your roles
with their dates and your exams with where each stands (passed, in progress or
planned), and Foothold keeps only what the resume says in those words. Dates are read
in any common format ("May 2025 – Aug 2025", "05/2024 – 08/2024", "Summer 2025",
"2023 – 2025"). A role that has ended since is written in the past tense, a current
one in the present, a passed exam is called passed rather than a candidacy, and one
that is planned or in progress is never called passed. The model checks each
sentence that mentions one and rewrites only the status, keeping what the sentence
says about the work: first in your past letter, before adapting it, so no sentence
of your story is dropped for being out of date, then in the new letter. The corrected
past letter is kept (until your resume, the model or the month changes), so only the
first letter waits for it. A company
your past letter talks about stays in the letter: where the model leaves it out (to
talk about a newer role instead, or by shortening the sentence), Foothold puts your
sentence about it back.

Foothold sets the top of every letter itself: your name and contact lines (from
your past letter, else your resume) and the date on the right, the recipient on the
left. The **To** line above the letter shows who it's addressed to: an address you
saved for that company and city, else the office the posting names, else just the
company and city. The local model reads the posting for the office's street, floor
and city, and for a named contact to write to. Foothold keeps only what the posting
actually says, and OpenStreetMap adds the postal code. **Find address** shows that
office first, then the street addresses OpenStreetMap has for the company: in the
posting's own city, and when it has none there, in the rest of the posting's location
(many "Toronto" roles sit in Markham or Mississauga), which the list then says. Bank
branches, cash machines and car parks are left out. An office mapped without a street
number is shown with the building at its map pin, marked for checking: the map often
lacks a company's published address and never its suite. Pick one, check it, and
**Save address**. It's then used for every letter to that company in
that city. A LinkedIn copy of a job has no posting text of its own, so Foothold uses
the text from the company's own copy of the same job when it has one.

To adjust a letter, type what you want in **Ask for a change** under it ("shorten
the second paragraph", "mention Bloomberg") and only that changes. The more exactly
you name the paragraph or sentence, the more reliably the model makes the change. If
the model leaves the letter as it was, Foothold asks once more, more firmly. A word
count for the whole letter ("keep it under 300 words") is met paragraph by paragraph. Read each letter
before sending: small models still slip now and then. Letters can be edited by hand,
and download as a one-page Times New Roman PDF or join the posting panel's "One PDF to upload" with your resume and other PDFs.
The posting, your resume and your letters never leave the computer; OpenStreetMap
gets only the company's name, the office street and the city.

## How ranking works

Collection and ranking are intentionally separate:

- **Collection is broad.** Every returned posting is stored before subscriber
  notification filters are applied.
- **Ranking is personal.** `profile` in `config.json` assigns weights for role
  family, career stage, geography, company type, and skills.
- **Alerts stay scarce.** The existing filters in `subscribers.json` decide
  what reaches quiet feeds and which watchlist matches create a loud ping.

The sample source profile boosts finance internships and new-grad roles,
Canadian and U.S. locations, banking and investment employers, and finance skills.
Senior roles and out-of-market locations rank lower but remain searchable.

Edit the `profile` object to retune the dashboard without changing collection
or alert behavior:

```json
{
  "profile": {
    "headline": "My finance search",
    "target_roles": ["investment_banking", "corporate_finance"],
    "target_countries": ["CA", "US"],
    "skills": ["valuation", "excel", "accounting"]
  }
}
```

## Sources

| Kind | Coverage |
|---|---|
| Greenhouse, Lever, Ashby, SmartRecruiters | Direct company boards, including a large startup/AI/fintech set. Ashby includes compensation where published. |
| Workday, Phenom, Eightfold, Oracle, iCIMS, Jibe, Radancy, Avature, SuccessFactors, Workable, UKG, Gem, Jobvite, Dayforce, Cornerstone, Taleo, SelectMinds, Connect | Banks, NVIDIA, Salesforce, Adobe, Capital One, Intel, PayPal, Mastercard, Disney, Netflix, Qualcomm, AMD, Microsoft, Stantec, WSP, AtkinsRéalis, Turner, and others. Jibe pages are read 5 seconds apart, the crawl delay its sites ask for. |
| Bespoke adapters | Amazon, Apple, Google, Uber, Verizon, ADP, Atlassian, Microsoft, and Jane Street. |
| LinkedIn guest search | Fresh U.S. and Canadian searches without a login, with repost filtering. |
| GitHub listing repos | Simplify, New Grad, internship, off-season, Canada, and salary-aware lists covering bespoke ATSs and long-tail companies. |

Cross-source deduplication prefers direct apply links and remembers alerts for
90 days. Staffing-agency patterns are excluded before alert fanout.

## Notifications

Foothold uses a two-speed model:

- **Apply now:** a ranked, capped, loud alert for matching categories at
  watchlist companies.
- **Complete feeds:** quiet digests containing every subscriber match,
  including anything omitted from the loud cap.

Recommended Discord channels are `#apply-now-intern`,
`#apply-now-full-time`, `#internships`, and `#full-time`. Unset optional hooks
fall back to `DISCORD_WEBHOOK_FULLTIME`, so a single channel also works.

Cloud alerts are optional. Set the repository variable `ENABLE_JOB_ALERTS=true`
and configure secrets in GitHub Actions to enable the scheduled poller:

- `DISCORD_WEBHOOK_FULLTIME` (required by the included workflow)
- `DISCORD_WEBHOOK_APPLY_INTERN`
- `DISCORD_WEBHOOK_APPLY_FULLTIME`
- `DISCORD_WEBHOOK_INTERN`
- `TELEGRAM_BOT_TOKEN` (optional)
- `HEALTHCHECK_URL` (optional)

The Windows app shows new short-list roles and the morning summary as Windows notifications, with nothing
to set up; they are on until Discord is connected, and **Settings → Notifications** switches them either
way. Windows itself must have notifications on (Windows Settings → System → Notifications); the page says
when it does not. Only the installed app shows them, never a run from source.

The Windows app can send Discord alerts too: open **Settings → Notifications**, paste a channel
webhook URL and press **Connect & send test**. New postings that match your profile are posted
while Foothold is running.

Webhook values in `subscribers.json` use `env:SECRET_NAME`; URLs do not belong
in the repository.

## Commands

```bash
python watcher.py --serve                 # daily dashboard
python watcher.py --serve --port 9000     # choose a local port
python watcher.py --once                  # one polling cycle + state export
python watcher.py                         # continuous local/VPS polling
python watcher.py --check                 # validate configuration and regexes
python watcher.py --verify                # test every enabled source
python watcher.py --list stripe           # inspect one source
python watcher.py --test shaun             # send notification examples
python -m unittest -v                     # run the full test suite (tests/, by area)
python -m unittest discover -s tests/letters -t .   # one area: app, letters, resume, matching, sources, store, install
```

## Add coverage

For a direct board, copy its token from its careers URL and add it to
`config.json`:

- `job-boards.greenhouse.io/TOKEN`
- `jobs.lever.co/TOKEN`
- `jobs.ashbyhq.com/TOKEN`
- `jobs.smartrecruiters.com/TOKEN`

For Workday, inspect the careers-page request to
`/wday/cxs/TENANT/SITE/jobs`. Run `python watcher.py --verify` after any source
change. To add a person, copy the example entry in `subscribers.json`, choose
their source set and filters, and configure their own delivery secret.

## Automation and storage

`.github/workflows/build-windows.yml` tests Python on Linux and Windows, runs
the JavaScript tests, validates configuration, and builds and verifies a clean
Windows installer on pushes to `main`, pull requests and manual runs. It also
tests a signed version N → N+1 update with a throwaway key. The `windows-package`
artifact contains the installer, plus the verified ZIP for the 0.2.0 bridge only.
Pushing a tag such as `v0.2.0` that matches `version.py` publishes a GitHub Release
with the installer, signed update manifest and signature (and the ZIP for 0.2.0).
The release remains a draft until all files are uploaded. Releases require the
`JOBWATCH_UPDATE_KEY` secret; tests and builds use no release or notification secrets.

`.github/workflows/jobwatch.yml` runs tests and configuration validation,
restores the portable state, polls repeatedly for roughly 25 minutes, and
chains a successor run when `ENABLE_JOB_ALERTS=true`. It is disabled by default.
`state.json` on the force-pushed `state` branch keeps
deduplication and alert queues durable across ephemeral runners.

Local SQLite stores richer searchable job metadata, run history, and the
application pipeline. Portable state deliberately excludes private pipeline
notes. Runtime dependencies are `requests` and `pypdf`; the dashboard uses
Python's standard-library HTTP server and plain HTML/CSS/JavaScript.
