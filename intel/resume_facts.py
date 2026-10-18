"""What a resume says is true today: which roles have ended, which exams are passed.

A cover letter takes the candidate's story and voice from their past letter, and the status of what it says from
these facts: a letter written in June says "I am currently interning at EY" about a role that ended in August.
Resumes write dates every way ("May 2025 – Aug 2025", "05/2024 – 08/2024", "Summer 2025", "2023 – 2025",
"2025-05 – 2025-08") and lay roles out every way, so the local model copies each role and credential out as written
(cover_letter.read_facts); code keeps only values the resume contains and works out from the dates, against today,
which roles have ended.
"""
from __future__ import annotations

import re
from datetime import date

from . import letterhead

PROMPT = """You read a resume and copy out its roles and credentials.
- Copy every value exactly as the resume writes it; never reword, complete or guess. Use "" for what the resume doesn't state.
- roles: every job, internship, co-op, research, club or campus position, with its employer or organization, its title, and its dates exactly as written ("May 2025 – Aug 2025", "Summer 2025", "2023 – 2025", "Sep 2025 - Present").
- credentials: every exam, licence, certification or designation, one entry per level ("CFA Level II Candidate (Level I passed)" is two), with its status: "passed" for passed, completed, earned or held; "in progress" for candidate, pursuing, enrolled or studying; "planned" for scheduled, registered or expected."""
STATUSES = ("passed", "in progress", "planned")
SCHEMA = {"type": "object", "required": ["roles", "credentials"], "properties": {
    "roles": {"type": "array", "items": {"type": "object", "required": ["employer", "title", "dates"], "properties": {
        "employer": {"type": "string"}, "title": {"type": "string"}, "dates": {"type": "string"}}}},
    "credentials": {"type": "array", "items": {"type": "object", "required": ["name", "status"], "properties": {
        "name": {"type": "string"}, "status": {"type": "string", "enum": list(STATUSES)}}}}}}
MAX_VALUE = 120
# A resume's section headings, which the model sometimes gives as a credential ("Languages: French, English").
_HEADINGS = frozenset("""languages language skills skill certifications certification certificates certificate licences
licenses licence license designations designation professional technical interests awards honours honors education
experience activities and other""".split())

_MONTHS = {m: n for n, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split(), 1)}
_SEASONS = {"winter": (1, 4), "spring": (3, 6), "summer": (5, 8), "fall": (9, 12), "autumn": (9, 12)}
_ONGOING = re.compile(r"\b(?:present|current|now|today|ongoing)\b", re.I)
# Between the two ends: a dash (not the one inside "2025-05"), or "to", "until", "through".
_SPLIT = re.compile(r"\s*(?:[–—]+|(?<!\d)-+|-+(?!\d)|(?<=\d{4})-(?=\d{4}\b)|\bto\b|\buntil\b|\bthrough\b)\s*", re.I)
_POINT = re.compile(r"(?:(?P<month>jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?|"
                    r"(?P<season>winter|spring|summer|fall|autumn))?\s*(?P<year>(?:19|20)\d\d)?", re.I)
_NUMERIC = re.compile(r"(\d{1,2})[/.](\d{4})|(\d{4})[-/.](\d{1,2})")


def _point(text: str, last: bool) -> tuple[int | None, int] | None:
    """(year, month) for one end of a range: 'Aug 2025', '08/2025', '2025-08', 'Summer 2025' or '2025'; the last
    month of a season or year when ``last``. (None, month) when only the month is written ('Jan' in 'Jan–Apr 2026')."""
    text = text.strip(" ().,")
    numeric = _NUMERIC.fullmatch(text)
    if numeric:
        return (int(numeric[2]), int(numeric[1])) if numeric[1] else (int(numeric[3]), int(numeric[4]))
    m = _POINT.fullmatch(text)
    if not m or not (m["month"] or m["season"] or m["year"]):
        return None
    year = int(m["year"]) if m["year"] else None
    if m["month"]:
        return year, _MONTHS[m["month"][:3].lower()]
    if m["season"]:
        return year, _SEASONS[m["season"].lower()][1 if last else 0]
    return year, 12 if last else 1


