# Resume parsing and automatic opportunity filtering

The user wants resume-driven filtering, retaining selected career targets and
adding roles supported by experience. Resume optimization remains out of scope.

## Design

Settings accepts PDF/DOCX/TXT or pasted text, previews extracted facts and proposed
profile changes, and offers “Apply & enable matching”. That action replaces skills
with supported skills, updates education/graduation/languages, adds experience
categories to selected role targets, and proposes graduate/internship cycles.
Existing geography and work authorization remain preferences, never resume guesses.
Store structured parsed data locally, without the original document or contact data.

A separate per-posting match table caches decisions during the existing scoring
pass. Resume match requires a relevant role and stage, target geography, and no
explicit graduation/degree/GPA/language/authorization conflict. Unknown requirements
stay visible with review notes; “match” is not a guarantee of hiring eligibility.
An active saved resume makes matching the default on Opportunities. A visible chip
can show all roles, and saved queries/CSV exports use the same SQL criteria.

Fix demonstrated extraction/classification defects: literal C++ labels; composite
treasury titles; combined section headings; engineering roles at banks; explicit
month-year internship starts. Bump facts version so existing cached jobs rebuild.

## Implementation plan

- [x] Add failing parser, classifier, cycle and profile regression tests; fix extraction.
- [x] Add pure matching rules and tests for conflicts, unknowns, and skill provenance.
- [x] Migrate private resume/match tables; add parse/apply/toggle/delete endpoints,
  cache integration and SQL filtering; test persistence, validation and stale scores.
- [x] Add Settings upload/preview controls, Opportunities chip and drawer reasons;
  test UI behavior and validate the real PDF in a disposable database/browser.
- [x] Run Python/JS regression suites, review the integrated diff and document use.

Verified on 2026-10-10: 129 Python tests and 24 JavaScript tests pass. The supplied
PDF was checked locally, and upload, preview, apply, matching, and show-all behavior
were exercised in a disposable browser/database on desktop and mobile. A partial
snapshot of real postings was used to diagnose classification errors; the live
candidate profile was not changed. Independent review covered stale-worker races,
incomplete imports, authorization preservation, eligibility, and filter consistency.

## Constraints and review focus

No external model calls, resume text in logs, raw document storage, or personal data
in portable state. A 5 MB file limit and bounded decompression/text extraction apply.
Changing targets invalidates match scores; stale rows must not be shown as current.
Requests without an active resume gracefully show all roles, including saved links. Partial
or unreadable resumes do not erase the existing saved resume. Preserve ongoing
workspace changes and verify without changing the live candidate profile.
