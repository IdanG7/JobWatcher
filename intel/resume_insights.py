"""What a resume says about the roles a candidate should be ranked for.

Past job *titles* alone are a poor guide: a student's titles are generic
("Student Financial Analyst") while the work behind them is specific
(DCF models, post-merger valuation, treasury funding). This module reads the
whole resume -- titles, bullets, coursework and certifications -- and turns
it into graded role interests, a recruiting plan from the graduation date,
and employer types. Every interest keeps the phrases that produced it, so
the dashboard can explain each suggestion. Nothing here guesses facts the
resume does not contain.
"""

from __future__ import annotations

import re
from datetime import date

from .knowledge import Knowledge
from .sources import TECH_FIELDS
from .taxonomy import classify

# (target role, weight, evidence pattern). Each distinct phrase counts once
# per resume block, so repeating a word does not inflate a role.
SIGNALS: list[tuple[str, float, re.Pattern]] = [(key, weight, re.compile(pattern, re.I)) for key, weight, pattern in [
    ("investment_banking.ma", 2.0, r"\bm&a\b|mergers?\b|acquisitions?\b|post-merger|due diligence|enterprise value|"
                                   r"pitch ?books?|precedent transactions?|comparable compan\w+|trading comps|accretion"),
    ("investment_banking.ma", 1.5, r"\bdcf\b|discounted cash flow|\bwacc\b|valuations?\b|terminal (?:growth|value)|"
                                   r"\blbo\b|leveraged buy ?outs?|sensitivity analysis"),
    ("investment_banking.dcm", 1.0, r"debt capital markets|bond issuance|fixed income"),
    ("investment_banking.ecm", 1.0, r"equity capital markets|\bipos?\b"),
    ("corporate_finance.corporate_development", 1.5, r"post-merger|due diligence|valuations?\b|capital (?:allocation|investment)|"
                                                     r"investment projects?|\bnpv\b|\birr\b|integration"),
    ("corporate_finance.strategic_finance", 1.0, r"strategic (?:budgeting|planning|finance)|business cases?|capital investment"),
    ("private_markets.private_equity", 1.0, r"\blbo\b|leveraged buy ?outs?|portfolio compan\w+|private equity|value creation|due diligence"),
    ("private_markets.real_estate", 2.0, r"real estate|\breits?\b|propert(?:y|ies)\b|\bnoi\b|cap rates?"),
    ("private_markets.infrastructure", 1.0, r"infrastructure"),
    ("public_markets.equity_research", 1.5, r"equity research|stock pitch\w*|investment thes[ie]s|\bcfa\b|"
                                            r"financial statement analysis|investments? (?:club|fund)"),
    ("public_markets.asset_management", 1.5, r"\bcfa\b|portfolios?\b|asset management|\binvestments\b|capital market theory|"
                                             r"pension|fund\b"),
    ("markets.fixed_income", 1.5, r"fixed income|\bbonds?\b|yield curves?|\bduration\b|credit spreads?"),
    ("markets.derivatives", 1.5, r"\boptions\b|greeks|derivatives?|futures|\bswaps?\b|volatility"),
    ("markets.sales_trading", 1.2, r"trading|macro\b|market making|sales (?:&|and) trading|financial markets"),
    ("corporate_finance.treasury", 2.0, r"treasury|liquidity|cash (?:positioning|management|forecast\w*)|funding|"
                                        r"wire transfers?|kyriba|banking relationships?"),
    ("corporate_finance.fpa", 2.0, r"fp&a|budget\w*|forecast\w*|variance|capex|management reporting|"
                                   r"financial planning|monthly reports?"),
    ("corporate_finance.accounting", 1.0, r"accounting|accounts payable|\bap\b|journal entr\w+|reconciliations?|general ledger|"
                                          r"\bg/l\b|invoices?|period-end close|month-end close|\bifrs\b|\bgaap\b"),
    ("banking.credit", 1.5, r"credit (?:analysis|memo|risk)|underwrit\w+|lending|\bloans?\b|covenants?"),
    ("risk.market_risk", 1.0, r"\bvar\b|value at risk|stress test\w*|liquidity risk|risk oversight"),
    ("quant.quant_research", 1.5, r"\bpython\b|stochastic|machine learning|statistical model\w*|\bc\+\+|backtest\w*"),
    ("wealth.wealth_management", 1.5, r"wealth|financial advis\w+|client portfolios|private client"),
]]
# A tech resume (see tech_resume) is also read for the Software, AI & Data and
# Hardware specialties. There Python, C++ and machine learning are everyday
# software work, so only quantitative-finance terms point at quant research.
# A finance resume is read with SIGNALS above, unchanged.
_QUANT_TERMS = re.compile(r"stochastic|backtest\w*|quantitative (?:finance|research|trading)|alpha (?:research|signals?)|"
                          r"statistical arbitrage|market microstructure", re.I)
