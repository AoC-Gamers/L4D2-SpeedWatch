#!/usr/bin/env python3
"""Shared production allowlist for the local build and CI release pipeline."""
import json
import hashlib
import shutil
import re
import stat
from pathlib import Path


def load_manifest(root: Path) -> dict:
    manifest = json.loads((root / "scripts/package/package-map.json").read_text(encoding="utf-8"))
    if set(manifest) != {"build", "artifact"} or set(manifest["build"]) != {"plugins", "extensions"}:
        raise ValueError("Unknown or missing package-map keys")
    for family in manifest["build"].values():
        if not isinstance(family, dict): raise ValueError("Invalid component family")
        for bucket, names in family.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]+", bucket) or not isinstance(names, list): raise ValueError("Invalid component bucket")
            if len(names) != len(set(names)) or any(not re.fullmatch(r"[A-Za-z_]\w*", name, flags=re.ASCII) for name in names): raise ValueError("Invalid component names")
    return manifest


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


def validate_artifact_node(node):
    if not isinstance(node, dict): raise ValueError("Artifact nodes must be objects")
    for key in ("files", "dirs"):
        if key in node and (not isinstance(node[key], list) or any(not isinstance(name, str) for name in node[key])): raise ValueError("Invalid artifact list")
    if "all" in node and type(node["all"]) is not bool: raise ValueError("Invalid all flag")


def selected_files(root: Path, node: dict, prefix: Path = Path()) -> set[Path]:
    validate_artifact_node(node)
    files = {prefix / name for name in node.get("files", [])}
    directories = [prefix / name for name in node.get("dirs", [])]
    if node.get("all", False):
        directories.append(prefix)
    for relative in directories:
        safe_path(root, relative)
        directory = root / relative
        if not directory.is_dir():
            raise FileNotFoundError(f"Required artifact directory not found: {directory}")
        files.update(p.relative_to(root) for p in directory.rglob("*") if checked_file(p))
    for key, child in node.items():
        if key not in ("files", "dirs", "all"):
            safe_path(root, prefix / key)
            files.update(selected_files(root, child, prefix / key))
    unique_case(files)
    for relative in files:
        safe_path(root, relative)
        if not (root / relative).is_file():
            raise FileNotFoundError(f"Required artifact file not found: {relative}")
    return files


def copy_files(source: Path, destination: Path, files: set[Path]) -> None:
    unique_case(files)
    for relative in sorted(files):
        safe_path(source, relative)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / relative, target)


def clean_output(root: Path, output: Path) -> None:
    # Cleanup is limited to generated trees, never the checkout or its sources.
    relative = output.relative_to(root)
    if len(relative.parts) < 2 or relative.parts[0] not in (".build", "dist"):
        raise ValueError(f"Output must be inside .build/ or dist/: {output}")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)


def validate_artifact(root: Path, artifact: Path, *, full: bool = True) -> None:
    manifest = load_manifest(root)
    plugins = plugin_paths(manifest)
    expected = set(plugins) | selected_files(root, manifest["artifact"])
    if full:
        expected |= selected_files(root, {"files": ["LICENSE"]})
        expected.add(Path("compile.log"))
        expected.add(Path("sourcepawn-build-info.json"))
        actual = tree_files(artifact)
    else:
        actual = {p for p in tree_files(artifact) if p.parts[0] == "addons"}
    missing, unexpected = expected - actual, actual - expected
    if missing or unexpected:
        raise ValueError(f"Missing artifact files: {sorted(map(str, missing))}; Unexpected artifact files: {sorted(map(str, unexpected))}")
    for relative in [*plugins, *([Path("compile.log")] if full else [])]:
        if (artifact / relative).stat().st_size == 0:
            raise ValueError(f"Empty artifact file: {relative}")


def sourcepawn_inputs(root: Path) -> dict[str, str]:
    directory = root / "addons/sourcemod/scripting"
    return {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob("*")) if p.suffix in (".sp", ".inc") and not p.stem.endswith("_test")}


def native_source_hashes(root: Path) -> dict[str, str]:
    files = [p for p in (root / "extension").rglob("*") if p.is_file()]
    files += [root / p for p in ("AMBuildScript", "configure.py", "PackageScript", "dependencies.lock.json")]
    files += [root/"scripts/package/package-map.json", *sorted((root/"scripts/build").glob("*.py"))]
    return {str(p.relative_to(root)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def unique_case(paths):
    keys=[str(path).replace("\\", "/").casefold() for path in paths]
    if len(keys)!=len(set(keys)): raise ValueError("Case collision in artifact")


def safe_path(root, relative):
    text=str(relative)
    if relative.is_absolute() or ".." in relative.parts or "\\" in text or re.match(r"^[A-Za-z]:", text):
        raise ValueError("Unsafe artifact path")
    current=root
    for part in relative.parts:
        current/=part
        if current.is_symlink(): raise ValueError("Artifact symlink is forbidden")


def checked_file(path):
    mode=path.lstat().st_mode
    if stat.S_ISLNK(mode) or not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
        raise ValueError("Artifact link or special file is forbidden")
    return stat.S_ISREG(mode)


def tree_files(tree):
    if tree.is_symlink(): raise ValueError("Artifact root cannot be a symlink")
    files={p.relative_to(tree) for p in tree.rglob("*") if checked_file(p)}
    unique_case(files)
    return files


def validate_basename(value):
    if not value or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,159}",value):
        raise ValueError("Invalid basename")
