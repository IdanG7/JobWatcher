"""Compensation normalization (CAD / USD / GBP / EUR), keeping the original text.

Annualized values derived from hourly, weekly, semi-monthly or monthly pay are always
flagged ``annualized_estimate`` and assume 40 h/week × 52 weeks.
"""

from __future__ import annotations

import html
import re

HOURS_PER_YEAR = 2080
PER_YEAR = {"hour": HOURS_PER_YEAR, "week": 52, "semimonth": 24, "month": 12, "year": 1}

_CURRENCY_HINTS = [
    # Not the design software: '3D CAD', 'CAD tools'
    ("CAD", re.compile(r"\b((?<![23]d )(?:cad)+\b(?!\s*(?:/|-|software|systems?|tools?|design|drawings?|models?|"
                       r"modell?ing|packages?|programs?|experience|skills?|files?|data|platforms?|applications?))"
                       r"|c\$|ca\$|cdn\b\$?|canadian dollars?)", re.I)),
    ("USD", re.compile(r"\b((?:usd)+\b|us\$|u\.s\. dollars?)", re.I)),
    ("GBP", re.compile(r"(£|\bgbp\b)", re.I)),
    ("EUR", re.compile(r"(€|\beur\b)", re.I)),
]
# Pay in a currency Foothold doesn't convert is left unread rather than shown as dollars
_OTHER_MONEY = re.compile(r"\b(?:pln|mxn|aud|nzd|inr|jpy|sgd|hkd|chf|brl|sek|nok|dkk|zar|cny|rmb|ils|krw|php|myr|"
                          r"czk|huf|ron|lei|aed|sar)\b|zł|₹|¥|₩|₪|\b(?:a|au|s|nz|hk|r|mx)\$", re.I)
_CODE = r"(?:usd|cad|gbp|eur)"
_MONEY = r"(?:(?:c|ca|us|cdn)\$|[$£€]|\b(?:cad|usd|gbp|eur)\s*[$£€]?)"
# One amount: '$120,000', 'CAD 58,000', '$35/hr', '105k', '172,400.00 USD', '€2,450', French '45 700,00 $'. A bare
# number counts as the other end of a range ('$3,500-5,700', '172,400.00 - 223,400.00 USD'), or under a pay label.
_AMOUNT = re.compile(
    # Workday runs fields together: 'Pay Details: 170,000$140,000 - 170,000$160,000 USDUSD'
    rf"(?:(?<![\w.,])|(?=[$£€]))(?:(?P<sign>{_MONEY})\s*)?"
    # '$97, 300', '$ 159 , 250', a decimal comma ('$38,85 - $54,34 CDN hourly'); never part of a longer number
    r"(?P<num>\d{1,3}(?: ?, ?\d{3})+(?:\.\d+)?|\d{1,3}(?: \d{3})+(?:,\d\d)?(?!\d)|\d{1,3},\d\d(?![\d,])"
    r"|\d+(?:\.\d+)?)(?![,.]?\d)"
    r"(?:\s*(?P<suffix>mm|bn|[kmb])(?![a-z]))?"
    r"(?P<post>\s?(?:[$£€]|zł)(?!\s?\d))?"
    r"(?P<unit>\s*/\s*(?:h(?:ou)?r|y(?:ea)?r|annum|wk|week|mo(?:nth)?)\b"
    r"|\s+(?:per|an?)\s+(?:hours?|year|annum|week|month)\b|\s+(?:annually|hourly|weekly|monthly|yearly|annual)\b)?"
    # Not the next label's: '$160,000 - $210,000 CAD Salary Range: C$225,000'
    rf"(?:\s*\(?(?P<code>{_CODE})\b(?![ \t]+(?:salary|pay|base|range|hourly)\b)\)?)?", re.I)