TECH_FINANCE_SIGNALS = [(key, weight, _QUANT_TERMS if key == "quant.quant_research" else pattern)
                        for key, weight, pattern in SIGNALS]
# What the work says it built, by specialty.
TECH_SIGNALS: list[tuple[str, float, re.Pattern]] = [(key, weight, re.compile(pattern, re.I)) for key, weight, pattern in [
    ("software.frontend", 1.5, r"\breact\b|angular|\bvue\b|front-?end|\bcss\b|\bhtml\b|user interfaces?|next\.js|typescript|"
                               r"web (?:apps?|ui|pages?)"),
    ("software.backend", 1.5, r"back-?end|\b(?:rest(?:ful)?|graphql|grpc) apis?\b|\bapis?\b|microservices?|server-?side|"
                              r"database schemas?|postgres\w*|mysql|redis|django|flask|fastapi|spring boot|node\.js|express\.js"),
    ("software.full_stack", 1.5, r"full-?stack|\bmern\b|end-to-end web"),
    ("software.mobile", 1.5, r"\bios\b|android|swift(?:ui)?\b|kotlin|react native|flutter|mobile apps?"),
    ("software.infrastructure", 1.5, r"kubernetes|\bk8s\b|\bdocker\b|terraform|\baws\b|\bgcp\b|\bazure\b|ci/cd|\bci\b|devops|"
                                     r"\bsre\b|site reliability|cloud infrastructure|observability|opentelemetry|"
                                     r"deployment pipelines?|github actions|jenkins"),
    ("software.systems", 1.5, r"distributed (?:systems?|platforms?)|operating systems?|\bkernel\b|compilers?|concurren\w+|"
                              r"multi-?thread\w*|systems programming|high-performance"),
    ("software.security", 1.5, r"cyber ?security|(?:application|network|cloud) security|security (?:engineering|research|audits?)|"
                               r"penetration test\w*|vulnerabilit\w+|cryptograph\w+|\bctf\b|threat model\w*|malware|"
                               r"reverse engineering"),
    ("software.game_dev", 1.5, r"game (?:engines?|dev\w*)|\bunity\b|unreal|gameplay|graphics programming|opengl|vulkan|"
                               r"directx|shaders?"),
    ("software.quant_dev", 1.5, r"low-?latency trading|trading (?:systems?|engines?|infrastructure)|order (?:books?|matching)|"
                                r"market data (?:feeds?|handlers?)|\bfix protocol\b"),
    ("software.qa_test", 1.2, r"test automation|selenium|cypress|quality assurance|\bqa\b|test (?:cases|plans|suites|frameworks?)"),
    ("data_ml.ml_engineering", 1.5, r"machine learning|deep learning|pytorch|tensorflow|\bllms?\b|\bnlp\b|computer vision|"
                                    r"neural networks?|mlops|model (?:training|deployment|serving|inference)|fine-?tun\w+|"
                                    r"\brag\b|reinforcement learning"),
    ("data_ml.ai_research", 1.5, r"publications?|published (?:at|in)|arxiv|neurips|\bicml\b|\biclr\b|\bcvpr\b|"
                                 r"research (?:paper|assistant)|co-?authored"),
    ("data_ml.data_science", 1.5, r"data science|predictive models?|regression models?|a/b test\w*|hypothesis test\w*|"
                                  r"scikit-learn|statistical model\w*|experimentation|feature engineering"),
    ("data_ml.data_engineering", 1.5, r"\betl\b|data pipelines?|\bspark\b|airflow|kafka|data warehouse\w*|snowflake|\bdbt\b|"
                                      r"bigquery|hadoop|data lakes?"),
    # Finance students build budgets in Excel and Power BI too; these name analytics work itself.
    ("data_ml.analytics", 1.2, r"tableau|looker|business intelligence|(?:data|product|marketing) analytics|analytics dashboards?"),
    ("hardware.embedded_firmware", 1.5, r"embedded|firmware|micro-?controllers?|\bmcus?\b|\brtos\b|bare-?metal|device drivers?|"
                                        r"stm32|arduino|esp32|\buart\b|\bi2c\b|\bspi\b|can bus|bootloaders?"),
    ("hardware.chip_design", 1.5, r"\bfpgas?\b|\basics?\b|\brtl\b|verilog|\bvhdl\b|\buvm\b|design verification|tape-?out|"
                                  r"physical design"),
    ("hardware.electrical", 1.5, r"circuit (?:design|boards?|analysis)|\bpcbs?\b|schematics?|altium|kicad|\bspice\b|analog|"
                                 r"power electronics|oscilloscopes?|soldering|signal integrity"),
    ("hardware.robotics_autonomy", 1.5, r"robot\w*|\bros2?\b|motion planning|\bslam\b|perception|autonomous|sensor fusion|"
                                        r"kalman|\bpid\b|control loops?|mujoco|gazebo|kinematics|actuators?"),
]]
_TECH_DEGREE = re.compile(r"computer science|computing|software|computer engineering|electrical|data science|"
                          r"artificial intelligence|machine learning|mechatronics|robotics|information technology", re.I)
