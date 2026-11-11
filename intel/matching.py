"""Explainable resume filtering: explicit conflicts exclude, unknowns stay visible."""

from __future__ import annotations

from .profile import CAMPUS_STAGES
from .sources import profile_fields

# Finance roles that need a background a resume must show; outside the
# candidate's targets they are filtered instead of merely ranked lower.
SPECIALIST = {
    "quant": "Quant role: needs a programming / mathematics background your resume and targets don't show",
    "insurance": "Actuarial / underwriting role: outside your resume and targets",
}


def match_resume(facts: dict, profile: dict, scored: dict, kn=None) -> dict:
    """``kn`` lets the profile's fields decide which roles outside its targets stay
    eligible; without it, or for a finance-only profile, finance roles do."""
    cls, stage = facts["classification"], facts["seniority"].get("stage")
    loc, elig = facts["location"], facts.get("eligibility") or {}
    exclusions, reasons, review = [], [], []
    targets = profile.get("target_roles") or []
    category, sub = cls.get("category"), cls.get("subcategory")
    full = f"{category}.{sub}" if sub else category
    relevant = not targets or category in targets or full in targets or (
        not sub and any(t.startswith(f"{category}.") for t in targets))
    fields = set(profile_fields(profile, kn)) if kn else {"finance"}
    family, label = cls.get("family"), cls.get("category_label") or category
    if not relevant and cls.get("is_finance") and "finance" in fields and category in SPECIALIST:
        exclusions.append(SPECIALIST[category])
    elif not relevant and cls.get("is_finance") and "finance" in fields:
        reasons.append("Eligible finance role; your targets and experience affect ranking")
    elif not relevant and any(t.startswith(f"{category}.") for t in targets):
        # Frontend work for someone targeting Backend: same field, ranked lower.
        reasons.append(f"{label} role outside your specialties; ranked lower")
    elif not relevant and not cls.get("is_finance") and family != "finance" and family in fields:
        # A field the user recruits in (Software, AI & Data…) with no target in it.
        reasons.append(f"Eligible {label} role; your targets and experience affect ranking")
    elif not relevant and family not in (None, "unknown", "other"):
        exclusions.append("Role is outside finance and your selected career targets" if fields == {"finance"} else
                          f"{'Finance' if cls.get('is_finance') else label} role is outside the fields you recruit in")
    elif not relevant and "finance" not in fields:
        # Nothing places the role in a field. Finance titles are often that vague, so a finance
        # profile reviews them; for tech boards it is noise ("Illustrator, Intern").
        exclusions.append("Role doesn't name a field you recruit in")
    elif not relevant:
        review.append("Role relevance needs review")
    elif cls.get("prior_only"):
        # Only the employer suggested the division: shown, but never a target match.
        review.append("Division is not named in the posting; check what the role does")
    else:
        reasons.append(f"Relevant role: {cls.get('category_label') or category}")
    if cls.get("confidence", 0) < 0.5:
        review.append("Role classification has limited evidence")
    stages = profile.get("target_stages") or []
    if (stage == "entry" and facts["seniority"].get("level") == "analyst" and "new_grad" in stages
            and relevant and cls.get("is_finance") and not cls.get("prior_only")):
        # A bare 'Analyst' title is the finance entry level and often a campus hire.
        review.append("Title does not say whether this is a new-grad role; check the experience required")
    elif (stage and stage not in ("unknown", "other") and stages and stage not in stages
          and (stage != "entry" or CAMPUS_STAGES & set(stages))):
        # A profile in the workforce still sees a title that names no level ("Registered Nurse", "QA Analyst"):
        # it reads as entry level, and the score ranks it below the target stages.
        exclusions.append(f"Career stage {stage.replace('_', ' ')} is outside your targets")
    elif not stage or stage == "unknown":
        review.append("Career stage is not stated")
    target_countries = set(profile.get("target_countries") or [])
    countries = set(loc.get("countries") or [])
    if countries and target_countries and not countries.intersection(target_countries):
        exclusions.append("Location is outside your target countries")
    elif not countries:
        review.append("Location eligibility needs review")
    for penalty in scored.get("penalties", []):
        if penalty["key"] in ("graduation", "degree", "gpa", "language", "cycle_year"):
            exclusions.append(penalty["detail"])
        elif penalty["key"] == "graduation_near":
            review.append(penalty["detail"])
    auth = profile.get("work_authorization") or {}
    if any(auth.get(c) in (None, "unknown") for c in countries):
        review.append("Work authorization is not confirmed for the posting location")
    citizenship = elig.get("citizenship") or ""
    required_country = "US" if citizenship.startswith("U.S.") else "CA" if citizenship.startswith("Canadian") else None
    generic_citizenship = citizenship.startswith("Permanent resident")
    if generic_citizenship and len(countries) == 1:
        required_country = next(iter(countries))
    if required_country:
        known = auth.get(required_country)
        permitted = ("citizen",) if required_country == "US" and not generic_citizenship else ("citizen", "permanent_resident")
        if known not in (None, "unknown") and known not in permitted:
            exclusions.append(citizenship)
        elif known in (None, "unknown"):
            review.append("Citizenship / work authorization needs confirmation")
    if elig.get("sponsorship") == "not_available":
        if any(auth.get(c) == "needs_sponsorship" for c in countries):
            exclusions.append("Posting does not offer required sponsorship")
        elif any(auth.get(c) in (None, "unknown") for c in countries):
            review.append("Work authorization is unknown; posting offers no sponsorship")
    if not facts.get("graduation") and (not stages or CAMPUS_STAGES & set(stages)):
        # A profile in the workforce (only entry, experienced or senior targets) has no graduation date to check.
        review.append("Graduation requirement is not stated")
    cycle = facts.get("cycle") or {}
    if cycle.get("inferred"):
        review.append("Recruiting cycle is inferred; confirm the start date in the posting")
    year = profile.get("graduation_year")
    if year and cycle.get("year") and not cycle.get("inferred") and stage == "new_grad" and cycle["year"] < year:
        exclusions.append(f"Graduate program starts in {cycle['year']}, before graduation in {year}")
    elif (year and cycle.get("year") and not cycle.get("inferred") and stage == "new_grad"
          and cycle["year"] > year + 1):
        exclusions.append(f"Graduate program is for {cycle['year']} graduates; you graduate in {year}")
    if scored.get("window_status") == "closed":
        exclusions.append("Posting or application window is closed")
    mine = set(profile.get("skills") or [])
    matched_skills = [s["label"] for s in facts.get("skills", []) if s["key"] in mine]
    if matched_skills:
        reasons.append(f"Skills: {', '.join(matched_skills[:6])}")
    if not facts.get("has_description"):
        review.append("Posting description is unavailable; check the original requirements")
    matched = not exclusions
    off_list = _off_list(facts, profile, kn, matched_skills) if matched else []
    return {"matched": matched, "reasons": reasons, "exclusions": list(dict.fromkeys(exclusions)),
            "review": review, "matched_skills": matched_skills,
            # The short list: eligible, and worth reading. What time decides (still listed, how old) is
            # checked when the list is asked for, so it needs no rescore to stay true.
            "shortlist": matched and not off_list, "off_list": off_list,
            "tier": SHORTLIST if matched and not off_list else ELIGIBLE if matched else EXCLUDED}


