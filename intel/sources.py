"""Which sources each profile polls.

Sources (the feeds Foothold polls; ``config["boards"]`` in the code) live in
packs under ``config/sources/<folder>/<group>.json``.  The folder decides
which boards (the fields picked in onboarding: Finance, Software…) may poll a
pack: ``finance/`` only the Finance board, ``tech/`` the tech boards and
Healthcare, ``shared/`` all of them and ``health/`` only Healthcare.
``config/sources/manifest.json`` gives each board the groups it polls and, for
boards split into filters (Software → Backend…), the groups each filter adds.

The Finance board polls every ``finance/`` and ``shared/`` pack: exactly the
sources it polled in 0.3.7, so new tech sources (always in ``tech/``) never
change what it shows.  ``config["boards"]`` stays the universe: selection only
leaves sources out, and a source in no pack (one the user added) is always
polled.
"""

from __future__ import annotations

import copy
import json
import threading
from dataclasses import dataclass
from pathlib import Path

from .knowledge import CONFIG_DIR

SOURCES_DIR = CONFIG_DIR / "sources"
MAX_PACK = 50
EVERYTHING = "everything"

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[tuple, "Packs"]] = {}


@dataclass(frozen=True)
class Pack:
    key: str            # 'shared/ai_labs'
    folder: str
    group: str
    title: str
    verified: str | None
    note: str
    sources: dict       # name -> settings, in file order
    sections: dict      # config.json heading a source sat under before packs -> those sources


class Packs:
    """The manifest and every pack, validated: each source is defined once."""

    def __init__(self, manifest: dict, packs: dict[str, dict]):
        self.folders: dict[str, set[str]] = {
            name: set(rule.get("fields") or []) for name, rule in (manifest.get("folders") or {}).items()}
        self.fields: dict[str, dict] = {k: v for k, v in (manifest.get("fields") or {}).items()
                                        if not k.startswith("_")}
        self.packs: dict[str, Pack] = {}
        self.source_pack: dict[str, str] = {}
        problems = []
        order = list(self.folders)

        def rank(key: str) -> tuple:      # folders in manifest order, packs alphabetically within each
            folder = key.partition("/")[0]
            return (order.index(folder) if folder in order else len(order), key)

        for key in sorted(packs, key=rank):
            folder, _, group = key.partition("/")
            data = packs[key]
            if folder not in self.folders:
                problems.append(f"pack {key}: folder {folder}/ is not in the manifest")
                continue
            sources = data.get("boards") or {}
            if len(sources) > MAX_PACK:
                problems.append(f"pack {key}: {len(sources)} sources (at most {MAX_PACK})")
            for name in sources:
                if name in self.source_pack:
                    problems.append(f"source {name}: defined in {self.source_pack[name]} and {key}")
                self.source_pack.setdefault(name, key)
            sections = data.get("sections") or {}
            problems += [f"pack {key}: section {heading} lists {name}, which is not one of its sources"
                         for heading, names in sections.items() for name in names if name not in sources]
            self.packs[key] = Pack(key, folder, group, data.get("title") or group.replace("_", " ").title(),
                                   data.get("verified"), data.get("note") or "", sources, sections)
        groups = {p.group for p in self.packs.values()}
        for field, rule in self.fields.items():
            named = set(rule.get("core") or [])
            if isinstance(rule.get("groups"), list):
                named |= set(rule["groups"])
            for picks in (rule.get("filters") or {}).values():
                named |= set(picks)
            problems += [f"board {field}: no pack for group {g}" for g in sorted(named - groups)]
        if problems:
            raise ValueError("; ".join(problems))

    def flat(self) -> dict:
        """Every source in pack order, after a '_<pack>' header (as config.json's sections were).
        A heading's name hints the company type of employers missing from companies.json
        (intel/companies.py), so sources a pack lists under an old heading follow it under
        '_<pack>/<heading>' and keep the type they had."""
        out: dict = {}
        for pack in self.packs.values():
            kept = {name for names in pack.sections.values() for name in names}
            out[f"_{pack.key}"] = pack.note or pack.title
            out.update({name: copy.deepcopy(cfg) for name, cfg in pack.sources.items() if name not in kept})
            for heading, names in pack.sections.items():
                out[f"_{pack.key}/{heading}"] = pack.title
                out.update({name: copy.deepcopy(pack.sources[name]) for name in names})
        return out


def _read(root: Path) -> tuple[dict, dict[str, dict]]:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    packs = {path.relative_to(root).with_suffix("").as_posix(): json.loads(path.read_text(encoding="utf-8"))
             for path in sorted(root.glob("*/*.json"))}
    return manifest, packs


