"""Compatibility facade over the finance intelligence engine (``intel/``).

Older code and scripts import ``role_track``, ``seniority``,
``location_bucket``, ``analyze_job`` and friends from here.  They now
delegate to the data-driven taxonomy, finance-aware seniority and Fit 2.0
scoring while keeping their original return shapes.
"""

from __future__ import annotations

from intel import analyze, load_knowledge, merge_profile
from intel.locations import parse_location
from intel.profile import DEFAULT_PROFILE
from intel.seniority import legacy_stage
from intel.taxonomy import classify

# Legacy broad tracks (labels used by older UIs and CSV exports).
TRACKS = {
    "quant": {"label": "Quant"},
    "data_ml": {"label": "AI & data"},
    "software": {"label": "Software"},
    "hardware": {"label": "Hardware"},
    "product": {"label": "Product"},
    "design": {"label": "Design"},
    "finance": {"label": "Finance"},
    "sales": {"label": "Sales & growth"},
    "operations": {"label": "Operations"},
    "people_legal": {"label": "People & legal"},
}
# Board section tags (from config.json headers) -> employer type for unknown firms.
_TAG_TYPES = {"quant": "quant_firm", "fintech": "fintech"}

__all__ = ["DEFAULT_PROFILE", "TRACKS", "analyze_job", "board_tags", "location_bucket",
           "merged_profile", "role_track", "seniority", "stable_job_key"]


def merged_profile(config: dict | None) -> dict:
    return merge_profile((config or {}).get("profile"))


def board_tags(config: dict | None) -> dict[str, set[str]]:
    """Infer useful company/source tags from the human sections in config."""
    tags: dict[str, set[str]] = {}
    section = ""
    for name in ((config or {}).get("boards") or {}):
        if name.startswith("_"):
            section = name
            continue
        current: set[str] = set()
        if "quant" in section:
            current.add("quant")
        if "startup" in section or "ai_and_startups" in section:
            current.add("startup")
        if "fintech" in section:
            current.add("fintech")
        if "aggregator" in section or "linkedin" in section:
            current.add("aggregator")
        if "canadian" in section:
            current.update(("canada", "finance"))
        tags[name] = current
    return tags


def role_track(title: str) -> str:
    """Broad track: finance roles collapse to 'quant' or 'finance'."""
    result = classify(title or "", load_knowledge())
    if result["is_finance"]:
        return "quant" if result["category"] == "quant" else "finance"
    return result["category"] if result["category"] in TRACKS else "other"


def seniority(title: str) -> str:
    return legacy_stage(title or "")


def location_bucket(location: str) -> str:
    return parse_location(location or "", load_knowledge())["bucket"]


def analyze_job(job: dict, config: dict | None = None, tags: set[str] | None = None,
                preferred_company: bool = False) -> dict:
    """Return legacy keys (score, reasons, track, …) plus the full Fit 2.0 result."""
    tags = set(tags or ())
    board_cfg = {}
    for tag, ctype in _TAG_TYPES.items():
        if tag in tags:
            board_cfg["company_type"] = ctype
    profile = (config or {}).get("profile")
    result = analyze(job, profile, board_cfg=board_cfg, dyn={"watched": preferred_company})
    cls = result["classification"]
    track = ("quant" if cls["category"] == "quant" else "finance") if cls["is_finance"] else cls["category"]
    return {
        **result,
        "score": result["fit"],
        "reasons": result["reasons"],
        "track": track,
        "track_label": TRACKS.get(track, {"label": "Other"})["label"],
        "seniority": result["seniority"]["stage"],
        "location_bucket": result["location"]["bucket"],
        "company_tags": sorted(tags),
    }


def stable_job_key(job: dict) -> str:
    board = str(job.get("board") or "unknown")
    job_id = str(job.get("job_id") or job.get("id") or "")
    return f"{board}:{job_id}"
