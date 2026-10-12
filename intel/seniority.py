"""Finance-aware career-stage detection.

Finance titles differ from software titles: "Analyst" is usually the entry
level, "Summer Analyst" is an internship, and "Associate" is post-undergrad
in some areas but post-MBA / post-banking in investment banking, private
equity and S&T.  ``stage`` keeps the legacy vocabulary (internship /
new_grad / entry / experienced / senior) so existing filters keep working;
``level`` carries the finance title.
"""

from __future__ import annotations

import re

R = lambda p: re.compile(p, re.I)  # noqa: E731

# (level, stage, label, pattern) — first match wins, order matters.
TITLE_RULES = [
    ("spring_week", "internship", "Spring Week / Insight", R(r"\b(spring (week|insight)|insight (day|week|program(me)?)|discovery (day|program(me)?)|early insights?|sophomore (program|summit)|freshman (program|summit)|first ?year (insight|program))\b")),
    ("summer_associate", "internship", "Summer Associate", R(r"\bsummer associates?\b|\bsummer 20\d\d,?\s+associates?\b|\bmba (summer )?intern(ship)?\b|\bassociate intern(ship)?\b")),
    ("summer_analyst", "internship", "Summer Analyst", R(r"\bsummer (analyst|internship analyst)s?\b|\bsummer 20\d\d,?\s+analysts?\b|\bsummer(?:\s+(?!analyst)[\w&]+){1,3}\s+analysts?\b|\bsummer (investment banking|markets|research|sales (and|&) trading) analyst\b")),
    ("off_cycle", "internship", "Off-Cycle Intern", R(r"\boff[\s-]?cycle\b")),
    ("co_op", "internship", "Co-op", R(r"\bco[\s-]?op\b|\bwork term\b|\bwork[\s-]integrated learning\b")),
    ("intern", "internship", "Intern", R(r"\bintern(ship|s)?\b|\bplacement (year|student)\b|\bindustrial placement\b|\bstudent (analyst|associate|program)\b|^\s*(university |college )?students?\s*[,:|–—-]|[,(|–—-]\s*students?\s*\)?\s*$|\bapprentice(ship)?\b")),
    ("rotational", "new_grad", "Rotational Analyst", R(r"\brotation(al)? (analyst|program(me)?|associate|development program)\b|\bleadership development program\b|\bdevelopment program(me)?\b|\b(management )?trainee\b")),
    ("graduate_analyst", "new_grad", "Graduate Analyst", R(r"\b(graduate|grad|campus|university|new[\s-]?grad|entry[\s-]?level|early[\s-]?career|first[\s-]?year|full[\s-]?time) analyst\b|\banalyst (program(me)?|class|development program)\b|\bgraduate program(me)?\b")),
    ("new_grad", "new_grad", "New Grad", R(r"\bnew[\s-]?grad(uate)?s?\b|\bcampus (hire|recruit)(?!er)\b|\buniversity (grad(uate)?|hire|recruit)(?!er)\b|\bearly[\s-]?career\b|\bentry[\s-]?level\b|\bclass of 20\d\d\b|\bgraduate\b|\bjunior\b")),
    ("managing_director", "senior", "Managing Director", R(r"\bmanaging director\b|\b(md)\b|\b(managing|general|equity|operating) partner\b|\bhead of\b|\bchief\b|\bc[efio]o\b")),
    ("executive_director", "senior", "Executive Director", R(r"\bexecutive director\b|\b(senior )?director\b")),
    ("vp", "senior", "Vice President", R(r"\b(senior )?vice[\s-]president\b|\b(s)?vp\b|\bprincipal\b")),
    ("avp", "experienced", "Assistant Vice President", R(r"\bassistant vice[\s-]president\b|\bavp\b")),
    ("senior_associate", "experienced", "Senior Associate", R(r"\bsenior associate\b|\bsr\.? associate\b")),
    ("senior_analyst", "experienced", "Senior Analyst", R(r"\bsenior analyst\b|\bsr\.? analyst\b|\banalyst (ii|iii|iv|2|3)\b|\blead analyst\b")),
    ("senior_ic", "senior", "Senior", R(r"\b(senior|sr\.?|staff|lead|distinguished)\b|\b(manager|head)\b|\b(iii|iv)\b")),
    ("associate", "entry", "Associate", R(r"\bassociate\b")),
    ("analyst", "entry", "Analyst", R(r"\banalyst\b")),
    ("mid_ic", "experienced", "Experienced", R(r"\b(ii|2)\b(?!\d)")),
]

