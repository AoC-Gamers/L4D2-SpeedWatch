#!/usr/bin/env python3
"""Stage the validated production tree with its license and compiler output."""
import shutil
import sys
from pathlib import Path

from artifact_manifest import clean_output, copy_files, selected_files, validate_artifact


def main() -> int:
    if len(sys.argv) not in (4, 5):
        raise SystemExit("Usage: stage-artifact.py <root> <build> <compile-log> [output]")
    root, build, compile_log = (Path(p).resolve() for p in sys.argv[1:4])
    output = Path(sys.argv[4]).resolve() if len(sys.argv) == 5 else root / "dist/sourcemod/artifact"
    if output == build or output in build.parents or build in output.parents:
        raise ValueError("Build and staging trees must be separate")
    validate_artifact(root, build, full=False)
    metadata = selected_files(root, {"files": ["LICENSE"]})
    if not compile_log.is_file() or compile_log.stat().st_size == 0:
        raise FileNotFoundError(f"Compile log missing or empty: {compile_log}")
    clean_output(root, output)
    shutil.copytree(build / "addons", output / "addons")
    copy_files(root, output, metadata)
    shutil.copy2(compile_log, output / "compile.log")
    validate_artifact(root, output)
    print(f"SourceMod artifact generated in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