_DIGITS = re.compile(r"\d[\d,. ]*")
# What may stand between a range's ends: a dash, 'to' or 'and', with min / mid / max or a unit around it.
_JOIN = re.compile(r"\s*(?:(?:min(?:imum)?|max(?:imum)?|mid(?:point)?|hourly|wage|salary|base|per|hour|hr|year|yr|"
                   r"annual(?:ly)?|usd|cad|gbp|eur|/|\.)\s*)*(?:[-–—]+|(?:up\s+)?(?<![a-z])to(?![a-z])|\band\b|"
                   r"\bthrough\b)\s*(?:(?:min(?:imum)?|max(?:imum)?|mid(?:point)?)\b\s*)?", re.I)
_PERIODS = [
    ("semimonth", re.compile(r"semi-?monthly|twice (?:a|per) month", re.I)),
    ("hour", re.compile(r"/\s*h(?:ou)?r\b|\bper\s+hours?\b|\ban\s+hour\b|\bhourly\b", re.I)),
    ("week", re.compile(r"/\s*(?:wk|week)\b|\bper\s+week\b|\ba\s+week\b|\bweekly\b", re.I)),
    ("month", re.compile(r"/\s*mo(?:nth)?\b|\bper\s+month\b|\ba\s+month\b|\bmonthly\b", re.I)),
    ("year", re.compile(r"/\s*y(?:ea)?r\b|\bper\s+(?:year|annum)\b|\ba\s+year\b|\bannual(?:ly|ized)?\b|\byearly\b"
                        r"|\bp\.a\.", re.I)),
]
_BARE_PERIOD = re.compile(r"\s*(HOUR|WEEK|MONTH|YEAR)\b")      # banks' 'CAD 25.50 - 32.00 HOUR'
# 'per week' in '5 days per week' is the schedule, not the pay
_SCHEDULE = re.compile(r"(?:hours?|hrs?|days?|shifts?|times?|nights?|weeks?|months?)\s*$", re.I)
# The largest amount a period read away from the figures can be: '$43,500 to $57,670' is never monthly pay
_MOST = {"hour": 300, "week": 10_000, "semimonth": 40_000, "month": 40_000, "year": float("inf")}
_DESC_CUE = re.compile(
    r"\b(base (?:salary|pay|compensation|range|rate)|salar(?:y|ies)|"
    r"pay(?! (?:periods?|transparency|warrants?|cycles?|days?|dates?|parity|frequency|schedules?|stubs?)\b)|"
    r"compensation|wages?|stipend|(?:hourly|hiring) (?:rate|range)|rate of pay)\b", re.I)
_NON_PAY = re.compile(
    r"\b(?:assets? under management|aum|revenue|quota|budget|tuition|reimburs\w*|wellness|relocation|"
    r"(?:sign(?:ing|[ -]on) )?bonus(?:es)?|referral|billion|million|match(?:ing)?|subsid\w*|allowance|coverage|"
    r"insurance|childcare|funding|raised|spend(?:s|ing)?|savings?|waiv\w*|book of|ote|on[- ]target(?: earnings)?|"
    r"of (?:your |the )?(?:sales )?target|(?:targeted )?commissions?|target(?:ed)? (?:cash|earnings)|"
    r"total target(?:ed)? compensation|"
    r"(?:learning|development|education|phone|internet|home office|work from home|commut\w*|meal|fitness|gym|"
    r"lifestyle|equipment|housing)\b[^.$\n]{0,25}?(?:stipend|credit|benefit)s?)\b|\b401\s*\(?k\b", re.I)
# 'excluding equity and bonus', 'does not include bonus', 'inclusive of the potential bonus value': the amount is
# said to leave it out or take it in, so it isn't one
_EXCLUDING = re.compile(r"\b(?:excluding|excludes|exclusive of|inclusive of|not including|(?:does not|doesn't|not) "
                        r"include|before|without)\b[^.;:()]{0,30}$", re.I)
_PARENS = re.compile(r"\([^()]*\)")
# Pay named after an OTE or bonus on the same line is still pay: 'The OTE includes a base hourly rate of $25.49'
_BASE_PAY = re.compile(r"\bbase (?:salary|pay|compensation|(?:hourly )?(?:rate|wage))\b", re.I)
_PAY_NAMED = re.compile(rf"(?:{_BASE_PAY.pattern}|\b(?:salar(?:y|ies)|wages?|(?:hourly|pay|salary|compensation) "
                        r"(?:rate|range)))"
                        r"(?: ranges?\b)?", re.I)
