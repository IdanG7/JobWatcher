"""Profile-independent facts for one posting.

Facts are the expensive part (dozens of regexes over the description), so
they are computed once per content change and stored in ``job_intel``.
Scoring (cheap, profile- and time-dependent) reads them later.
"""

from __future__ import annotations

import hashlib
import re

from .companies import resolve_company
from .compensation import comp_from_description, parse_compensation
from .cycle import detect_cycle, extract_deadline, graduation_window, is_rolling
from .eligibility import extract_eligibility
from .knowledge import Knowledge
from .locations import geo_key, parse_location
from .seniority import detect_seniority
from .skills import extract_skills
from .taxonomy import classify

FACTS_VERSION = 8

_TITLE_NOISE = re.compile(
    r"\((?:m/f/d|f/m/d|m/w/d|h/f|all genders)\)|\breq(?:uisition)?\s*#?\s*\d+\b|\bjob\s*id\s*:?\s*\w+\b|[-–—|,]\s*(remote|hybrid|on[\s-]?site)\s*$",
    re.I)


def normalize_title(title: str) -> str:
    text = _TITLE_NOISE.sub(" ", (title or "").lower())
    text = re.sub(r"[^a-z0-9+&]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def input_hash(job: dict) -> str:
    """Hash of every field facts depend on (time is deliberately excluded)."""
    parts = [job.get(k) or "" for k in ("title", "location", "company", "salary", "department")]
    parts.append(hashlib.sha1((job.get("description") or "").encode("utf-8", "ignore")).hexdigest())
    parts.append(str(int(float(job.get("posted") or 0)) // 86400))  # day bucket: inferred cycles
    return hashlib.sha1("\x1f".join(map(str, parts)).encode("utf-8", "ignore")).hexdigest()[:16]


# Explicit work-arrangement statements in the posting body ("We support a
# hybrid model – with 3 days in the office per week").  Only stated policies
# count; a passing mention of "hybrid" in a product name does not.
_HYBRID_MODEL = re.compile(
    r"\bhybrid\s+(?:work(?:ing)?\s+)?(?:model|schedule|arrangement|environment|policy|work)\b"
    r"|\b\d\s+days?\s+(?:(?:a|per|each)\s+week\s+)?(?:in|at)\s+(?:the\s+|our\s+)?office\b"
    r"|\b(?:in|at)\s+(?:the\s+|our\s+)?office\s+\d\s+days?\s+(?:a|per|each)\s+week\b", re.I)
_OFFICE_DAYS = re.compile(r"\b(\d)\s+days?\s+(?:(?:a|per|each)\s+week\s+)?(?:in|at)\s+(?:the\s+|our\s+)?office\b"
                          r"|\boffice\s+(\d)\s+days?\b", re.I)


def _work_model(description: str) -> dict | None:
    m = _HYBRID_MODEL.search(description or "")
    if not m:
        return None
    start = max(description.rfind("\n", 0, m.start()), description.rfind(". ", 0, m.start())) + 1
    end_candidates = [i for i in (description.find("\n", m.end()), description.find(". ", m.end())) if i >= 0]
    sentence = re.sub(r"\s+", " ", description[start:min(end_candidates) + 1 if end_candidates else len(description)]).strip()
    days = _OFFICE_DAYS.search(sentence)
    office_days = int(next(g for g in days.groups() if g)) if days else None
    model = "onsite" if office_days and office_days >= 5 else "hybrid"
    return {"model": model, "office_days": office_days, "text": sentence[:240]}


def build_facts(job: dict, kn: Knowledge, board_cfg: dict | None = None, section: str = "") -> dict:
    board_cfg = board_cfg or {}
    title = job.get("title") or ""
    description = job.get("description") or ""
    department = job.get("department") or ""
    posted = job.get("posted")
    posted_epoch = float(posted) if posted not in (None, "") else None

    company = resolve_company(job.get("company") or "", kn, job.get("board") or "",
                              board_cfg, section)
    classification = classify(title, kn, description, department, company["type"])
    level = detect_seniority(title, description, classification["associate_stage"],
                             classification["category"])
    location = parse_location(job.get("location") or "", kn)
    work_model = _work_model(description)
    if work_model:
        location["hybrid"] = location["hybrid"] or work_model["model"] == "hybrid"
        location["work_model"] = work_model
    cycle = detect_cycle(title, description, level["stage"], posted_epoch)
    graduation = graduation_window(description, title, cycle)
    deadline = extract_deadline(description)
    eligibility = extract_eligibility(description, title)
    country = location["countries"][0] if location["countries"] else (company.get("country") or None)
    comp = parse_compensation(job.get("salary") or "", country)
    if not comp or comp.get("unparsed"):
        comp = comp_from_description(description, country) or comp
    skills = extract_skills(f"{title}\n{description}", kn)

    title_norm = normalize_title(title)
    cluster_key = "|".join([company["key"], title_norm, geo_key(location, job.get("location") or "", kn)])
    return {
        "v": FACTS_VERSION,
        "company": company,
        "classification": classification,
        "seniority": level,
        "location": location,
        "cycle": cycle,
        "graduation": graduation,
        "deadline": deadline,
        "rolling": is_rolling(description),
        "eligibility": eligibility,
        "compensation": comp or {},
        "skills": skills,
        "has_description": bool(description.strip()),
        "title_norm": title_norm,
        "cluster_key": cluster_key,
    }
