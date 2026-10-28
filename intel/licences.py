"""Licences and certifications: what a posting asks for, and what a resume shows (plans/healthcare-board.md, D16).

The definitions are a board's `licences` in taxonomy.json, and only that board's postings and resume tracks read
them, so no other board's facts change. A posting requires a licence when its title names the occupation (a
'Registered Nurse', but not a 'Nursing Student Extern') or its description asks for the registration, regulator
or exam ('NCLEX-RN', 'CSMLS'). A certification (BLS, ACLS) is shown and never scored.
"""

from __future__ import annotations

import re

from .eligibility import _PREFERRED, _clause
from .knowledge import BoardLicences, Knowledge

# Resume lines that state a credential rather than describe work ("reported changes to the charge nurse").
_CREDENTIAL_LINE = re.compile(r"\b(?:licen[cs]\w*|registration|registered (?:with|member)|college of|nclex|"
                              r"in good standing|certifi\w+|certificate)\b", re.I)


def _asked(pattern, text: str, licence: bool) -> bool:
    """Whether the description asks for it; a licence it only prefers ('RPhT preferred') isn't required."""
    return any(not licence or not _PREFERRED.search(_clause(text, m)) for m in pattern.finditer(text))


def posting_licences(title: str, description: str, board: BoardLicences) -> dict:
    """{'required': [licence keys], 'certifications': [keys], 'pending_ok': True}, each only when stated."""
    title = title or ""
    description = (description or "")[:20000]
    required, certifications = [], []
    for item in board.items:
        named = bool(item.title and item.title.search(title)
                     and not (item.title_unless and item.title_unless.search(title)))
        if named or (item.description and _asked(item.description, description, item.kind == "licence")):
            (required if item.kind == "licence" else certifications).append(item.key)
    out: dict = {}
    if required:
        out["required"] = required
    if certifications:
        out["certifications"] = certifications
    if out and board.pending and (board.pending.search(title) or board.pending.search(description)):
        out["pending_ok"] = True
    return out


def resume_licences(sections: dict[str, list[str]], entries: list[dict], education: dict,
                    tracks: frozenset[str], kn: Knowledge) -> list[dict]:
    """What the resume shows held (a certifications line, a credential line, a licensed job title) or, for a
    licence, expected from the program ('Nursing' expects RN registration). Only the open tracks' boards are read."""
    boards = [kn.licences[b] for t in sorted(tracks) for b in kn.track_boards.get(t, []) if b in kn.licences]
    if not boards:
        return []
    lines = [l for l in sections.get("_top", [])[:3] + sections.get("certifications", []) if l.strip()]
    lines += [l for name, block in sections.items() if name not in ("_top", "certifications")
              for l in block if _CREDENTIAL_LINE.search(l)]
    credentials = "\n".join(lines)
    titles = [e["title"] for e in entries if e["block"] == "experience" and e["title"]]
    program = " ".join(education.get(k) or "" for k in ("program", "degree_text"))
    found, seen = [], set()
    for board in boards:
        for item in board.items:
            if item.key in seen:
                continue
            held = item.resume and item.resume.search(credentials)
            if not held and item.title:
                held = next((m for t in titles if (m := item.title.search(t))
                             and not (item.title_unless and item.title_unless.search(t))), None)
            expected = not held and item.kind == "licence" and item.degree and item.degree.search(program)
            if held or expected:
                seen.add(item.key)
                found.append({"key": item.key, "label": item.label, "kind": item.kind,
                              "status": "held" if held else "expected", "evidence": (held or expected).group(0)})
    return found
