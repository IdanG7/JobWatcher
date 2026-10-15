"""Build clean Windows installer/ZIP packages with a private, verified Python runtime.

No developer database, subscriber accounts, resume, profile, or state is copied.
The recipient needs no Python installation, pip, PowerShell, or administrator rights.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
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
from version import APP_VERSION

PYTHON_VERSION = "3.14.8"
RUNTIME_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/python-{PYTHON_VERSION}-embed-amd64.zip"
# Published at https://www.python.org/downloads/release/python-3148/
RUNTIME_SHA256 = "a93abe456ab01bd96d7a085b3cdb6566b3063f4241360d114142fbdb07f0a310"
MODULES = ("watcher.py", "dashboard.py", "db_migrations.py", "intel_store.py",
           "job_intelligence.py", "job_query.py", "portable_start.py", "version.py", "updater.py",
           "update_key.py")
KNOWLEDGE = ("companies.json", "locations.json", "skills.json", "taxonomy.json", "source_defaults_v1.json",
             "source_defaults_history.json")
BOARD_FIELDS = {"ats", "token", "tenant", "site", "host", "domain", "url", "repo",
                "query", "queries", "search", "location", "facets", "cols", "group",
                "min_interval", "disabled", "company_key", "company_type", "geography",
                "priority", "complete_listing", "indirect_links", "path", "branch", "max", "size", "pages", "recency", "seed_pages", "seed_recency",
                "feed", "servlet", "lang"}

QUICK_START = """JOBWATCH - Windows 10/11, 64-bit

INSTALLER (recommended)
Download Jobwatch-Setup-<version>.exe from:
    https://github.com/IdanG7/JobWatcher/releases/latest
Run Setup. It installs for your Windows account; no administrator rights are needed.
If Windows shows "Windows protected your PC", choose More info, then Run anyway.
Open Jobwatch from the Start menu any time to reopen the dashboard.

PORTABLE ZIP (0.2.0 is the final ZIP release)
1. Right-click the ZIP and choose Extract All.
2. Open the extracted Jobwatch folder.
3. Double-click Start Jobwatch.bat. Your browser opens automatically.

No Python installation, account, API key, or administrator access is needed.
Internet access is needed to fetch job postings. Setup itself works offline.
Jobwatch runs in the background without a window. In the ZIP copy, the start
window closes by itself; double-click Start Jobwatch.bat to reopen it. To start it
whenever you sign in to Windows, or to stop it, open Settings > Background.
Jobwatch fetches sources on startup and every five minutes while it runs
(about 200 MB of memory, little CPU between checks). The first fetch may take several
minutes. A progress panel shows sources checked, active sources, failures and
matching stages. Every tab stays usable, and results fill in automatically.
Open Sources for each source's current status and error details.

UPDATES
Jobwatch checks for updates every six hours and downloads them in the background.
When a verified update is ready, choose Restart to update. The page reconnects
automatically, keeping your data and settings. For a ZIP copy, this installs the
app and moves future starts to the Start menu; you can then delete the old folder.
Versions 0.1.13 and earlier need a manual upgrade: stop Jobwatch in Settings >
Background, run Setup, and open it from the Start menu. Check your data before
deleting the old extracted folder. Releases after 0.2.0 provide the installer only.
To uninstall, use Windows Settings > Apps; keeping your data is the default.

MAKE IT YOURS
Open Settings to choose career targets, locations and work authorization.
Upload your own resume under Resume & matching, preview the facts, then choose
Apply & enable matching. Unknown requirements show review notes. Use the Resume
match chip in Opportunities to switch between matched jobs and all jobs.

YOUR DATA
This is a fresh copy: no sender resume, profile, applications, letters, database
or notification accounts are included. Your data is stored only on your PC in:
    %LOCALAPPDATA%\\Jobwatch
To back up, stop Jobwatch (Settings > Background) and copy that entire data folder. Keep it when
updating or reinstalling Jobwatch. Do not send that data folder to
someone else. No Discord or Telegram notifications are connected by default.