# Book-keeping tasks appear in almost every finance student's resume, so they
# count for less unless the candidate actually held an accounting title.
TASK_DISCOUNT = {"corporate_finance.accounting": 0.4}
# Most recent role first; resumes list experience in reverse order.
RECENCY = (1.0, 0.8, 0.65, 0.55, 0.45)
BLOCK_WEIGHT = {"experience": 1.0, "leadership": 0.5, "projects": 0.7, "education": 0.8}
TITLE_POINTS = 4.0
COMPANY_TYPES = {
    "investment_banking": ["bulge_bracket", "elite_boutique", "middle_market_bank", "canadian_bank"],
    "private_markets": ["private_equity", "pension_fund", "asset_manager"],
    "public_markets": ["asset_manager", "pension_fund", "hedge_fund"],
    "markets": ["bulge_bracket", "canadian_bank", "global_bank"],
    "banking": ["canadian_bank", "commercial_bank"],
    "corporate_finance": ["corporate", "pension_fund"],
    "quant": ["quant_firm", "hedge_fund"],
    "wealth": ["canadian_bank", "asset_manager"],
    "risk": ["canadian_bank", "global_bank"],
    # Tech targets: a specialty's own employers first, else its family's.
    "software": ["big_tech", "high_growth_startup", "enterprise_saas", "developer_tools", "consumer_tech"],
    "software.infrastructure": ["developer_tools", "data_infrastructure", "big_tech", "ai_infrastructure"],
    "software.security": ["cybersecurity", "big_tech", "defense_tech"],
    "software.game_dev": ["gaming", "big_tech"],
    "software.quant_dev": ["quant_firm", "hedge_fund", "fintech"],
    "data_ml": ["ai_lab", "ai_infrastructure", "big_tech", "data_infrastructure", "high_growth_startup"],
    "data_ml.ai_research": ["ai_lab", "research_lab", "big_tech"],
    "hardware": ["semiconductors", "hardware_devices", "big_tech", "robotics_autonomy", "defense_tech"],
    "hardware.embedded_firmware": ["semiconductors", "hardware_devices", "robotics_autonomy"],
    "hardware.chip_design": ["semiconductors", "big_tech"],
    "hardware.robotics_autonomy": ["robotics_autonomy", "defense_tech", "hardware_devices"],
    "product": ["big_tech", "consumer_tech", "enterprise_saas", "high_growth_startup"],
    "design": ["big_tech", "consumer_tech", "enterprise_saas", "high_growth_startup"],
}
_STUDENT_ROLE = re.compile(r"\b(?:intern(?:ship)?|co-?op|student|summer (?:analyst|associate)|placement|work term)\b", re.I)
_BULLET = re.compile(r"^\s*(?:[•●▪◦\-–*·]|\d+\.)\s*")
_MON = r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
# Resume dates: "May 2025 – Aug 2025", "May – Aug 2026", "05/2026 – 08/2026",
# "Summer 2025", or a role line ending in a bare "2025" / "Aug 2025".
_RANGE = re.compile(
    rf"(?:(?:{_MON}\.?\s*|\b\d{{1,2}}\s*/\s*)(?:20\d\d)?|\b20\d\d)\s*(?:-|–|—|to)\s*"
    rf"(?:(?P<end_month>{_MON})\.?\s*|(?P<end_num>\d{{1,2}})\s*/\s*)?(?P<end>20\d\d|present|current|now)\b"
    rf"|\b(?P<season>summer|fall|autumn|winter|spring)\s+(?P<season_year>20\d\d)\b"
    rf"|(?:(?P<one_month>{_MON})\.?\s+|\b(?P<one_num>\d{{1,2}})\s*/\s*)?\b(?P<one>20\d\d)\s*\)?\s*$", re.I)
