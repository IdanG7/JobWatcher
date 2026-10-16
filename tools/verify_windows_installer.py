"""Install, start, upgrade in place and uninstall the real Setup exe.

Everything runs against a temporary install folder and a temporary
%LOCALAPPDATA%, so a copy the developer already runs keeps its program and
data. The Start menu entry is this account's real one: it is replaced, then
removed by the uninstall.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent


def wait_for(check, seconds: float, what: str):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(0.25)
    raise AssertionError(f"timed out waiting for {what}")


def status(url: str) -> dict | None:
    try:
        with urlopen(url + "/api/status", timeout=3) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


def instance(data: Path) -> dict | None:
    try:
        state = json.loads((data / "instance.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return state if status(state["url"]) else None


@contextmanager
def installed(install: Path, env: dict):
    """Always uninstall a test copy, even when a check fails or is interrupted:
    that stops it and removes its Start menu shortcut and uninstall entry."""
    try:
        yield
    finally:
        uninstaller = install / "unins000.exe"
        if uninstaller.is_file():
            try:
                subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                               env=env, timeout=120)
                wait_for(lambda: not uninstaller.exists(), 120, "the test copy to be uninstalled")
            except (OSError, subprocess.SubprocessError, AssertionError) as exc:
                print(f"! could not uninstall the test copy in {install}: {exc}", flush=True)


def setup(installer: Path, install: Path, env: dict, *extra: str) -> None:
    subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                    f"/DIR={install}", *extra], env=env, check=True, timeout=300)


def verify(installer: Path) -> None:
    cache = ROOT / ".build-cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="verify installer & (setup)-", dir=cache) as temporary:
        root = Path(temporary)
        install, local = root / "Programs" / "Jobwatch", root / "LocalAppData"
        data = local / "Jobwatch"
        env = {**os.environ, "LOCALAPPDATA": str(local), "JOBWATCH_NO_AUTOSTART": "1", "JOBWATCH_NO_UPDATES": "1"}
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)
        start_menu = Path(os.environ["APPDATA"]) / "Microsoft/Windows/Start Menu/Programs"
        shortcut, old_shortcut = start_menu / "Foothold.lnk", start_menu / "Jobwatch.lnk"

        with installed(install, env):
            # 1. Fresh install: program files only, no data, nothing running. A Start
            #    menu entry from a release named Jobwatch is replaced, not duplicated.
            planted = not old_shortcut.exists()
            old_shortcut.touch()
            try:
                setup(installer, install, env)
                assert not old_shortcut.exists(), "the old Jobwatch shortcut must be removed"
            finally:
                if planted:
                    old_shortcut.unlink(missing_ok=True)
            pythonw, launcher = install / "runtime/pythonw.exe", install / "app/portable_start.py"
            # jobwatch.ico: taskbar pins of the old shortcut still point at that name.
            for path in (pythonw, launcher, install / "app/web/foothold.ico", install / "app/web/jobwatch.ico",
                         install / "unins000.exe", install / "READ ME FIRST.txt", shortcut):
                assert path.is_file(), path
            assert not data.exists(), "installing must not create user data"

            # 2. Start it the way the Start menu shortcut does: no window, server in the background.
            subprocess.run([str(pythonw), str(launcher), "--no-browser"], env=env, cwd=install, timeout=120)
            first = wait_for(lambda: instance(data), 120, "the first start")
            with urlopen(first["url"] + "/api/background", timeout=5) as response:
                assert json.load(response)["installed"], "installed copies must show Start menu instructions"
            port = int(first["url"].rsplit(":", 1)[1])
            assert (data / "config.json").is_file() and (data / "jobwatch.db").is_file()
            print(f"installed copy serving {first['url']} (pid {first['pid']})", flush=True)

            # 3. Upgrade over the running copy, as an in-app update does: stopped,
            #    replaced, relaunched on the same port with the data kept.
            marker = data / "kept.txt"
            marker.write_text("user data", encoding="utf-8")
            setup(installer, install, env, "/RELAUNCH=1")
            second = wait_for(lambda: (s := instance(data)) and s["pid"] != first["pid"] and s, 120, "the relaunch")
            assert second["url"] == first["url"], (first["url"], second["url"])
            assert marker.read_text(encoding="utf-8") == "user data"
            print(f"upgrade relaunched on port {port} (pid {second['pid']})", flush=True)

            # 4. Uninstall: Foothold stopped, program folder and shortcut gone, data kept.
            log = root / "uninstall.log"
            subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                            f"/LOG={log}"], env=env, check=True, timeout=120)
            try:
                wait_for(lambda: not install.exists(), 120, "the program folder to be removed")
            except AssertionError:
                left = sorted(str(p.relative_to(install)) for p in install.rglob("*"))[:20]
                print("left behind:", *left, sep="\n  ")
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines() if log.exists() else []
                print(*[line for line in lines if "Deleting" not in line and "Failed to delete" not in line][:60],
                      sep="\n")
                raise
            wait_for(lambda: status(second["url"]) is None, 30, "Foothold to stop")
            assert marker.is_file() and (data / "jobwatch.db").is_file(), "uninstall must keep user data"
            assert not shortcut.exists(), "uninstall must remove the Start menu shortcut"
            print("uninstall removed the program and kept the data", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    verify(parser.parse_args().installer.resolve())
    print("Installer verified.")
