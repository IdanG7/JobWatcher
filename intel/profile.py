"""Candidate profile: defaults, merging, validation and versioning.

The profile drives ranking only.  It is seeded from ``config.json``'s
``profile`` block and overridden by the private copy stored in the local
SQLite database by the dashboard (never exported to state.json).  Nothing
sensitive is required; GPA and work authorization are optional.
"""

from __future__ import annotations

import copy
import hashlib
import json

WORK_AUTH_VALUES = ("citizen", "permanent_resident", "authorized", "needs_sponsorship", "unknown")
STAGES = ("internship", "new_grad", "entry", "experienced", "senior")

DEFAULT_PROFILE: dict = {
    "name": "My search",
    "headline": "2027 finance recruiting · Toronto & New York",
    "graduation_year": 2027,
    "graduation_month": 5,
    "education": {"level": "undergraduate", "school": "", "program": "", "gpa": None},
    "target_roles": [
        "investment_banking",
        "private_markets.private_equity",
        "public_markets.asset_management",
        "public_markets.equity_research",
    ],
    "role_weights": {},
    "target_stages": ["internship", "new_grad"],
    "target_cycles": ["summer_2027", "new_grad_2027"],
    "target_locations": ["toronto", "new_york", "chicago", "boston"],
    "target_countries": ["CA", "US"],
    "open_to_remote": True,
    "target_company_types": ["canadian_bank", "bulge_bracket", "elite_boutique",
                             "pension_fund", "private_equity"],
    "work_authorization": {"CA": "authorized", "US": "unknown"},
    "languages": ["English"],
    "skills": ["financial_modeling", "valuation", "excel", "python", "bloomberg",
               "capital_iq", "accounting", "capital_markets", "statistics"],
    "alerts": {"urgent_fit": 90, "high_fit": 75, "digest_fit": 55},
}

# Keys from the pre-finance profile format; tolerated so old configs load.
LEGACY_KEYS = ("track_weights", "seniority_weights", "location_weights", "company_type_weights",
               "year_weights", "education_penalties", "_note")


def merge_profile(*layers: dict | None) -> dict:
    """Deep-merge profile layers (later wins) on top of DEFAULT_PROFILE."""
    result = copy.deepcopy(DEFAULT_PROFILE)
    for layer in layers:
        for key, value in (layer or {}).items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = copy.deepcopy(value)
    # Settings once saved the United Kingdom as GB; locations are tagged UK.
    if isinstance(result.get("target_countries"), list):
        result["target_countries"] = list(dict.fromkeys(
            "UK" if c == "GB" else c for c in result["target_countries"]))
    auth = result.get("work_authorization")
    if isinstance(auth, dict) and "GB" in auth:
        gb = auth.pop("GB")
        if auth.get("UK") in (None, "unknown"):
            auth["UK"] = gb
    return result


def validate_profile(profile: dict, kn=None) -> list[str]:
    """Return human-readable problems (empty list = valid)."""
    problems = []
    year = profile.get("graduation_year")
    if year is not None and (not isinstance(year, int) or not 2020 <= year <= 2040):
        problems.append("graduation_year must be a year between 2020 and 2040")
    month = profile.get("graduation_month")
    if month is not None and (not isinstance(month, int) or not 1 <= month <= 12):
        problems.append("graduation_month must be 1–12")
    for key in ("target_roles", "target_stages", "target_cycles", "target_locations",
                "target_countries", "target_company_types", "languages", "skills", "fields"):
        if not isinstance(profile.get(key, []), list):
            problems.append(f"{key} must be a list")
    bad_stages = set(profile.get("target_stages") or []) - set(STAGES)
    if bad_stages:
        problems.append(f"unknown target_stages: {', '.join(sorted(bad_stages))}")
    gpa = (profile.get("education") or {}).get("gpa")
    if gpa not in (None, "") and not (isinstance(gpa, (int, float)) and 0 <= float(gpa) <= 4.3):
        problems.append("education.gpa must be a number between 0 and 4.3")
    for country, value in (profile.get("work_authorization") or {}).items():
        if value not in WORK_AUTH_VALUES:
            problems.append(f"work_authorization.{country} must be one of {', '.join(WORK_AUTH_VALUES)}")
    if kn is not None:
        valid_roles = set(kn.categories) | {f"{n.parent}.{n.key}" for n in kn.subcategories.values()} | set(kn.families)
        unknown = [r for r in profile.get("target_roles") or [] if r not in valid_roles]
        if unknown:
            problems.append(f"unknown target_roles: {', '.join(unknown)}")
        unknown = [t for t in profile.get("target_company_types") or [] if t not in kn.company_types]
        if unknown:
            problems.append(f"unknown target_company_types: {', '.join(unknown)}")
        unknown = [c for c in profile.get("target_locations") or [] if c not in kn.city_by_key]
        if unknown:
            problems.append(f"unknown target_locations: {', '.join(unknown)}")
        unknown = [s for s in profile.get("skills") or [] if s not in kn.skill_by_key]
        if unknown:
            problems.append(f"unknown skills: {', '.join(unknown)}")
        # Fields (finance or a job family) only choose what Settings and filters show.
        unknown = [f for f in profile.get("fields") or [] if f != "finance" and f not in kn.families]
        if unknown:
            problems.append(f"unknown fields: {', '.join(unknown)}")
    return problems


def prune_profile(profile: dict, kn) -> dict:
    """The profile without choices the knowledge base no longer offers, so it validates again.

    0.3.0 offered Software and AI & Data specialties ('software.backend'), tech
    employer types and tech skills; a specialty target falls back to its family.
    """
    roles = set(kn.categories) | {f"{n.parent}.{n.key}" for n in kn.subcategories.values()} | set(kn.families)

    def role(key):
        return next((k for k in (key, key.split(".")[0]) if k in roles), None)

    out = dict(profile)
    if isinstance(profile.get("target_roles"), list):
        out["target_roles"] = list(dict.fromkeys(r for r in map(role, profile["target_roles"]) if r))
    if isinstance(profile.get("role_weights"), dict):
        weights: dict = {}
        for key, weight in profile["role_weights"].items():
            if r := role(key):
                weights[r] = max(weights.get(r, 0), weight)
        out["role_weights"] = weights
    if isinstance(profile.get("target_company_types"), list):
        out["target_company_types"] = [t for t in profile["target_company_types"] if t in kn.company_types]
    if isinstance(profile.get("skills"), list):
        out["skills"] = [s for s in profile["skills"] if s in kn.skill_by_key]
    return out


RULES_VERSION = 2      # raise when scoring or resume-match rules change, so installs rescore once


def profile_version(profile: dict, watched: list[str] | tuple[str, ...] = ()) -> str:
    """Stable hash of everything that affects fit scores."""
    payload = json.dumps({"p": profile, "w": sorted(watched), "r": RULES_VERSION}, sort_keys=True, default=str)
    return hashlib.sha1(payload.encode()).hexdigest()[:12]
