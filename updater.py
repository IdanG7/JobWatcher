"""Over-the-air updates for the installed Windows app.

The latest GitHub release carries three files: the installer, a manifest
(``jobwatch-update.json``: version, installer name, size, sha256) and the
manifest's ed25519 signature (``jobwatch-update.json.sig``). An update is
downloaded only when the signature checks out against update_key.PUBLIC_KEY,
the manifest names the release's own tag and the version is newer than this
one, so a tampered, replayed or older release is never installed. The
installer is kept in ``<data>/updates`` and checked again right before it runs.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from urllib.parse import urlparse

import requests

import update_key
from version import APP_VERSION

RELEASES_API = "https://api.github.com/repos/IdanG7/JobWatcher/releases/latest"
MANIFEST = "jobwatch-update.json"
SIGNATURE = MANIFEST + ".sig"
TRUSTED_HOSTS = ("github.com", "api.github.com", "objects.githubusercontent.com",
                 "release-assets.githubusercontent.com")
MAX_SMALL = 64 * 1024            # release JSON, manifest and signature
MAX_INSTALLER = 250 * 1024 * 1024
CHECK_EVERY = 6 * 3600
RETRY_AFTER = 3600               # offline, rate-limited or a failed download
INSTALLER_NAME = re.compile(r"Jobwatch-Setup-\d+(?:\.\d+){1,3}\.exe")


class UpdateError(Exception):
    pass


def version_key(version: str) -> tuple[int, ...]:
    parts = str(version).strip().lstrip("v").split(".")
    if not 1 <= len(parts) <= 4 or not all(p.isdigit() for p in parts):
        raise UpdateError(f"not a version: {version!r}")
    return tuple(int(p) for p in parts)


def verify_manifest(manifest: bytes, signature: bytes, public_key: str = update_key.PUBLIC_KEY) -> dict:
    """The manifest's contents, only if ``signature`` is a valid ed25519 signature of it."""
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    try:
        key = Ed25519PublicKey.from_public_bytes(base64.b64decode(public_key, validate=True))
        key.verify(base64.b64decode(signature.strip(), validate=True), manifest)
    except (InvalidSignature, ValueError) as exc:
        raise UpdateError("the update's signature is not valid") from exc
    try:
        data = json.loads(manifest)
        version_key(data["version"])
        if not INSTALLER_NAME.fullmatch(data["installer"]):
            raise ValueError("installer name")
        if not (isinstance(data["size"], int) and 0 < data["size"] <= MAX_INSTALLER):
            raise ValueError("size")
        if not re.fullmatch(r"[0-9a-f]{64}", data["sha256"]):
            raise ValueError("sha256")
    except (ValueError, KeyError, TypeError) as exc:
        raise UpdateError(f"the update manifest is malformed ({exc})") from exc
    return data


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Updater:
    def __init__(self, data_dir: Path, current: str = APP_VERSION, session=None,
                 public_key: str = update_key.PUBLIC_KEY, feed: str | None = None,
                 allow_local: bool = update_key.ALLOW_FEED_OVERRIDE):
        self.dir = Path(data_dir) / "updates"
        self.current = current
        self.session = session or requests.Session()
        self.public_key = public_key
        # Only test builds may use a feed on this computer (plain http to 127.0.0.1).
        self.local_feed = allow_local
        self.feed = feed or (os.environ.get("JOBWATCH_UPDATE_FEED") if allow_local else None) or RELEASES_API
        self._lock = threading.Lock()
        self._checking = threading.Lock()      # the 6-hourly loop and "Check for updates" take turns
        self._stop = threading.Event()
        self.state = {"state": "idle", "current": current, "latest": None, "error": None,
                      "release_url": None, "checked_at": None}
        self._ready: dict | None = None

    # ---------------------------------------------------------------- network
    def _get(self, url: str, limit: int, stream_to: Path | None = None):
        """GET over HTTPS from GitHub only (every redirect hop included), size-capped."""
        def trusted(u: str) -> bool:
            parsed = urlparse(u)
            if self.local_feed and parsed.scheme == "http" and parsed.hostname == "127.0.0.1":
                return True
            return parsed.scheme == "https" and parsed.hostname in TRUSTED_HOSTS
        if not trusted(url):
            raise UpdateError(f"refusing to download from {urlparse(url).hostname}")
        headers = {"Accept": "application/vnd.github+json"} if url == self.feed else {}
        with self.session.get(url, timeout=30, stream=True, headers=headers) as response:
            for hop in [*response.history, response]:
                if not trusted(hop.url):
                    raise UpdateError(f"refusing a redirect to {urlparse(hop.url).hostname}")
            response.raise_for_status()
            declared = response.headers.get("Content-Length")
            if declared and declared.isdigit() and int(declared) > limit:
                raise UpdateError("download larger than expected")
            received = 0
            if stream_to is None:
                body = bytearray()
                for chunk in response.iter_content(65536):
                    received += len(chunk)
                    if received > limit:
                        raise UpdateError("download larger than expected")
                    body += chunk
                return bytes(body)
            with stream_to.open("wb") as output:
                for chunk in response.iter_content(1 << 20):
                    received += len(chunk)
                    if received > limit or self._stop.is_set():
                        raise UpdateError("download larger than expected" if received > limit else "stopped")
                    output.write(chunk)
            return received

    # ---------------------------------------------------------------- checking
    def _set(self, **changes) -> None:
        with self._lock:
            self.state.update(changes)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self.state)

    def check_now(self) -> dict:
        """Check in the background at once (Settings); returns the state to poll."""
        with self._lock:
            start = self.state["state"] in ("idle", "manual", "failed")
            if start:
                self.state.update(state="checking", error=None)
        if start:
            threading.Thread(target=self.check, name="jobwatch-update-check", daemon=True).start()
        return self.snapshot()

    def check(self) -> dict:
        """Find, verify and download a newer release; returns the new state."""
        with self._checking:
            return self._check()

    def _check(self) -> dict:
        self._set(state="checking", error=None)
        try:
            release = json.loads(self._get(self.feed, MAX_SMALL))
            tag = str(release.get("tag_name") or "").lstrip("v")
            version_key(tag)
            release_url = str(release.get("html_url") or "")
            if version_key(tag) <= version_key(self.current):
                self._set(state="idle", latest=tag, checked_at=time.time())
                return self.snapshot()
            assets = {a.get("name"): a.get("browser_download_url") for a in release.get("assets") or []
                      if isinstance(a, dict)}
            if not (assets.get(MANIFEST) and assets.get(SIGNATURE)):
                # A release from before in-app updates: link to it instead.
                self._set(state="manual", latest=tag, release_url=release_url, checked_at=time.time())
                return self.snapshot()
            manifest = verify_manifest(self._get(assets[MANIFEST], MAX_SMALL),
                                       self._get(assets[SIGNATURE], 1024), self.public_key)
            if manifest["version"].lstrip("v") != tag:
                raise UpdateError("the update manifest belongs to another release")
            if not assets.get(manifest["installer"]):
                raise UpdateError("the release is missing its installer")
            self._set(latest=tag, release_url=release_url)
            installer = self._download(manifest, assets[manifest["installer"]])
            with self._lock:
                self._ready = {**manifest, "path": installer}
                self.state.update(state="ready", checked_at=time.time())
        except (UpdateError, requests.RequestException, ValueError, OSError) as exc:
            self._set(state="failed", error=str(exc)[:300], checked_at=time.time())
        return self.snapshot()

    def _download(self, manifest: dict, url: str) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        target = self.dir / manifest["installer"]
        for old in self.dir.glob("Jobwatch-Setup-*"):     # earlier updates and broken downloads
            if old != target:
                old.unlink(missing_ok=True)
        if target.exists() and target.stat().st_size == manifest["size"] \
                and sha256_file(target) == manifest["sha256"]:
            return target                                  # downloaded before a restart
        self._set(state="downloading")
        partial = target.with_name(target.name + ".part")
        try:
            size = self._get(url, manifest["size"], stream_to=partial)
            if size != manifest["size"] or sha256_file(partial) != manifest["sha256"]:
                raise UpdateError("the downloaded installer does not match the signed manifest")
            partial.replace(target)
        finally:
            partial.unlink(missing_ok=True)
        return target

    # ---------------------------------------------------------------- applying
    def installer_command(self, log: Path) -> list[str]:
        """The verified installer to run silently; re-checked now, since it sat on disk."""
        with self._lock:
            ready = dict(self._ready) if self._ready else None
        if not ready:
            raise UpdateError("no update is ready")
        path = Path(ready["path"])
        if not path.is_file() or path.stat().st_size != ready["size"] or sha256_file(path) != ready["sha256"]:
            self._set(state="failed", error="the downloaded update changed on disk; it will be downloaded again")
            path.unlink(missing_ok=True)
            with self._lock:
                self._ready = None
            raise UpdateError("the downloaded update changed on disk")
        return [str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1", f"/LOG={log}"]

    def apply(self) -> None:
        """Start the installer detached; the caller then stops this server so its files are free."""
        command = self.installer_command(self.dir / "install.log")
        flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                 | getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0))
        quiet = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
                 "close_fds": True, "cwd": str(self.dir)}
        try:
            subprocess.Popen(command, creationflags=flags, **quiet)
        except OSError:      # not allowed to leave the job object
            subprocess.Popen(command, creationflags=flags & ~getattr(subprocess, "CREATE_BREAKAWAY_FROM_JOB", 0),
                             **quiet)
        self._set(state="installing")

    # ---------------------------------------------------------------- background
    def start(self, first_delay: float | None = None) -> None:
        """Check a minute after startup (test builds: at once), then every 6 hours."""
        def loop():
            wait = first_delay if first_delay is not None else (2 if self.local_feed else 60)
            while not self._stop.wait(wait):
                state = self.check()["state"]
                if state == "ready":
                    return              # nothing more to do until the user restarts
                wait = RETRY_AFTER if state == "failed" else CHECK_EVERY
        threading.Thread(target=loop, name="jobwatch-updates", daemon=True).start()

    def stop(self) -> None:
        self._stop.set()
