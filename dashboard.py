#!/usr/bin/env python3
"""Local, zero-dependency web API + static host for the Jobwatch dashboard.

Standard-library ``ThreadingHTTPServer`` with a tiny regex router.  Every
list is paginated SQL over precomputed ``job_intel`` rows; the browser never
receives the whole database.  Private data (applications, contacts, notes,
profile) lives only in the local SQLite file.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import csv
import copy
import io
import json
import os
import re
import socket
import sqlite3
import sys
import threading
import time
import webbrowser
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

import watcher
from intel import FACTS_VERSION, load_knowledge, merge_profile, validate_profile
from intel.profile import profile_version, prune_profile
from intel.eligibility import KNOWN_LANGUAGES
from intel import cover_letter, pdf_tools
from intel.resume import MAX_BYTES, MAX_CHARS, ResumeError, extract_text, parse_resume, profile_from_resume
from intel_store import IntelStore, iso_epoch, load_profile, save_profile, store_description, utcnow, watched_companies
from job_intelligence import stable_job_key
from job_query import (ACTIVE_APP_STATUSES, APP_STATUSES, FROM_CLAUSE, INTERVIEW_STATUSES,
                       SELECT_COLUMNS, build_order, build_where, flatten, page_args, resume_params)

HERE = Path(__file__).parent
WEB_DIR = HERE / "web"
LEGACY_STATUS = {"interview": "first_round"}
RELATIONSHIPS = ["alumni", "recruiter", "analyst", "associate", "vp", "referral", "other"]
STATUS_LABELS = {
    "discovered": "Discovered", "saved": "Saved", "preparing": "Preparing", "applied": "Applied",
    "assessment": "OA / Assessment", "phone_screen": "Phone Screen", "first_round": "First Round",
    "final_round": "Superday / Final", "offer": "Offer", "rejected": "Rejected",
    "withdrawn": "Withdrawn", "archived": "Archived",
}
FUNNEL = [("saved", "Saved"), ("applied", "Applied"), ("interview", "Interview"),
          ("final_round", "Final round"), ("offer", "Offer")]
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon",
                ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


DISCORD_WEBHOOK = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
DISCORD_SUBSCRIBER = "desktop"
RELEASES_API = "https://api.github.com/repos/IdanG7/JobWatcher/releases/latest"
RELEASES_PAGE = "https://github.com/IdanG7/JobWatcher/releases/"


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", version)[:3]) or (0,)


class ApiError(Exception):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


AUTOSTART_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
AUTOSTART_NAME = "Jobwatch"


def autostart_value() -> str | None:
    """The command Windows runs for Jobwatch at sign-in, if any (per user, no admin)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY) as key:
            return str(winreg.QueryValueEx(key, AUTOSTART_NAME)[0])
    except (ImportError, OSError):
        return None


def set_autostart(command: str | None) -> None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, AUTOSTART_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if command:
                winreg.SetValueEx(key, AUTOSTART_NAME, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, AUTOSTART_NAME)
                except FileNotFoundError:
                    pass
    except (ImportError, OSError) as exc:
        raise ApiError(f"Windows did not allow changing startup apps: {exc}") from exc


class FileResult:
    """A route result sent as a download instead of JSON."""
    def __init__(self, data: bytes, filename: str, content_type: str = "application/pdf"):
        self.data, self.filename, self.content_type = data, filename, content_type


class JobwatchHTTPServer(ThreadingHTTPServer):
    # Browsers request the module graph in parallel while collection uses CPU.
    # The standard server's five-connection backlog can drop those requests.
    request_queue_size = 128
    # Windows lets a second program bind a port marked reusable; Jobwatch keeps
    # its port to itself so a remembered port can never be shared or taken over.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def handle_error(self, request, client_address):
        # A browser that navigates away mid-response is routine, not an error.
        if isinstance(sys.exc_info()[1], CLIENT_GONE):
            return
        super().handle_error(request, client_address)


CLIENT_GONE = (ConnectionAbortedError, ConnectionResetError, BrokenPipeError)
# Read-heavy GET endpoints whose responses are reused until data changes.
CACHED_PATHS = {"/api/jobs", "/api/overview", "/api/analytics", "/api/companies", "/api/meta"}
CACHE_SECONDS = 20     # also bounds staleness while a poll is adding postings


def _today() -> date:
    return datetime.now().date()


def _clean_date(value, field: str) -> str:
    value = str(value or "").strip()[:10]
    if value and not _DATE.match(value):
        raise ApiError(f"{field} must be YYYY-MM-DD")
    if value:
        try:
            date.fromisoformat(value)
        except ValueError as exc:
            raise ApiError(f"{field} is not a real date") from exc
    return value


def _clean_url(value) -> str:
    value = str(value or "").strip()[:500]
    if value and not re.match(r"^https?://", value, re.I):
        raise ApiError("URLs must start with http:// or https://")
    return value


def cycle_label(key: str | None) -> str:
    if not key:
        return ""
    season, _, year = key.rpartition("_")
    if season == "new_grad":
        return f"New Grad {year}"
    if season == "off_cycle":
        return f"Off-Cycle {year}" if year.isdigit() else "Off-Cycle"
    return f"{season.replace('_', ' ').title()} {year}".strip()