_MONTH_NUMBERS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def span_end(m: re.Match) -> tuple[int | None, int | None]:
    """(end year, end month) of a _RANGE match; an ongoing role ends this year."""
    if m.group("end"):
        year = int(m.group("end")) if m.group("end").isdigit() else date.today().year
        month_text, number = m.group("end_month"), m.group("end_num")
    elif m.group("season_year"):
        season = m.group("season").lower()
        return int(m.group("season_year")), {"winter": 4, "spring": 4, "summer": 8, "fall": 12, "autumn": 12}[season]
    else:
        year, month_text, number = int(m.group("one")), m.group("one_month"), m.group("one_num")
    month = _MONTH_NUMBERS.get(month_text[:3].lower()) if month_text else (
        int(number) if number and 1 <= int(number) <= 12 else None)
    return year, month


def without_dates(line: str, m: re.Match) -> str:
    """The role text around a date: before it, or after it when the date leads."""
    before, after = line[:m.start()].strip(" ,|–—-()"), line[m.end():].strip(" ,|–—-()")
    return before or after
_SEASON_START = {"winter": 1, "summer": 5, "fall": 9}
# "Toronto, ON" / "New York, NY": one word, or two when the first is a city prefix.
_CITY_SUFFIX = re.compile(r"\s+(?:(?:New|San|Los|Las|Salt|St\.?|Saint|Fort|Grand|Thunder|Niagara)\s)?"
                          r"[A-Z][a-z.'-]+,\s*[A-Z]{2}$")
TITLE_SIGNAL_FACTOR = 2.0      # words in a job title say more than words in a bullet
COMPANY_SIGNAL_FACTOR = 0.5    # the employer's business ("Properties", "Capital") is weaker evidence


def strip_city(text: str) -> str:
    return _CITY_SUFFIX.sub("", text).strip()


