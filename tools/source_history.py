"""Every source setting value Jobwatch has shipped, so upgrades can tell a
recipient's own edits apart from older defaults.

config/source_defaults_history.json maps board -> key -> [values ever shipped];
MISSING marks a release where the key was absent. Two bookkeeping entries:

    "__since__":   board -> the sources_version that first shipped it, so a
                   board newer than a recipient's config is added on upgrade
                   (an older one missing from it was deleted by them)
                   and one the bundle stops shipping is removed; a board
                   shipped again after a release without it counts from then
    "__shipped__": the sources_version, a hash and the names of the boards last
                   built, so a build fails when defaults change without a
                   version bump

tools/build_windows.py records each release here before bundling.

    python tools/source_history.py v0.1.0 v0.1.1 ...   # rebuild from git tags
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "config" / "source_defaults_history.json"
MISSING = "__missing__"


def boards_hash(boards: dict) -> str:
    return hashlib.sha256(json.dumps(boards, sort_keys=True).encode()).hexdigest()[:16]


def merge_history(history: dict, boards: dict, version: int = 1) -> dict:
    since = history.setdefault("__since__", {})
    for name, board in boards.items():
        if not isinstance(board, dict) or name.startswith("_"):
            continue
        since.setdefault(name, version)
        earlier = name in history          # a key new to a recorded board was missing before
        known = history.setdefault(name, {})
        for key in known.keys() | board.keys():
            values = known.setdefault(key, [MISSING] if earlier else [])
            value = board.get(key, MISSING)
            if value not in values:
                values.append(value)
    return history


def ship(history: dict, boards: dict, version: int) -> dict:
    """merge_history, then record these boards as the last release's."""
    shipped = history.get("__shipped__") or {}
    if version > shipped.get("version", version) and "names" in shipped:
        # A board the last release dropped is new again: installs that lost it get it back
        # (sources_version 10 brings back tech employers 0.3.0 added and 0.3.2 removed).
        since = history.setdefault("__since__", {})
        for name in set(boards) & set(since) - set(shipped["names"]):
            since[name] = version
    merge_history(history, boards, version)
    history["__shipped__"] = {"version": version, "hash": boards_hash(boards), "names": sorted(boards)}
    return history


def record_release(history: dict, boards: dict, version: int) -> dict:
    """ship() for a build; refuses changed defaults under an old version."""
    shipped = history.get("__shipped__") or {}
    if shipped and shipped.get("hash") != boards_hash(boards) and version <= shipped.get("version", 0):
        raise SystemExit(f"Source defaults changed since sources_version {shipped['version']} was built; "
                         "raise sources_version in tools/build_windows.py so installs pick them up.")
    return ship(history, boards, version)


def load_history(path: Path = HISTORY) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_history(history: dict, path: Path = HISTORY) -> None:
    path.write_text(json.dumps(history, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _tag_config(tag: str) -> dict:
    """config.json at a tag, with its sources assembled from config/sources when it lists none."""
    from intel.sources import Packs

    def show(path: str) -> str:
        return subprocess.check_output(["git", "show", f"{tag}:{path}"], cwd=ROOT, text=True, encoding="utf-8")

    config = json.loads(show("config.json"))
    if "boards" not in config:
        files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", tag, "config/sources"], cwd=ROOT,
                                        text=True, encoding="utf-8").split()
        packs = {path[len("config/sources/"):-len(".json")]: json.loads(show(path))
                 for path in files if path.count("/") == 3 and path.endswith(".json")}
        config["boards"] = Packs(json.loads(show("config/sources/manifest.json")), packs).flat()
    return config


def _tag_version(tag: str) -> int:
    """sources_version a release shipped; releases before it existed count as 1."""
    text = subprocess.check_output(["git", "show", f"{tag}:tools/build_windows.py"], cwd=ROOT,
                                   text=True, encoding="utf-8")
    found = re.search(r'"sources_version":\s*(\d+)', text)
    return int(found.group(1)) if found else 1


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from build_windows import clean_config

    history = merge_history({}, json.loads((ROOT / "config/source_defaults_v1.json").read_text(encoding="utf-8"))["boards"], 1)
    for tag in sys.argv[1:]:
        ship(history, clean_config(_tag_config(tag))["boards"], _tag_version(tag))
    save_history(history)
    print(f"{len(history) - 2} boards recorded in {HISTORY.relative_to(ROOT)}")
