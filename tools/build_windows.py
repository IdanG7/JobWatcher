"""Build a clean Windows ZIP with a private, verified Python runtime.

No developer database, subscriber accounts, resume, profile, or state is copied.
The recipient needs no Python installation, pip, PowerShell, or administrator rights.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from urllib.request import urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from intel.profile import DEFAULT_PROFILE, STAGES

PYTHON_VERSION = "3.14.8"
RUNTIME_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
# Published at https://www.python.org/downloads/release/python-3148/
RUNTIME_SHA256 = "a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310"
MODULES = ("watcher.py", "dashboard.py", "db_migrations.py", "intel_store.py",
           "job_intelligence.py", "job_query.py", "portable_start.py")
KNOWLEDGE = ("companies.json", "locations.json", "skills.json", "taxonomy.json")
BOARD_FIELDS = {"ats", "token", "tenant", "site", "host", "domain", "url", "repo",
                "query", "queries", "search", "location", "facets", "cols", "group",
                "min_interval", "disabled", "company_key", "company_type", "geography",
                "priority", "complete_listing", "path", "branch", "max"}

QUICK_START = """JOBWATCH - Windows 10/11, 64-bit

1. Right-click the ZIP and choose Extract All.
2. Open the extracted Jobwatch folder.
3. Double-click Start Jobwatch.bat. Your browser opens automatically.

No Python installation, account, API key, or administrator access is needed.
Internet access is needed to fetch job postings. Setup itself works offline.
Keep the console window open while using Jobwatch. Close it to stop the app.
Double-click Start again to reopen a running app. Jobwatch fetches sources on
startup and every five minutes while open. The first fetch may take several
minutes. A progress panel shows sources checked, active sources, failures and
matching stages. Every tab stays usable, and results fill in automatically.
Open Sources for each source's current status and error details.

MAKE IT YOURS
Open Settings to choose career targets, locations and work authorization.
Upload your own resume under Resume & matching, preview the facts, then choose
Apply & enable matching. Unknown requirements show review notes. Use the Resume
match chip in Opportunities to switch between matched jobs and all jobs.
Open a job's drawer to generate, edit, save, copy or download a cover letter.

YOUR DATA
This is a fresh copy: no sender resume, profile, applications, letters, database
or notification accounts are included. Your data is stored only on your PC in:
    %LOCALAPPDATA%\\Jobwatch
To back up, close Jobwatch and copy that entire data folder. Keep it when
replacing the app folder with a newer release. Do not send that data folder to
someone else. No Discord or Telegram notifications are connected by default.

IF IT DOES NOT START
Make sure you extracted the entire ZIP before opening Start Jobwatch.bat.
Keep app and runtime beside the start file. This package is for 64-bit Windows,
not macOS or Linux. Any startup error stays visible in the console window.
If your browser did not open, copy the local URL printed in that window.

