"""Application documents: merge PDFs and typeset a plain-text letter as a PDF.

Merging uses pypdf (already required for resume parsing). The letter PDF is
written by hand in Times New Roman, so no extra dependency or font file ships
with the app. A past letter that signs with an image of a handwritten signature
gives that image up here too, so letters adapted from it can carry it.
"""
from __future__ import annotations

import base64
import io
import logging
import math
import re
import struct
import textwrap
import zlib

from .resume import _pdf_limits

MAX_FILES = 20
MAX_FILE_BYTES = 10_000_000
MAX_TOTAL_BYTES = 25_000_000
MAX_SIGNATURE_PIXELS = 600_000                  # a signature image larger than this isn't kept
MAX_SIGNATURE_BYTES = 250_000
SIGNATURE_BOX = (216, 72)                       # points: drawn no larger than 3 by 1 inches


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


# Times New Roman advance widths (1/1000 em) for cp1252 codes 32..255, read from the Windows font; 0 marks the
# codes cp1252 leaves unused. The font isn't embedded: Windows and macOS have it, and with these widths any
# other reader that substitutes a Times keeps the same line breaks and right edges.
_TIMES = [
    250, 333, 408, 500, 500, 833, 778, 180, 333, 333, 500, 564, 250, 333, 250, 278,
    500, 500, 500, 500, 500, 500, 500, 500, 500, 500, 278, 278, 564, 564, 564, 444,
    921, 722, 667, 667, 722, 611, 556, 722, 722, 333, 389, 722, 611, 889, 722, 722,
    556, 722, 667, 556, 611, 722, 722, 944, 722, 722, 611, 333, 278, 333, 469, 500,
    333, 444, 500, 444, 500, 444, 333, 500, 500, 278, 278, 500, 278, 778, 500, 500,
    500, 500, 333, 389, 278, 500, 500, 722, 500, 500, 444, 480, 200, 480, 541, 0,
    500, 0, 333, 500, 444, 1000, 500, 500, 333, 1000, 556, 333, 889, 0, 611, 0,
    0, 333, 333, 444, 444, 350, 500, 1000, 333, 980, 389, 333, 722, 0, 444, 722,
    250, 333, 500, 500, 500, 500, 200, 500, 333, 760, 276, 500, 564, 333, 760, 500,
    400, 549, 300, 300, 333, 576, 453, 333, 333, 300, 310, 500, 750, 750, 750, 444,
    722, 722, 722, 722, 722, 722, 889, 667, 611, 611, 611, 611, 333, 333, 333, 333,
    722, 722, 722, 722, 722, 722, 722, 564, 722, 722, 722, 722, 722, 722, 556, 500,
    444, 444, 444, 444, 444, 444, 667, 444, 444, 444, 444, 444, 278, 278, 278, 278,
    500, 500, 500, 500, 500, 500, 500, 549, 500, 500, 500, 500, 500, 500, 500, 500,
]
PAGE_W, PAGE_H = 612, 792                       # US Letter
# (type size, margin), largest first: the first that keeps the letter on one page is used.
FITS = ((12, 72), (11.5, 72), (11, 72), (11, 54))
LEADING = 1.15                                  # single line spacing for Times New Roman
SUPERSCRIPT = 0.65                              # the 'th' in 'May 11th, 2026'

GREETING = re.compile(r"^\s*(?:dear|to whom|hello)\b", re.I)
CLOSING = re.compile(r"[a-z][a-z ]{1,28},", re.I)                  # 'Best Regards,', 'Sincerely,'
_NAME = re.compile(r"[^\W\d_]+(?:[ .'-]+[^\W\d_]+){0,4}\.?")       # 'Idan Reitman', not an email or a phone
_SIGNATURE, _INKED = "signature", "inked"       # rows: the signature image starts on one and covers the next few
_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
DATE_LINE = re.compile(rf"^\s*(?:{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?,?|\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH},?)\s+\d{{4}}\s*$", re.I)
_ORDINAL = re.compile(rb"(?<=\d)(st|nd|rd|th)\b")


def _width(text: bytes, size: float) -> float:
    return sum(_TIMES[b - 32] if b >= 32 else 0 for b in text) * size / 1000


