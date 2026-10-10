"""Eligibility extraction from job descriptions.

Every field is either extracted with an evidence snippet or left as None.
The UI renders None as "Not specified" — nothing is guessed.
"""

from __future__ import annotations

import re

_DOCTORAL = r"(?:ph\.?\s?d\.?|doctoral|doctorate)(?!\w)"
_DEGREE_RULES = [
    ("phd", re.compile(
        rf"\b{_DOCTORAL}\s+(?:degree\s+)?(?:candidates?|students?|graduates?|program(me)?|only|required)\b|"
        rf"\b{_DOCTORAL}[^.\n;]{{0,40}}\b(required|minimum|must have)\b|"
        rf"\b(pursuing|enrolled in|working towards?)\s+(?:(?:a|an|your|the)\s+)?{_DOCTORAL}|"
        rf"\b(requires?|must (?:hold|have)|required to (?:hold|have))\s+(?:(?:a|an|completed)\s+)*{_DOCTORAL}",
        re.I)),
    ("mba", re.compile(r"\b(mba (candidates?|students?|program|required|graduates?)|pursuing (an|your) mba|first[\s-]year mba|completed (an|your) mba)\b", re.I)),
    ("masters", re.compile(r"\b(master'?s|msc|m\.sc|meng|mfe|mmf|mqf|mfin|msf|graduate degree)\b[^.\n]{0,40}\b(required|program|students?|candidates?|pursuing|enrolled)\b|\bpursuing (a|your) master'?s\b", re.I)),
    ("undergraduate", re.compile(r"\b(bachelor(?:'?s)?|undergraduate|undergrad|b\.?a\.?|b\.?sc|b\.?s\.|b\.?comm?|bba|college (students?|juniors?|seniors?)|university students?|rising (junior|senior)s?|sophomores?|juniors? and seniors?)\b", re.I)),
]
_PREFERRED = re.compile(r"\b(preferred|a plus|an asset|nice to have|beneficial|desirable|ideally)\b", re.I)
_DEGREE_NAME = r"(?:bachelor(?:['’]?s)?|undergrad(?:uate)?|master(?:['’]?s)?|ph\.?\s?d|doctoral|doctorate|mba)"
_DEGREE_LIST = re.compile(
    rf"\b{_DEGREE_NAME}(?:\s+degree)?(?:\s*(?:,\s*(?:(?:and|or)\s+)?|(?:and|or)\s+|[/&]\s*){_DEGREE_NAME}(?:\s+degree)?)+\b",
    re.I)
_UNDERGRAD_NAME = re.compile(r"\b(bachelor|undergrad)", re.I)
_GRAD_NAME = re.compile(r"\b(master|ph\.?\s?d|doctoral|doctorate|mba)", re.I)
_GPA = re.compile(
    r"(?:(?:minimum|min\.?|cumulative|overall)\s+(?:of\s+(?:a\s+)?)?(?:cumulative\s+)?gpa(?:\s+of)?\s*[:=]?\s*(?:a\s+)?(\d\.\d{1,2})|"
    r"gpa\s+(?:of\s+)?(?:at least\s+|minimum\s+(?:of\s+)?)?(\d\.\d{1,2})\s*(?:\+|or (?:higher|above|better)|/\s*4\.0)?|"
    r"(\d\.\d{1,2})\s*(?:/\s*4\.0\s*)?(?:\+\s*)?(?:cumulative\s+)?gpa)", re.I)
_WORK_AUTH = [
    ("Canada", re.compile(r"\b(legally (eligible|entitled|authori[sz]ed) to work in canada|eligible to work in canada|authori[sz]ed to work in canada|work (permit|authori[sz]ation) (for|in) canada|canadian work authori[sz]ation)\b", re.I)),
    ("United States", re.compile(r"\b(legally (eligible|entitled|authori[sz]ed) to work in the (united states|u\.?s\.?)|authori[sz]ed to work in the (united states|u\.?s\.?)|eligible to work in the (united states|u\.?s\.?)|u\.?s\.? work authori[sz]ation)\b", re.I)),
    ("United Kingdom", re.compile(r"\b(right to work in the (uk|united kingdom))\b", re.I)),
]
_NO_SPONSOR = re.compile(
    r"\b((will|does|do|can|is|are)\s*(not|n['’]t|unable to)\s+(be able to\s+)?(provide|offer|sponsor|support)\w*[^.\n]{0,40}?(sponsor\w*|visas?)|"
    r"(unable|not able) to (provide|offer|support)?\s*(visa |immigration )?sponsor\w*|no (visa )?sponsorship|"
    r"sponsorship (is|will) not (be )?(available|provided|offered)|"
    r"without (the need for |requiring )?(current or future )?(visa |employment )?sponsorship|not eligible for (visa )?sponsorship)\b", re.I)