def load_packs(root: Path | str | None = None) -> Packs:
    """Packs from ``root`` (default config/sources), re-read when a file changes.
    Without a manifest there are no packs, so every source counts as the user's own."""
    root = Path(root or SOURCES_DIR)
    files = [root / "manifest.json", *sorted(root.glob("*/*.json"))]
    stamp = tuple((str(f), f.stat().st_mtime_ns) for f in files if f.exists())
    key = str(root.resolve())
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        packs = Packs(*_read(root)) if (root / "manifest.json").exists() else Packs({}, {})
        _CACHE[key] = (stamp, packs)
        return packs


def load_config(path: Path | str, sources: Path | str | None = None) -> dict:
    """config.json with its sources.  An install's copy lists them itself; the
    repository's does not, so they are assembled from the packs."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if "boards" not in config:
        config["boards"] = load_packs(sources).flat()
    return config


def enabled_sources(config: dict) -> dict:
    return {name: cfg for name, cfg in (config.get("boards") or {}).items()
            if not name.startswith("_") and isinstance(cfg, dict) and not cfg.get("disabled")}


# ------------------------------------------------------------ boards and filters
def role_field(role: str, kn) -> str:
    """The board a target role belongs to: 'investment_banking.ma' -> finance, 'software.backend' -> software."""
    top = role.split(".")[0]
    return "finance" if top in kn.categories else top


def profile_fields(profile: dict, kn) -> list[str]:
    """The profile's boards plus the board of each target role; Finance when there are none.
    Mirrors profileFields() in web/js/fields.js."""
    fields = profile.get("fields")
    out = [f for f in fields if isinstance(f, str)] if isinstance(fields, list) else []
    for role in profile.get("target_roles") or []:
        field = role_field(role, kn)
        if field not in out:
            out.append(field)
    return out or ["finance"]


def chosen_filters(profile: dict, field: str, kn) -> set[str]:
    """Filters picked within a board: tech specialties ('software.backend' -> backend),
    finance areas (a target's category)."""
    out = set()
    for role in profile.get("target_roles") or []:
        if role_field(role, kn) != field:
            continue
        if field == "finance":
            out.add(role.split(".")[0])
        elif "." in role:
            out.add(role.split(".", 1)[1])
    return out


def groups_for(field: str, profile: dict, kn, packs: Packs) -> set[str] | str:
    """The pack groups a board polls: '*' for all of them, EVERYTHING for every pack
    in every folder (boards without packs of their own, or unknown to the manifest)."""
    rule = packs.fields.get(field)
    if rule is None or rule.get("everything"):
        return EVERYTHING
    if rule.get("groups") == "*":
        return "*"
    groups = set(rule.get("core") or []) | set(rule.get("groups") or [])
    filters = rule.get("filters") or {}
    chosen = chosen_filters(profile, field, kn)
    # "All of Software" (the board itself as a target) keeps every filter's groups.
    narrowed = chosen and field not in (profile.get("target_roles") or [])
    for name in (chosen if narrowed else filters):
        groups |= set(filters.get(name) or [])
    return groups


def _takes(packs: Packs, field: str, groups: set[str] | str, pack: Pack) -> bool:
    return field in packs.folders.get(pack.folder, ()) and (groups == "*" or pack.group in groups)


def selected_packs(profile: dict, kn, packs: Packs | None = None) -> set[str]:
    packs = packs or load_packs()
    out: set[str] = set()
    for field in profile_fields(profile, kn):
        groups = groups_for(field, profile, kn, packs)
        if groups == EVERYTHING:
            return set(packs.packs)
        out |= {key for key, pack in packs.packs.items() if _takes(packs, field, groups, pack)}
    return out


def pack_boards(kn, packs: Packs | None = None) -> tuple[dict[str, list[str]], list[str]]:
    """Each pack's boards (those that poll it with every filter picked), and the boards that
    poll every pack, which the Sources view names once instead of on every row."""
    packs = packs or load_packs()
    out: dict[str, list[str]] = {key: [] for key in packs.packs}
    everywhere = []
    for field in packs.fields:
        groups = groups_for(field, {}, kn, packs)
        if groups == EVERYTHING:
            everywhere.append(field)
            continue
        for key, pack in packs.packs.items():
            if _takes(packs, field, groups, pack):
                out[key].append(field)
    return out, everywhere


def polled_sources(config: dict, profile: dict, kn, packs: Packs | None = None) -> dict:
    """Enabled sources whose pack the profile's boards select, plus sources in no pack."""
    packs = packs or load_packs()
    chosen = selected_packs(profile, kn, packs)
    return {name: cfg for name, cfg in enabled_sources(config).items()
            if (pack := packs.source_pack.get(name)) is None or pack in chosen}