def experience_entries(sections: dict[str, list[str]]) -> list[dict]:
    """Group resume lines into roles: company, title, dates and their bullets.

    A line with a date range is a role; the plain line before it names the
    employer; bullet lines (and their wrapped continuations) belong to it.
    """
    entries: list[dict] = []
    for block in ("experience", "leadership", "projects"):
        company = ""
        current = None
        for raw in sections.get(block, []):
            line = raw.strip()
            if not line:
                continue
            if _BULLET.match(raw):
                if current is None:
                    current = {"block": block, "company": company, "title": "", "end": None, "bullets": []}
                    entries.append(current)
                current["bullets"].append(_BULLET.sub("", line).strip())
                continue
            dates = _RANGE.search(line)
            if dates:
                current = {"block": block, "company": company, "title": without_dates(line, dates),
                           "end": span_end(dates)[0], "bullets": []}
                entries.append(current)
                continue
            if current and current["bullets"] and not current["bullets"][-1].endswith((".", "!", "?")):
                current["bullets"][-1] += " " + line          # wrapped bullet text
            else:
                company = strip_city(line)        # drop a trailing "Toronto, ON"
                current = None
    return entries


def _tech_title(cls: dict) -> bool:
    return not cls["is_finance"] and cls.get("family") in TECH_FIELDS and cls["confidence"] >= 0.45


def tech_resume(entries: list[dict], education: dict, kn: Knowledge) -> bool:
    """Whether to read the resume for tech roles too: a tech job or project title, or a tech degree."""
    degree = " ".join(education.get(k) or "" for k in ("program", "degree_text"))
    return bool(_TECH_DEGREE.search(degree)) or any(
        e["title"] and e["block"] in ("experience", "projects") and _tech_title(classify(e["title"], kn))
        for e in entries)


def _hits(text: str, signals=SIGNALS) -> dict[str, tuple[float, list[str]]]:
    found: dict[str, tuple[float, list[str]]] = {}
    for key, weight, pattern in signals:
        phrases = list(dict.fromkeys(m.group(0).lower() for m in pattern.finditer(text)))
        if phrases:
            points, evidence = found.get(key, (0.0, []))
            found[key] = (points + weight * min(len(phrases), 3), evidence + phrases)
    return found


def role_interests(entries: list[dict], education_text: str, kn: Knowledge, tech: bool = False) -> list[dict]:
    """Graded role targets with the evidence behind each; ``tech`` (see tech_resume) adds tech roles."""
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}
    titled: set[str] = set()

    def add(key, points, why):
        scores[key] = scores.get(key, 0.0) + points
        evidence.setdefault(key, [])
        for w in why:
            if w not in evidence[key]:
                evidence[key].append(w)

    finance = TECH_FINANCE_SIGNALS if tech else SIGNALS
    default_signals = finance + TECH_SIGNALS if tech else SIGNALS
    work = [e for e in entries if e["block"] == "experience"]
    for entry in entries:
        rank = work.index(entry) if entry in work else 2
        weight = BLOCK_WEIGHT.get(entry["block"], 0.5) * RECENCY[min(rank, len(RECENCY) - 1)]
        signals = default_signals
        if entry["title"]:
            cls = classify(entry["title"], kn)
            sub = cls.get("subcategory")
            if cls["is_finance"] and sub and cls["confidence"] >= 0.45:
                key = f"{cls['category']}.{sub}"
                titled.add(key)
                add(key, TITLE_POINTS * weight, [f"title: {entry['title']}"])
            elif tech and _tech_title(cls):
                # A tech title counts at its specialty, or at the whole family when it names
                # none ("Software Engineer").
                key = f"{cls['category']}.{sub}" if sub else cls["category"]
                titled.add(key)
                add(key, TITLE_POINTS * weight, [f"title: {entry['title']}"])
            if tech and cls["confidence"] >= 0.45 and (cls["is_finance"] or _tech_title(cls)):
                # A finance job's work counts for finance roles, a tech job's for tech roles:
                # "integration tests" and "trading infrastructure" mean different things there.
                signals = finance if cls["is_finance"] else TECH_SIGNALS
        for key, (points, phrases) in _hits(entry["title"], signals).items():
            add(key, points * weight * TITLE_SIGNAL_FACTOR, [f"title: {p}" for p in phrases])
        for key, (points, phrases) in _hits(entry["company"], signals).items():
            add(key, points * weight * COMPANY_SIGNAL_FACTOR, [f"employer: {p}" for p in phrases])
        for key, (points, phrases) in _hits(" ".join(entry["bullets"]), signals).items():
            add(key, points * weight, phrases)
    for key, (points, phrases) in _hits(education_text, default_signals).items():
        add(key, points * BLOCK_WEIGHT["education"], phrases)
    for key, factor in TASK_DISCOUNT.items():
        if key in scores and key not in titled:
            scores[key] *= factor
    valid = {f"{s.parent}.{s.key}" for s in kn.subcategories.values()}
    if tech:
        # A generic title targets the whole family. Work that shows specialties at least as
        # strongly adds them, and the family stays when a job title named it ("Software
        # Developer"); a weaker specialty gives way to the family.
        for family in [k for k in scores if k in TECH_FIELDS]:
            specialties = [k for k in scores if k.startswith(f"{family}.")]
            if specialties and max(scores[k] for k in specialties) >= scores[family]:
                if family not in titled:
                    del scores[family]
            else:
                for key in specialties:
                    del scores[key]
        valid |= TECH_FIELDS & set(kn.families)
    ranked = sorted(((k, v) for k, v in scores.items() if k in valid and v > 0), key=lambda kv: -kv[1])
    if not ranked:
        return []
    top = ranked[0][1]
    out = []
    for key, value in ranked:
        strength = value / top
        if strength < 0.3:
            break
        category, _, sub = key.partition(".")
        label = kn.category_label(category) + (f" · {kn.subcategory_label(category, sub) or sub}" if sub else "")
        out.append({"key": key, "label": label, "strength": round(strength, 2), "evidence": evidence[key][:5]})
    return out[:8]


