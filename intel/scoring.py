"""Fit Score 2.0 — explainable, capped subscores plus explicit penalties.

    Role fit 25 · Career stage 20 · Company 15 · Location 10
    Recruiting cycle 10 · Skills 10 · Freshness 10          = 100
    minus penalties (senior role, degree, graduation year, geography,
    sponsorship, language, GPA, role mismatch, off-target finance role,
    closed/stale)

Every point carries a human-readable ``detail`` so the UI can answer
"Why 91?" exactly.  Nothing here touches the network or the database.
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

from .cycle import window_status
from .hours import EMPLOYMENT, EMPLOYMENT_LABELS
from .knowledge import Knowledge
from .sources import profile_fields

FINANCE_TYPES = {"bulge_bracket", "elite_boutique", "middle_market_bank", "global_bank", "canadian_bank",
                 "commercial_bank", "private_equity", "venture_capital", "hedge_fund", "quant_firm",
                 "asset_manager", "pension_fund", "insurance", "fintech", "market_infrastructure"}
STEEP = [(3, 10), (6, 9), (12, 8), (24, 7), (48, 5), (72, 4), (168, 2), (336, 1)]
GENTLE = [(24, 10), (72, 9), (168, 7), (336, 5), (720, 3), (1440, 1)]
LEVEL_BADGES = {"summer_analyst": "SUMMER ANALYST", "summer_associate": "SUMMER ASSOCIATE",
                "off_cycle": "OFF-CYCLE", "spring_week": "SPRING WEEK", "co_op": "CO-OP",
                "intern": "INTERN", "graduate_analyst": "GRADUATE ANALYST", "rotational": "ROTATIONAL",
                "new_grad": "NEW GRAD", "analyst": "ANALYST"}
# A board's own levels (taxonomy.json stage_rules), on that board's postings only.
BOARD_LEVEL_BADGES = {"extern": "EXTERN", "summer_student": "SUMMER STUDENT", "student_worker": "STUDENT",
                      "new_grad_program": "NEW GRAD PROGRAM", "residency": "RESIDENCY", "fellowship": "FELLOWSHIP",
                      "postdoc": "POSTDOC"}


GRADUATION_SLACK_MONTHS = 3


def _months_outside(mine: str, start: str, end: str) -> int:
    """Months between a 'YYYY-MM' date and the nearest end of a window."""
    def index(text):
        year, month = text.split("-")
        return int(year) * 12 + int(month)
    value = index(mine)
    return max(index(start) - value, value - index(end), 0)


def _age_text(hours: float) -> str:
    if hours < 1:
        return "under an hour ago"
    if hours < 48:
        return f"{int(hours)} hour{'s' if int(hours) != 1 else ''} ago"
    return f"{int(hours // 24)} days ago"


def _target_match(targets: list[str], category: str, sub: str | None) -> tuple[str, str | None]:
    """'exact' (sub or whole category targeted), 'category' (sibling sub), or ''."""
    if not category:
        return "", None
    if category in targets:
        return "exact", category
    if sub and f"{category}.{sub}" in targets:
        return "exact", f"{category}.{sub}"
    for target in targets:
        if target.split(".")[0] == category:
            return "category", target
    return "", None


def _related_target(kn: Knowledge, targets: list[str], category: str, sub: str | None) -> str | None:
    """A targeted specialty the posting's specialty is related to (Full-Stack and Backend)."""
    if not sub:
        return None
    mine = kn.subcategories.get(f"{category}.{sub}")
    for target in targets:
        node = kn.subcategories.get(target)
        if node and mine and node.parent == category and (
                node.key in (mine.meta.get("related") or []) or sub in (node.meta.get("related") or [])):
            return target
    return None


