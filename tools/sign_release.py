"""Sign a built installer for in-app updates.

Writes jobwatch-update.json (version, installer name, size, sha256) and its
ed25519 signature jobwatch-update.json.sig beside the installer. The private
key comes from --key-file or the JOBWATCH_UPDATE_KEY environment variable
(PEM text); it is never written anywhere.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from updater import MANIFEST, SIGNATURE, verify_manifest


def load_key(pem: bytes):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    key = load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit("the update key must be an ed25519 private key")
    return key


def public_key_text(key) -> str:
    from cryptography.hazmat.primitives import serialization
    raw = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return base64.b64encode(raw).decode()


def sign(installer: Path, pem: bytes, expected_public: str | None = None) -> tuple[Path, Path]:
    found = re.fullmatch(r"Jobwatch-Setup-(\d+(?:\.\d+){1,3})\.exe", installer.name)
    if not found:
        raise SystemExit(f"unexpected installer name: {installer.name}")
    key = load_key(pem)
    if expected_public and public_key_text(key) != expected_public:
        raise SystemExit("this key does not match the public key built into the app; "
                         "installed copies would reject the update")
    data = installer.read_bytes()
    manifest = json.dumps({"version": found.group(1), "installer": installer.name, "size": len(data),
                           "sha256": hashlib.sha256(data).hexdigest()}, indent=2).encode() + b"\n"
    signature = base64.b64encode(key.sign(manifest)) + b"\n"
    verify_manifest(manifest, signature, public_key_text(key))       # round trip before publishing
    manifest_path, signature_path = installer.with_name(MANIFEST), installer.with_name(SIGNATURE)
    manifest_path.write_bytes(manifest)
    signature_path.write_bytes(signature)
    return manifest_path, signature_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("installer", type=Path)
    parser.add_argument("--key-file", type=Path, help="PEM file (default: $JOBWATCH_UPDATE_KEY)")
    parser.add_argument("--any-key", action="store_true",
                        help="allow a key other than update_key.PUBLIC_KEY (test builds)")
    args = parser.parse_args()
    if args.key_file:
        pem = args.key_file.read_bytes()
    elif os.environ.get("JOBWATCH_UPDATE_KEY"):
        pem = os.environ["JOBWATCH_UPDATE_KEY"].encode()
    else:
        raise SystemExit("no signing key: set JOBWATCH_UPDATE_KEY or pass --key-file")
    import update_key
    for path in sign(args.installer.resolve(), pem, None if args.any_key else update_key.PUBLIC_KEY):
        print(f"Wrote {path}")