def role_state(dates: str, today: date) -> str:
    """'ended', 'ongoing', or '' when the dates don't say: '2022 – 2026' in 2026 could end any month."""
    if _ONGOING.search(dates):
        return "ongoing"
    ends = [end for end in _SPLIT.split(dates.strip()) if end and end.strip()]
    last = _point(ends[-1], last=True) if ends else None
    if not last:
        return ""
    year = last[0] or next((p[0] for p in (_point(end, True) for end in ends) if p and p[0]), None)
    if not year or (year == today.year and not re.search(r"[a-z]|\d[/.-]\d", ends[-1], re.I)):
        return ""
    return "ended" if (year, last[1]) < (today.year, today.month) else "ongoing"


def checked(answer, resume_text: str) -> dict:
    """{'roles': [{'employer', 'title', 'dates'}], 'credentials': [{'name', 'status'}]} from the model's answer,
    keeping only values whose words are all in the resume (the model completing or inventing one drops it)."""
    said = set(letterhead.words(resume_text))

    def clean(value) -> str:
        value = " ".join(str(value or "").split())[:MAX_VALUE]
        return value if value and set(letterhead.words(value)) <= said else ""

    answer = answer if isinstance(answer, dict) else {}
    roles, credentials = [], []
    for item in answer.get("roles") if isinstance(answer.get("roles"), list) else []:
        role = {key: clean(item.get(key)) for key in ("employer", "title", "dates")} if isinstance(item, dict) else {}
        if role.get("employer") and role.get("dates"):
            roles.append(role)
    for item in answer.get("credentials") if isinstance(answer.get("credentials"), list) else []:
        name = clean(item.get("name")) if isinstance(item, dict) else ""
        if name and item.get("status") in STATUSES and not set(letterhead.words(name)) <= _HEADINGS:
            credentials.append({"name": name, "status": item["status"]})
    return {"roles": roles, "credentials": credentials}


def today_lines(facts: dict, today: date) -> list[str]:
    """The facts as the prompts give them, ended roles first: what a past letter most often gets wrong."""
    def role(r: dict) -> str:
        return ", ".join(filter(None, [r["employer"], r["title"]])) + f" ({r['dates']})"
    states = {"ended": [], "ongoing": []}
    for r in facts.get("roles", []):
        states.get(role_state(r["dates"], today), []).append(role(r))
    by_status = {status: [c["name"] for c in facts.get("credentials", []) if c["status"] == status] for status in STATUSES}
    lines = [("Roles that have ended (write about them in the past tense)", states["ended"]),
             ("Current roles", states["ongoing"]),
             ("Passed (say passed, never candidate)", by_status["passed"]),
             ("In progress, not passed yet", by_status["in progress"]),
             ("Planned, not taken yet (never say passed)", by_status["planned"])]
    return [f"- {label}: " + "; ".join(items) for label, items in lines if items]


# Words in many employers' and credentials' names, which don't pick one out: "Bank" isn't National Bank.
_GENERIC = frozenset("""the of and for at in on group inc ltd llc llp corp co company canada canadian bank capital
market markets financial finance investment investments management asset assets global international securities
services partners holdings level part institute exam course certificate certification program programme candidate
designation university school society club""".split())


def _names(text: str) -> set[str]:
    """Capitalised words that pick a name out: 'EY', 'Oxford', 'OMERS', 'CFA', 'Bloomberg'."""
    return {w for w in re.findall(r"\b[A-Z][\w&'’.-]*[\w&]", text) if w.lower() not in _GENERIC}


def in_full(name: str, sentence: str) -> bool:
    """Whether ``sentence`` has the whole of ``name``, without what's in brackets: "the Canadian Securities Course"
    for "Canadian Securities Course (CSC)", but not "CFA Level I" in "CFA Level II"."""
    whole = re.sub(r"\s*\([^)]*\)", "", name).strip()
    return bool(whole) and re.search(rf"(?<!\w){re.escape(whole)}(?!\w)", sentence, re.I) is not None


def mentions(name: str, sentence: str) -> bool:
    """Whether ``sentence`` is about the employer or credential ``name``: one of its distinctive names is in it
    ("at EY", "Oxford Properties"), or the whole name is."""
    return bool(_names(name) & _names(sentence)) or in_full(name, sentence)
