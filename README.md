# Jobwatch

Your private career command center: broad job-market coverage, focused daily
ranking, fast alerts, and a lightweight application CRM.

Jobwatch continuously checks **212 enabled sources** across company ATSs,
startup boards, quant firms, banks, big tech, LinkedIn, and community listing
repos. It indexes every role it sees, ranks each one against a transparent
profile, and only interrupts you for the matches that meet your notification
rules.

The source configuration includes a sample 2027 finance profile for Canadian
and U.S. recruiting; personalize it in Settings. Windows releases start with
a clean profile. The product also indexes software, quant, AI/data, hardware, product,
design, finance, sales, operations, people/legal, and uncategorized roles are
all searchable.

## Start using it

### Share a Windows copy

Download **Jobwatch-Windows.zip** from [the latest release](https://github.com/IdanG7/JobWatcher/releases/latest),
or build `dist/Jobwatch-Windows.zip` locally. The recipient extracts the entire ZIP and
double-clicks **Start Jobwatch.bat**. Python and the dependencies are included;
no installation, administrator access, API key or account is required. The app
opens in the browser and fetches jobs automatically while the console stays open.
Internet access is needed to fetch postings. The first fetch can take several minutes.

The bundle starts with a clean profile and no notification accounts. It excludes
the sender's database, resume, subscriber configuration, letters and portable state.
Recipient settings and private data live in `%LOCALAPPDATA%\Jobwatch` and survive
replacing the extracted app folder. Close Jobwatch before backing up that data folder.
The package targets Windows 10/11 on x64 PCs.

To rebuild and verify the distribution on Windows:

```powershell
python tools/build_windows.py
python tools/verify_windows_bundle.py dist/Jobwatch-Windows.zip
```

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

Application notes and saved cover letters live only in `jobwatch.db`. They are never sent to Discord,
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

## Cover letters

Open a role in **Opportunities** and scroll to **Cover letter**. Enter your name,
relevant background in first-person sentences, and optionally why the role interests
you. **Generate draft** creates a local template using that text, the role title,
company, and skills mentioned in the posting. No API key or external AI service is
used; review the draft before sending it.

Edit the letter and choose **Save letter** to keep it for that job. Regenerating
previews a replacement and leaves the saved letter intact until you save again.
**Copy** and **Download .txt** use the current editor text, including unsaved edits.
Letters persist independently of the application tracker and are excluded from
portable state and CSV exports. Resume optimization remains out of scope.

## Resume parsing & automatic matching

Install `requirements.txt` for PDF support, then open **Settings → Resume & matching**.
Upload PDF, DOCX or TXT (up to 5 MB), or paste the complete resume. Choose
**Preview extracted facts** to review education, graduation, GPA, skills, experience
and proposed profile changes. **Apply & enable matching** keeps your saved career
targets and adds resume experience, replaces demo skills with extracted skills,
and updates education and recruiting cycles. Save any profile edits before applying.
Geography and work authorization remain under your control; correct extracted
fields in the profile form below and choose **Save profile & rescore**.

Opportunities automatically enables **📄 Resume match** while matching is enabled.
Click that chip to show all roles for the current view; pause matching in Settings
to change the default. Clear role/stage/geography and explicit eligibility conflicts
are excluded regardless of fit score. Preferred qualifications do not exclude a
posting. Unknown requirements stay visible with review notes in the job drawer;
matching is a shortlist, not a guarantee of eligibility. Saved views, their alerts
and CSV exports use the same filter. Results appear in batches during indexing.

Only structured matching facts are saved locally. Original documents, raw text,
contact details and accomplishment bullets are not retained or exported. Removing
the saved resume stops matching and leaves applied profile fields editable.
Incomplete/unreadable replacements preserve the saved resume. PDF extraction is
limited to 10 pages and 60,000 characters, with a 2 MB limit per decoded stream;
scanned PDFs need pasted text. DOCX XML is bounded before decompression.

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
| Workday, Phenom, Eightfold | Banks, NVIDIA, Salesforce, Adobe, Capital One, Intel, PayPal, Mastercard, Disney, Netflix, and others. |
| Bespoke adapters | Amazon, Microsoft, and Jane Street. |
| LinkedIn guest search | Fresh U.S. and Canadian searches without a login, with repost filtering. |
| GitHub listing repos | Simplify, New Grad, internship, off-season, Canada, and salary-aware lists covering bespoke ATSs and long-tail companies. |

Cross-source deduplication prefers direct apply links and remembers alerts for
90 days. Staffing-agency patterns are excluded before alert fanout.

## Notifications

Jobwatch uses a two-speed model:

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
python -m unittest -v                     # run the full test suite
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
Windows ZIP on pushes to `main`, pull requests and manual runs. The ZIP is
available as the `windows-package` artifact. Pushing a version tag such as
`v0.1.0` also publishes the ZIP as a public GitHub Release after all checks pass.
No notification secrets are needed for tests, builds or Windows releases.

`.github/workflows/jobwatch.yml` runs tests and configuration validation,
restores the portable state, polls repeatedly for roughly 25 minutes, and
chains a successor run when `ENABLE_JOB_ALERTS=true`. It is disabled by default.
`state.json` on the force-pushed `state` branch keeps
deduplication and alert queues durable across ephemeral runners.

Local SQLite stores richer searchable job metadata, run history, and the
application pipeline. Portable state deliberately excludes private pipeline
notes. Runtime dependencies are `requests` and `pypdf`; the dashboard uses
Python's standard-library HTTP server and plain HTML/CSS/JavaScript.
