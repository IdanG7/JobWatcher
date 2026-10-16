"""Loads and compiles the data-driven intelligence configuration.

Everything finance-specific (taxonomy, employers, skills, geography) lives in
``config/*.json`` so it can be extended without touching code.  This module
compiles those files once and caches the result per directory + mtime.
"""

from __future__ import annotations

import functools
import json
import re
import threading
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
FILES = ("taxonomy.json", "companies.json", "skills.json", "locations.json")

_SEP = r"[\s\-/]"


def fragment(pattern: str) -> str:
    """Expand the human-friendly fragment syntax used in config files.

    ``' ?'`` becomes an optional separator, ``' '`` one or more separators
    (space, hyphen, slash) and the whole fragment is wrapped in alphanumeric
    word boundaries, so ``'sales (and|&) trading'`` needs no escaping.
    """
    body = pattern.replace(" ?", _SEP + "*").replace(" ", _SEP + "+")
    return rf"(?<![a-z0-9])(?:{body})(?![a-z0-9])"


_META = set("()[]{}|?*+\\.^$ ")


def _split_top(pattern: str) -> list[str]:
    """Split on '|' that is not inside parentheses or a character class."""
    parts, depth, start, in_class = [], 0, 0, False
    for i, ch in enumerate(pattern):
        if ch == "[":
            in_class = True
        elif ch == "]":
            in_class = False
        elif not in_class and ch == "(":
            depth += 1
        elif not in_class and ch == ")":
            depth -= 1
        elif not in_class and ch == "|" and depth == 0:
            parts.append(pattern[start:i])
            start = i + 1
    return parts + [pattern[start:]]