# Senior words that name the team, not the role: "Analyst, Office of the CFO".
_TEAM_NAME = re.compile(
    r"\b(?:office of(?: the)?|reporting to(?: the)?|supporting(?: the)?|to the)\s+"
    r"(?:chief\s+\w+(?:\s+\w+)?\s+officer|c[efior]o|head of [\w&\s]+?|managing director)(?=$|[,|()–—-])|"
    r"\bchief \w+ office\b|\bhead office\b|\bheadquarters\b", re.I)
_YEAR_IN_TITLE = re.compile(r"\b20(2[5-9]|3[0-2])\b")
_YEARS_EXP = re.compile(
    r"(\d{1,2})\s*(?:\+|-\s*\d{1,2}|to\s+\d{1,2})?\s*(?:\+\s*)?years?(?:'|’)?\s+(?:of\s+)?(?:relevant\s+|professional\s+|full[\s-]time\s+|industry\s+|post[\s-](?:mba|graduate)\s+|work(?:ing)?\s+|investment banking\s+|private equity\s+)*(?:experience|exp\b)",
    re.I)
_POST_MBA = re.compile(r"\b(mba (required|graduates?|candidates?|students?)|post[\s-]mba|completed (an|your) mba|pursuing (an|your) mba)\b", re.I)


def years_required(description: str) -> int | None:
    """Smallest 'N+ years of experience' requirement, ignoring 0-1 year phrasing."""
    values = [int(m.group(1)) for m in _YEARS_EXP.finditer(description or "")]
    values = [v for v in values if v <= 25]
    return min(values) if values else None


def detect_seniority(title: str, description: str = "", associate_stage: str = "entry",
                     category: str | None = None) -> dict:
    """Return {stage, level, level_label, confidence, notes, years_required, post_mba}."""
    title = _TEAM_NAME.sub(" ", title or "")
    notes: list[str] = []
    level, stage, label = None, None, None
    for lvl, stg, lbl, pattern in TITLE_RULES:
        if pattern.search(title):
            level, stage, label = lvl, stg, lbl
            break

    confidence = 0.85 if level else 0.4
    post_mba = bool(_POST_MBA.search(description or ""))

    if level == "associate":
        # Associate is post-MBA / post-banking in IB, PE and S&T; entry elsewhere.
        if associate_stage == "experienced" or post_mba:
            stage = "experienced"
            notes.append("Associate is a post-MBA / post-analyst level in this area")
            confidence = 0.7
        else:
            notes.append("Associate is typically an entry-level title in this area")
            confidence = 0.65
    if level == "summer_associate":
        post_mba = True
        notes.append("Summer Associate programs usually target MBA students")
    if level == "analyst":
        notes.append("Analyst is the entry level in finance")

    years = years_required(description)
    if not level and _YEAR_IN_TITLE.search(title):
        # '2027 Investment Banking Program' — a dated start is a campus hire
        level, stage, label, confidence = "new_grad", "new_grad", "New Grad", 0.6
        notes.append("dated program in title")
    if not level:
        if years is not None and years >= 5:
            stage, label = "senior", "Senior"
        elif years is not None and years >= 2:
            stage, label = "experienced", "Experienced"
        else:
            stage, label = "experienced", "Unspecified"
        level = "unspecified"
        if years is not None:
            notes.append(f"{years}+ years of experience required")
            confidence = 0.6
    elif stage in ("entry", "new_grad") and years is not None and years >= 3:
        stage = "experienced"
        notes.append(f"{years}+ years of experience required despite an entry-level title")
        confidence = 0.6

    return {
        "stage": stage, "level": level, "level_label": label,
        "confidence": confidence, "notes": notes,
        "years_required": years, "post_mba": post_mba,
    }


def legacy_stage(title: str) -> str:
    """Title-only stage, used by the legacy ``job_intelligence.seniority``."""
    return detect_seniority(title)["stage"]
