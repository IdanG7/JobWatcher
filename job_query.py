"""SQL query builder for opportunity lists.

Shared by the dashboard API, saved-search notifications and CSV export so
"Toronto IB 2027" means the same thing everywhere.  Every filter maps to
indexed columns on ``job_intel``; nothing loads the whole table.
"""

from __future__ import annotations

import re
import time
from intel import FACTS_VERSION
from datetime import date, timedelta

APP_STATUSES = ["discovered", "saved", "preparing", "applied", "assessment", "phone_screen",
                "first_round", "final_round", "offer", "rejected", "withdrawn", "archived"]
ACTIVE_APP_STATUSES = ["saved", "preparing", "applied", "assessment", "phone_screen",
                       "first_round", "final_round", "offer"]
INTERVIEW_STATUSES = ["assessment", "phone_screen", "first_round", "final_round"]
POSTED_WINDOWS = {"today": 24, "24h": 24, "48h": 48, "3d": 72, "7d": 168, "14d": 336, "30d": 720}
SORTS = {
    "fit": "i.fit {d}, COALESCE(i.posted_ref,0) DESC",
    "newest": "COALESCE(i.posted_ref, 0) {d}, i.fit DESC",
    "deadline": "CASE WHEN i.eff_deadline IS NULL THEN 1 ELSE 0 END, i.eff_deadline {d}, i.fit DESC",
    "company": "i.company_name COLLATE NOCASE {d}, i.fit DESC",
    "title": "j.title COLLATE NOCASE {d}",
    "urgency": "i.urgency {d}, i.fit DESC",
    "category": "i.category {d}, i.fit DESC",
    "location": "COALESCE(i.city, i.country, '') {d}, i.fit DESC",
    "cycle": "COALESCE(i.cycle, 'zzz') {d}, i.fit DESC",
    "status": "COALESCE(a.status, 'zzz') {d}, i.fit DESC",
}
DEFAULT_DIR = {"fit": "DESC", "newest": "DESC", "urgency": "DESC", "deadline": "ASC",
               "company": "ASC", "title": "ASC", "category": "ASC", "location": "ASC",
               "cycle": "ASC", "status": "ASC"}

SELECT_COLUMNS = """
    i.board, i.job_id, j.title, j.location, j.url, j.first_seen, j.last_seen,
    COALESCE(d.company, '') AS raw_company, COALESCE(d.salary, '') AS salary, d.posted,
    i.company_key, i.company_name, i.company_type, i.family, i.category, i.subcategory,
    i.is_finance, i.class_confidence, i.stage, i.level, i.cycle, i.cycle_year, i.city, i.cities,
    i.country, i.location_bucket, i.eff_deadline AS deadline, i.window_status, i.fit, i.urgency,
    i.badges, i.comp_annual_min, i.comp_annual_max, i.comp_currency, i.cluster_key, i.posted_ref,
    i.skills, COALESCE(s.status, 'active') AS job_status, s.closed_at,
    a.status AS app_status, a.next_step, a.next_action_date, a.updated_at AS app_updated_at
"""
FROM_CLAUSE = """
    FROM job_intel i
    JOIN jobs j ON j.board=i.board AND j.job_id=i.job_id
    LEFT JOIN job_details d ON d.board=i.board AND d.job_id=i.job_id
    LEFT JOIN job_state s ON s.board=i.board AND s.job_id=i.job_id
    LEFT JOIN applications a ON a.job_key=(i.board||':'||i.job_id)
"""


def _list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = []
        for v in value:
            items.extend(_list(v))
        return items
    return [v.strip() for v in str(value).split(",") if v.strip()]


def flatten(params: dict) -> dict:
    """parse_qs-style {k: [v]} -> {k: v} (comma lists stay strings)."""
    return {k: (",".join(v) if isinstance(v, list) else v) for k, v in (params or {}).items()}


def resume_params(params: dict, enabled: bool) -> dict:
    """One default/paused behavior for lists, exports and saved-search alerts."""
    result = flatten(params)
    result.setdefault("resume_match", "1" if enabled else "0")
    if not enabled:
        result["resume_match"] = "0"
    return result


def fts_query(text: str) -> str:
    tokens = re.findall(r"[a-z0-9&+]+", (text or "").lower())
    tokens = [t.replace("&", "") for t in tokens if t.replace("&", "")]
    return " ".join(f'"{t}"*' for t in tokens[:8])


