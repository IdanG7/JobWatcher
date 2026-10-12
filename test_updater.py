"""In-app updates install only signed, newer releases from GitHub."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import updater
from updater import MANIFEST, RELEASES_API, SIGNATURE, UpdateError, Updater, verify_manifest
from sign_release import sign

API = RELEASES_API
DL = "https://github.com/IdanG7/JobWatcher/releases/download/v0.2.1/"
CDN = "https://release-assets.githubusercontent.com/x/"


def pem(key):
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def public(key):
    return base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw,
                                                          serialization.PublicFormat.Raw)).decode()


class Response:
    def __init__(self, url, body=b"", status=200, history=(), headers=None):
        self.url, self.body, self.status_code = url, body, status
        self.history = [Response(u) for u in history]
        self.headers = headers or {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]


class FakeGitHub:
    """GitHub's latest-release API plus asset downloads (redirected to the CDN)."""

    def __init__(self):
        self.files, self.redirect, self.requests = {}, CDN, []
        self.release = None

    def get(self, url, **kwargs):
        self.requests.append(url)
        if url == API:
            return Response(url, json.dumps(self.release).encode())
        name = url.rsplit("/", 1)[1]
        if url.startswith(DL) and name in self.files:
            return Response(self.redirect + name, self.files[name], history=[url])
        return Response(url, b"", status=404)


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.key = Ed25519PrivateKey.generate()
        self.github = FakeGitHub()

    def publish(self, version="0.2.1", tag=None, key=None, installer=b"MZ fake installer" * 100, extra=None):
        name = f"Jobwatch-Setup-{version}.exe"
        folder = self.root / "release"
        folder.mkdir(exist_ok=True)
        (folder / name).write_bytes(installer)
        manifest, signature = sign(folder / name, pem(key or self.key))
        self.github.files = {name: installer, MANIFEST: manifest.read_bytes(), SIGNATURE: signature.read_bytes(),
                             **(extra or {})}
        self.github.release = {"tag_name": f"v{tag or version}",
                               "html_url": f"https://github.com/IdanG7/JobWatcher/releases/tag/v{tag or version}",
                               "assets": [{"name": n, "browser_download_url": DL + n} for n in self.github.files]}
        return installer

    def updater(self, current="0.2.0"):
        return Updater(self.root / "data", current=current, session=self.github, public_key=public(self.key))

    def test_signed_newer_release_is_downloaded_and_ready(self):
        installer = self.publish()
        u = self.updater()
        state = u.check()
        self.assertEqual(state["state"], "ready", state)
        self.assertEqual(state["latest"], "0.2.1")
        path = self.root / "data/updates/Jobwatch-Setup-0.2.1.exe"
        self.assertEqual(path.read_bytes(), installer)
        command = u.installer_command(self.root / "log.txt")
        self.assertEqual(command[0], str(path))
        self.assertIn("/VERYSILENT", command)
        self.assertIn("/RELAUNCH=1", command)

    def test_same_or_older_release_does_nothing(self):
        for current in ("0.2.1", "0.3.0"):
            self.publish()
            self.github.requests.clear()
            state = self.updater(current).check()
            self.assertEqual(state["state"], "idle")
            self.assertEqual(self.github.requests, [API])      # nothing else downloaded

    def test_release_signed_with_another_key_is_rejected(self):
        self.publish(key=Ed25519PrivateKey.generate())
        state = self.updater().check()
        self.assertEqual(state["state"], "failed")
        self.assertIn("signature", state["error"])
        self.assertFalse(list((self.root / "data").rglob("*.exe")))

    def test_tampered_installer_is_rejected(self):
        self.publish()
        self.github.files["Jobwatch-Setup-0.2.1.exe"] = b"MZ evil installer" * 100
        state = self.updater().check()
        self.assertEqual(state["state"], "failed")
        self.assertFalse(list((self.root / "data").rglob("*.exe")))

    def test_tampered_manifest_is_rejected(self):
        self.publish()
        manifest = json.loads(self.github.files[MANIFEST])
        manifest["sha256"] = hashlib.sha256(b"other").hexdigest()
        self.github.files[MANIFEST] = json.dumps(manifest).encode()
        self.assertEqual(self.updater().check()["state"], "failed")

    def test_old_signed_manifest_replayed_under_a_new_tag_is_rejected(self):
        self.publish(version="0.2.1", tag="0.9.0")
        state = self.updater().check()
        self.assertEqual(state["state"], "failed")
        self.assertIn("another release", state["error"])

    def test_downloads_only_from_github(self):
        self.publish()
        self.github.redirect = "https://evil.example.com/"
        state = self.updater().check()
        self.assertEqual(state["state"], "failed")
        self.assertIn("evil.example.com", state["error"])
        self.github.redirect = "http://release-assets.githubusercontent.com/"     # not HTTPS
        self.assertEqual(self.updater().check()["state"], "failed")

    def test_local_feeds_need_a_test_build(self):
        with patch.dict("os.environ", {"JOBWATCH_UPDATE_FEED": "http://127.0.0.1:9/latest"}):
            self.assertEqual(Updater(self.root, allow_local=False).feed, API)
            self.assertEqual(Updater(self.root, allow_local=True).feed, "http://127.0.0.1:9/latest")
        self.assertFalse(updater.update_key.ALLOW_FEED_OVERRIDE)

    def test_oversized_downloads_stop(self):
        self.publish()
        manifest = json.loads(self.github.files[MANIFEST])
        self.github.files["Jobwatch-Setup-0.2.1.exe"] += b"x" * 10      # longer than signed
        self.assertEqual(manifest["size"] + 10, len(self.github.files["Jobwatch-Setup-0.2.1.exe"]))
        state = self.updater().check()
        self.assertEqual(state["state"], "failed")
        self.assertFalse(list((self.root / "data").rglob("*.part")))

    def test_release_without_update_files_links_to_the_page(self):
        self.github.release = {"tag_name": "v0.2.1", "assets": [],
                               "html_url": "https://github.com/IdanG7/JobWatcher/releases/tag/v0.2.1"}
        state = self.updater().check()
        self.assertEqual(state["state"], "manual")
        self.assertTrue(state["release_url"].endswith("v0.2.1"))

    def test_offline_is_a_quiet_failure(self):
        class Offline:
            def get(self, *a, **k):
                import requests
                raise requests.ConnectionError("no network")
        state = Updater(self.root, current="0.2.0", session=Offline(), public_key=public(self.key)).check()
        self.assertEqual(state["state"], "failed")

    def test_a_verified_download_is_reused_and_old_ones_removed(self):
        self.publish()
        updates = self.root / "data/updates"
        updates.mkdir(parents=True)
        (updates / "Jobwatch-Setup-0.1.9.exe").write_bytes(b"old")
        self.assertEqual(self.updater().check()["state"], "ready")
        self.assertFalse((updates / "Jobwatch-Setup-0.1.9.exe").exists())
        self.github.requests.clear()
        self.assertEqual(self.updater().check()["state"], "ready")
        self.assertNotIn(DL + "Jobwatch-Setup-0.2.1.exe", self.github.requests)

    def test_installer_changed_on_disk_is_not_run(self):
        self.publish()
        u = self.updater()
        u.check()
        (self.root / "data/updates/Jobwatch-Setup-0.2.1.exe").write_bytes(b"MZ swapped" * 170)
        with self.assertRaises(UpdateError):
            u.installer_command(self.root / "log.txt")
        self.assertEqual(u.snapshot()["state"], "failed")

    def test_manifest_fields_are_validated(self):
        def signed(data):
            body = json.dumps(data).encode()
            return body, base64.b64encode(self.key.sign(body))
        good = {"version": "0.2.1", "installer": "Jobwatch-Setup-0.2.1.exe", "size": 10, "sha256": "a" * 64}
        verify_manifest(*signed(good), public(self.key))
        for bad in ({"installer": "..\\evil.exe"}, {"installer": "Jobwatch-Setup-0.2.1.exe /x"},
                    {"size": 0}, {"size": "10"}, {"sha256": "z" * 64}, {"version": "latest"}):
            with self.assertRaises(UpdateError, msg=bad):
                verify_manifest(*signed({**good, **bad}), public(self.key))