# 'On-target Earnings OR Base Salary range', 'Salary Range or On Target Earnings': either one is the base pay
_OR_PAY_AFTER = re.compile(r"\s*or\s+(?:base\s+)?(?:salary|pay)\b", re.I)
_OR_PAY_BEFORE = re.compile(r"\b(?:salary|pay)(?: ranges?)?\s+or\s+$", re.I)
_LABEL_END = re.compile(r"[^.!?\n]{0,60}?(?::|=|\bis|\bof|\bfrom|\bbetween)\s*", re.I)
_SENTENCE_END = re.compile(r"[.!?]\s+(?=[A-Z(])")
# Where the words right after an amount stop being about it: '$235,000+ Bonus' adds one, '$180,000+ in commission'
# is still one phrase
_TAIL_END = re.compile(r",(?!\d)|[;\n]|\+(?!\s*in\b)|\.(?:\s|$)|\b(?:plus|with|and)\b", re.I)
# 'Starting Hourly Rate: $19.50' gives way to 'Pay Range: $19.50 - $29.25' below it
_PREFER_RANGE_WITHIN = 1500
_STARTING = re.compile(r"\bstart(?:s|ing)?\b", re.I)


def _plain(text: str) -> str:
    """HTML codes some sites leave in ('&mdash;', '&#xa;', twice-escaped '&amp;nbsp;') read as what they stand for."""
    for _ in range(2):
        text = html.unescape(text)
    return re.sub(r"[\xa0  ]", " ", text)


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


def _value(token: re.Match, euro: bool) -> float:
    num = token["num"]
    if re.fullmatch(r"\d{1,3}(?: \d{3})*(?:,\d\d)?", num):          # French: '45 700,00', '38,85'
        value = float(num.replace(" ", "").replace(",", "."))
    elif euro and re.fullmatch(r"\d{1,3}(?:\.\d{3})+", num):                    # '€100.000'
        value = float(num.replace(".", ""))
    else:
        value = float(re.sub(r"[, ]", "", num))
    if (token["suffix"] or "").lower() == "k" and value < 1000:    # '$190,000K' already counts the thousands
        value *= 1_000
    return value


def _non_pay(text: str) -> list[re.Match]:
    """What the text says the amount is, when not pay; 'excluding bonus' says it isn't one, and 'OTE or base salary'
    that either is."""
    return [m for m in _NON_PAY.finditer(text)
            if not (_EXCLUDING.search(text, max(0, m.start() - 50), m.start())
                    or _OR_PAY_AFTER.match(_PARENS.sub("", text[m.end():m.end() + 60]))
                    or _OR_PAY_BEFORE.search(text, max(0, m.start() - 30), m.start()))]


def _labelled(text: str) -> bool:
    """Whether a pay word leads straight to the end of the text: 'Annual Salary Range: ', 'base hourly rate of '."""
    return any(_LABEL_END.fullmatch(text, c.end()) for c in _PAY_NAMED.finditer(text))


def _joins(text: str, left: re.Match, right: re.Match) -> bool:
    between = text[left.end():right.start()]
    signed = (left["sign"] or left["code"]) and (right["sign"] or right["code"])
    # 'Minimum: $59,800 Maximum: $89,800', 'MIN $164,430.00 MIDPOINT $219,230.00 MAX $274,040.00'
    if (signed and len(between) <= 40 and re.search(r"\bm(?:ax(?:imum)?|id(?:point)?)\b", between, re.I)
            and re.search(r"\bmin(?:imum)?\b", text[max(0, left.start() - 40):left.start()], re.I)):
        return True
    if "\n\n" in between:                       # '...starting 2027\n\nSalary - £50,000' is no range
        return False
    return bool(_JOIN.fullmatch(between) or (signed and not between.strip()))           # '$184,050 $262,928'


