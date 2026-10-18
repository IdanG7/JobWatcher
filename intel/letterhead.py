"""The top of a cover letter: the sender's lines and the date, then the recipient's.

Foothold writes these itself instead of trusting the model. The sender's lines
come from the candidate's own past letter, or the resume's name and contact
line. The recipient's come from an address the user saved for that company and
city, else a street address in the posting's location, else the office and
contact the local model read in the posting's text, else just the company and
city. OpenStreetMap (no account or key) adds the postal code to a street found
in the posting, and Find address lists the company's addresses there for the
user to confirm; only the company, street and city are sent.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import date

from .pdf_tools import CLOSING, DATE_LINE, GREETING, letter_parts

NOMINATIM = "https://nominatim.openstreetmap.org/search"
MAX_LINES, MAX_LINE = 6, 120
_SALUTED = {"dear", "hiring", "manager", "managers", "team", "committee", "recruiter", "recruiting", "recruitment"}
# '745 7th Avenue', '100 King St W'; not '3 Locations'
_STREET = re.compile(r"^\d+[a-z]?(?:-\d+)?\s+(?!(?:locations?|offices?|sites?|cities)\b)\S", re.I)
_CONTACT = re.compile(r"@|\(\d{3}\)|\+\d|\d{3}[-. ]\d{3}[-. ]\d{4}")
# Places named after a company that aren't its offices: 'Barclays Center' the arena, its subway station.
_NOT_OFFICES = {"railway", "public_transport", "highway", "leisure", "tourism", "aeroway", "natural", "waterway"}
# Words that say what kind of street or unit it is: the model may spell them out ('St' as 'Street', a bare '5th'
# as '5th Floor'), so only the other words have to be in the posting.
GENERIC = frozenset("""st street ave avenue rd road blvd boulevard dr drive way pl place ln lane ct court cres
crescent pkwy parkway hwy highway sq square ter terrace fl floor ste suite unit level lvl rm room bldg building
w west e east n north s south nw ne sw se the of and at""".split())
_UNIT = re.compile(r"\d+(?:st|nd|rd|th)?(?:\s+(?:floor|fl\.?))?|(?:floor|fl\.?|suite|ste\.?|unit|level)\s*#?\w+", re.I)
_NOT_A_NAME = frozenset("""hiring manager managers team recruiter recruiting recruitment talent acquisition human
resources hr department careers people office student programs program campus""".split())
_lookups = threading.Lock()         # Nominatim's policy: at most one request a second
_last_lookup = 0.0
_answers: dict[str, list] = {}


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def stated(field: str, value: str, posting: set[str]) -> bool:
    """Whether the posting says ``value``: its words other than GENERIC ones are all in it. A street needs a
    number and a name; a contact needs to read like a person's full name."""
    key = [word for word in words(value) if word not in GENERIC]
    if not key or not set(key) <= posting:
        return False
    if field == "street":
        return any(word[0].isdigit() for word in key) and any(word.isalpha() for word in key)
    if field == "contact":
        names = value.split()
        return (2 <= len(names) <= 4 and all(name[:1].isupper() for name in names)
                and not any(word.isdigit() or word in _NOT_A_NAME for word in key))
    return True


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


def tidy_street(street: str, unit: str = "") -> tuple[str, str]:
    """The street and unit as an address writes them: Workday's 'Toronto-150 Bloor St W, 5th' is
    ('150 Bloor St W', '5th Floor')."""
    start = re.search(r"\d+[a-z]?\s+[a-z]", street, re.I)
    street = street[start.start():] if start else street
    head, comma, tail = street.partition(",")
    if comma and _UNIT.fullmatch(tail.strip()):
        street, unit = head.strip(), unit or tail.strip()
    if re.fullmatch(r"\d+(?:st|nd|rd|th)", unit, re.I):
        unit += " Floor"
    return street, unit


def details_address(job: dict, details: dict) -> list[str]:
    """['150 Bloor St W, 5th Floor', 'Toronto, ON M5S 2X9'] from what the model read in the posting (and the
    postal code OpenStreetMap has for it); [] without a street."""
    if not details.get("street"):
        return []
    street = ", ".join(filter(None, [details["street"], details.get("unit")]))
    location = job.get("location") or ""
    city = details.get("city") or location.split(",")[0].strip()
    code = " ".join(filter(None, [details.get("region"), details.get("postcode")]))
    if code:
        return [street, ", ".join(filter(None, [city, code]))]
    # Without a postal code, the posting's location ('Toronto, Ontario, Canada') says more than the city alone.
    return [street, location if city.lower() in location.lower() else city]


def recipient(job: dict, saved: dict, details: dict | None = None) -> dict:
    """{'lines': [...], 'source': 'saved' | 'posting' | 'city'}: who the letter is addressed to. ``details`` is
    what the model read in the posting: {'street', 'unit', 'city', 'contact', 'region', 'postcode'}."""
    if place_key(job) in saved:
        return {"lines": saved[place_key(job)]["lines"], "source": "saved"}
    details = details or {}
    company = job.get("company") or ""
    to = details.get("contact") or "Hiring Manager"
    address = posting_address(job.get("location") or "") or details_address(job, details)
    if address:
        return {"lines": [to, company, *address], "source": "posting"}
    return {"lines": [line for line in (to, company, job.get("location") or "") if line], "source": "city"}


