#!/usr/bin/env python3
"""Fetch the official Linux SourceMod SDK without replacing existing dependencies."""
import argparse
import hashlib
import json
import shutil
import tarfile
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--version", default="1.12")
parser.add_argument("--destination", default=".deps/smx/sourcemod-linux")
args = parser.parse_args()
if args.version not in ("1.12",):
    parser.error("Supported SourceMod branch: 1.12")
root = Path(__file__).resolve().parents[1]
destination = (root / args.destination).resolve()
lock = json.loads((root / "sourcepawn-package.lock.json").read_text())
if (destination / "addons/sourcemod/scripting/spcomp64").is_file() and (destination / "package.sha256").is_file() and (destination / "package.sha256").read_text().strip() == lock["sha256"]:
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
    (destination / "package.sha256").write_text(lock["sha256"] + "\n")
    print(f"SDK downloaded to {destination}")