_SPONSOR_OK = re.compile(r"\b((visa )?sponsorship (is )?(available|provided|offered)|will sponsor|able to sponsor|we sponsor|offers? (visa )?sponsorship|open to sponsor(ing|ship))\b", re.I)
_CITIZENSHIP = [
    ("U.S. citizenship required", re.compile(r"\b(u\.?s\.? citizen(ship)? (is )?required|must be (a )?u\.?s\.? citizens?|united states citizenship|security clearance|itar)\b", re.I)),
    ("Canadian citizen or PR", re.compile(r"\b(canadian citizens?( or| and)? (permanent residents?|pr)|must be (a )?canadian citizen|canadian citizenship)\b", re.I)),
    ("Permanent resident or citizen", re.compile(r"\b(permanent residents? (or|and) citizens?|citizens? (or|and) permanent residents?|green card)\b", re.I)),
]
_LANGUAGES = ["french", "english", "mandarin", "cantonese", "spanish", "portuguese", "german",
              "japanese", "korean", "arabic", "italian", "hindi", "russian"]
_LANG = re.compile(
    rf"\b(?:(?:fluen(?:t|cy)|proficien(?:t|cy)|bilingual(?:ism)?|business[\s-]level|native|working knowledge|written and (?:spoken|oral)|oral and written)[^.\n]{{0,40}}?)\b({'|'.join(_LANGUAGES)})\b|"
    rf"\b({'|'.join(_LANGUAGES)})\b[^.\n]{{0,25}}?\b(?:fluency|proficiency|is required|required|is an asset|is a plus|an asset)\b|"
    rf"\bbilingual\b\s*\(?\s*(?:english\s*(?:and|/|&)\s*)?({'|'.join(_LANGUAGES)})", re.I)
_EXP_PRIOR = re.compile(r"\b(prior|previous|relevant) (internship|work|industry|finance|banking) experience (is )?(required|preferred|an asset|a plus)\b", re.I)


def _snip(text: str, m: re.Match, pad: int = 40) -> str:
    return re.sub(r"\s+", " ", text[max(0, m.start() - pad): m.end() + pad]).strip()


def _clause(text: str, m: re.Match) -> str:
    """Include qualifiers before and after an occurrence, without adjacent clauses."""
    start = max(text.rfind(c, 0, m.start()) for c in ".\n;") + 1
    ends = [pos for c in ".\n;" if (pos := text.find(c, m.end())) >= 0]
    return text[start:min(ends) if ends else len(text)]


def extract_eligibility(description: str, title: str = "") -> dict:
    text = f"{title}\n{description or ''}"[:30000]
    out: dict = {"degree": None, "degree_text": None, "degree_required": [], "gpa_min": None, "gpa_text": None,
                 "work_authorization": [], "work_auth_text": None, "sponsorship": None, "sponsorship_text": None,
                 "citizenship": None, "citizenship_text": None, "languages": [], "language_text": None,
                 "experience": None}

    for level, pattern in _DEGREE_RULES:
        for m in pattern.finditer(text):
            if level in ("phd", "masters") and _PREFERRED.search(_clause(text, m)):
                continue
            out["degree_required"].append(level)
            if out["degree"] is None:
                out["degree"] = {"phd": "PhD", "mba": "MBA", "masters": "Master's",
                                 "undergraduate": "Undergraduate"}[level]
                out["degree_text"] = _snip(text, m)
            break
    # A degree list joined with commas, slashes or "and" is also inclusive.
    # Match the list itself so unrelated degree clauses cannot waive a requirement.
    out["degree_alternatives"] = "undergraduate" in out["degree_required"] and any(
        _UNDERGRAD_NAME.search(m.group()) and _GRAD_NAME.search(m.group())
        for m in _DEGREE_LIST.finditer(text))

    for m in _GPA.finditer(text):
        if _PREFERRED.search(_clause(text, m)):
            continue
        value = next((g for g in m.groups() if g), None)
        if value and 2.0 <= float(value) <= 4.0:
            out["gpa_min"] = float(value)
            out["gpa_text"] = _snip(text, m)
            break

    for country, pattern in _WORK_AUTH:
        m = pattern.search(text)
        if m:
            out["work_authorization"].append(country)
            out["work_auth_text"] = out["work_auth_text"] or _snip(text, m)

    m = _NO_SPONSOR.search(text)
    if m:
        out["sponsorship"] = "not_available"
        out["sponsorship_text"] = _snip(text, m)
    else:
        m = _SPONSOR_OK.search(text)
        if m:
            out["sponsorship"] = "available"
            out["sponsorship_text"] = _snip(text, m)

    for label, pattern in _CITIZENSHIP:
        m = pattern.search(text)
        if m:
            out["citizenship"] = label
            out["citizenship_text"] = _snip(text, m)
            break

    langs, required = [], []
    for m in _LANG.finditer(text):
        lang = next((g for g in m.groups() if g), "").lower()
        if lang and lang != "english":
            if lang.title() not in langs:
                langs.append(lang.title())
            out["language_text"] = out["language_text"] or _snip(text, m)
            if not _PREFERRED.search(_clause(text, m)) and lang.title() not in required:
                required.append(lang.title())
    out["languages"] = langs
    out["languages_required"] = required

    m = _EXP_PRIOR.search(text)
    if m:
        out["experience"] = m.group(0)
    return out
