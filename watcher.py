#!/usr/bin/env python3
"""
jobwatch v5 — broad-market watcher and local career command center.

Sources: Greenhouse / Lever / Ashby / SmartRecruiters / Workday / Eightfold
boards, amazon.jobs, Microsoft careers, LinkedIn guest search, community
GitHub listing repos (SimplifyJobs / vanshb03 / cvrve JSON + markdown-table
repos like speedyapply). Cross-source dedupe so the same job never pings
twice. Discord delivery uses embeds grouped by company (no link-preview spam).

    pip install requests
    python watcher.py --check            # validate config + regexes
    python watcher.py --verify           # hit every board once, report ok/404
    python watcher.py --list stripe      # dump one board (token debug)
    python watcher.py --test shaun       # send test message to a subscriber
    python watcher.py --serve            # open the local dashboard
    python watcher.py --once             # one cycle (GitHub Actions mode; exports state.json)
    python watcher.py                    # loop forever (VPS/systemd mode)

Files: config.json, subscribers.json, jobwatch.db (created), state.json
(portable state for Actions mode; auto-imported if DB is missing).
Env: TELEGRAM_BOT_TOKEN, HEALTHCHECK_URL (optional).
"""

import argparse
import hashlib
import html
import json
import os
import random
import re
import sqlite3
import sys
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit

import requests

from intel_store import (COMPLETE_LISTING_ATS, IntelStore, record_changes, store_description,
                         update_lifecycle)

HERE = Path(__file__).parent
DB_PATH = HERE / "jobwatch.db"
CONFIG = HERE / "config.json"
SUBSCRIBERS = HERE / "subscribers.json"
STATE_JSON = HERE / "state.json"
# GitHub Actions starts every run with an empty database (see state.json).
EPHEMERAL = bool(os.environ.get("GITHUB_ACTIONS"))

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
TIMEOUT = 25
PRUNE_AFTER_DAYS = 90   # dedupe memory: a job re-posted after this alerts again
RECENT_DAYS = 14        # compact digest history; full jobs live for 90 days
ZERO_GUARD_MIN = 5
SEND_RETRIES = 3


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def log(msg):
    print(f"{now()} {msg}", flush=True)


class SourceListing(list):
    """A list with coverage evidence; a partial read must never close jobs."""
    def __init__(self, jobs=(), *, complete=False, reason="", total=None):
        super().__init__(jobs)
        self.complete = complete
        self.reason = reason
        self.total = total


def _source_limit(cfg):
    limit = cfg.get("max", 5000)
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20000:
        raise ValueError("source max must be an integer from 1 to 20000")
    return limit


def _consume_page(out, page, seen, source, limit):
    """Validate pagination before considering the listing authoritative."""
    if out.total is not None and (out.total < 0 or (out.total == 0 and page)):
        raise RuntimeError(f"{source} pagination returned an inconsistent total")
    if not page:
        missing = out.total - len(out) if out.total is not None else 0
        if missing > 0:
            # Even a small gap can repeatedly omit the same job. Keep fetched
            # postings, but never use an incomplete snapshot to infer closures.
            out.reason = f"{source} pagination ended at {len(out)} of reported total {out.total}"
            return True
        out.complete = True
        return True
    if any(not j["id"] for j in page):
        raise RuntimeError(f"{source} pagination returned a posting without an id")
    fresh = [j for j in page if j["id"] not in seen]
    if not fresh:
        raise RuntimeError(f"{source} pagination repeated a page")
    capped = len(fresh) > limit - len(out)
    fresh = fresh[:limit - len(out)]
    for job in fresh:
        if job["id"] not in seen:
            seen.add(job["id"])
            out.append(job)
    if capped:
        return True
    if out.total is not None and len(out) >= out.total:
        out.complete = True
        return True
    return False


def _finish_listing(out, source, limit):
    if not out.complete and not out.reason:
        out.reason = f"{source} reached source limit {limit}; reported total {out.total if out.total is not None else 'unknown'}"
    return out


