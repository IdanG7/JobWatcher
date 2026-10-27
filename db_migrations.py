"""Forward-only SQLite migrations for Jobwatch.

``PRAGMA user_version`` records the applied schema version.  Every step is
idempotent (``IF NOT EXISTS`` / guarded ``ALTER``), so an interrupted
migration simply re-runs.  Existing tables keep their original column order
because older code and state imports insert into them positionally; new
per-job state therefore lives in side tables instead of new columns.
"""

from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 7


def _columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def _add_column(con: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    if column not in _columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def _v1_baseline(con: sqlite3.Connection) -> None:
    """The schema shipped before migrations existed (unchanged)."""
    con.execute("""CREATE TABLE IF NOT EXISTS jobs(
        board TEXT, job_id TEXT, title TEXT, location TEXT, url TEXT,
        first_seen TEXT, last_seen TEXT,
        PRIMARY KEY(board, job_id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS job_details(
        board TEXT, job_id TEXT, company TEXT DEFAULT '',
        salary TEXT DEFAULT '', posted REAL,
        PRIMARY KEY(board, job_id))""")
    con.execute("""CREATE TABLE IF NOT EXISTS boards(
        board TEXT PRIMARY KEY, seeded INTEGER DEFAULT 0,
        last_ok TEXT, failures INTEGER DEFAULT 0, last_poll REAL DEFAULT 0)""")
    con.execute("CREATE TABLE IF NOT EXISTS alerted(key TEXT PRIMARY KEY, ts TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS sends(
        ts TEXT, subscriber TEXT, board TEXT, job_id TEXT, ok INTEGER)""")
    con.execute("""CREATE TABLE IF NOT EXISTS recent(
        ts TEXT, company TEXT, title TEXT, url TEXT,
        location TEXT DEFAULT '', salary TEXT DEFAULT '')""")
    con.execute("""CREATE TABLE IF NOT EXISTS pending(
        sub TEXT, tier TEXT, ts TEXT, company TEXT, title TEXT, url TEXT,
        location TEXT DEFAULT '', salary TEXT DEFAULT '', posted REAL)""")
    con.execute("CREATE TABLE IF NOT EXISTS kv(k TEXT PRIMARY KEY, v TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS applications(
        job_key TEXT PRIMARY KEY, board TEXT, job_id TEXT, company TEXT,
        title TEXT, location TEXT DEFAULT '', url TEXT, salary TEXT DEFAULT '',
        posted REAL, status TEXT DEFAULT 'saved', priority INTEGER DEFAULT 0,
        notes TEXT DEFAULT '', next_step TEXT DEFAULT '', due_date TEXT DEFAULT '',
        created_at TEXT, updated_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS runs(
        started_at TEXT, finished_at TEXT, ok_count INTEGER, fail_count INTEGER,
        skipped_count INTEGER, new_count INTEGER, deduped_count INTEGER,
        delivered_count INTEGER, duration REAL)""")
    con.execute("CREATE INDEX IF NOT EXISTS jobs_last_seen ON jobs(last_seen)")
    con.execute("CREATE INDEX IF NOT EXISTS details_posted ON job_details(posted)")
    con.execute("CREATE INDEX IF NOT EXISTS applications_status ON applications(status)")


