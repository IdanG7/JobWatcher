"""Deterministic finance role classification.

Every category and subcategory accumulates evidence from the title (strong),
department (medium), description (weak, capped) and the employer type
(prior).  The best category wins; runners-up within reach become secondary
categories.  The returned ``evidence`` list explains the decision, and the
function signature leaves room for an optional LLM classifier to override a
low-confidence result later without changing callers.  Roles outside finance
get a job family (software, AI & data…) and, where the family defines them, a
specialty such as software.backend.
"""

from __future__ import annotations

import math
import re

from .knowledge import Claim, Knowledge, Node

_TECH_OCCUPATION = re.compile(
    r"\b(engineer(?:ing)?|developer|architect|designer|product (?:manag(?:er|ement)|coordinat(?:or|ion))|"
    r"data scientist|research scientist|applied research|genai|generative ai|"
    r"ai[\s/&-]+ml|quantum (?:technolog\w*|computing)|technology enablement|digital workplace)\b",
    re.I)
_CS_OCCUPATION = re.compile(
    r"\b(engineer(?:ing)?|developer|dev|architect|programmer|data scientist|"
    r"software (?:intern|internship|analyst|consultant|specialist)|"
    r"(?:technology|technical|it) consult(?:ant|ing)|"
    r"trading (?:systems|platform|infrastructure|technology|software))\b", re.I)
# Engineering outside software: 'Civil Engineering Intern', 'Water Infrastructure Engineer',
# 'Welding Engineer'. A bare 'engineer' or a shared word ('infrastructure', 'systems') must
# not file these under software unless the title also names software work.
_PHYSICAL_ENGINEERING = re.compile(
    r"\b(civil(?! liberties)|structural|environmental|water|wastewater|geotechnical|geolog\w*|hydro\w*|chemical|"
    r"process|petroleum|reservoir|drilling|mining|metallurg\w*|materials|welding|nuclear|construction|"
    r"transportation|traffic|coastal|municipal|utilit(?:y|ies)|hvac|piping|pipeline|energy|renewables?|"
    r"solar|wind|aerospace|aeronautical|propulsion|industrial)\b", re.I)
_SOFTWARE_WORK = re.compile(
    r"\b(software|developer|programmer|back[\s-]?end|front[\s-]?end|full[\s-]?stack|cloud|devops|"
    r"site reliability|sre|web|mobile|ios|android|data|machine learning|ml|ai|cyber\w*|privacy|security|"
    r"platform|network|solutions? (?:architect|engineer)|sales engineer)\b|(?-i:\bIT\b)", re.I)


def _physical_engineering(title: str) -> bool:
    return bool(_PHYSICAL_ENGINEERING.search(title)) and not _SOFTWARE_WORK.search(title)


# Hardware occupations that also write code: 'Embedded Software Engineer', 'Firmware
# Engineer' and 'Robotics Software Engineer' are Hardware roles, not Software.
_HARDWARE_OCCUPATION = re.compile(
    r"\b(embedded|firmware|fpga|asic|rtl|pcb|analog|robotics(?! process automation)|perception|motion planning)\b", re.I)


def _software_or_hardware(title: str) -> str:
    return "hardware" if _HARDWARE_OCCUPATION.search(title) else "software"


# A business occupation keeps its family when the title only names a subject:
# 'Product Manager, Threat Detection' and 'Recruiter, AI Research'.
_BUSINESS_OCCUPATION = re.compile(
    r"\b(product (?:manag\w*|owner|associate|analyst|lead|marketing)|program manag\w*|marketing|sales|"
    r"account (?:executive|manager)|counsel|legal|attorney|lawyer|paralegal|recruit\w*|talent|"
    r"auditor|audit|policy|economist|strategy|customer (?:support|success|service))\b", re.I)
_SUPPORT_OCCUPATION = re.compile(
    r"\b(corporate security|workplace (?:coordinator|services)|"
    r"(?:administrative|office|executive|clerical) (?:assistant|support|coordinator)|"
    r"business administration|facilities (?:coordinator|assistant|services))\b", re.I)


def _hits(patterns, text: str) -> list[str]:
    found = []
    if not text:
        return found
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            found.append(match.group(0).strip())
    return found


def _title_hits(node: Node, title: str, family: str) -> list[str]:
    hits = _hits(node.title, title)
    if family != "other":
        # Audit / assurance also describe software and clinical quality work.
        # They cannot override a concrete non-finance occupation by themselves.
        ambiguous = set(node.meta.get("ambiguous_title_hits") or [])
        hits = [hit for hit in hits if hit.lower() not in ambiguous]
    return hits


