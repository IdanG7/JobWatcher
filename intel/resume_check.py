"""A resume check by rule: weaknesses that can be seen without a model, each quoting the lines it is about.

It reads the resume's text as kept for cover letters (bullets written as "•", a bullet's wrapped lines on the
lines after it). Nothing here judges content or gives a score: each finding says what was seen and what to do.
"""
from __future__ import annotations

import re
from collections import Counter

MAX_LINES = 8                       # lines quoted per finding
LONG_BULLET = 35                    # words
ONE_PAGE, TWO_PAGES = 650, 1300     # words, when there is no file to count pages in

_MARK = re.compile(r"^\s*[•▪■●◦○‣⁃∙·*–-]\s+(?=\S)")
_HEADING = re.compile(r"^[A-Z][A-Za-z &/,-]{2,38}:?$")
_MONTH = r"(?:jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)"
_FULL = r"(?:january|february|march|april|june|july|august|september|october|november|december)"
_DATE_STYLES = (
    ("Jan 2026", re.compile(rf"\b{_MONTH}\.?\s+\d{{4}}\b", re.I)),
    ("January 2026", re.compile(rf"\b{_FULL}\s+\d{{4}}\b", re.I)),
    ("01/2026", re.compile(r"\b\d{1,2}/\d{4}\b")),
    ("2026-01", re.compile(r"\b\d{4}-(?:0[1-9]|1[0-2])\b")),       # not "2019-21", a span of years
)
_RANGE = re.compile(r"\S+\s+\d{4}\s*[-–—]+\s*(?:\S+\s+\d{4}|present|current|now)|\d{1,2}/\d{4}\s*[-–—]+\s*(?:\d{1,2}/\d{4}|present|current|now)"
                    r"|\d{4}-\d{2}\s*[-–—]+\s*(?:\d{4}-\d{2}|present|current|now)", re.I)
_LABEL = re.compile(r"^\s*[A-Z][\w &/]{1,30}:\s")          # "Languages: English, French"
_WEAK = re.compile(r"^(?:responsible for|helped|assisted|worked on|worked with|duties included|tasked with|"
                   r"participated in|involved in|in charge of)\b", re.I)
_NUMBER = re.compile(r"\d")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?\d[\s().-]*){10,}")
_SECTIONS = (("Education", re.compile(r"^\s*(?:education|academic|certifications? (?:&|and) education)", re.I)),
             ("Skills", re.compile(r"^\s*(?:(?:technical |core |key )?skills|competenc|technologies|technical proficienc|tools)", re.I)))


def weak(line: str) -> bool:
    """Whether a bullet opens with a duty ("responsible for", "helped") rather than what was done."""
    return bool(_WEAK.match(line.strip()))


def _is_heading(line: str) -> bool:
    return bool(_HEADING.match(line.strip())) and len(line.split()) <= 5 and not line.rstrip().endswith(".")


def _titled(line: str) -> bool:
    """A heading or a name on its own line: short, every word capitalised ("Technical Skills", "EXPERIENCE").
    "Operations teams", the tail of a wrapped bullet, is not."""
    words = [w for w in line.split() if w.lower() not in ("and", "of", "&", "the")]
    return _is_heading(line) and all(w[0].isupper() for w in words)


def bullets(text: str) -> list[str]:
    """The resume's bullets, each whole: a marked line and the wrapped lines after it. A resume with no bullet
    marks has its sentences under a job read as bullets."""
    lines = [line.rstrip() for line in text.splitlines()]
    full = 0.6 * max((len(line) for line in lines), default=0)      # a line this long may have wrapped
    found: list[str] = []
    open_bullet, wrapped = False, False
    for line in lines:
        rest = _MARK.sub("", line).strip()
        if _MARK.match(line) and len(rest.split()) >= 2:
            found.append(rest)
            open_bullet = True
        # The lines after a bullet are its own while it has no full stop and they read as running on: they start
        # in lower case, or the line before reached the margin. A job title or "Languages: …" after a short
        # bullet is not glued on.
        elif open_bullet and line.strip() and not found[-1].endswith((".", "!", "?")) and "|" not in line \
                and not _RANGE.search(line) and (line.strip()[0].islower() or (wrapped and not _titled(line)
                                                                              and not _LABEL.match(line))):
            found[-1] += " " + line.strip()
        else:
            open_bullet = False
        wrapped = len(line) >= full
    if found:
        return found
    return [line.strip() for line in lines
            if len(line.split()) >= 5 and line.strip().endswith(".") and "|" not in line and "@" not in line
            and not _RANGE.search(line)]


