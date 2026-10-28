"""Program windows: the yearly dates of a board's training programs, shown in Calendar (plans/healthcare-board.md, D16).

The definitions are a board's `program_windows` in taxonomy.json, and only profiles with that board see them, so
Finance and the tech boards' calendars don't change. The dates are typical ('PhORCAS applications typically due'),
since each program sets its own.
"""

from __future__ import annotations

from datetime import date

from .knowledge import Knowledge
from .sources import chosen_filters, profile_fields


def program_windows(profile: dict, kn: Knowledge, start: str, end: str) -> list[dict]:
    """Calendar items for the windows from start to end (ISO days) that the profile's boards call for.

    A window with filters or licences shows when the profile chose one of its filters or holds or expects one of
    its licences; a profile that chose no filter on the board and has none of the board's licences sees them all."""
    lo, hi = date.fromisoformat(start), date.fromisoformat(end)
    licences = set(profile.get("licences") or [])
    items = []
    for board in profile_fields(profile, kn):
        windows = kn.program_windows.get(board, [])
        filters = chosen_filters(profile, board, kn)
        named = {k for w in windows for k in w.get("licences", [])}
        for w in windows:
            w_filters = set(w.get("filters", []))
            w_licences = set(w.get("licences", []))
            if (w_filters or w_licences) and (filters or licences & named) and not (
                    filters & w_filters or licences & w_licences):
                continue
            if w.get("after_graduation"):
                year, month = profile.get("graduation_year"), profile.get("graduation_month")
                days = [date(year, month, 1)] if year and month else []
            else:
                days = [date(y, w["month"], w["day"]) for y in range(lo.year, hi.year + 1)]
            items += [{"date": d.isoformat(), "kind": "program", "source": "program", "key": w["key"],
                       "title": w["title"], "when": w["when"], "notes": w["note"], "manual": False}
                      for d in days if lo <= d <= hi]
    return items