def _node_score(node: Node, title: str, department: str, description: str,
                weights: dict, family: str = "other") -> tuple[float, list[str]]:
    t = _title_hits(node, title, family)
    d = _hits(node.department, department)
    x = _hits(node.description, description)
    if node.parent:
        # a subcategory's title phrases ('M&A team') are evidence in prose too
        x += [h for h in _hits(node.title, description) if h.lower() not in {e.lower() for e in x}]
    score = (len(t) * weights["title"] + len(d) * weights["department"]
             + min(len(x), weights["description_cap"]) * weights["description"])
    evidence = ([f"title: {h}" for h in t[:2]] + [f"department: {h}" for h in d[:1]]
                + [f"description: {h}" for h in x[:2]])
    return score, evidence


# The occupation comes before the first comma or spaced dash; the team after it.
_TITLE_TAIL = re.compile(r"\s[-–—|:]\s|[,(|–—:]")


def specialty(title: str, kn: Knowledge, family: str, department: str = "",
              description: str = "", company_type: str = "unknown") -> tuple[str | None, list[str], list[str]]:
    """Best specialty within a job family: (key, evidence, runner-up keys).

    'Backend Engineer, Payments Infrastructure' is backend work on an
    infrastructure team, so title words before the first separator count
    more than those after it, and a specialty the title names always beats
    one only the description suggests.  Ties go to the higher tie_priority
    (the more specific occupation).  Postings list every tool the team
    touches, so a specialty read from the description alone needs a full
    set of distinct phrases and a clear lead.  The employer type adds its
    prior (a game studio leans Game Development) but names nothing itself.
    """
    nodes = [n for n in kn.subcategories.values() if n.parent == family]
    if not nodes:
        return None, [], []
    weights = kn.weights
    priors = kn.company_priors.get(company_type, {})
    tail = _TITLE_TAIL.search(title)
    head_end = tail.start() if tail else len(title)
    scored = []
    for node in nodes:
        title_points, title_hits, in_head = 0, [], False
        for pattern in node.title:
            match = pattern.search(title)
            if match:
                title_hits.append(match.group(0).strip())
                in_head = in_head or match.start() < head_end
                title_points += weights["title"] if match.start() < head_end else weights["title"] - 1
        dept = _hits(node.department, department)
        desc = _hits(node.description, description)
        prior = priors.get(f"{family}.{node.key}", 0)
        score = (title_points + len(dept) * weights["department"]
                 + min(len(desc), weights["description_cap"]) * weights["description"] + prior)
        evidence = ([f"title: {h}" for h in title_hits[:2]] + [f"department: {h}" for h in dept[:1]]
                    + [f"description: {h}" for h in desc[:2]] + ([f"employer type: {company_type}"] if prior else []))
        named = 3 if in_head else 2 if title_hits else 1 if dept else 0
        scored.append((named, score, node.meta.get("tie_priority", 0), node.key, evidence))
    scored.sort(key=lambda s: (-s[0], -s[1], -s[2]))
    named, score, _, key, evidence = scored[0]
    runner_up = scored[1][1] if len(scored) > 1 else 0
    if named:
        ok = score >= weights["min_specialty_score"]
    else:
        ok = score >= weights["description_cap"] * weights["description"] and score - runner_up >= 2
    if not ok:
        return None, [], []
    floor = max(weights["min_specialty_score"], score * 0.5)
    secondary = [s[3] for s in scored[1:] if s[1] >= floor][:2]
    return key, evidence[:4], secondary


def family_of(title: str, kn: Knowledge) -> str:
    """Non-finance family for a title (legacy broad tracks)."""
    # Division-only campus titles do not contain "software engineer", but
    # employer priors must not turn an engineering internship into banking.
    business = bool(_BUSINESS_OCCUPATION.search(title))
    physical = _physical_engineering(title)
    for key, node in kn.families.items():
        if physical and key == "software":
            continue
        if _hits(node.title, title) or (not business and _hits(node.domain, title)):
            return _software_or_hardware(title) if key == "software" and not business else key
    if not physical and re.search(r"(?:[,|–—-]\s*engineering\b|\bengineering\s*[,|–—-])", title, re.I) and not re.search(r"\bfinancial engineering\b", title, re.I):
        return _software_or_hardware(title)
    if re.search(r"\b(public affairs|corporate communications)\b", title, re.I):
        return "people_legal"
    return "other"


def _finance_prose(kn: Knowledge, category: str, sub: str | None, description: str) -> int:
    """Distinct description phrases of the finance group a title was placed in."""
    nodes = [kn.categories[category]] + ([kn.subcategories[f"{category}.{sub}"]] if sub else [])
    return len({hit.lower() for node in nodes for hit in _hits(node.description, description)})


