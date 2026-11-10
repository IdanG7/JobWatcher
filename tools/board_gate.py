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

The placement check is the quick proof, in minutes, that a board's work leaves every other board's
postings where they were: on the same board, filter, company, employer type and location. Fit and order
are the gate's.

    python -m tools.board_gate sample --db <copy.db> --out <ids.json> [--cap 50] [--seed 0]
        [--words <checkout> ... --board <board> ...] [--title <word> ...] [--title-file <words.json>]
    python -m tools.board_gate place --code <checkout> --db <copy.db> --config <config.json>
        --ids <ids.json> --out <placed.db> [--workers 6]
    python -m tools.board_gate place --stored --db <copy.db> --ids <ids.json> --out <placed.db>
    python -m tools.board_gate place-compare <old placed.db> <new placed.db> [--board <board> ...]
        [--allow <from>:<to> ...] [--samples 8] [--json <changes.json>]

sample picks the postings: up to --cap from every source at random, and every posting whose title
matches a --title regex or the title words of a --board in a --words checkout (main's and the branch's,
so titles that leave a board are picked too). place runs the checkout's db_migrations on the copy it is
given, as the app does on open, computes those postings' facts with the checkout's build_facts and
records where each lands; with --stored it records where the app stored them instead. place-compare
reports postings missing or added, moves between boards (allowed only by --allow; a move from or to Finance
or "other", which Finance profiles review, changes what Finance shows, so it is marked and * never stands
for either), filter changes on the --board boards, label changes (a known employer type in place of unknown,
same company key) with counts per board and type, and every other change of filter, company, employer type
or location (every country and city counts). It exits 1 on any change not allowed. Career-stage changes off
the --board boards are listed too, without blocking. Each placement and id list is written to a new file;
place needs an install's config.json (one that lists its sources).
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import pickle
import random
import re
import sqlite3
import subprocess
import sys
import time
from collections import Counter
from contextlib import closing, suppress
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
    "aec": ["aec_design", "aec_analysis", "aec_delivery", "tools", "soft"],
}
BOARDS = ["software", "data_ml", "hardware", "product", "design", "sales", "operations", "people_legal", "healthcare", "aec"]
MIXES = (["finance", "healthcare"], ["software", "healthcare"], ["data_ml", "healthcare"],
         ["finance", "software"], ["finance", "sales"], ["finance", "product"], ["software", "product"],
         ["software", "design"], ["product", "design"], ["finance", "aec"], ["software", "aec"])
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
def _checkout(code: str, epoch: float, *also: str):
    """Import the checkout's app modules, and the modules named in ``also``, with the clock frozen at ``epoch``."""
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
    for name in also:
        __import__(name)
    for name, module in list(sys.modules.items()):
        if name in ("intel_store", "job_query", "job_intelligence", "watcher", "dashboard") or name.startswith("intel."):
            if getattr(module, "datetime", None) is dt.datetime:
                module.datetime = FrozenDateTime
            if getattr(module, "date", None) is dt.date:
                module.date = FrozenDate
    return intel_store


