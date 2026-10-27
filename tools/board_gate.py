"""The board gate: proof that a change leaves every board's postings, fit and order as they were.

Snapshot one checkout's code on a copy of a database, then compare two snapshots:

    python -m tools.board_gate snapshot --code <checkout> --db <copy.db> --config <config.json>
        --epoch <unix time> --out <snapshot.db> [--work <working copy>] [--workers 10]
    python -m tools.board_gate compare <old snapshot> <new snapshot> [--expect <profile> ...]

snapshot never writes the database it is given. It copies it to --work, runs that checkout's
db_migrations on the copy as the app does on open, freezes the clock at --epoch, computes facts in
worker processes with the checkout's build_facts and feeds them to its real IntelStore.facts_pass,
re-picks canonical rows everywhere and scores every sample profile with the real score_pass, resume
matching included. Each step runs in a subprocess on the checkout's own modules, so `main` exported
with `git archive` and this tree are run the same way.

compare lists each sample profile's board view as Opportunities shows it by default (canonical,
titled, not closed, not hidden, on the profile's boards, by fit then posting date) and reports
postings missing or added and any change of fit, order, category, filter, cluster, company, type,
fit detail or resume match. Postings whose only change is a known employer in place of an
unclassified one are listed apart as label changes. It exits 1 when a profile not named by --expect
changed.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pickle
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

# Onboarding's first-run skill groups (web/js/fields.js at v0.3.11). Kept fixed, so both sides
# of a comparison score the same profiles.
FIRST_RUN_SKILLS = {
    "finance": ["modeling", "accounting", "tools", "programming", "markets", "quant", "soft"],
    "software": ["programming", "web", "cloud", "data", "cs", "soft"],
    "data_ml": ["programming", "data", "ml", "quant", "tools", "cs", "soft"],
    "hardware": ["programming", "hardware", "cs", "soft"],
    "product": ["tools", "programming", "soft"],
    "design": ["tools", "soft"],
    "sales": ["tools", "soft"],
    "operations": ["tools", "soft"],
    "people_legal": ["soft"],
    "healthcare": ["quant", "tools", "soft"],
}
BOARDS = ["software", "data_ml", "hardware", "product", "design", "sales", "operations", "people_legal", "healthcare"]
MIXES = (["finance", "healthcare"], ["software", "healthcare"], ["data_ml", "healthcare"],
         ["finance", "software"], ["finance", "sales"])
VIEW = ("fit", "category", "subcategory", "cluster_key", "company_key", "company_name", "company_type",
        "detail_hash", "matched", "match_hash", "window_status", "urgency", "badges")
LABEL = {"company_name", "company_type", "detail_hash"}


def first_run(fields: list[str], default: dict, skill_group: dict) -> dict:
    """setupProfile() on a first run: the default's finance areas when Finance is picked, each other
    board whole; without Finance, no employer types and only the default skills in the boards' groups."""
    out = {"fields": list(fields),
           "target_roles": (list(default["target_roles"]) if "finance" in fields else [])
           + [f for f in fields if f != "finance"]}
    if "finance" not in fields:
        groups = {g for f in fields for g in FIRST_RUN_SKILLS.get(f, ["soft"])}
        out["target_company_types"] = []
        out["skills"] = [s for s in default["skills"] if skill_group.get(s) in groups]
    return out


def sample_profiles(default: dict, skill_group: dict) -> dict:
    """name -> stored-profile layer: a fresh install, each board, mixed boards, and None for the saved profile."""
    out = {"default": {}, "finance": first_run(["finance"], default, skill_group)}
    for board in BOARDS:
        out[board] = first_run([board], default, skill_group)
    for mix in MIXES:
        out["+".join(mix)] = first_run(mix, default, skill_group)
    out["user"] = None
    return copy.deepcopy(out)


