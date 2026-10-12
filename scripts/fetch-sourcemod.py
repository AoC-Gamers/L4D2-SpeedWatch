#!/usr/bin/env python3
"""Fetch the official Linux SourceMod SDK without replacing existing dependencies."""
import argparse
import shutil
import tarfile
import urllib.request
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--version", default="1.12")
args = parser.parse_args()
if args.version not in ("1.12",):
    parser.error("Supported SourceMod branch: 1.12")
root = Path(__file__).resolve().parents[1]
destination = root / "deps/sourcemod-linux"
if (destination / "addons/sourcemod/scripting/spcomp64").is_file():
    print(f"Using existing SDK: {destination}")
else:
    destination.parent.mkdir(parents=True, exist_ok=True)
    archive = destination.parent / "sourcemod-linux.tar.gz"
    request = urllib.request.Request(
        f"https://www.sourcemod.net/latest.php?os=linux&version={args.version}",
        headers={"User-Agent": "L4D2-SpeedWatch-build"},
    )
    with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
        shutil.copyfileobj(response, output)
    with tarfile.open(archive, "r:gz") as package:
        package.extractall(destination, filter="data")
    print(f"SDK downloaded to {destination}")
