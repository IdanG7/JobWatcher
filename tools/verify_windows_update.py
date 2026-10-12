"""End-to-end in-app update: version N updates itself to N+1.

Builds two test installers that trust a throwaway signing key (never the
release key), serves N+1 from a local stand-in for GitHub's release API,
installs N into a temporary folder with a temporary %LOCALAPPDATA%, waits
for the app to download and verify N+1, clicks "Restart to update" through
the API and checks that N+1 comes back on the same address with the data kept.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from build_windows import build                                      # noqa: E402
from sign_release import sign                                        # noqa: E402
from verify_windows_installer import installed, instance, setup, status, wait_for   # noqa: E402
from version import APP_VERSION                                      # noqa: E402


def next_version(version: str) -> str:
    parts = [int(p) for p in version.split(".")]
    parts[-1] += 1
    return ".".join(map(str, parts))


def feed_server(release_dir: Path, version: str) -> ThreadingHTTPServer:
    class Feed(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            base = f"http://127.0.0.1:{self.server.server_port}"
            if self.path == "/latest":
                names = [p.name for p in release_dir.iterdir()]
                body = json.dumps({"tag_name": f"v{version}",
                                   "html_url": f"https://github.com/IdanG7/JobWatcher/releases/tag/v{version}",
                                   "assets": [{"name": n, "browser_download_url": f"{base}/dl/{n}"}
                                              for n in names]}).encode()
            elif self.path.startswith("/dl/") and (release_dir / self.path[4:]).is_file():
                body = (release_dir / self.path[4:]).read_bytes()
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Feed)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def verify(iscc: Path | None) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    cache = ROOT / ".build-cache"
    cache.mkdir(exist_ok=True)
    newer = next_version(APP_VERSION)
    with tempfile.TemporaryDirectory(prefix="verify update & (ota)-", dir=cache) as temporary:
        root = Path(temporary)
        key_file = root / "test-key.pem"
        key_file.write_bytes(Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        old_dir, new_dir = root / "old", root / "new"
        build(old_dir / "unused.zip", installer=True, iscc=iscc, zip_bundle=False, update_key_file=key_file)
        build(new_dir / "unused.zip", installer=True, iscc=iscc, zip_bundle=False, version=newer,
              update_key_file=key_file)
        sign(new_dir / f"Jobwatch-Setup-{newer}.exe", key_file.read_bytes())
        feed = feed_server(new_dir, newer)

        install, local = root / "Programs" / "Jobwatch", root / "LocalAppData"
        data = local / "Jobwatch"
        env = {**os.environ, "LOCALAPPDATA": str(local), "JOBWATCH_NO_AUTOSTART": "1",
               "JOBWATCH_UPDATE_FEED": f"http://127.0.0.1:{feed.server_port}/latest"}
        env.pop("JOBWATCH_NO_UPDATES", None)
        try:
            with installed(install, env):
                setup(old_dir / f"Jobwatch-Setup-{APP_VERSION}.exe", install, env)
                subprocess.run([str(install / "runtime/pythonw.exe"), str(install / "app/portable_start.py"), "--no-browser"],
                               env=env, cwd=install, timeout=120)
                first = wait_for(lambda: instance(data), 120, "version N to start")
                url = first["url"]
                assert status(url)["version"] == APP_VERSION
                (data / "kept.txt").write_text("user data", encoding="utf-8")

                def update_state():
                    with urlopen(url + "/api/update", timeout=5) as response:
                        info = json.load(response)
                    assert info["state"] != "failed", info
                    return info if info["state"] == "ready" else None
                info = wait_for(update_state, 180, "the update to download")
                assert info["latest"] == newer, info
                print(f"{APP_VERSION} downloaded and verified {newer}", flush=True)

                request = Request(url + "/api/update/apply", data=b"{}", method="POST",
                                  headers={"Content-Type": "application/json", "Origin": url})
                with urlopen(request, timeout=10) as response:
                    assert json.load(response) == {"ok": True}
                after = wait_for(lambda: (s := status(url)) and s.get("version") == newer and s, 240,
                                 f"{newer} to answer on {url}")
                assert (data / "kept.txt").read_text(encoding="utf-8") == "user data"
                assert (install / "unins000.exe").is_file()
                log = data / "updates/install.log"
                assert log.is_file(), "the installer log is kept for troubleshooting"
                print(f"updated in place to {after['version']} on {url}", flush=True)

                subprocess.run([str(install / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                               env=env, check=True, timeout=120)
                wait_for(lambda: not install.exists(), 120, "the program folder to be removed")
        finally:
            feed.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iscc", type=Path)
    verify(parser.parse_args().iscc)
    print("In-app update verified.")