def _wrap(paragraph: bytes, limit: float, size: float) -> list[bytes]:
    words, lines, line = paragraph.split(b" "), [], b""
    for word in words:
        candidate = word if not line else line + b" " + word
        if _width(candidate, size) <= limit or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
        while _width(line, size) > limit:       # one very long word: hard-break it
            cut = max(1, int(len(line) * limit / _width(line, size)))
            lines.append(line[:cut])
            line = line[cut:]
    lines.append(line)
    return lines


def _escape(line: bytes) -> bytes:
    return line.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def letter_parts(text: str) -> tuple[list[str], list[str], list[str]]:
    """(sender, recipient, letter): the lines up to and including the date, which sit on the right; the
    recipient's lines between the date and the greeting, on the left; and the letter from its greeting.
    Text without a greeting is all letter."""
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").replace("\t", "    ").split("\n")]
    greeting = next((i for i, line in enumerate(lines) if GREETING.match(line)), None)
    if greeting is None:
        return [], [], lines
    head = lines[:greeting]
    date = next((i for i, line in enumerate(head) if DATE_LINE.match(line)), -1)
    return ([line.strip() for line in head[:date + 1] if line.strip()],
            [line.strip() for line in head[date + 1:] if line.strip()], lines[greeting:])


def _signature_place(letter: list[str]) -> tuple[int, int | None] | None:
    """Where a signature image goes: the index of the closing line near the letter's end ('Best Regards,') and of
    the typed name right under it, which the image takes the place of (None when no name follows). None when the
    letter has no closing."""
    filled = [i for i, line in enumerate(letter) if line.strip()]
    for k in range(len(filled) - 1, max(-1, len(filled) - 5), -1):
        line = letter[filled[k]].strip()
        if CLOSING.fullmatch(line) and not GREETING.match(line):
            after = filled[k + 1] if k + 1 < len(filled) else None
            return filled[k], after if after is not None and _NAME.fullmatch(letter[after].strip()) else None
    return None


def _signature_rows(height: float, size: float) -> int:
    """Rows a signature this tall covers, from just below the closing to clear of the next line's capitals."""
    return max(1, math.ceil((height + 1.7 * size) / (size * LEADING)) - 1)


def _rows(parts: tuple[list[str], list[str], list[str]], size: float, margin: float,
          signed: float = 0) -> list[tuple[bool, bytes] | str | None]:
    """Lines top to bottom as (right-aligned, cp1252 text), None for a blank line between blocks. With ``signed``
    (a signature's height in points), the signature's rows follow the closing in place of the typed name."""
    def encode(line: str) -> bytes:
        return line.encode("cp1252", errors="replace")
    sender, recipient, letter = parts
    place = _signature_place(letter) if signed else None
    rows: list[tuple[bool, bytes] | str | None] = [(True, encode(line)) for line in sender] + [None]
    rows += [(False, encode(line)) for line in recipient] + [None]
    for i, line in enumerate(letter):
        if place and i == place[1]:
            continue
        rows += [(False, part) for part in _wrap(encode(line), PAGE_W - 2 * margin, size)] if line.strip() else [None]
        if place and i == place[0]:
            rows += [_SIGNATURE] + [_INKED] * (_signature_rows(signed, size) - 1)
    tidy: list[tuple[bool, bytes] | str | None] = []
    for row in rows:
        if row is not None or (tidy and tidy[-1] is not None):     # one blank line at most, none on top
            tidy.append(row)
    while tidy and tidy[-1] is None:
        tidy.pop()
    return tidy


def _line(right: bool, text: bytes, y: float, size: float, margin: float) -> bytes:
    """One line of text; a date's ordinal ('11th') is set as a superscript."""
    pieces = _ORDINAL.split(text) if DATE_LINE.match(text.decode("cp1252", errors="replace")) else [text]
    sizes = [size * SUPERSCRIPT if i % 2 else size for i in range(len(pieces))]
    x = PAGE_W - margin - sum(_width(p, s) for p, s in zip(pieces, sizes)) if right else margin
    out = b"BT %.2f %.2f Td" % (x, y)
    for i, (piece, piece_size) in enumerate(zip(pieces, sizes)):
        out += b" /F1 %.2f Tf %.2f Ts (%s) Tj" % (piece_size, size * 0.33 if i % 2 else 0, _escape(piece))
    return out + b" ET\n"