# What resume_matches.matched holds.
EXCLUDED, ELIGIBLE, SHORTLIST = 0, 1, 2
# A posting with no specialty of its own, or a neighbouring one, is on the list only when the
# resume's skills are most of what it asks for.
SKILLS_SHARE, SKILLS_AT_LEAST = 0.75, 2


def _off_list(facts: dict, profile: dict, kn, matched_skills: list[str]) -> list[str]:
    """Why an eligible posting is not on the short list (empty when it is)."""
    cls, loc = facts["classification"], facts["location"]
    reasons = []
    targets = profile.get("target_roles") or []
    category, sub = cls.get("category"), cls.get("subcategory")
    label = cls.get("category_label") or category
    if targets and not _specific(cls, targets, kn, facts.get("skills") or [], matched_skills):
        mine = [t for t in targets if t.startswith(f"{category}.")]
        if cls.get("prior_only"):
            reasons.append("The posting doesn't name what the role does")
        elif category not in targets and not mine:
            reasons.append(f"{label} is not one of your target roles")
        elif sub:
            reasons.append(f"{cls.get('subcategory_label') or sub} is not one of your specialties, "
                           "and the posting asks for little that your resume shows")
        else:
            reasons.append("The posting names no specialty, and asks for little that your resume shows"
                           if facts.get("has_description") else
                           "The posting names no specialty, and its description hasn't been read yet")
    target_countries = set(profile.get("target_countries") or [])
    countries = set(loc.get("countries") or [])
    remote = loc.get("remote") and profile.get("open_to_remote", True)
    if target_countries and not countries & target_countries and not (remote and not countries):
        reasons.append("The posting doesn't say where the role is")
    return reasons


def _specific(cls: dict, targets: list[str], kn, job_skills: list[dict], matched_skills: list[str]) -> bool:
    """The role is one the person picked or the resume shows, not merely somewhere in a board."""
    from .scoring import _related_target
    category, sub = cls.get("category"), cls.get("subcategory")
    if cls.get("prior_only"):
        return False
    if sub and f"{category}.{sub}" in targets:
        return True
    mine = [t for t in targets if t.startswith(f"{category}.")]
    board_level = kn is not None and category in kn.families
    if category in targets and (not board_level or not mine):
        # A finance area (Investment Banking) is specific. A board picked with no specialty in it is
        # the person's own choice of breadth.
        return True
    if category not in targets and not mine:
        return False
    if kn is not None and _related_target(kn, targets, category, sub):
        return True
    asked = min(4, len(job_skills))
    return bool(asked) and len(matched_skills) >= SKILLS_AT_LEAST and len(matched_skills) / asked >= SKILLS_SHARE
