"""Skill extraction with synonym normalization."""

from __future__ import annotations

from .knowledge import Knowledge


def extract_skills(text: str, kn: Knowledge, limit: int = 24, tech: bool = False) -> list[dict]:
    """Return [{key, label, group, count}] ordered by group then frequency.

    Each canonical skill is counted once per distinct occurrence of any of
    its synonyms, so 'DCF' and 'discounted cash flow analysis' both feed DCF.
    Tech skills count only with ``tech``: finance postings and finance resumes
    are read with the finance vocabulary alone.
    """
    text = (text or "")[:40000]
    if not text:
        return []
    found = []
    order = list(kn.skill_groups)
    for skill in kn.skills:
        if not skill.pattern or (skill.tech and not tech):
            continue
        count = sum(1 for _ in skill.pattern.finditer(text))
        if count:
            found.append({"key": skill.key, "label": skill.label,
                          "group": skill.group, "count": count})
    found.sort(key=lambda s: (order.index(s["group"]) if s["group"] in order else 99,
                              -s["count"], s["label"]))
    return found[:limit]