def letter_pdf(text: str, title: str = "Cover letter", signature: dict | None = None) -> bytes:
    """``text`` set as a business letter in Times New Roman: the sender and date on the right, the recipient
    on the left, the letter below, one blank line between paragraphs. It takes the largest of 12, 11.5 and
    11 pt that keeps it on one page; a letter too long even at 11 pt goes on to a second page.

    ``signature`` (from ``letter_signature``) is drawn under the closing line in place of the typed name; a
    letter without a closing, or a signature that can't be read, is set without it."""
    parts = letter_parts(text)
    image = _signature_image(signature)
    for size, margin in FITS:
        rows = _rows(parts, size, margin, image[2] if image else 0)
        if len(rows) * size * LEADING <= PAGE_H - 2 * margin:
            break
    leading = size * LEADING
    per_page = int((PAGE_H - 2 * margin) // leading)
    signed = rows.index(_SIGNATURE) if _SIGNATURE in rows else -1
    pages, start = [], 0
    while start < len(rows):
        end = start + per_page
        if start < signed - 1 and signed <= end < signed + rows.count(_INKED) + 1:
            end = signed - 1                    # the closing and its whole signature go over to the next page
        pages.append(rows[start:end])
        start = end
    pages = pages or [[]]

    objects: list[bytes] = [b"", b""]          # 1 catalog, 2 page tree (filled below)
    objects.append(b"<< /Type /Font /Subtype /TrueType /BaseFont /TimesNewRomanPSMT /FirstChar 32 /LastChar 255 "
                   b"/Widths [" + b" ".join(b"%d" % w for w in _TIMES) + b"] /Encoding /WinAnsiEncoding /FontDescriptor 4 0 R >>")
    objects.append(b"<< /Type /FontDescriptor /FontName /TimesNewRomanPSMT /Flags 34 /FontBBox [-568 -307 2046 1040] "
                   b"/ItalicAngle 0 /Ascent 891 /Descent -216 /CapHeight 662 /StemV 82 >>")
    if signed >= 0:
        objects.append(image[0])                # 5: the signature image
    kids = []
    for page in pages:
        top = PAGE_H - margin - size
        stream = b""
        for n, row in enumerate(page):
            y = top - n * leading
            if row == _SIGNATURE:               # its top just below the closing line, at the left margin
                width, height = image[1], image[2]
                stream += b"q %.2f 0 0 %.2f %.2f %.2f cm /Sig Do Q\n" % (
                    width, height, margin, y + leading - 0.8 * size - height)
            elif isinstance(row, tuple):
                stream += _line(*row, y, size, margin)
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        images = b" /XObject << /Sig 5 0 R >>" if _SIGNATURE in page else b""
        objects.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /Font << /F1 3 0 R >>%s >> "
                       b"/Contents %d 0 R >>" % (PAGE_W, PAGE_H, images, len(objects)))
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


def letter_signature(data: bytes) -> dict | None:
    """The image a PDF letter signs with, just below the closing line ('Best Regards,') on its last page, as a
    file over white paper: {'format': 'png' | 'jpeg', 'data': base64, 'width', 'height', 'colors' (1 or 3),
    'points': [width, height] as drawn}. None when it has none, or one this can't carry over."""
    try:
        import pypdf
    except ImportError:                         # pragma: no cover - pypdf is a requirement
        return None
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    try:
        with _pdf_limits(pypdf):
            return _page_signature(pypdf.PdfReader(io.BytesIO(data)).pages[-1])
    except Exception:                           # pypdf raises many types on bad input; the letter's text is kept
        return None


