"""Employer resolution: free-text company names -> company intelligence."""

from __future__ import annotations

import re

from .knowledge import Knowledge, normalize_company

# Section headers among the sources ('_' keys: config/sources packs and their
# old headings, or an older config.json's) imply a company type for boards
# whose employer is not (yet) in companies.json.
_SECTION_TYPES = (
    ("quant", "quant_firm"),
    ("canadian_bank", "canadian_bank"),
    ("fintech", "fintech"),
    ("bulge", "bulge_bracket"),
    ("boutique", "elite_boutique"),
    ("private_equity", "private_equity"),
    ("pension", "pension_fund"),
    ("asset_manag", "asset_manager"),
    ("hedge", "hedge_fund"),
    ("insurance", "insurance"),
)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_company(name)).strip("_") or "unknown"


def resolve_company(name: str, kn: Knowledge, board: str = "",
                    board_cfg: dict | None = None, section: str = "") -> dict:
    """Return {key, name, type, type_label, known, country, hq}.

    Resolution order: explicit ``company_key`` on the board, the posting's
    company string, then the board name (direct boards are single-employer).
    Aggregator boards never fall back to the board name.
    """
    board_cfg = board_cfg or {}
    company = None
    pinned = board_cfg.get("company_key")
    if pinned and pinned in kn.companies:
        company = kn.companies[pinned]
    if company is None and name:
        company = kn.match_company(name)
    aggregator = board_cfg.get("ats") in {"github_listings", "github_md", "linkedin"}
    if company is None and board and not aggregator:
        company = kn.match_company(board.replace("_", " "))

    if company is not None:
        return {
            "key": company.key, "name": company.name, "type": company.type,
            "type_label": kn.type_label(company.type), "known": True,
            "country": company.country, "hq": company.hq,
        }

    ctype = board_cfg.get("company_type") or "unknown"
    if ctype == "unknown" and not aggregator:
        lowered = section.lower()
        for needle, inferred in _SECTION_TYPES:
            if needle in lowered:
                ctype = inferred
                break
    display = (name or board.replace("_", " ")).strip()
    return {
        "key": slug(display), "name": display, "type": ctype,
        "type_label": kn.type_label(ctype), "known": False,
        "country": "", "hq": "",
    }
