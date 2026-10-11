"""Local resume parsing: text extraction + deterministic field extraction.

Nothing leaves the machine.  The parser reuses the knowledge base (skills
with synonyms, the finance taxonomy, cities) so a resume is read with the
same vocabulary as job postings.  Every extracted field is a *suggestion*:
the dashboard shows it and the user decides what to apply to the profile.
Fields that are not clearly stated stay ``None`` — nothing is guessed.
"""

from __future__ import annotations

import io
import logging
import copy
import re
import zipfile
from collections import Counter
from contextlib import nullcontext
from datetime import date
from xml.etree import ElementTree

from .knowledge import Knowledge
from .locations import parse_location
from .skills import extract_skills
from .taxonomy import classify
from . import resume_insights as insights

MAX_BYTES = 5_000_000
MAX_CHARS = 60_000
MAX_PDF_STREAM = 2_000_000


class ResumeError(ValueError):
    """Unreadable or unsupported resume input (message is user-facing)."""


# ---------------------------------------------------------------- text extraction
def extract_text(filename: str, data: bytes) -> str:
    """Plain text from a .txt/.md, .docx or .pdf resume."""
    if len(data) > MAX_BYTES:
        raise ResumeError("resume file is larger than 5 MB")
    name = (filename or "").lower()
    if name.endswith((".txt", ".md", ".text")) or not name:
        return _decode(data)
    if name.endswith(".docx"):
        return _docx_text(data)
    if name.endswith(".pdf"):
        return _pdf_text(data)
    if name.endswith(".doc"):
        raise ResumeError("legacy .doc files are not supported — save as .docx or PDF, or paste the text")
    raise ResumeError("unsupported file type — upload a PDF, DOCX or TXT resume, or paste the text")


