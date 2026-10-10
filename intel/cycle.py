"""Recruiting-season intelligence: cycles, graduation windows, deadlines."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
_YEAR = r"(20[2-3]\d)"
SEASONS = {"summer": "Summer", "fall": "Fall", "autumn": "Fall", "winter": "Winter", "spring": "Spring"}

_SEASON_YEAR = re.compile(rf"\b(summer|fall|autumn|winter|spring)\b[^0-9\n]{{0,30}}?{_YEAR}\b", re.I)
_YEAR_SEASON = re.compile(rf"\b{_YEAR}\s*[-–/]?\s*(summer|fall|autumn|winter|spring)\b", re.I)
_OFF_CYCLE = re.compile(rf"\boff[\s-]?cycle\b(?:[^0-9\n]{{0,25}}{_YEAR})?|{_YEAR}[^0-9\n]{{0,25}}\boff[\s-]?cycle\b", re.I)
_YEAR_PROGRAM = re.compile(rf"\b{_YEAR}\b[^0-9\n]{{0,40}}?\b(summer analyst|summer associate|internship|intern|co[\s-]?op|analyst|associate|new grad|graduate|program(?:me)?|start)\b", re.I)
_PROGRAM_YEAR = re.compile(rf"\b(new[\s-]?grad(?:uate)?|graduate|full[\s-]?time|analyst program|class of|campus|university|start(?:ing)?(?: date)?)\b[^0-9\n]{{0,25}}?{_YEAR}\b", re.I)
_START_DATE = re.compile(rf"\b(start(?:ing)?|commenc(?:e|ing)|begin(?:ning|s)?)\b[^.\n]{{0,40}}?\b{_MONTH}\s+{_YEAR}\b", re.I)
_TITLE_MONTH_YEAR = re.compile(rf"\b{_MONTH}\s+{_YEAR}\b", re.I)

_GRAD_BETWEEN = re.compile(
    rf"graduat\w*[^.\n]{{0,60}}?\b(?:between|from)\s+(?:{_MONTH}\s+)?{_YEAR}\s+(?:and|to|-|–|through)\s+(?:{_MONTH}\s+)?{_YEAR}", re.I)
_GRAD_RANGE = re.compile(
    rf"(?:expected\s+)?graduation(?:\s+date)?\s*(?:of|in|between|:|-|is)?\s*(?:{_MONTH}\s+)?{_YEAR}\s*(?:and|to|-|–|through)\s*(?:{_MONTH}\s+)?{_YEAR}", re.I)
_GRAD_SINGLE = re.compile(
    rf"(?:graduat(?:e|ing|ion)(?:\s+date)?(?:\s+(?:in|by|of|date of|between))?|expected\s+to\s+graduate(?:\s+(?:in|by))?|class\s+of)\s*:?\s*(?:{_MONTH}\s+|(?:spring|summer|fall|winter)\s+)?{_YEAR}", re.I)
_PENULTIMATE = re.compile(r"\b(penultimate|pen-?ultimate|second[\s-]to[\s-]last|rising senior|junior year|third[\s-]year (student|undergraduate))\b", re.I)
_FINAL_YEAR = re.compile(r"\b(final[\s-]year|senior year|graduating (students?|seniors?)|recent graduates?)\b", re.I)

_DEADLINE_CUE = re.compile(
    r"(deadline|apply by|applications? (?:will )?(?:close|closes|closing|are due|is due|must be (?:received|submitted))|"
    r"closing date|closes on|no later than|submit (?:your |an )?applications? by|accept(?:ed|ing) (?:applications )?(?:until|through)|"
    r"posting (?:closes|end date|will close)|application window closes|due by|until)", re.I)
_DATE_PATTERNS = [
    (re.compile(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+{_YEAR}\b", re.I), "mdy"),
    (re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH},?\s+{_YEAR}\b", re.I), "dmy"),
    (re.compile(r"\b(20[2-3]\d)-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(20[2-3]\d)\b"), "us"),
    (re.compile(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?!,?\s*20)", re.I), "md"),
]
_ROLLING = re.compile(
    r"\b(rolling basis|on a rolling|rolling (admissions?|applications?|review|recruit(ing|ment))|reviewed as (they are )?received|"
    r"early applications? (is|are) (strongly )?(encouraged|recommended)|apply early|positions? (may|will) (be )?(fill|close) (early|before))\b", re.I)


def _month(text: str | None) -> int | None:
    if not text:
        return None
    return MONTHS.get(text.lower().rstrip(".")[:9]) or MONTHS.get(text.lower().rstrip(".")[:3])


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def detect_cycle(title: str, description: str = "", stage: str = "", posted_epoch: float | None = None) -> dict:
    """Return the recruiting cycle, e.g. {'cycle': 'summer_2027', ...} or {} when unknown."""
    title = title or ""
    description = (description or "")[:20000]
    # An explicit start month in the title beats inferred summer cycles and
    # conflicting season words inherited from a source's listing category.
    month_year = _TITLE_MONTH_YEAR.search(title)
    if stage == "internship" and month_year:
        month, year = _month(month_year.group(1)), int(month_year.group(2))
        season = "summer" if 5 <= month <= 7 else "fall" if 8 <= month <= 10 else "winter"
        return _cycle(season, year, "internship", 0.95)
    for text, base_conf in ((title, 0.95), (description, 0.7)):
        if not text:
            continue
        m = _OFF_CYCLE.search(text)
        if m:
            year = m.group(1) or m.group(2)
            if year:
                return _cycle("off_cycle", int(year), "internship", base_conf)
            if text is title:
                return {"cycle": "off_cycle", "season": "off_cycle", "year": None,
                        "kind": "internship", "label": "Off-Cycle", "confidence": 0.6,
                        "inferred": False, "internship_year": None}
        m = _SEASON_YEAR.search(text) or _YEAR_SEASON.search(text)
        if m:
            groups = [g for g in m.groups() if g]
            season = next(g for g in groups if not g.isdigit()).lower()
            year = int(next(g for g in groups if g.isdigit()))
            if text is not title and not _plausible_year(year):
                continue
            kind = "internship" if stage == "internship" or text is not title or re.search(
                r"intern|analyst|associate|co[\s-]?op|placement", title, re.I) else "full_time"
            if stage == "new_grad":
                kind = "full_time"
            return _cycle(SEASONS[season].lower(), year, kind, base_conf)
        if text is title:
            m = _YEAR_PROGRAM.search(text)
            if m:
                year, word = int(m.group(1)), m.group(2).lower()
                if word in ("summer analyst", "summer associate", "internship", "intern") or (
                        stage == "internship" and word not in ("new grad", "graduate", "start")):
                    season = "summer" if not re.search(r"co[\s-]?op", text, re.I) else "fall"
                    return _cycle(season, year, "internship", 0.85)
                return _cycle("new_grad", year, "full_time", 0.85)
            m = _PROGRAM_YEAR.search(text)
            if m:
                return _cycle("new_grad", int(m.group(2)), "full_time", 0.8)
    m = _START_DATE.search(description)
    if m:
        month, year = _month(m.group(2)), int(m.group(3))
        if stage == "internship" and month:
            season = "summer" if 4 <= month <= 7 else "fall" if 8 <= month <= 10 else "winter"
            return _cycle(season, year, "internship", 0.6)
        if stage in ("new_grad", "entry"):
            return _cycle("new_grad", year, "full_time", 0.6)

    # No explicit year: infer the most likely upcoming summer for internships.
    if stage == "internship" and posted_epoch:
        posted = datetime.fromtimestamp(posted_epoch, timezone.utc)
        year = posted.year + 1 if posted.month >= 7 else posted.year
        result = _cycle("summer", year, "internship", 0.35)
        result["inferred"] = True
        return result
    return {}


def _plausible_year(year: int) -> bool:
    """Descriptions mention history ('since Spring 2019'); only near-term years count."""
    this_year = datetime.now(timezone.utc).year
    return this_year - 1 <= year <= this_year + 3


def _cycle(season: str, year: int, kind: str, confidence: float) -> dict:
    if season == "new_grad":
        label = f"New Grad {year}"
    elif season == "off_cycle":
        label = f"Off-Cycle {year}"
    else:
        label = f"{season.title()} {year}"
    return {
        "cycle": f"{season}_{year}", "season": season, "year": year, "kind": kind,
        "label": label, "confidence": confidence, "inferred": False,
        "internship_year": year if kind == "internship" else None,
    }


def graduation_window(description: str, title: str = "", cycle: dict | None = None) -> dict:
    """Return {'start': 'YYYY-MM', 'end': 'YYYY-MM', 'years': [...], 'text': ...} or {}."""
    text = f"{title}\n{description or ''}"[:20000]
    for pattern in (_GRAD_BETWEEN, _GRAD_RANGE):
        m = pattern.search(text)
        if m:
            m1, y1, m2, y2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
            if y2 < y1 or y2 - y1 > 3:
                continue
            start = f"{y1}-{(_month(m1) or 1):02d}"
            end = f"{y2}-{(_month(m2) or 12):02d}"
            return {"start": start, "end": end, "years": sorted({y1, y2}),
                    "text": _snippet(text, m), "confidence": "high"}
    m = _GRAD_SINGLE.search(text)
    if m:
        month, year = _month(m.group(1)), int(m.group(2))
        start = f"{year}-{month:02d}" if month else f"{year}-01"
        end = f"{year}-{month:02d}" if month else f"{year}-12"
        return {"start": start, "end": end, "years": [year], "text": _snippet(text, m),
                "confidence": "high" if month else "medium"}
    m = _PENULTIMATE.search(text)
    if m and cycle and cycle.get("internship_year"):
        year = cycle["internship_year"] + 1
        return {"start": f"{year}-01", "end": f"{year}-12", "years": [year],
                "text": _snippet(text, m), "confidence": "medium", "relative": "penultimate year"}
    m = _FINAL_YEAR.search(text)
    if m and cycle and cycle.get("year") and cycle.get("kind") == "full_time":
        year = cycle["year"]
        return {"start": f"{year - 1}-09", "end": f"{year}-08", "years": [year - 1, year],
                "text": _snippet(text, m), "confidence": "low", "relative": "final year"}
    return {}


def extract_deadline(description: str, reference: datetime | None = None) -> dict:
    """Find an application deadline near a cue phrase.  Returns {} when unsure.

    Confidence: high = explicit date with year after a deadline cue; medium =
    month/day with the year inferred; low = date found only near a weak cue.
    """
    text = (description or "")[:30000]
    if not text:
        return {}
    reference = reference or datetime.now(timezone.utc)
    best = None
    for cue in _DEADLINE_CUE.finditer(text):
        window = text[cue.end(): cue.end() + 90]
        strong = cue.group(1).lower() not in ("until", "by")
        if re.search(r"\b(start|begin|commence|graduat|internship (runs|dates)|program (runs|dates))", window[:40], re.I):
            continue
        for pattern, kind in _DATE_PATTERNS:
            m = pattern.search(window)
            if not m or m.start() > 60:
                continue
            parsed = _parse_date(m, kind, reference)
            if not parsed:
                continue
            when, has_year = parsed
            confidence = ("high" if has_year else "medium") if strong else "low"
            candidate = {"date": when.isoformat(), "confidence": confidence,
                         "text": text[max(0, cue.start() - 20): cue.end() + m.end() + 5].strip()}
            rank = {"high": 3, "medium": 2, "low": 1}[confidence]
            if best is None or rank > best[0]:
                best = (rank, candidate)
            break
    return best[1] if best else {}


def _parse_date(m: re.Match, kind: str, reference: datetime) -> tuple[date, bool] | None:
    if kind == "mdy":
        d = _safe_date(int(m.group(3)), _month(m.group(1)) or 0, int(m.group(2)))
        return (d, True) if d else None
    if kind == "dmy":
        d = _safe_date(int(m.group(3)), _month(m.group(2)) or 0, int(m.group(1)))
        return (d, True) if d else None
    if kind == "iso":
        d = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        return (d, True) if d else None
    if kind == "us":
        d = _safe_date(int(m.group(3)), int(m.group(1)), int(m.group(2)))
        return (d, True) if d else None
    if kind == "md":
        month, day = _month(m.group(1)), int(m.group(2))
        if not month:
            return None
        ref = reference.date()
        d = _safe_date(ref.year, month, day)
        if d and d < ref - timedelta(days=30):
            d = _safe_date(ref.year + 1, month, day)
        return (d, False) if d else None
    return None


def is_rolling(description: str) -> bool:
    return bool(_ROLLING.search(description or ""))


def _snippet(text: str, m: re.Match, pad: int = 30) -> str:
    return re.sub(r"\s+", " ", text[max(0, m.start() - pad): m.end() + pad]).strip()


def window_status(deadline: str | None, rolling: bool, job_status: str, today: date) -> str:
    """open / closing_soon / closed / rolling / unknown."""
    if job_status == "closed":
        return "closed"
    if deadline:
        try:
            due = date.fromisoformat(deadline)
        except ValueError:
            due = None
        if due:
            if due < today:
                return "closed"
            if (due - today).days <= 7:
                return "closing_soon"
            return "open"
    if rolling:
        return "rolling"
    return "unknown"
