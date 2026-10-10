"""Deterministic finance role classification.

Every category and subcategory accumulates evidence from the title (strong),
department (medium), description (weak, capped) and the employer type
(prior).  The best category wins; runners-up within reach become secondary
categories.  The returned ``evidence`` list explains the decision, and the
function signature leaves room for an optional LLM classifier to override a
low-confidence result later without changing callers.
"""

from __future__ import annotations

import math
import re

from .knowledge import Knowledge, Node

_TECH_OCCUPATION = re.compile(
    r"\b(engineer(?:ing)?|developer|architect|designer|product (?:manag(?:er|ement)|coordinat(?:or|ion))|"
    r"data scientist|research scientist|applied research|genai|generative ai|"
    r"ai[\s/&-]+ml|quantum (?:technolog\w*|computing)|technology enablement|digital workplace)\b",
    re.I)


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


def family_of(title: str, kn: Knowledge) -> str:
    """Non-finance family for a title (legacy broad tracks)."""
    # Division-only campus titles do not contain "software engineer", but
    # employer priors must not turn an engineering internship into banking.
    for key, node in kn.families.items():
        if _hits(node.title, title):
            return key
    if re.search(r"(?:[,|–—-]\s*engineering\b|\bengineering\s*[,|–—-])", title, re.I) and not re.search(r"\bfinancial engineering\b", title, re.I):
        return "software"
    if re.search(r"\b(public affairs|corporate communications)\b", title, re.I):
        return "people_legal"
    return "other"


def classify(title: str, kn: Knowledge, description: str = "", department: str = "",
             company_type: str = "unknown", source_hint: str = "") -> dict:
    title = title or ""
    description = (description or "")[:20000]
    department = department or ""
    weights = kn.weights
    priors = kn.company_priors.get(company_type, {})
    generic = bool(kn.generic_finance_title.search(title))
    family = family_of(title, kn)

    results = {}
    for key, cat in kn.categories.items():
        cat_score, cat_evidence = _node_score(cat, title, department, description, weights, family)
        title_signal = bool(_title_hits(cat, title, family))
        best_sub, best_sub_score, best_sub_evidence = None, 0.0, []
        for full, sub in kn.subcategories.items():
            if sub.parent != key:
                continue
            score, evidence = _node_score(sub, title, department, description, weights, family)
            if _title_hits(sub, title, family):
                title_signal = True
            score += priors.get(full, 0) if (score or cat_score or generic) else 0
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
        results[key] = {
            "score": total, "sub": best_sub if best_sub_score > 0 else None,
            "evidence": cat_evidence + best_sub_evidence, "title_signal": title_signal,
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
    # Explicit quantitative / trading systems titles remain finance occupations.
    technical_occupation = family in {"software", "hardware", "data_ml", "product", "design", "healthcare"} and bool(
        _TECH_OCCUPATION.search(title))
    if technical_occupation:
        if results.get("quant", {}).get("title_signal"):
            best_key, best = "quant", results["quant"]
            ranked = [(best_key, best)] + [(k, r) for k, r in ranked if k != best_key]
            second_score = max((r["score"] for k, r in results.items() if k != "quant"), default=0)
        else:
            finance_title_hit = False

    min_score = weights["min_finance_score"]
    is_finance = best["score"] >= min_score and (finance_title_hit or family == "other")
    if not is_finance and family == "other" and generic and priors and best["score"] > 0:
        # 'Summer Analyst' at a bank with no division named: finance, low confidence
        is_finance = True

    if not is_finance:
        secondary = [k for k, r in ranked[:2] if r["score"] >= min_score]
        return {
            "family": family if family != "other" else "other",
            "category": family,
            "category_label": kn.category_label(family),
            "subcategory": None,
            "subcategory_label": "",
            "secondary": secondary,
            "secondary_labels": [kn.category_label(k) for k in secondary],
            "confidence": 0.6 if family != "other" else 0.2,
            "is_finance": False,
            "evidence": [f"title family: {family}"] if family != "other" else ["no strong signal"],
            "competitive": False,
            "associate_stage": "entry",
        }

    top = best["score"]
    margin = max(0, (top - second_score) / top) if top else 0
    confidence = round(min(0.99, (1 - math.exp(-top / 5)) * (0.55 + 0.45 * margin)), 2)
    secondary = [k for k, r in ranked[1:4] if r["score"] >= max(min_score, top * 0.45)]
    return _result(kn, best_key, best["sub"], confidence, best["evidence"], secondary)


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
