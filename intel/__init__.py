"""Finance recruiting intelligence (pure functions, no I/O beyond config).

    facts  = build_facts(job, kn)             # profile-independent, cached
    result = score_job(facts, profile, kn)    # cheap, explainable, time-aware

``analyze`` combines both for one-off callers (alerts, legacy facade).
"""

from __future__ import annotations

import time

from .facts import FACTS_VERSION, build_facts, input_hash, normalize_title
from .knowledge import CONFIG_DIR, Knowledge, config_fingerprint, load_knowledge, normalize_company
from .profile import DEFAULT_PROFILE, merge_profile, profile_version, validate_profile
from .scoring import score_job

__all__ = [
    "CONFIG_DIR", "DEFAULT_PROFILE", "FACTS_VERSION", "Knowledge", "analyze", "build_facts",
    "config_fingerprint", "input_hash", "load_knowledge", "merge_profile", "normalize_company",
    "normalize_title", "profile_version", "score_job", "validate_profile",
]


def analyze(job: dict, profile: dict | None = None, kn: Knowledge | None = None,
            board_cfg: dict | None = None, section: str = "", dyn: dict | None = None,
            now: float | None = None) -> dict:
    kn = kn or load_knowledge()
    profile = merge_profile(profile)
    facts = build_facts(job, kn, board_cfg, section)
    posted = job.get("posted")
    dyn = {"posted": float(posted) if posted not in (None, "") else None, **(dyn or {})}
    scored = score_job(facts, profile, kn, dyn, now or time.time())
    return {**facts, **scored}