# ---- posting freshness: adapters set job["posted"] = epoch seconds ----
def _iso_epoch(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _posted_epoch(value):
    """Normalize adapter timestamps, which may be epoch numbers or ISO text."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return _iso_epoch(value)


_AGE = re.compile(r"^(\d+)\s*(mo|m|h|d|w)$", re.I)
_AGE_SECONDS = {"m": 60, "h": 3600, "d": 86400, "w": 7 * 86400, "mo": 30 * 86400}


def _age_posted_epoch(text, now=None):
    """'36m' / '8h' / '2d' / '1w' / '3mo' (time since posting) -> epoch.

    Day-or-longer ages are pinned to 12:00 UTC of that day so the value stays
    stable across polls; 'Date unknown' and anything else gives None."""
    m = _AGE.match((text or "").strip())
    if not m:
        return None
    unit = m.group(2).lower()
    when = (now or time.time()) - int(m.group(1)) * _AGE_SECONDS[unit]
    if unit in ("m", "h"):
        return float(int(when))
    day = datetime.fromtimestamp(when, timezone.utc).replace(hour=12, minute=0, second=0, microsecond=0)
    return day.timestamp()


RELATIVE_DATE_ATS = {"workday", "github_md"}     # listing dates written as "Posted Today" / "3d"


def _workday_posted_epoch(text, now=None):
    """'Posted Today' / 'Posted Yesterday' / 'Posted 5 Days Ago' -> epoch at 12:00 UTC.

    Day precision keeps the value stable across polls on the same day, and it
    matches the exact posting date (``startDate``) the detail endpoint gives.
    Noon UTC renders as the same calendar day from UTC-11 to UTC+11.
    Open-ended buckets ('Posted 30+ Days Ago') are only a lower bound on age, so
    they return None rather than a made-up date; enrichment fills in the real one.
    """
    if not text:
        return None
    t = text.lower()
    if "+" in t:
        return None
    if "today" in t:
        days = 0
    elif "yesterday" in t:
        days = 1
    else:
        m = re.search(r"(\d+)\s*days?\b", t)
        if not m:
            return None
        days = int(m.group(1))
    now = now if now is not None else time.time()
    day = datetime.fromtimestamp(now, timezone.utc).date() - timedelta(days=days)
    # Never in the future ('Posted Today' before noon UTC); whole hours stay integral.
    return min(_date_epoch(day.isoformat()), now // 3600 * 3600)


def _date_epoch(value):
    """'2026-08-05' -> epoch at 12:00 UTC on that day (None if missing or malformed)."""
    try:
        day = datetime.strptime(str(value)[:10], "%Y-%m-%d")
    except (TypeError, ValueError):
        return None
    return day.replace(hour=12, tzinfo=timezone.utc).timestamp()


def _rel_age(posted):
    """Compact freshness badge; 🔥 for <24h, plain for up to 21d, else ''."""
    if not posted:
        return ""
    epoch = _posted_epoch(posted)
    if epoch is None:
        return ""
    age = time.time() - epoch
    if age < 0:
        return ""
    hours = age / 3600
    if hours < 2:
        return "🔥 just posted"
    if hours < 24:
        return f"🔥 {int(hours)}h ago"
    days = int(hours // 24)
    if days <= 21:
        return f"{days}d ago"
    return ""


_BLOCK_TAG = re.compile(r"<\s*(br|/p|/div|/li|/h\d|/tr)\s*/?>", re.I)
_ANY_TAG = re.compile(r"<[^>]+>")


def html_to_text(raw):
    """ATS HTML (sometimes entity-escaped twice, as on Greenhouse) -> plain text."""
    if not raw:
        return ""
    text = html.unescape(raw)
    if "&lt;" in text or "&amp;" in text:
        text = html.unescape(text)
    text = _BLOCK_TAG.sub("\n", text)
    text = re.sub(r"<\s*li[^>]*>", "\n• ", text, flags=re.I)
    text = _ANY_TAG.sub(" ", text)
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


# ================================================================ adapters
# Each returns list of {id, title, location, url, company}. id stable per board.
# Optional: posted, salary, description, department (descriptions feed the
# finance intelligence layer; adapters that cannot afford them leave them out
# and DETAIL_FETCHERS enrich a budgeted number of postings per cycle).

def fetch_greenhouse(cfg):
    url = f"https://boards-api.greenhouse.io/v1/boards/{cfg['token']}/jobs?content=false"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{
        "id": str(j["id"]),
        "title": j.get("title", ""),
        "location": (j.get("location") or {}).get("name", ""),
        "url": j.get("absolute_url", ""),
        "posted": _iso_epoch(j.get("first_published") or j.get("updated_at")),
    } for j in r.json().get("jobs", [])]


def _lever_text(j):
    """Lever ships the full posting in the list payload — keep it."""
    parts = [j.get("descriptionPlain") or ""]
    for block in j.get("lists") or []:
        items = _HTML_TAG.sub(" ", block.get("content") or "")
        parts.append(f"{block.get('text', '')}\n{html.unescape(items)}")
    parts.append(j.get("additionalPlain") or "")
    return "\n".join(p for p in parts if p).strip()


def fetch_lever(cfg):
    url = f"https://api.lever.co/v0/postings/{cfg['token']}?mode=json"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{
        "id": str(j["id"]),
        "title": j.get("text", ""),
        "location": (j.get("categories") or {}).get("location", "") or "",
        "url": j.get("hostedUrl", ""),
        "posted": (j.get("createdAt") or 0) / 1000 or None,
        "description": _lever_text(j),
        "department": " / ".join(filter(None, [(j.get("categories") or {}).get("department"),
                                               (j.get("categories") or {}).get("team")])),
    } for j in r.json()]


def fetch_ashby(cfg):
    url = f"https://api.ashbyhq.com/posting-api/job-board/{cfg['token']}?includeCompensation=true"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    return [{
        "id": str(j.get("id")),
        "title": j.get("title", ""),
        "location": j.get("location", "") or "",
        "url": j.get("jobUrl", ""),
        "salary": (j.get("compensation") or {}).get("compensationTierSummary", ""),
        "posted": _iso_epoch(j.get("publishedAt")),
        "description": j.get("descriptionPlain") or html_to_text(j.get("descriptionHtml") or ""),
        "department": " / ".join(filter(None, [j.get("department"), j.get("team")])),
    } for j in r.json().get("jobs", [])]


def fetch_smartrecruiters(cfg):
    """SmartRecruiters public postings API, every page (100 per request)."""
    t = cfg["token"]
    limit = _source_limit(cfg)
    out, seen, offset = SourceListing(), set(), 0
    while offset < limit:
        r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{t}/postings",
                         params={"limit": 100, "offset": offset},
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if out.total is None and isinstance(data.get("totalFound"), int):
            out.total = data["totalFound"]
        posts = data.get("content") or []
        for j in posts:
            jid = str(j.get("id"))
            if jid in seen or len(out) >= limit:
                continue
            seen.add(jid)
            loc = j.get("location") or {}
            out.append({
                "id": jid,
                "title": j.get("name", ""),
                "location": ", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
                "url": f"https://jobs.smartrecruiters.com/{t}/{jid}",
            })
        offset += len(posts)
        if not posts or (out.total is not None and offset >= out.total):
            break
    out.complete = out.total is not None and len(out) >= out.total
    if not out.complete:
        out.reason = f"SmartRecruiters returned {len(out)} of {out.total} postings"
    return out


# Workday stops at 2000: "total" never exceeds it and offsets past it repeat
# earlier pages (Citi: ~4,200 postings). Bigger searches are split by a facet.
WORKDAY_TOTAL_CAP = 2000


def _workday_split_facet(facets, applied, limit):
    """(estimated size, [(parameter, value id), ...]) for the flat facet that
    covers the most postings, or None when no facet covers the capped search
    or the search is larger than the source limit. Parts still at the cap are
    split again by another facet."""
    best = None
    for facet in facets or []:
        param, values = facet.get("facetParameter"), facet.get("values") or []
        if not param or param in applied or not values or any("values" in v for v in values):
            continue
        parts = [(param, v["id"], v.get("count", 0)) for v in values if v.get("id")]
        coverage = sum(c for _, _, c in parts)
        if not parts or len(parts) > 100 or coverage < WORKDAY_TOTAL_CAP:
            continue          # e.g. a "remote" facet covering 10 of 14,000 postings
        key = (coverage, -max(c for _, _, c in parts))
        if best is None or key > best[0]:
            best = (key, [(p, i) for p, i, _ in parts])
    if best is None or best[0][0] > limit:
        return None
    return best[0][0], best[1]


def _fetch_workday_split(cfg, parts, limit):
    applied = cfg.get("facets", {}) or {}
    out, seen = SourceListing(), set()
    out.complete = True
    for param, value in parts:
        part = fetch_workday({**cfg, "facets": {**applied, param: [value]}, "max": limit})
        for job in part:
            if job["id"] not in seen and len(out) < limit:
                seen.add(job["id"])
                out.append(job)
        if not part.complete:
            out.complete = False
            out.reason = part.reason
    if len(out) >= limit:
        out.complete = False
        out.reason = f"Workday reached source limit {limit}"
    out.total = len(out) if out.complete else None
    return out


def fetch_workday(cfg):
    host, tenant, site = cfg["host"], cfg["tenant"], cfg["site"]
    url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    out, offset, seen = SourceListing(), 0, set()
    raw_pages, malformed = set(), 0
    previous_short_page = False
    limit = _source_limit(cfg)
    capped = None          # estimated size when only the first 2000 can be read
    while offset < limit:
        body = {"appliedFacets": cfg.get("facets", {}), "limit": min(20, limit - offset),
                "offset": offset, "searchText": cfg.get("search", "")}
        r = requests.post(url, json=body, timeout=TIMEOUT,
                          headers={"User-Agent": UA, "Accept": "application/json",
                                   "Content-Type": "application/json"})
        r.raise_for_status()
        data = r.json()
        if offset == 0 and isinstance(data.get("total"), int) and data["total"] >= WORKDAY_TOTAL_CAP:
            split = _workday_split_facet(data.get("facets"), cfg.get("facets", {}) or {}, limit)
            if split:
                return _fetch_workday_split(cfg, split[1], limit)
            # Too large (or unsplittable) to read in full: keep the first 2000,
            # but never treat them as the whole listing.
            sizes = [sum(v.get("count", 0) for v in f.get("values") or [])
                     for f in data.get("facets") or [] if not any("values" in v for v in f.get("values") or [])]
            capped = max(sizes + [WORKDAY_TOTAL_CAP])
            limit = min(limit, WORKDAY_TOTAL_CAP)
        if out.total is None and capped is None and isinstance(data.get("total"), int):
            out.total = data["total"]
        posts = data.get("jobPostings")
        if not isinstance(posts, list):
            raise RuntimeError("Workday pagination response has no jobPostings list")
        if out.total is not None and (out.total < 0 or (out.total == 0 and posts)):
            raise RuntimeError(f"Workday pagination returned an inconsistent total at offset {offset}")
        if not posts:
            if out.total is not None and offset < out.total:
                if out and previous_short_page:
                    out.reason = f"Workday pagination ended at {len(out)} of reported total {out.total}; valid postings retained"
                    break
                raise RuntimeError(f"Workday pagination ended before reported total {out.total} at offset {offset}")
            out.complete = True
            break
        # Some tenants return tombstone summaries containing only bulletFields.
        # They occupy a result slot but provide no usable public posting URL.
        signature = hashlib.sha256(json.dumps(posts, sort_keys=True).encode()).digest()
        if signature in raw_pages:
            if out and previous_short_page:
                out.reason = f"Workday pagination repeated a page after a short final page at offset {offset}; valid postings retained"
                break
            raise RuntimeError(f"Workday pagination repeated a page at offset {offset}")
        raw_pages.add(signature)
        page = []
        for j in posts:
            path = j.get("externalPath") if isinstance(j, dict) else None
            title = j.get("title") if isinstance(j, dict) else None
            if not isinstance(path, str) or not path.strip() or not isinstance(title, str) or not title.strip():
                malformed += 1
                continue
            path = path.strip()
            page.append({
                "id": path,
                "title": title,
                "location": j.get("locationsText", "") or "",
                "url": f"https://{host}/en-US/{site}{path}",
                "posted": _workday_posted_epoch(j.get("postedOn", "")),
            })
        # Advance by raw results, including malformed summaries, so a missing
        # record cannot trap collection on one page or fake an exhausted feed.
        if page and not any(j["id"] not in seen for j in page) and out and previous_short_page:
            out.reason = f"Workday pagination repeated postings after a short final page at offset {offset}; valid postings retained"
            break
        previous_short_page = len(posts) < body["limit"]
        offset += len(posts)
        if page and _consume_page(out, page, seen, "Workday", limit):
            break
        if out.total is not None and offset >= out.total:
            out.complete = len(out) >= out.total
            if not out.complete and not malformed:
                out.reason = f"Workday returned {len(out)} of {out.total} usable postings; listing is incomplete"
            break
    if capped is not None:
        out.complete = False
        out.reason = (f"Workday lists about {capped:,} postings but serves only the first "
                      f"{WORKDAY_TOTAL_CAP:,}; removals are not tracked for this source")
    if malformed:
        out.complete = False
        noun = "summary" if malformed == 1 else "summaries"
        warning = (f"Workday returned {malformed} malformed posting {noun} without a title or public path; "
                   "valid summaries retained; listing is incomplete")
        out.reason = f"{out.reason}; {warning}" if out.reason else warning
        if offset >= limit and (out.total is None or offset < out.total):
            out.reason += f"; source limit {limit} reached"
    return _finish_listing(out, "Workday", limit)


def fetch_amazon_jobs(cfg):
    """amazon.jobs public search JSON. cfg: query (e.g. 'software intern'),
    optionally country and max (default 1000). Reads every page of matches,
    newest first; a keyword search is never treated as Amazon's full listing."""
    limit = cfg.get("max", 1000)
    out, seen, offset = SourceListing(reason="amazon.jobs keyword search"), set(), 0
    while offset < limit:
        params = {"base_query": cfg.get("query", "software engineer intern"),
                  "result_limit": 100, "offset": offset, "sort": "recent"}
        if cfg.get("country"):
            params["country"] = cfg["country"]
        r = requests.get("https://www.amazon.jobs/en/search.json", params=params,
                         headers={"User-Agent": UA, "Accept": "application/json"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if out.total is None and isinstance(data.get("hits"), int):
            out.total = data["hits"]
        jobs = data.get("jobs") or []
        for j in jobs:
            jid = str(j.get("id_icims") or j.get("id"))
            if jid in seen:
                continue
            seen.add(jid)
            desc = "\n\n".join(html_to_text(j.get(k) or "") for k in (
                "description_short", "basic_qualifications", "preferred_qualifications"))
            out.append({
                "id": jid,
                "title": j.get("title", ""),
                "location": j.get("normalized_location", "") or j.get("location", ""),
                "url": "https://www.amazon.jobs" + (j.get("job_path") or ""),
                "description": desc.strip(),
                "department": j.get("job_category") or "",
            })
        offset += len(jobs)
        if not jobs or (out.total is not None and offset >= out.total):
            break
    return out


def fetch_microsoft(cfg):
    """Microsoft careers public search JSON. cfg: query."""
    params = {"q": cfg.get("query", "software engineer"), "l": "en_us",
              "pg": 1, "pgSz": 100, "o": "Relevance", "flt": "true"}
    r = requests.get("https://gcsservices.careers.microsoft.com/search/api/v1/search",
                     params=params, headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    jobs = (((r.json().get("operationResult") or {}).get("result") or {}).get("jobs")) or []
    out = []
    for j in jobs:
        jid = str(j.get("jobId", ""))
        props = j.get("properties") or {}
        locs = props.get("locations") or []
        out.append({
            "id": jid,
            "title": j.get("title", ""),
            "location": "; ".join(locs[:3]),
            "url": f"https://jobs.careers.microsoft.com/global/en/job/{jid}",
        })
    return out


def fetch_github_listings(cfg):
    """Community-maintained listing repos (SimplifyJobs and forks).
    cfg: repo ('SimplifyJobs/New-Grad-Positions'), branch (default 'dev'),
    path (default '.github/scripts/listings.json').
    These aggregate hundreds of companies incl. bespoke boards (Jane Street,
    Google, Meta, Apple) — the machine-readable version of the IG job accounts."""
    repo = cfg["repo"]
    branch = cfg.get("branch", "dev")
    path = cfg.get("path", ".github/scripts/listings.json")
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    out = []
    for j in r.json():
        if not j.get("active") or not j.get("is_visible", True):
            continue
        locs = j.get("locations") or []
        # Listing metadata (terms, sponsorship, degrees) is phrased the way the
        # cycle and eligibility extractors already understand.
        meta = []
        if j.get("terms"):
            meta.append(f"Recruiting term: {', '.join(map(str, j['terms']))}.")
        if j.get("sponsorship"):
            meta.append(f"Sponsorship: {j['sponsorship']}.")
        if j.get("degrees"):
            meta.append(f"Degrees: {', '.join(map(str, j['degrees']))}.")
        out.append({
            "id": str(j.get("id")),
            "title": j.get("title", ""),
            "location": " | ".join(locs[:3]),
            "url": j.get("url", ""),
            "company": j.get("company_name", ""),
            "posted": j.get("date_posted") or j.get("date_updated") or None,
            "description": " ".join(meta),
            "description_source": "listing_metadata",
            "department": j.get("category") or "",
        })
    return out


_MD_LINK = re.compile(r"\[([^\]]*)\]\((https?://[^)\s]+)\)")
_MD_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_HREF = re.compile(r'href="(https?://[^"]+)"')
_RAW_URL = re.compile(r"https?://[^)\s\"'<>\]]+")
_HTML_TAG = re.compile(r"<[^>]+>")
_DECOR = re.compile(r"[✓✅🆕🔥⭐🎯🛂🔒🇺🇸🇨🇦↳*_`]")


_ZERO_WIDTH = re.compile("[\u200b-\u200d\u2060\ufeff]")


def _cell_text(cell):
    s = _MD_IMG.sub("", cell)
    m = _MD_LINK.search(s)
    if m and m.group(1).strip():
        s = m.group(1)
    else:
        s = _HTML_TAG.sub("", s)
    s = _DECOR.sub("", s)
    s = _ZERO_WIDTH.sub("", s)      # some lists hide zero-width spaces inside words
    return re.sub(r"\s+", " ", s).strip(" -—")


def _cell_url(cell):
    s = _MD_IMG.sub("", cell)       # shields.io badges hide the real link
    m = _HREF.search(s)
    if m:
        return m.group(1)
    m = _RAW_URL.search(s)
    return m.group(0).rstrip(".,;") if m else ""


def fetch_marqeta(cfg):
    """Marqeta's official careers page exposes its live openings as a
    semantic HTML table.  Their former Greenhouse board is no longer public,
    so parsing that first-party table is more reliable than a stale token."""
    base = cfg.get("url", "https://www.marqeta.com")
    path = cfg.get("path", "/company/careers")
    r = requests.get(base.rstrip("/") + path, headers={"User-Agent": UA},
                     timeout=TIMEOUT)
    r.raise_for_status()
    out, seen = [], set()
    pattern = re.compile(
        r'<a[^>]+href="(/careers/([0-9a-f-]{20,}))"[^>]*>(.*?)</a>', re.I | re.S)
    for href, job_id, body in pattern.findall(r.text):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", body, re.I | re.S)
        if len(cells) < 3 or job_id in seen:
            continue
        seen.add(job_id)
        out.append({
            "id": job_id,
            "title": _cell_text(cells[0]),
            "location": _cell_text(cells[2]),
            "url": base.rstrip("/") + href,
            "company": "Marqeta",
        })
    if not out:
        raise ValueError("official Marqeta careers page contained no job rows")
    return out


def fetch_github_md(cfg):
    """Community listing repos that publish a markdown table (speedyapply,
    Canadian lists, off-season lists, ...). cfg: repo, branch (default 'main'),
    path (default 'README.md'), cols: 0-based column indexes for
    company/title/url (+ optional location/salary). Handles md links, HTML
    anchors, shields.io Apply badges, and repos that repeat/omit the company
    on continuation rows."""
    cols = cfg["cols"]
    url = (f"https://raw.githubusercontent.com/{cfg['repo']}/"
           f"{cfg.get('branch', 'main')}/{cfg.get('path', 'README.md')}")
    r = requests.get(url, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    need = max(cols.values()) + 1
    out, seen, prev_company = [], set(), ""
    for row in r.text.splitlines():
        if not row.startswith("|"):
            continue
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if len(cells) < need:
            continue
        title = _cell_text(cells[cols["title"]])
        if (not title or set(title) <= set("-: ")
                or title.lower() in ("role", "position", "job title")):
            continue                     # header / separator rows
        joburl = _cell_url(cells[cols["url"]]) or _cell_url(cells[cols["title"]])
        if not joburl:
            continue
        company = _cell_text(cells[cols["company"]]) or prev_company
        prev_company = company
        jid = hashlib.md5(joburl.encode()).hexdigest()[:16]
        if jid in seen:
            continue
        seen.add(jid)
        job = {
            "id": jid,
            "title": title,
            "location": _cell_text(cells[cols["location"]]) if "location" in cols else "",
            "url": joburl,
            "company": company,
        }
        if "salary" in cols:
            sal = _cell_text(cells[cols["salary"]])
            if sal and sal != "-":
                job["salary"] = sal
        if "age" in cols:
            posted = _age_posted_epoch(_cell_text(cells[cols["age"]]))
            if posted:
                job["posted"] = posted
        out.append(job)
    return out


# LinkedIn answers bursts with 429. All LinkedIn sources share one IP, so their
# requests take turns with a gap, back off on 429, and pause briefly if blocked.
LINKEDIN_SPACING = 1.5             # seconds between requests (plus up to 1s jitter)
LINKEDIN_BACKOFF = (8, 20, 45)     # waits after successive 429s on one request
LINKEDIN_BLOCK_PAUSE = 300         # skip LinkedIn this long once retries are exhausted
LINKEDIN_SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
LINKEDIN_POSTING = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"
_linkedin_lock = threading.Lock()
_linkedin_next = 0.0
_linkedin_blocked_until = 0.0


class LinkedInRateLimited(requests.HTTPError):
    pass


def _linkedin_get(url, params=None):
    """Every LinkedIn request (searches and opened postings) takes its turn here."""
    global _linkedin_next, _linkedin_blocked_until
    with _linkedin_lock:
        for attempt in range(len(LINKEDIN_BACKOFF) + 1):
            now = time.monotonic()
            if now < _linkedin_blocked_until:
                raise LinkedInRateLimited("LinkedIn is rate limiting; paused for a few minutes")
            if now < _linkedin_next:
                time.sleep(_linkedin_next - now)
            r = requests.get(url, params=params,
                             headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}, timeout=TIMEOUT)
            _linkedin_next = time.monotonic() + LINKEDIN_SPACING + random.uniform(0, 1)
            if r.status_code != 429:
                return r
            if attempt < len(LINKEDIN_BACKOFF):
                try:
                    wait = min(float(r.headers.get("Retry-After") or 0), 120) or LINKEDIN_BACKOFF[attempt]
                except ValueError:
                    wait = LINKEDIN_BACKOFF[attempt]
                _linkedin_next = time.monotonic() + wait
        _linkedin_blocked_until = time.monotonic() + LINKEDIN_BLOCK_PAUSE
        raise LinkedInRateLimited("LinkedIn kept answering 429 Too Many Requests")


def fetch_linkedin(cfg):
    """LinkedIn public guest results, no login. cfg: queries (list) or query,
    location ('United States'), recency
    ('r86400' = posted in last 24h), pages (default 3, ~10 results/page).
    seed_recency/seed_pages can widen the first poll. This feed is always partial."""
    if cfg.get("_initial_seed"):
        cfg = {**cfg, "recency": cfg.get("seed_recency", cfg.get("recency", "r2592000")),
               "pages": cfg.get("seed_pages", cfg.get("pages", 3))}
    queries = cfg.get("queries") or [cfg.get("query", "software engineer intern")]
    location = cfg.get("location", "United States")
    out = SourceListing(reason="LinkedIn guest search is a bounded keyword and date window")
    seen, errors = set(), []
    for q in queries:
        try:
            _linkedin_query(cfg, q, location, out, seen)
        except Exception as e:      # one rate-limited query shouldn't kill the rest
            errors.append(e)
    if not out and errors:
        raise errors[0]
    if errors:
        out.reason += f"; {len(errors)} query request(s) failed"
        log(f"! linkedin({location}): {len(errors)} query request(s) failed; results are partial")
    return out


def _linkedin_query(cfg, q, location, out, seen):
    start = 0
    pages = cfg.get("pages", 3)
    if isinstance(pages, bool) or not isinstance(pages, int) or not 1 <= pages <= 40:
        raise ValueError("LinkedIn pages must be an integer from 1 to 40")
    previous_pages = set()
    for _ in range(pages):
        r = _linkedin_get(LINKEDIN_SEARCH, {"keywords": q, "location": location,
                                            "f_TPR": cfg.get("recency", "r86400"), "start": start})
        if r.status_code in (400, 404):         # past the end of results
            break
        r.raise_for_status()
        got = 0
        page_ids = []
        for card in r.text.split("<li")[1:]:
            m = re.search(r"urn:li:jobPosting:(\d+)", card)
            mt = re.search(r"base-search-card__title[^>]*>\s*([^<]+)", card)
            if not m or not mt:
                continue
            got += 1
            jid = m.group(1)
            page_ids.append(jid)
            if jid in seen:
                continue
            seen.add(jid)
            mc = re.search(r"base-search-card__subtitle[^>]*>\s*<a[^>]*>\s*([^<]+)", card)
            ml = re.search(r"job-search-card__location[^>]*>\s*([^<]+)", card)
            md = re.search(r'datetime="([^"]+)"', card)
            out.append({
                "id": jid,
                "title": html.unescape(mt.group(1)).strip(),
                "location": html.unescape(ml.group(1)).strip() if ml else "",
                "url": f"https://www.linkedin.com/jobs/view/{jid}",
                "company": html.unescape(mc.group(1)).strip() if mc else "",
                "posted": _iso_epoch(md.group(1)) if md else None,
            })
        signature = tuple(page_ids)
        if not got or signature in previous_pages:
            break
        previous_pages.add(signature)
        start += got                            # _linkedin_get spaces the requests


def fetch_janestreet(cfg):
    """Jane Street's own positions feed — no ATS, plain JSON. The
    availability field ('Full-Time: New Grad', 'Internship', ...) is folded
    into the title so intern/new-grad categorization and filters see it."""
    r = requests.get("https://www.janestreet.com/jobs/main.json",
                     headers={"User-Agent": UA, "Accept": "application/json"},
                     timeout=TIMEOUT)
    r.raise_for_status()
    cities = {"NYC": "New York, NY", "LDN": "London, UK", "HKG": "Hong Kong",
              "SGP": "Singapore", "AMS": "Amsterdam", "CHI": "Chicago, IL"}
    out = []
    for p in r.json():
        avail = (p.get("availability") or "").strip()
        title = p.get("position", "")
        if avail and avail.lower() not in title.lower():
            title = f"{title} — {avail}"
        sal = ""
        if p.get("min_salary") and p.get("max_salary"):
            try:
                lo = int(str(p["min_salary"]).replace(",", "").split(".")[0])
                hi = int(str(p["max_salary"]).replace(",", "").split(".")[0])
                sal = f"${lo:,} – ${hi:,}"
            except ValueError:
                sal = f"${p['min_salary']} – ${p['max_salary']}"
        out.append({
            "id": str(p.get("id")),
            "title": title,
            "location": cities.get(p.get("city"), p.get("city") or ""),
            "url": f"https://www.janestreet.com/join-jane-street/position/{p.get('id')}/",
            "company": "Jane Street",
            "salary": sal,
            "description": html_to_text(p.get("overview") or p.get("description") or ""),
            "department": p.get("team") or p.get("category") or "",
        })
    return out


PHENOM_PASSES = 4


def fetch_phenom(cfg):
    """Phenom People career sites (jobs.rbc.com etc). cfg: host, query,
    size (page size, default 100), max (default 5000), url template.

    Phenom orders ties differently on every request, so one paged pass can
    repeat some postings and skip others (RBC: 798-825 of 827). Pages are
    sorted newest first and whole passes repeat, merging by id, until every
    reported posting is seen. A short read keeps what it found but is not
    marked complete, so it can never close postings it merely missed."""
    limit = _source_limit(cfg)
    size = cfg.get("size", 100)
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 100:
        raise ValueError("Phenom size must be an integer from 1 to 100")
    body = {"lang": "en_us", "deviceType": "desktop", "country": "us",
            "pageName": "search-results", "ddoKey": "refineSearch", "from": 0,
            "jobs": True, "counts": True, "size": size, "sortBy": cfg.get("sort", "Most recent"),
            "clearAll": False, "jdsource": "facets", "siteType": "external",
            "keywords": cfg.get("query", ""), "global": True,
            "selected_fields": {}, "all_fields": ["category", "location"]}
    url_tmpl = cfg.get("url", f"https://{cfg['host']}/en/job/{{id}}")
    out, seen = SourceListing(), set()
    passes = 0
    while passes < PHENOM_PASSES:
        passes += 1
        offset = 0
        while offset < limit:
            request_body = {**body, "from": offset, "size": size}
            r = requests.post(f"https://{cfg['host']}/widgets", json=request_body,
                              headers={"User-Agent": UA, "Accept": "application/json",
                                       "Content-Type": "application/json"}, timeout=TIMEOUT)
            r.raise_for_status()
            result = r.json().get("refineSearch", {})
            if result.get("status", 200) != 200:
                raise RuntimeError("Phenom pagination returned an unsuccessful search")
            if out.total is None and isinstance(result.get("totalHits"), int):
                out.total = result["totalHits"]
                if out.total < 0:
                    raise RuntimeError("Phenom pagination returned an inconsistent total")
            posts = result.get("data", {}).get("jobs")
            if not isinstance(posts, list):
                raise RuntimeError("Phenom pagination response has no jobs list")
            if not posts:
                break
            for j in posts:
                jid = str(j.get("jobId") or j.get("reqId") or "")
                if not jid:
                    raise RuntimeError("Phenom pagination returned a posting without an id")
                if jid in seen or len(out) >= limit:
                    continue
                seen.add(jid)
                loc = (j.get("cityStateCountry") or j.get("cityState")
                       or j.get("location") or j.get("city") or "")
                out.append({
                    "id": jid, "title": j.get("title", ""),
                    "location": loc if isinstance(loc, str) else "; ".join(loc),
                    "url": j.get("applyUrl") or url_tmpl.format(id=jid),
                    "posted": _iso_epoch(j.get("postedDate")),
                    "description": html_to_text(j.get("descriptionTeaser") or ""),
                    "department": j.get("category") or "",
                })
            offset += len(posts)
            if out.total is not None and offset >= out.total:
                break
        if out.total is None or len(out) >= min(out.total, limit):
            break
    if out.total is not None and len(out) >= out.total:
        out.complete = True
    elif len(out) >= limit:
        out.reason = f"Phenom reached source limit {limit}; reported total {out.total}"
    else:
        out.reason = (f"Phenom returned {len(out)} of {out.total} postings after {passes} passes "
                      "(the site's ordering is unstable); removals are not tracked this time")
    return out


def fetch_eightfold(cfg):
    """Eightfold-powered career sites (Netflix etc). cfg: host
    ('explore.jobs.netflix.net'), domain ('netflix.com'), optional query,
    max (default 2000). The API serves 10 per page."""
    limit = cfg.get("max", 2000)
    out, seen, start = SourceListing(), set(), 0
    while start < limit:
        params = {"domain": cfg["domain"], "start": start, "num": 10,
                  "sort_by": "timestamp"}
        if cfg.get("query"):
            params["query"] = cfg["query"]
        r = requests.get(f"https://{cfg['host']}/api/apply/v2/jobs", params=params,
                         headers={"User-Agent": UA, "Accept": "application/json"},
                         timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if out.total is None and isinstance(data.get("count"), int):
            out.total = data["count"]
        positions = data.get("positions", [])
        for p in positions:
            pid = str(p.get("id"))
            if pid in seen:
                continue
            seen.add(pid)
            out.append({
                "id": pid,
                "title": p.get("name", ""),
                "location": p.get("location", "") or "",
                "url": p.get("canonicalPositionUrl")
                       or f"https://{cfg['host']}/careers/job/{pid}",
            })
        start += len(positions)
        if not positions or start >= (out.total or 0):
            break
    out.complete = not cfg.get("query") and out.total is not None and len(out) >= out.total
    if not out.complete:
        out.reason = f"Eightfold returned {len(out)} of {out.total} postings"
    return out


def fetch_oracle_hcm(cfg):
    """Oracle Recruiting Cloud candidate-experience API (JPMorgan Chase and
    other banks). cfg: host ('jpmc.fa.oraclecloud.com'), site ('CX_1001'),
    optional query (keyword), max (safety limit, default 5000) and url (a
    posting link template with {id}, for employers whose public site is not
    the Oracle candidate page, e.g. Goldman Sachs' higher.gs.com)."""
    host, site = cfg["host"], cfg["site"]
    url_tmpl = cfg.get("url", f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{{id}}")
    out, offset, seen = SourceListing(), 0, set()
    limit = _source_limit(cfg)
    keyword = cfg.get("query", "")
    while offset < limit:
        finder = f"findReqs;siteNumber={site},limit={min(25, limit - offset)},offset={offset},sortBy=POSTING_DATES_DESC"
        if keyword:
            finder += f',keyword="{keyword}"'
        r = requests.get(
            f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions",
            params={"onlyData": "true", "expand": "requisitionList.secondaryLocations", "finder": finder},
            headers={"User-Agent": UA, "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        items = r.json().get("items")
        if not isinstance(items, list) or not items:
            raise RuntimeError("Oracle pagination response has no search result")
        items = items[0]
        if out.total is None and isinstance(items.get("TotalJobsCount"), int):
            out.total = items["TotalJobsCount"]
        reqs = items.get("requisitionList")
        if not isinstance(reqs, list):
            raise RuntimeError("Oracle pagination response has no requisitionList")
        page = []
        for j in reqs:
            jid = str(j.get("Id") or "")
            page.append({
                "id": jid,
                "title": j.get("Title", ""),
                "location": j.get("PrimaryLocation") or "",
                "url": url_tmpl.format(id=jid),
                "posted": _iso_epoch(j.get("PostedDate")),
                "description": html_to_text(j.get("ShortDescriptionStr") or ""),
            })
        if _consume_page(out, page, seen, "Oracle", limit):
            break
        offset += len(reqs)
    return _finish_listing(out, "Oracle", limit)


def _html_attr(tag, name):
    match = re.search(r"\b" + re.escape(name) + r"\s*=\s*([\"'])(.*?)\1", tag, re.I | re.S)
    return html.unescape(match.group(2)) if match else ""


def fetch_successfactors(cfg):
    """Public SuccessFactors Recruiting Marketing HTML (Scotiabank)."""
    root = cfg["url"].rstrip("/") + "/"
    out, offset, seen = SourceListing(), 0, set()
    limit = _source_limit(cfg)
    while offset < limit:
        url = root if offset == 0 else f"{root}{offset}/"
        r = requests.get(url, params={"q": "", "sortColumn": "referencedate", "sortDirection": "desc"},
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        total = re.search(r'class=["\'][^"\']*paginationLabel[^"\']*["\'][^>]*>.*?of\s*<b>\s*([\d,]+)', r.text, re.S)
        if out.total is None and total:
            out.total = int(total.group(1).replace(",", ""))
        if 'id="searchresults"' not in r.text and not re.search(r"no (?:matching )?jobs", r.text, re.I):
            raise RuntimeError("SuccessFactors pagination response has no search results table")
        page = []
        for row in re.findall(r'<tr\b[^>]*class=["\'][^"\']*data-row[^"\']*["\'][^>]*>(.*?)</tr>', r.text, re.S | re.I):
            links = re.findall(r"<a\b([^>]*)>(.*?)</a>", row, re.S | re.I)
            link = next(((attrs, title) for attrs, title in links if "jobTitle-link" in _html_attr(attrs, "class")), None)
            if not link:
                raise RuntimeError("SuccessFactors pagination could not parse a result")
            attrs, title = link
            job_url = urljoin(root, _html_attr(attrs, "href"))
            jid = re.search(r"/(\d+)/?$", urlsplit(job_url).path)
            loc = re.search(r'<td\b[^>]*class=["\'][^"\']*colLocation[^"\']*["\'][^>]*>(.*?)</td>', row, re.S | re.I)
            date = re.search(r'<td\b[^>]*class=["\'][^"\']*colDate[^"\']*["\'][^>]*>(.*?)</td>', row, re.S | re.I)
            posted = None
            if date:
                try:
                    posted = datetime.strptime(html_to_text(date.group(1)).strip(), "%b %d, %Y").replace(tzinfo=timezone.utc).timestamp()
                except ValueError:
                    pass
            page.append({"id": jid.group(1) if jid else "", "title": html_to_text(title).strip(),
                         "location": html_to_text(loc.group(1)).strip() if loc else "",
                         "url": job_url, "posted": posted})
        if _consume_page(out, page, seen, "SuccessFactors", limit):
            break
        offset += len(page)
    return _finish_listing(out, "SuccessFactors", limit)


def fetch_avature(cfg):
    """National Bank's public Avature jobs table and jobOffset pagination."""
    root = cfg["url"]
    out, offset, seen = SourceListing(), 0, set()
    limit = _source_limit(cfg)
    while offset < limit:
        r = requests.get(root, params={"jobRecordsPerPage": 20, "jobOffset": offset},
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        page = []
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", r.text, re.S | re.I):
            links = re.findall(r"<a\b([^>]*)>(.*?)</a>", row, re.S | re.I)
            link = next(((attrs, title) for attrs, title in links if _html_attr(attrs, "data-map") == "job-detail-link"), None)
            if not link:
                continue
            attrs, title = link
            job_url = urljoin(root, _html_attr(attrs, "href"))
            jid = re.search(r"/(\d+)/?$", urlsplit(job_url).path)
            cells = re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S | re.I)
            loc = html_to_text(cells[0]).strip() if cells else ""
            if loc and re.search(r"\b(?:Quebec|Québec|Ontario|Alberta|British Columbia|Manitoba|Saskatchewan|Nova Scotia|New Brunswick|Newfoundland|Prince Edward Island|Yukon|Nunavut|Northwest Territories)\b", loc, re.I):
                loc += ", Canada"
            page.append({"id": jid.group(1) if jid else "", "title": html_to_text(title).strip(),
                         "location": loc, "url": job_url})
        if not page:
            raise RuntimeError("Avature pagination response has no parsed jobs")
        if _consume_page(out, page, seen, "Avature", limit):
            break
        next_offsets = []
        for attrs, _ in re.findall(r"<a\b([^>]*)>(.*?)</a>", r.text, re.S | re.I):
            if "paginationLink" not in _html_attr(attrs, "class"):
                continue
            href = urljoin(root, _html_attr(attrs, "href"))
            if urlsplit(href).netloc != urlsplit(root).netloc:
                continue
            value = parse_qs(urlsplit(href).query).get("jobOffset", [""])[0]
            if value.isdigit() and int(value) > offset:
                next_offsets.append(int(value))
        if not next_offsets:
            out.complete = True
            break
        offset = min(next_offsets)
    return _finish_listing(out, "Avature", limit)


def _us_date_epoch(value):
    """'10/14/2026' -> epoch at 12:00 UTC on that day (None if missing or malformed)."""
    try:
        return _date_epoch(datetime.strptime(str(value).strip(), "%m/%d/%Y").date().isoformat())
    except (TypeError, ValueError):
        return None


BOFA_SERVLETS = {"jobssearchservlet", "campusjobssearchservlet"}


def fetch_bofa(cfg):
    """Bank of America's careers search service (careers.bankofamerica.com).
    cfg: servlet ('jobssearchservlet' for every role, the default, or
    'campusjobssearchservlet' for student programs) and max."""
    servlet = cfg.get("servlet", "jobssearchservlet")
    if servlet not in BOFA_SERVLETS:
        raise ValueError(f"Bank of America servlet must be one of {sorted(BOFA_SERVLETS)}")
    root = "https://careers.bankofamerica.com"
    out, offset, seen = SourceListing(), 0, set()
    limit = _source_limit(cfg)
    while offset < limit:
        # "rows" is the end index (exclusive), not a page size.
        r = requests.get(f"{root}/services/{servlet}", params={"start": offset, "rows": offset + 100, "search": "getAllJobs"},
                         headers={"User-Agent": UA, "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        if out.total is None and isinstance(data.get("totalMatches"), int):
            out.total = data["totalMatches"]
        jobs = data.get("jobsList") or []        # null once start passes the end
        if not isinstance(jobs, list):
            raise RuntimeError("Bank of America search response has no jobsList")
        page = [{
            "id": str(j.get("jobRequisitionId") or ""),
            "title": j.get("postingTitle") or "",
            "location": ", ".join(p for p in (j.get("city"), j.get("state"), j.get("country")) if p),
            "url": urljoin(root, j.get("jcrURL") or ""),
            "posted": _us_date_epoch(j.get("postedDate")),
            "department": j.get("lob") or "",
        } for j in jobs]
        if _consume_page(out, page, seen, "Bank of America", limit):
            break
        offset += len(jobs)
    return _finish_listing(out, "Bank of America", limit)


_ATOM = "{http://www.w3.org/2005/Atom}"
OLEEO_FEED_CAP = 100      # treat a feed this long as possibly truncated


def fetch_oleeo(cfg):
    """Oleeo (tal.net) vacancy-board Atom feed: Evercore, Jefferies.
    cfg: feed, the board's .../candidate/jobboard/vacancy/<n>/feed/rss URL.
    Oleeo publishes these feeds for syndication; its HTML boards sit behind a
    bot check, which Jobwatch does not try to pass."""
    feed = cfg["feed"]
    parts = urlsplit(feed)
    if parts.scheme != "https" or not (parts.hostname or "").endswith(".tal.net"):
        raise ValueError("Oleeo feed must be an https://<employer>.tal.net URL")
    r = requests.get(feed, headers={"User-Agent": UA, "Accept": "application/atom+xml"}, timeout=TIMEOUT)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    if root.tag != f"{_ATOM}feed":
        raise RuntimeError("Oleeo response is not an Atom feed")
    out, seen = SourceListing(), set()
    for entry in root.findall(f"{_ATOM}entry"):
        link = next((l.get("href") for l in entry.findall(f"{_ATOM}link")
                     if l.get("rel", "alternate") == "alternate"), None) or entry.findtext(f"{_ATOM}id", "")
        url = link.split("?", 1)[0]
        vacancy = re.search(r"/opp/(\d+)", url)
        if not vacancy:
            raise RuntimeError("Oleeo feed entry has no vacancy id")
        if vacancy.group(1) in seen:
            continue
        seen.add(vacancy.group(1))
        content = entry.find(f"{_ATOM}content")
        out.append({
            "id": vacancy.group(1),
            "title": (entry.findtext(f"{_ATOM}title") or "").strip(),
            "location": "",
            "url": url,
            "posted": _iso_epoch(entry.findtext(f"{_ATOM}published") or entry.findtext(f"{_ATOM}updated")),
            # "Application Deadline: 13 Nov 2026 ..." feeds deadline extraction.
            "description": re.sub(r"\s*\n\s*", "\n", "".join(content.itertext())).strip() if content is not None else "",
        })
    if len(out) >= OLEEO_FEED_CAP:
        out.reason = f"Oleeo feed lists {len(out)} vacancies and may be truncated; removals are not tracked"
    else:
        out.complete = True
    return out


def fetch_radancy(cfg):
    """Radancy (TalentBrew) career sites, e.g. careers.moodys.com.
    cfg: host, lang (path prefix, default 'en'), size (page size, default 100), max."""
    host, lang = cfg["host"], cfg.get("lang", "en")
    size = cfg.get("size", 100)
    if isinstance(size, bool) or not isinstance(size, int) or not 1 <= size <= 100:
        raise ValueError("Radancy size must be an integer from 1 to 100")
    base = f"https://{host}/{lang}" if lang else f"https://{host}"
    out, seen, page_no = SourceListing(), set(), 1
    limit = _source_limit(cfg)
    while len(out) < limit:
        r = requests.get(f"{base}/search-jobs/results", params={
            "ActiveFacetID": 0, "CurrentPage": page_no, "RecordsPerPage": size, "Distance": 50,
            "RadiusUnitType": 0, "Keywords": "", "Location": "", "ShowRadius": "False", "IsPagination": "False",
            "FacetType": 0, "SearchResultsModuleName": "Search Results", "SearchFiltersModuleName": "Search Filters",
            "SortCriteria": 0, "SortDirection": 0, "SearchType": 5, "ResultsType": 0},
            headers={"User-Agent": UA, "Accept": "application/json", "X-Requested-With": "XMLHttpRequest"},
            timeout=TIMEOUT)
        r.raise_for_status()
        results = r.json().get("results")
        if not isinstance(results, str):
            raise RuntimeError("Radancy search response has no results markup")
        total = re.search(r'data-total-results="(\d+)"', results)
        if out.total is None and total:
            out.total = int(total.group(1))
        page = []
        for href, inner in re.findall(r'<a\b[^>]*href="(/(?:[a-z]{2}(?:-[a-z]{2})?/)?job/[^"]+)"[^>]*>(.*?)</a>',
                                      results, re.S | re.I):
            jid = href.rstrip("/").rsplit("/", 1)[-1]
            title = re.search(r"<h2[^>]*>(.*?)</h2>", inner, re.S)
            loc = re.search(r'class="job-location"[^>]*>(.*?)</span>', inner, re.S)
            date = re.search(r'class="job-date-posted"[^>]*>(.*?)</span>', inner, re.S)
            page.append({"id": jid if jid.isdigit() else "",
                         "title": html_to_text(title.group(1)) if title else "",
                         "location": html_to_text(loc.group(1)) if loc else "",
                         "url": f"https://{host}{href}",
                         "posted": _us_date_epoch(html_to_text(date.group(1))) if date else None})
        if _consume_page(out, page, seen, "Radancy", limit):
            break
        page_no += 1
    return _finish_listing(out, "Radancy", limit)


def _icims_location(text):
    """'US-NY-New York | UK-London' -> 'New York, NY, US; London, UK'."""
    places = []
    for part in (p.strip() for p in text.split("|")):
        bits = part.split("-", 2)
        places.append(", ".join(reversed(bits)) if len(bits) > 1 and re.fullmatch(r"[A-Z]{2}", bits[0]) else part)
    return "; ".join(p for p in places if p)


def fetch_icims(cfg):
    """iCIMS career portals' embedded search pages (MSCI). cfg: host, the
    portal ('globalcareers-msci.icims.com'), and max."""
    host = cfg["host"]
    if not re.fullmatch(r"[a-z0-9-]+\.icims\.com", host):
        raise ValueError("iCIMS host must be a <portal>.icims.com name")
    out, seen, page_no = SourceListing(), set(), 0
    limit = _source_limit(cfg)
    while len(out) < limit:
        r = requests.get(f"https://{host}/jobs/search", params={"ss": 1, "in_iframe": 1, "pr": page_no},
                         headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        if "iCIMS_JobsTable" not in r.text and not re.search(r"no (?:open )?(?:jobs|positions)", r.text, re.I):
            raise RuntimeError("iCIMS search response has no jobs table")
        pages = re.search(r"Page\s+\d+\s+of\s+(\d+)", r.text)
        page = []
        for card in re.findall(r'<li\b[^>]*class="[^"]*iCIMS_JobCardItem[^"]*"[^>]*>(.*?)</li>', r.text, re.S | re.I):
            link = re.search(r'<a\b[^>]*href="([^"]*/jobs/(\d+)/[^"]*)"[^>]*>(.*?)</a>', card, re.S | re.I)
            if not link:
                raise RuntimeError("iCIMS search page could not parse a result")
            title = re.search(r"<h3[^>]*>(.*?)</h3>", link.group(3), re.S | re.I)
            loc = re.search(r"Job Locations</span>\s*</dt>\s*<dd[^>]*>(.*?)</dd>", card, re.S | re.I)
            posted = re.search(r'<span title="(\d{1,2}/\d{1,2}/\d{4})', card)
            # Some portals (Susquehanna) show a description snippet instead of location and date.
            snippet = re.search(r'<div\b[^>]*class="[^"]*\bdescription\b[^"]*"[^>]*>(.*?)</div>', card, re.S | re.I)
            page.append({"id": link.group(2),
                         "title": html_to_text(title.group(1) if title else link.group(3)),
                         "location": _icims_location(html_to_text(loc.group(1))) if loc else "",
                         "url": html.unescape(link.group(1)).split("?", 1)[0],
                         "posted": _us_date_epoch(posted.group(1)) if posted else None,
                         "description": html_to_text(snippet.group(1)) if snippet else ""})
        if _consume_page(out, page, seen, "iCIMS", limit):
            break
        page_no += 1
        if page_no >= (int(pages.group(1)) if pages else 1):
            out.complete = True
            break
    return _finish_listing(out, "iCIMS", limit)


ADAPTERS = {
    "successfactors": fetch_successfactors,
    "avature": fetch_avature,
    "oracle_hcm": fetch_oracle_hcm,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "smartrecruiters": fetch_smartrecruiters,
    "workday": fetch_workday,
    "amazon_jobs": fetch_amazon_jobs,
    "microsoft": fetch_microsoft,
    "github_listings": fetch_github_listings,
    "github_md": fetch_github_md,
    "linkedin": fetch_linkedin,
    "eightfold": fetch_eightfold,
    "janestreet": fetch_janestreet,
    "phenom": fetch_phenom,
    "marqeta": fetch_marqeta,
    "bofa": fetch_bofa,
    "oleeo": fetch_oleeo,
    "radancy": fetch_radancy,
    "icims": fetch_icims,
}


# ---- per-posting detail fetchers: (cfg, job_id) -> (description, department)
def detail_greenhouse(cfg, job_id):
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{cfg['token']}/jobs/{job_id}",
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    dept = " / ".join(d.get("name", "") for d in data.get("departments") or [] if d.get("name"))
    return html_to_text(data.get("content") or ""), dept


def detail_workday(cfg, job_id):
    url = f"https://{cfg['host']}/wday/cxs/{cfg['tenant']}/{cfg['site']}{job_id}"
    r = requests.get(url, headers={"User-Agent": UA, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    info = r.json().get("jobPostingInfo") or {}
    # startDate is the exact posting date; the listing only says "30+ Days Ago".
    meta = {"posted": _date_epoch(info.get("startDate"))}
    return html_to_text(info.get("jobDescription") or ""), info.get("jobFamilyGroup") or "", meta


def detail_smartrecruiters(cfg, job_id):
    r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{cfg['token']}/postings/{job_id}",
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    sections = (data.get("jobAd") or {}).get("sections") or {}
    text = "\n\n".join(html_to_text((sections.get(k) or {}).get("text") or "") for k in (
        "jobDescription", "qualifications", "additionalInformation"))
    return text.strip(), (data.get("department") or {}).get("label") or ""


def detail_eightfold(cfg, job_id):
    r = requests.get(f"https://{cfg['host']}/api/apply/v2/jobs/{job_id}",
                     params={"domain": cfg["domain"]},
                     headers={"User-Agent": UA, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    return html_to_text(data.get("job_description") or ""), data.get("department") or ""


def detail_oracle_hcm(cfg, job_id):
    r = requests.get(
        f"https://{cfg['host']}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails",
        params={"onlyData": "true", "expand": "all",
                "finder": f'ById;Id="{job_id}",siteNumber={cfg["site"]}'},
        headers={"User-Agent": UA, "Accept": "application/json"}, timeout=TIMEOUT)
    r.raise_for_status()
    item = (r.json().get("items") or [{}])[0]
    text = "\n\n".join(html_to_text(item.get(k) or "") for k in (
        "ExternalDescriptionStr", "ExternalResponsibilitiesStr", "ExternalQualificationsStr")).strip()
    if not text:
        # Goldman Sachs' campus postings leave those empty and describe the program and division instead.
        text = "\n\n".join(html_to_text(item.get(k) or "") for k in (
            "CorporateDescriptionStr", "OrganizationDescriptionStr")).strip()
    return text, item.get("Category") or item.get("Organization") or ""


def detail_lever(cfg, job_id):
    host = "api.eu.lever.co" if cfg.get("region") == "eu" else "api.lever.co"
    r = requests.get(f"https://{host}/v0/postings/{cfg['token']}/{job_id}",
                     headers={"User-Agent": UA}, timeout=TIMEOUT)
    r.raise_for_status()
    data = r.json()
    cats = data.get("categories") or {}
    return _lever_text(data), " / ".join(filter(None, [cats.get("department"), cats.get("team")]))


def detail_linkedin(cfg, job_id):
    """A LinkedIn posting from the guest posting page, through the search's spaced,
    rate-limited client; while LinkedIn is paused this fails at once."""
    from intel.page_text import element_text
    if not str(job_id).isdigit():
        raise ValueError("not a LinkedIn job id")
    r = _linkedin_get(LINKEDIN_POSTING.format(id=job_id))
    r.raise_for_status()
    text = element_text(r.text, "show-more-less-html__markup")
    if not text:
        raise ValueError("the LinkedIn posting has no description")
    criteria = {html.unescape(k): html.unescape(v) for k, v in re.findall(
        r'description__job-criteria-subheader[^>]*>\s*([^<]+?)\s*<.*?description__job-criteria-text[^>]*>\s*([^<]+?)\s*<',
        r.text, re.S)}
    return text, criteria.get("Job function", "")


DETAIL_FETCHERS = {
    "oracle_hcm": detail_oracle_hcm,
    "greenhouse": detail_greenhouse,
    "workday": detail_workday,
    "smartrecruiters": detail_smartrecruiters,
    "eightfold": detail_eightfold,
}
# Fetched only when the user opens a posting, never in the poll's batches.
OPEN_DETAIL_FETCHERS = {"linkedin": detail_linkedin}
# Sources whose listings carry no description: each posting's own link is read
# instead (community lists link to employers' ATS pages, often via a redirect).
PAGE_DETAIL_ATS = {"bofa", "github_md", "avature", "radancy", "icims", "successfactors", "marqeta"}
# Links that only redirect to the posting; the page they land on otherwise is a job board.
REDIRECT_HOSTS = ("zapply.jobs",)
PAGE_MAX_BYTES = 5_000_000
_CHARSET = re.compile(rb"""charset=["']?([\w.:-]+)""", re.I)
_SOFT_404 = re.compile(r"/(?:errors?/)?404\b|/not-?found\b", re.I)     # a closed posting redirected to an error page


def _posting_api(url):
    """(fetcher, cfg, job_id) for a posting link on an ATS whose API serves one
    posting, else None. Covers the ATSs community lists link to most."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    path = [p for p in parts.path.split("/") if p]
    if host.endswith((".myworkdayjobs.com", ".myworkdaysite.com")) and "job" in path[1:]:
        i = path.index("job", 1)
        # tenant.wd1.myworkdayjobs.com/[en-US/]<site>/job/...;
        # wd3.myworkdaysite.com/[en-US/]recruiting/<tenant>/<site>/job/...
        tenant = host.split(".")[0] if host.endswith(".myworkdayjobs.com") else path[i - 2] if i >= 2 else ""
        tail = path[i:-1] if path[-1] == "apply" else path[i:]
        if tenant and len(tail) > 1:
            return detail_workday, {"host": host, "tenant": tenant, "site": path[i - 1]}, "/" + "/".join(tail)
    if host.endswith("greenhouse.io"):
        query = parse_qs(parts.query)
        if len(path) >= 3 and path[1] == "jobs" and path[2].isdigit():
            return detail_greenhouse, {"token": path[0]}, path[2]
        if query.get("for") and query.get("token", [""])[0].isdigit():      # boards.greenhouse.io/embed/job_app
            return detail_greenhouse, {"token": query["for"][0]}, query["token"][0]
    if host in ("jobs.lever.co", "jobs.eu.lever.co") and len(path) >= 2:
        return detail_lever, {"token": path[0], "region": "eu" if ".eu." in host else ""}, path[1]
    if host in ("jobs.smartrecruiters.com", "careers.smartrecruiters.com") and len(path) >= 2:
        posting = re.match(r"\d+", path[1])
        if posting:
            return detail_smartrecruiters, {"token": path[0]}, posting.group(0)
    if host.endswith(".oraclecloud.com") and "sites" in path and "job" in path:
        site, job = path.index("sites") + 1, path.index("job") + 1
        if site < len(path) and job < len(path):
            return detail_oracle_hcm, {"host": host, "site": path[site]}, path[job]
    return None


def _page_url(url):
    """The address of a posting's readable page (iCIMS serves it inside an iframe)."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    icims = re.match(r"/jobs/(\d+)", parts.path)
    if host.endswith(".icims.com") and icims:
        return f"https://{host}/jobs/{icims.group(1)}/job?in_iframe=1"
    if host == "jobs.ashbyhq.com" and parts.path.rstrip("/").endswith("/application"):
        return url.split("?", 1)[0].rstrip("/").removesuffix("/application")
    return url


def _not_linkedin(url):
    """Page links are read by the poll, which leaves LinkedIn alone; LinkedIn's own
    listings are fetched when opened (detail_linkedin)."""
    host = (urlsplit(url).hostname or "").lower()
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        raise ValueError("LinkedIn pages are fetched only for LinkedIn listings, when opened")


def _page_html(r):
    raw = r.content
    if len(raw) > PAGE_MAX_BYTES:
        raise ValueError("the posting page is too large to read")
    found = _CHARSET.search(r.headers.get("content-type", "").encode("latin-1", "ignore")) or _CHARSET.search(raw[:4096])
    try:
        return raw.decode(found.group(1).decode("ascii") if found else "utf-8", "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


def detail_page(url):
    """A posting's description from its link: through its ATS's API when the link
    (after redirects) is one, else the page's JobPosting data or main text."""
    from intel.page_text import posting_description
    api = _posting_api(url)
    if not api:
        _not_linkedin(url)
        with requests.get(_page_url(url), headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"},
                          timeout=TIMEOUT, stream=True) as r:
            r.raise_for_status()
            api = _posting_api(r.url)
            if not api:
                _not_linkedin(r.url)
                if (urlsplit(r.url).hostname or "").lower().endswith(REDIRECT_HOSTS):
                    raise ValueError("the listing's link no longer leads to the posting")
                if _SOFT_404.search(urlsplit(r.url).path):
                    raise ValueError("the posting page is gone")
                text = posting_description(_page_html(r))
                if not text:
                    raise ValueError("the posting page has no readable description")
                return text, ""
    fetcher, cfg, job_id = api
    return fetcher(cfg, job_id)


def describable(cfg, on_open=False):
    """Whether this source's postings can have their descriptions fetched one by one;
    LinkedIn's only when a posting is opened (on_open)."""
    ats = cfg.get("ats")
    return ats in DETAIL_FETCHERS or ats in PAGE_DETAIL_ATS or (on_open and ats in OPEN_DETAIL_FETCHERS)


def fetch_description(cfg, job_id, url=""):
    """(description, department[, meta]) for one posting; raises when it can't be read."""
    ats = cfg.get("ats")
    if ats in DETAIL_FETCHERS:
        return DETAIL_FETCHERS[ats](cfg, job_id)
    if ats in OPEN_DETAIL_FETCHERS:
        return OPEN_DETAIL_FETCHERS[ats](cfg, job_id)
    if ats in PAGE_DETAIL_ATS and url:
        return detail_page(url)
    raise ValueError(f"descriptions can't be fetched from {ats or 'this source'}")


DESCRIPTION_RETRY_HOURS = 6     # after a failed or empty fetch
DESCRIPTION_ATTEMPTS = 3        # then give up on that posting


def description_retry_before():
    """Fetches recorded before this time (ISO, UTC) may be retried."""
    return datetime.fromtimestamp(time.time() - DESCRIPTION_RETRY_HOURS * 3600,
                                  timezone.utc).isoformat(timespec="seconds")


def save_description(con, board, job_id, result):
    """Store a fetch_description result (the caller commits)."""
    text, dept = result[0], result[1]
    meta = result[2] if len(result) > 2 else {}
    store_description(con, board, job_id, text, dept, source="detail")
    # an unchanged description is not rewritten; still record the visit
    con.execute("UPDATE job_text SET fetched_at=? WHERE board=? AND job_id=?", (now(), board, job_id))
    if meta.get("posted"):
        # an exact posting date from the detail record beats a listing estimate
        con.execute("UPDATE job_details SET posted=? WHERE board=? AND job_id=?", (meta["posted"], board, job_id))
        con.execute("UPDATE job_intel SET input_hash=NULL WHERE board=? AND job_id=?", (board, job_id))


def record_description_error(con, board, job_id, error):
    """Count a failed fetch so it backs off (the caller commits)."""
    con.execute(
        """INSERT INTO job_text(board, job_id, fetched_at, attempts, last_error)
           VALUES (?,?,?,1,?) ON CONFLICT(board, job_id) DO UPDATE SET
           attempts=job_text.attempts+1, fetched_at=excluded.fetched_at,
           last_error=excluded.last_error""",
        (board, job_id, now(), f"{type(error).__name__}: {str(error)[:200]}"))
FINANCE_COMPANY_TYPES = ("bulge_bracket", "elite_boutique", "middle_market_bank", "global_bank",
                         "canadian_bank", "commercial_bank", "private_equity", "venture_capital",
                         "hedge_fund", "quant_firm", "asset_manager", "pension_fund", "insurance")


def enrich_descriptions(config, con, budget=None, fetched=None, progress=None):
    """Fetch descriptions for the postings that benefit most, politely.

    Priority: tracked applications, then finance roles, then finance
    employers, newest first.  A per-board cap spreads load; failures back
    off for six hours and give up after three attempts.  ``fetched`` (a list)
    collects the (board, job_id) keys that received a description.
    """
    budget = config.get("description_budget", 60) if budget is None else budget
    if budget <= 0:
        return 0
    boards = {k: v for k, v in config["boards"].items()
              if not k.startswith("_") and not v.get("disabled") and describable(v)}
    if not boards:
        return 0
    per_board = config.get("description_per_board", 12)
    retry_before = description_retry_before()
    # Workday listings say only "Posted 30+ Days Ago"; the detail record has the
    # exact date, so undated Workday rows are revisited (at most weekly).
    date_before = datetime.fromtimestamp(time.time() - 7 * 86400, timezone.utc).isoformat(timespec="seconds")
    dated = [k for k, v in boards.items() if v.get("ats") == "workday"] or [""]
    marks = ",".join("?" * len(boards))
    dmarks = ",".join("?" * len(dated))
    types = ",".join("?" * len(FINANCE_COMPANY_TYPES))
    rows = con.execute(f"""
        SELECT j.board, j.job_id, j.url FROM jobs j
        JOIN job_intel i ON i.board=j.board AND i.job_id=j.job_id
        LEFT JOIN job_text t ON t.board=j.board AND t.job_id=j.job_id
        LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id
        LEFT JOIN job_state s ON s.board=j.board AND s.job_id=j.job_id
        LEFT JOIN applications a ON a.job_key=(j.board||':'||j.job_id)
        WHERE j.board IN ({marks}) AND j.title != '' AND COALESCE(s.status,'active') != 'closed'
          AND (t.board IS NULL OR (COALESCE(t.description,'')='' AND t.attempts < ?
                                   AND COALESCE(t.fetched_at,'') < ?)
               OR (d.posted IS NULL AND j.board IN ({dmarks}) AND COALESCE(t.fetched_at,'') < ?))
        ORDER BY a.job_key IS NOT NULL DESC, i.is_finance DESC,
                 i.company_type IN ({types}) DESC, COALESCE(d.posted, 0) DESC
        LIMIT ?""", [*boards, DESCRIPTION_ATTEMPTS, retry_before, *dated, date_before,
                     *FINANCE_COMPANY_TYPES, budget * 4]).fetchall()
    picked, per = [], {}
    for board, job_id, url in rows:
        if per.get(board, 0) >= per_board:
            continue
        per[board] = per.get(board, 0) + 1
        picked.append((board, job_id, url))
        if len(picked) >= budget:
            break
    if not picked:
        return 0

    def fetch(item):
        board, job_id, url = item
        return item, fetch_description(boards[board], job_id, url)

    done = 0
    completed = 0
    report_progress(progress, "descriptions", completed=0, total=len(picked))
    # Finish any caller writes before waiting on description HTTP requests.
    con.commit()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futures = [ex.submit(fetch, item) for item in picked]
        for fut in as_completed(futures):
            completed += 1
            try:
                (board, job_id, _), result = fut.result()
            except Exception as e:  # recorded, retried later with back-off
                item = picked[futures.index(fut)]
                record_description_error(con, item[0], item[1], e)
                con.commit()
                report_progress(progress, "descriptions", completed=completed, total=len(picked))
                continue
            save_description(con, board, job_id, result)
            if fetched is not None:
                fetched.append((board, job_id))
            done += 1
            con.commit()
            report_progress(progress, "descriptions", completed=completed, total=len(picked))
    con.commit()
    return done


# ================================================================ storage
def db_open(path=None):
    """Open (and migrate) the database.  Schema lives in db_migrations.py."""
    from db_migrations import migrate
    target = path if path is not None else DB_PATH
    con = sqlite3.connect(target)
    # Outwait dashboard writes (a full rescore invalidation takes seconds on a
    # large database) rather than fail a whole poll; matches the refresh thread.
    con.execute("PRAGMA busy_timeout=15000")
    if str(target) != ":memory:":
        # The dashboard reads while the watcher writes; WAL keeps both moving.
        con.execute("PRAGMA journal_mode=WAL")
        # Recommended with WAL: commits stay atomic but skip a disk flush each;
        # a power cut can lose only the last few commits, never corrupt the file.
        con.execute("PRAGMA synchronous=NORMAL")
    migrate(con)
    return con


def known_ids(con, board):
    return {r[0] for r in con.execute("SELECT job_id FROM jobs WHERE board=?", (board,))}


def board_row(con, board):
    r = con.execute("SELECT seeded, failures, last_poll FROM boards WHERE board=?",
                    (board,)).fetchone()
    if r is None:
        con.execute("INSERT INTO boards(board) VALUES (?)", (board,))
        return (0, 0, 0.0)
    return r


# ---- portable state (GitHub Actions mode) ----
def export_state(con):
    """Export the durable subset of SQLite without refreshing record ages.

    Actions starts with a new database on every run.  Persisting only IDs (as
    older state files did) made every imported row look newly seen, so the
    90-day pruning window could never expire and state.json grew forever.
    """
    state = {"version": 2, "boards": {}, "alerted": []}
    for board, seeded, last_poll, failures in con.execute(
            "SELECT board, seeded, last_poll, failures FROM boards"):
        jobs = [list(r) for r in con.execute(
            "SELECT job_id, last_seen FROM jobs WHERE board=? ORDER BY job_id",
            (board,))]
        state["boards"][board] = {"seeded": seeded, "jobs": jobs,
                                  "lp": int(last_poll or 0),
                                  "f": failures or 0}
    state["alerted"] = [list(r) for r in con.execute(
        "SELECT key, ts FROM alerted ORDER BY key")]
    state["recent"] = [list(r) for r in con.execute(
        "SELECT ts, company, title, url, location, salary FROM recent")]
    state["pending"] = [list(r) for r in con.execute(
        "SELECT sub, tier, ts, company, title, url, location, salary, posted "
        "FROM pending")]
    state["kv"] = dict(con.execute("SELECT k, v FROM kv"))
    tmp = STATE_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, separators=(",", ":")))
    tmp.replace(STATE_JSON)


def import_state(con):
    state = json.loads(STATE_JSON.read_text())
    ts = now()
    for board, b in state.get("boards", {}).items():
        con.execute(
            "INSERT OR REPLACE INTO boards(board, seeded, last_poll, failures) "
            "VALUES (?,?,?,?)",
            (board, b.get("seeded", 1), b.get("lp", 0), b.get("f", 0)))
        # v1 stored only ``ids``.  Accept it once for a seamless migration;
        # v2 retains last_seen so stale jobs can actually age out.
        jobs = b.get("jobs")
        if jobs is None:
            jobs = [(job_id, ts) for job_id in b.get("ids", [])]
        con.executemany(
            """INSERT OR IGNORE INTO jobs
               (board, job_id, title, location, url, first_seen, last_seen)
               VALUES (?,?,?,?,?,?,?)""",
            [(board, str(r[0]), "", "", "", r[1] or ts, r[1] or ts)
             for r in jobs if r])
    alerted = state.get("alerted", [])
    con.executemany(
        "INSERT OR IGNORE INTO alerted VALUES (?,?)",
        [(str(r[0]), (r[1] if len(r) > 1 else ts))
         if isinstance(r, (list, tuple)) else (str(r), ts)
         for r in alerted if r])
    con.executemany("INSERT INTO recent VALUES (?,?,?,?,?,?)",
                    [tuple(r) + ("",) * (6 - len(r))
                     for r in state.get("recent", [])])
    con.executemany("INSERT INTO pending VALUES (?,?,?,?,?,?,?,?,?)",
                    [tuple(r) + (None,) * (9 - len(r))
                     for r in state.get("pending", [])])
    con.executemany("INSERT OR REPLACE INTO kv VALUES (?,?)",
                    list(state.get("kv", {}).items()))
    con.commit()
    log(f"imported state.json: {len(state.get('boards', {}))} boards")


# ================================================================ dedupe
def canon_url(url):
    if not url:
        return ""
    p = urlsplit(url.strip().lower())
    host = p.netloc.replace("www.", "")
    path = p.path.rstrip("/")
    return f"{host}{path}"


_CO_NOISE = re.compile(r"\(.*?\)|\b(incorporated|corporation|company|inc|llc|ltd|corp|co)\b\.?",
                       re.I)


def failure_backoff(failures):
    """Seconds to wait before retrying a source that keeps failing: none for a
    blip, then doubling from 5 minutes to a 2-hour ceiling."""
    if not isinstance(failures, int) or failures < 3:
        return 0
    return min(7200, 300 * 2 ** min(failures - 3, 5))


def name_key(company, title, normalize=False):
    c = company or ""
    if normalize:               # 'Stripe, Inc.' / 'Stripe (YC S10)' -> 'Stripe'
        c = _CO_NOISE.sub("", c)
    c = re.sub(r"[^a-z0-9]+", "", c.lower())
    t = re.sub(r"[^a-z0-9]+", "", (title or "").lower())
    return f"nk:{c}|{t}" if c and t else ""


def place_key(location):
    """The first place a posting names ('Toronto, ON' and 'Toronto, Ontario,
    Canada' agree), so one title in two cities is two jobs."""
    first = re.split(r"[,;|/(]|\s[-–]\s", location or "")[0]
    return re.sub(r"[^a-z0-9]+", "", first.lower())


def dedupe_keys(job):
    """LinkedIn hides direct apply URLs from guests, so a LinkedIn posting and
    its ATS twin never share a URL — company|title|place keys (exact +
    normalized company) do the cross-source matching instead."""
    ks = []
    cu = canon_url(job.get("url", ""))
    if cu:
        ks.append(f"url:{cu}")
    place = place_key(job.get("location", ""))
    for normalize in (False, True):
        nk = name_key(job.get("company", ""), job.get("title", ""), normalize=normalize)
        if nk:
            nk = f"{nk}|{place}" if place else nk
            if nk not in ks:
                ks.append(nk)
    return ks


def known_on_board(con, board, job, fresh_ids=()):
    """An older posting on this board has this title, company and place: a
    re-listed link (README links change), not a new job. Postings new in this
    same cycle (two requisitions for one title) never hide each other."""
    for job_id, company in con.execute(
            "SELECT j.job_id, COALESCE(d.company, '') FROM jobs j "
            "LEFT JOIN job_details d ON d.board=j.board AND d.job_id=j.job_id "
            "WHERE j.board=? AND j.title=? AND j.location=? LIMIT 50",
            (board, job.get("title") or "", job.get("location") or "")):
        if job_id == job["id"] or job_id in fresh_ids:
            continue
        if not job.get("company") or not company or company.casefold() == job["company"].casefold():
            return True
    return False


def already_alerted(con, job):
    for k in dedupe_keys(job):
        if con.execute("SELECT 1 FROM alerted WHERE key=?", (k,)).fetchone():
            return True
    return False


def mark_alerted(con, job):
    ts = now()
    for k in dedupe_keys(job):
        con.execute("INSERT OR IGNORE INTO alerted VALUES (?,?)", (k, ts))


# ================================================================ matching
class Filt:
    def __init__(self, d, fallback=None):
        fb = fallback or {}
        self.include = self._c(d.get("include", fb.get("include")))
        self.exclude = self._c(d.get("exclude", fb.get("exclude")))
        self.location = self._c(d.get("location", fb.get("location")))

    @staticmethod
    def _c(pat):
        return re.compile(pat, re.I) if pat else None

    def ok(self, job):
        if self.include and not self.include.search(job["title"]):
            return False
        if self.exclude and self.exclude.search(job["title"]):
            return False
        if self.location and job["location"] and not self.location.search(job["location"]):
            return False
        return True


def _resolve_secret(v, quiet=False):
    """'env:NAME' in subscribers.json reads NAME from the environment, so
    webhook URLs never live in the repo (GitHub Actions secrets). quiet=True
    for optional per-tier hooks that silently fall back to the main one."""
    if isinstance(v, str) and v.startswith("env:"):
        name = v[4:]
        v = os.environ.get(name, "")
        if not v and not quiet:
            log(f"! secret {name} not set — delivery channel disabled")
    return v


def load_subscribers(global_filters):
    subs = json.loads(SUBSCRIBERS.read_text(encoding="utf-8"))
    out = []
    for name, s in subs.items():
        if name.startswith("_") or s.get("mute"):
            continue
        out.append({
            "name": name,
            "companies": set(s.get("companies", ["all"])),
            "filt": Filt(s.get("filters", {}), fallback=global_filters),
            "watch": Filt._c(s.get("watchlist", "")),
            "mention": s.get("discord_mention", ""),
            "ping_categories": set(s.get(
                "ping_categories", ["intern", "new_grad", "other"])),
            "max_ping_jobs": max(0, int(s.get("max_ping_jobs", 10))),
            "ops": bool(s.get("ops")),
            "digest": bool(s.get("digest")),
            # deadline/interview/follow-up reminders and taken-down saved jobs
            "reminders": bool(s.get("reminders", True)),
            "discord": _resolve_secret(s.get("discord_webhook", "")),
            "ping_hooks": {k: _resolve_secret(v, quiet=True)
                           for k, v in (s.get("ping_webhooks") or {}).items()},
            "feeds": {k: _resolve_secret(v, quiet=True)
                      for k, v in (s.get("feeds") or {}).items()},
            "telegram_chat": str(s.get("telegram_chat_id", "") or ""),
            # finance fit-tier alerting (alert_mode: "fit"); legacy regex otherwise
            "alert_mode": s.get("alert_mode", "regex"),
            "fit_tiers": {"urgent": 90, "high": 75, "digest": 55, **(s.get("fit_tiers") or {})},
            "finance_only": bool(s.get("finance_only", True)),
            "cooldown_minutes": int(s.get("cooldown_minutes", 60)),
            "urgent_per_company": int(s.get("urgent_per_company", 2)),
            # saved views with Alerts on act as Discord filters
            "saved_search_alerts": bool(s.get("saved_search_alerts", True)),
            # False = only saved-view alerts, no general new-posting alerts
            "match_alerts": bool(s.get("match_alerts", True)),
        })
    return out


# ================================================================ delivery
def _post_with_retry(fn, what):
    for attempt in range(SEND_RETRIES):
        try:
            r = fn()
            if r.status_code == 429:
                try:
                    wait = float(r.headers.get("Retry-After") or
                                 r.json().get("retry_after", 2))
                except Exception:
                    wait = 2.0
                time.sleep(min(wait, 15))
                continue
            r.raise_for_status()
            return True
        except Exception as e:
            if attempt == SEND_RETRIES - 1:
                log(f"! send failed ({what}): {e}")
                return False
            time.sleep(2 ** attempt)
    return False


# ---- rendering: group by company, tag/tier by role type ----
TAG_INTERN = re.compile(r"\bintern(ship)?\b|\bco.?op\b", re.I)
TAG_GRAD = re.compile(r"new ?grad|graduate|early career|university|campus|entry.level|junior", re.I)


def _category(title):
    if TAG_INTERN.search(title):
        return "intern"
    if TAG_GRAD.search(title):
        return "new_grad"
    return "other"


def _tag(title):
    return {"intern": "🛠️", "new_grad": "🎓", "other": "💼"}[_category(title)]


def _short_loc(loc):
    """Trim noisy country suffixes for display ('Austin, TX, United States'
    -> 'Austin, TX'). Filters still see the full string."""
    return re.sub(r"\s*,?\s*(united states of america|united states|usa)\s*$",
                  "", (loc or "").strip(), flags=re.I)


def _group(jobs):
    """[(board, job)] -> [(company, [job])], companies A-Z, titles A-Z.
    Groups case-insensitively — direct boards say 'stripe' while aggregators
    say 'Stripe' — and displays the best-cased variant."""
    groups = {}
    for b, j in jobs:
        raw = (j.get("company") or b.replace("_", " ")).strip()
        g = groups.setdefault(raw.casefold(), {"name": raw, "jobs": []})
        if raw != raw.lower() and g["name"] == g["name"].lower():
            g["name"] = raw            # prefer 'Stripe' over 'stripe'
        g["jobs"].append(j)
    return sorted(((g["name"], sorted(g["jobs"], key=lambda x: x["title"]))
                   for g in groups.values()), key=lambda kv: kv[0].lower())


def send_discord_ping(webhook, jobs, kind, mention="", omitted=0):
    """The apply-now tier: one rich embed PER JOB (clickable title, location,
    salary) so each ping is a self-contained application card. kind is
    'internship' or 'new grad role'. The header line is plain content, so
    pings are also findable via Discord search."""
    color = 0xF1C40F if kind == "internship" else 0xE67E22
    ts = datetime.now(timezone.utc).isoformat()
    # content is what phone push previews show — plain text (markdown would
    # render as literal ** in the notification), one compact line per job so
    # you know company/role/location without opening Discord
    lines = []
    for b, j in jobs:
        company = j.get("company") or b.replace("_", " ")
        line = f"🎯 {company} — {j['title']}"
        loc = _short_loc(j["location"])
        if loc:
            line += f" · {loc}"
        age = _rel_age(j.get("posted"))
        if age:
            line += f" · {age}"
        lines.append(line[:170])
    shown = lines[:5]
    if len(lines) > 5:
        shown.append(f"…and {len(lines) - 5} more")
    if omitted:
        shown.append(f"📥 {omitted} lower-priority match{'es' if omitted != 1 else ''} "
                     "saved to the quiet feeds")
    header = "\n".join(shown)
    if mention:
        header = f"{mention}\n{header}"
    embeds = []
    for b, j in jobs:
        company = j.get("company") or b.replace("_", " ")
        parts = []
        loc = _short_loc(j["location"])
        if loc:
            parts.append(f"📍 {loc}")
        age = _rel_age(j.get("posted"))
        if age:
            parts.append(f"🕒 {age}")
        sal = (j.get("salary") or "").strip()
        if sal:
            parts.append(f"💰 {sal[:60]}")
        embeds.append({
            "title": f"{company} — {j['title']}"[:256],
            "url": j["url"],
            "description": "\n".join(parts),
            "color": color,
            "timestamp": ts,
            "footer": {"text": "jobwatch"},
        })
    ok = True
    for i in range(0, len(embeds), 10):     # 10 embeds max per message
        payload = {"embeds": embeds[i:i + 10]}
        if i == 0:
            payload["content"] = header
        ok &= _post_with_retry(
            lambda p=payload: requests.post(webhook, json=p, timeout=10),
            "discord")
    return ok


def _feed_blocks(jobs, watch=None):
    """[(header, [lines])] — one block per company; ⭐ marks watchlist
    companies so they pop while scrolling."""
    blocks = []
    for company, js in _group(jobs):
        star = "⭐ " if watch and watch.search(company) else ""
        lines = []
        for j in js:
            title = j["title"].replace("[", "(").replace("]", ")").strip()
            if len(title) > 90:
                title = title[:87] + "…"
            loc = _short_loc(j["location"])
            if len(loc) > 40:
                loc = loc[:37] + "…"
            line = f"{_tag(j['title'])} [{title}]({j['url']})"
            if loc:
                line += f" · {loc}"
            age = _rel_age(j.get("posted"))
            if age:
                line += f" · {age}"
            sal = (j.get("salary") or "").strip()
            if sal:
                line += f" · 💰 {sal[:40]}"
            lines.append(line)
        blocks.append((f"{star}**{company}**", lines))
    return blocks


def _pack(blocks, limit):
    """Pack (header, lines) blocks into strings ≤ limit chars. A company
    split across chunks repeats its header with '(cont.)' so no job ever
    floats under the wrong company."""
    descs, cur = [], ""
    for header, lines in blocks:
        block = "\n".join([header] + lines)
        if len(block) <= limit - (len(cur) + 2 if cur else 0):
            cur = f"{cur}\n\n{block}" if cur else block
            continue
        if cur:
            descs.append(cur)
            cur = ""
        buf = header
        for line in lines:
            if len(buf) + len(line) + 1 > limit:
                descs.append(buf)
                buf = f"{header} *(cont.)*"
            buf += "\n" + line
        cur = buf
    if cur:
        descs.append(cur)
    return descs


def send_discord_feed(webhook, label, jobs, color, watch=None):
    """Silent digest embed(s): jobs grouped under bold company names, @silent
    flag so the channel fills up quietly for browsing whenever."""
    descs = _pack(_feed_blocks(jobs, watch), 3500)
    ts = datetime.now(timezone.utc).isoformat()
    n = len(jobs)
    ok = True
    for i, desc in enumerate(descs):
        title = label.format(n=n, s="s" if n != 1 else "")
        if len(descs) > 1:
            title += f"  ·  {i + 1}/{len(descs)}"
        payload = {"embeds": [{"title": title, "description": desc,
                               "color": color, "timestamp": ts,
                               "footer": {"text": "jobwatch · quiet digest"}}],
                   "flags": 4096}
        ok &= _post_with_retry(
            lambda p=payload: requests.post(webhook, json=p, timeout=10),
            "discord")
    return ok


def send_discord_note(webhook, title, desc, color):
    """Single small embed for digests / ops notices."""
    payload = {"embeds": [{"title": title, "description": desc[:3900],
                           "color": color, "footer": {"text": "jobwatch"}}]}
    return _post_with_retry(
        lambda: requests.post(webhook, json=payload, timeout=10), "discord")


def send_telegram(chat_id, text):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        log("! telegram configured but TELEGRAM_BOT_TOKEN not set")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    ok = True
    for chunk in _chunks(text, 3900):
        ok &= _post_with_retry(
            lambda c=chunk: requests.post(url, json={
                "chat_id": chat_id, "text": c, "disable_web_page_preview": True
            }, timeout=10),
            "telegram")
    return ok


def _chunks(s, n):
    parts, cur = [], ""
    for block in s.split("\n\n"):
        if len(cur) + len(block) + 2 > n and cur:
            parts.append(cur)
            cur = block
        else:
            cur = f"{cur}\n\n{block}" if cur else block
    if cur:
        parts.append(cur)
    return parts


def _telegram_text(jobs):
    parts = [f"🆕 {len(jobs)} new job{'s' if len(jobs) != 1 else ''}"]
    for company, js in _group(jobs):
        lines = [f"— {company} —"]
        for j in js:
            loc = _short_loc(j["location"])
            lines.append(f"{_tag(j['title'])} {j['title']}"
                         + (f" · {loc}" if loc else ""))
            lines.append(f"   {j['url']}")
        parts.append("\n".join(lines))
    return "\n\n".join(parts)


def deliver(sub, jobs, con):
    """The feeds (🛠️ intern / 💼 full-time) receive EVERY matching job — they
    are the complete archive, queued in `pending` and posted @silent.
    Configured categories at watchlist companies also fire a ranked, capped
    loud ping (rich card per job + optional mention). Overflow remains in the
    feeds, preserving coverage without creating a notification firehose."""
    watch = sub.get("watch")
    ping_candidates = []
    ts = now()
    for b, j in jobs:
        cat = _category(j["title"])
        # watchlist matches company only — titles like 'Salesforce Developer
        # Intern' at a consultancy must not count
        if (watch and watch.search(j.get("company") or b)
                and cat in sub["ping_categories"]):
            ping_candidates.append((b, j))
        con.execute(
            "INSERT INTO pending VALUES (?,?,?,?,?,?,?,?,?)",
            (sub["name"], "intern" if cat == "intern" else "ft", ts,
             j.get("company") or b.replace("_", " "), j["title"],
             j["url"], j.get("location") or "", j.get("salary") or "",
             j.get("posted")))

    # Keep loud alerts scarce and useful. Early-career roles sort first, then
    # the freshest postings; every omitted match is still retained in the
    # complete quiet feeds above.
    priority = {"intern": 0, "new_grad": 1, "other": 2}
    ping_candidates.sort(key=lambda pair: (
        priority[_category(pair[1]["title"])],
        -(_posted_epoch(pair[1].get("posted")) or 0),
        (pair[1].get("company") or pair[0]).casefold(),
        pair[1]["title"].casefold()))
    limit = sub["max_ping_jobs"]
    selected = ping_candidates[:limit]
    omitted = len(ping_candidates) - len(selected)
    tiers = {"ping_intern": [], "ping_ft": []}
    for pair in selected:
        cat = _category(pair[1]["title"])
        tiers["ping_intern" if cat == "intern" else "ping_ft"].append(pair)

    main = sub["discord"]
    ok = True
    if tiers["ping_intern"]:
        hook = sub["ping_hooks"].get("intern") or main
        if hook:
            ok &= send_discord_ping(hook, tiers["ping_intern"],
                                    "internship", mention=sub["mention"],
                                    omitted=omitted)
            omitted = 0
    if tiers["ping_ft"]:
        hook = sub["ping_hooks"].get("full_time") or main
        if hook:
            ok &= send_discord_ping(hook, tiers["ping_ft"],
                                    "role", mention=sub["mention"],
                                    omitted=omitted)
    hot_all = tiers["ping_intern"] + tiers["ping_ft"]
    if sub["telegram_chat"] and hot_all:
        ok &= send_telegram(sub["telegram_chat"],
                            "🎯 apply now\n\n" + _telegram_text(hot_all))
    for b, j in jobs:
        con.execute("INSERT INTO sends VALUES (?,?,?,?,?)",
                    (now(), sub["name"], b, j["id"], int(ok)))
    return ok


# ---- finance fit-tier alerts ------------------------------------------------
def fetch_intel(con, gated):
    """{(board, job_id): intel row} for gated jobs that have been scored."""
    keys = [(b, j["id"]) for b, js in gated.items() for j in js]
    out = {}
    for chunk in range(0, len(keys), 300):
        part = keys[chunk:chunk + 300]
        where = " OR ".join("(board=? AND job_id=?)" for _ in part)
        for row in con.execute(
                f"""SELECT board, job_id, fit, fit_detail, facts, badges, urgency, eff_deadline,
                           company_key, is_finance, cycle
                    FROM job_intel WHERE fit_detail IS NOT NULL AND ({where})""",
                [v for pair in part for v in pair]):
            out[(row[0], row[1])] = {
                "fit": row[2], "detail": json.loads(row[3] or "{}"), "facts": json.loads(row[4] or "{}"),
                "badges": (row[5] or "").replace("_", " ").split(), "urgency": row[6],
                "deadline": row[7], "company_key": row[8], "is_finance": bool(row[9]), "cycle": row[10],
            }
    return out


def alert_tier(sub, intel, profile, watched):
    """'urgent' | 'high' | 'digest' | None for one scored job."""
    tiers = sub["fit_tiers"]
    if sub["finance_only"] and not intel["is_finance"]:
        return None
    fit = intel["fit"]
    age = (intel["detail"] or {}).get("posting_age_hours")
    on_target_cycle = intel.get("cycle") in set(profile.get("target_cycles") or [])
    if fit >= tiers["urgent"] or (
            intel["company_key"] in watched and on_target_cycle and age is not None
            and age <= 12 and fit >= tiers["high"] - 10):
        return "urgent"
    if fit >= tiers["high"]:
        return "high"
    if fit >= tiers["digest"]:
        return "digest"
    return None


def _finance_card(job, intel, company, tier, dashboard_url):
    facts = intel["facts"] or {}
    cls = facts.get("classification") or {}
    cyc = facts.get("cycle") or {}
    detail = intel["detail"] or {}
    role = cls.get("category_label", "")
    if cls.get("subcategory_label"):
        role += f" — {cls['subcategory_label']}"
    lines = []
    loc = _short_loc(job.get("location") or "")
    if loc:
        lines.append(f"📍 {loc}")
    if role and cls.get("is_finance"):
        lines.append(f"🏦 {role}")
    if cyc.get("label"):
        lines.append(f"🎓 {cyc['label']}")
    lines.append(f"⭐ Fit: {intel['fit']}/100")
    age = _rel_age(job.get("posted"))
    if age:
        lines.append(f"🕒 Posted: {age.replace('🔥 ', '')}")
    if intel.get("deadline"):
        try:
            due = datetime.fromisoformat(intel["deadline"]).strftime("%b %d").replace(" 0", " ")
        except ValueError:
            due = intel["deadline"]
        lines.append(f"📅 Deadline: {due}")
    sal = (job.get("salary") or "").strip()
    if sal:
        lines.append(f"💰 {sal[:60]}")
    reasons = detail.get("reasons") or []
    if reasons:
        lines.append("\n**Why:**\n" + "\n".join(f"• {r.lower()}" for r in reasons[:5]))
    concerns = detail.get("concerns") or []
    if concerns:
        lines.append("**Watch out:** " + ", ".join(c.lower() for c in concerns[:3]))
    key = f"{job.get('_board', '')}:{job['id']}"
    links = f"[Apply ↗]({job['url']})"
    if dashboard_url:
        links += f" · [View in Foothold]({dashboard_url.rstrip('/')}/#/opportunities?job={key})"
    lines.append("\n" + links)
    color = {"urgent": 0xE5484D, "high": 0x30A46C}.get(tier, 0x8B95A7)
    return {
        "title": f"{company} — {job['title']}"[:256],
        "url": job["url"],
        "description": "\n".join(lines)[:3900],
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": f"jobwatch · {tier} tier"},
    }


def send_finance_alerts(webhook, cards, tier, mention=""):
    header = {"urgent": "🚨 HIGH-PRIORITY FINANCE ROLE", "high": "⭐ HIGH-FIT FINANCE ROLE"}[tier]
    if len(cards) > 1:
        header += f"S ({len(cards)})"
    lines = [header] + [f"• {c['title']}"[:170] for c in cards[:5]]
    content = "\n".join(lines)
    if mention and tier == "urgent":
        content = f"{mention}\n{content}"
    ok = True
    for n, chunk in enumerate(_embed_chunks(cards)):
        payload = {"embeds": chunk}
        if n == 0:
            payload["content"] = content
        if tier != "urgent":
            payload["flags"] = 4096         # high-fit: visible, but no push buzz
        ok &= _post_with_retry(lambda p=payload: requests.post(webhook, json=p, timeout=10), "discord")
    return ok


DISCORD_EMBED_CHARS = 5500      # Discord rejects a message whose embeds total over 6000 characters


def _embed_size(card):
    parts = [card.get("title", ""), card.get("description", ""),
             (card.get("footer") or {}).get("text", ""), (card.get("author") or {}).get("name", "")]
    parts += [f.get("name", "") + f.get("value", "") for f in card.get("fields") or []]
    return sum(len(str(p)) for p in parts)


def _embed_chunks(cards):
    """Up to 10 embeds per message and under Discord's total character limit."""
    chunk, size = [], 0
    for card in cards:
        n = _embed_size(card)
        if chunk and (len(chunk) == 10 or size + n > DISCORD_EMBED_CHARS):
            yield chunk
            chunk, size = [], 0
        chunk.append(card)
        size += n
    if chunk:
        yield chunk


def deliver_fit(sub, jobs, intel_rows, con, config, profile):
    """Tiered delivery: urgent (loud), high fit (quiet card), digest (feed).

    A per-company cooldown keeps one firm's posting burst from flooding the
    urgent channel; overflow is downgraded to the high-fit tier.
    """
    watched = {r[0] for r in con.execute("SELECT company_key FROM company_prefs WHERE watched=1")}
    cutoff = datetime.fromtimestamp(time.time() - sub["cooldown_minutes"] * 60, timezone.utc).isoformat(
        timespec="seconds")
    recent = {}
    for company, n in con.execute(
            "SELECT company, COUNT(*) FROM alert_log WHERE sub=? AND tier='urgent' AND ts > ? GROUP BY company",
            (sub["name"], cutoff)):
        recent[company] = n
    buckets = {"urgent": [], "high": [], "digest": []}
    for board, job in jobs:
        intel = intel_rows[(board, job["id"])]
        tier = alert_tier(sub, intel, profile, watched)
        if not tier:
            continue
        company = (intel["facts"].get("company") or {}).get("name") or job.get("company") or board
        if tier == "urgent":
            if recent.get(company, 0) >= sub["urgent_per_company"]:
                tier = "high"
            else:
                recent[company] = recent.get(company, 0) + 1
        buckets[tier].append((board, job, intel, company))

    ts = now()
    dashboard_url = config.get("dashboard_url", "http://127.0.0.1:8787")
    cap = sub["max_ping_jobs"]
    ok = True
    for tier in ("urgent", "high"):
        items = sorted(buckets[tier], key=lambda t: -t[2]["fit"])
        shown, overflow = items[:cap], items[cap:]
        buckets["digest"].extend(overflow)
        if not shown:
            continue
        hook = (sub["ping_hooks"].get(tier) or sub["ping_hooks"].get("full_time")
                or sub["discord"])
        cards = [_finance_card({**job, "_board": board}, intel, company, tier, dashboard_url)
                 for board, job, intel, company in shown]
        if hook and not send_finance_alerts(hook, cards, tier, sub["mention"]):
            ok = False
            buckets["digest"].extend(shown)     # not lost: the queued feed retries delivery
            continue
        if sub["telegram_chat"]:
            text = "\n\n".join(
                f"{'🚨' if tier == 'urgent' else '⭐'} {company} — {job['title']}\n"
                f"⭐ Fit {intel['fit']}/100 · {_short_loc(job.get('location') or '')}\n{job['url']}"
                for board, job, intel, company in shown)
            ok &= send_telegram(sub["telegram_chat"], text)
        con.executemany("INSERT INTO alert_log VALUES (?,?,?,?,?)",
                        [(ts, sub["name"], tier, company, f"{board}:{job['id']}")
                         for board, job, intel, company in shown])
    for board, job, intel, company in buckets["digest"]:
        cat = _category(job["title"])
        con.execute("INSERT INTO pending VALUES (?,?,?,?,?,?,?,?,?)",
                    (sub["name"], "intern" if cat == "intern" else "ft", ts, company, job["title"],
                     job["url"], job.get("location") or "", job.get("salary") or "", job.get("posted")))
    sent = sum(len(v) for v in buckets.values())
    for board, job in jobs:
        con.execute("INSERT INTO sends VALUES (?,?,?,?,?)", (ts, sub["name"], board, job["id"], int(ok)))
    return sent


def notify_saved_searches(config, con, subs, store):
    """Local mode: saved searches with notify=1 report new matches once."""
    targets = [s for s in subs if s.get("saved_search_alerts") and s["discord"]]
    searches = con.execute(
        "SELECT id, name, query, COALESCE(last_notified_at, created_at) FROM saved_searches WHERE notify=1"
    ).fetchall()
    if not searches or not targets:
        return 0
    from job_query import FROM_CLAUSE, build_where, resume_params
    resume = con.execute("SELECT enabled FROM candidate_resume WHERE id=1").fetchone()
    sent = 0
    for sid, name, query, since in searches:
        params = resume_params({**json.loads(query or "{}"), "since": since}, bool(resume and resume[0]))
        where, args = build_where(params, store.fts, store.watched)
        rows = con.execute(
            f"SELECT i.company_name, j.title, j.url, i.fit {FROM_CLAUSE} WHERE {' AND '.join(where)} "
            f"ORDER BY i.fit DESC LIMIT 10", args).fetchall()
        con.execute("UPDATE saved_searches SET last_notified_at=? WHERE id=?", (now(), sid))
        if not rows:
            continue
        desc = "\n".join(f"**{r[3]}** · [{r[0]} — {r[1]}]({r[2]})" for r in rows)
        for sub in targets:
            send_discord_note(sub["discord"], f"🔎 {len(rows)} new for saved search “{name}”", desc, 0x3E63DD)
        sent += len(rows)
    return sent


def flush_feeds(config, con, subs, force=False):
    """Send queued feed jobs as one quiet digest per stream once the oldest
    queued job is feed_flush_minutes old (or the queue is huge). Pings never
    wait — this only paces the browse-later material."""
    flush_min = config.get("feed_flush_minutes", 180)
    for sub in subs:
        rows = con.execute(
            "SELECT tier, ts, company, title, url, location, salary, posted "
            "FROM pending WHERE sub=?", (sub["name"],)).fetchall()
        if not rows:
            continue
        oldest = min(r[1] for r in rows)
        age_min = (datetime.now(timezone.utc)
                   - datetime.fromisoformat(oldest)).total_seconds() / 60
        if not force and age_min < flush_min and len(rows) < 80:
            continue
        by_tier = {"intern": [], "ft": []}
        seen = set()
        for tier, ts, company, title, url, location, salary, posted in rows:
            key = (canon_url(url), company.casefold(), title.casefold())
            if key in seen:     # same job queued twice via near-identical rows
                continue
            seen.add(key)
            by_tier.setdefault(tier, []).append(
                (ts, {"company": company, "title": title, "url": url,
                      "location": location, "salary": salary, "posted": posted}))
        watch = sub.get("watch")
        headers = {"intern": ("🛠️ {n} new internship{s}", 0x5865F2, "intern"),
                   "ft": ("💼 {n} new-grad / full-time role{s}", 0x95A5A6, "full_time")}
        for tier, queued in by_tier.items():
            if not queued:
                continue
            title_fmt, color, feed = headers.get(tier, headers["ft"])
            channels = {}
            hook = sub["feeds"].get(feed) or sub["discord"]
            if hook:
                channels["discord"] = lambda items, h=hook: send_discord_feed(h, title_fmt, items, color, watch)
            if sub["telegram_chat"]:
                channels["telegram"] = lambda items: send_telegram(sub["telegram_chat"], _telegram_text(items))
            # Each channel remembers how far it got, so one failing channel never
            # makes the others resend; a failing channel waits before retrying.
            reached = [_deliver_feed(con, sub["name"], tier, name, send, queued)
                       for name, send in channels.items()]
            cutoff = min(reached) if reached else max(ts for ts, _ in queued)
            if cutoff:
                con.execute("DELETE FROM pending WHERE sub=? AND tier=? AND ts<=?", (sub["name"], tier, cutoff))
        log(f"  -> {sub['name']}: flushed queued feed jobs")


FEED_RETRY_SECONDS = 1800


def _deliver_feed(con, sub, tier, channel, send, queued):
    """Send this channel the queued jobs it has not had yet; returns the newest
    queue timestamp it has received ('' when none)."""
    key = f"feed_sent:{sub}:{tier}:{channel}"
    row = con.execute("SELECT v FROM kv WHERE k=?", (key,)).fetchone()
    state = json.loads(row[0]) if row else {}
    upto = state.get("upto", "")
    fresh = [(ts, item) for ts, item in queued if ts > upto]
    if not fresh or time.time() - state.get("failed_at", 0) < FEED_RETRY_SECONDS:
        return upto
    if send([("", item) for _, item in fresh]):
        state = {"upto": max(ts for ts, _ in fresh)}
    else:
        state["failed_at"] = time.time()
    con.execute("INSERT OR REPLACE INTO kv(k, v) VALUES (?, ?)", (key, json.dumps(state)))
    return state.get("upto", "")


def maybe_digest(config, con, subs):
    """Once a day (after digest_hour_utc), send subscribers with digest:true a
    summary of the last 24h — doubles as an is-it-alive heartbeat."""
    hour = config.get("digest_hour_utc")
    if hour is None:
        return
    now_dt = datetime.now(timezone.utc)
    if now_dt.hour < hour:
        return
    today = now_dt.date().isoformat()
    row = con.execute("SELECT v FROM kv WHERE k='last_digest'").fetchone()
    if row and row[0] >= today:
        return
    con.execute("INSERT OR REPLACE INTO kv VALUES ('last_digest', ?)", (today,))

    rows = con.execute(
        "SELECT company, COUNT(*) FROM recent WHERE ts > strftime('%Y-%m-%dT%H:%M:%S', 'now','-1 day') "
        "GROUP BY company ORDER BY COUNT(*) DESC, company").fetchall()
    total = sum(n for _, n in rows)
    n_boards = con.execute(
        "SELECT COUNT(*) FROM boards WHERE seeded=1").fetchone()[0]
    broken = [b for (b,) in con.execute(
        "SELECT board FROM boards WHERE failures >= 10 ORDER BY board")]

    if rows:
        top = "\n".join(f"• **{c}** — {n}" for c, n in rows[:10])
        more = f"\n…plus {len(rows) - 10} more companies" if len(rows) > 10 else ""
        desc = (f"**{total}** new job{'s' if total != 1 else ''} across "
                f"**{len(rows)}** compan{'ies' if len(rows) != 1 else 'y'} "
                f"in the last 24h:\n{top}{more}")
    else:
        desc = "Quiet day — no new matching jobs in the last 24h."
    desc += f"\n\nWatching {n_boards} boards."
    if broken:
        desc += f"\n⚠️ failing: {', '.join(broken)}"

    for sub in subs:
        if not sub["digest"]:
            continue
        if sub["discord"]:
            send_discord_note(sub["discord"], f"📊 daily digest — {today}",
                              desc, 0x2ECC71)
        if sub["telegram_chat"]:
            send_telegram(sub["telegram_chat"],
                          f"📊 daily digest — {today}\n\n"
                          + desc.replace("**", ""))


# ---- personal reminders: built from the desktop tracker (an Actions runner has none)
REMINDER_HOUR = 8            # local time of the once-a-day summary
CLOSED_LOOKBACK_DAYS = 2     # older closures were already visible in the app
OPEN_APP_STATUSES = ("discovered", "saved", "preparing")
ACTIVE_APP_STATUSES = ("saved", "preparing", "applied", "assessment", "phone_screen",
                       "first_round", "final_round", "offer")


def _when(day, today):
    days = (day - today).days
    return "today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days ({day:%b %d})"


def _item(company, title, url):
    label = f"{company}: {title}" if company else title
    return f"[{label}]({url})" if url and url.startswith("http") else label


def reminder_lines(con, today):
    """Deadlines in the next 3 days for jobs you have not applied to, interviews
    today/tomorrow, overdue next steps and contact follow-ups."""
    t = today.isoformat()
    lines = []
    due = "substr(COALESCE(NULLIF(a.deadline, ''), i.eff_deadline, ''), 1, 10)"
    for company, title, url, day in con.execute(
            f"""SELECT a.company, a.title, a.url, {due} FROM applications a
                LEFT JOIN job_intel i ON a.job_key=(i.board || ':' || i.job_id)
                WHERE a.status IN ({','.join('?' * len(OPEN_APP_STATUSES))}) AND {due} BETWEEN ? AND ?
                ORDER BY {due} LIMIT 8""",
            (*OPEN_APP_STATUSES, t, (today + timedelta(days=3)).isoformat())):
        lines.append(f"⏰ Deadline {_when(datetime.fromisoformat(day).date(), today)}: "
                     f"{_item(company, title, url)}")
    for company, title, url, day in con.execute(
            """SELECT company, title, url, substr(interview_date, 1, 10) FROM applications
               WHERE interview_date != '' AND substr(interview_date, 1, 10) BETWEEN ? AND ?
               ORDER BY interview_date LIMIT 8""", (t, (today + timedelta(days=1)).isoformat())):
        lines.append(f"🎤 Interview {_when(datetime.fromisoformat(day).date(), today)}: "
                     f"{_item(company, title, url)}")
    for company, title, url, step in con.execute(
            f"""SELECT company, title, url, next_step FROM applications
                WHERE next_action_date != '' AND substr(next_action_date, 1, 10) <= ?
                AND status IN ({','.join('?' * len(ACTIVE_APP_STATUSES))})
                ORDER BY next_action_date LIMIT 8""", (t, *ACTIVE_APP_STATUSES)):
        lines.append(f"➡️ Next step due{': ' + step if step else ''} — {_item(company, title, url)}")
    for name, company in con.execute(
            """SELECT name, company FROM contacts WHERE next_follow_up != '' AND next_follow_up <= ?
               ORDER BY next_follow_up LIMIT 8""", (t,)):
        lines.append(f"👋 Follow up with {name}" + (f" ({company})" if company else ""))
    return lines


def closed_saved_jobs(con):
    """Saved jobs whose posting was taken down recently and not yet announced."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=CLOSED_LOOKBACK_DAYS)).isoformat(timespec="seconds")
    out = []
    for key, company, title, url, closed_at in con.execute(
            f"""SELECT a.job_key, a.company, a.title, a.url, s.closed_at FROM applications a
                JOIN job_state s ON a.job_key=(s.board || ':' || s.job_id)
                WHERE s.status='closed' AND s.closed_at >= ?
                AND a.status IN ({','.join('?' * len(OPEN_APP_STATUSES))})
                ORDER BY s.closed_at""", (cutoff, *OPEN_APP_STATUSES)):
        seen = con.execute("SELECT v FROM kv WHERE k=?", (f"closed_notified:{key}",)).fetchone()
        if not seen or seen[0] != closed_at:   # a reopened-then-closed job is announced again
            out.append((key, company, title, url, closed_at))
    return out


def maybe_reminders(con, subs, now_local=None):
    targets = [s for s in subs if s["reminders"] and s["discord"]]
    if not targets:
        return
    closed = closed_saved_jobs(con)
    if closed:
        desc = "\n".join(f"• {_item(c, t, u)}" for _, c, t, u, _ in closed[:20])
        if len(closed) > 20:
            desc += f"\n…and {len(closed) - 20} more"
        desc += "\n\nThese were saved but not applied to. Check the Applications tab."
        ok = True
        for sub in targets:
            ok &= send_discord_note(sub["discord"], "🚫 Saved job taken down", desc, 0xE67E22)
        if ok:
            con.executemany("INSERT OR REPLACE INTO kv VALUES (?,?)",
                            [(f"closed_notified:{key}", closed_at) for key, *_, closed_at in closed])
    now_local = now_local or datetime.now()
    today = now_local.date()
    if now_local.hour < REMINDER_HOUR:
        return
    row = con.execute("SELECT v FROM kv WHERE k='last_reminder'").fetchone()
    if row and row[0] >= today.isoformat():
        return
    con.execute("INSERT OR REPLACE INTO kv VALUES ('last_reminder', ?)", (today.isoformat(),))
    lines = reminder_lines(con, today)
    if lines:
        for sub in targets:
            send_discord_note(sub["discord"], f"📅 Foothold today — {today:%a %b %d}", "\n".join(lines), 0x3E63DD)


# ================================================================ core cycle
def fetch_board(name, cfg):
    for attempt in range(2):
        try:
            jobs = ADAPTERS[cfg["ats"]](cfg)
            break
        except (requests.Timeout, requests.ConnectionError):
            if attempt:
                raise
            time.sleep(0.75)
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else 0
            if attempt or (status != 429 and status < 500):
                raise
            time.sleep(0.75)
    for j in jobs:
        j.setdefault("company", name.replace("_", " "))
    return name, jobs


def report_progress(callback, event, **data):
    if callback:
        try:
            callback(event, **data)
        except Exception as exc:
            log(f"! progress observer: {type(exc).__name__}: {exc}")


def repair_workday_posted(con, config):
    """Clear posting dates invented from 'Posted 30+ Days Ago'.

    Older versions stored ``now - 30 days`` for that bucket.  Those values came
    from time.time() and so carry fractional seconds; Workday never reports
    sub-second times, so a fractional value on a Workday board is always an
    estimate.  Clearing them lets the next poll (day precision) or the detail
    record (exact startDate) supply a real date instead.  Current code never
    writes such values, so this is idempotent and cheap; it runs every cycle
    because an older copy of the app may share (and re-dirty) the database.
    """
    boards = [k for k, v in config.get("boards", {}).items()
              if not k.startswith("_") and isinstance(v, dict) and v.get("ats") == "workday"]
    cleared = 0
    for chunk in range(0, len(boards), 400):
        part = boards[chunk:chunk + 400]
        marks = ",".join("?" * len(part))
        keys = con.execute(f"""SELECT board, job_id FROM job_details WHERE board IN ({marks})
                               AND posted IS NOT NULL AND posted != CAST(posted AS INTEGER)""", part).fetchall()
        if not keys:
            # executemany() with no rows still opens a transaction. Later reads
            # would pin a snapshot, and the next write after any other commit
            # fails at once with "database is locked", ignoring busy_timeout.
            continue
        con.executemany("UPDATE job_details SET posted=NULL WHERE board=? AND job_id=?", keys)
        con.executemany("UPDATE job_intel SET input_hash=NULL WHERE board=? AND job_id=?", keys)
        cleared += len(keys)
    if cleared:
        con.commit()
        log(f"cleared {cleared} estimated Workday posting date(s); real dates arrive with the next poll")
    return cleared


def cycle(config, con, progress=None):
    t0 = time.time()
    started_at = now()
    all_boards = {k: v for k, v in config["boards"].items()
                  if not k.startswith("_") and not v.get("disabled")}
    subs = load_subscribers(config.get("filters", {}))
    repair_workday_posted(con, config)
    new_by_board = {}
    broke = []
    ok_count = fail_count = skipped = 0
    change_count = closed_count = 0

    # respect per-board min_interval (big feeds like the 11MB listings repos
    # only change every ~15 min; no point fetching them every 45s)
    due = {}
    for name, cfg in all_boards.items():
        seeded, failures, last_poll = board_row(con, name)
        if time.time() - last_poll < max(cfg.get("min_interval", 0), failure_backoff(failures)):
            skipped += 1
            continue
        due[name] = {**cfg, "_initial_seed": not seeded}

    # New board rows must not hold a write lock during the first network wait.
    con.commit()
    report_progress(progress, "start", sources=list(due), skipped=skipped)

    def fetch(name, cfg):
        report_progress(progress, "source_started", board=name)
        return fetch_board(name, cfg)

    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch, n, c): n for n, c in due.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            seeded, failures, _ = board_row(con, name)
            con.execute("UPDATE boards SET last_poll=? WHERE board=?",
                        (time.time(), name))
            try:
                _, jobs = fut.result()
            except Exception as e:
                failures += 1
                con.execute("UPDATE boards SET failures=? WHERE board=?", (failures, name))
                fail_count += 1
                if failures == 10:      # persisted streak → fires once per outage
                    broke.append((name, type(e).__name__))
                if failures in (1, 3, 10) or failures % 50 == 0:
                    log(f"! {name}: {type(e).__name__}: {e} (streak {failures})")
                con.commit()
                report_progress(progress, "source_finished", board=name, outcome="failed",
                                error=f"{type(e).__name__}: {str(e)[:200]}")
                continue

            try:
                ok_count += 1
                known = known_ids(con, name)

                if not jobs and len(known) >= ZERO_GUARD_MIN:
                    log(f"! {name}: returned 0 jobs but {len(known)} known — ignoring read")
                    con.commit()
                    report_progress(progress, "source_finished", board=name, outcome="failed",
                                    error="Empty response ignored to protect existing postings")
                    continue

                fresh = [j for j in jobs if j["id"] and j["id"] not in known]
                ts = now()
                changes = record_changes(con, name, jobs, ts)
                if changes:
                    change_count += len(changes)
                con.executemany(
                    """INSERT INTO jobs
                       (board, job_id, title, location, url, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?)
                       ON CONFLICT(board, job_id) DO UPDATE SET
                         title=excluded.title, location=excluded.location,
                         url=excluded.url, last_seen=excluded.last_seen""",
                    [(name, j["id"], j["title"], j["location"], j["url"], ts, ts)
                     for j in jobs])
                # "Posted Today" / "3 days ago" are estimates: a later poll may only
                # move them earlier, or a stale listing keeps looking brand new.
                estimated = int(all_boards[name].get("ats") in RELATIVE_DATE_ATS)
                con.executemany(
                    """INSERT INTO job_details(board, job_id, company, salary, posted)
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(board, job_id) DO UPDATE SET
                         company=excluded.company, salary=excluded.salary,
                         posted=CASE WHEN ? AND excluded.posted IS NOT NULL AND job_details.posted IS NOT NULL
                                     THEN MIN(excluded.posted, job_details.posted)
                                     ELSE COALESCE(excluded.posted, job_details.posted) END""",
                    [(name, j["id"], j.get("company") or name.replace("_", " "),
                      j.get("salary") or "", _posted_epoch(j.get("posted")), estimated)
                     for j in jobs])
                con.execute("UPDATE boards SET failures=0, last_ok=?, seeded=1 WHERE board=?",
                            (ts, name))
                for j in jobs:
                    if j.get("description") or j.get("department"):
                        store_description(con, name, j["id"], j.get("description") or "",
                                          j.get("department") or "",
                                          source=j.get("description_source") or "listing")
                runtime_complete = getattr(jobs, "complete", None)
                complete = all_boards[name].get("complete_listing", runtime_complete if runtime_complete is not None
                                                 else all_boards[name].get("ats") in COMPLETE_LISTING_ATS)
                complete = bool(complete and runtime_complete is not False)
                coverage_warning = getattr(jobs, "reason", "")
                if coverage_warning:
                    log(f"  {name}: {coverage_warning}")
                source_cfg = due[name]
                window = {}
                if source_cfg.get("ats") == "linkedin":
                    initial = source_cfg.get("_initial_seed", False)
                    window = {"recency": source_cfg.get("seed_recency" if initial else "recency",
                                                         source_cfg.get("recency", "r2592000" if initial else "r86400")),
                              "pages": source_cfg.get("seed_pages" if initial else "pages",
                                                       source_cfg.get("pages", 3)),
                              "queries": source_cfg.get("queries") or [source_cfg.get("query", "software engineer intern")]}
                coverage = {"fetched": len(jobs), "reported_total": getattr(jobs, "total", None),
                            "complete": bool(runtime_complete if runtime_complete is not None else complete),
                            "detects_removals": complete,
                            "reason": coverage_warning, "fetched_at": ts, "window": window}
                con.execute("INSERT OR REPLACE INTO kv(k,v) VALUES (?,?)",
                            (f"source_coverage:{name}", json.dumps(coverage)))
                life = update_lifecycle(con, name, {j["id"] for j in jobs if j["id"]}, complete, ts,
                                        {j["id"] for j in fresh}, discovered=bool(seeded))
                closed_count += life["closed"]

                if not seeded:
                    for j in jobs:          # a later echo from another source is not new either
                        mark_alerted(con, j)
                    log(f"  {name}: seeded {len(jobs)} postings silently")
                elif fresh:
                    new_by_board[name] = fresh
                # Release the write lock before waiting for another network source.
                # First-run setup stays editable and completed sources appear early.
                con.commit()
                report_progress(progress, "source_finished", board=name, outcome="ok", jobs=len(jobs), new=len(fresh),
                                coverage_complete=complete, coverage_warning=coverage_warning,
                                reported_total=getattr(jobs, "total", None))
            except Exception as e:      # one board's bad data must not stop the others
                con.rollback()
                ok_count -= 1
                fail_count += 1
                new_by_board.pop(name, None)
                log(f"! {name}: could not store results: {type(e).__name__}: {e}")
                report_progress(progress, "source_finished", board=name, outcome="failed",
                                error=f"{type(e).__name__}: {str(e)[:200]}")

    # ---- finance intelligence for everything new or changed (incremental).
    # New postings are classified first so fit-based alerts never wait on
    # the background backlog.
    con.commit()
    store = None
    report_progress(progress, "phase", phase="indexing")
    try:
        store = IntelStore(con, config)
        store.facts_pass(keys=[(b, j["id"]) for b, js in new_by_board.items() for j in js])
        store.score_pass(commit_batches=True)
        con.commit()
    except Exception as e:      # intelligence must never stop collection or alerts
        log(f"! intel refresh failed: {type(e).__name__}: {e}")
        con.rollback()
        store = None

    # ---- cross-source dedupe gate (same job via ATS + repo = one alert)
    report_progress(progress, "phase", phase="alerts")
    excl_co = Filt._c((config.get("filters") or {}).get("exclude_companies"))
    total_new = deduped = agencies = 0
    gated = {}
    seen_keys = set()               # same job from two sources in ONE cycle
    # direct boards first so when LinkedIn and the company's own ATS surface
    # the same job in one cycle, the alert carries the direct apply link
    ordered = sorted(new_by_board.items(),
                     key=lambda kv: all_boards.get(kv[0], {}).get("ats") == "linkedin")
    for board, jobs in ordered:
        keep = []
        fresh_ids = {j["id"] for j in jobs}
        for j in jobs:
            total_new += 1
            if excl_co and excl_co.search(j.get("company") or ""):
                agencies += 1       # staffing-agency spam: drop, don't alert
                continue
            ks = dedupe_keys(j)
            if already_alerted(con, j) or any(k in seen_keys for k in ks) or known_on_board(con, board, j, fresh_ids):
                deduped += 1
                continue
            seen_keys.update(ks)
            keep.append(j)
        if keep:
            gated[board] = keep

    # ---- fanout
    delivered = 0
    alerted_jobs = set()
    intel_rows = fetch_intel(con, gated) if store else {}
    for sub in subs:
        mine = []
        if not sub["match_alerts"]:
            continue
        for board, jobs in gated.items():
            if "all" not in sub["companies"] and board not in sub["companies"]:
                continue
            if sub["alert_mode"] == "fit":
                mine.extend((board, j) for j in jobs if (board, j["id"]) in intel_rows)
            else:
                mine.extend((board, j) for j in jobs if sub["filt"].ok(j))
        if mine:
            mine.sort(key=lambda t: (t[1].get("company", ""), t[1]["title"]))
            if sub["alert_mode"] == "fit":
                sent = deliver_fit(sub, mine, intel_rows, con, config, store.profile)
            else:
                deliver(sub, mine, con)
                sent = len(mine)
            delivered += sent
            alerted_jobs.update(id(j) for _, j in mine)
            log(f"  -> {sub['name']}: {sent} job(s)")

    # mark every gated job as alerted (even if no subscriber matched, so a
    # later echo from another source can't ping something already evaluated)
    ts = now()
    for board, jobs in gated.items():
        for j in jobs:
            mark_alerted(con, j)
            con.execute("INSERT INTO recent VALUES (?,?,?,?,?,?)",
                        (ts, j.get("company") or board.replace("_", " "),
                         j["title"], j["url"], j.get("location") or "",
                         j.get("salary") or ""))

    flush_feeds(config, con, subs)

    # ---- backlog indexing: alerts only need the new postings above, so older
    # unindexed postings are processed after alerts instead of delaying them.
    # The backlog only feeds the local dashboard; on an ephemeral Actions
    # runner it would be rebuilt every run and slow every cycle.
    if store and not EPHEMERAL:
        report_progress(progress, "phase", phase="indexing")
        try:
            store.facts_pass(config.get("facts_per_cycle", 5000))
            store.score_pass(commit_batches=True)
            con.commit()
        except Exception as e:
            log(f"! backlog indexing failed: {type(e).__name__}: {e}")
            con.rollback()

    # ---- description enrichment (after alerts so they are never delayed)
    enriched = 0
    report_progress(progress, "phase", phase="descriptions")
    if store and not EPHEMERAL:
        try:
            fetched = []
            enriched = enrich_descriptions(config, con, fetched=fetched, progress=progress)
            if enriched:
                report_progress(progress, "phase", phase="indexing")
                # only the enriched rows: an unbounded pass would chew through
                # the whole backlog (every row on a fresh Actions runner)
                store.facts_pass(keys=fetched)
                store.score_pass(commit_batches=True)
            notify_saved_searches(config, con, subs, store)
            con.commit()
        except Exception as e:
            log(f"! enrichment failed: {type(e).__name__}: {e}")
            con.rollback()

    if broke:
        detail = ", ".join(f"{n} ({err})" for n, err in broke)
        for sub in subs:
            if sub["ops"] and sub["discord"]:
                send_discord_note(
                    sub["discord"], "⚠️ jobwatch: board trouble",
                    f"{len(broke)} board(s) failing 10 polls in a row: {detail}\n"
                    f"Check the token / run `python watcher.py --verify`.",
                    0xE74C3C)

    report_progress(progress, "phase", phase="finishing")
    maybe_digest(config, con, subs)
    try:
        maybe_reminders(con, subs)
    except Exception as e:      # reminders must never stop the cycle
        log(f"! reminders failed: {type(e).__name__}: {e}")

    # Closed postings stay visible as history until they age out; anything
    # with an application record is kept for the CRM.
    con.execute("""DELETE FROM jobs WHERE last_seen < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)
                   AND (board || ':' || job_id) NOT IN (SELECT job_key FROM applications)""",
                (f"-{PRUNE_AFTER_DAYS} days",))
    for table in ("job_details", "job_text", "job_intel", "job_state"):
        con.execute(f"""DELETE FROM {table} WHERE NOT EXISTS (
                       SELECT 1 FROM jobs WHERE jobs.board={table}.board
                       AND jobs.job_id={table}.job_id)""")
    con.execute("DELETE FROM job_changes WHERE ts < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)", (f"-{PRUNE_AFTER_DAYS} days",))
    con.execute("DELETE FROM alert_log WHERE ts < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-7 days')")
    if store and store.fts:
        con.execute("DELETE FROM job_fts WHERE rowid NOT IN (SELECT rowid FROM job_intel)")
    con.execute("DELETE FROM alerted WHERE ts < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)",
                (f"-{PRUNE_AFTER_DAYS} days",))
    con.execute("DELETE FROM recent WHERE ts < strftime('%Y-%m-%dT%H:%M:%S', 'now', ?)",
                (f"-{RECENT_DAYS} days",))
    con.execute("DELETE FROM pending WHERE ts < strftime('%Y-%m-%dT%H:%M:%S', 'now', '-7 days')")
    duration = time.time() - t0
    con.execute(
        "INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)",
        (started_at, now(), ok_count, fail_count, skipped, total_new,
         deduped, delivered, duration))
    con.execute("""DELETE FROM runs WHERE rowid NOT IN
                   (SELECT rowid FROM runs ORDER BY rowid DESC LIMIT 1000)""")
    con.commit()

    log(f"cycle: {ok_count} ok / {fail_count} fail / {skipped} not-due | "
        f"{total_new} new, {deduped} cross-source dupes, {agencies} agency-spam, "
        f"{delivered} deliveries | {change_count} changes, {closed_count} closed, "
        f"{enriched} descriptions | {duration:.1f}s")

    hc = os.environ.get("HEALTHCHECK_URL", config.get("healthcheck_url", ""))
    if hc and (ok_count > 0):
        try:
            requests.get(hc, timeout=10)
        except Exception:
            pass


# ================================================================ cli
def cmd_check(config):
    errs = 0
    try:
        Filt(config.get("filters", {}))
        Filt._c(config.get("filters", {}).get("exclude_companies"))
    except re.error as e:
        print(f"✗ global filters: bad regex: {e}")
        errs += 1
    profile = config.get("profile", {})
    for section in ("track_weights", "seniority_weights", "location_weights",
                    "company_type_weights", "year_weights", "skills",
                    "education_penalties"):
        values = profile.get(section, {})
        if section == "skills" and isinstance(values, list):
            continue        # Fit 2.0 profiles list skill keys; validated below
        if not isinstance(values, dict) or any(
                isinstance(v, bool) or not isinstance(v, (int, float))
                for v in values.values()):
            print(f"✗ profile {section}: values must be numeric weights")
            errs += 1
    # finance intelligence: config/*.json must compile and the profile must
    # reference real taxonomy keys, company types, cities and skills
    try:
        from intel import load_knowledge, merge_profile, validate_profile
        kn = load_knowledge()
        for problem in validate_profile(merge_profile(profile), kn):
            print(f"✗ profile: {problem}")
            errs += 1
    except Exception as e:      # bad regex / JSON / unknown company type
        print(f"✗ intelligence config: {type(e).__name__}: {e}")
        errs += 1
        kn = None
    for name, b in config["boards"].items():
        if name.startswith("_"):
            continue
        if b.get("ats") not in ADAPTERS:
            print(f"✗ board {name}: unknown ats {b.get('ats')}")
            errs += 1
        if kn and b.get("company_key") and b["company_key"] not in kn.companies:
            print(f"✗ board {name}: unknown company_key {b['company_key']}")
            errs += 1
        if kn and b.get("company_type") and b["company_type"] not in kn.company_types:
            print(f"✗ board {name}: unknown company_type {b['company_type']}")
            errs += 1
    subs = json.loads(SUBSCRIBERS.read_text(encoding="utf-8"))
    n_subs = 0
    for name, s in subs.items():
        if name.startswith("_"):
            continue
        n_subs += 1
        try:
            Filt(s.get("filters", {}), fallback=config.get("filters", {}))
            Filt._c(s.get("watchlist", ""))
        except re.error as e:
            print(f"✗ subscriber {name}: bad regex: {e}")
            errs += 1
        for c in s.get("companies", ["all"]):
            if c != "all" and c not in config["boards"]:
                print(f"✗ subscriber {name}: unknown company '{c}'")
                errs += 1
        categories = s.get("ping_categories", ["intern", "new_grad", "other"])
        invalid = set(categories) - {"intern", "new_grad", "other"}
        if invalid:
            print(f"✗ subscriber {name}: unknown ping categories "
                  f"{', '.join(sorted(invalid))}")
            errs += 1
        if s.get("alert_mode", "regex") not in ("regex", "fit"):
            print(f"✗ subscriber {name}: alert_mode must be 'regex' or 'fit'")
            errs += 1
        tiers = s.get("fit_tiers") or {}
        if any(not isinstance(v, int) or not 0 <= v <= 100 for v in tiers.values()):
            print(f"✗ subscriber {name}: fit_tiers values must be integers 0–100")
            errs += 1
        cap = s.get("max_ping_jobs", 10)
        if not isinstance(cap, int) or isinstance(cap, bool) or cap < 0:
            print(f"✗ subscriber {name}: max_ping_jobs must be a non-negative integer")
            errs += 1
        if not s.get("discord_webhook") and not s.get("telegram_chat_id"):
            print(f"⚠ subscriber {name}: no delivery channel configured")
    n_boards = sum(1 for k in config["boards"] if not k.startswith("_"))
    print("config INVALID" if errs else f"config ok: {n_boards} boards, {n_subs} subscribers")
    sys.exit(1 if errs else 0)


def cmd_verify(config):
    """Hit every enabled board once. The fastest way to fix wrong tokens."""
    boards = {k: v for k, v in config["boards"].items()
              if not k.startswith("_") and not v.get("disabled")}
    good = bad = 0
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(fetch_board, n, c): n for n, c in boards.items()}
        for fut in as_completed(futs):
            name = futs[fut]
            try:
                _, jobs = fut.result()
                print(f"✓ {name:22} {len(jobs):>5} postings")
                good += 1
            except Exception as e:
                print(f"✗ {name:22} {type(e).__name__}: {str(e)[:90]}")
                bad += 1
    if bad:
        print(f"\n{good} working, {bad} broken. Fix tokens for broken boards "
              f"(careers page URL) or set \"disabled\": true.")
    else:
        print(f"\n{good} working, 0 broken — every enabled source is healthy.")


def cmd_test(config, who):
    subs = load_subscribers(config.get("filters", {}))
    sub = next((s for s in subs if s["name"] == who), None)
    if not sub:
        sys.exit(f"no active subscriber '{who}'")
    if not sub["discord"] and not sub["telegram_chat"]:
        sys.exit(f"'{who}' has no delivery channel — if the webhook is an "
                 f"env: secret, export it first")
    if sub["discord"]:
        send_discord_note(
            sub["discord"], "🧪 jobwatch test — every delivery scenario",
            "How this works, in one line: **high-signal watchlist roles "
            "buzz you; every match lands quietly in the feeds.**"
            "\n\nThe next messages demo it with fake jobs:\n\n"
            "**1. 🎯 apply-now intern (LOUD, gold cards)** — internships at "
            "watchlist companies → Stripe, Jane Street\n"
            "**2. 🎯 apply-now full-time (LOUD, orange cards)** — new-grad "
            "roles at watchlist companies → Databricks\n"
            "**3. 🛠️ internships feed (@silent)** — EVERY internship incl. "
            "the apply-now ones (⭐ = watchlist company) → ⭐ Stripe, "
            "⭐ Jane Street, SomeCo\n"
            "**4. 💼 full-time feed (@silent)** — every other role, same "
            "idea → ⭐ Databricks, ⭐ Anthropic, RandomCorp\n"
            "Loud cards are capped; overflow stays in these feeds.\n"
            "\nThat's the whole system.",
            0x9B59B6)
    nowt = time.time()
    fake = [
        ("test", {"id": "t1", "company": "Stripe",
                  "title": "Software Engineer, Intern (Summer 2026)",
                  "location": "New York, NY", "salary": "$55 – $62/hr",
                  "posted": nowt - 3600, "url": "https://example.com/1"}),
        ("test", {"id": "t2", "company": "Jane Street",
                  "title": "Quantitative Trader — Summer Internship",
                  "location": "New York, NY", "posted": nowt - 5 * 3600,
                  "url": "https://example.com/2"}),
        ("test", {"id": "t3", "company": "Databricks",
                  "title": "New Grad Software Engineer",
                  "location": "Toronto, ON", "salary": "$140K – $180K",
                  "posted": nowt - 2 * 86400, "url": "https://example.com/3"}),
        ("test", {"id": "t4", "company": "Anthropic",
                  "title": "Software Engineer, 2026 Start",
                  "location": "Remote — US", "url": "https://example.com/4"}),
        ("test", {"id": "t5", "company": "SomeCo",
                  "title": "Software Engineer Intern",
                  "location": "Chicago, IL", "posted": nowt - 30 * 60,
                  "url": "https://example.com/5"}),
        ("test", {"id": "t6", "company": "RandomCorp",
                  "title": "Machine Learning Engineer",
                  "location": "Seattle, WA", "url": "https://example.com/6"}),
    ]
    con = db_open()
    ok = deliver(sub, fake, con)
    flush_feeds(config, con, [sub], force=True)   # demo digests immediately
    print("sent ok" if ok else "send FAILED — check webhook/token")
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(CONFIG))
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--list", metavar="BOARD")
    ap.add_argument("--test", metavar="SUBSCRIBER")
    ap.add_argument("--serve", action="store_true",
                    help="open the local daily-use dashboard")
    ap.add_argument("--host", default="127.0.0.1",
                    help="dashboard host (default: loopback only)")
    ap.add_argument("--port", type=int, default=8787,
                    help="dashboard port (default: 8787)")
    ap.add_argument("--no-browser", action="store_true",
                    help="do not open the dashboard in a browser")
    ap.add_argument("--enrich", type=int, metavar="N",
                    help="fetch up to N job descriptions now, then refresh intelligence")
    ap.add_argument("--rescore", action="store_true",
                    help="recompute finance intelligence and fit scores for every job")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    if args.check:
        cmd_check(config)
    if args.verify:
        cmd_verify(config)
        return
    if args.test:
        cmd_test(config, args.test)
        return
    if args.list:
        _, jobs = fetch_board(args.list, config["boards"][args.list])
        for j in sorted(jobs, key=lambda x: (x.get("company", ""), x["title"])):
            print(f"{(j.get('company') or '')[:18]:18} | {j['title']!r:55.55} | "
                  f"{j['location']!r:28.28} | {j['url'][:60]}")
        print(f"\n{len(jobs)} live postings")
        return
    if args.enrich or args.rescore:
        con = db_open()
        if args.enrich:
            log(f"fetched {enrich_descriptions(config, con, args.enrich)} description(s)")
        store = IntelStore(con, config)
        if args.rescore:
            con.execute("UPDATE job_intel SET input_hash=NULL")
        stats = store.refresh(force_score=args.rescore)
        log(f"intelligence: {stats['facts']} classified, {stats['scored']} scored in {stats['seconds']}s")
        return
    if args.serve:
        from dashboard import serve
        serve(args.host, args.port, not args.no_browser,
              DB_PATH, Path(args.config), SUBSCRIBERS)
        return

    # single-instance lock (POSIX)
    try:
        import fcntl
        lockf = open(HERE / ".watcher.lock", "w")
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another watcher instance is already running")
    except ImportError:
        pass  # windows: rely on the user not double-launching

    fresh_db = not DB_PATH.exists()
    con = db_open()
    if fresh_db and STATE_JSON.exists():
        import_state(con)

    interval = config.get("interval_seconds", 45)

    if args.once:
        cycle(config, con)
        export_state(con)      # portable state for Actions runners
        return

    log(f"watching {sum(1 for k in config['boards'] if not k.startswith('_'))} "
        f"boards every ~{interval}s")
    while True:
        try:
            cycle(config, con)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"! cycle crashed: {type(e).__name__}: {e}")
        time.sleep(max(5, interval) + random.uniform(0, interval * 0.2))


if __name__ == "__main__":
    main()
