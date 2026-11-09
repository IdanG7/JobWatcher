"""Poll time per sample profile: time each source once with the app's reader, then replay each profile's poll.

    python -m tools.poll_time time --config config.json --out timings.jsonl [--only a,b] [--workers 10]
    python -m tools.poll_time simulate --before <checkout> --after <checkout> --timings timings.jsonl [--workers 10]

time: fetches every enabled source of the config once with watcher.fetch_board, as a poll does (no database, no
  alert, no first-poll seed), on `workers` threads. The sources of an ATS whose requests take turns (LinkedIn,
  Lever, Eightfold) run one after another on a thread of their own, so no source waits for another's requests;
  a time includes the spacing between its own requests. One JSON line per source: seconds, postings, complete,
  reason, error. Names already in the file are not fetched again, so an interrupted run carries on.
simulate: each sample profile's full poll (every source due) as watcher.cycle runs it: the polled sources in poll
  order, each taken by the next free thread of `workers`; a source of a lock group starts once the group's
  previous source has finished, and holds its thread while it waits. "everything" is the GitHub Actions runner,
  which polls every source.
  - LinkedIn holds its lock through each request (_linkedin_get), so its sources' requests run one at a time and
    LinkedIn's time is the sum of its sources' times.
  - Lever and Eightfold only space the starts of their requests (_lever_get, _eightfold_get: 1 s and 1.5 s) and
    let them run together. Serialising their sources is an upper bound, close when a request returns within its
    spacing; `poll_low` lets them run freely, a lower bound.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LOCKED = ("linkedin", "lever", "eightfold")     # watcher's _linkedin_lock, _lever_lock, _eightfold_lock


def replay(order, seconds, group, workers=10) -> float:
    """The length of a poll that submits `order` to `workers` threads, as ThreadPoolExecutor hands them out."""
    free = [0.0] * workers
    group_free: dict[str, float] = {}
    end = 0.0
    for name in order:
        i = min(range(workers), key=free.__getitem__)
        start = free[i]
        if g := group.get(name):
            start = max(start, group_free.get(g, 0.0))
        free[i] = finish = start + seconds[name]
        if g:
            group_free[g] = finish
        end = max(end, finish)
    return end


def read_timings(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["name"]] = row
    return out


def time_sources(sources: dict, out, workers=10, fetch=None) -> None:
    """Fetch each source once and append its timing to `out` (JSON lines)."""
    if fetch is None:
        import watcher
        fetch = watcher.fetch_board
    done = read_timings(out)
    todo = {n: c for n, c in sources.items() if n not in done}
    write = threading.Lock()

    def one(name, cfg):
        t0 = time.perf_counter()
        row = {"name": name, "ats": cfg.get("ats"), "count": None, "complete": None, "reason": "", "error": ""}
        try:
            _, jobs = fetch(name, cfg)
            row.update(count=len(jobs), complete=getattr(jobs, "complete", None), reason=getattr(jobs, "reason", ""))
        except Exception as e:      # a refusal is a result: its time counts, and the report names it
            row["error"] = f"{type(e).__name__}: {str(e)[:200]}"
        row["seconds"] = round(time.perf_counter() - t0, 2)
        with write, open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(f"{row['seconds']:8.1f}s {name} {row['count']} {row['error']}", flush=True)

    def chain(names):
        for n in names:
            one(n, todo[n])

    locked = {ats: [n for n, c in todo.items() if c.get("ats") == ats] for ats in LOCKED}
    rest = [n for n in todo if todo[n].get("ats") not in LOCKED]
    with ThreadPoolExecutor(max_workers=workers + len(LOCKED)) as ex:
        futures = [ex.submit(chain, names) for names in locked.values() if names]
        futures += [ex.submit(one, n, todo[n]) for n in rest]
        for f in futures:
            f.result()


def _load_gate():
    spec = importlib.util.spec_from_file_location("_board_gate", Path(__file__).with_name("board_gate.py"))
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def _orders(code, out) -> None:
    """Each sample profile's polled sources in poll order, with `code`'s packs, selection and config."""
    gate = _load_gate()         # this checkout's sample profiles, as board_gate's polled lists use them
    sys.path[0] = str(Path(code).resolve())
    from intel.knowledge import load_knowledge
    from intel.profile import DEFAULT_PROFILE, merge_profile
    from intel.sources import enabled_sources, load_config, load_packs, polled_sources
    kn, packs, config = load_knowledge(), load_packs(), load_config(Path(code) / "config.json")
    orders = {"everything": {n: c.get("ats") for n, c in enabled_sources(config).items()}}
    for name, layer in gate.sample_profiles(DEFAULT_PROFILE, {s.key: s.group for s in kn.skills}).items():
        if layer is not None:   # None is the saved profile: the user's own, not a sample
            profile = merge_profile(config.get("profile"), layer)
            orders[name] = {n: c.get("ats") for n, c in polled_sources(config, profile, kn, packs).items()}
    Path(out).write_text(json.dumps(orders), encoding="utf-8")


def orders(code) -> dict:
    fd, name = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    out = Path(name)
    try:
        subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "_orders", str(code), str(out)],
                       check=True)
        return json.loads(out.read_text(encoding="utf-8"))
    finally:
        out.unlink(missing_ok=True)


def profile_times(order: dict, timings: dict, workers=10) -> dict:
    """One profile's poll (both bounds), each lock group's total, and the sources with no timing or a failed read."""
    timed = [n for n in order if n in timings]
    seconds = {n: timings[n]["seconds"] for n in timed}
    group = {n: order[n] for n in timed if order[n] in LOCKED}
    linkedin = {n: g for n, g in group.items() if g == "linkedin"}
    return {"sources": len(order), "poll": replay(timed, seconds, group, workers),
            "poll_low": replay(timed, seconds, linkedin, workers),
            **{ats: sum(seconds[n] for n, g in group.items() if g == ats) for ats in LOCKED},
            "eightfold_sources": sorted(n for n, g in group.items() if g == "eightfold"),
            "untimed": sorted(set(order) - set(timed)),
            "failed": sorted(n for n in timed if timings[n]["error"])}


def simulate(before, after, timings_path, workers=10, out=print) -> dict:
    timings = read_timings(timings_path)
    old, new = orders(before), orders(after)
    report = {}
    out(f"{'profile':24s} {'sources':>15s} {'poll, min (low)':>27s} {'LinkedIn min':>15s} {'Eightfold min':>15s}")
    for name in new:
        a, b = (profile_times(o.get(name, {}), timings, workers) for o in (old, new))
        report[name] = {"before": a, "after": b}
        poll = lambda r: f"{r['poll'] / 60:5.1f} ({r['poll_low'] / 60:5.1f})"
        out(f"{name:24s} {a['sources']:6d} -> {b['sources']:6d} {poll(a)} -> {poll(b)}"
            f" {a['linkedin'] / 60:6.1f} -> {b['linkedin'] / 60:6.1f} {a['eightfold'] / 60:6.1f} -> {b['eightfold'] / 60:6.1f}")
    untimed = sorted({n for r in report.values() for side in r.values() for n in side["untimed"]})
    failed = sorted({n for r in report.values() for side in r.values() for n in side["failed"]})
    out(f"untimed: {len(untimed)} {untimed[:20]}")
    out(f"failed reads: {len(failed)} {failed}")
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("time", help="fetch each source once and record its time")
    t.add_argument("--config", required=True, help="a config.json: the checkout's, or an install's")
    t.add_argument("--out", required=True)
    t.add_argument("--only", help="comma-separated source names")
    t.add_argument("--workers", type=int, default=10)
    s = sub.add_parser("simulate", help="replay each sample profile's poll, before and after")
    s.add_argument("--before", required=True, help="a checkout")
    s.add_argument("--after", required=True, help="a checkout")
    s.add_argument("--timings", required=True)
    s.add_argument("--workers", type=int, default=10)
    s.add_argument("--json", help="write the report here")
    sub.add_parser("_orders").add_argument("args", nargs=2)
    args = parser.parse_args(argv)
    if args.command == "_orders":
        _orders(*args.args)
    elif args.command == "time":
        from intel.sources import enabled_sources, load_config
        sources = enabled_sources(load_config(args.config))
        if args.only:
            sources = {n: sources[n] for n in args.only.split(",")}
        time_sources(sources, args.out, args.workers)
    else:
        report = simulate(args.before, args.after, args.timings, args.workers)
        if args.json:
            Path(args.json).write_text(json.dumps(report, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