def _ro(path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{Path(path).resolve().as_posix()}?mode=ro", uri=True)


def _context(cfg, section) -> str:
    return hashlib.sha1((json.dumps(cfg or {}, sort_keys=True) + "\x1f" + (section or "")).encode()).hexdigest()[:16]


# ------------------------------------------------------------ inside a checkout (subprocesses)
def _checkout(code: str, epoch: float):
    """Import the checkout's app modules with the clock frozen at ``epoch``."""
    import datetime as dt

    class FrozenDateTime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls.fromtimestamp(epoch, tz)

        @classmethod
        def utcnow(cls):
            return cls.fromtimestamp(epoch, dt.timezone.utc).replace(tzinfo=None)

        @classmethod
        def today(cls):
            return cls.fromtimestamp(epoch)

    class FrozenDate(dt.date):
        @classmethod
        def today(cls):
            return cls.fromtimestamp(epoch)

    sys.path[0] = str(Path(code).resolve())
    time.time = lambda: epoch
    import intel_store
    import intel.profile  # noqa: F401  (imported here so its clock is frozen too)
    for name, module in list(sys.modules.items()):
        if name in ("intel_store", "job_query", "job_intelligence", "watcher", "dashboard") or name.startswith("intel."):
            if getattr(module, "datetime", None) is dt.datetime:
                module.datetime = FrozenDateTime
            if getattr(module, "date", None) is dt.date:
                module.date = FrozenDate
    return intel_store


def _facts_worker(code, work, config_path, epoch, shard, shards, out) -> None:
    store = _checkout(code, float(epoch))
    from intel.knowledge import load_knowledge
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    boards = {k: v for k, v in (config.get("boards") or {}).items() if not k.startswith("_")}
    sections, kn = store.board_sections(config), load_knowledge()
    src, dst = _ro(work), sqlite3.connect(out)
    dst.execute("CREATE TABLE IF NOT EXISTS f (board TEXT, job_id TEXT, p BLOB, ctx TEXT, PRIMARY KEY (board, job_id))")
    # Since schema 7 facts read the description and any community-list note together.
    notes = hasattr(store, "facts_description")
    rows = src.execute(f"""
        SELECT j.board, j.job_id, j.title, j.location, j.url, j.first_seen,
               COALESCE(d.company, REPLACE(j.board,'_',' ')), COALESCE(d.salary,''), d.posted,
               CAST(COALESCE(t.description,'') AS BLOB), COALESCE(t.department,''),
               {"COALESCE(n.note,'')" if notes else "''"}
        FROM jobs j
        LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
        LEFT JOIN job_text t ON t.board=j.board AND t.job_id=j.job_id
        {"LEFT JOIN job_notes n ON n.board=j.board AND n.job_id=j.job_id" if notes else ""}
        WHERE j.title != '' AND (j.rowid % ?) = ?""", (int(shards), int(shard)))
    batch = []
    for board, job_id, title, location, url, first_seen, company, salary, posted, description, department, note in rows:
        text = bytes(description).decode("utf-8", "replace")
        job = {"board": board, "id": job_id, "title": title, "location": location, "url": url,
               "company": company, "salary": salary, "posted": posted,
               "description": store.facts_description(text, note) if notes else text, "department": department}
        cfg, section = boards.get(board, {}), sections.get(board, "")
        batch.append((board, job_id, pickle.dumps(store.build_facts(job, kn, cfg, section), protocol=4),
                      _context(cfg, section)))
        if len(batch) >= 500:
            dst.executemany("INSERT INTO f VALUES (?,?,?,?)", batch)
            dst.commit()
            batch = []
    dst.executemany("INSERT INTO f VALUES (?,?,?,?)", batch)
    dst.commit()


def _store_run(code, work, facts_db, config_path, epoch, out) -> None:
    store_module = _checkout(code, float(epoch))
    from intel.profile import DEFAULT_PROFILE, merge_profile
    from intel.sources import profile_fields
    facts = _ro(facts_db)

    def precomputed(job, kn, board_cfg=None, section=""):
        row = facts.execute("SELECT p, ctx FROM f WHERE board=? AND job_id=?", (job["board"], job["id"])).fetchone()
        if row is None:
            raise KeyError(f"no precomputed facts for {job['board']}:{job['id']}")
        if row[1] != _context(board_cfg, section):
            raise ValueError(f"{job['board']}:{job['id']}: facts were computed with other source settings")
        return pickle.loads(row[0])

    store_module.build_facts = precomputed
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    con = sqlite3.connect(work, timeout=60)
    con.execute("UPDATE job_intel SET input_hash=NULL")
    con.execute("DELETE FROM kv WHERE k='canonical_ranks'")
    con.commit()
    store = store_module.IntelStore(con, config)
    store.recluster_if_ranks_changed()
    store.facts_pass()
    con.commit()
    # Re-pick canonical members everywhere after the new facts, as an upgrade does.
    con.execute("DELETE FROM kv WHERE k='canonical_ranks'")
    store.recluster_if_ranks_changed()
    con.commit()

    res = sqlite3.connect(out)
    res.executescript("""
        DROP TABLE IF EXISTS meta; DROP TABLE IF EXISTS facts; DROP TABLE IF EXISTS scores;
        CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
        CREATE TABLE facts (board TEXT, job_id TEXT, title TEXT, is_canonical INT, is_finance INT, family TEXT,
          category TEXT, subcategory TEXT, company_key TEXT, company_name TEXT, company_type TEXT, cluster_key TEXT,
          city TEXT, country TEXT, stage TEXT, level TEXT, cycle TEXT, skills TEXT, status TEXT, hidden INT,
          facts_hash TEXT, PRIMARY KEY (board, job_id));
        CREATE TABLE scores (profile TEXT, board TEXT, job_id TEXT, fit REAL, urgency REAL, window_status TEXT,
          badges TEXT, deadline TEXT, posted_ref REAL, detail_hash TEXT, matched INT, match_hash TEXT,
          PRIMARY KEY (profile, board, job_id));""")
    res.executemany("INSERT INTO meta VALUES (?,?)", [("code", str(code)), ("epoch", str(epoch)),
                                                      ("kb_version", store.kb_version)])
    rows = con.execute("""
        SELECT i.board, i.job_id, j.title, i.is_canonical, i.is_finance, i.family, i.category, i.subcategory,
               i.company_key, i.company_name, i.company_type, i.cluster_key, i.city, i.country, i.stage, i.level,
               i.cycle, i.skills, COALESCE(s.status,'active'),
               EXISTS (SELECT 1 FROM job_overrides o WHERE o.job_key=(i.board||':'||i.job_id) AND o.hidden=1),
               i.facts
        FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
        LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id""")
    res.executemany("INSERT INTO facts VALUES (" + ",".join("?" * 21) + ")",
                    ((*r[:20], hashlib.sha1((r[20] or "").encode()).hexdigest()[:16]) for r in rows))
    res.commit()

    skill_group = {s.key: s.group for s in store.kn.skills}
    for name, layer in sample_profiles(DEFAULT_PROFILE, skill_group).items():
        profile = None if layer is None else merge_profile(config.get("profile"), layer)
        scored = store_module.IntelStore(con, config) if profile is None else \
            store_module.IntelStore(con, config, profile=profile)
        # Every profile reads the stored resume, if any, as its own.
        con.execute("UPDATE candidate_resume SET version=? WHERE id=1", (scored.version,))
        con.commit()
        scored.score_pass(force=True, commit_batches=True)
        con.commit()
        res.executemany("INSERT INTO scores VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (
            (name, b, j, fit, urgency, window, badges, deadline, posted,
             hashlib.sha1((detail or "").encode()).hexdigest()[:16], matched,
             hashlib.sha1(match.encode()).hexdigest()[:16] if match else None)
            for b, j, fit, urgency, window, badges, deadline, posted, detail, matched, match in con.execute("""
                SELECT i.board, i.job_id, i.fit, i.urgency, i.window_status, i.badges, i.eff_deadline,
                       i.posted_ref, i.fit_detail, rm.matched, rm.detail
                FROM job_intel i LEFT JOIN resume_matches rm ON rm.board=i.board AND rm.job_id=i.job_id
                     AND rm.profile_version=i.profile_version""")))
        res.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [
            (f"profile:{name}", json.dumps(scored.profile, sort_keys=True)),
            (f"boards:{name}", json.dumps(profile_fields(scored.profile, store.kn)))])
        res.commit()
    con.close()


