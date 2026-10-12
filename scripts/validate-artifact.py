#!/usr/bin/env python3
"""Reject missing files and any payload outside the production manifest."""
import argparse
from pathlib import Path

from artifact_manifest import validate_artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--artifact", default="dist/sourcemod/artifact")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    validate_artifact(root, (root / args.artifact).resolve())
    print("ARTIFACT_VALIDATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