IF IT DOES NOT START
This package is for 64-bit Windows, not macOS or Linux. The installer shows startup
errors in a message box; the ZIP leaves them in the start window. Details are
written to %LOCALAPPDATA%\\Jobwatch\\jobwatch.log. For the ZIP, extract the entire
archive and keep app and runtime beside Start Jobwatch.bat. For the installed app,
try running Setup again; it keeps your data. For a visible troubleshooting window,
open Command Prompt in the program folder and run:
    runtime\\python.exe app\\portable_start.py --console

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
        "sources_version": 6,
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
    for folder, suffixes in (("intel", {".py"}), ("web", {".html", ".js", ".css", ".svg", ".ico", ".woff2", ".txt"})):
        for path in (source / folder).rglob("*"):
            if (path.is_file() and path.suffix in suffixes
                    and not {"tests", "__pycache__", "preview"}.intersection(path.relative_to(source).parts)
                    and path.name != "preview.html"):
                target = app / path.relative_to(source)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    original = json.loads((source / "config.json").read_text(encoding="utf-8"))
    cleaned = clean_config(original)
    # Record this release's source defaults so later upgrades recognise them as unedited.
    from tools.source_history import load_history, record_release, save_history
    history_path = source / "config" / "source_defaults_history.json"
    save_history(record_release(load_history(history_path), cleaned["boards"], cleaned["sources_version"]), history_path)
    (app / "config").mkdir()
    for name in KNOWLEDGE:
        shutil.copyfile(source / "config" / name, app / "config" / name)
    (app / "config.json").write_text(json.dumps(cleaned, indent=2) + "\n", encoding="utf-8")
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


def find_iscc(explicit: Path | None = None) -> Path:
    """Inno Setup's compiler: --iscc, $ISCC, or a standard install location."""
    candidates = [explicit, os.environ.get("ISCC"),
                  Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6/ISCC.exe",
                  Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6/ISCC.exe",
                  Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Inno Setup 6/ISCC.exe"]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    raise FileNotFoundError("Inno Setup 6 (ISCC.exe) not found; pass --iscc or set ISCC")


def make_test_build(stage: Path, version: str | None, key_file: Path | None) -> None:
    """Update tests only: another version number, and/or a test signing key with
    a local update feed allowed (JOBWATCH_UPDATE_FEED). Never used for releases."""
    app = stage / "app"
    if version:
        (app / "version.py").write_text(f'APP_VERSION = "{version}"\n', encoding="utf-8")
    if key_file:
        sys.path.insert(0, str(ROOT / "tools"))
        from sign_release import load_key, public_key_text
        public = public_key_text(load_key(key_file.read_bytes()))
        (app / "update_key.py").write_text(
            '"""TEST BUILD: test signing key and local update feed."""\n\n'
            f'PUBLIC_KEY = "{public}"\nALLOW_FEED_OVERRIDE = True\n', encoding="utf-8")


def build_installer(stage: Path, output_dir: Path, iscc: Path, version: str = APP_VERSION) -> Path:
    """Compile tools/jobwatch.iss over the staged folder into Jobwatch-Setup-<version>.exe."""
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(iscc), "/Q", f"/DAppVersion={version}", f"/DStageDir={stage}",
                    f"/DOutputDir={output_dir}", str(ROOT / "tools/jobwatch.iss")], check=True)
    setup = output_dir / f"Jobwatch-Setup-{version}.exe"
    print(f"Ready: {setup} ({setup.stat().st_size / 1024 / 1024:.1f} MB)")
    return setup


def build(output: Path, installer: bool = False, iscc: Path | None = None, zip_bundle: bool = True,
          version: str | None = None, update_key_file: Path | None = None) -> Path:
    cache = ROOT / ".build-cache"
    cache.mkdir(exist_ok=True)
    archive = runtime_archive(cache)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="windows-", dir=cache) as temporary:
        stage = Path(temporary) / "Jobwatch"
        stage_app(ROOT, stage)
        make_test_build(stage, version, update_key_file)
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
        if installer:
            build_installer(stage, output.parent, find_iscc(iscc), version or APP_VERSION)
        if zip_bundle:
            temporary_zip = output.with_suffix(".building.zip")
            with zipfile.ZipFile(temporary_zip, "w", zipfile.ZIP_DEFLATED) as bundle:
                for path in bundle_files(stage):
                    bundle.write(path, "Jobwatch/" + path.relative_to(stage).as_posix())
            temporary_zip.replace(output)
            print(f"Ready: {output} ({output.stat().st_size / 1024 / 1024:.1f} MB)")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist/Jobwatch-Windows.zip",
                        help="the ZIP; the installer is written beside it")
    parser.add_argument("--installer", action="store_true", help="also build Jobwatch-Setup-<version>.exe")
    parser.add_argument("--no-zip", action="store_true", help="skip the portable ZIP")
    parser.add_argument("--iscc", type=Path, help="path to Inno Setup's ISCC.exe")
    parser.add_argument("--version", help="TEST BUILDS ONLY: build as this version")
    parser.add_argument("--update-key-file", type=Path,
                        help="TEST BUILDS ONLY: trust this signing key and allow a local update feed")
    args = parser.parse_args()
    build(args.output.resolve(), installer=args.installer, iscc=args.iscc, zip_bundle=not args.no_zip,
          version=args.version, update_key_file=args.update_key_file)