# ------------------------------------------------------------ snapshot
def _run(*args) -> None:
    subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), *map(str, args)], check=True)


def snapshot(code, db, config, epoch, out, work=None, workers=10, log=lambda line: print(line, flush=True)) -> None:
    code, out = Path(code).resolve(), Path(out).resolve()
    work = Path(work).resolve() if work else out.with_name(out.stem + ".work.db")
    if work.exists():
        raise SystemExit(f"{work} exists: a snapshot runs on a fresh working copy")
    t0 = time.monotonic()
    source, copy_ = _ro(db), sqlite3.connect(work)
    source.backup(copy_)
    source.close()
    copy_.close()
    _run("_migrate", code, work)
    log(f"[{time.monotonic() - t0:5.0f}s] working copy {work} migrated by {code}")
    shards = [work.with_name(f"{work.stem}.facts{i}.db") for i in range(workers)]
    procs = [subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "_facts", str(code), str(work),
                               str(config), str(epoch), str(i), str(workers), str(shard)])
             for i, shard in enumerate(shards)]
    if any(p.wait() for p in procs):
        raise SystemExit("a facts worker failed")
    facts = work.with_name(f"{work.stem}.facts.db")
    merged = sqlite3.connect(facts)
    merged.execute("CREATE TABLE f (board TEXT, job_id TEXT, p BLOB, ctx TEXT, PRIMARY KEY (board, job_id))")
    for shard in shards:
        merged.execute("ATTACH DATABASE ? AS s", (str(shard),))
        merged.execute("INSERT INTO f SELECT * FROM s.f")
        merged.commit()
        merged.execute("DETACH DATABASE s")
        shard.unlink()
    merged.close()
    log(f"[{time.monotonic() - t0:5.0f}s] facts computed by {workers} workers")
    _run("_store", code, work, facts, config, epoch, out)
    log(f"[{time.monotonic() - t0:5.0f}s] snapshot written to {out}")


