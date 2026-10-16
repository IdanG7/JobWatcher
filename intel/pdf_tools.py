"""Application documents: merge PDFs and typeset a plain-text letter as a PDF.

Merging uses pypdf (already required for resume parsing). The letter PDF is
written by hand with the built-in Helvetica font, so no extra dependency or
font file ships with the app.
"""
from __future__ import annotations

import io
import logging
import textwrap

from .resume import _pdf_limits

MAX_FILES = 20
MAX_FILE_BYTES = 10_000_000
MAX_TOTAL_BYTES = 25_000_000


class PdfError(ValueError):
    """A message safe to show the user."""


def merge_pdfs(files: list[tuple[str, bytes]]) -> bytes:
    """Concatenate PDFs in order; ``files`` is [(filename, data), ...]."""
    if not files:
        raise PdfError("add at least one PDF")
    if len(files) > MAX_FILES:
        raise PdfError(f"merge up to {MAX_FILES} PDFs at a time")
    if sum(len(data) for _, data in files) > MAX_TOTAL_BYTES:
        raise PdfError("these PDFs add up to more than 25 MB")
    try:
        import pypdf
    except ImportError as exc:      # pragma: no cover - pypdf is a requirement
        raise PdfError("merging PDFs needs pypdf (pip install -r requirements.txt)") from exc
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    writer = pypdf.PdfWriter()
    with _pdf_limits(pypdf):
        for name, data in files:
            if len(data) > MAX_FILE_BYTES:
                raise PdfError(f"{name} is larger than 10 MB")
            if not data.lstrip()[:5] == b"%PDF-":
                raise PdfError(f"{name} is not a PDF")
            try:
                reader = pypdf.PdfReader(io.BytesIO(data))
                if reader.is_encrypted and not reader.decrypt(""):
                    raise PdfError(f"{name} is password-protected; remove the password and try again")
                writer.append(reader)
            except PdfError:
                raise
            except Exception as exc:          # pypdf raises many types on bad input
                raise PdfError(f"{name} could not be read as a PDF") from exc
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


# Helvetica advance widths (1/1000 em) for ASCII 32..126, from the standard AFM.
_HELVETICA = [
    278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278,
    556, 556, 556, 556, 556, 556, 556, 556, 556, 556, 278, 278, 584, 584, 584, 556,
    1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556,
    333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833, 556, 556,
    556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584,
]
# Common cp1252 punctuation: ‘ ’ “ ” • – — …
_EXTRA = {0x91: 222, 0x92: 222, 0x93: 333, 0x94: 333, 0x95: 350, 0x96: 556, 0x97: 1000, 0x85: 1000}

PAGE_W, PAGE_H, MARGIN = 612, 792, 72      # US Letter, 1-inch margins
FONT_SIZE, LEADING = 11, 15


def _width(line: bytes) -> float:
    return sum(_HELVETICA[b - 32] if 32 <= b <= 126 else _EXTRA.get(b, 556) for b in line) * FONT_SIZE / 1000


def _wrap(paragraph: bytes, limit: float) -> list[bytes]:
    words, lines, line = paragraph.split(b" "), [], b""
    for word in words:
        candidate = word if not line else line + b" " + word
        if _width(candidate) <= limit or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
        while _width(line) > limit:       # one very long word: hard-break it
            cut = max(1, int(len(line) * limit / _width(line)))
            lines.append(line[:cut])
            line = line[cut:]
    lines.append(line)
    return lines


def _escape(line: bytes) -> bytes:
    return line.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(text: str, title: str = "Cover letter") -> bytes:
    """A simple one-column PDF of ``text`` (blank lines separate paragraphs)."""
    limit = PAGE_W - 2 * MARGIN
    lines: list[bytes] = []
    for raw in (text or "").replace("\r\n", "\n").replace("\t", "    ").split("\n"):
        encoded = raw.rstrip().encode("cp1252", errors="replace")
        lines.extend(_wrap(encoded, limit) if encoded else [b""])
    per_page = int((PAGE_H - 2 * MARGIN) / LEADING)
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[b""]]

    objects: list[bytes] = [b"", b""]          # 1 catalog, 2 page tree (filled below)
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    kids = []
    for page in pages:
        stream = b"BT /F1 %d Tf %d TL %d %d Td\n" % (FONT_SIZE, LEADING, MARGIN, PAGE_H - MARGIN - FONT_SIZE)
        stream += b"".join(b"(" + _escape(line) + b") Tj T*\n" for line in page) + b"ET"
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R >> >> "
                       b"/Contents %d 0 R >>" % (PAGE_W, PAGE_H, len(objects)))
        kids.append(len(objects))
    info_title = ("﻿" + title[:200]).encode("utf-16-be").hex().encode()   # text strings are not cp1252
    objects.append(b"<< /Title <" + info_title + b"> /Producer (Foothold) >>")
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = b"<< /Type /Pages /Kids [%s] /Count %d >>" % (
        b" ".join(b"%d 0 R" % k for k in kids), len(kids))

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1, len(objects), xref)
    return bytes(out)


def safe_filename(*parts: str, suffix: str = ".pdf") -> str:
    """'RBC - Summer Analyst.pdf' with characters Windows rejects removed."""
    name = " - ".join(p.strip() for p in parts if p and p.strip()) or "Foothold"
    name = "".join(c for c in name if c not in '<>:"/\\|?*' and ord(c) >= 32)
    return textwrap.shorten(name, 120, placeholder="…").strip(" .") + suffix
