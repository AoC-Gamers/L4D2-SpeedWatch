#!/usr/bin/env python3
"""Shared production allowlist for the local build and CI release pipeline."""
import json
import shutil
from pathlib import Path


def load_manifest(root: Path) -> dict:
    return json.loads((root / "plugin-package-map.json").read_text(encoding="utf-8"))


def plugin_paths(manifest: dict) -> dict[Path, Path]:
    plugins = {}
    for bucket, names in manifest["build"]["plugins"].items():
        for name in names:
            source = Path("addons/sourcemod/scripting") / f"{name}.sp"
            target = Path("addons/sourcemod/plugins")
            if bucket != "root":
                target /= bucket
            plugins[target / f"{name}.smx"] = source
    if not plugins:
        raise ValueError("No production plugins declared in build.plugins")
    return plugins


def selected_files(root: Path, node: dict, prefix: Path = Path()) -> set[Path]:
    files = {prefix / name for name in node.get("files", [])}
    directories = [prefix / name for name in node.get("dirs", [])]
    if node.get("all", False):
        directories.append(prefix)
    for relative in directories:
        directory = root / relative
        if not directory.is_dir():
            raise FileNotFoundError(f"Required artifact directory not found: {directory}")
        files.update(p.relative_to(root) for p in directory.rglob("*") if p.is_file())
    for key, child in node.items():
        if key not in ("files", "dirs", "all"):
            files.update(selected_files(root, child, prefix / key))
    for relative in files:
        if not (root / relative).is_file():
            raise FileNotFoundError(f"Required artifact file not found: {relative}")
    return files


def copy_files(source: Path, destination: Path, files: set[Path]) -> None:
    for relative in sorted(files):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)


def clean_output(root: Path, output: Path) -> None:
    # Cleanup is limited to generated trees, never the checkout or its sources.
    relative = output.relative_to(root)
    if not relative.parts or relative.parts[0] not in (".build", "dist"):
        raise ValueError(f"Output must be inside .build/ or dist/: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)


def validate_artifact(root: Path, artifact: Path, *, full: bool = True) -> None:
    manifest = load_manifest(root)
    plugins = plugin_paths(manifest)
    expected = set(plugins) | selected_files(root, manifest["artifact"])
    if full:
        expected |= selected_files(root, {"files": ["README.md", "LICENSE", "docs/index.md"], "dirs": ["docs"]})
        expected.add(Path("compile.log"))
        actual = {p.relative_to(artifact) for p in artifact.rglob("*") if p.is_file()}
    else:
        actual = {p.relative_to(artifact) for p in (artifact / "addons").rglob("*") if p.is_file()}
    missing, unexpected = expected - actual, actual - expected
    if missing or unexpected:
        raise ValueError(f"Missing artifact files: {sorted(map(str, missing))}; Unexpected artifact files: {sorted(map(str, unexpected))}")
    for relative in [*plugins, *([Path("compile.log")] if full else [])]:
        if (artifact / relative).stat().st_size == 0:
            raise ValueError(f"Empty artifact file: {relative}")