def _page_signature(page) -> dict | None:
    pieces: list[tuple[float, float, str]] = []

    def visit(text, cm, tm, font, size):
        if text.strip():                        # where the text starts on the page: the text matrix through the CTM
            pieces.append((tm[4] * cm[1] + tm[5] * cm[3] + cm[5], tm[4] * cm[0] + tm[5] * cm[2] + cm[4], text))
    page.extract_text(visitor_text=visit)
    lines: list[list[tuple[float, float, str]]] = []
    for piece in sorted(pieces, key=lambda p: -p[0]):
        if lines and lines[-1][0][0] - piece[0] <= 2:
            lines[-1].append(piece)
        else:
            lines.append([piece])
    closings = []
    for line in lines:
        text = " ".join(" ".join(p[2] for p in sorted(line, key=lambda p: p[1])).split())
        if CLOSING.fullmatch(text) and not GREETING.match(text):
            closings.append((line[0][0], min(p[1] for p in line)))
    if not closings:
        return None
    baseline, left = closings[-1]               # the lowest

    resources = page.get("/Resources")
    xobjects = resources.get_object().get("/XObject") if resources else None
    xobjects = xobjects.get_object() if xobjects else {}
    contents = page.get_contents()
    ctm, saved, below = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), [], []
    for operands, op in contents.operations if contents is not None else []:     # an empty dict, so falsy
        if op == b"q":
            saved.append(ctm)
        elif op == b"Q" and saved:
            ctm = saved.pop()
        elif op == b"cm" and len(operands) == 6:
            a, b, c, d, e, f = (float(v) for v in operands)
            A, B, C, D, E, F = ctm
            ctm = (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)
        elif op == b"Do" and operands and operands[0] in xobjects:
            image = xobjects[operands[0]].get_object()
            width, skew, shear, height, x, y = ctm
            # Upright, signature-sized, its top just below the closing, starting near where the closing does.
            if (image.get("/Subtype") == "/Image" and abs(skew) < 0.01 and abs(shear) < 0.01
                    and 18 <= width <= 432 and 6 <= height <= 144
                    and baseline - 72 <= y + height <= baseline + 6 and abs(x - left) <= 144):
                below.append((y + height, image, width, height))
    for _, image, width, height in sorted(below, key=lambda found: -found[0]):
        found = _image_file(image)
        if found:
            return {**found, "points": [round(width, 2), round(height, 2)]}
    return None


def _image_file(image) -> dict | None:
    """A PDF image as a PNG (or the JPEG it already is) over white paper; None for kinds this doesn't handle."""
    width, height = int(image.get("/Width", 0)), int(image.get("/Height", 0))
    if (not 0 < width * height <= MAX_SIGNATURE_PIXELS or image.get("/ImageMask") or "/Mask" in image
            or "/Decode" in image or image.get("/BitsPerComponent", 8) != 8):
        return None
    colors, palette = _colors(image.get("/ColorSpace"))
    filters = _filters(image)
    if filters[-1:] == ["/DCTDecode"]:
        data, kind = image.get_data(), "jpeg"
        if palette or "/SMask" in image or not data.startswith(b"\xff\xd8"):
            return None
    elif {"/DCTDecode", "/JPXDecode", "/CCITTFaxDecode", "/JBIG2Decode"} & set(filters) or not colors:
        return None
    else:
        pixels = image.get_data()
        if palette:
            entries = [palette[i * colors:(i + 1) * colors].ljust(colors, b"\0") for i in range(256)]
            pixels = b"".join(map(entries.__getitem__, pixels[:width * height]))
        if len(pixels) < width * height * colors:
            return None
        pixels = pixels[:width * height * colors]
        if "/SMask" in image:
            mask = image["/SMask"].get_object()
            if ((mask.get("/Width"), mask.get("/Height"), mask.get("/BitsPerComponent", 8)) != (width, height, 8)
                    or "/Matte" in mask or {"/DCTDecode", "/JPXDecode", "/JBIG2Decode"} & set(_filters(mask))):
                return None
            alpha = mask.get_data()
            if len(alpha) < width * height:
                return None
            pixels = _on_white(pixels, alpha[:width * height], colors)
        data, kind = _png(pixels, width, height, colors), "png"
    if len(data) > MAX_SIGNATURE_BYTES:
        return None
    return {"format": kind, "data": base64.b64encode(data).decode("ascii"), "width": width, "height": height,
            "colors": colors}


def _filters(stream) -> list[str]:
    found = stream.get("/Filter") or []
    return [found] if isinstance(found, str) else [str(f) for f in found]


