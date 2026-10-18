"""A job description read from a posting's own web page.

Most career sites publish the posting as schema.org JobPosting data, as JSON-LD
(Bank of America, Radancy, iCIMS, Ashby, Phenom) or as microdata
(SuccessFactors).  Pages without it fall back to their main text: the block
with the most paragraph text once navigation, headers, footers and scripts are
dropped.  Standard library only.
"""

from __future__ import annotations

import html
import json
import re
from html.parser import HTMLParser

_JSON_LD = re.compile(r"<script\b[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>", re.I | re.S)
_SKIP = {"head", "script", "style", "noscript", "template", "svg", "nav", "header", "footer", "aside", "form",
         "button", "select", "iframe", "dialog"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
# Elements that end a line, and the ones that also leave a blank line after them.
_LINE = {"div", "li", "ul", "ol", "tr", "dd", "dt", "main", "section", "article", "table"}
_PARA = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre"}
_PARAGRAPH = {"p", "li", "pre", "blockquote", "dd"}
_HEADING = {"h1", "h2", "h3", "h4", "h5", "h6", "strong", "b", "dt"}
_SECTION = re.compile(r"responsibilit|qualification|requirement|dut(?:y|ies)\b|skills|what you.?ll (?:do|bring)|"
                      r"about (?:the|this) (?:job|role|position|opportunity|team)|your (?:role|team|impact)|"
                      r"who you are|what we.?re looking for", re.I)
# Chrome around the posting that sites mark by class or id rather than with <nav>/<footer>.
_CHROME = re.compile(r"(?:^|[\s_-])(?:cookies?|consent|breadcrumbs?|share|sharing|social|newsletter|subscribe|"
                     r"(?:related|similar|recommended)[-_]?(?:jobs|roles|positions)|sr-only|visually-hidden)(?=$|[\s_-])",
                     re.I)
LINE, PARA = "\x00", "\x01"     # break markers, resolved by _render
MIN_JSON_LD = 80    # a JobPosting's own description, however short, is the description
MIN_TEXT = 200      # a heuristic pick shorter than this is a teaser or a page shell


def tidy(text: str) -> str:
    """Plain text: single spaces, at most one blank line between paragraphs."""
    text = re.sub(r"[ \t\r\f\v\xa0]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _render(node: "_Node") -> str:
    text = re.sub(r"[ \t\r\n\f\v\xa0]+", " ", node.text())
    text = re.sub(r" ?[\x00\x01][\x00\x01 ]*", lambda m: "\n\n" if PARA in m.group(0) else "\n", text)
    return re.sub(r"(?m)^•$\n?", "", text).strip()      # list items that held only an icon


def html_text(fragment: str) -> str:
    """HTML (sometimes entity-escaped, as JSON-LD descriptions often are) -> plain text."""
    text = html.unescape(fragment or "")
    if "<" not in text:
        return tidy(text)
    if "&lt;" in text:
        text = html.unescape(text)
    tree = _Tree()
    tree.feed(text)
    tree.close()
    return _render(tree.root)


def _postings(data):
    """Every JobPosting object in a JSON-LD document (lists and @graph included)."""
    if isinstance(data, list):
        for item in data:
            yield from _postings(item)
    elif isinstance(data, dict):
        kind = data.get("@type")
        if kind == "JobPosting" or (isinstance(kind, list) and "JobPosting" in kind):
            yield data
        if "@graph" in data:
            yield from _postings(data["@graph"])


def json_ld_posting(page: str) -> dict:
    """The page's schema.org JobPosting (the one with the longest description), or {}."""
    best = {}
    for block in _JSON_LD.findall(page):
        raw = block.strip().removeprefix("<!--").removesuffix("-->").strip()
        try:
            data = json.loads(raw, strict=False)    # some sites leave raw newlines inside strings
        except ValueError:
            continue
        for posting in _postings(data):
            if len(str(posting.get("description") or "")) > len(str(best.get("description") or "")):
                best = posting
    return best


class _Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    def text(self) -> str:
        """Text with LINE/PARA break markers; _render turns them into newlines."""
        parts = []
        self._collect(parts)
        return "".join(parts)

    def _collect(self, parts):
        brk = PARA if self.tag in _PARA else LINE if self.tag in _LINE else ""
        parts.append(f"{LINE}• " if self.tag == "li" else brk)
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                child._collect(parts)
        parts.append(brk)

    def iter(self):
        yield self
        for child in self.children:
            if isinstance(child, _Node):
                yield from child.iter()


class _Tree(HTMLParser):
    """A forgiving element tree: skipped elements are dropped with their contents."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _Node("root", {}, None)
        self.node = self.root
        self.skip = 0          # depth inside a dropped element

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            if tag == "br" and not self.skip:
                self._br()
            return
        if self.skip:
            self.skip += 1
            return
        attrs = dict(attrs)
        marker = f"{attrs.get('class') or ''} {attrs.get('id') or ''}"
        if (tag in _SKIP or "hidden" in attrs or attrs.get("aria-hidden") == "true"
                or attrs.get("role") in ("navigation", "banner", "contentinfo", "dialog")
                or (tag in ("div", "section", "ul") and _CHROME.search(marker))):
            self.skip = 1
            return
        node = _Node(tag, attrs, self.node)
        self.node.children.append(node)
        self.node = node

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip:
            self._br()

    def _br(self):
        """A line break; a second one in a row (LinkedIn's paragraphs) leaves a blank line."""
        kids = self.node.children
        i = len(kids) - 1
        while i >= 0 and isinstance(kids[i], str) and kids[i] not in (LINE, PARA) and not kids[i].strip():
            i -= 1
        if i >= 0 and kids[i] == LINE:
            kids[i] = PARA
        else:
            kids.append(LINE)

    def handle_endtag(self, tag):
        if tag in _VOID:
            return
        if self.skip:
            self.skip -= 1
            return
        node = self.node
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:      # an unmatched end tag is ignored
            self.node = node.parent

    def handle_data(self, data):
        if not self.skip:
            self.node.children.append(data)


def element_text(page: str, css_class: str) -> str:
    """Plain text of the first element carrying this class, or ''."""
    tree = _Tree()
    tree.feed(page)
    tree.close()
    for node in tree.root.iter():
        if css_class in (node.attrs.get("class") or "").split():
            return _render(node)
    return ""


def _microdata_description(root: _Node) -> str:
    for node in root.iter():
        if node.attrs.get("itemprop") == "description":
            text = _render(node)
            if len(text) >= MIN_TEXT:
                return text
    return ""


def _main_text(root: _Node) -> str:
    """The text of the element holding the most paragraph text (readability-style scoring).

    A posting is often split into sibling sections (qualifications, about the job,
    responsibilities), so an element gets more weight for each such heading inside
    it; that keeps one dense block of legal boilerplate from winning."""
    scores, headings = {}, {}
    for node in root.iter():
        if node.tag in _HEADING and _SECTION.search(node.text()[:80]):
            parent = node.parent
            for _ in range(3):
                if parent is None or parent is root:
                    break
                headings[id(parent)] = headings.get(id(parent), 0) + 1
                parent = parent.parent
        if node.tag not in _PARAGRAPH:
            continue
        length = len(_render(node))
        if length < 25:
            continue
        parent = node.parent
        for share in (1.0, 0.5, 0.25):
            if parent is None or parent is root:
                break
            scores[id(parent)] = (scores.get(id(parent), (0, parent))[0] + length * share, parent)
            parent = parent.parent
    if not scores:
        return ""
    best = max(scores.items(), key=lambda item: item[1][0] * (1 + 0.5 * min(headings.get(item[0], 0), 3)))[1][1]
    # Climb while a wrapper adds little besides the chosen block (the job's heading, a short intro).
    while best.parent is not None and best.parent is not root:
        own, wider = len(_render(best)), len(_render(best.parent))
        if wider > own * 1.1:
            break
        best = best.parent
    return _render(best)


def posting_description(page: str) -> str:
    """The job description on a posting page: JobPosting JSON-LD, else microdata, else main text."""
    posting = json_ld_posting(page)
    text = html_text(str(posting.get("description") or "")) if posting else ""
    if len(text) >= MIN_JSON_LD:
        return text
    tree = _Tree()
    tree.feed(page)
    tree.close()
    found = _microdata_description(tree.root) or _main_text(tree.root)
    return found if len(found) >= MIN_TEXT else ""