def _finding(key: str, title: str, detail: str, lines: list[str] | None = None) -> dict:
    return {"key": key, "title": title, "detail": detail, "lines": (lines or [])[:MAX_LINES]}


def check(text: str, experienced: bool = False, pages: int | None = None) -> list[dict]:
    """Findings [{'key', 'title', 'detail', 'lines'}], wording first, then length, dates and what is missing.
    ``experienced`` is the resume reader's career stage; ``pages`` the kept PDF's page count, when there is one."""
    items = bullets(text)
    found = []

    duties = [b for b in items if weak(b)]
    if duties:
        found.append(_finding("weak_openers", f"{len(duties)} bullet{'s' if len(duties) != 1 else ''} open with what you were given, not what you did",
                              "“Responsible for” and “helped with” name a duty. Start with the verb for what you did: built, cut, ran, wrote.", duties))

    plain = [b for b in items if not _NUMBER.search(b)]
    if len(items) >= 2 and len(plain) * 2 > len(items):
        found.append(_finding("no_numbers", f"{len(plain)} of {len(items)} bullets have no number",
                              "A number (how many, how much, how often, how fast) makes a result easier to believe. "
                              "Add one where you have it; leave the line alone where you don’t.", plain))

    firsts = Counter(b.split()[0].strip(",.:;").capitalize() for b in items if b.split())
    for word, count in firsts.most_common(1):
        if count >= 3:
            found.append(_finding("repeated_openers", f"“{word}” opens {count} bullets",
                                  "The same verb again and again reads as one job done many times. Vary it where the work differed.",
                                  [b for b in items if b.split()[0].strip(",.:;").capitalize() == word]))

    long = [b for b in items if len(b.split()) > LONG_BULLET]
    if long:
        found.append(_finding("long_bullets", f"{len(long)} bullet{'s' if len(long) != 1 else ''} run past {LONG_BULLET} words",
                              "A long bullet hides its result. Split it, or cut to the action and what came of it.", long))

    words = len(text.split())
    limit_pages, limit_words = (2, TWO_PAGES) if experienced else (1, ONE_PAGE)
    stage = "an experienced candidate" if experienced else "a student or recent graduate"
    if pages is not None and pages > limit_pages:
        found.append(_finding("length", f"{pages} pages; {limit_pages} is usual for {stage}",
                              "Recruiters read the first page closely and skim the rest. Cut the oldest and least relevant lines first."))
    elif pages is None and words > limit_words:
        found.append(_finding("length", f"About {words} words; likely more than {limit_pages} page{'s' if limit_pages > 1 else ''}",
                              f"{limit_pages} page{'s are' if limit_pages > 1 else ' is'} usual for {stage}. Cut the oldest and least relevant lines first."))

    used = {}
    for line in text.splitlines():
        for name, pattern in _DATE_STYLES:
            if pattern.search(line) and name not in used:
                used[name] = (_RANGE.search(line) or pattern.search(line)).group(0).strip()
    if len(used) > 1:
        found.append(_finding("date_styles", f"Dates are written {len(used)} ways",
                              "Pick one form (“May 2026 – Aug 2026”) and use it everywhere; mixed forms are harder to scan and to parse.",
                              list(used.values())))

    missing = [name for name, pattern in (("email address", _EMAIL), ("phone number", _PHONE)) if not pattern.search(text)]
    if missing:
        found.append(_finding("missing_contact", f"No {' or '.join(missing)} was read",
                              "If it is on your resume, it may sit in a page header, a text box or an image, where "
                              "application systems often can’t read it either. Put it in the body, at the top."))

    absent = [name for name, pattern in _SECTIONS if not any(pattern.match(line) and len(line) < 50 for line in text.splitlines())]
    if absent:
        found.append(_finding("missing_sections", f"No {' or '.join(absent)} heading was found",
                              "Application systems look for standard headings. Name the section plainly: “Education”, “Skills”."))
    return found
