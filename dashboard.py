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
import hashlib
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
from intel.programs import program_windows
from intel import cover_letter, hardware, letterhead, pdf_tools
from intel.resume import MAX_BYTES, MAX_CHARS, ResumeError, extract_text, parse_resume, profile_from_resume, rejoin_runs
from intel.sources import load_config, load_packs, pack_boards, polled_sources, profile_fields
from intel_store import IntelStore, iso_epoch, load_profile, save_profile, utcnow, watched_companies
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
# A posting's resume verdict, with FACTS_VERSION as its parameter: matched (1), ruled out (0) or not yet read (NULL).
RESUME_VERDICT = """CASE WHEN i.facts_version=? THEN (SELECT rm.matched FROM resume_matches rm
    JOIN candidate_resume cr ON cr.id=1 WHERE rm.board=i.board AND rm.job_id=i.job_id
    AND rm.profile_version=i.profile_version AND rm.profile_version=cr.version) END"""
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
STATIC_TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon",
                ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8"}


DISCORD_WEBHOOK = re.compile(r"^https://(?:canary\.|ptb\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")
DISCORD_SUBSCRIBER = "desktop"
RELEASES_API = "https://api.github.com/repos/IdanG7/JobWatcher/releases/latest"
RELEASES_PAGE = "https://github.com/IdanG7/JobWatcher/releases/"
COVER_LIBRARY = 10     # past cover letters kept to adapt from
LETTER_LIMIT = f"the letter must be text up to {cover_letter.MAX_LETTER:,} characters"
# What a letter goes through, in order, as its panel shows while it is written; the past letter is put
# right only when there is one.
LETTER_STEPS = ("Reading the posting", "Reading your resume", "Updating your past letter", "Writing the letter",
                "Checking roles and dates", "Using the posting's words")
STORY_STEP = LETTER_STEPS[2]


def _digest(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:16]


def _needs_digest(job: dict, resume_text: str) -> str:
    """posting_needs is read again when the posting's text or the resume changes."""
    return _digest((job.get("description") or "") + "\n" + resume_text)


def _story_key(model: str, resume_text: str, base_text: str, facts: dict) -> str:
    """Where _story keeps a corrected past letter: per letter, resume, model and its reading, and month."""
    return "letter_story:" + _digest("\n".join((base_text, resume_text, model, json.dumps(facts, sort_keys=True),
                                                date.today().isoformat()[:7])))


def _description_failure(error: str) -> str:
    """Why a description fetch failed, said for the drawer (job_text.last_error is 'Type: message')."""
    if "RateLimited" in error or "429" in error:
        return "the site is limiting requests right now"
    if "404" in error or "410" in error:
        return "the posting may have been taken down"
    if "Timeout" in error or "Connection" in error or re.search(r"\b5\d\d\b", error):
        return "the site didn't answer"
    return "the site sent nothing Foothold could read"


def _letter_text(body) -> bool:
    return isinstance(body, str) and bool(body.strip()) and len(body) <= cover_letter.MAX_LETTER


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
# Also reused until the data changes, but only recomputed when asked (keep_ready leaves them alone).
CACHED_ON_DEMAND = {"/api/saved-searches", "/api/sources", "/api/calendar", "/api/applications"}
CACHE_REFRESH_SECONDS = 30   # how stale a page may be while postings arrive; it is refreshed in the background
CACHE_HOT_SECONDS = 600      # the pages asked for in the last ten minutes are kept ready
CACHE_STALE_SECONDS = 120    # after background changes, a page this old is still shown while it is recomputed
# Changes that leave every cached page as it was (opening a link, an update, a letter): nothing is recomputed.
KEEPS_PAGES = re.compile(r"/api/(open|refresh|shutdown|background|whats-new/seen|update/.+|discord/test|letters/.+"
                         r"|documents/merge|jobs/[^/]+/(cover-letter(/revise)?|recipient(/lookup)?))")