def required_literal(pattern: str) -> str | None:
    """The longest lowercase word every match of this config fragment contains.

    Only plain text outside parentheses counts; a character made optional by
    ? * or { is dropped. Longer words are rarer, so the check skips more often.
    """
    runs, current, depth, i = [], "", 0, 0
    while i < len(pattern):
        ch = pattern[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        elif depth == 0 and ch == "\\":
            i += 1                       # escaped character: not plain text
        elif depth == 0 and ch == "[":
            i = pattern.find("]", i)
            if i < 0:
                break
        elif depth == 0 and ch not in _META:
            current += ch
            i += 1
            continue
        if depth == 0 and ch in "?*{" and current:
            current = current[:-1]       # its last character is optional
        if current:
            runs.append(current)
        current = ""
        i += 1
    if current:
        runs.append(current)
    runs = [r.lower() for r in runs if len(r) >= 2 and r.isascii()]
    return max(runs, key=len) if runs else None


def prematchers(patterns) -> tuple[str, ...] | None:
    """Strings of which at least one appears in any text the patterns match.

    None means "no cheap test is possible": always run the regex.
    """
    literals = []
    for pattern in patterns:
        for alternative in _split_top(pattern):
            literal = required_literal(alternative)
            if literal is None:
                return None
            literals.append(literal)
    return tuple(dict.fromkeys(literals)) or None


@functools.lru_cache(maxsize=32)
def _lower(text: str) -> str:
    return text.lower()


class Prefiltered:
    """A compiled pattern that skips the regex when a required word is absent.

    Most of the ~650 taxonomy and skill patterns never occur in a given posting.
    A substring test ('in' on the lowercased text) is far cheaper than a
    case-insensitive regex scan that starts with a lookbehind, which defeats
    the regex engine's own literal-prefix search. Results are identical: the
    regex still decides every match it is allowed to run on.
    """
    __slots__ = ("regex", "literals")

    def __init__(self, regex: re.Pattern, literals: tuple[str, ...] | None):
        self.regex = regex
        self.literals = literals

    def _possible(self, text: str) -> bool:
        if self.literals is None:
            return True
        low = _lower(text)
        return any(literal in low for literal in self.literals)

    def search(self, text, *args):
        return self.regex.search(text, *args) if self._possible(text) else None

    def finditer(self, text, *args):
        return self.regex.finditer(text, *args) if self._possible(text) else iter(())

    def findall(self, text, *args):
        return self.regex.findall(text, *args) if self._possible(text) else []

    def __getattr__(self, name):
        return getattr(self.regex, name)


def compile_fragments(patterns) -> list[Prefiltered]:
    return [Prefiltered(re.compile(fragment(p), re.I), prematchers([p])) for p in (patterns or [])]


def compile_union(patterns) -> Prefiltered | None:
    patterns = [p for p in (patterns or []) if p]
    if not patterns:
        return None
    return Prefiltered(re.compile("|".join(fragment(p) for p in patterns), re.I), prematchers(patterns))


@dataclass
class Node:
    key: str
    label: str
    parent: str | None
    title: list[re.Pattern] = field(default_factory=list)
    department: list[re.Pattern] = field(default_factory=list)
    description: list[re.Pattern] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    domain: list[re.Pattern] = field(default_factory=list)


@dataclass
class Company:
    key: str
    name: str
    type: str
    country: str = ""
    hq: str = ""
    aliases: tuple[str, ...] = ()


@dataclass
class Skill:
    key: str
    label: str
    group: str
    pattern: re.Pattern


class Knowledge:
    """Compiled view of config/*.json.  Treat instances as immutable."""

    def __init__(self, config_dir: Path | str = CONFIG_DIR):
        self.config_dir = Path(config_dir)
        raw = {name: self._read(name) for name in FILES}
        self.raw = raw
        self._load_taxonomy(raw["taxonomy.json"])
        self._load_companies(raw["companies.json"])
        self._load_skills(raw["skills.json"])
        self._load_locations(raw["locations.json"])

    def _read(self, name: str) -> dict:
        path = self.config_dir / name
        return json.loads(path.read_text(encoding="utf-8"))

    # ------------------------------------------------------------ taxonomy
    def _load_taxonomy(self, data: dict) -> None:
        self.weights = {"title": 4, "department": 2, "description": 1,
                        "description_cap": 4, "min_finance_score": 3,
                        **data.get("weights", {})}
        self.generic_finance_title = re.compile(
            fragment(data.get("generic_finance_title", "analyst|associate")), re.I)
        self.categories: dict[str, Node] = {}
        self.subcategories: dict[str, Node] = {}
        for key, cat in data.get("categories", {}).items():
            meta = {k: v for k, v in cat.items()
                    if k not in ("title", "department", "description", "subcategories")}
            self.categories[key] = Node(
                key, cat["label"], None,
                compile_fragments(cat.get("title")),
                compile_fragments(cat.get("department")),
                compile_fragments(cat.get("description")), meta)
            for sub_key, sub in (cat.get("subcategories") or {}).items():
                full = f"{key}.{sub_key}"
                self.subcategories[full] = Node(
                    sub_key, sub["label"], key,
                    compile_fragments(sub.get("title")),
                    compile_fragments(sub.get("department")),
                    compile_fragments(sub.get("description")),
                    {k: v for k, v in sub.items()
                     if k not in ("title", "department", "description")})
        self.company_priors: dict[str, dict[str, float]] = data.get("company_priors", {})
        self.tech_at_trading_firm = data.get("tech_at_trading_firm", {})
        self.families: dict[str, Node] = {}
        for key, fam in data.get("non_finance_families", {}).items():
            if key.startswith("_"):
                continue
            self.families[key] = Node(key, fam["label"], None,
                                      compile_fragments(fam.get("title")),
                                      domain=compile_fragments(fam.get("domain_title")))

    def category_label(self, key: str | None) -> str:
        if not key:
            return ""
        if key in self.categories:
            return self.categories[key].label
        if key in self.families:
            return self.families[key].label
        return "Other" if key == "other" else key.replace("_", " ").title()

    def subcategory_label(self, category: str | None, sub: str | None) -> str:
        if not category or not sub:
            return ""
        node = self.subcategories.get(f"{category}.{sub}")
        return node.label if node else sub.replace("_", " ").title()

    def taxonomy_tree(self) -> list[dict]:
        tree = []
        for key, node in self.categories.items():
            subs = [{"key": n.key, "label": n.label}
                    for full, n in self.subcategories.items() if n.parent == key]
            tree.append({"key": key, "label": node.label,
                         "short": node.meta.get("short", node.label),
                         "competitive": bool(node.meta.get("competitive")),
                         "subcategories": subs})
        return tree

    def family_tree(self) -> list[dict]:
        """Job families outside finance, in the shape of taxonomy_tree (they have no groups)."""
        return [{"key": key, "label": node.label, "subcategories": []} for key, node in self.families.items()]

    # ------------------------------------------------------------ companies
    def _load_companies(self, data: dict) -> None:
        self.company_types: dict[str, dict] = data.get("types", {})
        self.companies: dict[str, Company] = {}
        self._alias_exact: dict[str, str] = {}
        word_aliases: list[tuple[str, str]] = []
        for entry in data.get("companies", []):
            ctype = entry.get("type", "unknown")
            if ctype not in self.company_types:
                raise ValueError(f"company {entry.get('key')}: unknown type {ctype}")
            aliases = []
            # An '=' alias keeps the display name exact-only too: '=gemini'
            # must not let "Gemini" match "Google Gemini Team".
            exact = {normalize_company(a[1:]) for a in entry.get("aliases", []) if a.startswith("=")}
            for alias in entry.get("aliases", []) + [entry["name"]]:
                norm = normalize_company(alias.lstrip("="))
                exact_only = alias.startswith("=") or norm in exact
                if not norm:
                    continue
                aliases.append(norm)
                self._alias_exact.setdefault(norm, entry["key"])
                if not exact_only:
                    word_aliases.append((norm, entry["key"]))
            self.companies[entry["key"]] = Company(
                entry["key"], entry["name"], ctype, entry.get("country", ""),
                entry.get("hq", ""), tuple(aliases))
        word_aliases.sort(key=lambda kv: -len(kv[0]))
        self._alias_words = [(re.compile(rf"(?<![a-z0-9]){re.escape(a)}(?![a-z0-9])"), key)
                             for a, key in word_aliases
                             if len(a) >= 3 and a not in _GENERIC_ALIASES]

    def match_company(self, name: str) -> Company | None:
        norm = normalize_company(name)
        if not norm:
            return None
        key = self._alias_exact.get(norm)
        if key:
            return self.companies[key]
        for pattern, key in self._alias_words:
            if pattern.search(norm):
                return self.companies[key]
        return None

    def type_label(self, ctype: str | None) -> str:
        return (self.company_types.get(ctype or "unknown") or {}).get("label", "Unclassified")

    # ------------------------------------------------------------ skills
    def _load_skills(self, data: dict) -> None:
        self.skill_groups: dict[str, str] = data.get("groups", {})
        self.skills: list[Skill] = []
        for entry in data.get("skills", []):
            # Synonyms are regex fragments; display labels are literal text.
            label = re.escape(entry["label"]).replace(r"\ ", " ")
            pattern = compile_union(entry.get("synonyms", []) + [label])
            self.skills.append(Skill(entry["key"], entry["label"],
                                     entry.get("group", "other"), pattern))
        self.skill_by_key = {s.key: s for s in self.skills}

    # ------------------------------------------------------------ geography
    def _load_locations(self, data: dict) -> None:
        self.countries = data.get("countries", {})
        self.cities = []
        for entry in data.get("cities", []):
            self.cities.append({
                **entry,
                "pattern": compile_union(entry.get("aliases", [])),
                "not": compile_union(entry.get("not", [])),
            })
        self.city_by_key = {c["key"]: c for c in self.cities}
        self.country_patterns = {
            code: compile_union(info.get("aliases", []))
            for code, info in self.countries.items()
        }
        self.region_names = {
            code: compile_union(list(info.get("regions", {}).values()))
            for code, info in self.countries.items()
        }
        self.region_codes = {
            code: set(info.get("regions", {}).keys())
            for code, info in self.countries.items()
        }


_COMPANY_NOISE = re.compile(
    r"\((?:[^)]*)\)|\b(incorporated|corporation|inc|llc|l\.l\.c|ltd|limited|corp|co|plc|lp|llp|na|n\.a)\b\.?",
    re.I)
# Generic words must never identify an employer on their own ("Capital").
_GENERIC_ALIASES = {"capital", "partners", "group", "financial", "bank", "trading",
                    "investments", "management", "global", "securities", "company",
                    "holdings", "advisors", "markets"}


def normalize_company(name: str) -> str:
    """'Goldman Sachs & Co. LLC' -> 'goldman sachs'; keeps '&' as 'and'-free text."""
    text = (name or "").lower().replace("&", " & ")
    text = _COMPANY_NOISE.sub(" ", text)
    text = re.sub(r"[^a-z0-9&+ ]+", " ", text)
    text = re.sub(r"\s+&\s+$", "", text)
    return re.sub(r"\s+", " ", text).strip(" &")


_CACHE: dict[str, tuple[tuple, Knowledge]] = {}
_LOCK = threading.Lock()


def load_knowledge(config_dir: Path | str = CONFIG_DIR) -> Knowledge:
    """Return a cached Knowledge, recompiled whenever a config file changes."""
    root = Path(config_dir)
    stamp = tuple((root / name).stat().st_mtime_ns for name in FILES)
    key = str(root.resolve())
    with _LOCK:
        cached = _CACHE.get(key)
        if cached and cached[0] == stamp:
            return cached[1]
        kn = Knowledge(root)
        _CACHE[key] = (stamp, kn)
        return kn


def config_fingerprint(config_dir: Path | str = CONFIG_DIR) -> str:
    """Changes whenever classification inputs change (used to re-run facts)."""
    import hashlib
    root = Path(config_dir)
    digest = hashlib.sha1()
    for name in FILES:
        digest.update((root / name).read_bytes())
    return digest.hexdigest()[:12]