def _amounts(text: str) -> list[re.Match]:
    """_AMOUNT's matches, looked for only around the digits: trying it at every letter of a posting is slow."""
    spans = []
    for m in _DIGITS.finditer(text):
        lo, hi = max(0, m.start() - 12), m.end() + 60
        if spans and lo <= spans[-1][1]:
            spans[-1][1] = hi
        else:
            spans.append([lo, hi])
    return [t for lo, hi in spans for t in _AMOUNT.finditer(text, lo, min(hi, len(text)))]


def _expressions(text: str) -> list[dict]:
    """Money amounts in the order they appear, a range's ends joined ('MIN $X -MID $Y - MAX $Z' is X to Z)."""
    tokens = _amounts(text)
    found, i = [], 0
    while i < len(tokens):
        j = i
        if j + 1 < len(tokens) and _joins(text, tokens[j], tokens[j + 1]):
            j += 1
            # A midpoint between the ends: '..., a midpoint of $Y, and a maximum salary of $Z', or three rising
            # figures in a row ('Pay Equity $43,900.00 - $54,900.00 - $65,800.00 of salary range')
            if j + 1 < len(tokens) and (
                    (re.search(r"\bmid(?:point)?\b", text[tokens[i].end():tokens[j].start()], re.I)
                     and (_joins(text, tokens[j], tokens[j + 1])
                          or re.fullmatch(r"[^$\d]{0,40}?\bmax(?:imum)?\b[^$\d]{0,30}",
                                          text[tokens[j].end():tokens[j + 1].start()], re.I)))
                    or (_JOIN.fullmatch(text, tokens[j].end(), tokens[j + 1].start()) and tokens[j + 1]["sign"]
                        and _value(tokens[i], False) < _value(tokens[j], False) < _value(tokens[j + 1], False))):
                j += 1
        first, last = tokens[i], tokens[j]
        ends = tokens[i:j + 1]
        i = j + 1
        signed = any(t["sign"] or t["post"] or t["code"] for t in ends)
        # Without a sign, only amounts written as money ('140,000', '25.50') are kept, for a pay label to claim
        if not signed and not all(re.search(r"[, ]\d{3}|\.\d\d$", t["num"]) for t in ends):
            continue
        euro = any("€" in (t["sign"] or "") + (t["post"] or "") or (t["code"] or "").upper() == "EUR" for t in ends)
        low, high = _value(first, euro), _value(last, euro)
        if first is not last:
            if not first["suffix"] and (last["suffix"] or "").lower() == "k" and low < 1000:
                low *= 1_000                                      # '$90–105k'
            elif not first["suffix"] and not last["suffix"] and high < 1000 <= low:
                high *= 1000                                      # '$90,000 - 105' is never meant; be safe
            elif low < 1000 <= high and "," in first["num"] and low * 1000 <= high:
                low *= 1000                                       # '$108,00 and $154,500': a thousands typo
        found.append({
            "start": first.start(), "end": last.end(), "low": min(low, high), "high": max(low, high),
            "signed": signed,
            "big": any((t["suffix"] or "").lower() in ("m", "mm", "b", "bn") for t in ends),   # '$5m', '$275B': never pay
            "unit": " ".join(t["unit"] for t in ends if t["unit"]),
            "code": next((t["code"].upper() for t in ends if t["code"]), None),
            "text": text[first.start():last.end()],
        })
    return found


def _period(unit: str, tail: str, lead: str, heading: str, low: float, high: float) -> str:
    """The period written by the amount, else the last one written before it on its line, else under its
    heading; checked against the amount's size."""
    period = next((p for where in (unit, tail) for p, pattern in _PERIODS if pattern.search(where)), None)
    if not period and (bare := _BARE_PERIOD.match(tail)):
        period = bare.group(1).lower()
    for where in (lead, heading):
        if period:
            break
        # The last one written; 'Semi-Monthly' is semi-monthly, though 'Monthly' ends there too
        hits = [(m.end(), -order, p) for order, (p, pattern) in enumerate(_PERIODS) for m in pattern.finditer(where)
                if not _SCHEDULE.search(where, max(0, m.start() - 12), m.start())]
        period = max(hits)[2] if hits and low < _MOST[max(hits)[2]] else None
    if period == "hour" and low >= 1000:       # '$104,000 - $166,000 per hour' is a slip for a year
        return "year"
    if period == "year" and high < 300:
        return "hour"
    return period or ("hour" if low < 300 else "month" if high < 20_000 else "year")


