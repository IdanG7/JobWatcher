"""Working hours a posting states: employment type, shifts and on-call (plans/healthcare-board.md, D15).

Read on every board from the title, and from the description only where it states them ('Employment type:
Casual', 'This is a temporary full-time position', '12-hour rotating shifts'), never from passing words
('business casual', 'full-time students', 'a full-time offer after graduation'). Facts only: they cost fit
only through the profile's hours preference, in scoring.py.
"""

from __future__ import annotations

import re

R = lambda p: re.compile(p, re.I)  # noqa: E731

EMPLOYMENT = ("full_time", "part_time", "casual", "per_diem", "temporary")
EMPLOYMENT_LABELS = {"full_time": "Full-time", "part_time": "Part-time", "casual": "Casual",
                     "per_diem": "Per diem / PRN", "temporary": "Temporary or contract"}
SHIFTS = ("day", "evening", "night", "weekend", "rotating", "twelve_hour")

# Employment-type words, and where a title or a description states them.
_TYPE_WORDS = (
    ("full_time", R(r"\bfull[\s-]?time\b")),
    ("part_time", R(r"\bpart[\s-]?time\b")),
    ("casual", R(r"\bcasual\b")),
    ("per_diem", R(r"\bper[\s-]?diem\b|\bprn\b")),
    ("temporary", R(r"\b(?:temporary|temp|fixed[\s-]?term|seasonal|locum|contract)\b|(?<![\w-])term\b")),
)
_TITLE_TEMPORARY = R(r"\b(?:temporary|temp|fixed[\s-]?term|seasonal|locum)\b|\b(?:maternity|parental) leave\b|"
                     r"\(\s*(?:contract|term)\s*\)|[-–—|,]\s*(?:contract|term)\s*(?:$|[-–—|,(])")
_STATED_TYPE = R(
    r"\b(?:employment|job|position|work|contract|appointment)\s+(?:type|status)\s*[:\-–]\s*[^\n.;]{0,60}"
    r"|\bstatus\s*:\s*[^\n.;]{0,40}"
    r"|\bthis is an?\s+[^\n.;]{0,60}?\b(?:position|role|opportunity|job|assignment|contract)\b"
    r"|\b(?:casual|per[\s-]?diem|prn|part[\s-]?time|temporary|fixed[\s-]?term)\s+(?:position|role|opportunit(?:y|ies)|"
    r"employment|basis|status|vacanc(?:y|ies)|assignment|contract|line|pool|nurse|rn)\b")

_SHIFT_TITLE = (
    ("day", R(r"\bdays\b|\bday shifts?\b|\bdays?\s*/\s*nights?\b")),
    ("evening", R(r"\bevenings\b|\b(?:evening|swing) shifts?\b")),
    ("night", R(r"\bnights\b|\bovernights?\b|\b(?:night|graveyard) shifts?\b|\bdays?\s*/\s*nights?\b")),
    ("weekend", R(r"\bweekends\b|\bweekend shifts?\b")),
    ("rotating", R(r"\brotating\b|\brotation(?:al)? shifts?\b")),
    ("twelve_hour", R(r"\b12[\s-]?(?:hour|hr)s?\b")),
)
_SHIFT_DESCRIPTION = (
    ("day", R(r"\bday\s+shifts?\b|\bdays\s*/\s*nights\b|\bnights\s*/\s*days\b")),
    ("evening", R(r"\b(?:evening|swing)\s+shifts?\b")),
    ("night", R(r"\b(?:night|overnight|graveyard)\s+shifts?\b|\bdays\s*/\s*nights\b|\bnights\s*/\s*days\b")),
    ("weekend", R(r"\bweekend\s+shifts?\b|\bevery\s+(?:other|second|third)\s+weekend\b|"
                  r"\bweekends?\s+(?:(?:and|&)\s+holidays?\s+)?(?:are\s+|is\s+)?(?:required|rotation)\b")),
    ("rotating", R(r"\brotating\s+(?:shifts?|schedule|days|nights|weekends)\b|\bshift\s+rotation\b")),
    ("twelve_hour", R(r"\b12[\s-]?(?:hour|hr)s?\s+(?:(?:day|night|rotating)\s+)?shifts?\b")),
)
_ON_CALL_TITLE = R(r"\bon[\s-]?call\b")
_ON_CALL = R(r"\bon[\s-]?call\s+(?:position|basis|status|shifts?|schedule|rotation|duties|duty|availability|"
             r"responsibilit\w+|requirements?|coverage|hours|employee)\b|"
             r"\b(?:be|being|available|participate in|take|taking|share|sharing|provide|providing)\s+"
             r"(?:an?\s+|the\s+)?on[\s-]?call\b|\bon[\s-]?call\s+as\s+(?:needed|required)\b")


def extract_hours(title: str, description: str = "") -> dict:
    """{'employment': [...], 'shifts': [...], 'on_call': True}, each only when stated."""
    title = title or ""
    description = (description or "")[:20000]
    employment = set()
    for key, pattern in _TYPE_WORDS:
        if key == "temporary" and _TITLE_TEMPORARY.search(title) or key != "temporary" and pattern.search(title):
            employment.add(key)
    for stated in _STATED_TYPE.finditer(description):
        employment.update(key for key, pattern in _TYPE_WORDS if pattern.search(stated.group(0)))
    shifts = {key for key, pattern in _SHIFT_TITLE if pattern.search(title)}
    shifts.update(key for key, pattern in _SHIFT_DESCRIPTION if pattern.search(description))
    out = {}
    if employment:
        out["employment"] = [key for key in EMPLOYMENT if key in employment]
    if shifts:
        out["shifts"] = [key for key in SHIFTS if key in shifts]
    if _ON_CALL_TITLE.search(title) or _ON_CALL.search(description):
        out["on_call"] = True
    return out
