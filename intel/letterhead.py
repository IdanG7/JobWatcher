"""The top of a cover letter: the sender's lines and the date, then the recipient's.

Foothold writes these itself instead of trusting the model. The sender's lines
come from the candidate's own past letter, or the resume's name and contact
line. The recipient's come from an address the user saved for that company and
city, else the posting's own street address, else just the company and city.
Find address asks OpenStreetMap (no account or key) and the user confirms what
it finds; only the company and the place are sent.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import date

from .pdf_tools import CLOSING, DATE_LINE, GREETING, letter_parts

NOMINATIM = "https://nominatim.openstreetmap.org/search"
MAX_LINES, MAX_LINE = 6, 120
# '745 7th Avenue', '100 King St W'; not '3 Locations'
_STREET = re.compile(r"^\d+[a-z]?(?:-\d+)?\s+(?!(?:locations?|offices?|sites?|cities)\b)\S", re.I)
_CONTACT = re.compile(r"@|\(\d{3}\)|\+\d|\d{3}[-. ]\d{3}[-. ]\d{4}")
# Places named after a company that aren't its offices: 'Barclays Center' the arena, its subway station.
_NOT_OFFICES = {"railway", "public_transport", "highway", "leisure", "tourism", "aeroway", "natural", "waterway"}
_lookups = threading.Lock()         # Nominatim's policy: at most one request a second
_last_lookup = 0.0
_found: dict[str, list[dict]] = {}


def date_line(today: date, like: str = "") -> str:
    """'October 17, 2026', or 'October 17th, 2026' when ``like`` (the base letter) writes its date that way."""
    day = str(today.day)
    if re.search(r"\b\d{1,2}(?:st|nd|rd|th),? \d{4}\b", like):
        day += "th" if 11 <= today.day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(today.day % 10, "th")
    return f"{today.strftime('%B')} {day}, {today.year}"


def place_key(job: dict) -> str:
    """Saved addresses belong to a company in a city."""
    return f"{(job.get('company') or '').strip().lower()}|{job.get('city') or (job.get('location') or '').strip().lower()}"


def posting_address(location: str) -> list[str]:
    """['745 7th Avenue', 'New York'] when the posting's location names a street, else []."""
    parts = [part.strip() for part in (location or "").split(",") if part.strip()]
    street = next((part for part in parts if _STREET.match(part)), None)
    if not street:
        return []
    rest = ", ".join(part for part in parts if part is not street)
    return [street, rest] if rest else [street]


def recipient(job: dict, saved: dict) -> dict:
    """{'lines': [...], 'source': 'saved' | 'posting' | 'city'}: who the letter is addressed to."""
    if place_key(job) in saved:
        return {"lines": saved[place_key(job)]["lines"], "source": "saved"}
    company = job.get("company") or ""
    address = posting_address(job.get("location") or "")
    if address:
        return {"lines": ["Hiring Manager", company, *address], "source": "posting"}
    return {"lines": [line for line in ("Hiring Manager", company, job.get("location") or "") if line], "source": "city"}


def clean_lines(lines) -> list[str]:
    """The recipient lines the user typed, blank ones dropped; raises ValueError with a message for them."""
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise ValueError("the address must be a list of lines")
    kept = [" ".join(line.split()) for line in lines if line.strip()]
    if not kept or len(kept) > MAX_LINES or any(len(line) > MAX_LINE for line in kept):
        raise ValueError(f"write the address in 1 to {MAX_LINES} lines of up to {MAX_LINE} characters")
    return kept


def candidate_name(resume_text: str) -> str:
    """The resume's first line, title-cased if the resume shouts it ('IDAN REITMAN')."""
    first = next((line.strip() for line in resume_text.splitlines() if line.strip()), "")
    return first.title() if first.isupper() else first


def sender(letters: list[str], resume_text: str) -> list[str]:
    """The candidate's own lines: those above the date in a past letter, else the resume's name and contact line."""
    for text in letters:
        head = letter_parts(text)[0]
        if len(head) > 1:
            return head[:-1]             # the last one is the date
    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if not lines:
        return []
    contact = next((line for line in lines[1:4] if _CONTACT.search(line)), None)
    return [candidate_name(resume_text), *([contact] if contact else [])]


def sign_off(letter: str, name: str) -> str:
    """The name under a closing left without one ('Best Regards,'): a past letter signed with an image of a
    signature comes out of its PDF with no name, and the model copies that. The letter's PDF draws that image
    in the name's place (pdf_tools.letter_pdf)."""
    lines = letter.rstrip().split("\n")
    return "\n".join([*lines, name]) if name and CLOSING.fullmatch(lines[-1].strip()) else letter


def header(letter: str) -> tuple[list[str], str | None]:
    """The letter's own sender lines and date line: ([], None) when it has no date above the greeting."""
    own = letter_parts(letter)[0]
    return (own[:-1], own[-1]) if own and DATE_LINE.match(own[-1]) else ([], None)


def set_header(letter: str, sender_lines: list[str], dated: str, recipient_lines: list[str]) -> str:
    """The letter under this header: the sender's lines, the date, the recipient's lines, then the letter from
    its greeting. A text without a greeting is left as it is."""
    lines = letter.split("\n")
    greeting = next((i for i, line in enumerate(lines) if GREETING.match(line)), None)
    if greeting is None:
        return letter
    return "\n".join([*sender_lines, dated, "", *recipient_lines, ""] + lines[greeting:])


def address_lines(address: dict) -> list[str]:
    """['745 7th Avenue', 'New York, NY 10019'] from a Nominatim address; [] without a street."""
    street = " ".join(filter(None, [address.get("house_number"), address.get("road")]))
    if not street:
        return []
    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or ""
    region = (address.get("ISO3166-2-lvl4") or "").partition("-")[2] or address.get("state") or ""
    last = ", ".join(filter(None, [city, " ".join(filter(None, [region, address.get("postcode")]))]))
    return [street, last] if last else [street]


def find_address(company: str, place: str, user_agent: str) -> list[dict]:
    """Up to three street addresses OpenStreetMap has for the company in this place: [{'name', 'lines'}].
    Raises LookupError with a message for the user."""
    global _last_lookup
    query = ", ".join(part for part in (company.strip(), place.strip()) if part)
    if query in _found:
        return _found[query]
    import requests
    with _lookups:
        time.sleep(max(0.0, 1 - (time.monotonic() - _last_lookup)))
        try:
            response = requests.get(NOMINATIM, params={"q": query, "format": "jsonv2", "addressdetails": 1, "limit": 8},
                                    headers={"User-Agent": user_agent}, timeout=10)
            if not response.ok:
                raise ValueError(f"HTTP {response.status_code}")
            items = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise LookupError("Couldn't reach OpenStreetMap. Check the connection, or type the address.") from exc
        finally:
            _last_lookup = time.monotonic()
    found: list[dict] = []
    for item in items if isinstance(items, list) else []:
        if item.get("category") in _NOT_OFFICES:
            continue
        lines = address_lines(item.get("address") or {})
        if lines and all(lines != f["lines"] for f in found):
            found.append({"name": item.get("name") or str(item.get("display_name", "")).split(",")[0], "lines": lines})
    _found[query] = found[:3]
    return _found[query]