if __name__ == "__main__":
    unittest.main()


from test_dashboard import ServiceFixture   # noqa: E402
from dashboard import ApiError               # noqa: E402


class UpdateApiTests(ServiceFixture):
    def setUp(self):
        super().setUp()
        root = Path(self.tmp.name)
        self.key = Ed25519PrivateKey.generate()
        self.github = FakeGitHub()
        self.root = root
        UpdaterTests.publish(self, version="9.9.9")       # newer than any real version
        self.service.updater = Updater(root / "data", session=self.github, public_key=public(self.key))
        self.service.app_root = root / "zip copy"
        (root / "zip copy").mkdir()
        self.stopped = []
        self.service.on_shutdown = lambda: self.stopped.append(True)

    def test_state_and_apply(self):
        info = self.service.update_info()
        self.assertEqual((info["state"], info["available"]), ("idle", False))
        self.service.updater.check()
        info = self.service.update_info()
        self.assertEqual((info["state"], info["latest"], info["available"]), ("ready", "9.9.9", True))
        self.assertTrue(info["url"].startswith("https://github.com/IdanG7/JobWatcher/releases/"))
        launched = []
        # Model Windows even when the regression suite runs on Linux, where
        # subprocess omits these constants. Popen remains mocked on both systems.
        with patch.multiple("updater.subprocess", DETACHED_PROCESS=0x8,
                            CREATE_NEW_PROCESS_GROUP=0x200, CREATE_BREAKAWAY_FROM_JOB=0x1000000,
                            create=True), \
                patch("updater.subprocess.Popen", side_effect=lambda cmd, **kw: launched.append(cmd)) as popen, \
                patch("dashboard.threading.Timer") as timer:
            self.assertEqual(self.service.apply_update(), {"ok": True})
        self.assertEqual(popen.call_args.kwargs["creationflags"], 0x1000208)
        self.assertTrue(launched[0][0].endswith("Jobwatch-Setup-9.9.9.exe"))
        timer.assert_called_once()
        timer.return_value.start.assert_called_once()
        # a ZIP copy (no uninstaller): the installed app, not the ZIP copy itself,
        # offers to remove this folder
        self.assertIsNone(self.service.old_copy())
        self.service.app_root = self.root / "Programs/Jobwatch"
        self.assertEqual(self.service.update_info()["old_copy"], str(self.root / "zip copy"))
        self.service.dismiss_old_copy()
        self.assertIsNone(self.service.old_copy())

    def test_apply_without_a_download_or_outside_the_app(self):
        with self.assertRaises(ApiError):
            self.service.apply_update()
        self.service.updater = None
        with self.assertRaises(ApiError):
            self.service.apply_update()