def _compensation(expr: dict, period: str, currency: tuple[str, bool], original: str) -> dict:
    low, high = expr["low"], expr["high"]
    if low <= 0:
        return {}
    annual_min, annual_max = round(low * PER_YEAR[period]), round(high * PER_YEAR[period])
    if expr["big"] or annual_max > 2_000_000 or annual_min < 5_000:
        return {"original": original, "unparsed": True}
    code, inferred = currency
    low, high = (int(v) if v == int(v) else v for v in (low, high))
    return {
        "original": original,
        "min": low, "max": high, "currency": code, "currency_inferred": inferred,
        "period": period, "annual_min": annual_min, "annual_max": annual_max,
        "annualized_estimate": period != "year",
        "display": format_comp(low, high, code, period),
        "annual_display": format_comp(annual_min, annual_max, code, "year"),
    }


def parse_compensation(text: str, country_hint: str | None = None) -> dict:
    """Parse a salary string.  Returns {} when nothing numeric is found."""
    original = (text or "").strip()
    plain = _plain(original)
    expressions = [e for e in _expressions(plain) if e["signed"]]
    if not expressions or _OTHER_MONEY.search(plain):
        return {}
    expr = expressions[0]
    period = _period(expr["unit"], plain[expr["end"]:expr["end"] + 25], plain[:expr["start"]], "",
                     expr["low"], expr["high"])
    currency = (expr["code"], False) if expr["code"] else _currency(plain, country_hint)
    return _compensation(expr, period, currency, original)