def _colors(space) -> tuple[int, bytes | None]:
    """(components, palette) of a grey, RGB or indexed colour space; (0, None) for any other."""
    space = space.get_object() if space is not None else None
    if space in ("/DeviceGray", "/CalGray", "/DeviceRGB", "/CalRGB"):
        return (1 if "Gray" in space else 3), None
    if isinstance(space, list) and space:
        if space[0] in ("/CalGray", "/CalRGB"):
            return _colors(space[0])
        if space[0] == "/ICCBased" and len(space) == 2:
            n = space[1].get_object().get("/N")
            return (int(n), None) if n in (1, 3) else (0, None)
        if space[0] == "/Indexed" and len(space) == 4:
            colors, palette = _colors(space[1])
            table = space[3].get_object()
            table = table.get_data() if hasattr(table, "get_data") else table.original_bytes
            return (colors, table) if colors and not palette else (0, None)
    return 0, None


def _on_white(pixels: bytes, alpha: bytes, colors: int) -> bytes:
    """A transparent image as it shows on white paper: the ink stays, the background turns white."""
    out = bytearray(pixels)
    white = b"\xff" * colors
    for i, a in enumerate(alpha):
        if a == 0:
            out[i * colors:(i + 1) * colors] = white
        elif a < 255:
            for j in range(i * colors, (i + 1) * colors):
                out[j] = 255 - (255 - out[j]) * a // 255
    return bytes(out)


def _png(pixels: bytes, width: int, height: int, colors: int) -> bytes:
    """An 8-bit grey or RGB PNG, every row unfiltered."""
    def chunk(kind: bytes, body: bytes) -> bytes:
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body))
    stride = width * colors
    rows = b"".join(b"\0" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 0 if colors == 1 else 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


def _png_data(png: bytes) -> tuple[int, int, int, bytes]:
    """(width, height, colors, compressed rows) of an 8-bit grey or RGB PNG; ValueError for any other."""
    if not png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("not a PNG")
    head, rows, at = None, [], 8
    while at + 8 <= len(png):
        length, kind = struct.unpack(">I4s", png[at:at + 8])
        body = png[at + 8:at + 8 + length]
        if kind == b"IHDR":
            head = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            rows.append(body)
        elif kind == b"IEND":
            break
        at += 12 + length
    if not head or not rows or head[2:] not in ((8, 0, 0, 0, 0), (8, 2, 0, 0, 0)):
        raise ValueError("only 8-bit grey or RGB PNGs")
    return head[0], head[1], 1 if head[3] == 0 else 3, b"".join(rows)


def _signature_image(signature: dict | None) -> tuple[bytes, float, float] | None:
    """The signature as a PDF image object and the width and height it's drawn at; None when it can't be used."""
    if not signature:
        return None
    try:
        data = base64.b64decode(signature["data"], validate=True)
        if signature["format"] == "png":
            width, height, colors, data = _png_data(data)
            coding = b"/Filter /FlateDecode /DecodeParms << /Predictor 15 /Colors %d /BitsPerComponent 8 /Columns %d >>" % (
                colors, width)
        elif signature["format"] == "jpeg" and data.startswith(b"\xff\xd8"):
            width, height, colors = int(signature["width"]), int(signature["height"]), int(signature["colors"])
            coding = b"/Filter /DCTDecode"
        else:
            return None
        drawn_w, drawn_h = (float(v) for v in signature["points"])
    except (KeyError, TypeError, ValueError, struct.error):
        return None
    if colors not in (1, 3) or not (0 < width and 0 < height and 0 < drawn_w < 1000 and 0 < drawn_h < 1000):
        return None
    scale = min(1, SIGNATURE_BOX[0] / drawn_w, SIGNATURE_BOX[1] / drawn_h)
    image = (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /%s /BitsPerComponent 8 %s "
             b"/Length %d >>\nstream\n" % (width, height, b"DeviceGray" if colors == 1 else b"DeviceRGB", coding, len(data))
             + data + b"\nendstream")
    return image, drawn_w * scale, drawn_h * scale


def safe_filename(*parts: str, suffix: str = ".pdf") -> str:
    """'RBC - Summer Analyst.pdf' with characters Windows rejects removed."""
    name = " - ".join(p.strip() for p in parts if p and p.strip()) or "Foothold"
    name = "".join(c for c in name if c not in '<>:"/\\|?*' and ord(c) >= 32)
    return textwrap.shorten(name, 120, placeholder="…").strip(" .") + suffix
