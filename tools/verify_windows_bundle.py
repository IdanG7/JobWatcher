"""Exercise the actual ZIP and batch file without an installed Python on PATH."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def verify(bundle: Path, resume: Path | None = None) -> None:
    cache = ROOT / ".build-cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verify friend & (portable)-", dir=cache) as temporary:
        fixture = Path(temporary)
        with zipfile.ZipFile(bundle) as archive:
            for member in archive.namelist():
                assert (fixture / member).resolve().is_relative_to(fixture.resolve())
                assert str(Path.home()).lower().encode() not in archive.read(member).lower(), member
                assert "/site-packages/bin/" not in member, member
            archive.extractall(fixture)
        app = fixture / "Jobwatch"
        manifest = json.loads((app / "manifest.json").read_text())
        for name, digest in manifest["files"].items():
            assert hashlib.sha256((app / name).read_bytes()).hexdigest() == digest, name
        assert not list(app.rglob("*.db"))
        assert json.loads((app / "app/subscribers.json").read_text()) == {}
        config = json.loads((app / "app/config.json").read_text())
        assert config["profile"]["skills"] == []
        assert config["profile"]["graduation_year"] is None
        assert not config["healthcheck_url"]
        runtime = app / "runtime/python.exe"
        env = {**os.environ, "JOBWATCH_NO_AUTOSTART": "1",   # never move the real sign-in start
               "PATH": str(Path(os.environ["SystemRoot"]) / "System32"),
               "PYTHONHOME": "Z:\\no-global-python", "PYTHONPATH": "Z:\\no-global-packages"}
        isolated = subprocess.check_output([str(runtime), "-c",
            "import sys,requests,pypdf,watcher,sqlite3; print(sys.executable); print(requests.__file__); print(pypdf.__file__); print(watcher.__file__); c=sqlite3.connect(':memory:'); c.execute('CREATE VIRTUAL TABLE f USING fts5(body)'); c.close()"],
            env=env, text=True)
        for path in isolated.splitlines():
            assert Path(path).resolve().is_relative_to(app.resolve()), path
        data = fixture / "friend data"
        data.mkdir()
        # Exercise automatic polling safely with no external sources in this test.
        config["boards"] = {}
        (data / "config.json").write_text(json.dumps(config), encoding="utf-8")
        batch = app / "Start Jobwatch.bat"
        command = f'cmd.exe /d /c ""{batch}" --data-dir "{data}" --no-browser"'
        log = fixture / "startup.log"

        def launch():
            # The batch file starts a windowless server, waits for it and exits.
            output = log.open("ab")
            launcher = subprocess.run(command, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
            output.close()
            assert launcher.returncode == 0, log.read_text(encoding="utf-8")
            pid = json.loads((data / "instance.json").read_text())["pid"]
            image = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], text=True,
                                            creationflags=subprocess.CREATE_NO_WINDOW)
            assert "pythonw.exe" in image.lower(), image
            return pid

        def stop(pid):
            if pid is None:
                return
            try:
                request = Request(json.loads((data / "instance.json").read_text())["url"] + "/api/shutdown",
                                  data=b"{}", method="POST", headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=5):
                    pass
                deadline = time.monotonic() + 15
                while (data / "instance.json").exists() and time.monotonic() < deadline:
                    time.sleep(0.1)
                assert not (data / "instance.json").exists(), "shutdown did not stop the server"
            finally:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True,
                               creationflags=subprocess.CREATE_NO_WINDOW)

        def ready(pid):
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                try:
                    url = json.loads((data / "instance.json").read_text())["url"]
                    with urlopen(url + "/api/status", timeout=2) as response:
                        if json.load(response)["last_poll"]:
                            return url
                except (OSError, ValueError, KeyError):
                    pass
                time.sleep(0.1)
            raise AssertionError("Startup timed out: " + log.read_text(encoding="utf-8"))

        process = None
        try:
            process = launch()
            url = ready(process)

            def api(path, body=None, method="GET"):
                request = Request(url + path, method=method,
                    data=None if body is None else json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"})
                with urlopen(request, timeout=15) as response:
                    return json.load(response)

            with urlopen(url, timeout=5) as response:
                html = response.read()
                assert b"collection-status" in html and b"Loading your dashboard" in html
            for module in ("start.js", "app.js", "view-loader.js", "collection-status.js"):
                with urlopen(url + "/js/" + module, timeout=5) as response:
                    assert response.status == 200 and "javascript" in response.headers["Content-Type"]
            progress = api("/api/status")["progress"]
            assert progress["phase"] == "complete" and progress["total"] == 0, progress
            assert not api("/api/resume")["available"]
            profile = api("/api/profile")["profile"]
            assert profile["skills"] == [] and profile["graduation_year"] is None
            profile["target_roles"] = ["investment_banking"]
            profile["alerts"]["high_fit"] = 90
            api("/api/profile", profile, "PUT")
            assert api("/api/overview")["profile"]["alerts"]["high_fit"] == 90
            seed = """import sys,json,watcher