def _v2_finance(con: sqlite3.Connection) -> None:
    """Finance recruiting command center."""
    # Per-job lifecycle (closure detection) and discovery provenance.
    con.execute("""CREATE TABLE IF NOT EXISTS job_state(
        board TEXT, job_id TEXT, status TEXT DEFAULT 'active',
        missing_count INTEGER DEFAULT 0, closed_at TEXT, reopened_at TEXT,
        discovered INTEGER DEFAULT 0,
        PRIMARY KEY(board, job_id))""")
    con.execute("CREATE INDEX IF NOT EXISTS job_state_status ON job_state(status)")
    # Descriptions are large and optional, so they live apart from jobs.
    con.execute("""CREATE TABLE IF NOT EXISTS job_text(
        board TEXT, job_id TEXT, description TEXT DEFAULT '', department TEXT DEFAULT '',
        source TEXT DEFAULT '', content_hash TEXT DEFAULT '', fetched_at TEXT,
        attempts INTEGER DEFAULT 0, last_error TEXT DEFAULT '',
        PRIMARY KEY(board, job_id))""")
    # Derived intelligence: facts (profile-independent) + fit (profile-dependent).
    con.execute("""CREATE TABLE IF NOT EXISTS job_intel(
        board TEXT, job_id TEXT,
        input_hash TEXT, facts_version INTEGER, kb_version TEXT, facts TEXT, facts_at TEXT,
        family TEXT, category TEXT, subcategory TEXT, is_finance INTEGER DEFAULT 0,
        class_confidence REAL, stage TEXT, level TEXT,
        company_key TEXT, company_name TEXT, company_type TEXT,
        country TEXT, city TEXT, cities TEXT DEFAULT '', location_bucket TEXT,
        cycle TEXT, cycle_year INTEGER, deadline TEXT, deadline_confidence TEXT,
        rolling INTEGER DEFAULT 0, comp_annual_min REAL, comp_annual_max REAL,
        comp_currency TEXT, skills TEXT DEFAULT '', search_text TEXT DEFAULT '',
        cluster_key TEXT, is_canonical INTEGER DEFAULT 1,
        fit INTEGER DEFAULT 0, fit_detail TEXT, urgency INTEGER DEFAULT 0,
        window_status TEXT, badges TEXT DEFAULT '', eff_deadline TEXT, posted_ref REAL, profile_version TEXT, scored_at REAL,
        PRIMARY KEY(board, job_id))""")
    for name, cols in {
        "intel_fit": "is_canonical, fit DESC",
        "intel_category": "category, fit DESC",
        "intel_company": "company_key",
        "intel_cluster": "cluster_key",
        "intel_deadline": "eff_deadline",
        "intel_cycle": "cycle",
        "intel_stage": "stage",
        "intel_urgency": "urgency DESC",
        "intel_posted": "posted_ref DESC",
    }.items():
        con.execute(f"CREATE INDEX IF NOT EXISTS {name} ON job_intel({cols})")
    con.execute("""CREATE TABLE IF NOT EXISTS job_changes(
        id INTEGER PRIMARY KEY AUTOINCREMENT, board TEXT, job_id TEXT, ts TEXT,
        kind TEXT, field TEXT, old TEXT, new TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS job_changes_ts ON job_changes(ts)")
    con.execute("CREATE INDEX IF NOT EXISTS job_changes_job ON job_changes(board, job_id)")
    con.execute("CREATE INDEX IF NOT EXISTS jobs_first_seen ON jobs(first_seen)")
    con.execute("CREATE INDEX IF NOT EXISTS jobs_board_title ON jobs(board, title)")

    # Application CRM: richer records + status history.
    for column, decl in (
            ("applied_date", "TEXT DEFAULT ''"), ("deadline", "TEXT DEFAULT ''"),
            ("resume_version", "TEXT DEFAULT ''"), ("cover_letter_status", "TEXT DEFAULT ''"),
            ("referral", "TEXT DEFAULT ''"), ("networking_status", "TEXT DEFAULT ''"),
            ("next_action_date", "TEXT DEFAULT ''"), ("interview_date", "TEXT DEFAULT ''"),
            ("outcome", "TEXT DEFAULT ''"), ("category", "TEXT DEFAULT ''"),
            ("company_key", "TEXT DEFAULT ''"), ("fit", "INTEGER")):
        _add_column(con, "applications", column, decl)
    con.execute("UPDATE applications SET status='first_round' WHERE status='interview'")
    con.execute("""UPDATE applications SET deadline=due_date
                   WHERE COALESCE(deadline,'')='' AND COALESCE(due_date,'')!=''""")
    con.execute("""CREATE TABLE IF NOT EXISTS application_events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, job_key TEXT, ts TEXT,
        from_status TEXT, to_status TEXT, note TEXT DEFAULT '')""")
    con.execute("CREATE INDEX IF NOT EXISTS app_events_key ON application_events(job_key, ts)")

    # Networking CRM.
    con.execute("""CREATE TABLE IF NOT EXISTS contacts(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, position TEXT DEFAULT '',
        company TEXT DEFAULT '', company_key TEXT DEFAULT '', email TEXT DEFAULT '',
        linkedin_url TEXT DEFAULT '', relationship TEXT DEFAULT 'other',
        last_contacted TEXT DEFAULT '', next_follow_up TEXT DEFAULT '', notes TEXT DEFAULT '',
        job_key TEXT DEFAULT '', created_at TEXT, updated_at TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS contacts_company ON contacts(company_key)")
    con.execute("CREATE INDEX IF NOT EXISTS contacts_follow_up ON contacts(next_follow_up)")
    con.execute("""CREATE TABLE IF NOT EXISTS contact_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT, contact_id INTEGER, ts TEXT,
        kind TEXT DEFAULT 'note', note TEXT DEFAULT '')""")

    # Watchlist, saved searches, calendar, overrides, profile, alert log.
    con.execute("""CREATE TABLE IF NOT EXISTS company_prefs(
        company_key TEXT PRIMARY KEY, name TEXT DEFAULT '', watched INTEGER DEFAULT 0,
        alerts INTEGER DEFAULT 1, notes TEXT DEFAULT '', created_at TEXT, updated_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS saved_searches(
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, query TEXT NOT NULL,
        notify INTEGER DEFAULT 0, last_visited_at TEXT, last_notified_at TEXT, created_at TEXT)""")
    con.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT DEFAULT 'event', title TEXT NOT NULL,
        date TEXT NOT NULL, time TEXT DEFAULT '', company TEXT DEFAULT '', job_key TEXT DEFAULT '',
        contact_id INTEGER, notes TEXT DEFAULT '', created_at TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS events_date ON events(date)")
    con.execute("""CREATE TABLE IF NOT EXISTS job_overrides(
        job_key TEXT PRIMARY KEY, deadline TEXT DEFAULT '', deadline_note TEXT DEFAULT '',
        hidden INTEGER DEFAULT 0, updated_at TEXT)""")
    con.execute("CREATE TABLE IF NOT EXISTS user_profile(k TEXT PRIMARY KEY, v TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS alert_log(
        ts TEXT, sub TEXT, tier TEXT, company TEXT, job_key TEXT)""")
    con.execute("CREATE INDEX IF NOT EXISTS alert_log_ts ON alert_log(ts)")


def _v3_activity_index(con: sqlite3.Connection) -> None:
    """Activity, analytics and company charts count *discovered* postings
    (found after a board was seeded).  Those are a small minority, so letting
    the planner start from them avoids scanning every recent posting."""
    con.execute("CREATE INDEX IF NOT EXISTS job_state_discovered ON job_state(discovered, board, job_id)")


def _v4_cover_letters(con: sqlite3.Connection) -> None:
    # Private drafts live independently of the application tracker and exports.
    con.execute("""CREATE TABLE IF NOT EXISTS cover_letters(
        job_key TEXT PRIMARY KEY, candidate_name TEXT NOT NULL DEFAULT '',
        background TEXT NOT NULL DEFAULT '', motivation TEXT NOT NULL DEFAULT '',
        content TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")


def _v5_resume_matching(con: sqlite3.Connection) -> None:
    con.execute("""CREATE TABLE IF NOT EXISTS candidate_resume(
        id INTEGER PRIMARY KEY CHECK(id=1), filename TEXT NOT NULL, parsed TEXT NOT NULL,
        enabled INTEGER NOT NULL DEFAULT 1, version TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS resume_matches(
        board TEXT, job_id TEXT, matched INTEGER NOT NULL, detail TEXT NOT NULL,
        profile_version TEXT NOT NULL, PRIMARY KEY(board, job_id))""")
    con.execute("CREATE INDEX IF NOT EXISTS resume_matches_filter ON resume_matches(profile_version, matched)")


def _v6_drop_cover_letters(con: sqlite3.Connection) -> None:
    # The cover-letter feature was removed; its saved letters go with it.
    con.execute("DROP TABLE IF EXISTS cover_letters")


def _v7_listing_notes(con: sqlite3.Connection) -> None:
    """Community lists (SimplifyJobs and forks) carry metadata, not descriptions. It was
    stored as the description ("Sponsorship: Other."), which the drawer showed and which
    kept the posting's own text from being fetched. It moves to its own table; facts read
    description and note together, so moved postings keep the same facts."""
    con.execute("""CREATE TABLE IF NOT EXISTS job_notes(
        board TEXT, job_id TEXT, note TEXT NOT NULL DEFAULT '', PRIMARY KEY(board, job_id))""")
    con.execute("""INSERT OR IGNORE INTO job_notes(board, job_id, note)
                   SELECT board, job_id, description FROM job_text
                   WHERE source='listing_metadata' AND COALESCE(description, '')!=''""")
    # Never fetched: the poll and the drawer may fetch the description at once.
    con.execute("""UPDATE job_text SET description='', content_hash='', source='', fetched_at=NULL,
                   attempts=0, last_error='' WHERE source='listing_metadata'""")


MIGRATIONS = {1: _v1_baseline, 2: _v2_finance, 3: _v3_activity_index, 4: _v4_cover_letters,
              5: _v5_resume_matching, 6: _v6_drop_cover_letters, 7: _v7_listing_notes}


def migrate(con: sqlite3.Connection) -> int:
    """Bring ``con`` to SCHEMA_VERSION.  Returns the version it started at."""
    start = con.execute("PRAGMA user_version").fetchone()[0]
    # Pre-migration databases report 0 but already hold the v1 tables; the
    # baseline is idempotent, so running it on them is safe.
    for version in range(start + 1, SCHEMA_VERSION + 1):
        MIGRATIONS[version](con)
        con.execute(f"PRAGMA user_version={version}")
    con.commit()
    return start