class JobwatchService:
    def __init__(self, db_path=watcher.DB_PATH, config_path=watcher.CONFIG,
                 subscribers_path=watcher.SUBSCRIBERS):
        self.db_path = Path(db_path) if str(db_path) != ":memory:" else db_path
        self.config_path = Path(config_path)
        self.subscribers_path = Path(subscribers_path)
        # The Gemini key sits beside the database (git-ignored, never in the DB or config).
        self.ai_path = (Path(db_path).parent if isinstance(self.db_path, Path) else self.subscribers_path.parent) / "ai.local.json"
        self._ai_lock = threading.Lock()
        # Set by the portable launcher, which owns the server and the Windows paths.
        self.on_shutdown = None
        self.autostart_command: str | None = None
        self.log_path: Path | None = None
        self.updater = None                   # updater.Updater in the Windows app
        self.app_root: Path | None = None     # the folder holding app/ and runtime/
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        self.boards = {k: v for k, v in self.config.get("boards", {}).items() if not k.startswith("_")}
        self.kn = load_knowledge()
        self._refresh_lock = threading.Lock()
        self._poll_lock = threading.Lock()
        self._discord_lock = threading.Lock()
        self._update_cache: tuple[float, dict] | None = None
        self._cache: dict = {}
        self._cache_gen = 0
        self._cache_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._scan_slots = threading.BoundedSemaphore(4)
        self._merge_slots = threading.BoundedSemaphore(2)   # each merge can hold ~100 MB of PDFs
        self._scan_lock = threading.Lock()
        self._scanning = set()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._pending_cache: tuple[float, int] | None = None
        self.status = {"indexing": False, "last_refresh": None, "last_stats": None,
                       "poll_running": False, "last_poll": None, "error": None, "progress": None}
        con = watcher.db_open(self.db_path)
        self._import_legacy_watchlist(con)
        self._prune_profile(con)
        con.commit()
        con.close()

    # ------------------------------------------------------------ db
    def connect(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.execute("PRAGMA busy_timeout=8000")
        con.execute("PRAGMA synchronous=NORMAL")
        con.row_factory = sqlite3.Row
        return con

    @contextmanager
    def db(self):
        con = self.connect()
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def _prune_profile(self, con) -> None:
        """Drop saved choices this version no longer offers (0.3.0's tech specialties,
        employer types and skills), so saving Settings doesn't fail validation."""
        row = con.execute("SELECT v FROM user_profile WHERE k='profile'").fetchone()
        stored = json.loads(row[0]) if row and row[0] else None
        if stored and (pruned := prune_profile(stored, self.kn)) != stored:
            save_profile(con, pruned)

    def _import_legacy_watchlist(self, con) -> None:
        """Seed the company watchlist once from the subscriber watchlist regex."""
        if con.execute("SELECT 1 FROM kv WHERE k='watchlist_seeded'").fetchone():
            return
        con.execute("INSERT OR REPLACE INTO kv VALUES ('watchlist_seeded', ?)", (utcnow(),))
        try:
            raw = json.loads(self.subscribers_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        pattern = next((s.get("watchlist") for n, s in raw.items()
                        if not n.startswith("_") and not s.get("mute") and s.get("watchlist")), None)
        if not pattern:
            return
        try:
            regex = re.compile(pattern, re.I)
        except re.error:
            return
        ts = utcnow()
        finance_types = set(watcher.FINANCE_COMPANY_TYPES)
        rows = [(c.key, c.name, ts, ts) for c in self.kn.companies.values()
                if c.type in finance_types and regex.search(c.name)]
        con.executemany("INSERT OR IGNORE INTO company_prefs(company_key, name, watched, created_at, updated_at) "
                        "VALUES (?,?,1,?,?)", rows)

    # ------------------------------------------------------------ response cache
    def cached(self, key, compute):
        """Reuse a GET response until data changes (or CACHE_SECONDS pass)."""
        now = time.monotonic()
        with self._cache_lock:
            gen, hit = self._cache_gen, self._cache.get(key)
        if hit and hit[0] == gen and now - hit[1] < CACHE_SECONDS:
            return hit[2]
        value = compute()
        with self._cache_lock:
            if gen == self._cache_gen:          # never store a result computed before a change
                if len(self._cache) > 64:
                    self._cache.clear()
                self._cache[key] = (gen, now, value)
        return value

    def invalidate(self) -> None:
        with self._cache_lock:
            self._cache_gen += 1
            self._cache.clear()

    # ------------------------------------------------------------ intelligence refresh
    def refresh_now(self, force_score: bool = False) -> dict:
        with self._refresh_lock:
            self.status["indexing"] = True
            try:
                con = sqlite3.connect(self.db_path, timeout=30)
                con.execute("PRAGMA busy_timeout=15000")
                con.execute("PRAGMA synchronous=NORMAL")   # WAL: safe, fewer disk flushes
                try:
                    self.pending_facts(con)
                    store = IntelStore(con, self.config)
                    stats = store.refresh(force_score=force_score)
                finally:
                    con.close()
                self.status.update(last_refresh=utcnow(), last_stats=stats, error=None)
                self._pending_cache = None
                if stats.get("facts") or stats.get("scored"):
                    self.invalidate()
                return stats
            except Exception as exc:   # surfaced in /api/status, never crashes the server
                self.status["error"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                self.status["indexing"] = False

    def start_background(self, interval: int = 60) -> None:
        def loop():
            while not self._stop.is_set():
                try:
                    self.refresh_now()
                except Exception:
                    pass
                self._wake.wait(interval)
                self._wake.clear()
        threading.Thread(target=loop, name="jobwatch-intel", daemon=True).start()

    def kick(self) -> None:
        self._wake.set()

    def pending_facts(self, con) -> int:
        """Backlog size; cached briefly because /api/status polls it."""
        cached = self._pending_cache
        if cached and time.time() - cached[0] < 15:
            return cached[1]
        from intel import FACTS_VERSION, config_fingerprint
        count = con.execute(
            """SELECT COUNT(*) FROM jobs j LEFT JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
               WHERE j.title != '' AND (i.board IS NULL OR i.input_hash IS NULL OR i.facts_version != ?
                                        OR i.kb_version != ? OR i.fit_detail IS NULL)""",
            (FACTS_VERSION, config_fingerprint())).fetchone()[0]
        self._pending_cache = (time.time(), count)
        return count

    # ------------------------------------------------------------ shared helpers
    def profile(self, con) -> dict:
        return load_profile(con, self.config)

    def watched(self, con) -> set[str]:
        return set(watched_companies(con))

    def source_label(self, board: str) -> str:
        cfg = self.boards.get(board) or {}
        if cfg.get("label"):
            return cfg["label"]
        ats = cfg.get("ats", "")
        if ats == "linkedin":
            return "LinkedIn" + (f" · {cfg.get('location')}" if cfg.get("location") else "")
        if ats in ("github_listings", "github_md"):
            return f"GitHub · {cfg.get('repo', board).split('/')[-1]}"
        company = self.kn.match_company(board.replace("_", " "))
        name = company.name if company else board.replace("_", " ").title()
        return f"{name} Careers"

    def source_kind(self, board: str) -> str:
        ats = (self.boards.get(board) or {}).get("ats", "")
        if ats == "linkedin":
            return "linkedin"
        if ats in ("github_listings", "github_md"):
            return "aggregator"
        return "direct"

    def _row(self, row: sqlite3.Row) -> dict:
        job = dict(row)
        job["key"] = f"{job['board']}:{job['job_id']}"
        job["category_label"] = self.kn.category_label(job.get("category"))
        job["subcategory_label"] = self.kn.subcategory_label(job.get("category"), job.get("subcategory"))
        job["company_type_label"] = self.kn.type_label(job.get("company_type"))
        job["cycle_label"] = cycle_label(job.get("cycle"))
        job["city_label"] = (self.kn.city_by_key.get(job.get("city") or "") or {}).get("label", "")
        job["badges"] = [b.replace("_", " ") for b in (job.get("badges") or "").split()]
        job["source_label"] = self.source_label(job["board"])
        job["company"] = job.get("company_name") or job.get("raw_company")
        return job

    def _attach_sources(self, con, jobs: list[dict]) -> None:
        keys = list({j["cluster_key"] for j in jobs if j.get("cluster_key")})
        if not keys:
            return
        found: dict[str, list] = {}
        for chunk in range(0, len(keys), 400):
            part = keys[chunk:chunk + 400]
            for r in con.execute(
                    f"SELECT cluster_key, board FROM job_intel WHERE cluster_key IN ({','.join('?' * len(part))})",
                    part):
                found.setdefault(r[0], []).append(r[1])
        for job in jobs:
            boards = found.get(job.get("cluster_key"), [job["board"]])
            job["discovered_from"] = sorted({self.source_label(b) for b in boards})

    # ------------------------------------------------------------ jobs
    def jobs(self, params: dict) -> dict:
        params = flatten(params)
        page, per_page = page_args(params)
        with self.db() as con:
            resume = self._resume_status(con)
            params = self._resume_params(params, resume)
            resume["active"] = params.get("resume_match") == "1" and resume["enabled"]
            store_fts = bool(con.execute(
                "SELECT 1 FROM sqlite_master WHERE name='job_fts'").fetchone())
            where, args = build_where(params, store_fts, self.watched(con))
            clause = " AND ".join(where)
            want_facets = params.get("facets", "1") != "0"
            if want_facets:
                # Evaluate the (multi-join) filter once; the count and every
                # facet then group over the matched rowids only.
                con.execute("CREATE TEMP TABLE IF NOT EXISTS _match(rid INTEGER PRIMARY KEY)")
                con.execute("DELETE FROM _match")
                con.execute(f"INSERT INTO _match SELECT i.rowid {FROM_CLAUSE} WHERE {clause}", args)
                total = con.execute("SELECT COUNT(*) FROM _match").fetchone()[0]
            else:
                total = con.execute(f"SELECT COUNT(*) {FROM_CLAUSE} WHERE {clause}", args).fetchone()[0]
            rows = con.execute(
                f"SELECT {SELECT_COLUMNS} {FROM_CLAUSE} WHERE {clause} ORDER BY {build_order(params)} "
                f"LIMIT ? OFFSET ?", [*args, per_page, (page - 1) * per_page]).fetchall()
            jobs = [self._row(r) for r in rows]
            resume["unfiltered_total"] = total
            resume["excluded_total"] = 0
            if resume["active"]:
                all_where, all_args = build_where({**params, "resume_match": "0"}, store_fts, self.watched(con))
                resume["unfiltered_total"] = con.execute(
                    f"SELECT COUNT(*) {FROM_CLAUSE} WHERE {' AND '.join(all_where)}", all_args).fetchone()[0]
                exclusion = """i.facts_version=? AND EXISTS (SELECT 1 FROM resume_matches rm
                    JOIN candidate_resume cr ON cr.id=1 WHERE rm.board=i.board AND rm.job_id=i.job_id
                    AND rm.matched=0 AND rm.profile_version=i.profile_version AND rm.profile_version=cr.version)"""
                resume["excluded_total"] = con.execute(
                    f"SELECT COUNT(*) {FROM_CLAUSE} WHERE {' AND '.join(all_where)} AND {exclusion}",
                    [*all_args, FACTS_VERSION]).fetchone()[0]
            resume["pending_filtered"] = max(0, resume["unfiltered_total"] - total - resume["excluded_total"])
            self._attach_sources(con, jobs)
            facets = {}
            if want_facets:
                for name, column in (("category", "category"), ("company_type", "company_type"),
                                     ("stage", "stage"), ("cycle", "cycle"), ("city", "city")):
                    facets[name] = [
                        {"key": r[0], "count": r[1],
                         "label": (self.kn.category_label(r[0]) if name == "category"
                                   else self.kn.type_label(r[0]) if name == "company_type"
                                   else cycle_label(r[0]) if name == "cycle"
                                   else (self.kn.city_by_key.get(r[0]) or {}).get("label", r[0]) if name == "city"
                                   else r[0])}
                        for r in con.execute(
                            f"""SELECT i.{column}, COUNT(*) FROM _match m JOIN job_intel i ON i.rowid=m.rid
                                WHERE i.{column} IS NOT NULL GROUP BY i.{column} ORDER BY COUNT(*) DESC LIMIT 25""")]
        return {"jobs": jobs, "total": total, "page": page, "per_page": per_page,
                "pages": max(1, (total + per_page - 1) // per_page), "facets": facets,
                "resume_matching": resume}

    def job_detail(self, key: str) -> dict:
        board, _, job_id = key.partition(":")
        with self.db() as con:
            row = con.execute(
                f"SELECT {SELECT_COLUMNS}, i.facts, i.fit_detail {FROM_CLAUSE} WHERE i.board=? AND i.job_id=?",
                (board, job_id)).fetchone()
            if not row:
                raise ApiError("job not found", HTTPStatus.NOT_FOUND)
            job = self._row(row)
            job["facts"] = json.loads(job.pop("facts") or "{}")
            job["fit_detail"] = json.loads(job.pop("fit_detail") or "{}")
            match = con.execute("""SELECT rm.detail FROM resume_matches rm
                JOIN candidate_resume cr ON cr.id=1 AND cr.version=rm.profile_version
                JOIN job_intel i ON i.board=rm.board AND i.job_id=rm.job_id AND i.profile_version=rm.profile_version
                WHERE rm.board=? AND rm.job_id=? AND i.facts_version=?""", (board, job_id, FACTS_VERSION)).fetchone()
            job["resume_match"] = json.loads(match[0]) if match else None
            text = con.execute("SELECT CAST(description AS BLOB) AS description, department, source, fetched_at "
                               "FROM job_text WHERE board=? AND job_id=?", (board, job_id)).fetchone()
            job["description"] = bytes(text["description"] or b"").decode("utf-8", "replace") if text else ""
            job["department"] = text["department"] if text else ""
            job["description_source"] = text["source"] if text else ""
            scan = con.execute("SELECT v FROM kv WHERE k=?", ("posting_scan:" + key,)).fetchone()
            scan = json.loads(scan[0]) if scan else {}
            job["posting_scan"] = {"checked_at": scan.get("checked_at"), "error": scan.get("error", ""),
                "auto": time.time() - scan.get("timestamp", 0) >= 6 * 3600}
            members = con.execute(
                """SELECT i.board, i.job_id, j.url, j.first_seen, i.is_canonical
                   FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                   WHERE i.cluster_key=? ORDER BY j.first_seen""", (job["cluster_key"],)).fetchall()
            job["sources"] = [{"board": m["board"], "label": self.source_label(m["board"]),
                               "kind": self.source_kind(m["board"]), "url": m["url"],
                               "first_seen": m["first_seen"], "canonical": bool(m["is_canonical"]),
                               "key": f"{m['board']}:{m['job_id']}"} for m in members]
            job["discovered_from"] = sorted({s["label"] for s in job["sources"]})
            keys = [(m["board"], m["job_id"]) for m in members] or [(board, job_id)]
            where = " OR ".join("(board=? AND job_id=?)" for _ in keys)
            # The earliest real posting date and sighting among the duplicates
            posted, first_seen = con.execute(
                "SELECT MIN(d.posted), MIN(j.first_seen) FROM jobs j LEFT JOIN job_details d "
                "ON d.board=j.board AND d.job_id=j.job_id WHERE "
                + " OR ".join("(j.board=? AND j.job_id=?)" for _ in keys),
                [v for pair in keys for v in pair]).fetchone()
            job["posted"] = posted or job.get("posted")
            job["first_seen"] = first_seen or job["first_seen"]
            job["changes"] = [dict(r) for r in con.execute(
                f"SELECT ts, kind, field, old, new FROM job_changes WHERE {where} ORDER BY ts DESC LIMIT 30",
                [v for pair in keys for v in pair])]
            app = con.execute("SELECT * FROM applications WHERE job_key=?", (key,)).fetchone()
            job["application"] = dict(app) if app else None
            job["application_events"] = [dict(r) for r in con.execute(
                "SELECT ts, from_status, to_status, note FROM application_events WHERE job_key=? ORDER BY ts DESC",
                (key,))]
            job["contacts"] = [dict(r) for r in con.execute(
                "SELECT * FROM contacts WHERE company_key=? OR job_key=? ORDER BY next_follow_up='' , next_follow_up",
                (job["company_key"], key))]
            override = con.execute("SELECT deadline, deadline_note, hidden FROM job_overrides WHERE job_key=?",
                                   (key,)).fetchone()
            job["override"] = dict(override) if override else None
            job["watched"] = job["company_key"] in self.watched(con)
            company = self.kn.companies.get(job["company_key"])
            job["company_meta"] = ({"name": company.name, "type": company.type,
                                    "type_label": self.kn.type_label(company.type),
                                    "hq": company.hq, "country": company.country}
                                   if company else None)
        return job

    def scan_job(self, key: str, payload: dict) -> dict:
        """Fetch only this stored posting; network work never holds a DB lock."""
        job = self.job_detail(key)
        cfg = self.boards.get(job["board"])
        if not cfg or cfg.get("disabled"):
            raise ApiError("This posting's source is unavailable for scanning.")
        with self.db() as con:
            cached = con.execute("SELECT v FROM kv WHERE k=?", ("posting_scan:" + key,)).fetchone()
        previous = json.loads(cached[0]) if cached else {}
        cooldown = 60 if payload.get("force") is True else 6 * 3600
        if time.time() - previous.get("timestamp", 0) < cooldown:
            if previous.get("error"):
                raise ApiError(previous["error"], HTTPStatus.BAD_GATEWAY)
            return job
        with self._scan_lock:
            if key in self._scanning or not self._scan_slots.acquire(blocking=False):
                raise ApiError("A posting scan is already running. Try again shortly.", HTTPStatus.CONFLICT)
            self._scanning.add(key)
        try:
            try:
                result = watcher.scan_posting(cfg, job["job_id"], job["url"])
                if not (result.get("description") or "").strip():
                    raise ValueError("The source did not provide readable posting details.")
            except (ValueError, watcher.requests.RequestException) as exc:
                message = str(exc)[:250] or "Posting details are temporarily unavailable."
                with self.db() as con:
                    con.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", ("posting_scan:" + key,
                        json.dumps({"timestamp": time.time(), "checked_at": utcnow(), "error": message})))
                raise ApiError(message, HTTPStatus.BAD_GATEWAY) from exc
            with self.db() as con:
                store_description(con, job["board"], job["job_id"], result["description"],
                                  result.get("department", ""), source="detail")
                url = result.get("url") or job["url"]
                if url != job["url"]:
                    con.execute("UPDATE jobs SET url=? WHERE board=? AND job_id=?", (url, job["board"], job["job_id"]))
                    con.execute("INSERT INTO job_changes(board,job_id,ts,kind,field,old,new) VALUES (?,?,?,'link_changed','url',?,?)",
                                (job["board"], job["job_id"], utcnow(), job["url"], url))
                if result.get("salary"):
                    con.execute("UPDATE job_details SET salary=? WHERE board=? AND job_id=?",
                                (result["salary"], job["board"], job["job_id"]))
                con.execute("INSERT OR REPLACE INTO kv VALUES (?,?)", ("posting_scan:" + key,
                    json.dumps({"timestamp": time.time(), "checked_at": utcnow(), "error": ""})))
            with self.db() as con:
                store = IntelStore(con, self.config)
                store.facts_pass(keys=[(job["board"], job["job_id"])])
                store.score_pass(keys=[(job["board"], job["job_id"])])
            self._pending_cache = None
            return self.job_detail(key)
        finally:
            with self._scan_lock:
                self._scanning.discard(key)
                self._scan_slots.release()

    def set_override(self, key: str, payload: dict) -> dict:
        deadline = _clean_date(payload.get("deadline"), "deadline")
        hidden = 1 if payload.get("hidden") else 0
        with self.db() as con:
            con.execute(
                """INSERT INTO job_overrides(job_key, deadline, deadline_note, hidden, updated_at) VALUES (?,?,?,?,?)
                   ON CONFLICT(job_key) DO UPDATE SET deadline=excluded.deadline,
                     deadline_note=excluded.deadline_note, hidden=excluded.hidden, updated_at=excluded.updated_at""",
                (key, deadline, str(payload.get("deadline_note") or "")[:300], hidden, utcnow()))
            board, _, job_id = key.partition(":")
            con.execute("UPDATE job_intel SET profile_version=NULL WHERE board=? AND job_id=?", (board, job_id))
            try:
                # Just this job; a full refresh here could index a whole backlog first.
                IntelStore(con, self.config).score_pass(keys=[(board, job_id)])
            except Exception:
                self.kick()
        return {"ok": True}

    def _rescore_soon(self) -> None:
        """Rescoring can touch every job (watching a company changes every
        score), so it runs in the background loop, never inside a request."""
        self.kick()

    # ------------------------------------------------------------ overview
    def overview(self) -> dict:
        now = time.time()
        today = _today()
        with self.db() as con:
            profile = self.profile(con)
            alerts = profile.get("alerts") or {}
            high, digest = alerts.get("high_fit", 75), alerts.get("digest_fit", 55)
            base = (f"{FROM_CLAUSE} WHERE i.is_canonical=1 AND COALESCE(s.status,'active')!='closed' "
                    "AND COALESCE(i.window_status,'')!='closed' AND j.title!=''")
            stat = lambda sql, *a: con.execute(sql, a).fetchone()[0]  # noqa: E731
            stats = {
                "new_today": stat(f"SELECT COUNT(*) {base} AND i.is_finance=1 AND i.posted_ref >= ?", now - 86400),
                "high_fit": stat(f"SELECT COUNT(*) {base} AND i.fit >= ?", high),
                "closing_soon": stat(f"SELECT COUNT(*) {base} AND i.eff_deadline BETWEEN ? AND ? AND (i.fit >= ? OR a.status IS NOT NULL)",
                                     today.isoformat(), (today + timedelta(days=7)).isoformat(), digest),
                "applications": stat(f"SELECT COUNT(*) FROM applications WHERE status IN ({','.join('?' * len(ACTIVE_APP_STATUSES))})",
                                     *ACTIVE_APP_STATUSES),
                "interviews": stat(f"SELECT COUNT(*) FROM applications WHERE status IN ({','.join('?' * len(INTERVIEW_STATUSES))})",
                                   *INTERVIEW_STATUSES),
                "follow_ups": stat("SELECT COUNT(*) FROM contacts WHERE next_follow_up != '' AND next_follow_up <= ?",
                                   today.isoformat()),
                "tracked_jobs": stat("SELECT COUNT(*) FROM jobs WHERE title != ''"),
            }
            top = [self._row(r) for r in con.execute(
                f"""SELECT {SELECT_COLUMNS} {base}
                    AND COALESCE(a.status,'') NOT IN ('rejected','withdrawn','archived','applied','offer')
                    AND (i.posted_ref IS NULL OR i.posted_ref >= ?)
                    ORDER BY i.fit DESC, COALESCE(i.posted_ref,0) DESC LIMIT 8""", (now - 30 * 86400,))]
            self._attach_sources(con, top)
            attention = self._attention(con, base, high, digest, now, today)
            follow_ups = [dict(r) for r in con.execute(
                """SELECT * FROM contacts WHERE next_follow_up != '' AND next_follow_up <= ?
                   ORDER BY next_follow_up LIMIT 8""", ((today + timedelta(days=1)).isoformat(),))]
            upcoming = self.calendar({"start": [today.isoformat()],
                                      "end": [(today + timedelta(days=7)).isoformat()]}, con)["items"][:10]
            last_run = con.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
            source_rows = con.execute("SELECT seeded, failures FROM boards").fetchall()
            searches = self._saved_searches(con, with_counts=True)
            pending = self.pending_facts(con)
            pipeline = dict(con.execute("SELECT status, COUNT(*) FROM applications GROUP BY status").fetchall())
        enabled = sum(1 for cfg in self.boards.values() if not cfg.get("disabled"))
        return {
            "profile": {k: profile.get(k) for k in ("name", "headline", "graduation_year", "target_cycles", "alerts")},
            "stats": stats,
            "top": top,
            "attention": attention,
            "follow_ups": follow_ups,
            "upcoming": upcoming,
            "activity": self.activity({"limit": ["12"]})["items"],
            "saved_searches": searches,
            "pipeline": pipeline,
            "sources": {"enabled": enabled, "healthy": sum(1 for r in source_rows if r[0] and not r[1]),
                        "failing": sum(1 for r in source_rows if r[1])},
            "last_run": dict(last_run) if last_run else None,
            "indexing": {**{k: v for k, v in self.status.items() if k != "progress"}, "pending": pending},
            "generated_at": utcnow(),
        }

    def _attention(self, con, base, high, digest, now, today) -> list[dict]:
        items = []
        for r in con.execute(
                f"""SELECT {SELECT_COLUMNS} {base} AND i.fit >= ? AND i.posted_ref >= ? AND a.status IS NULL
                    ORDER BY i.fit DESC LIMIT 6""", (high, now - 12 * 3600)):
            job = self._row(r)
            hours = max(0, int((now - (job["posted_ref"] or now)) / 3600))
            items.append({"kind": "fresh_high_fit", "severity": "high", "job": job,
                          "title": f"High-fit role posted {hours}h ago" if hours else "High-fit role just posted",
                          "action": "apply"})
        horizon = (today + timedelta(days=3)).isoformat()
        for r in con.execute(
                f"""SELECT {SELECT_COLUMNS} {base} AND i.eff_deadline BETWEEN ? AND ?
                    AND (i.fit >= ? OR a.status IN ('saved','preparing','discovered'))
                    AND COALESCE(a.status,'') NOT IN ('applied','rejected','withdrawn','archived','offer')
                    ORDER BY i.eff_deadline, i.fit DESC LIMIT 6""", (today.isoformat(), horizon, digest)):
            job = self._row(r)
            days = (date.fromisoformat(job["deadline"]) - today).days
            when = "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days"
            items.append({"kind": "deadline", "severity": "critical" if days <= 1 else "high", "job": job,
                          "title": f"Deadline {when}" + (" · saved" if job.get("app_status") else ""),
                          "action": "apply"})
        for r in con.execute(
                """SELECT * FROM applications WHERE interview_date != '' AND interview_date BETWEEN ? AND ?
                   ORDER BY interview_date""", (today.isoformat(), (today + timedelta(days=2)).isoformat())):
            app = dict(r)
            days = (date.fromisoformat(app["interview_date"][:10]) - today).days
            items.append({"kind": "interview", "severity": "critical" if days <= 1 else "high", "application": app,
                          "title": f"{STATUS_LABELS.get(app['status'], 'Interview')} "
                                   f"{'today' if days == 0 else 'tomorrow' if days == 1 else 'in 2 days'}",
                          "action": "prepare"})
        for r in con.execute(
                f"""SELECT * FROM applications WHERE next_action_date != '' AND next_action_date <= ?
                    AND status IN ({','.join('?' * len(ACTIVE_APP_STATUSES))}) ORDER BY next_action_date LIMIT 6""",
                (today.isoformat(), *ACTIVE_APP_STATUSES)):
            app = dict(r)
            overdue = (today - date.fromisoformat(app["next_action_date"][:10])).days
            items.append({"kind": "next_action", "severity": "high" if overdue else "medium", "application": app,
                          "title": (f"Follow-up overdue by {overdue}d" if overdue else "Next step due today")
                                   + (f": {app['next_step']}" if app.get("next_step") else ""),
                          "action": "update"})
        for r in con.execute(
                f"""SELECT a.*, s.closed_at FROM applications a
                    JOIN job_state s ON a.job_key=(s.board||':'||s.job_id)
                    WHERE s.status='closed' AND a.status IN ('saved','preparing','discovered')
                    ORDER BY s.closed_at DESC LIMIT 4"""):
            app = dict(r)
            items.append({"kind": "closed_saved", "severity": "high", "application": app,
                          "title": "Saved role was removed from the careers site", "action": "review"})
        for r in con.execute("""SELECT * FROM contacts WHERE next_follow_up != '' AND next_follow_up <= ?
                                ORDER BY next_follow_up LIMIT 4""", (today.isoformat(),)):
            contact = dict(r)
            items.append({"kind": "follow_up", "severity": "medium", "contact": contact,
                          "title": f"Follow up with {contact['name']}", "action": "log_contact"})
        order = {"critical": 0, "high": 1, "medium": 2}
        items.sort(key=lambda it: order.get(it["severity"], 3))
        return items[:12]

    # ------------------------------------------------------------ companies
    def companies(self, params: dict) -> dict:
        p = flatten(params)
        now = time.time()
        with self.db() as con:
            watched = self.watched(con)
            where = ["i.is_canonical=1", "COALESCE(s.status,'active')!='closed'", "j.title!=''"]
            args: list = []
            if p.get("type"):
                where.append("i.company_type=?")
                args.append(p["type"])
            if p.get("finance", "1") == "1":
                where.append("(i.is_finance=1 OR i.company_type NOT IN ('unknown','corporate'))")
            if p.get("q"):
                where.append("LOWER(i.company_name) LIKE ?")
                args.append(f"%{p['q'].lower()}%")
            rows = con.execute(
                f"""SELECT i.company_key, MAX(i.company_name) name, MAX(i.company_type) type,
                           COUNT(*) active, SUM(i.posted_ref >= ?) new_7d, SUM(i.fit >= 75) high_fit,
                           MAX(i.fit) best_fit, MAX(i.posted_ref) last_posted,
                           SUM(i.is_finance) finance_jobs
                    {FROM_CLAUSE} WHERE {' AND '.join(where)}
                    GROUP BY i.company_key ORDER BY new_7d DESC, high_fit DESC, active DESC LIMIT 400""",
                [now - 7 * 86400, *args]).fetchall()
            apps = dict(con.execute("SELECT company_key, COUNT(*) FROM applications WHERE company_key!='' "
                                    "GROUP BY company_key").fetchall())
            contacts = dict(con.execute("SELECT company_key, COUNT(*) FROM contacts GROUP BY company_key").fetchall())
            out = []
            for r in rows:
                item = dict(r)
                item.update(type_label=self.kn.type_label(item["type"]), watched=item["company_key"] in watched,
                            applications=apps.get(item["company_key"], 0),
                            contacts=contacts.get(item["company_key"], 0),
                            known=item["company_key"] in self.kn.companies)
                out.append(item)
            present = {c["company_key"] for c in out}
            for key in watched - present:
                company = self.kn.companies.get(key)
                pref = con.execute("SELECT name FROM company_prefs WHERE company_key=?", (key,)).fetchone()
                out.append({"company_key": key, "name": company.name if company else (pref[0] if pref else key),
                            "type": company.type if company else "unknown",
                            "type_label": self.kn.type_label(company.type if company else "unknown"),
                            "active": 0, "new_7d": 0, "high_fit": 0, "best_fit": None, "last_posted": None,
                            "finance_jobs": 0, "watched": True, "applications": apps.get(key, 0),
                            "contacts": contacts.get(key, 0), "known": bool(company)})
            if p.get("watched") == "1":
                out = [c for c in out if c["watched"]]
        return {"companies": out, "types": [{"key": k, **v} for k, v in self.kn.company_types.items()]}

    def company_detail(self, key: str) -> dict:
        now = time.time()
        with self.db() as con:
            company = self.kn.companies.get(key)
            jobs = [self._row(r) for r in con.execute(
                f"""SELECT {SELECT_COLUMNS} {FROM_CLAUSE}
                    WHERE i.company_key=? AND i.is_canonical=1 AND j.title!=''
                    ORDER BY COALESCE(s.status,'active')='closed', i.fit DESC LIMIT 200""", (key,))]
            if not jobs and not company:
                pref = con.execute("SELECT * FROM company_prefs WHERE company_key=?", (key,)).fetchone()
                if not pref:
                    raise ApiError("company not found", HTTPStatus.NOT_FOUND)
            self._attach_sources(con, jobs)
            weeks = []
            start = datetime.now(timezone.utc) - timedelta(weeks=12)
            counts = dict(con.execute(
                """SELECT strftime('%Y-%W', j.first_seen), COUNT(*) FROM job_intel i
                   JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                   LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                   WHERE i.company_key=? AND i.is_canonical=1 AND j.first_seen >= ?
                     AND COALESCE(s.discovered, 0)=1
                   GROUP BY 1""", (key, start.isoformat())).fetchall())
            for w in range(12, -1, -1):
                day = datetime.now(timezone.utc) - timedelta(weeks=w)
                label = day.strftime("%Y-%W")
                weeks.append({"week": label, "start": (day - timedelta(days=day.weekday())).date().isoformat(),
                              "count": counts.get(label, 0)})
            pref = con.execute("SELECT * FROM company_prefs WHERE company_key=?", (key,)).fetchone()
            apps = [dict(r) for r in con.execute(
                "SELECT * FROM applications WHERE company_key=? ORDER BY updated_at DESC", (key,))]
            contacts = [dict(r) for r in con.execute(
                "SELECT * FROM contacts WHERE company_key=? ORDER BY name", (key,))]
        active = [j for j in jobs if j["job_status"] != "closed"]
        name = company.name if company else (jobs[0]["company"] if jobs else (pref["name"] if pref else key))
        return {
            "company_key": key, "name": name,
            "type": company.type if company else (jobs[0]["company_type"] if jobs else "unknown"),
            "type_label": self.kn.type_label(company.type if company else (jobs[0]["company_type"] if jobs else "unknown")),
            "hq": company.hq if company else "", "country": company.country if company else "",
            "known": bool(company), "watched": bool(pref and pref["watched"]),
            "notes": pref["notes"] if pref else "",
            "stats": {"active": len(active), "new_7d": sum(1 for j in active if (j["posted_ref"] or 0) >= now - 7 * 86400),
                      "high_fit": sum(1 for j in active if j["fit"] >= 75),
                      "closed": len(jobs) - len(active)},
            "jobs": jobs, "weekly": weeks, "applications": apps, "contacts": contacts,
        }

    def watch_company(self, key: str, payload: dict) -> dict:
        watched = 1 if payload.get("watched", True) else 0
        company = self.kn.companies.get(key)
        name = str(payload.get("name") or (company.name if company else key))[:200]
        ts = utcnow()
        with self.db() as con:
            con.execute(
                """INSERT INTO company_prefs(company_key, name, watched, notes, created_at, updated_at)
                   VALUES (?,?,?,?,?,?) ON CONFLICT(company_key) DO UPDATE SET watched=excluded.watched,
                   name=excluded.name, notes=COALESCE(?, company_prefs.notes), updated_at=excluded.updated_at""",
                (key, name, watched, str(payload.get("notes") or ""), ts, ts,
                 payload.get("notes") if "notes" in payload else None))
            con.execute("UPDATE job_intel SET profile_version=NULL WHERE company_key=?", (key,))
            self._update_resume_version(con)
            # This company's jobs now; every other score changes too, in the background.
            keys = con.execute("SELECT board, job_id FROM job_intel WHERE company_key=? LIMIT 500", (key,)).fetchall()
            if keys:
                try:
                    IntelStore(con, self.config).score_pass(force=True, keys=[tuple(k) for k in keys])
                except Exception:
                    pass
        self._rescore_soon()
        return {"ok": True, "company_key": key, "watched": bool(watched)}

    # ------------------------------------------------------------ applications
    def _job_snapshot(self, con, key: str) -> dict:
        board, _, job_id = key.partition(":")
        row = con.execute(
            f"SELECT {SELECT_COLUMNS} {FROM_CLAUSE} WHERE i.board=? AND i.job_id=?", (board, job_id)).fetchone()
        if row:
            return self._row(row)
        row = con.execute("""SELECT j.board, j.job_id, j.title, j.location, j.url, d.company, d.salary, d.posted
                             FROM jobs j LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
                             WHERE j.board=? AND j.job_id=?""", (board, job_id)).fetchone()
        return dict(row) if row else {}

    def save_application(self, payload: dict) -> dict:
        status = str(payload.get("status") or "saved")
        status = LEGACY_STATUS.get(status, status)
        if status not in APP_STATUSES:
            raise ApiError("invalid application status")
        job = payload.get("job") or payload
        key = str(job.get("key") or payload.get("key") or stable_job_key(job))
        if not key or key == "unknown:" or ":" not in key:
            raise ApiError("job key is required")
        with self.db() as con:
            snapshot = self._job_snapshot(con, key)
            title = job.get("title") or snapshot.get("title")
            if not title:
                raise ApiError("job title and key are required")
            existing = con.execute("SELECT * FROM applications WHERE job_key=?", (key,)).fetchone()
            if existing and status == "saved":
                status = existing["status"]     # saving again never resets progress; PATCH changes status
            ts = utcnow()
            fields = self._application_fields(payload, existing)
            if status == "applied" and not fields["applied_date"]:
                fields["applied_date"] = _today().isoformat()
            board, _, job_id = key.partition(":")
            values = {
                "job_key": key, "board": board, "job_id": job_id,
                "company": job.get("company") or snapshot.get("company") or snapshot.get("company_name") or "",
                "title": title, "location": job.get("location") or snapshot.get("location") or "",
                "url": job.get("url") or snapshot.get("url") or "",
                "salary": job.get("salary") or snapshot.get("salary") or "",
                "posted": job.get("posted") or snapshot.get("posted"), "status": status,
                "category": snapshot.get("category") or "", "company_key": snapshot.get("company_key") or "",
                "fit": snapshot.get("fit"), "created_at": existing["created_at"] if existing else ts,
                "updated_at": ts, **fields,
            }
            cols = list(values)
            con.execute(
                f"INSERT INTO applications({','.join(cols)}) VALUES ({','.join('?' * len(cols))}) "
                f"ON CONFLICT(job_key) DO UPDATE SET "
                + ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("job_key", "created_at")),
                [values[c] for c in cols])
            previous = existing["status"] if existing else None
            if previous != status:
                con.execute("INSERT INTO application_events(job_key, ts, from_status, to_status, note) "
                            "VALUES (?,?,?,?,?)", (key, ts, previous, status, str(payload.get("event_note") or "")[:300]))
        return {"ok": True, "key": key, "status": status, "updated_at": ts}

    def _application_fields(self, payload: dict, existing) -> dict:
        def pick(name, default=""):
            if name in payload:
                return payload[name]
            if existing is not None and name in existing.keys():
                return existing[name]
            return default
        try:
            priority = min(3, max(0, int(pick("priority", 0) or 0)))
        except (TypeError, ValueError):
            priority = 0
        deadline = pick("deadline", "") or pick("due_date", "")
        return {
            "priority": priority,
            "notes": str(pick("notes") or "")[:10000],
            "next_step": str(pick("next_step") or "")[:500],
            "due_date": _clean_date(deadline, "deadline"),
            "deadline": _clean_date(deadline, "deadline"),
            "applied_date": _clean_date(pick("applied_date"), "applied_date"),
            "resume_version": str(pick("resume_version") or "")[:120],
            "referral": str(pick("referral") or "")[:200],
            "networking_status": str(pick("networking_status") or "")[:80],
            "next_action_date": _clean_date(pick("next_action_date"), "next_action_date"),
            "interview_date": _clean_date(pick("interview_date"), "interview_date"),
            "outcome": str(pick("outcome") or "")[:200],
        }

    def patch_application(self, key: str, payload: dict) -> dict:
        with self.db() as con:
            existing = con.execute("SELECT status FROM applications WHERE job_key=?", (key,)).fetchone()
        if not existing:
            raise ApiError("application not found", HTTPStatus.NOT_FOUND)
        return self.save_application({**payload, "key": key, "status": payload.get("status") or existing[0]})

    def delete_application(self, key: str) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM applications WHERE job_key=?", (key,))
            con.execute("DELETE FROM application_events WHERE job_key=?", (key,))
        return {"ok": True, "key": key}

    def applications(self) -> dict:
        with self.db() as con:
            rows = con.execute(
                """SELECT a.*, i.fit AS live_fit, i.category AS live_category, i.eff_deadline,
                          i.company_type, COALESCE(s.status,'active') AS job_status, i.cycle
                   FROM applications a
                   LEFT JOIN job_intel i ON a.job_key=(i.board||':'||i.job_id)
                   LEFT JOIN job_state s ON a.job_key=(s.board||':'||s.job_id)
                   ORDER BY a.priority DESC, a.updated_at DESC""").fetchall()
            events = {}
            for r in con.execute("SELECT job_key, ts, from_status, to_status FROM application_events ORDER BY ts"):
                events.setdefault(r[0], []).append(dict(r))
        items = []
        for r in rows:
            app = dict(r)
            app["key"] = app["job_key"]
            app["fit"] = app.get("live_fit") if app.get("live_fit") is not None else app.get("fit")
            app["category"] = app.get("live_category") or app.get("category")
            app["category_label"] = self.kn.category_label(app["category"])
            app["deadline"] = app.get("deadline") or app.get("eff_deadline") or ""
            app["cycle_label"] = cycle_label(app.get("cycle"))
            app["status_label"] = STATUS_LABELS.get(app["status"], app["status"])
            app["events"] = events.get(app["key"], [])
            items.append(app)
        grouped = {s: [a for a in items if a["status"] == s] for s in APP_STATUSES}
        return {"applications": items, "grouped": grouped, "total": len(items),
                "statuses": [{"key": s, "label": STATUS_LABELS[s]} for s in APP_STATUSES]}

    def pipeline(self) -> dict:
        """Legacy endpoint shape."""
        data = self.applications()
        return {"pipeline": data["grouped"], "total": data["total"]}

    # ------------------------------------------------------------ contacts
    def _contact_values(self, payload: dict, existing=None) -> dict:
        def pick(name, default=""):
            if name in payload:
                return payload[name]
            return existing[name] if existing is not None else default
        name = str(pick("name") or "").strip()[:200]
        if not name:
            raise ApiError("contact name is required")
        relationship = str(pick("relationship", "other") or "other").lower()
        if relationship not in RELATIONSHIPS:
            raise ApiError(f"relationship must be one of {', '.join(RELATIONSHIPS)}")
        email = str(pick("email") or "").strip()[:200]
        if email and not _EMAIL.match(email):
            raise ApiError("email address looks invalid")
        company = str(pick("company") or "").strip()[:200]
        matched = self.kn.match_company(company) if company else None
        company_key = str(pick("company_key") or "") or (matched.key if matched else "")
        if not company_key and company:
            from intel.companies import slug
            company_key = slug(company)
        return {
            "name": name, "position": str(pick("position") or "")[:200], "company": company,
            "company_key": company_key, "email": email, "linkedin_url": _clean_url(pick("linkedin_url")),
            "relationship": relationship, "last_contacted": _clean_date(pick("last_contacted"), "last_contacted"),
            "next_follow_up": _clean_date(pick("next_follow_up"), "next_follow_up"),
            "notes": str(pick("notes") or "")[:10000], "job_key": str(pick("job_key") or "")[:300],
        }

    def contacts(self, params: dict) -> dict:
        p = flatten(params)
        where, args = [], []
        if p.get("company"):
            where.append("company_key=?")
            args.append(p["company"])
        if p.get("due") == "1":
            where.append("next_follow_up != '' AND next_follow_up <= ?")
            args.append(_today().isoformat())
        sql = "SELECT * FROM contacts" + (f" WHERE {' AND '.join(where)}" if where else "")
        sql += " ORDER BY CASE WHEN next_follow_up='' THEN 1 ELSE 0 END, next_follow_up, name"
        with self.db() as con:
            rows = [dict(r) for r in con.execute(sql, args)]
            logs = {}
            for r in con.execute("SELECT contact_id, ts, kind, note FROM contact_log ORDER BY ts DESC"):
                logs.setdefault(r[0], []).append(dict(r))
        for row in rows:
            row["log"] = logs.get(row["id"], [])[:10]
        return {"contacts": rows, "relationships": RELATIONSHIPS}

    def create_contact(self, payload: dict) -> dict:
        values = self._contact_values(payload)
        ts = utcnow()
        with self.db() as con:
            cur = con.execute(
                f"INSERT INTO contacts({','.join(values)}, created_at, updated_at) "
                f"VALUES ({','.join('?' * len(values))}, ?, ?)", [*values.values(), ts, ts])
            return {"ok": True, "id": cur.lastrowid}

    def patch_contact(self, contact_id: int, payload: dict) -> dict:
        with self.db() as con:
            existing = con.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
            if not existing:
                raise ApiError("contact not found", HTTPStatus.NOT_FOUND)
            values = self._contact_values(payload, existing)
            con.execute(f"UPDATE contacts SET {', '.join(f'{k}=?' for k in values)}, updated_at=? WHERE id=?",
                        [*values.values(), utcnow(), contact_id])
        return {"ok": True, "id": contact_id}

    def delete_contact(self, contact_id: int) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM contacts WHERE id=?", (contact_id,))
            con.execute("DELETE FROM contact_log WHERE contact_id=?", (contact_id,))
        return {"ok": True}

    def log_contact(self, contact_id: int, payload: dict) -> dict:
        today = _today()
        days = payload.get("follow_up_days", 14)
        try:
            days = max(0, min(365, int(days)))
        except (TypeError, ValueError):
            days = 14
        next_follow = _clean_date(payload.get("next_follow_up"), "next_follow_up") or (
            (today + timedelta(days=days)).isoformat() if days else "")
        with self.db() as con:
            if not con.execute("SELECT 1 FROM contacts WHERE id=?", (contact_id,)).fetchone():
                raise ApiError("contact not found", HTTPStatus.NOT_FOUND)
            con.execute("INSERT INTO contact_log(contact_id, ts, kind, note) VALUES (?,?,?,?)",
                        (contact_id, utcnow(), str(payload.get("kind") or "note")[:30],
                         str(payload.get("note") or "")[:2000]))
            con.execute("UPDATE contacts SET last_contacted=?, next_follow_up=?, updated_at=? WHERE id=?",
                        (today.isoformat(), next_follow, utcnow(), contact_id))
        return {"ok": True, "last_contacted": today.isoformat(), "next_follow_up": next_follow}

    # ------------------------------------------------------------ calendar
    def calendar(self, params: dict, con=None) -> dict:
        p = flatten(params)
        today = _today()
        start = _clean_date(p.get("start"), "start") or (today - timedelta(days=7)).isoformat()
        end = _clean_date(p.get("end"), "end") or (today + timedelta(days=60)).isoformat()
        own = con is None
        con = con or self.connect()
        try:
            items = []
            for r in con.execute(
                    """SELECT a.job_key, a.company, a.title, a.status, a.deadline, a.interview_date, a.next_action_date,
                              a.next_step, a.url FROM applications a""").fetchall():
                for field, kind in (("deadline", "deadline"), ("interview_date", "interview"),
                                    ("next_action_date", "next_action")):
                    value = (r[field] or "")[:10]
                    if value and start <= value <= end and (kind != "deadline" or r["status"] not in ("rejected", "withdrawn", "archived")):
                        items.append({"date": value, "kind": kind, "source": "application", "job_key": r["job_key"],
                                      "title": r["next_step"] if kind == "next_action" and r["next_step"] else r["title"],
                                      "company": r["company"], "status": r["status"], "url": r["url"], "manual": True})
            seen = {(i["job_key"], i["date"]) for i in items if i["kind"] == "deadline"}
            profile = load_profile(con, self.config)
            digest = (profile.get("alerts") or {}).get("digest_fit", 55)
            for r in con.execute(
                    f"""SELECT i.board, i.job_id, i.eff_deadline, i.company_name, j.title, i.fit, i.deadline_confidence,
                               j.url, a.status
                        {FROM_CLAUSE} WHERE i.eff_deadline BETWEEN ? AND ? AND i.is_canonical=1
                        AND COALESCE(s.status,'active')!='closed' AND (i.fit >= ? OR a.status IS NOT NULL)
                        ORDER BY i.eff_deadline LIMIT 300""", (start, end, digest)):
                key = f"{r['board']}:{r['job_id']}"
                if (key, r["eff_deadline"]) in seen:
                    continue
                items.append({"date": r["eff_deadline"], "kind": "deadline", "source": "extracted", "job_key": key,
                              "title": r["title"], "company": r["company_name"], "fit": r["fit"],
                              "confidence": r["deadline_confidence"], "url": r["url"], "status": r["status"],
                              "manual": False})
            for r in con.execute("SELECT * FROM contacts WHERE next_follow_up BETWEEN ? AND ?", (start, end)):
                items.append({"date": r["next_follow_up"], "kind": "follow_up", "source": "contact",
                              "contact_id": r["id"], "title": f"Follow up: {r['name']}", "company": r["company"],
                              "manual": True})
            for r in con.execute("SELECT * FROM events WHERE date BETWEEN ? AND ?", (start, end)):
                items.append({"date": r["date"], "time": r["time"], "kind": r["kind"] or "event", "source": "event",
                              "event_id": r["id"], "title": r["title"], "company": r["company"],
                              "notes": r["notes"], "job_key": r["job_key"], "manual": True})
        finally:
            if own:
                con.close()
        order = {"interview": 0, "deadline": 1, "next_action": 2, "follow_up": 3}
        items.sort(key=lambda i: (i["date"], i.get("time") or "", order.get(i["kind"], 4)))
        return {"start": start, "end": end, "items": items}

    def create_event(self, payload: dict) -> dict:
        title = str(payload.get("title") or "").strip()[:200]
        if not title:
            raise ApiError("event title is required")
        day = _clean_date(payload.get("date"), "date")
        if not day:
            raise ApiError("event date is required")
        kind = str(payload.get("kind") or "event")[:30]
        with self.db() as con:
            cur = con.execute(
                "INSERT INTO events(kind, title, date, time, company, job_key, notes, created_at) VALUES (?,?,?,?,?,?,?,?)",
                (kind, title, day, str(payload.get("time") or "")[:5], str(payload.get("company") or "")[:200],
                 str(payload.get("job_key") or "")[:300], str(payload.get("notes") or "")[:2000], utcnow()))
            return {"ok": True, "id": cur.lastrowid}

    def delete_event(self, event_id: int) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM events WHERE id=?", (event_id,))
        return {"ok": True}

    # ------------------------------------------------------------ activity
    def activity(self, params: dict) -> dict:
        p = flatten(params)
        try:
            limit = max(1, min(200, int(p.get("limit") or 50)))
        except ValueError:
            limit = 50
        since = (datetime.now(timezone.utc) - timedelta(days=int(p.get("days") or 14))).isoformat(timespec="seconds")
        items = []
        with self.db() as con:
            for r in con.execute(
                    """SELECT substr(j.first_seen,1,13) hour, i.company_key, MAX(i.company_name) company,
                              COUNT(*) n, MAX(j.title) sample, MAX(j.first_seen) ts, MAX(i.fit) best,
                              MAX(i.category) category, MAX(i.city) city, SUM(i.is_finance) fin,
                              MAX(i.board || ':' || i.job_id) job_key
                       FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                       JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                       WHERE s.discovered=1 AND j.first_seen > ? AND +i.is_canonical=1
                       GROUP BY hour, i.company_key ORDER BY ts DESC LIMIT ?""", (since, limit)):
                city = (self.kn.city_by_key.get(r["city"] or "") or {}).get("label", "")
                if r["n"] == 1:
                    text = f"{r['company']} posted {r['sample']}" + (f" — {city}" if city else "")
                else:
                    text = f"{r['company']} posted {r['n']} {self.kn.category_label(r['category'])} roles" \
                        if r["fin"] else f"{r['company']} posted {r['n']} roles"
                items.append({"ts": r["ts"], "kind": "posted", "text": text, "company_key": r["company_key"],
                              "fit": r["best"], "count": r["n"], "job_key": r["job_key"] if r["n"] == 1 else None})
            for r in con.execute(
                    """SELECT c.ts, c.kind, c.field, c.old, c.new, c.board, c.job_id, j.title,
                              COALESCE(i.company_name, d.company) company, i.company_key
                       FROM job_changes c JOIN jobs j ON j.board=c.board AND j.job_id=c.job_id
                       LEFT JOIN job_intel i ON i.board=c.board AND i.job_id=c.job_id
                       LEFT JOIN job_details d ON d.board=c.board AND d.job_id=c.job_id
                       WHERE c.ts > ? AND c.kind != 'possibly_closed' ORDER BY c.ts DESC LIMIT ?""", (since, limit)):
                verb = {"removed": "role removed from careers site", "reopened": "role reopened",
                        "description_changed": "description updated", "title_changed": "title changed",
                        "location_changed": f"location changed: {r['old']} → {r['new']}",
                        "compensation_changed": f"compensation changed: {r['old']} → {r['new']}",
                        "link_changed": "application link changed",
                        "deadline_changed": f"deadline changed: {r['old']} → {r['new']}"}.get(r["kind"], r["kind"])
                items.append({"ts": r["ts"], "kind": r["kind"], "text": f"{r['company']} — {r['title']}: {verb}",
                              "company_key": r["company_key"], "job_key": f"{r['board']}:{r['job_id']}"})
            for r in con.execute(
                    """SELECT e.ts, e.job_key, e.from_status, e.to_status, a.company, a.title
                       FROM application_events e JOIN applications a ON a.job_key=e.job_key
                       WHERE e.ts > ? ORDER BY e.ts DESC LIMIT ?""", (since, limit)):
                items.append({"ts": r["ts"], "kind": "application",
                              "text": f"You moved {r['company']} — {r['title']} to {STATUS_LABELS.get(r['to_status'], r['to_status'])}",
                              "job_key": r["job_key"]})
        items.sort(key=lambda i: i["ts"] or "", reverse=True)
        return {"items": items[:limit]}

    # ------------------------------------------------------------ analytics
    def analytics(self, params: dict) -> dict:
        p = flatten(params)
        try:
            window = max(1, min(365, int(p.get("window") or 30)))
        except ValueError:
            window = 30
        now = time.time()
        since_epoch = now - window * 86400
        since_iso = datetime.fromtimestamp(since_epoch, timezone.utc).isoformat(timespec="seconds")
        with self.db() as con:
            discovered = """FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                            JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                            WHERE s.discovered=1 AND +i.is_canonical=1 AND j.first_seen > ?"""
            # Flow uses posted_ref: the source's posting date, or the discovery
            # time when a source gives none.  That keeps the market picture
            # meaningful even right after boards were seeded silently.
            posted = """FROM job_intel i WHERE i.is_canonical=1 AND i.is_finance=1 AND i.posted_ref >= ?"""
            flow = {w: con.execute(f"SELECT COUNT(*) {posted}", (now - w * 86400,)).fetchone()[0]
                    for w in (7, 30, 90)}
            daily = [{"day": r[0], "count": r[1], "high_fit": r[2]} for r in con.execute(
                f"""SELECT date(i.posted_ref, 'unixepoch') d, COUNT(*), SUM(i.fit >= 75) {posted}
                    AND i.posted_ref <= ? GROUP BY d ORDER BY d""", (since_epoch, now + 3600))]
            # The inventory view (all active finance roles) is always available,
            # even before any posting has been discovered live.
            inventory = """FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                           LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                           WHERE i.is_canonical=1 AND COALESCE(s.status,'active')!='closed' AND i.is_finance=1"""
            by_category = [{"key": r[0], "label": self.kn.category_label(r[0]), "count": r[1], "high_fit": r[2],
                            "new": r[3]} for r in con.execute(
                f"""SELECT i.category, COUNT(*), SUM(i.fit >= 75), SUM(i.posted_ref >= ?)
                    {inventory} GROUP BY i.category ORDER BY COUNT(*) DESC""", (since_epoch,))]
            by_city = [{"key": r[0], "label": (self.kn.city_by_key.get(r[0]) or {}).get("label", r[0]),
                        "count": r[1], "high_fit": r[2]} for r in con.execute(
                f"""SELECT i.city, COUNT(*), SUM(i.fit >= 75) {inventory} AND i.city IS NOT NULL
                    GROUP BY i.city ORDER BY COUNT(*) DESC LIMIT 12""")]
            companies = [{"key": r[0], "name": r[1], "count": r[2], "type_label": self.kn.type_label(r[3])}
                         for r in con.execute(
                f"""SELECT i.company_key, MAX(i.company_name), COUNT(*), MAX(i.company_type) {posted}
                    GROUP BY i.company_key ORDER BY COUNT(*) DESC LIMIT 12""", (since_epoch,))]
            heat = [[0] * 24 for _ in range(7)]
            for wd, hr, n in con.execute(
                    f"""SELECT CAST(strftime('%w', j.first_seen) AS INT), CAST(strftime('%H', j.first_seen) AS INT),
                               COUNT(*) {discovered} AND i.is_finance=1 GROUP BY 1, 2""", (since_iso,)):
                if wd is not None and hr is not None:
                    heat[wd][hr] = n
            # Source performance: volume, quality, earliest discovery within clusters.
            sources = []
            first_by_cluster = dict(con.execute(
                """SELECT i.cluster_key, MIN(j.first_seen) FROM job_intel i
                   JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id GROUP BY i.cluster_key
                   HAVING COUNT(*) > 1""").fetchall())
            per_board = {}
            for board, cluster, first_seen, fit, fin in con.execute(
                    """SELECT i.board, i.cluster_key, j.first_seen, i.fit, i.is_finance FROM job_intel i
                       JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id WHERE j.title != ''"""):
                b = per_board.setdefault(board, {"jobs": 0, "finance": 0, "high_fit": 0, "fit_sum": 0,
                                                 "shared": 0, "first": 0})
                b["jobs"] += 1
                b["finance"] += fin or 0
                b["high_fit"] += 1 if (fit or 0) >= 75 else 0
                b["fit_sum"] += fit or 0
                if cluster in first_by_cluster:
                    b["shared"] += 1
                    b["first"] += 1 if first_seen == first_by_cluster[cluster] else 0
            apps_by_board = dict(con.execute(
                "SELECT board, COUNT(*) FROM applications WHERE status NOT IN ('discovered','saved') GROUP BY board").fetchall())
            offers_by_board = dict(con.execute(
                "SELECT board, COUNT(*) FROM applications WHERE status IN ('offer') GROUP BY board").fetchall())
            for board, b in per_board.items():
                sources.append({"board": board, "label": self.source_label(board), "kind": self.source_kind(board),
                                "jobs": b["jobs"], "finance": b["finance"], "high_fit": b["high_fit"],
                                "avg_fit": round(b["fit_sum"] / b["jobs"], 1) if b["jobs"] else 0,
                                "first_share": round(b["first"] / b["shared"], 2) if b["shared"] else None,
                                "shared": b["shared"], "applications": apps_by_board.get(board, 0),
                                "offers": offers_by_board.get(board, 0)})
            sources.sort(key=lambda s: (-s["high_fit"], -s["finance"]))
            # Funnel: furthest stage each application has ever reached.
            reached = {}
            for key, status in con.execute("SELECT job_key, status FROM applications"):
                reached[key] = {status}
            for key, to_status in con.execute("SELECT job_key, to_status FROM application_events"):
                reached.setdefault(key, set()).add(to_status)
            def hit(statuses, stage):
                if stage == "saved":
                    return True
                if stage == "applied":
                    return bool(statuses & {"applied", *INTERVIEW_STATUSES, "offer"}) or bool(
                        statuses & {"rejected"} and len(statuses) > 1)
                if stage == "interview":
                    return bool(statuses & {*INTERVIEW_STATUSES, "offer"})
                if stage == "final_round":
                    return bool(statuses & {"final_round", "offer"})
                return "offer" in statuses
            funnel = []
            prev = None
            for stage, label in FUNNEL:
                n = sum(1 for s in reached.values() if hit(s, stage))
                funnel.append({"stage": stage, "label": label, "count": n,
                               "conversion": round(n / prev, 2) if prev else None})
                prev = n or None
        return {"window": window, "flow": flow, "daily": daily, "by_category": by_category, "by_city": by_city,
                "companies": companies, "heatmap": heat, "sources": sources[:40], "funnel": funnel}

    # ------------------------------------------------------------ sources
    def sources(self) -> dict:
        with self.db() as con:
            rows = {r["board"]: dict(r) for r in con.execute(
                "SELECT board, seeded, last_ok, failures, last_poll FROM boards")}
            counts = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
                """SELECT i.board, COUNT(*), SUM(i.is_finance), SUM(i.fit >= 75) FROM job_intel i
                   LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                   WHERE COALESCE(s.status,'active')!='closed' GROUP BY i.board""")}
            last_run = con.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
            coverage = {}
            for r in con.execute("SELECT k,v FROM kv WHERE k LIKE 'source_coverage:%'"):
                try:
                    coverage[r[0].split(':', 1)[1]] = json.loads(r[1])
                except (ValueError, TypeError):
                    pass
        sources = []
        section = ""
        for name, cfg in self.config.get("boards", {}).items():
            if name.startswith("_"):
                section = name.strip("_").replace("_", " ")
                continue
            state = rows.get(name, {})
            company = self.kn.companies.get(cfg.get("company_key", "")) or (
                None if cfg.get("ats") in ("linkedin", "github_listings", "github_md")
                else self.kn.match_company(name.replace("_", " ")))
            ctype = cfg.get("company_type") or (company.type if company else "")
            jobs, finance, high = counts.get(name, (0, 0, 0))
            sources.append({
                "name": name, "label": self.source_label(name), "adapter": cfg.get("ats"),
                "disabled": bool(cfg.get("disabled")), "note": cfg.get("_note", ""),
                "section": section, "group": cfg.get("group") or (
                    self.kn.company_types.get(ctype, {}).get("group") if ctype else section.title()),
                "company": company.name if company else "", "company_type": ctype,
                "priority": cfg.get("priority", 2), "geography": cfg.get("geography", ""),
                "complete_listing": cfg.get("complete_listing", cfg.get("ats") in watcher.COMPLETE_LISTING_ATS),
                "seeded": bool(state.get("seeded")), "last_ok": state.get("last_ok"),
                "failures": state.get("failures", 0), "last_poll": state.get("last_poll", 0),
                "jobs": jobs or 0, "finance_jobs": finance or 0, "high_fit": high or 0,
                "coverage": coverage.get(name),
            })
        sources.sort(key=lambda s: (s["disabled"], -s["failures"], s["group"] or "", s["label"]))
        return {"sources": sources, "last_run": dict(last_run) if last_run else None}

    # ------------------------------------------------------------ profile & meta
    def _update_resume_version(self, con) -> str:
        version = profile_version(self.profile(con), sorted(self.watched(con)))
        con.execute("UPDATE candidate_resume SET version=? WHERE id=1", (version,))
        return version

    def _resume_status(self, con, include_parsed=False) -> dict:
        row = con.execute("SELECT * FROM candidate_resume WHERE id=1").fetchone()
        if not row:
            return {"available": False, "enabled": False, "pending": 0}
        pending = con.execute("""SELECT COUNT(*) FROM jobs j LEFT JOIN job_intel i
            ON i.board=j.board AND i.job_id=j.job_id LEFT JOIN resume_matches rm
            ON rm.board=j.board AND rm.job_id=j.job_id WHERE j.title!='' AND
            (i.facts IS NULL OR i.facts_version!=? OR rm.profile_version IS NULL OR rm.profile_version!=?
             OR i.profile_version IS NULL OR i.profile_version!=?)""",
            (FACTS_VERSION, row["version"], row["version"])).fetchone()[0]
        result = {"available": True, "enabled": bool(row["enabled"]), "pending": pending,
                  "filename": row["filename"], "updated_at": row["updated_at"],
                  "targets": self.profile(con).get("target_roles") or [],
                  # read by the parser before graded role targets; re-uploading improves matching
                  "outdated": "role_interests" not in json.loads(row["parsed"])}
        if include_parsed:
            result["parsed"] = json.loads(row["parsed"])
        return result

    @staticmethod
    def _resume_params(params, resume):
        return resume_params(params, resume["enabled"])

    def get_resume(self) -> dict:
        with self.db() as con:
            return self._resume_status(con, include_parsed=True)

    @staticmethod
    def _document_text(payload: dict, what: str = "resume") -> tuple[str, str]:
        """(filename, text) from an uploaded .pdf/.docx/.txt (base64 ``data``) or pasted ``text``."""
        filename = payload.get("filename", f"Pasted {what}")
        if not isinstance(filename, str) or len(filename) > 200:
            raise ApiError("filename must be text up to 200 characters")
        try:
            if "text" in payload:
                text = payload["text"]
                if not isinstance(text, str) or len(text) > MAX_CHARS:
                    raise ResumeError(f"{what} text must be text up to 60,000 characters")
            else:
                encoded = payload.get("data")
                if not isinstance(encoded, str) or len(encoded) > (MAX_BYTES + 2) // 3 * 4:
                    raise ResumeError(f"upload a {what} up to 5 MB or paste its text")
                try:
                    data = base64.b64decode(encoded, validate=True)
                except (binascii.Error, ValueError) as exc:
                    raise ResumeError("invalid file encoding") from exc
                text = extract_text(filename, data)
            if len(text) > MAX_CHARS:
                raise ResumeError(f"{what} contains too much text; upload or paste up to 60,000 characters")
        except ResumeError as exc:
            raise ApiError(str(exc).replace("resume", what)) from exc
        return filename, text

    def parse_resume(self, payload: dict, keep_text: bool = False) -> dict:
        filename, text = self._document_text(payload)
        try:
            parsed = parse_resume(text, self.kn)
            if not (parsed["education"].get("level") and (parsed["skills"] or parsed["roles"])):
                raise ResumeError("could not recognize education and experience or skills; upload or paste the complete resume")
        except ResumeError as exc:
            raise ApiError(str(exc)) from exc
        parsed = {k: parsed.get(k) for k in ("education", "skills", "roles", "role_categories", "role_interests", "career",
                                             "company_types", "cities", "internships", "languages", "work_authorization")}
        parsed["roles"] = [{k: r[k] for k in ("title", "category", "subcategory", "label")} for r in parsed["roles"]]
        with self.db() as con:
            current = self.profile(con)
        proposed = profile_from_resume(parsed, current, self.kn)
        problems = validate_profile(proposed, self.kn)
        if problems:
            raise ApiError("; ".join(problems))
        result = {"filename": filename, "parsed": parsed, "profile": proposed,
                  "changes": {k: {"before": current.get(k), "after": v}
                              for k, v in proposed.items() if v != current.get(k)}}
        if keep_text:
            result["text"] = text
        return result

    def apply_resume(self, payload: dict) -> dict:
        preview = self.parse_resume(payload, keep_text=True)
        with self.db() as con:
            con.execute("BEGIN IMMEDIATE")
            profile = profile_from_resume(preview["parsed"], self.profile(con), self.kn)
            save_profile(con, profile)
            version = profile_version(profile, sorted(self.watched(con)))
            con.execute("""INSERT INTO candidate_resume VALUES (1,?,?,1,?,?) ON CONFLICT(id)
                DO UPDATE SET filename=excluded.filename, parsed=excluded.parsed, enabled=1,
                version=excluded.version, updated_at=excluded.updated_at""",
                (preview["filename"], json.dumps(preview["parsed"]), version, utcnow()))
            # full text for cover letters; parsed facts alone lose the wording
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('resume_text', ?)", (preview["text"],))
            con.execute("DELETE FROM resume_matches")
            con.execute("UPDATE job_intel SET profile_version=NULL")
        self.kick()
        return {"ok": True, "profile": profile, **self.get_resume()}

    def set_resume_enabled(self, payload: dict) -> dict:
        if not isinstance(payload.get("enabled"), bool):
            raise ApiError("enabled must be true or false")
        with self.db() as con:
            if not con.execute("SELECT 1 FROM candidate_resume WHERE id=1").fetchone():
                raise ApiError("upload a resume first")
            con.execute("UPDATE candidate_resume SET enabled=? WHERE id=1", (int(payload["enabled"]),))
        self.kick()
        return {"ok": True, **self.get_resume()}

    def delete_resume(self) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM candidate_resume")
            con.execute("DELETE FROM resume_matches")
            con.execute("DELETE FROM kv WHERE k='resume_text'")
        return {"ok": True}

    def get_profile(self) -> dict:
        with self.db() as con:
            # "saved" is false until a profile is first saved: the browser offers onboarding then.
            saved = con.execute("SELECT 1 FROM user_profile WHERE k='profile'").fetchone() is not None
            return {"profile": self.profile(con), "defaults": merge_profile(self.config.get("profile")), "saved": saved}

    def put_profile(self, payload: dict) -> dict:
        incoming = payload.get("profile") or payload
        allowed = set(merge_profile({}).keys()) | {"role_weights", "fields"}
        cleaned = {k: v for k, v in incoming.items() if k in allowed}
        profile = merge_profile(self.config.get("profile"), cleaned)
        gpa = (profile.get("education") or {}).get("gpa")
        if gpa in ("", None):
            profile["education"]["gpa"] = None
        elif isinstance(gpa, str):
            try:
                profile["education"]["gpa"] = float(gpa)
            except ValueError as exc:
                raise ApiError("education.gpa must be a number") from exc
        problems = validate_profile(profile, self.kn)
        if problems:
            raise ApiError("; ".join(problems))
        with self.db() as con:
            save_profile(con, profile)
            self._update_resume_version(con)
        self.kick()
        return {"ok": True, "profile": profile}

    # ------------------------------------------------------------ Discord alerts
    def _read_subscribers(self) -> dict:
        try:
            raw = json.loads(self.subscribers_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as exc:
            raise ApiError(f"subscribers.json is unreadable: {exc}", HTTPStatus.INTERNAL_SERVER_ERROR) from exc
        return raw if isinstance(raw, dict) else {}

    def _write_subscribers(self, subs: dict) -> None:
        temporary = self.subscribers_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(subs, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self.subscribers_path)

    def get_discord(self) -> dict:
        with self._discord_lock:
            entry = self._read_subscribers().get(DISCORD_SUBSCRIBER, {})
        hook = str(entry.get("discord_webhook", ""))
        mode = "views_only" if entry.get("match_alerts") is False else "matches_and_views"
        return {"configured": bool(hook), "webhook_hint": f"…{hook[-6:]}" if hook else "", "mode": mode}

    def put_discord_settings(self, payload: dict) -> dict:
        mode = payload.get("mode")
        if mode not in ("matches_and_views", "views_only"):
            raise ApiError("mode must be matches_and_views or views_only")
        with self._discord_lock:
            subs = self._read_subscribers()
            if DISCORD_SUBSCRIBER not in subs:
                raise ApiError("Connect Discord first.")
            subs[DISCORD_SUBSCRIBER].update(match_alerts=mode == "matches_and_views", saved_search_alerts=True)
            self._write_subscribers(subs)
        return self.get_discord()

    def put_discord(self, payload: dict) -> dict:
        webhook = str(payload.get("webhook") or "").strip()
        if not DISCORD_WEBHOOK.match(webhook):
            raise ApiError("That is not a Discord webhook URL. In Discord: channel settings → Integrations → "
                           "Webhooks → Copy Webhook URL.")
        if not watcher.send_discord_note(
                webhook, "✅ Foothold connected",
                "New matching postings, a morning summary of deadlines, interviews and follow-ups, "
                "and saved jobs that get taken down will be posted in this channel.", 0x3E63DD):
            raise ApiError("Discord rejected the webhook. Check that it still exists and try again.")
        with self._discord_lock:
            subs = self._read_subscribers()
            subs[DISCORD_SUBSCRIBER] = {
                "companies": ["all"], "alert_mode": "fit", "finance_only": False,
                "ops": True, "reminders": True, "saved_search_alerts": True,
                "discord_webhook": webhook,
                # replacing the webhook keeps the chosen alert mode
                "match_alerts": subs.get(DISCORD_SUBSCRIBER, {}).get("match_alerts", True),
            }
            self._write_subscribers(subs)
        return self.get_discord()

    def test_discord(self) -> dict:
        with self._discord_lock:
            hook = str(self._read_subscribers().get(DISCORD_SUBSCRIBER, {}).get("discord_webhook", ""))
        if not hook:
            raise ApiError("Discord is not connected yet.")
        if not watcher.send_discord_note(
                hook, "🧪 Foothold test",
                "If you can read this, Discord alerts are working.", 0x3E63DD):
            raise ApiError("Discord rejected the message. The webhook may have been deleted; reconnect it.")
        return {"ok": True}

    def delete_discord(self) -> dict:
        with self._discord_lock:
            subs = self._read_subscribers()
            if subs.pop(DISCORD_SUBSCRIBER, None) is not None:
                self._write_subscribers(subs)
        return self.get_discord()

    # ------------------------------------------------------------ background running
    def background_info(self) -> dict:
        from version import APP_VERSION
        return {"can_stop": self.on_shutdown is not None,
                "version": APP_VERSION, "updates": self.updater is not None,
                "installed": bool(self.app_root and (self.app_root / "unins000.exe").exists()),
                "autostart_supported": bool(self.autostart_command),
                "autostart": autostart_value() == self.autostart_command if self.autostart_command else False,
                "log": str(self.log_path or "")}

    def put_background(self, payload: dict) -> dict:
        if not isinstance(payload.get("autostart"), bool):
            raise ApiError("autostart must be true or false")
        if not self.autostart_command:
            raise ApiError("Starting at sign-in is only available in the Windows app.")
        set_autostart(self.autostart_command if payload["autostart"] else None)
        return self.background_info()

    def shutdown(self) -> dict:
        if self.on_shutdown is None:
            raise ApiError("Stop this copy of Foothold from the window it is running in.")
        threading.Timer(0.3, self.on_shutdown).start()      # let this response reach the browser first
        return {"ok": True}

    # ------------------------------------------------------------ Gemini cover letters
    def _read_ai(self) -> dict:
        try:
            raw = json.loads(self.ai_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def get_ai(self) -> dict:
        with self._ai_lock:
            ai = self._read_ai()
        key = str(ai.get("api_key") or "")
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k='cover_reference'").fetchone()
        reference = json.loads(row[0]) if row else None
        return {"configured": bool(key), "key_hint": f"…{key[-4:]}" if key else "",
                "model": (ai.get("models") or [""])[0],
                "reference": {"filename": reference["filename"], "chars": len(reference["text"]),
                              "updated_at": reference["updated_at"]} if reference else None}

    def put_ai(self, payload: dict) -> dict:
        key = str(payload.get("api_key") or "").strip()
        if not re.fullmatch(r"[\w-]{20,200}", key):
            raise ApiError("Paste the API key from aistudio.google.com/apikey (it usually starts with AIza).")
        try:
            models = cover_letter.pick_models(cover_letter.list_models(key))
        except cover_letter.CoverLetterError as exc:
            raise ApiError(str(exc)) from exc
        with self._ai_lock:
            temporary = self.ai_path.with_suffix(".tmp")
            temporary.write_text(json.dumps({"api_key": key, "models": models}), encoding="utf-8")
            temporary.replace(self.ai_path)
        return self.get_ai()

    def delete_ai(self) -> dict:
        with self._ai_lock:
            self.ai_path.unlink(missing_ok=True)
        return self.get_ai()

    def put_cover_reference(self, payload: dict) -> dict:
        filename, text = self._document_text(payload, "cover letter")
        if len(text.strip()) < 200:
            raise ApiError("That letter is too short to learn from; upload a complete past cover letter.")
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cover_reference', ?)",
                        (json.dumps({"filename": filename, "text": text, "updated_at": utcnow()}),))
        return self.get_ai()

    def delete_cover_reference(self) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM kv WHERE k='cover_reference'")
        return self.get_ai()

    def get_cover_letter(self, key: str) -> dict:
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            has_resume = bool(con.execute("SELECT 1 FROM kv WHERE k='resume_text'").fetchone())
        ai = self.get_ai()
        return {"letter": json.loads(row[0]) if row else None, "ai": ai["configured"],
                "resume": has_resume, "reference": ai["reference"]}

    def generate_cover_letter(self, key: str, payload: dict) -> dict:
        notes = payload.get("notes") or ""
        if not isinstance(notes, str) or len(notes) > cover_letter.MAX_NOTES:
            raise ApiError(f"notes must be text up to {cover_letter.MAX_NOTES} characters")
        with self._ai_lock:
            ai = self._read_ai()
        if not ai.get("api_key"):
            raise ApiError("Connect Gemini in Settings first.")
        job = self.job_detail(key)
        with self.db() as con:
            resume = con.execute("SELECT v FROM kv WHERE k='resume_text'").fetchone()
            reference = con.execute("SELECT v FROM kv WHERE k='cover_reference'").fetchone()
        if not resume:
            raise ApiError("Upload your resume in Settings first; the letter is written from it.")
        prompt = cover_letter.build_prompt(job, resume[0], json.loads(reference[0])["text"] if reference else "", notes)
        try:
            text, model = cover_letter.generate(ai["api_key"], prompt, ai.get("models") or cover_letter.MODELS)
        except cover_letter.CoverLetterError as exc:
            raise ApiError(str(exc)) from exc
        letter = {"body": text, "model": model, "notes": notes, "created_at": utcnow(), "edited": False}
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return {**self.get_cover_letter(key), "letter": letter}

    def put_cover_letter(self, key: str, payload: dict) -> dict:
        body = payload.get("body")
        if not isinstance(body, str) or not body.strip() or len(body) > 20_000:
            raise ApiError("the letter must be text up to 20,000 characters")
        board, _, job_id = key.partition(":")
        with self.db() as con:
            if not con.execute("SELECT 1 FROM jobs WHERE board=? AND job_id=?", (board, job_id)).fetchone():
                raise ApiError("job not found", HTTPStatus.NOT_FOUND)
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            letter = {**(json.loads(row[0]) if row else {"model": "", "notes": "", "created_at": utcnow()}),
                      "body": body, "edited": True}
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return self.get_cover_letter(key)

    def merge_documents(self, payload: dict) -> FileResult:
        """One PDF from uploaded PDFs and, optionally, this job's cover letter.

        ``files`` items are {"filename", "data" (base64)} or {"cover_letter": "<job key>"}.
        """
        items = payload.get("files")
        if not isinstance(items, list) or not items:
            raise ApiError("add at least one PDF")
        if not self._merge_slots.acquire(blocking=False):
            raise ApiError("Another merge is still running; try again in a moment.", HTTPStatus.TOO_MANY_REQUESTS)
        try:
            return self._merge_documents(payload, items)
        finally:
            self._merge_slots.release()

    def _merge_documents(self, payload: dict, items: list) -> FileResult:
        files = []
        for item in items[:pdf_tools.MAX_FILES + 1]:
            if not isinstance(item, dict):
                raise ApiError("files must be objects")
            if item.get("cover_letter"):
                key = str(item["cover_letter"])
                letter = self.get_cover_letter(key)["letter"]
                if not letter:
                    raise ApiError("this job has no cover letter yet")
                files.append(("Cover letter", pdf_tools.text_pdf(letter["body"], "Cover letter")))
                continue
            name = str(item.get("filename") or "document.pdf")[:200]
            try:
                files.append((name, base64.b64decode(str(item.get("data") or ""), validate=True)))
            except (binascii.Error, ValueError) as exc:
                raise ApiError(f"{name}: invalid file encoding") from exc
        try:
            merged = pdf_tools.merge_pdfs(files)
        except pdf_tools.PdfError as exc:
            raise ApiError(str(exc)) from exc
        name = payload.get("name") if isinstance(payload.get("name"), str) else ""
        return FileResult(merged, pdf_tools.safe_filename(name[:150] or "Application"))

    def meta(self) -> dict:
        with self.db() as con:
            cycles = [r[0] for r in con.execute(
                "SELECT cycle FROM job_intel WHERE cycle IS NOT NULL GROUP BY cycle ORDER BY COUNT(*) DESC LIMIT 20")]
        return {
            "taxonomy": self.kn.taxonomy_tree(),
            "families": self.kn.family_tree(),
            "company_types": [{"key": k, **v} for k, v in self.kn.company_types.items()],
            "cities": [{"key": c["key"], "label": c["label"], "country": c["country"], "target": bool(c.get("target"))}
                       for c in self.kn.cities],
            "countries": [{"key": k, "label": v["label"]} for k, v in self.kn.countries.items()],
            "languages": sorted(lang.title() for lang in KNOWN_LANGUAGES),
            "skills": [{"key": s.key, "label": s.label, "group": s.group} for s in self.kn.skills],
            "skill_groups": self.kn.skill_groups,
            "statuses": [{"key": s, "label": STATUS_LABELS[s]} for s in APP_STATUSES],
            "relationships": RELATIONSHIPS,
            "cycles": [{"key": c, "label": cycle_label(c)} for c in cycles],
            "stages": ["internship", "new_grad", "entry", "experienced", "senior"],
        }

    # ------------------------------------------------------------ saved searches
    def _saved_searches(self, con, with_counts: bool = False) -> list[dict]:
        rows = [dict(r) for r in con.execute("SELECT * FROM saved_searches ORDER BY name")]
        if with_counts:
            fts = bool(con.execute("SELECT 1 FROM sqlite_master WHERE name='job_fts'").fetchone())
            watched = self.watched(con)
            resume = self._resume_status(con)
            for row in rows:
                params = json.loads(row["query"] or "{}")
                params = self._resume_params(params, resume)
                total_where, total_args = build_where(params, fts, watched)
                row["total"] = con.execute(f"SELECT COUNT(*) {FROM_CLAUSE} WHERE {' AND '.join(total_where)}",
                                           total_args).fetchone()[0]
                since = row["last_visited_at"] or row["created_at"]
                where, args = build_where({**params, "since": since}, fts, watched)
                row["new_since_visit"] = con.execute(
                    f"SELECT COUNT(*) {FROM_CLAUSE} WHERE {' AND '.join(where)}", args).fetchone()[0]
        for row in rows:
            row["query"] = json.loads(row["query"] or "{}")
        return rows

    def saved_searches(self) -> dict:
        with self.db() as con:
            return {"saved_searches": self._saved_searches(con, with_counts=True)}

    def create_saved_search(self, payload: dict) -> dict:
        name = str(payload.get("name") or "").strip()[:80]
        if not name:
            raise ApiError("saved search name is required")
        query = payload.get("query") or {}
        if not isinstance(query, dict):
            raise ApiError("query must be an object of filters")
        query = {k: str(v)[:200] for k, v in query.items() if k not in ("page", "since") and v not in (None, "")}
        ts = utcnow()
        with self.db() as con:
            cur = con.execute("INSERT INTO saved_searches(name, query, notify, last_visited_at, created_at) "
                              "VALUES (?,?,?,?,?)", (name, json.dumps(query, sort_keys=True),
                                                     int(bool(payload.get("notify"))), ts, ts))
            return {"ok": True, "id": cur.lastrowid}

    def patch_saved_search(self, sid: int, payload: dict) -> dict:
        with self.db() as con:
            row = con.execute("SELECT * FROM saved_searches WHERE id=?", (sid,)).fetchone()
            if not row:
                raise ApiError("saved search not found", HTTPStatus.NOT_FOUND)
            name = str(payload.get("name") or row["name"])[:80]
            notify = int(bool(payload.get("notify", row["notify"])))
            visited = utcnow() if payload.get("visited") else row["last_visited_at"]
            con.execute("UPDATE saved_searches SET name=?, notify=?, last_visited_at=? WHERE id=?",
                        (name, notify, visited, sid))
        return {"ok": True}

    def delete_saved_search(self, sid: int) -> dict:
        with self.db() as con:
            con.execute("DELETE FROM saved_searches WHERE id=?", (sid,))
        return {"ok": True}

    # ------------------------------------------------------------ polling
    def _poll_progress(self, event, **data):
        """Update a small in-memory snapshot; HTTP status never waits on SQLite."""
        with self._status_lock:
            p = self.status["progress"]
            if event == "start":
                p.update(phase="fetching", total=len(data["sources"]), skipped=data["skipped"],
                         sources={name: {"label": self.source_label(name), "state": "queued"}
                                  for name in data["sources"]})
            elif event == "source_started":
                p["sources"][data["board"]]["state"] = "running"
            elif event == "source_finished":
                p["sources"][data["board"]].update(state=data["outcome"], jobs=data.get("jobs", 0),
                                                    error=data.get("error"))
                p["completed"] += 1
                p["failed"] += int(data["outcome"] != "ok")
                p["jobs"] += data.get("jobs", 0)
                p["new"] += data.get("new", 0)
                if data["outcome"] == "ok":
                    self._pending_cache = None
                    self.kick()  # Make completed sources searchable before slow ones finish.
            elif event == "phase":
                p["phase"] = data["phase"]
            elif event == "descriptions":
                p["descriptions"] = data

    def trigger_poll(self) -> dict:
        if not self._poll_lock.acquire(blocking=False):
            return {"ok": True, "started": False, "message": "a poll is already running"}

        with self._status_lock:
            self.status.update(poll_running=True, error=None, progress={
                "phase": "starting", "started_at": time.time(), "finished_at": None,
                "total": 0, "completed": 0, "failed": 0, "skipped": 0,
                "jobs": 0, "new": 0, "sources": {}, "descriptions": None})

        def run():
            try:
                con = watcher.db_open(self.db_path)
                try:
                    watcher.cycle(self.config, con, progress=self._poll_progress)
                finally:
                    con.close()
                with self._status_lock:
                    self.status["last_poll"] = utcnow()
                    self.status["progress"]["phase"] = "complete"
            except Exception as exc:
                with self._status_lock:
                    self.status["error"] = f"poll failed: {type(exc).__name__}: {exc}"
                    self.status["progress"]["error"] = self.status["error"]
                    self.status["progress"]["phase"] = "failed"
            finally:
                with self._status_lock:
                    self.status["poll_running"] = False
                    self.status["progress"]["finished_at"] = time.time()
                self._poll_lock.release()
                self.invalidate()
                self.kick()
        threading.Thread(target=run, name="jobwatch-poll", daemon=True).start()
        return {"ok": True, "started": True}

    def status_info(self) -> dict:
        from version import APP_VERSION
        with self._status_lock:
            result = copy.deepcopy(self.status)
        p = result["progress"]
        if p:
            p["elapsed"] = round((p["finished_at"] or time.time()) - p["started_at"])
        return {**result, "version": APP_VERSION, "pending": self._pending_cache[1] if self._pending_cache else 0}

    def update_info(self) -> dict:
        """Whether a newer release exists, and in the Windows app whether it is downloaded."""
        from version import APP_VERSION
        if self.updater is not None:
            snap = self.updater.snapshot()
            url = snap.get("release_url") or ""
            return {"current": APP_VERSION, "latest": snap.get("latest"), "state": snap["state"],
                    "available": snap["state"] in ("ready", "manual"),
                    "url": url if url.startswith(RELEASES_PAGE) else None,
                    "error": snap.get("error"), "old_copy": self.old_copy()}
        now = time.time()
        if self._update_cache and now < self._update_cache[0]:
            return self._update_cache[1]
        info = {"current": APP_VERSION, "latest": None, "available": False, "url": None}
        try:
            r = watcher.requests.get(RELEASES_API, timeout=5, headers={"Accept": "application/vnd.github+json"})
            r.raise_for_status()
            data = r.json()
            latest, url = str(data.get("tag_name") or "").lstrip("v"), str(data.get("html_url") or "")
            info["latest"] = latest or None
            if latest and url.startswith(RELEASES_PAGE) and _version_key(latest) > _version_key(APP_VERSION):
                info.update(available=True, url=url)
            expires = now + 6 * 3600
        except (watcher.requests.RequestException, ValueError, AttributeError):
            expires = now + 3600      # offline or rate-limited: try again later
        self._update_cache = (expires, info)
        return info

    def check_update(self) -> dict:
        """Check GitHub now (Settings); the Windows app then downloads in the background."""
        if self.updater is not None:
            self.updater.check_now()
        else:
            self._update_cache = None
        return self.update_info()

    def _old_copy_note(self) -> Path | None:
        return self.updater.dir / "old-copy.txt" if self.updater is not None else None

    def old_copy(self) -> str | None:
        """A ZIP copy this installation replaced, which the user may now delete."""
        note = self._old_copy_note()
        try:
            folder = Path(note.read_text(encoding="utf-8").strip()) if note else None
        except OSError:
            return None
        if not folder or not folder.is_dir() or (self.app_root and folder.resolve() == self.app_root.resolve()):
            return None
        return str(folder)

    def dismiss_old_copy(self) -> dict:
        note = self._old_copy_note()
        if note:
            note.unlink(missing_ok=True)
        return {"ok": True}

    def apply_update(self) -> dict:
        """Run the downloaded, verified installer and stop so it can replace this copy."""
        from updater import UpdateError
        if self.updater is None or self.on_shutdown is None:
            raise ApiError("Updates are installed by the Windows app.")
        try:
            self.updater.apply()
        except (UpdateError, OSError) as exc:
            raise ApiError(f"The update could not start: {exc}") from exc
        if self.app_root and not (self.app_root / "unins000.exe").exists():
            try:       # a ZIP copy: once installed, tell the user this folder can go
                self._old_copy_note().write_text(str(self.app_root), encoding="utf-8")
            except OSError:
                pass
        self.updater.stop()
        threading.Timer(0.5, self.on_shutdown).start()      # the installer waits for this copy to exit
        return {"ok": True}

    # ------------------------------------------------------------ export
    def csv_export(self, params: dict) -> str:
        params = {**flatten(params), "per_page": "200", "facets": "0"}
        first = self.jobs({**params, "page": "1"})
        jobs = list(first["jobs"])
        for page in range(2, min(first["pages"], 50) + 1):
            jobs.extend(self.jobs({**params, "page": str(page)})["jobs"])
        stream = io.StringIO()
        fields = ["fit", "company", "title", "category_label", "subcategory_label", "stage", "level",
                  "cycle_label", "location", "deadline", "app_status", "salary", "url", "first_seen"]
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        # Scraped text starting with = + - @ would run as a spreadsheet formula.
        writer.writerows({k: "'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r") else v
                          for k, v in job.items()} for job in jobs)
        return stream.getvalue()