from pathlib import Path
from intel_store import IntelStore
d=Path(sys.argv[1]); c=watcher.db_open(d/'jobwatch.db'); ts=watcher.now()
c.execute('INSERT INTO jobs(board,job_id,title,location,url,first_seen,last_seen) VALUES (?,?,?,?,?,?,?)',('rbc','portable-test','2027 Investment Banking Summer Analyst','Toronto, Ontario, Canada','https://example.com/job',ts,ts))
c.execute('INSERT INTO job_details(board,job_id,company,salary) VALUES (?,?,?,?)',('rbc','portable-test','RBC',''))
watcher.store_description(c,'rbc','portable-test','Summer 2027 internship. Undergraduate students graduating April 2028. Valuation, financial modeling and Excel.')
c.commit(); IntelStore(c,json.loads((d/'config.json').read_text())).refresh(force_score=True); c.close()
"""
            subprocess.run([str(runtime), "-c", seed, str(data)], env=env, check=True, capture_output=True)
            synthetic = """Education
University of Toronto - Bachelor of Commerce
Expected graduation April 2028 | GPA: 3.92/4.0
Technical Skills
Excel, valuation, DCF, accounting, financial modeling
Experience
Treasury Analyst | Example Company | May 2026 - August 2026
Built cash flow forecasts and financial reports.
"""
            payload = ({"filename": "test-resume.pdf", "data": base64.b64encode(resume.read_bytes()).decode()}
                       if resume else {"text": synthetic})
            preview = api("/api/resume/parse", payload, "POST")
            assert preview["profile"]["graduation_year"] == 2028
            assert "corporate_finance.treasury" in preview["profile"]["target_roles"], preview["profile"]["target_roles"]
            assert not api("/api/resume")["available"]
            api("/api/resume", payload, "POST")
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                jobs = api("/api/jobs")
                if jobs["total"] == 1 and jobs["resume_matching"]["active"]:
                    break
                time.sleep(0.1)
            assert jobs["total"] == 1 and jobs["resume_matching"]["active"], jobs
            duplicate = subprocess.run(command, env=env, capture_output=True, timeout=10,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
            assert duplicate.returncode == 0, duplicate.stdout + duplicate.stderr
            assert b"already running" in duplicate.stdout
            stop(process)
            process = None
            process = launch()
            url = ready(process)
            assert api("/api/resume")["enabled"]
            assert api("/api/profile")["profile"]["graduation_year"] == 2028
        finally:
            stop(process)
        print("PASS: ZIP checksums, isolated runtime, windowless batch startup, automatic polling/progress, loading shell,")
        print("clean profile, resume upload/apply/matching, duplicate starts, shutdown and restart persistence.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--resume", type=Path, help="optional local test PDF; never added to the ZIP")
    args = parser.parse_args()
    verify(args.bundle.resolve(), args.resume)