class _Computation:
    """A response being computed, which other requests for it wait for rather than compute it again."""

    def __init__(self, gen: int):
        self.gen, self.done, self.value, self.error = gen, threading.Event(), None, None


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
        # Cover letters: a model download in progress, and Ollama's status for a few seconds.
        self._letters_lock = threading.Lock()
        self._model_download: dict | None = None
        self._ollama_cache: tuple[float, dict] | None = None
        self._computer: dict | None = None        # graphics cards and memory; scanned once
        # Set by the portable launcher, which owns the server and the Windows paths.
        self.on_shutdown = None
        self.autostart_command: str | None = None
        self.log_path: Path | None = None
        self.updater = None                   # updater.Updater in the Windows app
        self.app_root: Path | None = None     # the folder holding app/ and runtime/
        self.config = load_config(self.config_path)
        self.boards = {k: v for k, v in self.config.get("boards", {}).items() if not k.startswith("_")}
        self.kn = load_knowledge()
        self._refresh_lock = threading.Lock()
        self._poll_lock = threading.Lock()
        self._discord_lock = threading.Lock()
        self._update_cache: tuple[float, dict] | None = None
        self._cache: dict = {}           # key -> (gen, data version, computed at, response)
        self._cache_gen = 0              # invalidate() bumps it: nothing from before is served again
        self._cache_lock = threading.Lock()
        self._computing: dict = {}       # key -> _Computation under way
        self._asked: dict = {}           # key -> (last asked at, compute): the pages keep_ready refreshes
        self._ready = threading.Event()  # wakes keep_ready
        self._version_con = None
        self._version_lock = threading.Lock()
        self._status_lock = threading.Lock()
        self._merge_slots = threading.BoundedSemaphore(2)   # each merge can hold ~100 MB of PDFs
        self._describe_lock = threading.Lock()
        self._describing = set()         # postings whose description is being fetched
        self._letters = {}               # a letter being written or changed in the background, by posting
        self._letter_lock = threading.Lock()
        self._letter_turn = threading.Lock()     # the model writes one letter at a time
        # Opening a posting without a description fetches it; turned on with the background
        # work, so tests and tools that build the service never reach the network.
        self.fetch_on_open = False
        # The desktop app (portable_start) runs on the user's own computer, in a window of its own:
        # open_link sends the page's links to other sites to their browser.
        self.desktop = False
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._pending_cache: tuple[float, int] | None = None
        self._resume_pending: tuple[tuple, int] | None = None   # (data version, resume version) -> count
        self.status = {"indexing": False, "last_refresh": None, "last_stats": None,
                       "poll_running": False, "last_poll": None, "error": None, "progress": None}
        con = watcher.db_open(self.db_path)
        self._seed_whats_new(con)        # before the watchlist seed marks the database as opened
        self._import_legacy_watchlist(con)
        self._prune_profile(con)
        self._move_cover_reference(con)
        con.commit()
        con.close()

    # ------------------------------------------------------------ db
    def connect(self):
        con = sqlite3.connect(self.db_path, timeout=10)
        con.execute("PRAGMA busy_timeout=8000")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute(f"PRAGMA mmap_size={watcher.MMAP_SIZE}")
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

    def _seed_whats_new(self, con) -> None:
        """A new install has no release to catch up on, so its version's notes count as read.
        A database a dashboard opened before (the watchlist seed is set on the first start) gets
        no mark, so its first version with release notes shows them."""
        from version import APP_VERSION
        if not con.execute("SELECT 1 FROM kv WHERE k IN ('watchlist_seeded', 'whats_new_seen')").fetchone():
            con.execute("INSERT INTO kv(k, v) VALUES ('whats_new_seen', ?)", (APP_VERSION,))

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
    def data_version(self):
        """A number that changes whenever any connection commits to the database (a poll, scoring, the
        user), read on a connection of its own that never writes. None if it can't be read."""
        with self._version_lock:
            if self._stop.is_set():         # closed (or stopping): don't open the file again
                return None
            try:
                if self._version_con is None:
                    self._version_con = sqlite3.connect(self.db_path, check_same_thread=False)
                return self._version_con.execute("PRAGMA data_version").fetchone()[0]
            except sqlite3.Error:
                return None

    def close(self) -> None:
        """Let go of the database file (Windows can't delete or move a file that is open)."""
        self._stop.set()
        self._ready.set()
        with self._version_lock:
            if self._version_con is not None:
                self._version_con.close()
                self._version_con = None

    def cached(self, key, compute, keep=True, fresh=False):
        """A GET response, kept until the data changes, so moving between pages costs nothing. While
        postings arrive in the background a page is served as it was for up to CACHE_REFRESH_SECONDS, and
        keep_ready recomputes it meanwhile (``keep``). Older than that but younger than CACHE_STALE_SECONDS, it
        is still served at once while it is recomputed in the background (stale-while-revalidate). ``fresh``
        (a Refresh the user clicked) serves only a page computed since the data last changed. After
        invalidate() (a change the user made) it is computed afresh, once however many requests ask for it."""
        return self.cached_page(key, compute, keep, fresh)[0]

    def cached_page(self, key, compute, keep=True, fresh=False):
        """cached(), and whether the page is one kept from before background changes (being recomputed)."""
        now, version = time.monotonic(), self.data_version()
        stale = None
        with self._cache_lock:
            if len(self._asked) > 64:
                self._asked.clear()
            if keep:
                self._asked[key] = (now, compute)
            hit = self._cache.get(key)
            if hit and hit[0] == self._cache_gen:
                if (version is not None and hit[1] == version) or (
                        not fresh and now - hit[2] < CACHE_REFRESH_SECONDS):
                    return hit[3], False
                if not fresh and now - hit[2] < CACHE_STALE_SECONDS:
                    stale = hit
        if stale is not None:
            self._revalidate(key, compute)
            return stale[3], True
        return self._compute(key, compute), False

    def _revalidate(self, key, compute) -> None:
        """Recompute a page in the background, once however many stale reads ask for it."""
        with self._cache_lock:
            if key in self._computing:
                return

        def run():
            try:
                self._compute(key, compute)
            except Exception:       # the next request that computes it hears why
                pass
        threading.Thread(target=run, name="jobwatch-revalidate", daemon=True).start()

    def data_changed(self) -> None:
        """Background work (a poll, facts or scoring) committed: pages in use are refreshed by keep_ready and
        meanwhile served as they were, rather than dropped (invalidate() is for changes the user made)."""
        self._ready.set()

    def _compute(self, key, compute):
        with self._cache_lock:
            gen = self._cache_gen
            computation = self._computing.get(key)
            mine = computation is None or computation.gen != gen     # one begun before a change won't do
            if mine:
                computation = self._computing[key] = _Computation(gen)
        if not mine:
            computation.done.wait()
            if computation.error is not None:
                raise computation.error
            return computation.value
        try:
            version, started = self.data_version(), time.monotonic()
            computation.value = compute()
            with self._cache_lock:
                if gen == self._cache_gen:          # never keep a result computed before a change
                    if len(self._cache) > 64:
                        self._cache.clear()
                    self._cache[key] = (gen, version, started, computation.value)
            return computation.value
        except BaseException as exc:
            computation.error = exc
            raise
        finally:
            with self._cache_lock:
                if self._computing.get(key) is computation:
                    del self._computing[key]
            computation.done.set()

    def invalidate(self) -> None:
        with self._cache_lock:
            self._cache_gen += 1
            self._cache.clear()
        self._ready.set()           # recompute the pages in use now, before they are asked for again

    def keep_ready(self) -> None:
        """Recompute in the background the pages asked for lately whose data changed, so moving to one is
        instant: right after invalidate(), and every CACHE_REFRESH_SECONDS / 2 while postings arrive."""
        while not self._stop.is_set():
            self._ready.wait(5)
            self._ready.clear()
            now, version = time.monotonic(), self.data_version()
            with self._cache_lock:
                self._asked = {k: v for k, v in self._asked.items() if now - v[0] < CACHE_HOT_SECONDS}
                due = [(key, compute) for key, (_, compute) in self._asked.items()
                       if not (hit := self._cache.get(key)) or hit[0] != self._cache_gen
                       or (hit[1] != version and now - hit[2] >= CACHE_REFRESH_SECONDS / 2)]
            for key, compute in due:
                try:
                    self._compute(key, compute)
                except Exception:           # a request that can't be answered: its own asker hears why
                    with self._cache_lock:
                        self._asked.pop(key, None)

    # ------------------------------------------------------------ intelligence refresh
    def refresh_now(self, force_score: bool = False) -> dict:
        with self._refresh_lock:
            self.status["indexing"] = True
            try:
                con = sqlite3.connect(self.db_path, timeout=30)
                con.execute("PRAGMA busy_timeout=15000")
                con.execute("PRAGMA synchronous=NORMAL")   # WAL: safe, fewer disk flushes
                con.execute(f"PRAGMA mmap_size={watcher.MMAP_SIZE}")
                try:
                    backlog = self.pending_facts(con)
                    store = IntelStore(con, self.config)
                    # Count down as batches land, so a long re-rank after an update shows what's left.
                    stats = store.refresh(force_score=force_score, on_progress=lambda done: setattr(
                        self, "_pending_cache", (time.time(), max(0, backlog - done))))
                finally:
                    con.close()
                self.status.update(last_refresh=utcnow(), last_stats=stats, error=None)
                self._pending_cache = None
                if stats.get("facts") or stats.get("scored"):
                    self.data_changed()
                return stats
            except Exception as exc:   # surfaced in /api/status, never crashes the server
                self.status["error"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                self.status["indexing"] = False

    def start_background(self, interval: int = 60) -> None:
        self.fetch_on_open = True

        def loop():
            while not self._stop.is_set():
                try:
                    self.refresh_now()
                except Exception:
                    pass
                self._wake.wait(interval)
                self._wake.clear()
        threading.Thread(target=loop, name="jobwatch-intel", daemon=True).start()
        threading.Thread(target=self.keep_ready, name="jobwatch-pages", daemon=True).start()

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
            # Evaluate the (multi-join) filter once. With resume matching on, the pass leaves the resume
            # out and notes each row's verdict instead: matched (1), ruled out (0) or not yet read (NULL).
            # The list's count, the resume totals and every facet then come from those rows.
            if resume["active"]:
                scan_where, scan_args = build_where({**params, "resume_match": "0"}, store_fts, self.watched(con))
                verdict = RESUME_VERDICT
                scan_args = [FACTS_VERSION, *scan_args]
            else:
                scan_where, verdict, scan_args = where, "1", args
            con.execute("CREATE TEMP TABLE IF NOT EXISTS _match(rid INTEGER PRIMARY KEY, matched INTEGER)")
            con.execute("DELETE FROM _match")
            con.execute(f"INSERT INTO _match SELECT i.rowid, {verdict} {FROM_CLAUSE} WHERE {' AND '.join(scan_where)}",
                        scan_args)
            verdicts = dict(con.execute("SELECT matched, COUNT(*) FROM _match GROUP BY matched").fetchall())
            total = verdicts.get(1, 0)
            rows = con.execute(
                f"SELECT {SELECT_COLUMNS} {FROM_CLAUSE} WHERE {clause} ORDER BY {build_order(params)} "
                f"LIMIT ? OFFSET ?", [*args, per_page, (page - 1) * per_page]).fetchall()
            jobs = [self._row(r) for r in rows]
            resume["unfiltered_total"] = sum(verdicts.values())
            resume["excluded_total"] = verdicts.get(0, 0)
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
                                WHERE m.matched=1 AND i.{column} IS NOT NULL
                                GROUP BY i.{column} ORDER BY COUNT(*) DESC LIMIT 25""")]
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
            text = con.execute("SELECT CAST(description AS BLOB) AS description, department, source, fetched_at, "
                               "attempts, last_error FROM job_text WHERE board=? AND job_id=?", (board, job_id)).fetchone()
            job["description"] = bytes(text["description"] or b"").decode("utf-8", "replace") if text else ""
            job["department"] = text["department"] if text else ""
            job["description_source"] = text["source"] if text else ""
            # True while this posting's missing description is fetched and scored, so the drawer checks back.
            job["description_pending"] = self._describe_later(job, text)
            # Why the last fetch failed, while there is still no description: the drawer offers to try again.
            job["description_failed"] = (_description_failure(text["last_error"]) if text and text["last_error"]
                                         and not job["description"].strip() and not job["description_pending"] else "")
            members = con.execute(
                """SELECT i.board, i.job_id, j.url, j.first_seen, i.is_canonical
                   FROM job_intel i JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
                   WHERE i.cluster_key=? ORDER BY j.first_seen""", (job["cluster_key"],)).fetchall()
            job["sources"] = [{"board": m["board"], "label": self.source_label(m["board"]),
                               "kind": self.source_kind(m["board"]), "url": m["url"],
                               "first_seen": m["first_seen"], "canonical": bool(m["is_canonical"]),
                               "key": f"{m['board']}:{m['job_id']}"} for m in members]
            job["discovered_from"] = sorted({s["label"] for s in job["sources"]})
            job["description_from"] = ""
            others = [(m["board"], m["job_id"]) for m in members if (m["board"], m["job_id"]) != (board, job_id)]
            if not job["description"].strip() and others:
                # LinkedIn keeps only the title and city; the company's own copy of the job has the text.
                copy = con.execute(
                    "SELECT board, CAST(description AS BLOB) AS description, department FROM job_text WHERE ("
                    + " OR ".join("(board=? AND job_id=?)" for _ in others)
                    + ") AND COALESCE(description, '') != '' ORDER BY LENGTH(description) DESC LIMIT 1",
                    [v for pair in others for v in pair]).fetchone()
                if copy:
                    job["description"] = bytes(copy["description"]).decode("utf-8", "replace")
                    job["department"] = job["department"] or copy["department"] or ""
                    job["description_from"] = self.source_label(copy["board"])
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

    def _describe_later(self, job: dict, text, force: bool = False) -> bool:
        """Start fetching a posting's missing description in the background, with the poll's
        back-off (retried after 6 hours, 3 attempts at most) unless forced (the drawer's Try again).
        True until that fetch and the re-scoring after it finish."""
        key, cfg = job["key"], self.boards.get(job["board"])
        with self._describe_lock:
            if key in self._describing:
                return True
            if (job["description"].strip() or not self.fetch_on_open or not cfg or cfg.get("disabled")
                    or not watcher.describable(cfg, on_open=True) or len(self._describing) >= 4):
                return False
            if not force and text and (text["attempts"] >= watcher.DESCRIPTION_ATTEMPTS
                                       or (text["fetched_at"] or "") >= watcher.description_retry_before()):
                return False
            self._describing.add(key)
        threading.Thread(target=self._describe, args=(cfg, job["board"], job["job_id"], job["url"]),
                         name="jobwatch-describe", daemon=True).start()
        return True

    def _describe(self, cfg: dict, board: str, job_id: str, url: str) -> None:
        """Fetch and store one description; the network wait never holds a DB lock."""
        try:
            try:
                result = watcher.fetch_description(cfg, job_id, url)
            except Exception as exc:        # recorded, so it backs off like the poll's fetches
                with self.db() as con:
                    watcher.record_description_error(con, board, job_id, exc)
                return
            with self.db() as con:
                watcher.save_description(con, board, job_id, result)
            with self.db() as con:
                store = IntelStore(con, self.config)
                store.facts_pass(keys=[(board, job_id)])
                store.score_pass(keys=[(board, job_id)])
            self._pending_cache = None
            self.data_changed()
        except Exception as exc:            # a busy or closed database: the next open tries again
            watcher.log(f"! description fetch for {board}:{job_id} failed: {type(exc).__name__}: {exc}")
        finally:
            with self._describe_lock:
                self._describing.discard(f"{board}:{job_id}")

    def open_link(self, payload: dict) -> dict:
        """Open another site's page in the user's browser, where their sign-ins are, rather than in
        Foothold's window. Only http(s), and only in the desktop app."""
        url = payload.get("url")
        parts = urlparse(url) if isinstance(url, str) and len(url) <= 4000 else None
        if not parts or parts.scheme not in ("http", "https") or not parts.netloc:
            raise ApiError("only http and https links open")
        if not self.desktop:
            raise ApiError("links open in your browser only in the desktop app", HTTPStatus.CONFLICT)
        webbrowser.open(url)
        return {"opened": True}

    def retry_description(self, key: str) -> dict:
        """Fetch a missing description now, past the back-off: the drawer's Try again."""
        job = self.job_detail(key)
        if job["description_pending"] or job["description"].strip():
            return {"pending": job["description_pending"]}
        board, _, job_id = key.partition(":")
        with self.db() as con:
            text = con.execute("SELECT fetched_at, attempts FROM job_text WHERE board=? AND job_id=?",
                               (board, job_id)).fetchone()
        if not self._describe_later(job, text, force=True):
            raise ApiError("This posting's description can't be fetched from here; read it on the posting.")
        return {"pending": True}

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
            # The same counts Settings shows: shared through the response cache rather than counted twice.
            searches = self.cached(("/api/saved-searches", ""), self.saved_searches, keep=False)["saved_searches"]
            pending = self.pending_facts(con)
            pipeline = dict(con.execute("SELECT status, COUNT(*) FROM applications GROUP BY status").fetchall())
        enabled = len(polled_sources(self.config, profile, self.kn))      # the sources this profile's boards poll
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
                   -- Split at the first ':' as save_application does, so the primary keys are used
                   -- (the bare expression join read both tables in full once per application).
                   LEFT JOIN job_intel i ON i.board=substr(a.job_key, 1, instr(a.job_key, ':') - 1)
                        AND i.job_id=substr(a.job_key, instr(a.job_key, ':') + 1) AND a.job_key=(i.board||':'||i.job_id)
                   LEFT JOIN job_state s ON s.board=substr(a.job_key, 1, instr(a.job_key, ':') - 1)
                        AND s.job_id=substr(a.job_key, instr(a.job_key, ':') + 1) AND a.job_key=(s.board||':'||s.job_id)
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
            keep, keep_args = "i.fit >= ?", [digest]
            resume = con.execute("SELECT enabled FROM candidate_resume WHERE id=1").fetchone()
            if resume and resume["enabled"]:
                # With a resume on, deadlines are its matches in your boards; a posting it hasn't read
                # yet (a rescore after an update) keeps the fit rule until it has.
                fields = profile_fields(profile, self.kn)
                boards = " OR ".join("i.is_finance=1" if f == "finance" else "i.family=?" for f in fields)
                keep = f"({boards}) AND COALESCE({RESUME_VERDICT}, i.fit >= ?)"
                keep_args = [f for f in fields if f != "finance"] + [FACTS_VERSION, digest]
            for r in con.execute(
                    f"""SELECT i.board, i.job_id, i.eff_deadline, i.company_name, j.title, i.fit, i.deadline_confidence,
                               j.url, a.status
                        {FROM_CLAUSE} WHERE i.eff_deadline BETWEEN ? AND ? AND i.is_canonical=1
                        AND COALESCE(s.status,'active')!='closed' AND (a.status IS NOT NULL OR ({keep}))
                        ORDER BY i.eff_deadline LIMIT 300""", (start, end, *keep_args)):
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
            items += program_windows(profile, self.kn, start, end)
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
            # Summed in SQL: one row per source instead of every posting through Python. Shared = in a
            # cluster of two or more; first = found at the cluster's earliest first sighting. Sources come in
            # the order a scan of jobs first meets them, as the row-by-row loop did, so ties sort the same.
            per_board = {}
            for board, jobs, fin, high, fit_sum, shared, first in con.execute(
                    """WITH firsts AS (SELECT i.cluster_key, MIN(j.first_seen) first_seen FROM job_intel i
                                       JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id GROUP BY i.cluster_key
                                       HAVING COUNT(*) > 1)
                       SELECT i.board, COUNT(*), SUM(COALESCE(i.is_finance, 0)), SUM(COALESCE(i.fit, 0) >= 75),
                              SUM(COALESCE(i.fit, 0)), SUM(COALESCE(f.hit, 0)),
                              SUM(COALESCE(f.hit, 0) AND j.first_seen IS f.first_seen)
                       FROM jobs j JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
                       LEFT JOIN (SELECT *, 1 hit FROM firsts) f ON f.cluster_key IS i.cluster_key
                       WHERE j.title != '' GROUP BY i.board ORDER BY MIN(j.rowid)"""):
                per_board[board] = {"jobs": jobs, "finance": fin, "high_fit": high, "fit_sum": fit_sum,
                                    "shared": shared, "first": first or 0}
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
            profile = self.profile(con)
            # Open roles in this profile's boards, as Opportunities counts them ('finance' = any finance category).
            fields = profile_fields(profile, self.kn)
            yours = " OR ".join("i.is_finance=1" if f == "finance" else "i.family=?" for f in fields)
            counts = {r[0]: (r[1], r[2], r[3]) for r in con.execute(
                f"""SELECT i.board, COUNT(*), SUM({yours}), SUM(i.fit >= 75) FROM job_intel i
                   LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
                   WHERE COALESCE(s.status,'active')!='closed' GROUP BY i.board""",
                [f for f in fields if f != "finance"])}
            last_run = con.execute("SELECT * FROM runs ORDER BY rowid DESC LIMIT 1").fetchone()
            coverage = {}
            for r in con.execute("SELECT k,v FROM kv WHERE k LIKE 'source_coverage:%'"):
                try:
                    coverage[r[0].split(':', 1)[1]] = json.loads(r[1])
                except (ValueError, TypeError):
                    pass
        packs = load_packs()
        polled = polled_sources(self.config, profile, self.kn, packs)       # what this profile's boards poll
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
            jobs, yours, high = counts.get(name, (0, 0, 0))
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
                "jobs": jobs or 0, "board_jobs": yours or 0, "high_fit": high or 0,
                "coverage": coverage.get(name),
                "pack": packs.source_pack.get(name, ""), "polled": name in polled,
            })
        sources.sort(key=lambda s: (s["disabled"], -s["failures"], s["group"] or "", s["label"]))
        labels = {"finance": "Finance", **{f["key"]: f["label"] for f in self.kn.family_tree()}}
        boards, everywhere = pack_boards(self.kn, packs)
        return {"sources": sources, "last_run": dict(last_run) if last_run else None,
                "boards": [labels.get(f, f) for f in fields],
                "packs": [{"key": key, "title": pack.title, "verified": pack.verified,
                           "boards": [labels.get(f, f) for f in boards[key]]} for key, pack in packs.packs.items()],
                "every_pack": [labels.get(f, f) for f in everywhere]}

    # ------------------------------------------------------------ profile & meta
    def _update_resume_version(self, con) -> str:
        version = profile_version(self.profile(con), sorted(self.watched(con)))
        con.execute("UPDATE candidate_resume SET version=? WHERE id=1", (version,))
        return version

    def _resume_status(self, con, include_parsed=False) -> dict:
        row = con.execute("SELECT * FROM candidate_resume WHERE id=1").fetchone()
        if not row:
            return {"available": False, "enabled": False, "pending": 0}
        # A full count over every posting (~2 s on a large database), the same for every list, saved view and
        # page until the database changes: counted once per data version. The version is read before
        # counting, so a commit during the count only makes the next caller count again. Only once the
        # response cache has opened its version connection (any page asked for), so nothing new holds the file.
        key = (self.data_version() if self._version_con is not None else None, row["version"])
        known = self._resume_pending
        if key[0] is not None and known and known[0] == key:
            pending = known[1]
        else:
            # facts_version is written with facts, so this never reads the facts themselves (a third of the table).
            pending = con.execute("""SELECT COUNT(*) FROM jobs j LEFT JOIN job_intel i
                ON i.board=j.board AND i.job_id=j.job_id LEFT JOIN resume_matches rm
                ON rm.board=j.board AND rm.job_id=j.job_id WHERE j.title!='' AND
                (i.facts_version IS NOT ? OR rm.profile_version IS NULL OR rm.profile_version!=?
                 OR i.profile_version IS NULL OR i.profile_version!=?)""",
                (FACTS_VERSION, row["version"], row["version"])).fetchone()[0]
            self._resume_pending = (key, pending)
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

    # ------------------------------------------------------------ cover letters (local model)
    def _move_cover_reference(self, con) -> None:
        """0.3.2 and earlier kept a single past letter; it becomes the first one in the list."""
        row = con.execute("SELECT v FROM kv WHERE k='cover_reference'").fetchone()
        if not row:
            return
        old = json.loads(row[0])
        text = rejoin_runs(old["text"])     # Google Docs PDFs used to come out one word per line
        letters = self._cover_references(con)
        letter_id = hashlib.sha1(text.encode()).hexdigest()[:12]
        if not any(letter["id"] == letter_id for letter in letters):
            letters.insert(0, {"id": letter_id, "filename": old["filename"], "text": text,
                               "added_at": old.get("updated_at") or utcnow()})
            self._save_cover_references(con, letters)
        con.execute("DELETE FROM kv WHERE k='cover_reference'")

    @staticmethod
    def _cover_references(con) -> list[dict]:
        row = con.execute("SELECT v FROM kv WHERE k='cover_references'").fetchone()
        return json.loads(row[0]) if row else []

    @staticmethod
    def _save_cover_references(con, letters: list[dict]) -> None:
        con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cover_references', ?)", (json.dumps(letters),))

    @staticmethod
    def _recipients(con) -> dict:
        """Addresses the user confirmed, by company and city: {place_key: {"lines", "saved_at"}}."""
        row = con.execute("SELECT v FROM kv WHERE k='cover_recipients'").fetchone()
        return json.loads(row[0]) if row else {}

    def _ollama(self, fresh: bool = False) -> dict:
        cached = self._ollama_cache
        if fresh or not cached or time.time() - cached[0] > 10:
            cached = (time.time(), cover_letter.status())
            self._ollama_cache = cached
        return cached[1]

    @staticmethod
    def _cover_model(con, installed: list[str]) -> str:
        row = con.execute("SELECT v FROM kv WHERE k='cover_model'").fetchone()
        return cover_letter.choose_model(row[0] if row else "", installed)

    def letters_info(self, fresh: bool = True) -> dict:
        ollama = self._ollama(fresh)
        with self.db() as con:
            model = self._cover_model(con, ollama["models"])
            letters = self._cover_references(con)
        with self._letters_lock:
            download = dict(self._model_download) if self._model_download else None
        if self._computer is None:
            self._computer = hardware.scan()
        return {"ollama": ollama, "model": model, "computer": self._computer,
                "suggestions": cover_letter.suggest_models(self._computer, ollama["models"]),
                "download": download, "max_letters": COVER_LIBRARY,
                "references": [{"id": letter["id"], "filename": letter["filename"], "chars": len(letter["text"]),
                                "added_at": letter["added_at"], "signature": bool(letter.get("signature")),
                                # a PDF saved before Foothold kept signatures: adding it again picks its signature up
                                "add_again": letter["filename"].lower().endswith(".pdf") and "checked" not in letter}
                               for letter in letters]}

    def put_letters_model(self, payload: dict) -> dict:
        model = payload.get("model")
        if model not in self._ollama(fresh=True)["models"]:
            raise ApiError("Choose a model Ollama has downloaded.")
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cover_model', ?)", (model,))
        return self.letters_info(fresh=False)

    def download_model(self, payload: dict) -> dict:
        model = payload.get("model") or cover_letter.DEFAULT_MODEL
        if not isinstance(model, str) or not cover_letter.MODEL_NAME.fullmatch(model):
            raise ApiError("model must be an Ollama model name such as qwen3:8b")
        if not self._ollama(fresh=True)["running"]:
            raise ApiError(cover_letter.NOT_RUNNING)
        with self._letters_lock:
            if self._model_download and self._model_download["state"] == "running":
                raise ApiError(f"{self._model_download['model']} is already downloading.")
            self._model_download = {"model": model, "state": "running", "completed": 0, "total": 0, "error": ""}

        def run():
            def progress(completed, total):
                with self._letters_lock:
                    self._model_download.update(completed=completed, total=total)
            try:
                cover_letter.pull(model, progress)
                outcome = {"state": "done"}
            except cover_letter.CoverLetterError as exc:
                outcome = {"state": "failed", "error": str(exc)}
            except Exception as exc:      # a background thread must still report how it ended
                outcome = {"state": "failed", "error": f"{type(exc).__name__}: {exc}"}
            with self._letters_lock:
                self._model_download.update(outcome)
            self._ollama_cache = None     # list the new model
        threading.Thread(target=run, name="foothold-model-download", daemon=True).start()
        return self.letters_info(fresh=False)

    def add_cover_reference(self, payload: dict) -> dict:
        filename, text = self._document_text(payload, "cover letter")
        if len(text.strip()) < 200:
            raise ApiError("That letter is too short to learn from; upload a complete past cover letter.")
        # A signature drawn as an image isn't in the text; it is kept to sign the letters adapted from this one.
        pdf = "text" not in payload and filename.lower().endswith(".pdf")
        signature = pdf_tools.letter_signature(base64.b64decode(payload["data"])) if pdf else None
        # 'checked': this PDF was looked at for a signature (letters saved before that have no such key)
        found = {"checked": True, **({"signature": signature} if signature else {})} if pdf else {}
        letter_id = hashlib.sha1(text.encode()).hexdigest()[:12]
        with self.db() as con:
            letters = self._cover_references(con)
            saved = next((letter for letter in letters if letter["id"] == letter_id), None)
            if saved and ("checked" in saved or not pdf):
                raise ApiError(f"{filename} is already saved.")
            if saved:
                saved.update(found)                 # saved before Foothold kept signatures
            elif len(letters) >= COVER_LIBRARY:
                raise ApiError(f"Keep up to {COVER_LIBRARY} past letters; remove one first.")
            else:
                letters.append({"id": letter_id, "filename": filename, "text": text, "added_at": utcnow(), **found})
            self._save_cover_references(con, letters)
        return self.letters_info(fresh=False)

    def delete_cover_reference(self, letter_id: str) -> dict:
        with self.db() as con:
            letters = self._cover_references(con)
            kept = [letter for letter in letters if letter["id"] != letter_id]
            if len(kept) == len(letters):
                raise ApiError("past letter not found", HTTPStatus.NOT_FOUND)
            self._save_cover_references(con, kept)
        return self.letters_info(fresh=False)

    def get_cover_letter(self, key: str, job: dict | None = None) -> dict:
        ollama = self._ollama()
        job = job or self.job_detail(key)
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            has_resume = bool(con.execute("SELECT 1 FROM kv WHERE k='resume_text'").fetchone())
            model = self._cover_model(con, ollama["models"])
            references = len(self._cover_references(con))
            recipient = letterhead.recipient(job, self._recipients(con), self._details(con, key, job))
        return {"letter": json.loads(row[0]) if row else None, "running": ollama["running"], "model": model,
                "resume": has_resume, "references": references, "recipient": recipient,
                "writing": self._writing(key)}

    def _writing(self, key: str) -> dict | None:
        """The letter being written or changed for this posting (the step it is on; -1 while another posting's
        letter goes first), or why the last try failed, for ten minutes."""
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(timespec="seconds")
        with self._letter_lock:
            entry = self._letters.get(key)
            if entry and entry.get("finished_at") and entry["finished_at"] < cutoff:
                del self._letters[key]
                entry = None
            return dict(entry) if entry else None

    def start_cover_letter(self, key: str, payload: dict) -> dict:
        """Write the letter in the background and answer at once. The panel follows it through get_cover_letter,
        so reopening the posting shows it under way, and a second click starts nothing."""
        setup = self._letter_setup(key, payload)
        steps = self._letter_steps(key, setup)
        self._in_background(key, "write", steps, lambda progress: self.generate_cover_letter(key, payload, progress, setup))
        return self.get_cover_letter(key, setup["job"])

    def start_revision(self, key: str, payload: dict) -> dict:
        """revise_cover_letter in the background, followed like a new letter."""
        setup = self._revision_setup(key, payload)
        self._in_background(key, "revise", ["Making the change"],
                            lambda progress: self.revise_cover_letter(key, payload, progress, setup))
        return self.get_cover_letter(key, setup["job"])

    def _in_background(self, key: str, kind: str, steps: list, work) -> None:
        with self._letter_lock:
            if key in self._letters and "error" not in self._letters[key]:
                return                      # under way already
            entry = {"kind": kind, "steps": steps, "step": -1, "started_at": utcnow()}
            self._letters[key] = entry

        def progress(step: str) -> None:       # a step left out of steps takes no time: the bar stays put
            if step in steps:
                with self._letter_lock:
                    entry["step"] = max(entry["step"], steps.index(step))

        def run() -> None:
            error = None
            try:
                with self._letter_turn:
                    progress(steps[0])          # its turn: no longer waiting for another posting's letter
                    work(progress)
            except ApiError as exc:
                error = str(exc)
            except Exception as exc:        # a model or database failure: said in the panel, logged here
                watcher.log(f"! cover letter for {key} failed: {type(exc).__name__}: {exc}")
                error = "The letter couldn't be written. Try again."
            with self._letter_lock:
                if error:
                    entry.update(error=error, finished_at=utcnow())
                elif self._letters.get(key) is entry:
                    del self._letters[key]

        threading.Thread(target=run, name="foothold-letter", daemon=True).start()

    @staticmethod
    def _details(con, key: str, job: dict) -> dict:
        """What the model read in this posting's text (read_posting_details), while the text is unchanged."""
        row = con.execute("SELECT v FROM kv WHERE k=?", ("posting_details:" + key,)).fetchone()
        details = json.loads(row[0]) if row else {}
        return details if details.get("text") == _digest(job.get("description") or "") else {}

    def resume_facts(self, resume_text: str, model: str) -> dict:
        """The resume's roles and credentials (cover_letter.read_facts), read once per resume text and model.
        {} without a resume or when the model can't say: letters then go by the dates the code can read."""
        if not resume_text.strip():
            return {}
        digest = _digest(resume_text)
        saved = self._reading("resume_facts", digest, model)
        if saved:
            return saved["facts"]
        try:
            facts = cover_letter.read_facts(model, resume_text)
        except cover_letter.CoverLetterError:
            return {}
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('resume_facts', ?)", (json.dumps(
                {"facts": facts, "text": digest, "model": model, "read_at": utcnow()}),))
        return facts

    def posting_needs(self, key: str, job: dict, resume_text: str, model: str) -> list[dict]:
        """What the posting stresses most and the resume experience that shows each (cover_letter.key_requirements),
        read once per posting text and resume. [] when the model can't say."""
        digest = _needs_digest(job, resume_text)
        saved = self._reading("posting_needs:" + key, digest, model)
        if saved:
            return saved["needs"]
        try:
            needs = cover_letter.key_requirements(model, job, resume_text)
        except cover_letter.CoverLetterError:
            return []               # the letter is written without them
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("posting_needs:" + key, json.dumps(
                {"needs": needs, "text": digest, "model": model, "read_at": utcnow()})))
        return needs

    def read_posting_details(self, key: str, job: dict, model: str) -> dict:
        """The office street, floor, city and contact the posting states, read by the local model once per
        posting text, with the postal code OpenStreetMap has for that street. {} without a model or text."""
        with self.db() as con:
            details = self._details(con, key, job)
        if not details and model and (job.get("description") or "").strip():
            try:
                details = {**cover_letter.read_details(model, job), "text": _digest(job["description"]),
                           "model": model, "read_at": utcnow()}
            except cover_letter.CoverLetterError:
                return {}           # the letter, or the address search, goes on without it
        if details.get("street") and not details.get("postcode"):
            place = job.get("location") or details.get("city") or ""
            try:
                details.update(letterhead.locate(details["street"], place, self._osm_agent()))
            except LookupError:
                pass                # offline: tried again next time
        if details:
            with self.db() as con:
                con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("posting_details:" + key, json.dumps(details)))
        return details

    @staticmethod
    def _osm_agent() -> str:
        from version import APP_VERSION
        return f"Foothold/{APP_VERSION} (+https://github.com/IdanG7/JobWatcher)"

    def _letter_setup(self, key: str, payload: dict) -> dict:
        """What a letter for this posting is written from, checked before any model work so a missing piece
        is said at once."""
        notes = payload.get("notes") or ""
        if not isinstance(notes, str) or len(notes) > cover_letter.MAX_NOTES:
            raise ApiError(f"notes must be text up to {cover_letter.MAX_NOTES} characters")
        ollama = self._ollama(fresh=True)
        if not ollama["running"]:
            raise ApiError(cover_letter.NOT_RUNNING)
        job = self.job_detail(key)
        with self.db() as con:
            resume = con.execute("SELECT v FROM kv WHERE k='resume_text'").fetchone()
            model = self._cover_model(con, ollama["models"])
            letters = self._cover_references(con)
            saved = self._recipients(con)
        if not model:
            raise ApiError("Download a writing model in Settings › Cover letters first.")
        if not resume:
            raise ApiError("Upload your resume in Settings first; the letter is written from it.")
        return {"notes": notes, "job": job, "resume": resume[0], "model": model, "letters": letters, "saved": saved,
                "base": cover_letter.pick_reference(job, letters, self.kn)}

    def generate_cover_letter(self, key: str, payload: dict, progress=None, setup: dict | None = None) -> dict:
        """Write and save the letter; progress(step) hears each of LETTER_STEPS as it starts."""
        setup = setup or self._letter_setup(key, payload)
        step = progress or (lambda name: None)
        job, model, resume, base = setup["job"], setup["model"], setup["resume"], setup["base"]
        base_text = base["text"] if base else ""
        step("Reading the posting")
        details = {}
        if letterhead.recipient(job, setup["saved"])["source"] == "city":     # no address yet: the posting may say it
            details = self.read_posting_details(key, job, model)
        recipient = letterhead.recipient(job, setup["saved"], details)["lines"]
        needs = self.posting_needs(key, job, resume, model)
        step("Reading your resume")
        facts = self.resume_facts(resume, model)
        try:
            story = ""
            if base_text:
                step(STORY_STEP)
                story = self._story(model, resume, base_text, facts)
            messages = cover_letter.build_prompt(job, resume, story, setup["notes"], recipient=recipient, needs=needs,
                                                 facts=facts)
            step("Writing the letter")
            text = cover_letter.sign_as(cover_letter.generate(model, messages), resume)
        except cover_letter.CoverLetterError as exc:
            raise ApiError(str(exc)) from exc
        step("Checking roles and dates")
        text = cover_letter.keep_experiences(story, text, facts)
        text = cover_letter.check_status(model, job, resume, text, facts)
        step("Using the posting's words")
        text = cover_letter.tailor(model, job, resume, text, needs)
        # The top of the letter is set here, not left to the model, which drops or garbles these lines.
        sender = letterhead.sender([base_text] + [letter["text"] for letter in setup["letters"]], resume)
        text = letterhead.set_header(text, sender, letterhead.date_line(date.today(), base_text), recipient)
        if details.get("contact") and recipient[0] == details["contact"]:
            text = letterhead.greet(text, details["contact"])
        text = letterhead.sign_off(text, letterhead.candidate_name(resume))
        letter = {"body": text, "model": model, "references": [base["filename"]] if base else [],
                  "notes": setup["notes"], "created_at": utcnow(), "edited": False,
                  "needs": cover_letter.coverage(text, needs)}
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return {**self.get_cover_letter(key, job), "letter": letter}

    def _story(self, model: str, resume_text: str, base_text: str, facts: dict) -> str:
        """The past letter with its statuses put right first, in its words (cover_letter.check_status): asked to
        change them while it adapts the letter, the model drops or swaps the sentences instead (the candidate's
        story with them). It doesn't depend on the posting, so it is kept per letter, resume and model, and done
        again each month as roles end."""
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k=?", (_story_key(model, resume_text, base_text, facts),)).fetchone()
        if row:
            return json.loads(row[0])["story"]
        story = cover_letter.check_status(model, {}, resume_text, base_text, facts)
        stale = (datetime.now(timezone.utc) - timedelta(days=62)).isoformat(timespec="seconds")
        with self.db() as con:
            con.execute("DELETE FROM kv WHERE k LIKE 'letter_story:%' AND json_extract(v, '$.at') < ?", (stale,))
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", (_story_key(model, resume_text, base_text, facts),
                                                                          json.dumps({"story": story, "at": utcnow()})))
        return story

    def _reading(self, k: str, digest: str, model: str) -> dict | None:
        """A model's reading kept in kv under k, while what it read (digest) and the model are the same."""
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k=?", (k,)).fetchone()
        saved = json.loads(row[0]) if row else {}
        return saved if saved.get("text") == digest and saved.get("model") == model else None

    def _letter_steps(self, key: str, setup: dict) -> list[str]:
        """The LETTER_STEPS this letter goes through. A reading kept from an earlier letter takes no time, so the
        panel leaves it out rather than show a step that flashes by."""
        job, resume, model, base = setup["job"], setup["resume"], setup["model"], setup["base"]
        with self.db() as con:
            details = self._details(con, key, job)
        address = (letterhead.recipient(job, setup["saved"])["source"] == "city" and not details
                   and (job.get("description") or "").strip())
        posting = address or not self._reading("posting_needs:" + key, _needs_digest(job, resume), model)
        facts = self._reading("resume_facts", _digest(resume), model)
        story = False
        if base and base["text"]:
            with self.db() as con:
                story = not (facts and con.execute("SELECT 1 FROM kv WHERE k=?", (
                    _story_key(model, resume, base["text"], facts["facts"]),)).fetchone())
        return [step for step, needed in zip(LETTER_STEPS, (posting, not facts, story, True, True, True)) if needed]

    def _revision_setup(self, key: str, payload: dict) -> dict:
        change, body = payload.get("request"), payload.get("body")
        if not isinstance(change, str) or not change.strip() or len(change) > cover_letter.MAX_NOTES:
            raise ApiError(f"describe the change in up to {cover_letter.MAX_NOTES} characters")
        if body is not None and not _letter_text(body):
            raise ApiError(LETTER_LIMIT)
        ollama = self._ollama(fresh=True)
        if not ollama["running"]:
            raise ApiError(cover_letter.NOT_RUNNING)
        job = self.job_detail(key)
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            resume = con.execute("SELECT v FROM kv WHERE k='resume_text'").fetchone()
            model = self._cover_model(con, ollama["models"])
        if not row:
            raise ApiError("Write a letter first, then ask for changes.")
        if not model:
            raise ApiError("Download a writing model in Settings › Cover letters first.")
        letter = json.loads(row[0])
        return {"job": job, "letter": letter, "current": body or letter["body"], "change": change,
                "resume": resume[0] if resume else "", "model": model}

    def revise_cover_letter(self, key: str, payload: dict, progress=None, setup: dict | None = None) -> dict:
        """Make the one change the user asked for, in the letter as they see it (unsaved edits included)."""
        setup = setup or self._revision_setup(key, payload)
        job, letter, current, model, resume_text = setup["job"], setup["letter"], setup["current"], setup["model"], setup["resume"]
        if progress:
            progress("Making the change")
        try:
            text = cover_letter.revise(model, job, resume_text, current, setup["change"],
                                       facts=self.resume_facts(resume_text, model))
        except cover_letter.CoverLetterError as exc:
            raise ApiError(str(exc)) from exc
        text = letterhead.sign_off(cover_letter.sign_as(text, resume_text), letterhead.candidate_name(resume_text))
        letter.update(body=text, model=model, needs=cover_letter.coverage(text, letter.get("needs") or []),
                      edited=bool(letter.get("edited")) or current != letter["body"])
        with self.db() as con:
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return {**self.get_cover_letter(key, job), "letter": letter}

    def put_cover_letter(self, key: str, payload: dict) -> dict:
        body = payload.get("body")
        if not _letter_text(body):
            raise ApiError(LETTER_LIMIT)
        board, _, job_id = key.partition(":")
        with self.db() as con:
            if not con.execute("SELECT 1 FROM jobs WHERE board=? AND job_id=?", (board, job_id)).fetchone():
                raise ApiError("job not found", HTTPStatus.NOT_FOUND)
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            letter = {**(json.loads(row[0]) if row else {"model": "", "notes": "", "created_at": utcnow()}),
                      "body": body, "edited": True}
            letter["needs"] = cover_letter.coverage(body, letter.get("needs") or [])
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return self.get_cover_letter(key)

    def put_recipient(self, key: str, payload: dict) -> dict:
        """Save who letters for this company and city are addressed to, and readdress this job's letter (the
        text the user sees, unsaved edits included)."""
        try:
            lines = letterhead.clean_lines(payload.get("lines"))
        except ValueError as exc:
            raise ApiError(str(exc)) from exc
        body = payload.get("body")
        if body is not None and not _letter_text(body):
            raise ApiError(LETTER_LIMIT)
        job = self.job_detail(key)
        with self.db() as con:
            saved = self._recipients(con)
            saved[letterhead.place_key(job)] = {"lines": lines, "saved_at": utcnow()}
            con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('cover_recipients', ?)", (json.dumps(saved),))
            row = con.execute("SELECT v FROM kv WHERE k=?", ("cover_letter:" + key,)).fetchone()
            if row:
                letter = json.loads(row[0])
                current = body or letter["body"]
                own, dated = letterhead.header(current)
                if not own:
                    resume = con.execute("SELECT v FROM kv WHERE k='resume_text'").fetchone()
                    own = letterhead.sender([item["text"] for item in self._cover_references(con)],
                                            resume[0] if resume else "")
                text = letterhead.set_header(current, own, dated or letterhead.date_line(date.today()), lines)
                letter.update(body=text, edited=bool(letter.get("edited")) or current != letter["body"])
                con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", ("cover_letter:" + key, json.dumps(letter)))
        return self.get_cover_letter(key, job)

    def find_recipient(self, key: str) -> dict:
        """Addresses for the user to pick from: the office the posting names (read by the local model), then the
        street addresses OpenStreetMap has for the company in the posting's city."""
        job = self.job_detail(key)
        ollama = self._ollama()
        with self.db() as con:
            model = self._cover_model(con, ollama["models"]) if ollama["running"] else ""
        details = self.read_posting_details(key, job, model)
        address = letterhead.details_address(job, details)
        results = [{"name": "In the posting", "lines": address, "contact": details.get("contact", "")}] if address else []
        place = job.get("city_label") or job.get("location") or ""
        try:
            results += letterhead.find_address(job.get("company") or "", place, self._osm_agent())
        except LookupError as exc:
            if not results:
                raise ApiError(str(exc), HTTPStatus.BAD_GATEWAY) from exc
        return {"query": ", ".join(filter(None, [job.get("company"), place])), "results": results,
                "recipient": self.get_cover_letter(key, job)["recipient"]}

    def _letter_signature(self, letter: dict) -> dict | None:
        """The signature image of the past letter this one was adapted from, when that letter signs with one."""
        if not letter.get("references"):
            return None
        with self.db() as con:
            return next((past["signature"] for past in self._cover_references(con)
                         if past["filename"] in letter["references"] and past.get("signature")), None)

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
                files.append(("Cover letter", pdf_tools.letter_pdf(letter["body"], "Cover letter",
                                                                   self._letter_signature(letter))))
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
            "finance": {"skill_groups": self.kn.finance_skill_groups},
            # Each track's employer types are shown to its boards in Settings.
            "tracks": [{"key": t.key, "label": t.label, "employer_heading": t.employer_heading,
                        "boards": self.kn.track_boards.get(t.key, [])} for t in self.kn.tracks.values()],
            "company_types": [{"key": k, **v} for k, v in self.kn.company_types.items()],
            "cities": [{"key": c["key"], "label": c["label"], "country": c["country"], "target": bool(c.get("target"))}
                       for c in self.kn.cities],
            "countries": [{"key": k, "label": v["label"]} for k, v in self.kn.countries.items()],
            "languages": sorted(lang.title() for lang in KNOWN_LANGUAGES),
            "skills": [{"key": s.key, "label": s.label, "group": s.group} for s in self.kn.skills],
            "skill_groups": self.kn.skill_groups,
            # Licences & certifications a board's postings may ask for (D16).
            "licences": [{"key": l.key, "label": l.label, "kind": l.kind} for l in self.kn.licence_by_key.values()],
            "statuses": [{"key": s, "label": STATUS_LABELS[s]} for s in APP_STATUSES],
            "relationships": RELATIONSHIPS,
            "cycles": [{"key": c, "label": cycle_label(c)} for c in cycles],
            "stages": ["internship", "new_grad", "entry", "experienced", "senior"],
        }

    # ------------------------------------------------------------ saved searches
    def _saved_searches(self, con, with_counts: bool = False) -> list[dict]:
        rows = [dict(r) for r in con.execute("SELECT * FROM saved_searches ORDER BY name")]
        if with_counts and rows:
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
                    watcher.cycle(self.config, con, progress=self._poll_progress,
                                  ranking=lambda: self.status["indexing"])
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
                self.data_changed()
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

    def whats_new(self) -> dict:
        """The running version and the last one whose release notes the user closed. Kept here,
        not in the browser, so the app window and any browser tab show the notes once in all."""
        from version import APP_VERSION
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k='whats_new_seen'").fetchone()
        return {"version": APP_VERSION, "seen": row[0] if row else None}

    def close_whats_new(self, payload: dict) -> dict:
        """The notes up to `version` were read. A tab left open from before an update sends its own
        older version, so the newer notes still show; the mark never moves back."""
        from version import APP_VERSION
        version = str(payload.get("version") or "")
        if not re.fullmatch(r"\d+(?:\.\d+){0,2}", version) or _version_key(version) > _version_key(APP_VERSION):
            raise ApiError("version must be this version or an earlier one")
        with self.db() as con:
            row = con.execute("SELECT v FROM kv WHERE k='whats_new_seen'").fetchone()
            if not row or _version_key(version) > _version_key(row[0] or ""):
                con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES ('whats_new_seen', ?)", (version,))
        return self.whats_new()

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
    ("POST", r"/api/jobs/(?P<key>[^/]+)/description", lambda s, m, q, b: s.retry_description(unquote(m["key"]))),
    ("POST", r"/api/open", lambda s, m, q, b: s.open_link(b)),
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
    ("GET", r"/api/letters", lambda s, m, q, b: s.letters_info()),
    ("PUT", r"/api/letters/model", lambda s, m, q, b: s.put_letters_model(b)),
    ("POST", r"/api/letters/model/download", lambda s, m, q, b: s.download_model(b)),
    ("POST", r"/api/letters/references", lambda s, m, q, b: s.add_cover_reference(b)),
    ("DELETE", r"/api/letters/references/(?P<id>[0-9a-f]{12})", lambda s, m, q, b: s.delete_cover_reference(m["id"])),
    ("GET", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.get_cover_letter(unquote(m["key"]))),
    ("POST", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.start_cover_letter(unquote(m["key"]), b)),
    ("PUT", r"/api/jobs/(?P<key>[^/]+)/cover-letter", lambda s, m, q, b: s.put_cover_letter(unquote(m["key"]), b)),
    ("POST", r"/api/jobs/(?P<key>[^/]+)/cover-letter/revise", lambda s, m, q, b: s.start_revision(unquote(m["key"]), b)),
    ("PUT", r"/api/jobs/(?P<key>[^/]+)/recipient", lambda s, m, q, b: s.put_recipient(unquote(m["key"]), b)),
    ("POST", r"/api/jobs/(?P<key>[^/]+)/recipient/lookup", lambda s, m, q, b: s.find_recipient(unquote(m["key"]))),
    ("POST", r"/api/documents/merge", lambda s, m, q, b: s.merge_documents(b)),
    ("GET", r"/api/meta", lambda s, m, q, b: s.meta()),
    ("GET", r"/api/status", lambda s, m, q, b: s.status_info()),
    ("GET", r"/api/update", lambda s, m, q, b: s.update_info()),
    ("POST", r"/api/update/check", lambda s, m, q, b: s.check_update()),
    ("POST", r"/api/update/apply", lambda s, m, q, b: s.apply_update()),
    ("POST", r"/api/update/old-copy/dismiss", lambda s, m, q, b: s.dismiss_old_copy()),
    ("GET", r"/api/whats-new", lambda s, m, q, b: s.whats_new()),
    ("POST", r"/api/whats-new/seen", lambda s, m, q, b: s.close_whats_new(b)),
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
        if "/api/" in str(args[0] if args else ""):     # a timed-out request logs the exception itself
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

    def json(self, value, status=HTTPStatus.OK, extra_headers=None):
        self._send(json.dumps(value, default=str).encode(), status=status, extra_headers=extra_headers)

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
                         else 6_700_000 if parsed.path in ("/api/resume", "/api/resume/parse", "/api/letters/references")
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
                    stale = False
                    if method == "GET" and (parsed.path in CACHED_PATHS or parsed.path in CACHED_ON_DEMAND):
                        # Kept with the response and called again in the background: it holds no request.
                        service, query = self.service, parsed.query
                        # "Cache-Control: no-cache" (a Refresh the user clicked) waits for current data.
                        fresh = "no-cache" in (self.headers.get("Cache-Control") or "")
                        result, stale = service.cached_page(
                            (parsed.path, query), lambda handler=handler, match=match: handler(
                                service, match, parse_qs(query), body), keep=parsed.path in CACHED_PATHS, fresh=fresh)
                    else:
                        result = handler(self.service, match, parse_qs(parsed.query), body)
                        if method != "GET" and not KEEPS_PAGES.fullmatch(parsed.path):
                            self.service.invalidate()
                    if isinstance(result, FileResult):
                        return self._send(result.data, result.content_type, extra_headers={
                            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(result.filename)}"})
                    # A page from before background changes: the app asks again shortly for the current one.
                    return self.json(result, extra_headers={"X-Foothold-Stale": "1"} if stale else None)
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