# ================================================================ HTTP layer
def _required_key(query: dict) -> str:
    """Legacy DELETE /api/applications?key=… form."""
    key = (query.get("key") or [""])[0]
    if not key:
        raise ApiError("key is required")
    return key


def _int(value: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise ApiError("invalid id", HTTPStatus.NOT_FOUND) from exc


ROUTES = [
    ("GET", r"/api/resume", lambda s, m, q, b: s.get_resume()),
    ("POST", r"/api/resume/parse", lambda s, m, q, b: s.parse_resume(b)),
    ("POST", r"/api/resume", lambda s, m, q, b: s.apply_resume(b)),
    ("PATCH", r"/api/resume", lambda s, m, q, b: s.set_resume_enabled(b)),
    ("DELETE", r"/api/resume", lambda s, m, q, b: s.delete_resume()),
    ("GET", r"/api/overview", lambda s, m, q, b: s.overview()),
    ("GET", r"/api/jobs", lambda s, m, q, b: s.jobs(q)),
    ("GET", r"/api/jobs/(?P<key>[^/]+)", lambda s, m, q, b: s.job_detail(unquote(m["key"]))),
    ("POST", r"/api/jobs/(?P<key>[^/]+)/scan", lambda s, m, q, b: s.scan_job(unquote(m["key"]), b)),
    ("PUT", r"/api/jobs/(?P<key>[^/]+)/override", lambda s, m, q, b: s.set_override(unquote(m["key"]), b)),
    ("GET", r"/api/companies", lambda s, m, q, b: s.companies(q)),
    ("GET", r"/api/companies/(?P<key>[^/]+)", lambda s, m, q, b: s.company_detail(unquote(m["key"]))),
    ("PUT", r"/api/companies/(?P<key>[^/]+)/watch", lambda s, m, q, b: s.watch_company(unquote(m["key"]), b)),
    ("GET", r"/api/applications", lambda s, m, q, b: s.applications()),
    ("POST", r"/api/applications", lambda s, m, q, b: s.save_application(b)),
    ("PATCH", r"/api/applications/(?P<key>[^/]+)", lambda s, m, q, b: s.patch_application(unquote(m["key"]), b)),
    ("DELETE", r"/api/applications/(?P<key>[^/]+)", lambda s, m, q, b: s.delete_application(unquote(m["key"]))),
    ("DELETE", r"/api/applications", lambda s, m, q, b: s.delete_application(_required_key(q))),
    ("GET", r"/api/pipeline", lambda s, m, q, b: s.pipeline()),
    ("GET", r"/api/contacts", lambda s, m, q, b: s.contacts(q)),
    ("POST", r"/api/contacts", lambda s, m, q, b: s.create_contact(b)),
    ("PATCH", r"/api/contacts/(?P<id>\d+)", lambda s, m, q, b: s.patch_contact(_int(m["id"]), b)),
    ("DELETE", r"/api/contacts/(?P<id>\d+)", lambda s, m, q, b: s.delete_contact(_int(m["id"]))),
    ("POST", r"/api/contacts/(?P<id>\d+)/log", lambda s, m, q, b: s.log_contact(_int(m["id"]), b)),
    ("GET", r"/api/calendar", lambda s, m, q, b: s.calendar(q)),
    ("POST", r"/api/events", lambda s, m, q, b: s.create_event(b)),
    ("DELETE", r"/api/events/(?P<id>\d+)", lambda s, m, q, b: s.delete_event(_int(m["id"]))),
    ("GET", r"/api/analytics", lambda s, m, q, b: s.analytics(q)),
    ("GET", r"/api/activity", lambda s, m, q, b: s.activity(q)),
    ("GET", r"/api/sources", lambda s, m, q, b: s.sources()),
    ("GET", r"/api/profile", lambda s, m, q, b: s.get_profile()),
    ("PUT", r"/api/profile", lambda s, m, q, b: s.put_profile(b)),
    ("GET", r"/api/discord", lambda s, m, q, b: s.get_discord()),
    ("PUT", r"/api/discord", lambda s, m, q, b: s.put_discord(b)),
    ("PUT", r"/api/discord/settings", lambda s, m, q, b: s.put_discord_settings(b)),
    ("POST", r"/api/discord/test", lambda s, m, q, b: s.test_discord()),
    ("DELETE", r"/api/discord", lambda s, m, q, b: s.delete_discord()),
    ("GET", r"/api/background", lambda s, m, q, b: s.background_info()),
    ("PUT", r"/api/background", lambda s, m, q, b: s.put_background(b)),
    ("POST", r"/api/shutdown", lambda s, m, q, b: s.shutdown()),
    ("GET", r"/api/ai", lambda s, m, q, b: s.get_ai()),
    ("PUT", r"/api/ai", lambda s, m, q, b: s.put_ai(b)),
    ("DELETE", r"/api/ai", lambda s, m, q, b: s.delete_ai()),
    ("PUT", r"/api/ai/reference", lambda s, m, q, b: s.put_cover_reference(b)),
    ("DELETE", r"/api/ai/reference", lambda s, m, q, b: s.delete_cover_reference()),
    ("GET", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.get_cover_letter(unquote(m["key"]))),
    ("POST", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.generate_cover_letter(unquote(m["key"]), b)),
    ("PUT", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.put_cover_letter(unquote(m["key"]), b)),
    ("POST", r"/api/documents/merge", lambda s, m, q, b: s.merge_documents(b)),
    ("GET", r"/api/meta", lambda s, m, q, b: s.meta()),
    ("GET", r"/api/status", lambda s, m, q, b: s.status_info()),
    ("GET", r"/api/update", lambda s, m, q, b: s.update_info()),
    ("POST", r"/api/update/check", lambda s, m, q, b: s.check_update()),
    ("POST", r"/api/update/apply", lambda s, m, q, b: s.apply_update()),
    ("POST", r"/api/update/old-copy/dismiss", lambda s, m, q, b: s.dismiss_old_copy()),
    ("POST", r"/api/refresh", lambda s, m, q, b: s.trigger_poll() if b.get("poll") else (
        s.kick() or {"ok": True, "started": True})),
    ("GET", r"/api/saved-searches", lambda s, m, q, b: s.saved_searches()),
    ("POST", r"/api/saved-searches", lambda s, m, q, b: s.create_saved_search(b)),
    ("PATCH", r"/api/saved-searches/(?P<id>\d+)", lambda s, m, q, b: s.patch_saved_search(_int(m["id"]), b)),
    ("DELETE", r"/api/saved-searches/(?P<id>\d+)", lambda s, m, q, b: s.delete_saved_search(_int(m["id"]))),
]
COMPILED_ROUTES = [(method, re.compile(f"^{pattern}$"), handler) for method, pattern, handler in ROUTES]


class JobwatchHandler(BaseHTTPRequestHandler):
    service: JobwatchService
    allowed_hosts: set[str] = {"127.0.0.1", "localhost", "[::1]", "::1"}
    allow_any_host = False      # only when deliberately bound to 0.0.0.0 / ::
    timeout = 60                # a client that stalls mid-request never holds a thread forever

    def log_message(self, fmt, *args):
        if "/api/" in (args[0] if args else ""):
            return      # keep the console readable; errors still print
        print(f"{self.log_date_time_string()} {fmt % args}")

    def _send(self, body: bytes, content_type="application/json; charset=utf-8",
              status=HTTPStatus.OK, extra_headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; img-src 'self' data:; connect-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'",
        )
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def json(self, value, status=HTTPStatus.OK):
        self._send(json.dumps(value, default=str).encode(), status=status)

    def _reject_unread_body(self, message, status):
        """Deliver early errors before closing a socket with unread upload data.

        Windows can reset such sockets and discard the response. Half-close the
        response first, then briefly drain incoming data with bounded time/work.
        A forged Content-Length must never make rejection wait for a full body.
        """
        self.close_connection = True
        self._send(json.dumps({"error": message}).encode(), status=status,
                   extra_headers={"Connection": "close"})
        self.wfile.flush()
        previous_timeout = self.connection.gettimeout()
        try:
            self.connection.shutdown(socket.SHUT_WR)
            deadline = time.monotonic() + 0.25
            remaining = 6_700_000
            while remaining > 0 and time.monotonic() < deadline:
                self.connection.settimeout(min(0.05, max(0.001, deadline - time.monotonic())))
                chunk = self.rfile.read1(min(65_536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
        except OSError:
            pass  # idle, disconnected, or finished sending the rejected upload
        finally:
            self.connection.settimeout(previous_timeout)

    def _host_ok(self) -> bool:
        """Reject DNS-rebinding requests whose Host is not this machine."""
        if self.allow_any_host:
            return True
        host = self.headers.get("Host") or ""
        name = host[: host.find("]") + 1] if host.startswith("[") else host.split(":")[0]
        return name in self.allowed_hosts

    def _dispatch(self, method: str):
        parsed = urlparse(self.path)
        if not self._host_ok():
            return self._reject_unread_body("forbidden host", HTTPStatus.FORBIDDEN)
        body = {}
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            # Cross-site forms can only send text/plain / form bodies; requiring
            # JSON forces a CORS preflight this server never approves.
            # The Origin must be this exact server, port included: any other
            # local app (another port) is a different site.
            origin = self.headers.get("Origin")
            if origin and not self.allow_any_host and origin.rstrip("/").lower() !=                     f"http://{self.headers.get('Host') or ''}".lower():
                return self._reject_unread_body("cross-origin request refused", HTTPStatus.FORBIDDEN)
            if (self.headers.get("Sec-Fetch-Site") or "same-origin") not in ("same-origin", "none"):
                return self._reject_unread_body("cross-origin request refused", HTTPStatus.FORBIDDEN)
            try:
                length = int(self.headers.get("Content-Length") or 0)
                if length < 0:
                    raise ValueError
            except ValueError:
                return self._reject_unread_body("invalid Content-Length", HTTPStatus.BAD_REQUEST)
            if length:
                media_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if media_type != "application/json":
                    return self._reject_unread_body("Content-Type must be application/json",
                                                    HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
                limit = (34_000_000 if parsed.path == "/api/documents/merge"
                         else 6_700_000 if parsed.path in ("/api/resume", "/api/resume/parse", "/api/ai/reference")
                         else 200_000)
                if length > limit:
                    return self._reject_unread_body("request too large", HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                raw = self.rfile.read(length)
                if len(raw) < length:
                    self.close_connection = True
                    return self.json({"error": "request body ended early"}, HTTPStatus.BAD_REQUEST)
                try:
                    body = json.loads(raw.decode("utf-8") or "{}")
                except (ValueError, RecursionError):      # bad JSON, bad UTF-8 or absurd nesting
                    return self.json({"error": "invalid JSON"}, HTTPStatus.BAD_REQUEST)
                if not isinstance(body, dict):
                    return self.json({"error": "JSON body must be an object"}, HTTPStatus.BAD_REQUEST)
        if parsed.path == "/api/export.csv" and method == "GET":
            try:
                data = self.service.csv_export(parse_qs(parsed.query)).encode()
            except ApiError as exc:
                return self.json({"error": str(exc)}, exc.status)
            except (ValueError, TypeError, OverflowError) as exc:
                return self.json({"error": f"invalid request: {exc}"}, HTTPStatus.BAD_REQUEST)
            return self._send(data, "text/csv; charset=utf-8", extra_headers={
                "Content-Disposition": "attachment; filename=jobwatch-opportunities.csv"})
        if parsed.path.startswith("/api/"):
            path_known = False
            for route_method, pattern, handler in COMPILED_ROUTES:
                match = pattern.match(parsed.path)
                if not match:
                    continue
                path_known = True
                if route_method != method:
                    continue
                try:
                    if method == "GET" and parsed.path in CACHED_PATHS:
                        result = self.service.cached((parsed.path, parsed.query), lambda: handler(
                            self.service, match, parse_qs(parsed.query), body))
                    else:
                        result = handler(self.service, match, parse_qs(parsed.query), body)
                        if method != "GET":
                            self.service.invalidate()
                    if isinstance(result, FileResult):
                        return self._send(result.data, result.content_type, extra_headers={
                            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(result.filename)}"})
                    return self.json(result)
                except ApiError as exc:
                    return self.json({"error": str(exc)}, exc.status)
                except CLIENT_GONE:
                    return      # the browser cancelled this request; nobody is listening
                except (ValueError, TypeError, OverflowError) as exc:
                    # Malformed parameters (page=1e20, a list where text belongs, ...).
                    return self.json({"error": f"invalid request: {exc}"}, HTTPStatus.BAD_REQUEST)
                except Exception as exc:
                    print(f"! {method} {parsed.path}: {type(exc).__name__}: {exc}")
                    return self.json({"error": f"{type(exc).__name__}: {exc}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            status = HTTPStatus.METHOD_NOT_ALLOWED if path_known else HTTPStatus.NOT_FOUND
            return self.json({"error": "method not allowed" if path_known else "not found"}, status)
        if method != "GET":
            return self.json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        return self._static(parsed.path)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_OPTIONS(self):
        self._reject_unread_body("method not allowed", HTTPStatus.METHOD_NOT_ALLOWED)   # no CORS preflight

    def do_HEAD(self):
        self.close_connection = True
        self.send_response(HTTPStatus.METHOD_NOT_ALLOWED)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE")
        self.send_header("Content-Length", "0")
        self.send_header("Connection", "close")
        self.end_headers()

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except CLIENT_GONE:
            self.close_connection = True
        except (TimeoutError, socket.timeout):
            self.close_connection = True        # stalled client: drop it quietly

    def _static(self, path):
        if path in ("", "/", "/index.html"):
            path = "/index.html"
        rel = Path(unquote(path.lstrip("/")))
        if ".." in rel.parts or rel.is_absolute():
            return self.json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        target = (WEB_DIR / rel).resolve()
        if WEB_DIR.resolve() not in target.parents or not target.is_file() or target.suffix not in STATIC_TYPES:
            return self.json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        self._send(target.read_bytes(), STATIC_TYPES[target.suffix])


def serve(host="127.0.0.1", port=8787, open_browser=True, db_path=watcher.DB_PATH,
          config_path=watcher.CONFIG, subscribers_path=watcher.SUBSCRIBERS):
    service = JobwatchService(db_path, config_path, subscribers_path)
    allowed = set(JobwatchHandler.allowed_hosts)
    if host not in ("0.0.0.0", "::"):
        allowed.add(host)
    handler = type("ConfiguredJobwatchHandler", (JobwatchHandler,),
                   {"service": service, "allowed_hosts": allowed,
                    "allow_any_host": host in ("0.0.0.0", "::")})
    server = JobwatchHTTPServer((host, port), handler)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '::') else host}:{server.server_port}"
    print(f"Foothold · Recruiting dashboard → {url}")
    print("Applications, contacts, notes and your profile stay in the local SQLite database.")
    if host not in {"127.0.0.1", "localhost", "::1"}:
        print("WARNING: bound to a non-loopback address. This dashboard has NO authentication —\n"
              "anyone who can reach this port can read and change your private recruiting data.\n"
              "Put it behind an authenticating reverse proxy or VPN, or bind to 127.0.0.1.")
    service.start_background()
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nDashboard stopped.")
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Foothold local recruiting dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--db", default=str(watcher.DB_PATH))
    args = parser.parse_args()
    serve(args.host, args.port, not args.no_browser, args.db)


if __name__ == "__main__":
    main()