Third-party license notices are included with the runtime and its packages.
"""


def clean_config(source: dict) -> dict:
    profile = copy.deepcopy(DEFAULT_PROFILE)
    profile.update(name="My search", headline="Choose your targets in Settings",
                   graduation_year=None, graduation_month=None,
                   education={"level": "", "school": "", "program": "", "gpa": None},
                   target_roles=[], role_weights={}, target_stages=list(STAGES),
                   target_cycles=[], target_locations=[], target_company_types=[],
                   skills=[], languages=[], work_authorization={"CA": "unknown", "US": "unknown"})
    return {
        "interval_seconds": 300, "feed_flush_minutes": 90, "digest_hour_utc": None,
        "healthcheck_url": "", "dashboard_url": "", "description_budget": 60,
        "description_per_board": 12, "facts_per_cycle": 5000, "profile": profile,
        "filters": {key: value for key, value in source.get("filters", {}).items()
                    if key in {"include", "exclude", "location", "exclude_companies"}},
        "boards": {name: {key: value for key, value in board.items() if key in BOARD_FIELDS}
                   for name, board in source["boards"].items()
                   if not name.startswith("_") and isinstance(board, dict)},
    }


def stage_app(source: Path, destination: Path) -> None:
    app = destination / "app"
    app.mkdir(parents=True)
    for name in MODULES:
        shutil.copyfile(source / name, app / name)
    for folder, suffixes in (("intel", {".py"}), ("web", {".html", ".js", ".css", ".svg", ".ico"})):
        for path in (source / folder).rglob("*"):
            if (path.is_file() and path.suffix in suffixes
                    and not {"tests", "__pycache__"}.intersection(path.relative_to(source).parts)):
                target = app / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    (app / "config").mkdir()
    for name in KNOWLEDGE:
        shutil.copyfile(source / "config" / name, app / "config" / name)
    original = json.loads((source / "config.json").read_text(encoding="utf-8"))
    (app / "config.json").write_text(json.dumps(clean_config(original), indent=2) + "\n", encoding="utf-8")
    (app / "subscribers.json").write_text("{}\n", encoding="utf-8")
    shutil.copyfile(source / "Start Jobwatch.bat", destination / "Start Jobwatch.bat")
    (destination / "READ ME FIRST.txt").write_text(QUICK_START, encoding="utf-8")


def runtime_archive(cache: Path) -> Path:
    path = cache / f"python-{PYTHON_VERSION}-embed-amd64.zip"
    if not path.exists():
        print(f"Downloading Python {PYTHON_VERSION} from python.org...", flush=True)
        temporary = path.with_suffix(".download")
        with urlopen(RUNTIME_URL, timeout=60) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != RUNTIME_SHA256:
        raise ValueError(f"Python runtime checksum mismatch: {path}")
    return path


def bundle_files(stage: Path) -> list[Path]:
    """Omit pip's unused CLI wrappers, which embed the builder's Python path."""
    wrappers = {("runtime", "Lib", "site-packages", "bin"),
                ("runtime", "Lib", "site-packages", "Scripts")}
    return [path for path in sorted(stage.rglob("*"))
            if path.is_file() and path.relative_to(stage).parts[:4] not in wrappers]


def build(output: Path) -> Path:
    cache = ROOT / ".build-cache"
    cache.mkdir(exist_ok=True)
    archive = runtime_archive(cache)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="windows-", dir=cache) as temporary:
        stage = Path(temporary) / "Jobwatch"
        stage_app(ROOT, stage)
        runtime = stage / "runtime"
        runtime.mkdir()
        with zipfile.ZipFile(archive) as embedded:
            for member in embedded.namelist():
                if not (runtime / member).resolve().is_relative_to(runtime.resolve()):
                    raise ValueError("Unexpected path in runtime archive")
            embedded.extractall(runtime)
        (runtime / "python314._pth").write_text(
            "python314.zip\n.\nLib\\site-packages\n..\\app\n", encoding="utf-8")
        print("Bundling dependencies (binary wheels only)...", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                        "--only-binary=:all:", "--no-compile", "--ignore-installed",
                        "--platform", "win_amd64", "--python-version", "3.14",
                        "--implementation", "cp", "--abi", "cp314", "--no-warn-script-location",
                        "--target", str(runtime / "Lib/site-packages"),
                        "-r", str(ROOT / "requirements.txt")], check=True)
        # Licenses in Python and *.dist-info remain in the distribution.
        files = {path.relative_to(stage).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                 for path in bundle_files(stage)}
        manifest = {"python": PYTHON_VERSION, "platform": "Windows x64",
                    "runtime_source": RUNTIME_URL, "runtime_sha256": RUNTIME_SHA256,
                    "files": files}
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary_zip = output.with_suffix(".building.zip")
        with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
            for path in bundle_files(stage):
                bundle.write(path, "Jobwatch/" + path.relative_to(stage).as_posix())
        temporary_zip.replace(output)
    print(f"Ready: {output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Jobwatch-Windows.zip")
    build(parser.parse_args().output.resolve())
