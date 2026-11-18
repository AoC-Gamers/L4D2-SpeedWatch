#!/usr/bin/env python3
"""Fetch the official Linux SourceMod SDK without replacing existing dependencies."""
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sourcepawn_sdk import describe_sdk

PACKAGE_HASH = 'package.sha256'


def main(root=Path(__file__).resolve().parents[2]):
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.12")
    parser.add_argument("--destination", default=".deps/smx/sourcemod-linux")
    args = parser.parse_args()
    if args.version not in ("1.12",):
        parser.error("Supported SourceMod branch: 1.12")
    destination = (root / args.destination).resolve()
    compiler = destination / "addons/sourcemod/scripting/spcomp64"
    lock = json.loads((root / "scripts/deps/sourcepawn-package.lock.json").read_text())
    if compiler.is_file() and (destination / PACKAGE_HASH).is_file() and (destination / PACKAGE_HASH).read_text().strip() == lock["sha256"]:
        describe_sdk(root, compiler)
        print(f"Using existing SDK: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        archive = destination.parent / "sourcemod-linux.tar.gz"
        request = urllib.request.Request(
            lock["url"],
            headers={"User-Agent": "L4D2-SpeedWatch-build"},
        )
        with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
            shutil.copyfileobj(response, output)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != lock["sha256"]:
            raise RuntimeError("SourceMod archive checksum mismatch")
        if destination.exists():
            raise RuntimeError("Existing unverified SDK directory; select a fresh --destination")
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(destination, filter="data")
        (destination / PACKAGE_HASH).write_text(lock["sha256"] + "\n")
        describe_sdk(root, compiler)
        print(f"SDK downloaded to {destination}")


if __name__ == '__main__':
    main()
