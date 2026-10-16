"""Which fields each source serves, so a poll skips sources outside the profile's fields.

A source's track is 'finance', 'tech' or 'both': the board's own ``track`` in
config.json, else the track of its employer's type (config/companies.json).
Shared sources (GitHub lists, LinkedIn searches) have no single employer and
count as 'both' unless they say otherwise.

Finance profiles poll finance sources, Software, AI & Data, Hardware, Product
and Design poll tech sources, and every profile polls 'both'.  Fields every
employer hires for (sales, operations, legal, healthcare) poll everything, as
does a profile that names no field yet.
"""

from __future__ import annotations

from .companies import resolve_company
from .knowledge import Knowledge

TRACKS = ("finance", "tech")
TECH_FIELDS = frozenset({"software", "data_ml", "hardware", "product", "design"})
SHARED_ATS = frozenset({"github_listings", "github_md", "linkedin"})


def source_track(name: str, cfg: dict, kn: Knowledge) -> str:
    """'finance', 'tech' or 'both' for one board."""
    if cfg.get("track") in ("finance", "tech", "both"):
        return cfg["track"]
    if cfg.get("ats") in SHARED_ATS:
        return "both"
    ctype = resolve_company("", kn, board=name, board_cfg=cfg)["type"]
    return kn.company_types.get(ctype, {}).get("track") or "both"


def profile_fields(profile: dict, kn: Knowledge) -> set[str]:
    """The fields a profile names, plus the field of each target role ('investment_banking.ma' -> finance)."""
    fields = set(profile.get("fields") or [])
    for role in profile.get("target_roles") or []:
        top = role.split(".")[0]
        fields.add("finance" if top in kn.categories else top)
    return fields


def profile_tracks(profile: dict, kn: Knowledge) -> set[str]:
    """The source tracks a profile polls."""
    tracks = {"finance" if f == "finance" else "tech" if f in TECH_FIELDS else "any"
              for f in profile_fields(profile, kn)}
    return set(TRACKS) if not tracks or "any" in tracks else tracks


def polls(track: str, tracks: set[str]) -> bool:
    return track == "both" or track in tracks
