"""Record the live listings of some sources once, then replay them through two versions of
watcher.py, to show an adapter change leaves every existing source's listing as it was.

    python tools/replay_sources.py record <dir> --ats phenom,icims [--config <config.json>]
    python tools/replay_sources.py replay <dir> [--base main] [--ignore teaser]

record reads every enabled source of those ATSs (the repository's packs, or an install's
config.json) through the working tree's adapters, saving each HTTP response in order.
replay runs each source's adapter from <base> (git show <base>:watcher.py) and from the
working tree on the saved responses, and compares the postings (minus --ignore keys) and the
listing's completeness. A request the recording lacks fails that source.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import defaultdict, deque
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests  # noqa: E402

import watcher  # noqa: E402
from intel.sources import enabled_sources, load_config  # noqa: E402


def _key(method, url, kw):
    return json.dumps([method, url, kw.get("params"), kw.get("json"), kw.get("data")], sort_keys=True, default=str)


class Replayed:
    """Enough of requests.Response for the adapters. The body is kept as bytes, as requests reads
    JSON from them (its .text guesses an encoding when a JSON reply names no charset)."""

    def __init__(self, saved):
        self.status_code, self.text, self.url = saved["status"], saved["text"], saved["url"]
        self.content = base64.b64decode(saved["body"])
        self.headers = {"content-type": saved["ctype"]}

    def json(self):
        return json.loads(self.content)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} (recorded)", response=self)


def record(out: Path, ats: set[str], config_path: Path | None):
    config = load_config(config_path or ROOT / "config.json")
    sources = {k: v for k, v in enabled_sources(config).items() if v.get("ats") in ats}
    out.mkdir(parents=True, exist_ok=True)
    real = {"get": requests.get, "post": requests.post}
    for name, cfg in sorted(sources.items()):
        saved = []

        def recorder(method):
            def call(url, **kw):
                r = real[method](url, **kw)
                saved.append({"key": _key(method, url, kw), "status": r.status_code, "url": r.url,
                              "ctype": r.headers.get("content-type", ""), "text": r.text,
                              "body": base64.b64encode(r.content).decode("ascii")})
                return r
            return call

        with patch.object(watcher.requests, "get", recorder("get")), \
                patch.object(watcher.requests, "post", recorder("post")):
            try:
                jobs = watcher.ADAPTERS[cfg["ats"]](cfg)
                note = f"{len(jobs)} postings"
            except Exception as exc:        # recorded as it failed; replay expects the same failure
                note = f"failed: {type(exc).__name__}: {exc}"
        with gzip.open(out / f"{name}.json.gz", "wt", encoding="utf-8") as f:
            json.dump({"source": name, "cfg": cfg, "responses": saved}, f)
        print(f"{name:34} {cfg['ats']:8} {len(saved):4} responses, {note}", flush=True)


def _load(ref: str):
    code = subprocess.run(["git", "show", f"{ref}:watcher.py"], cwd=ROOT, capture_output=True, check=True).stdout
    path = Path(tempfile.mkdtemp()) / f"watcher_{ref.replace('/', '_')}.py"
    path.write_bytes(code)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module, saved, cfg):
    queues = defaultdict(deque)
    for r in saved:
        queues[r["key"]].append(r)

    def replay(method):
        def call(url, **kw):
            q = queues[_key(method, url, kw)]
            if not q:
                raise RuntimeError(f"not in the recording: {method.upper()} {url} {kw.get('params') or kw.get('json')}")
            return Replayed(q.popleft())
        return call

    with patch.object(module.requests, "get", replay("get")), patch.object(module.requests, "post", replay("post")):
        try:
            jobs = module.ADAPTERS[cfg["ats"]](cfg)
        except Exception as exc:
            return None, f"{type(exc).__name__}: {exc}"
    return jobs, None


def replay(src: Path, base: str, ignore: set[str]) -> int:
    old = _load(base)
    differ = 0
    for path in sorted(src.glob("*.json.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            data = json.load(f)
        name, cfg = data["source"], data["cfg"]
        before, err_b = _run(old, data["responses"], cfg)
        after, err_a = _run(watcher, data["responses"], cfg)
        if err_b or err_a:
            same = err_b == err_a
            print(f"{'same' if same else 'DIFFERENT':9} {name:34} {base}: {err_b or 'ok'} | tree: {err_a or 'ok'}")
            differ += not same
            continue
        strip = lambda jobs: [{k: v for k, v in j.items() if k not in ignore} for j in jobs]  # noqa: E731
        shape = lambda jobs: (getattr(jobs, "complete", None), getattr(jobs, "total", None))  # noqa: E731
        same = strip(before) == strip(after) and shape(before) == shape(after)
        added = _tree_only_keys(before, after)
        differ += not same
        print(f"{'same' if same else 'DIFFERENT':9} {name:34} {len(after):5} postings; complete={shape(after)[0]}; "
              f"keys only in the tree: {added or '-'}")
    print(f"{differ} source(s) differ beyond {sorted(ignore) or 'nothing'}")
    return differ


def _tree_only_keys(before, after):
    """How many postings carry each key (with its value) that only the tree's adapter sets."""
    out = defaultdict(int)
    for b, a in zip(before, after):
        for k in a.keys() - b.keys():
            out[f"{k}={a[k]!r}"] += 1
    return dict(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=["record", "replay"])
    ap.add_argument("dir", type=Path)
    ap.add_argument("--ats", default="")
    ap.add_argument("--config", type=Path)
    ap.add_argument("--base", default="main")
    ap.add_argument("--ignore", default="")
    args = ap.parse_args()
    if args.mode == "record":
        record(args.dir, set(filter(None, args.ats.split(","))), args.config)
    else:
        sys.exit(1 if replay(args.dir, args.base, set(filter(None, args.ignore.split(",")))) else 0)