def _facts_worker(code, work, config_path, epoch, shard, shards, out, ids="") -> None:
    store = _checkout(code, float(epoch))
    from intel.knowledge import load_knowledge
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    boards = {k: v for k, v in (config.get("boards") or {}).items() if not k.startswith("_")}
    sections, kn = store.board_sections(config), load_knowledge()
    src, dst = _ro(work), sqlite3.connect(out)
    dst.execute("CREATE TABLE IF NOT EXISTS f (board TEXT, job_id TEXT, p BLOB, ctx TEXT, PRIMARY KEY (board, job_id))")
    # The placement check computes only the postings sample picked.
    if ids:
        src.execute("CREATE TEMP TABLE pick (board TEXT, job_id TEXT, PRIMARY KEY (board, job_id))")
        src.executemany("INSERT INTO pick VALUES (?,?)", json.loads(Path(ids).read_text(encoding="utf-8"))["ids"])
    # Since schema 7 facts read the description and any community-list note together.
    notes = hasattr(store, "facts_description")
    rows = src.execute(f"""
        SELECT j.board, j.job_id, j.title, j.location, j.url, j.first_seen,
               COALESCE(d.company, REPLACE(j.board,'_',' ')), COALESCE(d.salary,''), d.posted,
               CAST(COALESCE(t.description,'') AS BLOB), COALESCE(t.department,''),
               {"COALESCE(n.note,'')" if notes else "''"}
        FROM jobs j
        {"JOIN pick p ON p.board=j.board AND p.job_id=j.job_id" if ids else ""}
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
    store.facts_workers = 1     # facts come precomputed (above), so none are built in processes of their own
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


# ------------------------------------------------------------ polled lists
def _polled(code, config_path, out) -> None:
    sys.path[0] = str(Path(code).resolve())
    from intel.knowledge import load_knowledge
    from intel.profile import DEFAULT_PROFILE, merge_profile
    from intel.sources import load_config, load_packs, polled_sources, profile_fields
    from tools.source_history import boards_hash
    kn, packs, config = load_knowledge(), load_packs(), load_config(config_path)
    lists = {}
    for name, layer in sample_profiles(DEFAULT_PROFILE, {s.key: s.group for s in kn.skills}).items():
        if layer is None:       # the saved profile: the user's own, not a sample
            continue
        profile = merge_profile(config.get("profile"), layer)
        polled = polled_sources(config, profile, kn, packs)
        lists[name] = {"boards": profile_fields(profile, kn), "count": len(polled), "hash": boards_hash(polled),
                       "folders": dict(Counter(packs.source_pack.get(s, "(no pack)").partition("/")[0] for s in polled)),
                       "sources": sorted(polled)}
    Path(out).write_text(json.dumps({"code": str(Path(code).resolve()), "config": str(Path(config_path).resolve()),
                                     "profiles": lists}, indent=1), encoding="utf-8")


def polled(code, config, out) -> dict:
    """What each sample profile polls with the checkout's packs and selection, and its settings hash."""
    out = Path(out).resolve()
    if out.exists():
        raise SystemExit(f"{out} exists: each list is written to a new file")
    _run("_polled", code, Path(config).resolve(), out)
    return json.loads(out.read_text(encoding="utf-8"))["profiles"]


def polled_compare(old_path, new_path, expect=(), out=print) -> int:
    old, new = (json.loads(Path(p).read_text(encoding="utf-8"))["profiles"] for p in (old_path, new_path))
    failed = False
    out(f"{'profile':22} {'boards':26} {'polled':>13}  hash")
    for name in dict.fromkeys([*old, *new]):
        a, b = old.get(name), new.get(name)
        if a is None or b is None:
            out(f"{name:22} {'missing from ' + str(new_path if b is None else old_path)}")
            failed |= name not in expect
            continue
        same = a["hash"] == b["hash"]
        failed |= not same and name not in expect
        out(f"{name:22} {','.join(b['boards']):26} {a['count']:5} -> {b['count']:5}  "
            f"{'=' if same else a['hash'] + ' -> ' + b['hash']}{' (expected)' if name in expect and not same else ''}")
        for sign, names in (("+", sorted(set(b["sources"]) - set(a["sources"]))),
                            ("-", sorted(set(a["sources"]) - set(b["sources"])))):
            if names:
                out(f"      {sign}{len(names)}: {', '.join(names[:12])}{' ...' if len(names) > 12 else ''}")
    out("polled: " + ("FAILED" if failed else "passed"))
    return 1 if failed else 0


# ------------------------------------------------------------ placement check
# Where a posting lands: its board ("finance" when Finance places it, else its family), filter, company,
# employer type and location, as intel_store stores them in job_intel.
PLACE = ("field", "family", "category", "subcategory", "is_finance", "company_key", "company_name", "company_type",
         "country", "countries", "city", "cities", "location_bucket")
PLACED = ("title", *PLACE, "rule", "stage", "level")
KINDS = {"filter": ("field", "family", "category", "subcategory", "is_finance"),
         "company": ("company_key", "company_name"), "type": ("company_type",),
         "location": ("country", "countries", "city", "cities", "location_bucket")}
UNKNOWN = (None, "", "unknown")
# "other" is no board's, and Finance profiles review it (intel/matching.py): a move from or to either changes
# what Finance shows, so --allow must name it; * never stands for it.
FINANCE_SEES = {"finance", "other"}


def _placement(facts: dict) -> tuple:
    """PLACE, then the rule that placed it and its career stage and level."""
    cls, loc, company, seniority = facts["classification"], facts["location"], facts["company"], facts["seniority"]
    return ("finance" if cls["is_finance"] else cls["family"], cls["family"], cls["category"], cls.get("subcategory"),
            int(cls["is_finance"]), company["key"], company["name"], company["type"],
            (loc["countries"] or [None])[0], " ".join(loc["countries"]), (loc["cities"] or [None])[0],
            " ".join(loc["cities"]), loc["bucket"], cls.get("rule"), seniority["stage"], seniority["level"])


def _utc_offset(epoch: float) -> int:
    """The frozen clock's local UTC offset in seconds: today's date, and so posting age, depend on it."""
    import datetime as dt
    return int(dt.datetime.fromtimestamp(epoch).astimezone().utcoffset().total_seconds())


def _title_file(path) -> list[str]:
    """Title words from a JSON list of strings, or from lists of strings under keys (keys starting _ skipped)."""
    words = json.loads(Path(path).read_text(encoding="utf-8"))
    lists = {"": words} if isinstance(words, list) else (
        {k: v for k, v in words.items() if not k.startswith("_")} if isinstance(words, dict) else None)
    if lists is None or any(not isinstance(v, list) or not all(isinstance(w, str) and w for w in v)
                            for v in lists.values()):
        raise SystemExit(f"{path}: give a list of title words, or lists of them under keys")
    return [w for v in lists.values() for w in v]


def _words(code, boards, out) -> None:
    """The title words by which the checkout places a title on one of ``boards`` (comma-separated)."""
    sys.path[0] = str(Path(code).resolve())
    from intel.knowledge import load_knowledge
    kn, boards = load_knowledge(), set(boards.split(","))
    words = [w for b in sorted(boards) if b in kn.families for w in (*kn.families[b].title, *kn.families[b].domain)]
    words += [w for node in kn.subcategories.values() if node.parent in boards for w in node.title]
    words += [w for claim in kn.claims if claim.board in boards for w in claim.title]
    words += [w for key, fallback in kn.fallback_titles if key in boards for w in fallback]
    Path(out).write_text(json.dumps({"patterns": list(dict.fromkeys(w.pattern for w in words))}), encoding="utf-8")


def sample(db, out, cap=50, seed=0, words=(), boards=(), titles=(), log=lambda line: print(line, flush=True)) -> dict:
    """Pick the postings to place: up to ``cap`` from every source, and every title the words name."""
    out = Path(out).resolve()
    if out.exists():
        raise SystemExit(f"{out} exists: each id list is written to a new file")
    if bool(words) != bool(boards):
        raise SystemExit("--words reads the title words of the --board boards: give both")
    patterns = []
    for i, code in enumerate(words):
        tmp = out.with_name(f"{out.stem}.words{i}.json")
        _run("_words", code, ",".join(boards), tmp)
        read = json.loads(tmp.read_text(encoding="utf-8"))["patterns"]
        tmp.unlink()
        if not read:
            raise SystemExit(f"{code} has no title words for {', '.join(boards)}")
        patterns += read
    if titles:
        from intel.knowledge import fragment    # title words read as taxonomy.json's do: whole words
        patterns += [fragment(t) for t in titles]
    patterns = list(dict.fromkeys(patterns))
    match = re.compile("|".join(f"(?:{p})" for p in patterns), re.I) if patterns else None
    by_source, matched = {}, set()
    with closing(_ro(db)) as con:
        for board, job_id, title in con.execute("SELECT board, job_id, title FROM jobs WHERE title != '' ORDER BY board, job_id"):
            by_source.setdefault(board, []).append(job_id)
            if match and match.search(title):
                matched.add((board, job_id))
    rng, picked = random.Random(seed), set(matched)
    for board in sorted(by_source):
        ids = by_source[board]
        picked.update((board, j) for j in (ids if len(ids) <= cap else rng.sample(ids, cap)))
    counts = {"sources": len(by_source), "postings": sum(map(len, by_source.values())),
              "title_matches": len(matched), "picked": len(picked)}
    out.write_text(json.dumps({"db": str(Path(db).resolve()), "cap": cap, "seed": seed, "epoch": int(time.time()),
                               "boards": list(boards), "patterns": patterns, "counts": counts,
                               "ids": sorted(map(list, picked))}, separators=(",", ":")), encoding="utf-8")
    log(f"{counts['picked']} postings picked of {counts['postings']} in {counts['sources']} sources "
        f"({counts['title_matches']} by title, {len(patterns)} patterns) -> {out}")
    return counts


def place(code, db, config, ids, out, epoch=None, workers=6, stored=False,
          log=lambda line: print(line, flush=True)) -> int:
    """Record where the checkout (or, with ``stored``, the app's stored facts) places the picked postings."""
    db, ids, out = Path(db).resolve(), Path(ids).resolve(), Path(out).resolve()
    if out.exists():
        raise SystemExit(f"{out} exists: each placement is written to a new file")
    installed = (Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local") / "Jobwatch").resolve()
    if db.is_relative_to(installed):
        raise SystemExit(f"{db} is the installed database: place reads, and migrates, a copy of it")
    if not stored and "boards" not in json.loads(Path(config).read_text(encoding="utf-8")):
        raise SystemExit(f"{config} lists no sources: give an install's config.json, whose source settings the "
                         "postings were read with")
    shards = [] if stored else [out.with_name(f"{out.stem}.facts{i}.db") for i in range(workers)]
    if any(s.exists() for s in shards):
        raise SystemExit(f"{out.stem}.facts*.db exist beside {out}: a placement starts with no shards")
    picked = json.loads(ids.read_text(encoding="utf-8"))
    epoch = float(picked["epoch"] if epoch is None else epoch)
    t0 = time.monotonic()
    res, procs = sqlite3.connect(out), []
    try:
        res.executescript(f"""
            CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE placed (board TEXT, job_id TEXT, {", ".join(f"{c} {'INT' if c == 'is_finance' else 'TEXT'}"
                                                                  for c in PLACED)}, PRIMARY KEY (board, job_id));""")
        insert = f"INSERT INTO placed VALUES ({','.join('?' * (2 + len(PLACED)))})"
        if not stored:
            _run("_migrate", code, db)
            log(f"[{time.monotonic() - t0:5.0f}s] {db} migrated by {code}")
        with closing(_ro(db)) as con:
            con.execute("CREATE TEMP TABLE pick (board TEXT, job_id TEXT, PRIMARY KEY (board, job_id))")
            con.executemany("INSERT INTO pick VALUES (?,?)", picked["ids"])
            titles = {(b, j): t for b, j, t in con.execute(
                "SELECT j.board, j.job_id, j.title FROM pick p JOIN jobs j ON j.board=p.board AND j.job_id=p.job_id")}
            if stored:
                res.executemany(insert, ((b, j, titles[b, j], *_placement(json.loads(f))) for b, j, f in con.execute("""
                    SELECT i.board, i.job_id, i.facts FROM pick p
                    JOIN job_intel i ON i.board=p.board AND i.job_id=p.job_id
                    JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                    WHERE j.title != '' AND i.facts IS NOT NULL""")))
        if not stored:
            for i, shard in enumerate(shards):
                procs.append(subprocess.Popen([sys.executable, "-I", str(Path(__file__).resolve()), "_facts", str(code),
                                               str(db), str(config), str(epoch), str(i), str(workers), str(shard),
                                               str(ids)]))
            if any([p.wait() for p in procs]):     # every worker ends before the shards go
                raise SystemExit("a facts worker failed")
            for shard in shards:
                with closing(sqlite3.connect(shard)) as part:
                    res.executemany(insert, ((b, j, titles[b, j], *_placement(pickle.loads(p)))
                                             for b, j, p in part.execute("SELECT board, job_id, p FROM f")))
                shard.unlink()
        count = res.execute("SELECT COUNT(*) FROM placed").fetchone()[0]
        res.executemany("INSERT INTO meta VALUES (?,?)", [
            ("code", "stored" if stored else str(Path(code).resolve())), ("db", str(db)),
            ("config", "" if stored else str(Path(config).resolve())), ("ids", str(ids)),
            ("ids_sha1", hashlib.sha1(json.dumps(picked["ids"]).encode()).hexdigest()), ("epoch", str(epoch)),
            ("utc_offset", str(_utc_offset(epoch))), ("count", str(count))])
        res.commit()
    except BaseException:
        for p in procs:         # interrupted: no worker outlives the run
            if p.poll() is None:
                p.kill()
                p.wait()
        res.close()
        for path in (out, *shards):
            with suppress(OSError):
                path.unlink(missing_ok=True)
        raise
    res.close()
    log(f"[{time.monotonic() - t0:5.0f}s] {count} of {len(picked['ids'])} postings placed -> {out}")
    return count


def placements(path) -> tuple[dict, dict]:
    with closing(_ro(path)) as con:
        rows = {(r[0], r[1]): dict(zip(PLACED, r[2:]))
                for r in con.execute(f"SELECT board, job_id, {', '.join(PLACED)} FROM placed")}
        return rows, dict(con.execute("SELECT k, v FROM meta"))


def placement_changes(old: dict, new: dict, boards=(), allow=()) -> dict:
    """Sort every difference between two placements into the buckets place-compare reports."""
    def matches(pattern, board):
        return pattern == board or (pattern == "*" and board not in FINANCE_SEES)

    def allowed(a, b):
        return any(matches(f, a) and matches(t, b) for f, t in allow)

    out = {"missing": [], "added": [], "moves": [], "allowed_moves": [], "inside": [], "labels": [], "changed": [],
           "stages": []}
    for key, a in old.items():
        b = new.get(key)
        if b is None:
            out["missing"].append({"key": key, "title": a["title"], "from": a["field"]})
            continue
        # Career stage is not placement (it never blocks), but another board's should stay as it was.
        if (a["stage"], a["level"]) != (b["stage"], b["level"]) and not {a["field"], b["field"]} & set(boards):
            out["stages"].append({"key": key, "title": a["title"], "from": a["field"], "company": a["company_name"],
                                  "changes": {c: [a[c], b[c]] for c in ("stage", "level") if a[c] != b[c]}})
        cols = [c for c in PLACE if a[c] != b[c]]
        if not cols:
            continue
        entry = {"key": key, "title": a["title"], "from": a["field"], "to": b["field"], "company": a["company_name"],
                 "changes": {c: [a[c], b[c]] for c in (*PLACE, "rule") if a[c] != b[c]}}
        kinds = {kind for kind, names in KINDS.items() if set(cols) & set(names)}
        label = "company_key" not in cols and a["company_type"] in UNKNOWN and b["company_type"] not in UNKNOWN
        if label:
            kinds -= {"company", "type"}
        moved = a["field"] != b["field"]
        if moved and allowed(a["field"], b["field"]):
            kinds.discard("filter")
        elif not moved and a["field"] in boards:
            kinds.discard("filter")
        entry["kinds"] = sorted(kinds)
        entry["finance"] = moved and bool(FINANCE_SEES & {a["field"], b["field"]})
        if moved and "filter" in kinds:
            out["moves"].append(entry)
        elif kinds:     # an allowed move that also changes company or location counts as that change
            out["changed"].append(entry)
        elif moved:
            out["allowed_moves"].append(entry)
        elif label and not (set(cols) & set(KINDS["filter"])):
            out["labels"].append(entry)
        else:
            out["inside"].append(entry)
    out["added"] = [{"key": k, "title": b["title"], "to": b["field"]} for k, b in new.items() if k not in old]
    return out


def place_compare(old_path, new_path, boards=(), allow=(), samples=8, json_out=None, out=print) -> int:
    (old, old_meta), (new, new_meta) = placements(old_path), placements(new_path)
    if bad := [a for a in allow if a.count(":") != 1 or "" in a.split(":")]:
        raise SystemExit(f"--allow takes <from>:<to>: {', '.join(bad)}")
    allow = [tuple(a.split(":")) for a in allow]
    for k in ("ids_sha1", "epoch", "utc_offset"):
        if old_meta.get(k) != new_meta.get(k):
            out(f"note: the placements differ in {k} ({old_meta.get(k)} vs {new_meta.get(k)})")
    d = placement_changes(old, new, boards, allow)
    rng = random.Random(0)

    def show(entries):
        for e in sorted(rng.sample(entries, min(samples, len(entries))), key=lambda e: e["key"]):
            change = "; ".join(f"{c}: {a!r} -> {b!r}" for c, (a, b) in e.get("changes", {}).items())
            out(f"      {e['key'][0]}:{e['key'][1]}  {e['title']!r} @ {e.get('company')}  {change}")

    def by_board(entries):
        return dict(Counter(e["from"] for e in entries).most_common())

    finance = sum(e["finance"] for e in d["allowed_moves"])
    out(f"placed: {len(old)} -> {len(new)}; missing {len(d['missing'])}, added {len(d['added'])}, "
        f"moved {len(d['moves'])} (+{len(d['allowed_moves'])} allowed, {finance} of them change what Finance shows), "
        f"changed {len(d['changed'])}, inside {','.join(boards) or '-'} {len(d['inside'])}, "
        f"label changes {len(d['labels'])}, stage changes off the boards {len(d['stages'])}")
    for name, entries in (("missing", d["missing"]), ("added", d["added"])):
        if entries:
            out(f"  {name}: {dict(Counter(e.get('from', e.get('to')) for e in entries).most_common())}")
            show(entries)
    for name in ("moves", "allowed_moves"):
        groups = {}
        for e in d[name]:
            groups.setdefault((e["from"], e["to"]), []).append(e)
        if groups:
            out(f"  {'moved (not allowed)' if name == 'moves' else 'moved (allowed)'}:")
        for (a, b), group in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            out(f"    {a} -> {b}: {len(group)}{'  (changes what Finance shows)' if group[0]['finance'] else ''}")
            show(group)
    kinds = Counter(k for e in d["changed"] for k in e["kinds"])
    if kinds:
        moved = Counter((e["from"], e["to"]) for e in d["changed"] if e["from"] != e["to"])
        out(f"  changed (not allowed): {dict(kinds.most_common())} on {by_board(d['changed'])}"
            + (f"; also moved {dict(moved)}, {sum(e['finance'] for e in d['changed'])} changing what Finance shows"
               if moved else ""))
        for kind in kinds:
            cols = Counter(c for e in d["changed"] if kind in e["kinds"] for c in e["changes"] if c in KINDS[kind])
            out(f"    {kind}: {dict(cols.most_common())}")
            show([e for e in d["changed"] if kind in e["kinds"]])
    if d["inside"]:
        out(f"  inside the boards: {dict(Counter(c for e in d['inside'] for c in e['changes']).most_common())} "
            f"on {by_board(d['inside'])}")
        show(d["inside"])
    if d["labels"]:
        types = Counter((e["from"], e["changes"]["company_type"][1]) for e in d["labels"])
        out(f"  label changes: {by_board(d['labels'])}; renamed {sum('company_name' in e['changes'] for e in d['labels'])}")
        out(f"    by board and new type: {', '.join(f'{b} {t} {n}' for (b, t), n in types.most_common())}")
        show(d["labels"])
    if d["stages"]:
        steps = Counter(tuple(e["changes"].get("stage", ("", ""))) for e in d["stages"])
        out(f"  stage changes off the boards (not blocking): {by_board(d['stages'])}; "
            f"{', '.join(f'{a}->{b} {n}' for (a, b), n in steps.most_common() if a or b)}")
        show(d["stages"])
    if json_out:
        Path(json_out).write_text(json.dumps({"old": str(old_path), "new": str(new_path), "boards": list(boards),
                                              "allow": [":".join(a) for a in allow], **d}, ensure_ascii=False),
                                  encoding="utf-8")
    failed = bool(d["missing"] or d["added"] or d["moves"] or d["changed"])
    out("place: " + ("FAILED" if failed else "passed"))
    return 1 if failed else 0


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
    facts = {(r[0], r[1]): r[2:] for r in con.execute(
        "SELECT board, job_id, facts_hash, is_finance, family, title, company_name, is_canonical, status FROM facts")}
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
    def placed(row):
        return "finance" if row[1] else row[2]
    moved = [k for k in old["facts"] if k in new["facts"] and placed(old["facts"][k]) != placed(new["facts"][k])]
    refacted = sum(1 for k in old["facts"] if k in new["facts"] and old["facts"][k][0] != new["facts"][k][0])
    out(f"postings: {len(old['facts'])} -> {len(new['facts'])}; facts differ for {refacted}; "
        f"{len(moved)} change board")
    for (a, b), n in Counter((placed(old["facts"][k]), placed(new["facts"][k])) for k in moved).most_common():
        out(f"    {a} -> {b}: {n}")
    # Postings that leave a board (not 'other', which no board shows), listed in full when open and listed.
    for key in sorted(k for k in moved if placed(old["facts"][k]) != "other" and new["facts"][k][5] == 1
                      and new["facts"][k][6] != "closed"):
        row = new["facts"][key]
        out(f"      {placed(old['facts'][key])} -> {placed(row)}  {key[0]}:{key[1]}  {row[3]!r} @ {row[4]}")
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
    lists = sub.add_parser("polled", help="record what each sample profile polls")
    lists.add_argument("--code", required=True, help="the checkout whose packs and selection to read")
    lists.add_argument("--config", required=True, help="a config.json: the checkout's, or an install's")
    lists.add_argument("--out", required=True)
    lists_cmp = sub.add_parser("polled-compare", help="compare two polled lists")
    lists_cmp.add_argument("old")
    lists_cmp.add_argument("new")
    lists_cmp.add_argument("--expect", action="append", default=[], help="a profile allowed to change")
    pick = sub.add_parser("sample", help="pick the postings the placement check places")
    pick.add_argument("--db", required=True, help="a copy of the database; it is only read")
    pick.add_argument("--out", required=True)
    pick.add_argument("--cap", type=int, default=50, help="postings picked at random from each source")
    pick.add_argument("--seed", type=int, default=0)
    pick.add_argument("--words", action="append", default=[], help="a checkout whose --board title words pick titles")
    pick.add_argument("--board", action="append", default=[])
    pick.add_argument("--title", action="append", default=[],
                      help="a title word, written as in taxonomy.json (a regex; whole words, a space is any separator)")
    pick.add_argument("--title-file", help="a JSON file of title words: a list, or lists under keys (_keys skipped)")
    put = sub.add_parser("place", help="record where a checkout places the picked postings")
    put.add_argument("--code", help="the checkout to run")
    put.add_argument("--db", required=True, help="a copy of the database; the checkout's db_migrations run on it")
    put.add_argument("--config", help="the install's config.json")
    put.add_argument("--ids", required=True, help="the id list from sample")
    put.add_argument("--out", required=True)
    put.add_argument("--epoch", type=float, help="the frozen clock (default: the id list's)")
    put.add_argument("--workers", type=int, default=min(6, os.cpu_count() or 1))
    put.add_argument("--stored", action="store_true", help="record the app's stored facts instead of running code")
    where = sub.add_parser("place-compare", help="compare two placements")
    where.add_argument("old")
    where.add_argument("new")
    where.add_argument("--board", action="append", default=[], help="a board whose own filters may change")
    where.add_argument("--allow", action="append", default=[], help="a move allowed, <from>:<to> (* is any board)")
    where.add_argument("--samples", type=int, default=8)
    where.add_argument("--json", help="write every change here")
    for private in ("_migrate", "_facts", "_store", "_words", "_polled"):
        sub.add_parser(private).add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "snapshot":
        snapshot(args.code, args.db, args.config, args.epoch, args.out, args.work, args.workers)
        return 0
    if args.command == "compare":
        return compare(args.old, args.new, args.expect)
    if args.command == "polled":
        polled(args.code, args.config, args.out)
        return 0
    if args.command == "polled-compare":
        return polled_compare(args.old, args.new, args.expect)
    if args.command == "sample":
        titles = [*args.title, *(_title_file(args.title_file) if args.title_file else [])]
        sample(args.db, args.out, args.cap, args.seed, args.words, args.board, titles)
        return 0
    if args.command == "place":
        if not args.stored and not (args.code and args.config):
            parser.error("place needs --code and --config (or --stored)")
        place(args.code, args.db, args.config, args.ids, args.out, args.epoch, args.workers, args.stored)
        return 0
    if args.command == "place-compare":
        return place_compare(args.old, args.new, args.board, args.allow, args.samples, args.json)
    {"_migrate": _migrate, "_facts": _facts_worker, "_store": _store_run, "_words": _words,
     "_polled": _polled}[args.command](*args.args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
