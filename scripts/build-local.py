#!/usr/bin/env python3
"""Compile only production entrypoints declared in plugin-package-map.json."""
import argparse
import subprocess
import sys
from pathlib import Path

from artifact_manifest import clean_output, copy_files, load_manifest, plugin_paths, selected_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--spcomp", required=True)
    parser.add_argument("--output-root", default=".build/smx")
    parser.add_argument("--compile-log", default="deps/build-smx-compile.log")
    args = parser.parse_args()
    root = Path(args.root).resolve()
    spcomp = (root / args.spcomp).resolve()
    output = (root / args.output_root).resolve()
    compile_log = (root / args.compile_log).resolve()
    manifest = load_manifest(root)
    plugins = plugin_paths(manifest)
    published = selected_files(root, manifest["artifact"])
    if not spcomp.is_file() or not (spcomp.parent / "include").is_dir():
        raise FileNotFoundError(f"SourceMod compiler or SDK includes missing: {spcomp}")
    for source in plugins.values():
        if not (root / source).is_file():
            raise FileNotFoundError(f"Production entrypoint missing: {source}")
    clean_output(root, output)
    compile_log.parent.mkdir(parents=True, exist_ok=True)
    includes = [root / "addons/sourcemod/scripting/include", root / "addons/sourcemod/scripting", spcomp.parent / "include"]
    with compile_log.open("w", encoding="utf-8") as log:
        for target, source in plugins.items():
            destination = output / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"Compiling {source} -> {target}", flush=True)
            log.write(f"Compiling {source} -> {target}\n")
            result = subprocess.run([str(spcomp), str(root / source), *[f"-i{p}" for p in includes],
                                     f"-o{destination}", "-E"], capture_output=True, text=True, check=False)
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            log.write(result.stdout + result.stderr)
            log.flush()
            if result.returncode != 0:
                raise RuntimeError(f"spcomp failed for {source}; see {compile_log}")
            if not destination.is_file() or destination.stat().st_size == 0:
                raise RuntimeError(f"Expected compiler output missing or empty: {destination}")
    copy_files(root, output, published)
    print(f"Production build completed in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
