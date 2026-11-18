"""Internal release receipts preserve integrity outside installable ZIPs."""
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import zipfile

from artifact_contract import load_manifest, selected_files
from installer_docs import LICENSE_PATH, documentation_paths, verify_license


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def receipt_path(root, platform):
    return root / '.build/release-receipts' / (platform + '.json')


def read_receipt(path):
    payload = json.loads(path.read_text())
    if payload.get('schema') != 1:
        raise ValueError('Unsupported release receipt')
    return payload


def sourcepawn_payload(root):
    manifest = load_manifest(root)
    return {path.as_posix() for path in selected_files(root, manifest['artifact'])
            if path.suffix.lower() == '.sp'}


def validate_zip(path, receipt, platform, sha, root):
    if receipt['platform'] != platform or receipt['architecture'] != 'x86' or receipt['project_sha'] != sha:
        raise ValueError('ZIP commit/platform mismatch')
    if receipt['archive_name'] != path.name or receipt['archive_sha256'] != digest(path):
        raise ValueError('Release archive differs from receipt')
    with zipfile.ZipFile(path) as archive:
        validate_contents(archive, receipt['runtime_files'], root)


def validate_contents(archive, hashes, root):
    validate_members(archive, hashes, root)
    for name, expected in hashes.items():
        if hashlib.sha256(archive.read(name)).hexdigest() != expected:
            raise ValueError('ZIP payload hash mismatch')


def validate_members(archive, hashes, root):
    names = archive.namelist()
    if len(names) != len(set(names)) or len({n.casefold() for n in names}) != len(names):
        raise ValueError('Duplicate ZIP members')
    files = {name for name in names if not name.endswith('/')}
    if files != set(hashes) or not {path.as_posix() for path in documentation_paths(root)} <= files:
        raise ValueError('Unexpected ZIP payload')
    for name in names:
        if (PurePosixPath(name).anchor or PureWindowsPath(name).anchor
                or '..' in PurePosixPath(name).parts or '\\' in name):
            raise ValueError('Unsafe ZIP path')
    sources = {name for name in files if PurePosixPath(name).suffix.lower() == '.sp'}
    if sources != sourcepawn_payload(root):
        raise ValueError('Unexpected or missing SourcePawn sources in release ZIP')
    if any(forbidden_member(name) for name in files):
        raise ValueError('Build files are forbidden in release ZIPs')
    verify_license(archive.read(LICENSE_PATH.as_posix()))


def forbidden_member(name):
    path = PurePosixPath(name)
    return (path.name == 'package-map.json' or path.name.startswith('.env')
            or path.name.endswith('build-info.json') or path.suffix == '.log')