def _other_occupation(title: str) -> bool:
    """The title names a tech or business occupation: 'Nurse Recruiter' is a recruiter."""
    return bool(_TECH_OCCUPATION.search(title) or _CS_OCCUPATION.search(title) or _BUSINESS_OCCUPATION.search(title))


def _other_work(title: str) -> bool:
    """Tech or business work that a board's fallback words must not claim: 'AI Scientist', 'Marketing, Biotech'."""
    return _other_occupation(title) or bool(_SOFTWARE_WORK.search(title))


def _claim(kn: Knowledge, title: str, description: str, company_type: str, placed: str,
           finance_prose: int = 0) -> Claim | None:
    """The first named rule by which a board takes this title from where it is placed ('finance' or a family)."""
    if placed == "other" and _other_work(title):
        return None
    for claim in kn.claims:
        if placed not in claim.takes_from or not _hits(claim.title, title) or _hits(claim.unless, title):
            continue
        if claim.sole_occupation and _other_occupation(title):
            continue
        if claim.needs_evidence and not _hits(claim.subject, title):
            prose = bool(claim.description) and len(_hits(claim.description, description)) >= claim.min_description
            if not ((company_type in claim.employer_types or prose) and finance_prose < 2):
                continue
        return claim
    return None


def classify(title: str, kn: Knowledge, description: str = "", department: str = "",
             company_type: str = "unknown", source_hint: str = "") -> dict:
    title = title or ""
    description = (description or "")[:20000]
    department = department or ""
    weights = kn.weights
    priors = kn.company_priors.get(company_type, {})
    generic = bool(kn.generic_finance_title.search(title))
    family = family_of(title, kn)
    cs_occupation = bool(_CS_OCCUPATION.search(title))
    support_occupation = bool(_SUPPORT_OCCUPATION.search(title))
    if family == "other" and cs_occupation and not _physical_engineering(title):
        family = _software_or_hardware(title)
    elif family == "other" and support_occupation:
        family = "operations"
    # 'CT Technologist, Enhanced Pay Rates': finance title words are read without the title's pay line.
    pay = kn.pay_rate_phrase
    finance_title = pay.regex.sub(" ", title) if pay and pay.search(title) else title

    results = {}
    for key, cat in kn.categories.items():
        cat_score, cat_evidence = _node_score(cat, finance_title, department, description, weights, family)
        title_signal = bool(_title_hits(cat, finance_title, family))
        best_sub, best_sub_score, best_sub_evidence = None, 0.0, []
        sub_scores = {}
        for full, sub in kn.subcategories.items():
            if sub.parent != key:
                continue
            score, evidence = _node_score(sub, finance_title, department, description, weights, family)
            if _title_hits(sub, finance_title, family):
                title_signal = True
            score += priors.get(full, 0) if (score or cat_score or generic) else 0
            sub_scores[sub.key] = score
            # ties go to the specific product over a generic bucket (FX over S&T)
            best_generic = best_sub and kn.subcategories[f"{key}.{best_sub}"].meta.get("generic")
            if score > best_sub_score or (score and score == best_sub_score and best_generic
                                          and not sub.meta.get("generic")):
                best_sub, best_sub_score, best_sub_evidence = sub.key, score, evidence
        total = cat_score + best_sub_score
        prior = priors.get(key, 0)
        if prior and (total > 0 or generic):
            total += prior
            cat_evidence = cat_evidence + [f"employer type: {company_type}"]
        # Runner-up groups within reach: a 'Financial Analyst' intern program
        # that also rotates through Accounting lists Accounting as secondary.
        floor = max(weights["title"] - 1, best_sub_score * 0.5)
        runner_ups = sorted((k for k, v in sub_scores.items() if k != best_sub and v >= floor),
                            key=lambda k: -sub_scores[k])
        results[key] = {
            "score": total, "sub": best_sub if best_sub_score > 0 else None,
            "evidence": cat_evidence + best_sub_evidence, "title_signal": title_signal,
            "secondary_subs": runner_ups[:2] if best_sub_score > 0 else [],
        }

    ranked = sorted(results.items(), key=lambda kv: (
        -kv[1]["score"], -kn.categories[kv[0]].meta.get("tie_priority", 0)))
    best_key, best = ranked[0]
    second_score = ranked[1][1]["score"] if len(ranked) > 1 else 0.0
    # Weak categories (FinTech, Strategy) only claim a title from 'other';
    # 'Senior Software Engineer, Payments' stays a software role.
    finance_title_hit = any(r["title_signal"] for k, r in results.items()
                            if family == "other" or not kn.categories[k].meta.get("weak_title"))
    if family != "other" and kn.categories[best_key].meta.get("weak_title"):
        strong = [(k, r) for k, r in ranked if not kn.categories[k].meta.get("weak_title")]
        best_key, best = strong[0]

    # "Lending AI Engineer" names a technical occupation in a banking domain.
    # Domain words and employer priors must not replace the actual occupation.
    # Financial quantitative research remains finance, while software and
    # trading systems development stays technical even at a trading firm.
    technical_occupation = family in kn.occupation_families and bool(_TECH_OCCUPATION.search(title))
    if cs_occupation or support_occupation:
        finance_title_hit = False
    elif technical_occupation:
        if results.get("quant", {}).get("title_signal"):
            best_key, best = "quant", results["quant"]
            ranked = [(best_key, best)] + [(k, r) for k, r in ranked if k != best_key]
            second_score = max((r["score"] for k, r in results.items() if k != "quant"), default=0)
        else:
            finance_title_hit = False

    min_score = weights["min_finance_score"]
    is_finance = best["score"] >= min_score and (finance_title_hit or family == "other")
    # Tech employer types carry priors for tech specialties only; those never make a role finance.
    finance_priors = any(k.split(".")[0] in kn.categories for k in priors)
    if not is_finance and family == "other" and generic and finance_priors and best["score"] > 0:
        # 'Summer Analyst' at a bank with no division named: finance, low confidence
        is_finance = True

    # 'Research Associate, Cell Biology' is lab work that Equity Research's title words also cover: a board's
    # named rule takes it (plans/healthcare-board.md, D1). Finance is otherwise decided exactly as before.
    claim = None
    if is_finance:
        claim = _claim(kn, title, description, company_type, "finance",
                       _finance_prose(kn, best_key, best["sub"], description))
        is_finance = claim is None
    if not is_finance:
        secondary = [] if claim else [k for k, r in ranked[:2] if r["score"] >= min_score]
        claim = claim or _claim(kn, title, description, company_type, family)
        if claim:
            family = claim.board
        elif family == "other" and not _other_work(title):
            # Tier 2: a board's fallback words place what no board and no finance rule placed.
            family = next((key for key, words in kn.fallback_titles if _hits(words, title)), family)
        if claim and claim.subcategory:
            sub, sub_evidence, secondary_subs = claim.subcategory, [], []
        else:
            sub, sub_evidence, secondary_subs = specialty(title, kn, family, department, description, company_type)
        out = {
            "family": family if family != "other" else "other",
            "category": family,
            "category_label": kn.category_label(family),
            "subcategory": sub,
            "subcategory_label": kn.subcategory_label(family, sub),
            "secondary": secondary,
            "secondary_labels": [kn.category_label(k) for k in secondary],
            "confidence": 0.6 if family != "other" else 0.2,
            "is_finance": False,
            "evidence": ([f"rule: {claim.name}" if claim else f"title family: {family}"] + sub_evidence)
                        if family != "other" else ["no strong signal"],
            "competitive": False,
            "associate_stage": "entry",
            "secondary_subcategories": secondary_subs,
            "secondary_subcategory_labels": [kn.subcategory_label(family, k) for k in secondary_subs],
        }
        if claim:
            out["rule"] = claim.name
        return out

    top = best["score"]
    margin = max(0, (top - second_score) / top) if top else 0
    confidence = round(min(0.99, (1 - math.exp(-top / 5)) * (0.55 + 0.45 * margin)), 2)
    secondary = [k for k, r in ranked[1:4] if r["score"] >= max(min_score, top * 0.45)]
    out = _result(kn, best_key, best["sub"], confidence, best["evidence"], secondary)
    # 'Global Technology Summer Analyst' at a bank: nothing but the employer
    # points at a division, so the label is a guess, not evidence.
    out["prior_only"] = all(e.startswith("employer type:") for e in best["evidence"])
    out["secondary_subcategories"] = best.get("secondary_subs", [])
    out["secondary_subcategory_labels"] = [kn.subcategory_label(best_key, k) for k in out["secondary_subcategories"]]
    return out


def _result(kn: Knowledge, category: str, sub: str | None, confidence: float,
            evidence: list[str], secondary: list[str], family: str = "finance",
            rule: str = "") -> dict:
    meta = kn.categories[category].meta
    out = {
        "family": family,
        "category": category,
        "category_label": kn.category_label(category),
        "subcategory": sub,
        "subcategory_label": kn.subcategory_label(category, sub),
        "secondary": secondary,
        "secondary_labels": [kn.category_label(k) for k in secondary],
        "confidence": confidence,
        "is_finance": True,
        "evidence": evidence[:6],
        "competitive": bool(meta.get("competitive")),
        "associate_stage": meta.get("associate_stage", "entry"),
    }
    if rule:
        out["rule"] = rule
    return out


def confidence_label(value: float) -> str:
    return "high" if value >= 0.75 else "medium" if value >= 0.5 else "low"
