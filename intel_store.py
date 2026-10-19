"""Persistence layer for finance intelligence.

Bridges the pure ``intel`` package and SQLite:

* facts pass   — (re)computes profile-independent facts for new/changed jobs
* score pass   — recomputes fit for the current profile; hourly for jobs
                 whose freshness / deadline can still move
* clustering   — cross-source duplicates share a ``cluster_key``; one member
                 is ``is_canonical`` (direct ATS > bespoke > repo > LinkedIn > lists whose
                 links often miss the posting)
* lifecycle    — change history and closed/removed detection for complete
                 listings

Both the watcher and the dashboard call ``IntelStore.refresh``; the work is
incremental, so repeated calls are cheap.
"""

from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from intel import (CONFIG_DIR, FACTS_VERSION, build_facts, config_fingerprint, input_hash,
                   load_knowledge, merge_profile, profile_version, score_job)

# Adapters that return the board's complete listing.  Only for these does
# "missing from a successful poll" mean the posting was taken down; the rest
# are windows (newest N, last 24h) where jobs simply scroll out of view.
# Markdown READMEs (github_md) are left out: many show only a window of the newest
# rows (zapply ~600, zshah "648 of 1182"), so a row scrolling off is not a removal.
# A README verified to list everything can opt in with "complete_listing": true.
COMPLETE_LISTING_ATS = {"greenhouse", "lever", "ashby", "janestreet", "marqeta", "github_listings"}
SOURCE_RANK = {"linkedin": 0, "github_listings": 1, "github_md": 1}
DIRECT_RANK = 3
INDIRECT_RANK = -1      # lists whose links often miss the posting (config: indirect_links)
CHANGE_FIELDS = ("title", "location", "url", "salary")
RESCORE_SECONDS = 3600
CLOSE_AFTER_MISSES = 3
CLOSE_AFTER_HOURS = 24


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def iso_epoch(value) -> float | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def board_sections(config: dict) -> dict[str, str]:
    """Board name -> the '_section' header it sits under in config.json."""
    out, section = {}, ""
    for name in (config.get("boards") or {}):
        if name.startswith("_"):
            section = name
            continue
        out[name] = section
    return out