def greet(letter: str, name: str) -> str:
    """'Dear Hiring Manager,' as 'Dear <name>,' when the posting names the person to write to."""
    return re.sub(r"(?im)^[ \t]*dear hiring (?:manager|team)[ \t]*,?[ \t]*$", f"Dear {name},", letter, count=1) \
        if name else letter


def clean_lines(lines) -> list[str]:
    """The recipient lines the user typed, blank ones dropped; raises ValueError with a message for them."""
    if not isinstance(lines, list) or not all(isinstance(line, str) for line in lines):
        raise ValueError("the address must be a list of lines")
    kept = [" ".join(line.split()) for line in lines if line.strip()]
    if not kept or len(kept) > MAX_LINES or any(len(line) > MAX_LINE for line in kept):
        raise ValueError(f"write the address in 1 to {MAX_LINES} lines of up to {MAX_LINE} characters")
    return kept


_HEADING = re.compile(r"^(?:resume|résumé|curriculum vitae|cv)$", re.I)


def candidate_name(resume_text: str) -> str:
    """The resume's name, title-cased if the resume shouts it ('IDAN REITMAN'): its first line, or the first after
    a 'Curriculum Vitae' heading, up to the contact details that often share it ('Aisha Mohammed | aisha@…')."""
    for line in resume_text.splitlines()[:6]:
        first = re.split(r"\s*[|•·]\s*|\s{2,}|\s[–—-]\s", line.strip())[0].strip()
        if first and not _HEADING.match(first) and not _CONTACT.search(first) and "," not in first:
            return first.title() if first.isupper() else first
    return ""


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
    rest = lines[greeting:]
    # The model sometimes salutes twice: 'To the Hiring Manager,' then 'Hiring Manager,'.
    after = next((i for i in range(1, len(rest)) if rest[i].strip()), None)
    if after and rest[after].rstrip().endswith((",", ":")) and \
            set(words(rest[after])) <= set(words(rest[0])) | _SALUTED:
        del rest[1:after + 1]
    return "\n".join([*sender_lines, dated, "", *recipient_lines, ""] + rest)


def address_lines(address: dict) -> list[str]:
    """['745 7th Avenue', 'New York, NY 10019'] from a Nominatim address; [] without a numbered street."""
    if not (address.get("house_number") and address.get("road")):
        return []
    street = f"{address['house_number']} {address['road']}"
    city = address.get("city") or address.get("town") or address.get("village") or address.get("municipality") or ""
    region = (address.get("ISO3166-2-lvl4") or "").partition("-")[2] or address.get("state") or ""
    last = ", ".join(filter(None, [city, " ".join(filter(None, [region, address.get("postcode")]))]))
    return [street, last] if last else [street]


def _search(query: str, user_agent: str) -> list:
    """Nominatim's places for ``query``, each search sent once. Raises LookupError with a message for the user."""
    global _last_lookup
    if query in _answers:
        return _answers[query]
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
    _answers[query] = items if isinstance(items, list) else []
    return _answers[query]


def find_address(company: str, place: str, user_agent: str) -> list[dict]:
    """Up to three street addresses OpenStreetMap has for the company in this place: [{'name', 'lines'}].
    Raises LookupError with a message for the user."""
    found: list[dict] = []
    for item in _search(", ".join(part for part in (company.strip(), place.strip()) if part), user_agent):
        if item.get("category") in _NOT_OFFICES:
            continue
        lines = address_lines(item.get("address") or {})
        if lines and all(lines != f["lines"] for f in found):
            found.append({"name": item.get("name") or str(item.get("display_name", "")).split(",")[0], "lines": lines})
    return found[:3]


def locate(street: str, place: str, user_agent: str) -> dict:
    """{'city', 'region', 'postcode'} for this street address, when OpenStreetMap has the building: the same
    house number on a road with the street's name. {} otherwise; raises LookupError when it can't be reached."""
    number = re.match(r"\s*(\d+[a-z]?)\b", street, re.I)
    names = [word for word in words(street) if word not in GENERIC and not word[0].isdigit()]
    if not (number and names):
        return {}
    for item in _search(f"{street}, {place}", user_agent):
        address = item.get("address") or {}
        numbers = {n.strip().lower() for n in re.split(r"[;,]", address.get("house_number") or "")}
        if number.group(1).lower() in numbers and names[0] in words(address.get("road") or "") and address.get("postcode"):
            lines = address_lines(address)
            return {"city": lines[-1].split(",")[0] if len(lines) > 1 else "",
                    "region": (address.get("ISO3166-2-lvl4") or "").partition("-")[2] or address.get("state") or "",
                    "postcode": address["postcode"]}
    return {}