def score_job(facts: dict, profile: dict, kn: Knowledge, dyn: dict | None = None,
              now: float | None = None) -> dict:
    """Score one job.  ``dyn`` carries mutable state: posted, first_seen,
    discovered, status, watched, deadline_override, recent_change."""
    dyn = dyn or {}
    now = now or time.time()
    today = datetime.fromtimestamp(now, timezone.utc).date()
    cls = facts["classification"]
    lvl = facts["seniority"]
    loc = facts["location"]
    cyc = facts.get("cycle") or {}
    elig = facts.get("eligibility") or {}
    company = facts["company"]
    targets = list(profile.get("target_roles") or [])
    # A specialty can count a finance group as itself: Quant Development matches Quant Developer.
    extra = [t for target in targets if target in kn.subcategories
             for t in kn.subcategories[target].meta.get("also_targets") or []]
    targets += [t for t in dict.fromkeys(extra) if t not in targets]
    subscores: list[dict] = []
    penalties: list[dict] = []
    reasons: list[str] = []

    def sub(key, label, points, maximum, detail):
        points = max(0, min(maximum, int(round(points))))
        subscores.append({"key": key, "label": label, "points": points, "max": maximum, "detail": detail})
        return points

    def penalty(key, label, points, detail):
        penalties.append({"key": key, "label": label, "points": -abs(int(points)), "detail": detail})

    # ---- role fit (25)
    role_label = cls["category_label"] + (f" — {cls['subcategory_label']}" if cls.get("subcategory_label") else "")
    match, which = _target_match(targets, cls["category"], cls.get("subcategory"))
    if cls.get("prior_only"):
        match, which = "", None
        pts, detail = 8, f"Division not named in the posting (the employer suggests {cls['category_label']})"
    elif match == "exact":
        pts, detail = 25, f"{role_label} matches your {kn.category_label(which.split('.')[0])} target"
        reasons.append(f"{kn.category_label(cls['category'])} target")
    elif match == "category":
        # A sibling of a target (Accounting next to an FP&A target) is related
        # work, not a target: partial credit only.  Specialties the taxonomy
        # marks as related (Full-Stack next to Backend) earn more.
        related = _related_target(kn, targets, cls["category"], cls.get("subcategory"))
        which = related or which
        pts = 14 if not cls.get("subcategory") or related else 9
        detail = (f"{role_label}: {'related to' if related else 'same division as'} your "
                  f"{kn.subcategory_label(*which.split('.')) or kn.category_label(which)} target")
    elif any(_target_match(targets, s, None)[0] for s in cls.get("secondary") or []):
        pts, detail = 14, f"{role_label}; secondary fit with a target ({', '.join(cls.get('secondary_labels') or [])})"
    elif cls.get("is_finance"):
        pts, detail = 5, f"{role_label} is outside your target roles"
    else:
        pts, detail = 0, f"{role_label} is not a target role family"
    weight = (profile.get("role_weights") or {}).get(which or "", 1)
    if isinstance(weight, (int, float)) and weight != 1 and pts:
        pts *= max(0.0, min(1.0, float(weight)))
        detail += f" (weighted ×{weight})"
    if pts and cls.get("confidence", 1) < 0.45:
        pts *= 0.8
        detail += " (low-confidence classification)"
    sub("role", "Role fit", pts, 25, detail)
    related = match or any(_target_match(targets, s, None)[0] for s in cls.get("secondary") or [])
    if targets and not related and cls.get("is_finance") and not cls.get("prior_only"):
        # Internship + bank + city + cycle alone add up to ~60 points; without
        # this, any generic co-op outranks the roles the candidate targets.
        confident = cls.get("confidence", 0) >= 0.5
        penalty("off_target", "Not a target role", 12 if confident else 6,
                f"{role_label} is not one of your target roles")
    elif targets and cls["category"] == "other":
        penalty("off_target", "Not a target role", 6, "Couldn't place this role in any of your targets")
    has_nonfinance_target = any(t.split(".")[0] in kn.families for t in targets)
    if not cls.get("is_finance") and targets and not has_nonfinance_target and cls["category"] != "other":
        penalty("role_mismatch", "Role mismatch", 10, f"{cls['category_label']} role; your targets are finance roles")

    # ---- career stage (20)
    stage_targets = set(profile.get("target_stages") or ["internship", "new_grad"])
    stage = lvl["stage"]
    level_label = lvl.get("level_label") or stage
    if lvl.get("level") == "spring_week":
        pts, detail = (8, "Spring week / insight program — usually for first- and second-year students")
    elif stage in stage_targets:
        pts, detail = 20, f"{level_label} — target career stage"
        reasons.append(f"{level_label} level")
    elif stage == "entry" and ({"new_grad", "entry"} & stage_targets):
        pts, detail = 16, f"{level_label} — entry level{'' if lvl.get('board_level') else ' in finance'}"
        reasons.append("Entry-level title")
    elif stage == "entry":
        pts, detail = 10, f"{level_label} — entry level, not a target stage"
    elif stage == "experienced":
        pts, detail = 4, f"{level_label} — experienced hire"
    else:
        pts, detail = 0, f"{level_label} — senior role"
    sub("stage", "Career stage", pts, 20, detail)
    early_targets = stage_targets <= {"internship", "new_grad", "entry"}
    if stage == "senior" and early_targets:
        penalty("senior", "Senior role", 25, f"{level_label} is well above your target stage")
    elif stage == "experienced" and early_targets:
        years = lvl.get("years_required")
        penalty("experienced", "Experience required", 8,
                f"{years}+ years of experience required" if years else f"{level_label} targets experienced hires")

    # ---- company preference (15)
    watched = bool(dyn.get("watched"))
    target_types = set(profile.get("target_company_types") or [])
    if watched:
        pts, detail = 15, f"{company['name']} is on your watchlist"
        reasons.append("Watchlist company")
    elif company["type"] in target_types:
        pts, detail = 12, f"{company['type_label']} — a target employer tier"
        reasons.append(f"{company['type_label']} priority")
    elif company["type"] in FINANCE_TYPES:
        pts, detail = 7, f"{company['type_label']} — recognized finance employer"
    elif tracks := [t for t in kn.type_tracks(company["type"]) if t != "finance"]:
        # Only a board on the employer's track makes it count: Finance-only profiles score tech
        # employers as before.
        boards = {kn.board_track.get(field) for field in profile_fields(profile, kn)}
        shared = next((t for t in tracks if t in boards), None)
        if shared:
            pts, detail = 7, f"{company['type_label']} — {kn.tracks[shared].employer_noun}"
        else:
            pts, detail = 4, f"{company['type_label']} — outside finance"
    elif company["type"] in ("consulting", "accounting_advisory"):
        pts, detail = 6, f"{company['type_label']}"
    else:
        pts, detail = 4, "Employer not in company intelligence"
    sub("company", "Company", pts, 15, detail)

    # ---- location (10)
    target_cities = set(profile.get("target_locations") or [])
    target_countries = set(profile.get("target_countries") or [])
    hit = next((c for c in loc["cities"] if c in target_cities), None)
    if hit:
        label = kn.city_by_key[hit]["label"]
        pts, detail = 10, f"{label} — preferred city"
        reasons.append(f"{label} preferred")
    elif loc["remote"] and profile.get("open_to_remote", True) and (
            not loc["countries"] or set(loc["countries"]) & target_countries):
        pts, detail = 7, "Remote within your target countries"
    elif set(loc["countries"]) & target_countries:
        country = next(c for c in loc["countries"] if c in target_countries)
        where = ", ".join(loc["city_labels"]) or kn.countries.get(country, {}).get("label", country)
        pts, detail = 6, f"{where} — target country, not a preferred city"
    elif loc["bucket"] == "unknown":
        pts, detail = 4, "Location not specified"
    else:
        where = ", ".join(loc["city_labels"]) or ", ".join(loc["countries"]) or "this location"
        pts, detail = 0, f"{where} is outside your target geography"
        if target_countries or target_cities:
            penalty("geography", "Outside target geography", 10, detail)
    sub("location", "Location", pts, 10, detail)

    # ---- recruiting cycle (10)
    target_cycles = set(profile.get("target_cycles") or [])
    grad = facts.get("graduation") or {}
    grad_ok = None
    if grad and profile.get("graduation_year"):
        mine = f"{profile['graduation_year']}-{int(profile.get('graduation_month') or 5):02d}"
        grad_ok = grad["start"] <= mine <= grad["end"]
    if cyc.get("cycle") and cyc["cycle"] in target_cycles:
        if cyc.get("inferred"):
            pts, detail = 6, f"Likely {cyc['label']} (inferred from the posting date)"
        else:
            pts, detail = 10, f"{cyc['label']} — target recruiting cycle"
            reasons.append(f"{cyc['label']} target cycle")
    elif cyc.get("cycle"):
        same_year = any(t.endswith(str(cyc.get("year"))) for t in target_cycles)
        if cyc.get("inferred"):
            pts, detail = 3, f"Possibly {cyc['label']} (inferred, not a target cycle)"
        elif same_year:
            pts, detail = 5, f"{cyc['label']} — right year, different season/track"
        else:
            pts, detail = 0, f"{cyc['label']} is not one of your target cycles"
            if target_cycles and cyc.get("year"):
                penalty("cycle_year", "Wrong recruiting year", 10, detail)
    elif stage in stage_targets:
        pts, detail = 5, "No recruiting cycle stated"
    else:
        pts, detail = 3, "No recruiting cycle stated"
    if grad_ok is True:
        pts = max(pts, 8)
        detail += f"; graduation window {grad['start']} → {grad['end']} includes you"
        reasons.append("Graduation window matches")
    sub("cycle", "Recruiting cycle", pts, 10, detail)
    if grad_ok is False:
        detail = (f"Requires graduation {grad['start']} → {grad['end']}; you graduate "
                  f"{profile['graduation_year']}-{int(profile.get('graduation_month') or 5):02d}")
        if _months_outside(mine, grad["start"], grad["end"]) <= GRADUATION_SLACK_MONTHS:
            # Off by a month or two is usually a term-end rounding, not a different class.
            penalty("graduation_near", "Graduation window (close)", 4, detail + " — close; check with the employer")
        else:
            penalty("graduation", "Graduation window", 12, detail)

    # ---- skills (10)
    job_skills = facts.get("skills") or []
    mine = set(profile.get("skills") or [])
    if not job_skills:
        pts = 5 if not facts.get("has_description") else 4
        detail = "No description available yet" if not facts.get("has_description") else "No finance skills detected"
    else:
        matched = [s for s in job_skills if s["key"] in mine]
        denom = min(4, len(job_skills))
        pts = 10 * min(1.0, len(matched) / denom) if denom else 0
        if matched:
            detail = (f"Matched {', '.join(s['label'] for s in matched[:4])} "
                      f"({len(matched)} of {len(job_skills)} detected)")
        else:
            detail = f"None of your skills among {len(job_skills)} detected"
    sub("skills", "Skills", pts, 10, detail)

    # ---- freshness (10)
    posted = dyn.get("posted")
    seen = dyn.get("first_seen") if dyn.get("discovered") else None
    ref = posted or seen
    age_hours = max(0.0, (now - ref) / 3600) if ref else None
    competitive = cls.get("competitive") and stage in ("internship", "new_grad", "entry")
    if age_hours is None:
        pts, detail = 3, "Posting date unknown"
    else:
        curve = STEEP if competitive else GENTLE
        pts = next((p for limit, p in curve if age_hours <= limit), 0)
        basis = "posted" if posted else "discovered"
        detail = f"{basis.title()} {_age_text(age_hours)}" + (
            " — competitive postings decay fast" if competitive else "")
        if age_hours < 24:
            reasons.append(f"{basis.title()} {_age_text(age_hours)}")
    sub("freshness", "Freshness", pts, 10, detail)

    # ---- eligibility penalties
    edu_level = ((profile.get("education") or {}).get("level") or "undergraduate").lower()
    degrees = set(elig.get("degree_required") or [])
    if lvl.get("post_mba"):
        degrees.add("mba")
    if edu_level == "undergraduate" and not (elig.get("degree_alternatives") and "undergraduate" in degrees):
        if "phd" in degrees:
            penalty("degree", "Graduate degree required", 20, "PhD candidates targeted")
        elif "mba" in degrees:
            penalty("degree", "Graduate degree required", 15, "MBA / post-MBA program")
        elif "masters" in degrees and "undergraduate" not in degrees:
            penalty("degree", "Graduate degree required", 10, "Master's students targeted")
        elif "undergraduate" in degrees:
            reasons.append("Undergraduate eligible")
    # A posting's licences, none of which the profile holds or expects (D16; Healthcare postings only). Any one is
    # enough, since a posting that names several mostly takes either ("LPN or RN", "RT/RN/RPN").
    licences = facts.get("licences") or {}
    required = [k for k in licences.get("required") or [] if k in kn.licence_by_key]
    if required and not set(required) & set(profile.get("licences") or []):
        penalty("licence", "Licence required", 20, " or ".join(kn.licence_by_key[k].label for k in required) + " required"
                + ("; candidates whose registration is pending are considered" if licences.get("pending_ok") else ""))
    # Hours the profile can work (D15; Settings, unset by default): a posting that states only other employment
    # types, or night shifts. One that states no hours costs nothing.
    hours, can = facts.get("hours") or {}, profile.get("hours") or {}
    stated = hours.get("employment") or []
    if can.get("employment") and stated and not set(stated) & set(can["employment"]):
        penalty("hours", "Hours", 10, " / ".join(EMPLOYMENT_LABELS[k] for k in stated) + "; you can work "
                + ", ".join(EMPLOYMENT_LABELS[k] for k in EMPLOYMENT if k in can["employment"]))
    if can.get("no_nights") and "night" in (hours.get("shifts") or []):
        penalty("nights", "Night shifts", 10, "Night shifts")
    job_countries = set(loc["countries"]) or ({company["country"]} if company.get("country") else set())
    auth = profile.get("work_authorization") or {}
    if elig.get("sponsorship") == "not_available":
        needs = [c for c in job_countries if auth.get(c) == "needs_sponsorship"]
        if needs:
            penalty("sponsorship", "No sponsorship", 15, f"No visa sponsorship; you need sponsorship in {', '.join(needs)}")
    citizenship = elig.get("citizenship") or ""
    if citizenship.startswith("U.S.") and auth.get("US") not in ("citizen",):
        penalty("citizenship", "Citizenship restriction", 20, citizenship)
    elif citizenship.startswith("Canadian") and auth.get("CA") not in ("citizen", "permanent_resident"):
        penalty("citizenship", "Citizenship restriction", 15, citizenship)
    langs = {lang.lower() for lang in profile.get("languages") or ["English"]}
    missing = [lang for lang in elig.get("languages_required", elig.get("languages")) or [] if lang.lower() not in langs]
    if missing:
        penalty("language", "Language requirement", min(12, 8 * len(missing)), f"Requires {', '.join(missing)}")
    gpa = (profile.get("education") or {}).get("gpa")
    if elig.get("gpa_min") and isinstance(gpa, (int, float)) and gpa < elig["gpa_min"]:
        penalty("gpa", "GPA requirement", 10, f"Minimum GPA {elig['gpa_min']} (yours: {gpa})")

    # ---- status / deadline penalties
    status = dyn.get("status") or "active"
    deadline = dyn.get("deadline_override") or (
        (facts.get("deadline") or {}).get("date")
        if (facts.get("deadline") or {}).get("confidence") in ("high", "medium") else None)
    win = window_status(deadline, facts.get("rolling", False), status, today)
    if status == "closed":
        penalty("closed", "Posting closed", 40, "No longer listed on the source")
    elif status == "possibly_closed":
        penalty("possibly_closed", "Possibly closed", 10, "Missing from the latest poll of a complete listing")
    if win == "closed" and status != "closed":
        penalty("deadline_passed", "Deadline passed", 30, f"Deadline was {deadline}")
    elif age_hours is not None and age_hours > 45 * 24 and status == "active":
        penalty("stale", "Stale posting", 5, f"Posted {int(age_hours // 24)} days ago")

    total = sum(s["points"] for s in subscores) + sum(p["points"] for p in penalties)
    fit = max(0, min(100, total))

    # ---- urgency and badges
    urgency = 0
    days_left = None
    if deadline and win in ("open", "closing_soon"):
        days_left = (date.fromisoformat(deadline) - today).days
        urgency += 60 if days_left <= 3 else 40 if days_left <= 7 else 20 if days_left <= 14 else 0
    if competitive and age_hours is not None:
        urgency += 30 if age_hours < 12 else 15 if age_hours < 48 else 0
    if facts.get("rolling") and competitive:
        urgency += 10
    if status != "active" or win == "closed":
        urgency = 0
    urgency = min(100, urgency)
    urgency_label = ("critical" if urgency >= 70 else "high" if urgency >= 45
                     else "medium" if urgency >= 20 else "low")

    badges = []
    first_seen = dyn.get("first_seen")
    if dyn.get("discovered") and first_seen and now - first_seen < 86400:
        badges.append("NEW")
    if posted and now - posted < 86400:
        badges.append("TODAY")
    elif posted and now - posted < 172800:
        badges.append("48H")
    if win == "closing_soon":
        badges.append("DEADLINE SOON")
    if facts.get("rolling"):
        badges.append("ROLLING")
    if cyc.get("year") and not cyc.get("inferred"):
        badges.append(str(cyc["year"]))
    if lvl.get("level") in LEVEL_BADGES and cls.get("is_finance"):
        badges.append(LEVEL_BADGES[lvl["level"]])
    elif lvl.get("board_level") and lvl.get("level") in BOARD_LEVEL_BADGES:
        badges.append(BOARD_LEVEL_BADGES[lvl["level"]])
    if status == "closed":
        badges.append("CLOSED")
    elif status == "possibly_closed":
        badges.append("POSSIBLY CLOSED")
    if dyn.get("recent_change"):
        badges.append("UPDATED")

    return {
        "fit": fit,
        "raw_total": total,
        "subscores": subscores,
        "penalties": penalties,
        "reasons": list(dict.fromkeys(reasons))[:8],
        "concerns": [p["label"] for p in penalties],
        "urgency": urgency,
        "urgency_label": urgency_label,
        "badges": badges,
        "window_status": win,
        "deadline": deadline,
        "days_left": days_left,
        "posting_age_hours": round(age_hours, 1) if age_hours is not None else None,
    }
