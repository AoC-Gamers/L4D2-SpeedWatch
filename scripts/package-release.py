#!/usr/bin/env python3
"""Package the validated SourceMod artifact into a channel release ZIP."""
import argparse
import shutil
from pathlib import Path

from artifact_manifest import validate_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--basename", required=True)
    args = parser.parse_args()
    if not args.basename or Path(args.basename).name != args.basename or args.basename in (".", ".."):
        raise ValueError("Release basename must be a filename without a directory")
    root = Path(args.root).resolve()
    artifact = root / "dist/sourcemod/artifact"
    validate_artifact(root, artifact)
    release_dir = root / "dist/release"
    release_dir.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(release_dir / args.basename), "zip", root_dir=artifact)
    print(f"Release archive generated in {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
