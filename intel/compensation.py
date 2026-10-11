"""Compensation normalization (CAD / USD / GBP), keeping the original text.

Annualized values derived from hourly, weekly or monthly pay are always
flagged ``annualized_estimate`` and assume 40 h/week × 52 weeks.
"""

from __future__ import annotations

import re

HOURS_PER_YEAR = 2080

_CURRENCY_HINTS = [
    ("CAD", re.compile(r"\b(cad|c\$|ca\$|cdn\$?|canadian dollars?)", re.I)),
    ("USD", re.compile(r"\b(usd|us\$|u\.s\. dollars?)", re.I)),
    ("GBP", re.compile(r"(£|\bgbp\b)", re.I)),
    ("EUR", re.compile(r"(€|\beur\b)", re.I)),
]
_NUM = r"(\d{1,3}(?:[,\s]\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*([kK]|[mM](?![a-z]))?"
_MONEY = r"(?:(?:c|ca|us|cdn)\$|[$£€]|\b(?:cad|usd|gbp|eur)\s*[$£€]?)"
_RANGE = re.compile(
    rf"{_MONEY}\s*{_NUM}\s*(?:(?:cad|usd|gbp|eur)\s*)?(?:[-–—]|to|and)\s*(?:{_MONEY})?\s*{_NUM}", re.I)
_SINGLE = re.compile(rf"{_MONEY}\s*{_NUM}", re.I)
_PERIOD = [
    ("hour", re.compile(r"(/\s*h(ou)?r\b|\bhours?\b|hourly|/hr|\bph\b)", re.I)),
    ("week", re.compile(r"(/\s*w(ee)?k\b|\bweeks?\b|weekly)", re.I)),
    ("month", re.compile(r"(/\s*mo(nth)?\b|\bmonths?\b|monthly)", re.I)),
    ("year", re.compile(r"(/\s*y(ea)?r\b|\byears?\b|per\s+annum|annual(ly)?|salary|base pay|/yr|p\.?a\.?\b)", re.I)),
]
_DESC_CUE = re.compile(
    r"\b(base (?:salary|pay|compensation)|salary|pay|compensation|wages?|hourly rate|rate of pay)\b", re.I)
_NON_PAY = re.compile(
    r"\b(assets? under management|aum|revenue|operating budget|tuition|reimburse\w*|"
    r"wellness|relocation|signing bonus|sign[ -]on bonus|billion|million)\b", re.I)


def _to_number(text: str, suffix: str | None) -> float:
    value = float(re.sub(r"[,\s]", "", text))
    if suffix and suffix.lower() == "k":
        value *= 1_000
    elif suffix and suffix.lower() == "m":
        value *= 1_000_000
    return value


def _currency(text: str, country_hint: str | None) -> tuple[str, bool]:
    for code, pattern in _CURRENCY_HINTS:
        if pattern.search(text):
            return code, False
    if "$" in text:
        if country_hint == "CA":
            return "CAD", True
        if country_hint == "US":
            return "USD", True
        return "USD", True
    if country_hint == "UK":
        return "GBP", True
    return ("CAD" if country_hint == "CA" else "USD"), True


def _period(text: str, low: float) -> str:
    for period, pattern in _PERIOD:
        if pattern.search(text):
            return period
    if low < 300:
        return "hour"
    if low < 20_000:
        return "month"
    return "year"


def parse_compensation(text: str, country_hint: str | None = None) -> dict:
    """Parse a salary string.  Returns {} when nothing numeric is found."""
    original = (text or "").strip()
    if not original:
        return {}
    m = _RANGE.search(original)
    if m:
        low_suffix = m.group(2)
        if not low_suffix and m.group(4) and float(re.sub(r"[,\s]", "", m.group(1))) < 1000:
            low_suffix = m.group(4)
        low = _to_number(m.group(1), low_suffix)
        high = _to_number(m.group(3), m.group(4) or m.group(2))
        if m.group(4) is None and m.group(2) is None and high < 1000 <= low:
            high *= 1000  # '$90,000 - 105' is never meant; be safe
    else:
        m = _SINGLE.search(original)
        if not m:
            return {}
        low = high = _to_number(m.group(1), m.group(2))
    if high < low:
        low, high = high, low
    if low <= 0:
        return {}
    currency, inferred = _currency(original, country_hint)
    period = _period(original, low)
    factor = {"hour": HOURS_PER_YEAR, "week": 52, "month": 12, "year": 1}[period]
    annual_min, annual_max = round(low * factor), round(high * factor)
    if annual_max > 2_000_000 or annual_min < 5_000:
        return {"original": original, "unparsed": True}
    return {
        "original": original,
        "min": low, "max": high, "currency": currency, "currency_inferred": inferred,
        "period": period, "annual_min": annual_min, "annual_max": annual_max,
        "annualized_estimate": period != "year",
        "display": format_comp(low, high, currency, period),
        "annual_display": format_comp(annual_min, annual_max, currency, "year"),
    }


def comp_from_description(description: str, country_hint: str | None = None) -> dict:
    """Pay-transparency text: 'The base salary range for this role is $110,000 - $125,000'."""
    text = (description or "")[:30000]
    for cue in _DESC_CUE.finditer(text):
        window = text[cue.start():cue.end() + 200].split("\n\n", 1)[0]
        money = _RANGE.search(window) or _SINGLE.search(window)
        if not money:
            continue
        before = window[:money.start()]
        after = window[money.end():money.end() + 65]
        if _NON_PAY.search(before) or _NON_PAY.search(after.split(".", 1)[0].split("plus", 1)[0]):
            continue
        # A different sentence / field must not donate its dollars to a pay cue.
        if re.search(r"[.!?]\s+[A-Z]|\n[^\n:]+:", before):
            continue
        end = money.end() + len(re.split(r"[.;](?=\s|$)|\n", after, maxsplit=1)[0])
        snippet = window[:end].strip()
        parsed = parse_compensation(snippet, country_hint)
        if parsed and not parsed.get("unparsed"):
            parsed["original"] = re.sub(r"\s+", " ", snippet)
            parsed["source"] = "description"
            return parsed
    return {}


def _money(value: float, symbol: str) -> str:
    if value >= 1000:
        k = value / 1000
        return f"{symbol}{k:.1f}k".replace(".0k", "k")
    return f"{symbol}{value:,.0f}" if value == int(value) else f"{symbol}{value:,.2f}"


def format_comp(low: float, high: float, currency: str, period: str) -> str:
    symbol = {"GBP": "£", "EUR": "€"}.get(currency, "$")
    prefix = f"{currency} " if currency in ("CAD", "USD") else ""
    suffix = {"hour": "/hour", "week": "/week", "month": "/month", "year": ""}[period]
    if low == high:
        return f"{prefix}{_money(low, symbol)}{suffix}"
    return f"{prefix}{_money(low, symbol)}–{_money(high, symbol)}{suffix}"
