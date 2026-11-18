#!/usr/bin/env python3
"""Package the validated SourceMod artifact into a channel release ZIP."""
import argparse
import shutil
import zipfile
from pathlib import Path

from artifact_contract import validate_artifact, validate_basename, clean_output, tree_files
from installer_docs import installer_docs, stage_docs
from release_receipt import validate_contents, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--basename", required=True)
    args = parser.parse_args()
    validate_basename(args.basename)
    root = Path(args.root).resolve()
    artifact = root / "dist/sourcemod/artifact"
    validate_artifact(root, artifact)
    package = root / '.build/package-smx-release'
    clean_output(root, package)
    shutil.copytree(artifact / 'addons', package / 'addons')
    stage_docs(package, installer_docs(root, 'SourcePawn (requiere el core nativo)', None))
    release_dir = root / "dist/release"
    release_dir.mkdir(parents=True, exist_ok=True)
    archive = shutil.make_archive(str(release_dir / args.basename), "zip", root_dir=package)
    hashes = {path.as_posix(): digest(package / path) for path in tree_files(package)}
    with zipfile.ZipFile(archive) as packaged:
        validate_contents(packaged, hashes, root)
    print(f"Release archive generated in {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