def build_where(params: dict, fts: bool, watched: set[str] | None = None,
                now: float | None = None) -> tuple[list[str], list]:
    p = flatten(params)
    now = now or time.time()
    where, args = ["j.title != ''"], []

    if not p.get("all_sources"):
        where.append("i.is_canonical=1")
    if not p.get("include_closed"):
        where.append("COALESCE(s.status,'active') != 'closed'")
        where.append("COALESCE(i.window_status,'') != 'closed'")
    if not p.get("include_hidden"):
        where.append("NOT EXISTS (SELECT 1 FROM job_overrides o WHERE o.job_key=(i.board||':'||i.job_id) AND o.hidden=1)")
    if str(p.get("resume_match", "0")) == "1":
        where.append("i.facts_version=?")
        args.append(FACTS_VERSION)
        where.append("""EXISTS (SELECT 1 FROM resume_matches rm JOIN candidate_resume cr ON cr.id=1
            WHERE rm.board=i.board AND rm.job_id=i.job_id AND rm.matched=1
            AND rm.profile_version=i.profile_version AND rm.profile_version=cr.version AND cr.enabled=1)""")

    q = (p.get("q") or "").strip()
    if q:
        if fts and fts_query(q):
            where.append("i.rowid IN (SELECT rowid FROM job_fts WHERE job_fts MATCH ?)")
            args.append(fts_query(q))
        else:
            for term in q.lower().split()[:8]:
                where.append("i.search_text LIKE ?")
                args.append(f"%{term}%")

    # One or more job families (interests); 'finance' means any finance category.
    families = _list(p.get("family"))
    if families:
        parts = []
        for family in families:
            if family == "finance":
                parts.append("i.is_finance=1")
            else:
                parts.append("i.family=?")
                args.append(family)
        where.append("(" + " OR ".join(parts) + ")")

    def any_of(column: str, values: list[str]):
        if values:
            where.append(f"{column} IN ({','.join('?' * len(values))})")
            args.extend(values)

    cats = _list(p.get("category"))
    if cats:
        # 'investment_banking.ma' targets a subcategory
        parts = []
        for c in cats:
            if "." in c:
                cat, sub = c.split(".", 1)
                parts.append("(i.category=? AND i.subcategory=?)")
                args.extend([cat, sub])
            else:
                parts.append("i.category=?")
                args.append(c)
        where.append("(" + " OR ".join(parts) + ")")
    any_of("i.subcategory", _list(p.get("subcategory")))
    any_of("i.company_type", _list(p.get("company_type")))
    any_of("i.company_key", _list(p.get("company")))
    any_of("i.stage", _list(p.get("stage")))
    any_of("i.level", _list(p.get("level")))

    cycles = _list(p.get("cycle"))
    if cycles:
        parts = []
        for c in cycles:
            if c.isdigit():
                parts.append("i.cycle_year=?")
                args.append(int(c))
            else:
                parts.append("i.cycle=?")
                args.append(c)
        where.append("(" + " OR ".join(parts) + ")")

    locations = _list(p.get("location"))
    if locations:
        parts = []
        for loc in locations:
            if loc in ("us", "canada") or (len(loc) == 2 and loc.isupper()):
                country = {"us": "US", "canada": "CA"}.get(loc, loc)
                parts.append("(i.country=? OR EXISTS (SELECT 1 FROM json_each(i.facts, '$.location.countries') WHERE value=?))")
                args.extend([country, country])
            elif loc in ("remote", "other", "unknown"):
                parts.append("i.location_bucket=?")
                args.append(loc)
            else:
                parts.append("(' ' || i.cities || ' ') LIKE ?")
                args.append(f"% {loc} %")
        where.append("(" + " OR ".join(parts) + ")")

    posted = p.get("posted")
    if posted in POSTED_WINDOWS:
        where.append("i.posted_ref >= ?")
        args.append(now - POSTED_WINDOWS[posted] * 3600)

    deadline = p.get("deadline")
    today = date.fromtimestamp(now)
    if deadline in ("3d", "7d", "14d", "30d"):
        days = int(deadline[:-1])
        where.append("i.eff_deadline BETWEEN ? AND ?")
        args.extend([today.isoformat(), (today + timedelta(days=days)).isoformat()])
    elif deadline == "any":
        where.append("i.eff_deadline IS NOT NULL")
    elif deadline == "rolling":
        where.append("i.rolling=1")

    for key, column, op in (("min_fit", "i.fit", ">="), ("max_fit", "i.fit", "<="),
                            ("comp_min", "i.comp_annual_max", ">=")):
        value = p.get(key)
        if value not in (None, ""):
            try:
                args.append(float(value))
                where.append(f"{column} {op} ?")
            except ValueError:
                pass

    statuses = _list(p.get("status"))
    if statuses:
        parts = []
        concrete = [s for s in statuses if s in APP_STATUSES]
        if concrete:
            parts.append(f"a.status IN ({','.join('?' * len(concrete))})")
            args.extend(concrete)
        if "untracked" in statuses:
            parts.append("a.status IS NULL")
        if "tracked" in statuses:
            parts.append("a.status IS NOT NULL")
        if "active" in statuses:
            parts.append(f"a.status IN ({','.join('?' * len(ACTIVE_APP_STATUSES))})")
            args.extend(ACTIVE_APP_STATUSES)
        if parts:
            where.append("(" + " OR ".join(parts) + ")")

    if p.get("watchlist"):
        keys = sorted(watched or [])
        if keys:
            where.append(f"i.company_key IN ({','.join('?' * len(keys))})")
            args.extend(keys)
        else:
            where.append("0")

    if p.get("since"):
        where.append("j.first_seen > ?")
        args.append(p["since"])
    return where, args


def build_order(params: dict) -> str:
    p = flatten(params)
    sort = p.get("sort") if p.get("sort") in SORTS else "fit"
    direction = (p.get("dir") or DEFAULT_DIR[sort]).upper()
    if direction not in ("ASC", "DESC"):
        direction = DEFAULT_DIR[sort]
    return SORTS[sort].format(d=direction)


def page_args(params: dict, default: int = 50, maximum: int = 200) -> tuple[int, int]:
    p = flatten(params)
    try:
        page = max(1, int(p.get("page") or 1))
        per_page = min(maximum, max(1, int(p.get("per_page") or default)))
    except ValueError:
        page, per_page = 1, default
    return page, per_page