def _migrate(code, work) -> None:
    sys.path[0] = str(Path(code).resolve())
    import db_migrations
    con = sqlite3.connect(work)
    db_migrations.migrate(con)
    con.close()


# ------------------------------------------------------------ compare
def board_views(path) -> dict:
    """Each profile's boards and its board view: {(board, job_id): columns} plus their order."""
    con = _ro(path)
    boards = {k.split(":", 1)[1]: json.loads(v) for k, v in con.execute("SELECT k, v FROM meta WHERE k LIKE 'boards:%'")}
    out = {}
    for name, fields in boards.items():
        rows = con.execute("""
            SELECT f.board, f.job_id, s.posted_ref, f.is_finance, f.family, s.fit, f.category, f.subcategory,
                   f.cluster_key, f.company_key, f.company_name, f.company_type, s.detail_hash, s.matched,
                   s.match_hash, s.window_status, s.urgency, s.badges
            FROM facts f JOIN scores s ON s.board=f.board AND s.job_id=f.job_id AND s.profile=?
            WHERE f.title != '' AND f.is_canonical=1 AND f.status != 'closed'
              AND COALESCE(s.window_status,'') != 'closed' AND f.hidden=0""", (name,)).fetchall()
        rows = [r for r in rows if ("finance" in fields if r[3] else r[4] in fields)]
        rows.sort(key=lambda r: (-(r[5] or 0), -(r[2] or 0), r[0], r[1]))
        out[name] = {"boards": fields, "order": [(r[0], r[1]) for r in rows],
                     "rows": {(r[0], r[1]): dict(zip(VIEW, r[5:])) for r in rows}}
    facts = {(r[0], r[1]): r[2:] for r in con.execute("SELECT board, job_id, facts_hash, is_finance, family FROM facts")}
    con.close()
    return {"profiles": out, "facts": facts}


def digest(view: dict) -> str:
    return hashlib.sha256(json.dumps([[*key, *(view["rows"][key][c] for c in VIEW)] for key in view["order"]],
                                     default=str).encode()).hexdigest()[:16]