def _decode(data: bytes) -> str:
    for enc in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _docx_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > 20_000_000:        # zip-bomb guard
                raise ResumeError("document is too large")
            xml = zf.read(info)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ResumeError("could not read this .docx file") from exc
    try:
        root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc:
        raise ResumeError("could not read this .docx file") from exc
    lines = []
    for para in root.iter(f"{_W}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{_W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{_W}tab":
                parts.append("\t")
            elif node.tag in (f"{_W}br", f"{_W}cr"):
                parts.append("\n")
        lines.append("".join(parts))
    return "\n".join(lines)


def _pdf_text(data: bytes) -> str:
    try:
        import pypdf
    except ImportError as exc:
        raise ResumeError("reading PDFs needs pypdf (pip install -r requirements.txt) "
                          "— or upload DOCX/TXT, or paste the text") from exc
    try:
        logger = logging.getLogger("pypdf")
        if not any(isinstance(handler, logging.NullHandler) for handler in logger.handlers):
            logger.addHandler(logging.NullHandler())
        logger.propagate = False  # malformed-input diagnostics may contain document bytes
        with _pdf_limits(pypdf):
            reader = pypdf.PdfReader(io.BytesIO(data))
            if len(reader.pages) > 10:
                raise ResumeError("resume PDFs must contain at most 10 pages")
            parts, chars = [], 0
            for page in reader.pages:
                part = page.extract_text() or ""
                chars += len(part)
                if chars > MAX_CHARS:
                    raise ResumeError("resume PDF contains too much text; upload a shorter resume")
                parts.append(part)
            text = "\n".join(parts)
    except ResumeError:
        raise
    except Exception as exc:                  # pypdf raises many types on bad input
        raise ResumeError("could not read this PDF — try DOCX/TXT or paste the text") from exc
    if len(text.strip()) < 40:
        raise ResumeError("this PDF has no extractable text (it may be a scanned image) — paste the text instead")
    return text


def _pdf_limits(pypdf):
    """Use contextual guards on current pypdf, legacy constants on 6.10+."""
    limits = {key: MAX_PDF_STREAM for key in (
        "maximum_declared_stream_length", "array_based_stream_maximum_output_length",
        "lzw_maximum_output_length", "run_length_maximum_output_length",
        "zlib_maximum_output_length", "jbig2_maximum_output_length", "zlib_maximum_recovery_input_length")}
    if hasattr(pypdf, "apply_configuration"):
        defaults = pypdf.Configuration()
        extra = {"page_tree_maximum_entries": 1000, "page_tree_maximum_depth": 30,
                 "xform_maximum_invocations_per_extraction": 100,
                 "stream_decoding_work_maximum_length": 10_000_000}
        limits.update({k: v for k, v in extra.items() if hasattr(defaults, k)})
        return pypdf.apply_configuration(**limits)
    from pypdf import filters
    # https://pypdf.readthedocs.io/en/6.10.0/user/security.html
    for key in ("MAX_DECLARED_STREAM_LENGTH", "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
                "LZW_MAX_OUTPUT_LENGTH", "RUN_LENGTH_MAX_OUTPUT_LENGTH", "ZLIB_MAX_OUTPUT_LENGTH",
                "JBIG2_MAX_OUTPUT_LENGTH", "ZLIB_MAX_RECOVERY_INPUT_LENGTH"):
        if not hasattr(filters, key):
            raise ResumeError("update PDF support with pip install -r requirements.txt, or paste the text")
        setattr(filters, key, min(getattr(filters, key) or MAX_PDF_STREAM, MAX_PDF_STREAM))
    return nullcontext()


# ---------------------------------------------------------------- field extraction
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
_LINKEDIN = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+/?|(?<![\w/])in/[\w-]{3,}", re.I)
_SECTION = re.compile(
    r"^\s*(education|academic|experience|work experience|professional experience|employment|"
    r"skills|technical skills(?:\s*(?:&|and)\s*interests)?|skills\s*(?:&|and)\s*interests|leadership(?:\s*(?:&|and)\s*activities)?|activities|extracurricular|"
    r"projects|interests|languages|certifications|awards|summary|profile|objective)\s*:?\s*$", re.I)
_SCHOOL = re.compile(r"\b(?:university|université|universite|college|école|ecole|institute|school of|"
                     r"polytechnic|business school)\b", re.I)
_DEGREES = [
    ("phd", re.compile(r"\b(?:ph\.?\s?d|doctor(?:ate)? of)\b", re.I)),
    ("mba", re.compile(r"\bm\.?b\.?a\b", re.I)),
    ("masters", re.compile(r"\b(?:master(?:'?s)? of|m\.?sc|m\.?fin|m\.?eng|mmf|mfe|mmath|m\.?a\.? in|msf|master'?s)\b", re.I)),
    ("undergraduate", re.compile(r"\b(?:bachelor(?:'?s)?(?: of)?|b\.?com|bba|b\.?sc|b\.?a\.?(?: in| of|\b)|b\.?eng|b\.?math|"
                                 r"b\.?s\.?(?: in)?|honou?rs business|hba|undergraduate)\b", re.I)),
]
_PROGRAM = re.compile(
    r"\b(?:bachelor|master|doctor)(?:'?s)?\s+of\s+(?:arts|science|commerce|business administration|"
    r"engineering|mathematics|applied science)?\s*(?:\(?(?:hons?\.?|honou?rs)\)?)?\s*(?:,|in|–|-)?\s*([A-Z][A-Za-z&,' ]{2,60})", re.I)
_PROGRAM_IN = re.compile(r"\b(?:major(?:ing)?|concentration|specializ(?:ation|ing)|degree)\s*(?:in|:)\s*([A-Za-z&' ]{3,50})", re.I)
_GPA = re.compile(r"\b(?:c?gpa|grade point average)\s*[:\-]?\s*(\d(?:\.\d{1,2})?)\s*(?:/\s*(\d(?:\.\d)?))?", re.I)
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
_GRAD = [
    re.compile(rf"\b(?:expected|anticipated|graduat(?:ion|ing|e))\s*(?:date)?\s*[:\-]?\s*(?:{_MONTH}\.?\s*)?(20\d\d)", re.I),
    re.compile(r"\bclass of\s*(20\d\d)", re.I),
]
_RANGE = re.compile(rf"(?:{_MONTH}\.?\s*)?(20\d\d)\s*(?:-|–|—|to)\s*(?:{_MONTH}\.?\s*)?(20\d\d|present|current|now)", re.I)
_LANG_LINE = re.compile(r"\blanguages?\s*:\s*([^\n]{3,120})", re.I)
_KNOWN_LANGS = ["English", "French", "Mandarin", "Cantonese", "Spanish", "Portuguese", "German", "Italian",
                "Japanese", "Korean", "Hindi", "Punjabi", "Urdu", "Arabic", "Russian", "Hebrew", "Farsi",
                "Vietnamese", "Tagalog", "Polish", "Dutch", "Turkish", "Bengali", "Tamil", "Gujarati"]
_AUTH = [
    ("CA", "citizen", re.compile(r"\bcanadian citizen(?:ship)?\b", re.I)),
    ("CA", "permanent_resident", re.compile(r"\b(?:canadian permanent resident|permanent resident of canada)\b", re.I)),
    ("US", "citizen", re.compile(r"\b(?:u\.?s\.? citizen|american citizen|united states citizen)\b", re.I)),
    ("US", "permanent_resident", re.compile(r"\b(?:green card|u\.?s\.? permanent resident)\b", re.I)),
]
_BULLET = re.compile(r"^\s*(?:[•●▪◦\-–*·]|\d+\.)\s*")


def _sections(lines: list[str]) -> dict[str, list[str]]:
    """Split into coarse sections keyed by normalized heading."""
    out: dict[str, list[str]] = {"_top": []}
    current = "_top"
    for line in lines:
        m = _SECTION.match(line)
        if m and len(line) < 50:
            head = m.group(1).lower()
            current = ("education" if head in ("education", "academic") else
                       "experience" if "experience" in head or head == "employment" else
                       "skills" if "skill" in head else
                       "leadership" if "leadership" in head or head in ("activities", "extracurricular") else head)
            out.setdefault(current, [])
            continue
        out.setdefault(current, []).append(line)
    return out


def _guess_name(top: list[str]) -> str | None:
    for line in top[:4]:
        s = line.strip()
        if not s or _EMAIL.search(s) or _PHONE.search(s) or any(ch.isdigit() for ch in s):
            continue
        words = s.split()
        if 2 <= len(words) <= 4 and all(w[:1].isupper() for w in words if w.isalpha()) and len(s) <= 40:
            return s.title() if s.isupper() else s
    return None


def _graduation(edu_text: str, full: str) -> tuple[int | None, int | None, str | None]:
    for pattern in _GRAD:
        for text in (edu_text, full):
            m = pattern.search(text)
            if m:
                groups = m.groups()
                month = _MONTHS.get((groups[0] or "")[:3].lower()) if len(groups) > 1 else None
                return int(groups[-1]), month, m.group(0).strip()
    # education ranges: the latest end year is the graduation date
    best = None
    for m in _RANGE.finditer(edu_text):
        end = m.group(4)
        if end and end.isdigit():
            year = int(end)
            if best is None or year > best[0]:
                best = (year, _MONTHS.get((m.group(3) or "")[:3].lower()), m.group(0).strip())
    return best if best else (None, None, None)


def _education(edu_lines: list[str], full: str) -> dict:
    text = "\n".join(edu_lines) or full
    school = next((l.strip(" ,|") for l in (edu_lines or full.splitlines()) if _SCHOOL.search(l) and len(l) < 120), None)
    if school:
        school = re.split(r"\s{2,}|\t|\s[|–—]\s|,\s*(?:expected|20\d\d)", school)[0].strip(" ,|")
        school = insights.strip_city(school)
    level, degree_text = None, None
    for key, pattern in _DEGREES:
        m = pattern.search(text)
        if m:
            level = key
            line = next((l for l in text.splitlines() if m.group(0) in l), m.group(0))
            degree_text = re.sub(r"\s{2,}", " · ", line.strip())[:140]
            break
    program = None
    for pattern in (_PROGRAM, _PROGRAM_IN):
        m = pattern.search(text)
        if m:
            program = re.split(r"\s{2,}|,|\t|\(|\||–|—|\bminor\b|\bexpected\b", m.group(1), flags=re.I)[0].strip()
            if program.lower() in ("arts", "science", "commerce") or len(program) < 3:
                program = program.title()
            break
    if not program and level == "undergraduate":
        m = re.search(r"\b(b\.?com|bba|hba|commerce|business administration)\b", text, re.I)
        if m:
            program = "Commerce" if "com" in m.group(1).lower() else "Business Administration"
    gpa, gpa_text = None, None
    m = _GPA.search(full)
    if m:
        value = float(m.group(1))
        scale = float(m.group(2)) if m.group(2) else 4.0
        if 0 < value <= scale and scale in (4.0, 4.3, 4.33, 5.0, 9.0, 10.0, 12.0):
            gpa = round(value / scale * 4.0, 2) if scale not in (4.0, 4.3, 4.33) else value
            gpa_text = m.group(0).strip()
    year, month, grad_text = _graduation(text, full)
    if year and not 2015 <= year <= date.today().year + 7:
        year, month, grad_text = None, None, None
    return {"school": school, "level": level, "degree_text": degree_text, "program": program,
            "gpa": gpa, "gpa_text": gpa_text, "graduation_year": year, "graduation_month": month,
            "graduation_text": grad_text}


def _experience(lines: list[str], kn: Knowledge) -> tuple[list[dict], list[str]]:
    """Role-like lines (classified with the job taxonomy) and achievement bullets."""
    roles, bullets = [], []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        # explicit bullets, or long sentence-like lines without a date range
        if _BULLET.match(raw) or (len(line.split()) >= 12 and not re.search(r"\s{3,}|\t", line)
                                  and not _RANGE.search(line)):
            text = _BULLET.sub("", line).strip()
            if len(text) > 25:
                bullets.append(text[:400])
            continue
        if len(line) <= 160:
            # "Company — Role", "Role, Company" and "Role | Dates" all occur:
            # classify only the segment that reads like a job title, so a
            # firm name ("… Asset Management") never stands in for the role.
            title_line = _RANGE.sub("", line).strip(" ,|–—-")
            segments = [s.strip() for s in re.split(r"\s{2,}|\t|\s[|–—-]\s|,\s", title_line) if s.strip()]
            titled = [s for s in segments if _ROLE_WORD.search(s)]
            best = None
            for seg in titled:
                cls = classify(seg, kn)
                # Mixed product/division titles can tie across categories.
                # Treasury is explicit role evidence, not a low-confidence
                # inference from "capital markets" or the employer's name.
                if re.search(r"\btreasury\b", seg, re.I):
                    cls = classify("Treasury Analyst", kn)
                if cls["is_finance"] and (best is None or cls["confidence"] > best[1]["confidence"]):
                    best = (seg, cls)
            if best and best[1]["confidence"] >= 0.45:
                seg, cls = best
                roles.append({"text": re.sub(r"\s{2,}", " ", line)[:140], "title": seg, "category": cls["category"],
                              "subcategory": cls.get("subcategory"),
                              "label": cls["category_label"] + (f" · {cls['subcategory_label']}" if cls.get("subcategory_label") else "")})
    return roles[:12], bullets[:40]


_ROLE_WORD = re.compile(r"\b(?:analyst|associate|intern|internship|co-?op|summer|trader|trading|manager|"
                        r"researcher|research|banker|banking|consultant|developer|engineer|actuar\w*|underwriter|"
                        r"advisor|specialist|assistant|fellow|portfolio)\b", re.I)


def _languages(text: str) -> list[str]:
    found = []
    m = _LANG_LINE.search(text)
    scope = m.group(1) if m else ""
    for lang in _KNOWN_LANGS:
        if re.search(rf"\b{lang}\b", scope, re.I) or re.search(rf"\b(?:fluent|native|bilingual|proficient)[^.\n]{{0,30}}\b{lang}\b", text, re.I):
            found.append(lang)
    return found


def parse_resume(text: str, kn: Knowledge) -> dict:
    """Structured, explainable fields from resume text."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")[:MAX_CHARS]
    if len(text.strip()) < 40:
        raise ResumeError("the resume text is too short to parse")
    lines = [l.rstrip() for l in text.split("\n")]
    sections = _sections(lines)
    top = [l for l in sections.get("_top", []) if l.strip()]
    edu_lines = sections.get("education", [])
    exp_lines = sections.get("experience", []) + sections.get("leadership", []) + sections.get("projects", [])
    education = _education(edu_lines, text)
    roles, bullets = _experience(exp_lines or lines, kn)
    entries = insights.experience_entries(sections)
    edu_text = "\n".join(edu_lines + sections.get("certifications", []) + sections.get("awards", []))
    interests = insights.role_interests(entries, edu_text, kn)
    career = insights.career_plan(education.get("graduation_year"), education.get("graduation_month"))
    skills = extract_skills(text, kn, limit=60)
    cities: Counter = Counter()
    # contact block + experience only: the school's city is not a job preference
    for line in top[:6] + exp_lines:
        if len(line) < 160:
            for city in parse_location(line, kn)["cities"]:
                cities[city] += 1
    work_auth = {}
    for country, value, pattern in _AUTH:
        if country not in work_auth and pattern.search(text):
            work_auth[country] = value
    email = _EMAIL.search("\n".join(top[:8]) or text)
    phone = _PHONE.search("\n".join(top[:8]) or text)
    linkedin = _LINKEDIN.search(text)
    return {
        "name": _guess_name(top),
        "email": email.group(0) if email else None,
        "phone": phone.group(0).strip() if phone else None,
        "linkedin": linkedin.group(0) if linkedin else None,
        "education": education,
        "skills": skills,
        "roles": roles,
        "bullets": bullets,
        # specific role targets (never whole categories), strongest first
        "role_categories": [i["key"] for i in interests],
        "role_interests": interests,
        "career": career,
        "company_types": insights.company_types(interests),
        "entries": [{k: e[k] for k in ("block", "company", "title", "end")} for e in entries],
        "cities": [c for c, _ in cities.most_common(6)],
        "languages": _languages(text),
        "work_authorization": work_auth,
        "internships": insights.student_roles(entries),
        "chars": len(text),
    }


def profile_suggestions(parsed: dict, profile: dict, kn: Knowledge) -> dict:
    """What the resume would change in the profile, field by field."""
    edu = parsed.get("education") or {}
    out: dict = {}
    if edu.get("graduation_year") and edu["graduation_year"] != profile.get("graduation_year"):
        out["graduation_year"] = edu["graduation_year"]
    if edu.get("graduation_month") and edu["graduation_month"] != profile.get("graduation_month"):
        out["graduation_month"] = edu["graduation_month"]
    current_edu = profile.get("education") or {}
    new_edu = {k: edu[k] for k in ("level", "school", "program", "gpa") if edu.get(k) not in (None, "")
               and edu.get(k) != current_edu.get(k)}
    if new_edu.get("level") not in (None, "undergraduate", "masters", "mba", "phd"):
        new_edu.pop("level")
    if new_edu:
        out["education"] = new_edu
    skills = [s["key"] for s in parsed.get("skills") or [] if s["key"] in kn.skill_by_key]
    added = [s for s in skills if s not in (profile.get("skills") or [])]
    if added:
        out["skills"] = added
    valid_roles = set(kn.categories) | {f"{n.parent}.{n.key}" for n in kn.subcategories.values()}
    roles = [r for r in parsed.get("role_categories") or [] if r in valid_roles
             and r not in (profile.get("target_roles") or [])
             and r.split(".")[0] not in (profile.get("target_roles") or [])]
    if roles:
        out["target_roles"] = roles[:4]
    cities = [c for c in parsed.get("cities") or [] if c in kn.city_by_key and c not in (profile.get("target_locations") or [])]
    if cities:
        out["target_locations"] = cities[:4]
    langs = [l for l in parsed.get("languages") or [] if l not in (profile.get("languages") or [])]
    if langs:
        out["languages"] = langs
    auth = {k: v for k, v in (parsed.get("work_authorization") or {}).items()
            if (profile.get("work_authorization") or {}).get(k) in (None, "unknown")}
    if auth:
        out["work_authorization"] = auth
    return out


def apply_suggestions(profile: dict, suggestions: dict, fields: list[str] | None = None) -> dict:
    """Merge chosen suggestion fields into a copy of the profile (lists are unioned)."""
    result = {**profile}
    for key, value in suggestions.items():
        if fields is not None and key not in fields:
            continue
        if isinstance(value, list):
            result[key] = list(dict.fromkeys([*(profile.get(key) or []), *value]))
        elif isinstance(value, dict):
            result[key] = {**(profile.get(key) or {}), **value}
        else:
            result[key] = value
    return result


def profile_from_resume(parsed: dict, profile: dict, kn: Knowledge) -> dict:
    """Apply supported facts, retaining selected career/geography preferences.

    Skills are replaced, not unioned with demo defaults. Contact details and
    inferred location are never used to infer work authorization or preferences.
    """
    result = copy.deepcopy(profile)
    edu = parsed.get("education") or {}
    result["education"] = {**(result.get("education") or {}),
        **{k: edu[k] for k in ("school", "program", "level", "gpa") if edu.get(k) not in (None, "")}}
    result["skills"] = [s["key"] for s in parsed.get("skills", []) if s["key"] in kn.skill_by_key]
    valid = {f"{n.parent}.{n.key}" for n in kn.subcategories.values()}
    interests = [i for i in parsed.get("role_interests") or [] if i["key"] in valid]
    if interests:
        # The resume decides the targets; weights grade them (strongest = 1.0).
        result["target_roles"] = [i["key"] for i in interests]
        result["role_weights"] = {i["key"]: round(0.6 + 0.4 * i["strength"], 2) for i in interests}
    else:
        roles = [r for r in parsed.get("role_categories", []) if r in valid]
        result["target_roles"] = list(dict.fromkeys([*(profile.get("target_roles") or []), *roles]))
    types = [t for t in parsed.get("company_types") or [] if t in kn.company_types]
    if types:
        result["target_company_types"] = types
    career = parsed.get("career") or {}
    if career.get("stages"):
        result["target_stages"] = career["stages"]
    # Location stays the user's choice; the resume only fills an empty one.
    if not result.get("target_locations"):
        result["target_locations"] = [c for c in parsed.get("cities") or [] if c in kn.city_by_key][:3]
    if not result.get("target_countries"):
        countries = [kn.city_by_key[c].get("country") for c in result["target_locations"]]
        result["target_countries"] = list(dict.fromkeys(c for c in countries if c))
    if parsed.get("languages"):
        result["languages"] = list(parsed["languages"])
    if edu.get("graduation_year"):
        year = edu["graduation_year"]
        result["graduation_year"] = year
        if edu.get("graduation_month"):
            result["graduation_month"] = edu["graduation_month"]
        result["target_cycles"] = career.get("cycles") or (
            ([f"summer_{year - 1}"] if year - 1 >= date.today().year else []) + [f"new_grad_{year}"])
    # Authorization remains a user-controlled preference, even when mentioned in a CV.
    return result
