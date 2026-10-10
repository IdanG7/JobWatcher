"""Location parsing: raw ATS location strings -> cities, countries, bucket."""

from __future__ import annotations

import re

from .knowledge import Knowledge

_REMOTE = re.compile(r"(?<![a-z])(remote|anywhere|work from home|wfh|distributed)(?![a-z])", re.I)
_HYBRID = re.compile(r"(?<![a-z])hybrid(?![a-z])", re.I)
_REGION_CODE = re.compile(r"(?:,|\s-|\()\s*([A-Z]{2})(?=\s*(?:,|$|\)|;|\||/|\s-|\s+\d))")


def parse_location(text: str, kn: Knowledge) -> dict:
    """Return {cities, city_labels, countries, bucket, remote, hybrid}.

    ``bucket`` keeps the legacy facet vocabulary (us / canada / remote /
    other / unknown) so older filters and alert rules still apply.
    """
    raw = (text or "").strip()
    cities: list[str] = []
    countries: list[str] = []

    for city in kn.cities:
        if city["pattern"] and city["pattern"].search(raw):
            if city["not"] and city["not"].search(raw):
                continue
            if city["key"] not in cities:
                cities.append(city["key"])
                if city["country"] not in countries:
                    countries.append(city["country"])

    # Region codes: ', ON' means Canada; ', CA' is California unless a
    # Canadian province is also present ('Toronto, ON, CA').
    codes = set(_REGION_CODE.findall(raw))
    ca_codes = kn.region_codes.get("CA", set())
    us_codes = kn.region_codes.get("US", set())
    if codes & ca_codes and "CA" not in countries:
        countries.append("CA")
    canadian_context = bool(codes & ca_codes) or ("CA" in countries and "US" not in countries)
    if (codes & us_codes) - ({"CA"} if canadian_context else set()) and "US" not in countries:
        countries.append("US")

    for code, pattern in kn.country_patterns.items():
        if code in countries or not pattern:
            continue
        # bare 'us' / 'uk' / 'hk' only count when they are clearly a country token
        if pattern.search(raw):
            countries.append(code)
    for code, pattern in kn.region_names.items():
        if code not in countries and pattern and pattern.search(raw):
            # 'Washington' alone is ambiguous with DC; cities already handled it
            countries.append(code)

    remote = bool(_REMOTE.search(raw))
    hybrid = bool(_HYBRID.search(raw))
    if "US" in countries and "CA" in countries and cities:
        # 'Toronto, ON / New York, NY' keeps both; nothing to resolve
        pass

    if remote and not cities:
        bucket = "remote"
    elif "US" in countries:
        bucket = "us"
    elif "CA" in countries:
        bucket = "canada"
    elif remote:
        bucket = "remote"
    elif raw:
        bucket = "other"
    else:
        bucket = "unknown"

    return {
        "cities": cities,
        "city_labels": [kn.city_by_key[c]["label"] for c in cities],
        "countries": countries,
        "bucket": bucket,
        "remote": remote,
        "hybrid": hybrid,
        "target_city": next((c for c in cities if kn.city_by_key[c].get("target")), None),
    }


def geo_key(loc: dict) -> str:
    """Coarse geography identity for cross-source clustering."""
    if loc["cities"]:
        return loc["cities"][0]
    if loc["countries"]:
        return loc["countries"][0].lower()
    return "remote" if loc["remote"] else ""