def comp_from_description(description: str, country_hint: str | None = None) -> dict:
    """Pay-transparency text: 'The base salary range for this role is $110,000 - $125,000'.

    An amount is read as pay when it comes with its unit or currency ('172,400.00 USD annually'), or follows a pay
    word ('Pay Ranges\\nVancouver, Canada: $127,000 - $203,000'); never when its own line or the words right after
    it say it's something else (a stipend, a 401(k) match, revenue)."""
    text = _plain((description or "")[:30000])
    cues = list(_DESC_CUE.finditer(text))
    first = None
    for expr in _expressions(text):
        start, end = expr["start"], expr["end"]
        if first and start - first["end"] > _PREFER_RANGE_WITHIN:
            break
        # Its sentence or line, at most 300 characters back (some sites run a whole posting into one line)
        line_start = max([text.rfind("\n", 0, start) + 1, start - 300,
                          *(m.end() for m in _SENTENCE_END.finditer(text, max(0, start - 300), start))])
        lead = text[line_start:start]
        tail = _TAIL_END.split(text[end:end + 40], maxsplit=1)[0]
        if expr["big"] or _OTHER_MONEY.search(f"{lead[-6:]}{expr['text']}{tail[:6]}"):
            continue
        # A non-pay word just before it rules it out (or on the line above, for a figure on its own line), unless pay
        # is named after that and leads to it ('The OTE includes a base hourly rate of', not 'OTE Salary' or
        # 'life insurance of two times annual salary (up to'), or the words after it call it base pay ('$55,000 base
        # pay - $115,000 OTE'). Asides in brackets don't count: 'Annual base salary range (excluding equity and
        # bonus):'. One right after it rules it out unless a pay label leads straight to it ('Annual Salary Range:
        # $130,000-$170,000 Annual Bonus Target: 20%').
        label = lead
        if not lead.strip():
            above = text[max(0, line_start - 200):line_start].rstrip()
            label = above[above.rfind("\n") + 1:]
            label = label[max([0, *(m.end() for m in _SENTENCE_END.finditer(label))]):]
            if label.endswith((".", "!", "?")):        # a whole sentence above it labels nothing
                label = ""
        label = _PARENS.sub(" ", label[-150:])
        based = re.match(r"\s*\(?base\b", tail, re.I)
        other = _non_pay(label)
        if other and not (_labelled(label[other[-1].end() + 2:]) or based):
            continue
        if _non_pay(tail) and not (_labelled(label) or based):
            continue
        self_cued = bool(expr["unit"] or expr["code"] or any(p.search(tail) for _, p in _PERIODS)
                         or re.match(r"\s*(?:base (?:salary|pay)|salary|pay|wages?)\b", tail, re.I))
        cue = next((c for c in reversed(cues) if c.end() <= start), None)
        heading = ""
        if cue and (start - cue.end() > 300 or text.count("\n\n", cue.end(), start) > 1):
            cue = None
        if cue:
            between = text[cue.end():start]
            # The heading's own sentence, up to the end of its line
            head_start = max([text.rfind("\n", 0, cue.start()) + 1, cue.start() - 120,
                              *(m.end() for m in _SENTENCE_END.finditer(text, max(0, cue.start() - 120), cue.start()))])
            heading = text[head_start:cue.end() + len(between.split("\n", 1)[0])]
            # Past a sentence or a line, only a range or an amount with its unit or currency is read, or one figure
            # under a short heading ('Salary:\n$85,000').
            crossed = "\n" in between or _SENTENCE_END.search(between)
            short_heading = len(heading.strip()) <= 60 and not _SENTENCE_END.search(between)
            labelled = re.fullmatch(r"[^.!?\n]{0,80}:\s*", between)     # '...salary range for this role is:\n\n $70,000'
            if crossed and not (self_cued or expr["low"] != expr["high"] or short_heading or labelled):
                cue = None
        if not cue and not self_cued:
            continue
        # An amount with no currency is pay only right after a pay label ('Salary Range: 120,000.00 - 130,000.00')
        if not expr["signed"] and not (cue and _LABEL_END.fullmatch(text, cue.end(), start)):
            continue
        period = _period(expr["unit"], tail, lead, heading, expr["low"], expr["high"])
        # The currency written by it, else just before it, else just after it
        currency = (expr["code"], False) if expr["code"] else _currency(f"{lead[-80:]}{expr['text']}", country_hint)
        if currency[1]:
            currency = _currency(f"{lead[-80:]}{expr['text']}{tail}", country_hint)
        snippet = re.sub(r"\s+", " ", text[max(line_start, start - 160):end + len(tail)]).strip()
        parsed = _compensation(expr, period, currency, snippet)
        if not parsed or parsed.get("unparsed"):
            continue
        parsed["source"] = "description"
        # A range, or the one figure a pay label gives ('the base salary for this specific position is $40,000'), is
        # the pay; a starting rate or a figure in passing ('the final $2,500 after one year') gives way to either below
        if parsed["min"] != parsed["max"] or (_labelled(label) and not _STARTING.search(label)):
            return parsed
        first = first or dict(parsed, end=end)
    return {k: v for k, v in first.items() if k != "end"} if first else {}


def _money(value: float, symbol: str) -> str:
    if value >= 1000:
        k = value / 1000
        return f"{symbol}{k:.1f}k".replace(".0k", "k")
    return f"{symbol}{value:,.0f}" if value == int(value) else f"{symbol}{value:,.2f}"


def format_comp(low: float, high: float, currency: str, period: str) -> str:
    symbol = {"GBP": "£", "EUR": "€"}.get(currency, "$")
    prefix = f"{currency} " if currency in ("CAD", "USD") else ""
    suffix = {"hour": "/hour", "week": "/week", "semimonth": " semi-monthly", "month": "/month", "year": ""}[period]
    if low == high:
        return f"{prefix}{_money(low, symbol)}{suffix}"
    return f"{prefix}{_money(low, symbol)}–{_money(high, symbol)}{suffix}"
