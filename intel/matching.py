"""Explainable resume filtering: explicit conflicts exclude, unknowns stay visible."""

# Finance roles that need a background a resume must show; outside the
# candidate's targets they are filtered instead of merely ranked lower.
SPECIALIST = {
    "quant": "Quant role: needs a programming / mathematics background your resume and targets don't show",
    "insurance": "Actuarial / underwriting role: outside your resume and targets",
}


def match_resume(facts: dict, profile: dict, scored: dict) -> dict:
    cls, stage = facts["classification"], facts["seniority"].get("stage")
    loc, elig = facts["location"], facts.get("eligibility") or {}
    exclusions, reasons, review = [], [], []
    targets = profile.get("target_roles") or []
    category, sub = cls.get("category"), cls.get("subcategory")
    full = f"{category}.{sub}" if sub else category
    relevant = not targets or category in targets or full in targets or (
        not sub and any(t.startswith(f"{category}.") for t in targets))
    if not relevant and cls.get("is_finance") and category in SPECIALIST:
        exclusions.append(SPECIALIST[category])
    elif not relevant and cls.get("is_finance"):
        reasons.append("Eligible finance role; your targets and experience affect ranking")
    elif not relevant and cls.get("family") not in (None, "unknown", "other"):
        exclusions.append("Role is outside finance and your selected career targets")
    elif not relevant:
        review.append("Role relevance needs review")
    else:
        reasons.append(f"Relevant role: {cls.get('category_label') or category}")
    if cls.get("confidence", 0) < 0.5:
        review.append("Role classification has limited evidence")
    stages = profile.get("target_stages") or []
    if stage and stage not in ("unknown", "other") and stages and stage not in stages:
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
    if not facts.get("graduation"):
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
    return {"matched": not exclusions, "reasons": reasons, "exclusions": list(dict.fromkeys(exclusions)),
            "review": review, "matched_skills": matched_skills}