def differences(old: dict, new: dict) -> dict:
    """Per profile: postings missing and added, changed columns (label-only changes apart), and order."""
    out = {}
    for name, a in old["profiles"].items():
        b = new["profiles"].get(name)
        if b is None:
            out[name] = {"missing_profile": True}
            continue
        changed, labels = {}, []
        for key, row in a["rows"].items():
            other = b["rows"].get(key)
            if other is None:
                continue
            cols = {c for c in VIEW if row[c] != other[c]}
            if cols and cols <= LABEL and row["company_type"] == "unknown" != other["company_type"]:
                labels.append(key)
            for c in cols - (LABEL if key in labels else set()):
                changed.setdefault(c, []).append(key)
        out[name] = {"missing": [k for k in a["order"] if k not in b["rows"]],
                     "added": [k for k in b["order"] if k not in a["rows"]],
                     "changed": changed, "labels": labels,
                     "order": [k for k in a["order"] if k in b["rows"]] == [k for k in b["order"] if k in a["rows"]]}
    return out


def compare(old_path, new_path, expect=(), out=print) -> int:
    old, new = board_views(old_path), board_views(new_path)
    out(f"{'profile':22} {'boards':24} {'postings':>17} {'fit>=55':>8} {'matched':>8}  digest")
    for name, b in new["profiles"].items():
        a = old["profiles"].get(name, {"order": [], "rows": {}})
        fits = sum((b["rows"][k]["fit"] or 0) >= 55 for k in b["order"])
        matched = sum(bool(b["rows"][k]["matched"]) for k in b["order"])
        same = "=" if a["order"] and digest(a) == digest(b) else digest(b)
        out(f"{name:22} {','.join(b['boards']):24} {len(a['order']):8} -> {len(b['order']):5} {fits:8} {matched:8}  {same}")
    moved = [k for k in old["facts"] if k in new["facts"] and old["facts"][k][1:] != new["facts"][k][1:]]
    refacted = sum(1 for k in old["facts"] if k in new["facts"] and old["facts"][k][0] != new["facts"][k][0])
    out(f"postings: {len(old['facts'])} -> {len(new['facts'])}; facts differ for {refacted}; "
        f"{len(moved)} change board")
    for key in moved[:20]:
        a, b = old["facts"][key][1:], new["facts"][key][1:]
        out(f"    {key[0]}:{key[1]}  {'finance' if a[0] else a[1]} -> {'finance' if b[0] else b[1]}")
    failed = False
    for name, d in differences(old, new).items():
        if d.get("missing_profile"):
            out(f"  {name}: missing from {new_path}")
            failed = True
            continue
        if not (d["missing"] or d["added"] or d["changed"] or not d["order"] or d["labels"]):
            continue
        real = bool(d["missing"] or d["added"] or d["changed"] or not d["order"])
        failed |= real and name not in expect
        out(f"  {name}{' (expected)' if name in expect else ''}: missing {len(d['missing'])}, added {len(d['added'])}, "
            f"changed {({c: len(v) for c, v in d['changed'].items()}) or 0}, same order {d['order']}, "
            f"label changes {len(d['labels'])}")
        for sign, keys in (("-", d["missing"]), ("+", d["added"]), ("~", [k for v in d["changed"].values() for k in v])):
            for key in list(dict.fromkeys(keys))[:10]:
                out(f"      {sign} {key[0]}:{key[1]}")
    out("gate: " + ("FAILED" if failed else "passed"))
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.board_gate", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    snap = sub.add_parser("snapshot", help="run one checkout on a copy of a database")
    snap.add_argument("--code", required=True, help="the checkout to run (this tree, or `git archive` of main)")
    snap.add_argument("--db", required=True, help="a copy of the database; it is read, never written")
    snap.add_argument("--config", required=True, help="the install's config.json")
    snap.add_argument("--epoch", required=True, type=float, help="the frozen clock, in Unix seconds")
    snap.add_argument("--out", required=True)
    snap.add_argument("--work", help="the working copy (default: beside --out)")
    snap.add_argument("--workers", type=int, default=min(10, os.cpu_count() or 1))
    cmp = sub.add_parser("compare", help="compare two snapshots' board views")
    cmp.add_argument("old")
    cmp.add_argument("new")
    cmp.add_argument("--expect", action="append", default=[], help="a profile allowed to change")
    for private in ("_migrate", "_facts", "_store"):
        sub.add_parser(private).add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        snapshot(args.code, args.db, args.config, args.epoch, args.out, args.work, args.workers)
        return 0
    if args.command == "compare":
        return compare(args.old, args.new, args.expect)
    {"_migrate": _migrate, "_facts": _facts_worker, "_store": _store_run}[args.command](*args.args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
