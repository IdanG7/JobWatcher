"""Record what the app reads from each fixture resume, to show a board's work changes none of them.

    python -m tools.resume_record record --code <checkout> --out <recording.json> [--epoch 1793070000]
        [--only finance,nursing]
    python -m tools.resume_record compare <old recording.json> <new recording.json>

record runs the checkout's own JobwatchService.parse_resume, as the app's resume preview does, with the
clock frozen, on the fixture resumes in the checkout's tests: the finance, cover-letter, mixed and CS ones
and the health and P&D ones. Each is read as pasted text, as a PDF (with plain fonts, and as LaTeX's fonts encode
it) and as a Word file (in three layouts), through the checkout's own test helpers. Each reading is taken
with no saved profile ("<fixture>/<form>") and under each of PROFILES saved first ("<fixture>/<form>@<profile>"),
since the profile a resume proposes depends on the one it starts from. When the preview refuses a resume,
what the parser read is recorded beside the refusal. A fixture or helper the checkout lacks is recorded as
skipped. compare exits 1 when a recorded result (key order included), or the document it was read from,
differs, or when it is missing or newly skipped; results only the new recording has are listed.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

EPOCH = 1793070000          # 2026-10-27 03:00 UTC
# name: (module, attribute) of the fixture text in the checkout's tests
FIXTURES = {
    "finance": ("tests.resume.test_resume_matching", "RESUME"),
    "letter": ("tests.letters.test_cover_letters", "RESUME"),
    "mixed": ("tests.resume.test_resume_tech", "MIXED_RESUME"),
    "cs": ("tests.resume.test_resume_tech", "CS_TEXT"),
    "nursing": ("tests.resume.test_resume_health", "NURSING"),
    "biology": ("tests.resume.test_resume_health", "BIOLOGY"),
    "pharmacy": ("tests.resume.test_resume_health", "PHARMACY"),
    "biomedical": ("tests.resume.test_resume_health", "BIOMEDICAL"),
    "pm": ("tests.resume.test_resume_pd_fixtures", "PM"),
    "ux_designer": ("tests.resume.test_resume_pd_fixtures", "UX_DESIGNER"),
    "ux_researcher": ("tests.resume.test_resume_pd_fixtures", "UX_RESEARCHER"),
    "visual": ("tests.resume.test_resume_pd_fixtures", "VISUAL"),
    "industrial": ("tests.resume.test_resume_pd_fixtures", "INDUSTRIAL"),
    "cs_pm": ("tests.resume.test_resume_pd_fixtures", "CS_PM"),
}
FORMS = ("text", "pdf", "latex", "docx", "docx-nested", "docx-flat")
# Saved first-run profiles (tools/board_gate.py sample_profiles) each reading is also taken under.
PROFILES = ("finance", "software", "product", "design", "healthcare", "finance+product", "software+design")


def _helper(module: str, name: str):
    return getattr(__import__(module, fromlist=[name]), name)


def _payload(name: str, text: str, form: str) -> dict:
    """The request the app's resume preview gets for this form."""
    if form == "text":
        return {"text": text}
    if form in ("pdf", "latex"):
        pdf = _helper("tests.resume.test_resume_tech", "pdf")
        if name == "cs" and form == "latex":
            lines = _helper("tests.resume.test_resume_tech", "CS_LINES")
        else:
            lines = _helper("tests.resume.test_resume_health", "plain_lines" if form == "pdf" else "latex_lines")(text)
        return {"filename": f"{name}.pdf", "data": base64.b64encode(pdf(lines)).decode()}
    listed = {"docx": None, "docx-nested": "nested", "docx-flat": "flat"}[form]
    data = _helper("tests.resume.test_resume_health", "word_docx")(text, listed)
    return {"filename": f"{name}.docx", "data": base64.b64encode(data).decode()}


def _input_hash(payload: dict) -> str:
    """The document the parser is given: the text, the PDF's bytes, or the Word file's parts (not its zip dates)."""
    if "text" in payload:
        blob = payload["text"].encode()
    else:
        blob = base64.b64decode(payload["data"])
        if payload["filename"].endswith(".docx"):
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                blob = json.dumps(sorted((n, z.read(n).hex()) for n in z.namelist())).encode()
    return hashlib.sha1(blob).hexdigest()[:16]


def _as_app_sends(value):
    return json.loads(json.dumps(value, default=str))     # the app's JSON (dashboard.py serializes with default=str)


