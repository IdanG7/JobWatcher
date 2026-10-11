"""Every source setting value Jobwatch has shipped, so upgrades can tell a
recipient's own edits apart from older defaults.

config/source_defaults_history.json maps board -> key -> [values ever shipped];
MISSING marks a release where the key was absent. tools/build_windows.py
merges the current config into it on every build, so each release records
its defaults before the next one compares against them.

    python tools/source_history.py v0.1.5 v0.1.6 ...   # rebuild from git tags
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "config" / "source_defaults_history.json"
MISSING = "__missing__"


def merge_history(history: dict, boards: dict) -> dict:
    for name, board in boards.items():
        if not isinstance(board, dict) or name.startswith("_"):
            continue
        earlier = name in history          # a key new to a recorded board was missing before
        known = history.setdefault(name, {})
        for key in known.keys() | board.keys():
            values = known.setdefault(key, [MISSING] if earlier else [])
            value = board.get(key, MISSING)
            if value not in values:
                values.append(value)
    return history


def load_history(path: Path = HISTORY) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save_history(history: dict, path: Path = HISTORY) -> None:
    path.write_text(json.dumps(history, indent=1, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "tools"))
    from build_windows import clean_config

    history = merge_history({}, json.loads((ROOT / "config/source_defaults_v1.json").read_text(encoding="utf-8"))["boards"])
    for tag in sys.argv[1:]:
        text = subprocess.check_output(["git", "show", f"{tag}:config.json"], cwd=ROOT, text=True, encoding="utf-8")
        merge_history(history, clean_config(json.loads(text))["boards"])
    save_history(history)
    print(f"{len(history)} boards recorded in {HISTORY.relative_to(ROOT)}")