def career_plan(graduation_year: int | None, graduation_month: int | None, today: date | None = None) -> dict:
    """Stages and recruiting cycles that make sense for the graduation date."""
    today = today or date.today()
    if not graduation_year:
        return {}
    grad = date(graduation_year, graduation_month or 5, 1)
    months = (grad.year - today.year) * 12 + grad.month - today.month
    cycles: list[str] = []
    if months > 0:
        # internship terms that start after today and before graduation
        for year in range(today.year, graduation_year + 1):
            for season, month in _SEASON_START.items():
                start = date(year, month, 1)
                if today < start < grad:
                    cycles.append(f"{season}_{year}")
        cycles += sorted({f"off_cycle_{int(c.rsplit('_', 1)[1])}" for c in cycles})
    if months <= 13:
        stages = ["internship", "new_grad", "entry"] if months > 0 else ["new_grad", "entry"]
        cycles.append(f"new_grad_{graduation_year}")
        note = ("Final year: new-grad and entry-level programs, plus any remaining internships"
                if months > 0 else "Graduated: new-grad and entry-level roles")
    elif months <= 24:
        # Penultimate year: internships now; a few banks already post graduate
        # programs for the graduation year, so those stay in (that year only).
        stages = ["internship", "new_grad"]
        cycles.append(f"new_grad_{graduation_year}")
        note = (f"Graduating {grad:%b %Y}: internships and co-op terms, plus {graduation_year} "
                "graduate programs that open early")
    else:
        stages = ["internship"]
        note = f"Graduating {grad:%b %Y}: internships and co-op terms"
    return {"stages": stages, "cycles": list(dict.fromkeys(cycles)), "note": note, "months_to_graduation": months}


def company_types(interests: list[dict]) -> list[str]:
    types: list[str] = []
    for interest in interests[:5]:
        key = interest["key"]
        for t in COMPANY_TYPES.get(key) or COMPANY_TYPES.get(key.split(".")[0], []):
            if t not in types:
                types.append(t)
    return types[:7]


def student_roles(entries: list[dict]) -> int:
    return sum(1 for e in entries if e["block"] == "experience" and _STUDENT_ROLE.search(e["title"]))