def _record(code, out, epoch, only="") -> None:
    gate = importlib.util.spec_from_file_location("board_gate", Path(__file__).with_name("board_gate.py"))
    board_gate = importlib.util.module_from_spec(gate)
    gate.loader.exec_module(board_gate)
    board_gate._checkout(code, float(epoch), "dashboard")
    from dashboard import ApiError, JobwatchService
    from intel.profile import DEFAULT_PROFILE, merge_profile
    from intel.resume import parse_resume
    from intel_store import save_profile
    names = [n for n in FIXTURES if not only or n in only.split(",")]
    results = {}
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "config.json").write_text(json.dumps({"boards": {}}), encoding="utf-8")
        (root / "subscribers.json").write_text("{}", encoding="utf-8")
        service = JobwatchService(root / "jobwatch.db", root / "config.json", root / "subscribers.json")
        layers = board_gate.sample_profiles(DEFAULT_PROFILE, {s.key: s.group for s in service.kn.skills})
        for name in names:
            try:
                text = _helper(*FIXTURES[name])
            except (ImportError, AttributeError) as exc:
                results.update({f"{name}/{form}": {"skipped": type(exc).__name__} for form in FORMS})
                continue
            for form in FORMS:
                try:
                    payload = _payload(name, text, form)
                except Exception as exc:    # a helper this checkout lacks, or a fixture it cannot encode
                    results[f"{name}/{form}"] = {"skipped": type(exc).__name__}
                    continue
                for profile in ("", *PROFILES):
                    with service.db() as con:
                        con.execute("DELETE FROM user_profile")
                        if profile:
                            save_profile(con, merge_profile(None, layers[profile]))
                    entry = {"input": _input_hash(payload)}
                    try:
                        entry["result"] = _as_app_sends(service.parse_resume(payload))
                    except ApiError as exc:
                        # The preview refuses it; what the parser read is still compared.
                        try:
                            filename, document = service._document_text(payload)
                            read = parse_resume(document, service.kn, wrapped="text" in payload
                                                or not filename.lower().endswith(".docx"))
                        except Exception as inner:
                            read = {"crash": f"{type(inner).__name__}: {inner}"}
                        entry["result"] = {"error": str(exc), "parsed": _as_app_sends(read)}
                    except Exception as exc:
                        entry["result"] = {"crash": f"{type(exc).__name__}: {exc}"}
                    results[f"{name}/{form}" + (f"@{profile}" if profile else "")] = entry
    Path(out).write_text(json.dumps({"code": str(Path(code).resolve()), "epoch": float(epoch),
                                     "utc_offset": board_gate._utc_offset(float(epoch)), "results": results},
                                    ensure_ascii=False, indent=1), encoding="utf-8")


def record(code, out, epoch=EPOCH, only=()) -> dict:
    out = Path(out).resolve()
    if out.exists():
        raise SystemExit(f"{out} exists: each recording is written to a new file")
    if unknown := [n for n in only if n not in FIXTURES]:
        raise SystemExit(f"no fixture named {', '.join(unknown)}; the fixtures are {', '.join(FIXTURES)}")
    subprocess.run([sys.executable, "-I", str(Path(__file__).resolve()), "_record", str(Path(code).resolve()),
                    str(out), str(epoch), ",".join(only)], check=True, cwd=str(Path(code).resolve()))
    return json.loads(out.read_text(encoding="utf-8"))


def _differ(a, b, path="") -> list[str]:
    """The paths at which two recorded results differ."""
    if isinstance(a, dict) and isinstance(b, dict):
        return [p for k in dict.fromkeys([*a, *b]) for p in _differ(a.get(k), b.get(k), f"{path}.{k}" if path else k)]
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [p for i, (x, y) in enumerate(zip(a, b)) for p in _differ(x, y, f"{path}[{i}]")]
    return [] if a == b else [path or "(result)"]


def compare(old_path, new_path, out=print) -> int:
    old_rec, new_rec = (json.loads(Path(p).read_text(encoding="utf-8")) for p in (old_path, new_path))
    old, new = old_rec["results"], new_rec["results"]
    failed = False
    for k in ("epoch", "utc_offset"):
        if old_rec.get(k) != new_rec.get(k):
            out(f"  different {k}: {old_rec.get(k)} vs {new_rec.get(k)}: record both with the same clock")
            failed = True
    if all("skipped" in e for e in old.values()):
        out(f"  {old_path} records nothing to compare")
        failed = True
    for key, a in old.items():
        b = new.get(key)
        if b is None:
            out(f"  missing: {key}")
        elif "skipped" in a:
            if "skipped" not in b:
                out(f"  now recorded: {key}")
            continue
        elif "skipped" in b:
            out(f"  skipped now: {key} ({b['skipped']})")
        elif a["input"] != b["input"]:
            out(f"  input changed: {key}")
        elif json.dumps(a) != json.dumps(b):
            paths = _differ(a, b)
            out(f"  changed: {key}: {', '.join(paths[:12]) if paths else 'key order'}{' ...' if len(paths) > 12 else ''}")
        else:
            continue
        failed = True
    for key in [k for k in new if k not in old]:
        out(f"  added: {key}")
    skipped = sum("skipped" in e for e in new.values())
    out(f"{len(old)} -> {len(new)} recorded ({skipped} skipped in {new_path})")
    out("resumes: " + ("FAILED" if failed else "passed"))
    return 1 if failed else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tools.resume_record", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    rec = sub.add_parser("record", help="record a checkout's readings of the fixture resumes")
    rec.add_argument("--code", required=True, help="the checkout to run (this tree, or `git archive` of main)")
    rec.add_argument("--out", required=True)
    rec.add_argument("--epoch", type=float, default=EPOCH, help="the frozen clock, in Unix seconds")
    rec.add_argument("--only", default="", help="comma-separated fixture names (default: all)")
    cmp = sub.add_parser("compare", help="compare two recordings")
    cmp.add_argument("old")
    cmp.add_argument("new")
    sub.add_parser("_record").add_argument("args", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "record":
        record(args.code, args.out, args.epoch, [n for n in args.only.split(",") if n])
        return 0
    if args.command == "compare":
        return compare(args.old, args.new)
    _record(*args.args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