def ensure_fts(con: sqlite3.Connection) -> bool:
    """Full-text index keyed by ``job_intel.rowid``.

    FTS5 cannot index ordinary columns, so rows are addressed by rowid: deletes
    and joins stay O(log n).  (An earlier layout filtered on UNINDEXED
    board/job_id columns, which made every update a full scan; it is rebuilt.)
    job_intel is only ever upserted, so its rowids are stable.

    Contentless: a search only needs the matching rowids, so the index keeps no copy of the text (that copy
    was a sixth of the database, and rebuilding also compacts the index to a third). An older layout is
    rebuilt; contentless_delete (SQLite 3.43) lets a row be replaced or pruned by rowid.
    """
    try:
        row = con.execute("SELECT sql FROM sqlite_master WHERE name='job_fts'").fetchone()
        if row and ("job_id" in (row[0] or "") or "content=''" not in (row[0] or "")):
            con.execute("DROP TABLE job_fts")
            row = None
        con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS job_fts USING fts5(
            body, content='', contentless_delete=1, tokenize='unicode61 remove_diacritics 2')""")
        if row is None:
            con.execute("""INSERT INTO job_fts(rowid, body)
                           SELECT i.rowid, COALESCE(i.search_text,'') || ' ' || LOWER(SUBSTR(COALESCE(t.description,''),1,6000))
                           FROM job_intel i LEFT JOIN job_text t ON t.board=i.board AND t.job_id=i.job_id
                           WHERE i.search_text IS NOT NULL""")
        return True
    except sqlite3.OperationalError:
        return False


# ---------------------------------------------------------------- profile
def load_profile(con: sqlite3.Connection, config: dict) -> dict:
    row = con.execute("SELECT v FROM user_profile WHERE k='profile'").fetchone()
    stored = json.loads(row[0]) if row and row[0] else {}
    return merge_profile(config.get("profile"), stored)


def save_profile(con: sqlite3.Connection, profile: dict) -> None:
    con.execute("INSERT OR REPLACE INTO user_profile VALUES ('profile', ?)",
                (json.dumps(profile, sort_keys=True),))


def watched_companies(con: sqlite3.Connection) -> list[str]:
    return [r[0] for r in con.execute("SELECT company_key FROM company_prefs WHERE watched=1")]


# ---------------------------------------------------------------- lifecycle
def record_changes(con: sqlite3.Connection, board: str, jobs: list[dict], ts: str) -> list[tuple]:
    """Compare incoming postings with stored rows; log meaningful changes.

    Blank previous values are ignored: Actions-mode state imports restore ids
    with empty titles, and an empty -> value transition is not news.
    """
    if not jobs:
        return []
    ids = [j["id"] for j in jobs if j.get("id")]
    stored = {}
    for chunk in range(0, len(ids), 500):
        part = ids[chunk:chunk + 500]
        marks = ",".join("?" * len(part))
        for row in con.execute(
                f"""SELECT j.job_id, j.title, j.location, j.url, COALESCE(d.salary,'')
                    FROM jobs j LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
                    WHERE j.board=? AND j.job_id IN ({marks})""", [board, *part]):
            stored[row[0]] = dict(zip(("title", "location", "url", "salary"), row[1:]))
    changes = []
    for job in jobs:
        old = stored.get(job.get("id"))
        if not old:
            continue
        for field in CHANGE_FIELDS:
            before, after = (old.get(field) or "").strip(), (job.get(field) or "").strip()
            if before and after and before != after:
                kind = {"salary": "compensation_changed", "url": "link_changed"}.get(field, f"{field}_changed")
                changes.append((board, job["id"], ts, kind, field, before[:500], after[:500]))
    if changes:
        con.executemany("INSERT INTO job_changes(board, job_id, ts, kind, field, old, new) "
                        "VALUES (?,?,?,?,?,?,?)", changes)
        touched = {(c[0], c[1]) for c in changes}
        con.executemany("UPDATE job_intel SET input_hash=NULL WHERE board=? AND job_id=?", list(touched))
    return changes


def forget_boards(con: sqlite3.Connection, boards: list[str]) -> int:
    """Delete the postings of sources that were removed, except ones with an application."""
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type IN ('table','view')")}
    if not boards or "jobs" not in tables:
        return 0
    marks = ",".join("?" * len(boards))
    keep = " AND (board || ':' || job_id) NOT IN (SELECT job_key FROM applications)" if "applications" in tables else ""
    deleted = con.execute(f"DELETE FROM jobs WHERE board IN ({marks}){keep}", boards).rowcount
    gone = lambda t: f"{t}.board IN ({marks}) AND NOT EXISTS (SELECT 1 FROM jobs WHERE jobs.board={t}.board AND jobs.job_id={t}.job_id)"
    if {"job_fts", "job_intel"} <= tables:
        con.execute(f"DELETE FROM job_fts WHERE rowid IN (SELECT rowid FROM job_intel WHERE {gone('job_intel')})", boards)
    for table in ("job_details", "job_text", "job_intel", "job_state", "job_changes", "resume_matches"):
        if table in tables:
            con.execute(f"DELETE FROM {table} WHERE {gone(table)}", boards)
    if "boards" in tables:      # a source added again later is seeded afresh, not flooded with alerts
        con.execute(f"DELETE FROM boards WHERE board IN ({marks})", boards)
    return deleted


def update_lifecycle(con: sqlite3.Connection, board: str, seen_ids: set[str], complete: bool,
                     ts: str, fresh_ids: set[str] = frozenset(), discovered: bool = False) -> dict:
    """Mark discovery, reopenings and (for complete listings) closures."""
    stats = {"possibly_closed": 0, "closed": 0, "reopened": 0}
    if fresh_ids:
        con.executemany(
            """INSERT INTO job_state(board, job_id, discovered) VALUES (?,?,?)
               ON CONFLICT(board, job_id) DO UPDATE SET discovered=excluded.discovered""",
            [(board, jid, int(discovered)) for jid in fresh_ids])
    # Reopen anything we see again.
    rows = con.execute("SELECT job_id, status FROM job_state WHERE board=? AND status!='active'",
                       (board,)).fetchall()
    reopen = [(jid,) for jid, _ in rows if jid in seen_ids]
    if reopen:
        con.executemany(
            "UPDATE job_state SET status='active', missing_count=0, reopened_at=?, closed_at=NULL "
            "WHERE board=? AND job_id=?", [(ts, board, jid) for (jid,) in reopen])
        con.executemany("INSERT INTO job_changes(board, job_id, ts, kind, field, old, new) "
                        "VALUES (?,?,?,'reopened','status','closed','active')",
                        [(board, jid, ts) for (jid,) in reopen])
        stats["reopened"] = len(reopen)
    con.executemany("UPDATE job_state SET missing_count=0 WHERE board=? AND job_id=? AND missing_count>0",
                    [(board, jid) for jid in seen_ids])
    if not complete:
        return stats

    known = con.execute(
        """SELECT j.job_id, j.last_seen, COALESCE(s.status,'active'), COALESCE(s.missing_count,0)
           FROM jobs j LEFT JOIN job_state s ON s.board=j.board AND s.job_id=j.job_id
           WHERE j.board=? AND j.title != ''""", (board,)).fetchall()
    now_epoch = time.time()
    for jid, last_seen, status, missing in known:
        if jid in seen_ids or status == "closed":
            continue
        missing += 1
        hours = (now_epoch - (iso_epoch(last_seen) or now_epoch)) / 3600
        new_status = "closed" if missing >= CLOSE_AFTER_MISSES and hours >= CLOSE_AFTER_HOURS else "possibly_closed"
        con.execute(
            """INSERT INTO job_state(board, job_id, status, missing_count, closed_at) VALUES (?,?,?,?,?)
               ON CONFLICT(board, job_id) DO UPDATE SET status=excluded.status,
                 missing_count=excluded.missing_count,
                 closed_at=COALESCE(job_state.closed_at, excluded.closed_at)""",
            (board, jid, new_status, missing, ts if new_status == "closed" else None))
        if new_status != status:
            con.execute("INSERT INTO job_changes(board, job_id, ts, kind, field, old, new) "
                        "VALUES (?,?,?,?, 'status', ?, ?)",
                        (board, jid, ts, "removed" if new_status == "closed" else "possibly_closed",
                         status, new_status))
            con.execute("UPDATE job_intel SET profile_version=NULL WHERE board=? AND job_id=?", (board, jid))
            stats[new_status] += 1
    return stats


def store_description(con: sqlite3.Connection, board: str, job_id: str, description: str,
                      department: str = "", source: str = "") -> bool:
    """Persist a description; returns True when it changed (logged as an event)."""
    import hashlib
    text = (description or "").strip()
    digest = hashlib.sha1(text.encode("utf-8", "ignore")).hexdigest()[:16] if text else ""
    row = con.execute("SELECT content_hash FROM job_text WHERE board=? AND job_id=?",
                      (board, job_id)).fetchone()
    ts = utcnow()
    if row and row[0] == digest:
        return False
    con.execute(
        """INSERT INTO job_text(board, job_id, description, department, source, content_hash, fetched_at, attempts)
           VALUES (?,?,?,?,?,?,?,1)
           ON CONFLICT(board, job_id) DO UPDATE SET description=excluded.description,
             department=CASE WHEN excluded.department!='' THEN excluded.department ELSE job_text.department END,
             source=excluded.source, content_hash=excluded.content_hash, fetched_at=excluded.fetched_at,
             attempts=job_text.attempts+1, last_error=''""",
        (board, job_id, text, department or "", source, digest, ts))
    if row and row[0]:
        con.execute("INSERT INTO job_changes(board, job_id, ts, kind, field, old, new) "
                    "VALUES (?,?,?,'description_changed','description',?,?)",
                    (board, job_id, ts, row[0], digest))
    con.execute("UPDATE job_intel SET input_hash=NULL WHERE board=? AND job_id=?", (board, job_id))
    return True


# ---------------------------------------------------------------- store
class IntelStore:
    def __init__(self, con: sqlite3.Connection, config: dict, config_dir: Path | str = CONFIG_DIR,
                 profile: dict | None = None):
        self.con = con
        self.config = config
        self.kn = load_knowledge(config_dir)
        self.kb_version = config_fingerprint(config_dir)
        self.boards = {k: v for k, v in (config.get("boards") or {}).items() if not k.startswith("_")}
        self.sections = board_sections(config)
        self._stored_profile = profile is None
        self.profile = profile if profile is not None else load_profile(con, config)
        self.watched = set(watched_companies(con))
        self.version = profile_version(self.profile, sorted(self.watched))
        self._batch_scored = 0
        self.fts = ensure_fts(con)

    # ---- facts
    def facts_pass(self, limit: int | None = None, keys: list[tuple[str, str]] | None = None,
                   incremental_score: bool = False, on_progress=None) -> int:
        """Compute facts for jobs lacking current ones; ``keys`` restricts to specific jobs."""
        if keys is not None:
            done = 0
            for chunk in range(0, len(keys), 300):
                part = keys[chunk:chunk + 300]
                if part:
                    done += self._facts_rows(part=part)
            return done
        # Commit in chunks so a large backlog never holds the write lock long
        # enough to starve the watcher (or the dashboard) of the database.
        done = 0
        while True:
            step = 500 if limit is None else min(500, limit - done)
            if step <= 0:
                break
            n = self._facts_rows(limit=step)
            if incremental_score and n:
                self._batch_scored += self.score_pass(commit_batches=True)
            self.con.commit()
            done += n
            if on_progress:
                on_progress(done)
            if n < step:
                break
        return done

    def _facts_rows(self, limit: int | None = None, part: list[tuple[str, str]] | None = None) -> int:
        scope, scope_args = "", []
        if part:
            scope = " AND (" + " OR ".join("(j.board=? AND j.job_id=?)" for _ in part) + ")"
            scope_args = [v for pair in part for v in pair]
        rows = self.con.execute(
            f"""SELECT j.board, j.job_id, j.title, j.location, j.url, j.first_seen,
                       COALESCE(d.company, REPLACE(j.board,'_',' ')), COALESCE(d.salary,''), d.posted,
                       CAST(COALESCE(t.description,'') AS BLOB), COALESCE(t.department,''), i.cluster_key
                FROM jobs j
                LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
                LEFT JOIN job_text t ON t.board=j.board AND t.job_id=j.job_id
                LEFT JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
                WHERE j.title != '' AND (i.board IS NULL OR i.input_hash IS NULL
                      OR i.facts_version != ? OR i.kb_version != ?){scope}
                ORDER BY COALESCE(i.is_finance,0) DESC, COALESCE(d.posted, 0) DESC
                {'LIMIT ' + str(int(limit)) if limit else ''}""",
            (FACTS_VERSION, self.kb_version, *scope_args)).fetchall()
        if not rows:
            return 0
        ts = utcnow()
        clusters = set()
        batch, fts_rows = [], []
        for (board, job_id, title, location, url, first_seen, company, salary, posted,
             description, department, old_cluster) in rows:
            job = {"board": board, "id": job_id, "title": title, "location": location, "url": url,
                   "company": company, "salary": salary, "posted": posted,
                   # bytes: one damaged byte on disk must not stop indexing for everything
                   "description": bytes(description).decode("utf-8", "replace"), "department": department}
            facts = build_facts(job, self.kn, self.boards.get(board, {}), self.sections.get(board, ""))
            cls, loc, cyc, comp = (facts["classification"], facts["location"], facts["cycle"],
                                   facts["compensation"])
            skills = " ".join(s["key"] for s in facts["skills"])
            search = " ".join(filter(None, [
                facts["company"]["name"], company, title, location, cls["category_label"],
                cls.get("subcategory_label"), facts["seniority"].get("level_label"),
                cyc.get("label"), " ".join(s["label"] for s in facts["skills"]),
                " ".join(loc["city_labels"])])).lower()
            clusters.add(facts["cluster_key"])
            # A job leaving its old cluster can take the canonical flag with it;
            # rerank that cluster too so it keeps a visible member.
            if old_cluster and old_cluster != facts["cluster_key"]:
                clusters.add(old_cluster)
            batch.append((
                board, job_id, input_hash(job), FACTS_VERSION, self.kb_version,
                json.dumps(facts, separators=(",", ":")), ts,
                cls["family"], cls["category"], cls.get("subcategory"), int(cls["is_finance"]),
                cls["confidence"], facts["seniority"]["stage"], facts["seniority"]["level"],
                facts["company"]["key"], facts["company"]["name"], facts["company"]["type"],
                (loc["countries"] or [None])[0], (loc["cities"] or [None])[0],
                " ".join(loc["cities"]), loc["bucket"],
                cyc.get("cycle"), cyc.get("year"),
                (facts["deadline"] or {}).get("date"), (facts["deadline"] or {}).get("confidence"),
                int(facts["rolling"]), comp.get("annual_min"), comp.get("annual_max"), comp.get("currency"),
                skills, search, facts["cluster_key"]))
            if self.fts:
                fts_rows.append((board, job_id, f"{search} {job['description'][:6000].lower()}"))
        self.con.executemany(
            """INSERT INTO job_intel(board, job_id, input_hash, facts_version, kb_version, facts, facts_at,
                 family, category, subcategory, is_finance, class_confidence, stage, level,
                 company_key, company_name, company_type, country, city, cities, location_bucket,
                 cycle, cycle_year, deadline, deadline_confidence, rolling,
                 comp_annual_min, comp_annual_max, comp_currency, skills, search_text, cluster_key,
                 profile_version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
               ON CONFLICT(board, job_id) DO UPDATE SET
                 input_hash=excluded.input_hash, facts_version=excluded.facts_version,
                 kb_version=excluded.kb_version, facts=excluded.facts, facts_at=excluded.facts_at,
                 family=excluded.family, category=excluded.category, subcategory=excluded.subcategory,
                 is_finance=excluded.is_finance, class_confidence=excluded.class_confidence,
                 stage=excluded.stage, level=excluded.level, company_key=excluded.company_key,
                 company_name=excluded.company_name, company_type=excluded.company_type,
                 country=excluded.country, city=excluded.city, cities=excluded.cities,
                 location_bucket=excluded.location_bucket, cycle=excluded.cycle,
                 cycle_year=excluded.cycle_year, deadline=excluded.deadline,
                 deadline_confidence=excluded.deadline_confidence, rolling=excluded.rolling,
                 comp_annual_min=excluded.comp_annual_min, comp_annual_max=excluded.comp_annual_max,
                 comp_currency=excluded.comp_currency, skills=excluded.skills,
                 search_text=excluded.search_text, cluster_key=excluded.cluster_key,
                 profile_version=NULL""", batch)
        if self.fts and fts_rows:
            self.con.executemany(
                "DELETE FROM job_fts WHERE rowid=(SELECT rowid FROM job_intel WHERE board=? AND job_id=?)",
                [(b, j) for b, j, _ in fts_rows])
            self.con.executemany(
                "INSERT INTO job_fts(rowid, body) SELECT rowid, ? FROM job_intel WHERE board=? AND job_id=?",
                [(body, b, j) for b, j, body in fts_rows])
        self.recluster(clusters)
        return len(rows)

    # ---- clustering
    def source_rank(self, board: str) -> int:
        cfg = self.boards.get(board) or {}
        if cfg.get("indirect_links"):
            return INDIRECT_RANK
        return SOURCE_RANK.get(cfg.get("ats", ""), DIRECT_RANK)

    def recluster_if_ranks_changed(self) -> None:
        """Re-pick canonical members everywhere after source ranks change (config upgrade)."""
        signature = json.dumps({b: self.source_rank(b) for b in sorted(self.boards)}, separators=(",", ":"))
        row = self.con.execute("SELECT v FROM kv WHERE k='canonical_ranks'").fetchone()
        if row and row[0] == signature:
            return
        self.recluster([k for (k,) in self.con.execute(
            "SELECT DISTINCT cluster_key FROM job_intel WHERE cluster_key IS NOT NULL")])
        # rescore once so posted dates are shared across the re-picked duplicates
        self.con.execute("UPDATE job_intel SET profile_version=NULL")
        self.con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('canonical_ranks', ?)", (signature,))

    def recluster(self, keys) -> None:
        keys = [k for k in keys if k]
        for chunk in range(0, len(keys), 400):
            part = keys[chunk:chunk + 400]
            marks = ",".join("?" * len(part))
            members = self.con.execute(
                f"""SELECT i.cluster_key, i.board, i.job_id, COALESCE(s.status,'active'),
                           LENGTH(COALESCE(t.description,'')) > 0, j.first_seen
                    FROM job_intel i
                    JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                    LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                    LEFT JOIN job_text t ON t.board=i.board AND t.job_id=i.job_id
                    WHERE i.cluster_key IN ({marks})""", part).fetchall()
            groups: dict[str, list] = {}
            for row in members:
                groups.setdefault(row[0], []).append(row)
            updates = []
            for rows in groups.values():
                def rank(r):
                    return (r[3] == "active", self.source_rank(r[1]), r[4], -(iso_epoch(r[5]) or 0))
                best = max(rows, key=rank)
                for r in rows:
                    updates.append((int(r is best), r[1], r[2]))
            self.con.executemany("UPDATE job_intel SET is_canonical=? WHERE board=? AND job_id=?", updates)

    # ---- scoring
    def score_pass(self, force: bool = False, keys: list[tuple[str, str]] | None = None,
                   *, commit_batches: bool = False) -> int:
        """Score jobs; background callers opt into short committed write batches.

        Scoped dashboard edits keep the caller's transaction atomic by default.
        Bulk indexing releases preceding facts writes before expensive scoring.
        """
        from intel.matching import match_resume
        if commit_batches:
            self.con.commit()
        resume = self.con.execute("SELECT version FROM candidate_resume WHERE id=1").fetchone()
        # Only profile mutations advance the authoritative resume version.
        # If a profile edit races with this pass, old results stay invisible
        # because queries join against that authoritative version.
        if resume and resume[0] != self.version:
            # Either this store is stale (the profile changed after it was built:
            # skip, the next pass scores) or the saved version drifted because the
            # version's inputs changed (e.g. a new profile default in an update).
            # The second would stop scoring for good, so re-sync it.
            current = profile_version(load_profile(self.con, self.config), sorted(watched_companies(self.con)))
            if not self._stored_profile or current != self.version:
                return 0
            repaired = self.con.execute("UPDATE candidate_resume SET version=? WHERE id=1 AND version=?",
                                        (self.version, resume[0])).rowcount
            if not repaired:
                # A profile edit won the race after validation. Keep its version
                # authoritative and leave scoring to a store with that profile.
                if commit_batches:
                    self.con.commit()
                return 0
            self.con.execute("UPDATE job_intel SET profile_version=NULL WHERE profile_version IS NOT NULL "
                             "AND profile_version != ?", (self.version,))
        if commit_batches:
            self.con.commit()  # version repair must not lock collection while scores are computed
        now = time.time()
        stale_before = now - RESCORE_SECONDS
        recent_iso = (datetime.now(timezone.utc) - timedelta(days=32)).isoformat(timespec="seconds")
        recent_epoch = now - 32 * 86400
        horizon = (datetime.now(timezone.utc) - timedelta(days=2)).date().isoformat()
        if keys is not None and not keys:
            return 0
        scope = " AND (" + " OR ".join("(i.board=? AND i.job_id=?)" for _ in keys) + ")" if keys else ""
        scope_args = [v for pair in (keys or []) for v in pair]
        rows = self.con.execute(
            # Duplicates share the earliest real posting date and first sighting, so a
            # list that picked a job up late does not make it look new.
            f"""SELECT i.board, i.job_id, i.facts,
                       COALESCE((SELECT MIN(d2.posted) FROM job_intel i2 JOIN job_details d2
                                 ON d2.board=i2.board AND d2.job_id=i2.job_id
                                 WHERE i2.cluster_key=i.cluster_key), d.posted),
                       COALESCE((SELECT MIN(j2.first_seen) FROM job_intel i2 JOIN jobs j2
                                 ON j2.board=i2.board AND j2.job_id=i2.job_id
                                 WHERE i2.cluster_key=i.cluster_key), j.first_seen),
                       COALESCE(s.discovered,0), COALESCE(s.status,'active'),
                       NULLIF(COALESCE(NULLIF(o.deadline,''), a.deadline), ''),
                       i.company_key, i.input_hash, i.facts_version, i.kb_version,
                       i.profile_version, i.scored_at
                FROM job_intel i
                JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                LEFT JOIN job_details d ON d.board=i.board AND d.job_id=i.job_id
                LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                LEFT JOIN job_overrides o ON o.job_key=(i.board||':'||i.job_id)
                LEFT JOIN applications a ON a.job_key=(i.board||':'||i.job_id)
                WHERE i.facts IS NOT NULL AND i.facts_version=? AND (
                    {'1=1 OR ' if force else ''}
                    i.profile_version IS NULL OR i.profile_version != ?
                    OR (i.scored_at < ? AND (COALESCE(d.posted,0) > ? OR j.first_seen > ?
                        OR i.deadline >= ? OR a.deadline >= ? OR o.deadline >= ?))
                    -- the freshness curve runs to 60 days: older steps change daily at most
                    OR (i.scored_at < ? AND (COALESCE(d.posted,0) > ? OR j.first_seen > ?))){scope}""",
            (FACTS_VERSION, self.version, stale_before, recent_epoch, recent_iso, horizon, horizon, horizon,
             now - 86400, now - 61 * 86400,
             (datetime.now(timezone.utc) - timedelta(days=61)).isoformat(timespec="seconds"), *scope_args)).fetchall()
        if not rows:
            return 0
        since = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="seconds")
        changed = {(b, j) for b, j in self.con.execute(
            "SELECT DISTINCT board, job_id FROM job_changes WHERE ts > ? AND kind NOT IN ('possibly_closed')",
            (since,))}
        updates = []
        matches = []
        for (board, job_id, facts_json, posted, first_seen, discovered, status, override, ckey,
             sampled_hash, facts_version, kb_version, scored_version, scored_at) in rows:
            facts = json.loads(facts_json)
            dyn = {"posted": float(posted) if posted else None, "first_seen": iso_epoch(first_seen),
                   "discovered": bool(discovered), "status": status, "deadline_override": override,
                   "watched": ckey in self.watched, "recent_change": (board, job_id) in changed}
            result = score_job(facts, self.profile, self.kn, dyn, now)
            if resume:
                match = match_resume(facts, self.profile, result)
                matches.append((board, job_id, int(match["matched"]), json.dumps(match), self.version))
            detail = {k: result[k] for k in ("subscores", "penalties", "reasons", "concerns", "raw_total",
                                             "urgency_label", "days_left", "posting_age_hours")}
            updates.append((result["fit"], json.dumps(detail, separators=(",", ":")), result["urgency"],
                            result["window_status"], " ".join(b.replace(" ", "_") for b in result["badges"]),
                            result["deadline"], dyn["posted"] or (dyn["first_seen"] if discovered else None),
                            self.version, now, board, job_id, sampled_hash, facts_version, kb_version,
                            facts_json, scored_version, scored_at, int(bool(resume)), self.version))
        applied = 0
        for start in range(0, len(updates), 500):
            accepted_matches = []
            for index in range(start, min(start + 500, len(updates))):
                # Calculation runs without a writer lock. Collection may rebuild
                # facts, or a dashboard edit may rescore this job in the meantime.
                # Save only if the sampled inputs and score revision still agree.
                changed = self.con.execute(
                    """UPDATE job_intel SET fit=?, fit_detail=?, urgency=?, window_status=?, badges=?,
                         eff_deadline=?, posted_ref=?, profile_version=?, scored_at=?
                       WHERE board=? AND job_id=? AND input_hash IS ? AND facts_version IS ?
                         AND kb_version IS ? AND facts IS ? AND profile_version IS ? AND scored_at IS ?
                         AND (?=0 OR EXISTS (SELECT 1 FROM candidate_resume WHERE id=1 AND version=?))""",
                    updates[index]).rowcount
                applied += changed
                if changed and resume:
                    accepted_matches.append(matches[index])
            self.con.executemany("""INSERT INTO resume_matches VALUES (?,?,?,?,?)
                ON CONFLICT(board,job_id) DO UPDATE SET matched=excluded.matched,
                detail=excluded.detail, profile_version=excluded.profile_version""", accepted_matches)
            if commit_batches:
                self.con.commit()
        return applied

    def refresh(self, max_facts: int | None = None, force_score: bool = False, on_progress=None) -> dict:
        """``on_progress(n)`` hears how many postings have new facts so far."""
        t0 = time.time()
        self._batch_scored = 0
        resume = bool(self.con.execute("SELECT 1 FROM candidate_resume WHERE id=1").fetchone())
        self.recluster_if_ranks_changed()
        self.con.commit()  # release upgrade writes before building facts for the backlog
        facts = self.facts_pass(max_facts, incremental_score=resume, on_progress=on_progress)
        scored = self.score_pass(force_score, commit_batches=True) + self._batch_scored
        self.con.commit()
        return {"facts": facts, "scored": scored, "seconds": round(time.time() - t0, 2)}

    def invalidate_company(self, company_key: str) -> None:
        self.con.execute("UPDATE job_intel SET profile_version=NULL WHERE company_key=?", (company_key,))

    def invalidate_job(self, board: str, job_id: str) -> None:
        self.con.execute("UPDATE job_intel SET profile_version=NULL WHERE board=? AND job_id=?",
                         (board, job_id))
