"""Verify managed compiler inputs against the pinned archive; label external SDKs."""
import hashlib
import json
import tarfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler_inputs(compiler):
    include = compiler.parent / 'include'
    if compiler.is_symlink() or not compiler.is_file() or not include.is_dir() or include.is_symlink():
        raise ValueError('Missing or linked SourcePawn compiler/includes')
    headers = {}
    for path in sorted(include.rglob('*')):
        if path.is_symlink():
            raise ValueError('SDK include symlink is forbidden')
        if path.is_file():
            headers[path.relative_to(include).as_posix()] = digest(path)
    return {'compiler_sha256': digest(compiler), 'sdk_headers': headers}


def archive_inputs(archive, compiler):
    prefix = 'addons/sourcemod/scripting/'
    include_prefix = prefix + 'include/'
    expected = {}
    with tarfile.open(archive, 'r:gz') as package:
        for member in package:
            name = member.name.removeprefix('./')
            if name != prefix + compiler.name and not name.startswith(include_prefix):
                continue
            if member.isdir():
                continue
            if not member.isfile() or name in expected:
                raise ValueError('Invalid compiler input in SDK archive')
            with package.extractfile(member) as source:
                expected[name] = hashlib.sha256(source.read()).hexdigest()
    return {'compiler_sha256': expected.get(prefix + compiler.name),
            'sdk_headers': {name[len(include_prefix):]: value for name, value in expected.items()
                            if name.startswith(include_prefix)}}


def describe_sdk(root, compiler):
    inputs = compiler_inputs(compiler)
    sdk = compiler.parent
    if compiler.parent.parts[-3:] == ('addons', 'sourcemod', 'scripting'):
        sdk = compiler.parents[3]
    marker = sdk / 'package.sha256'
    managed = compiler.is_relative_to(root / '.deps/smx') or marker.exists()
    if not managed:
        return {**inputs, 'sdk_origin': 'external', 'sdk_package': None}
    lock = json.loads((root / 'scripts/deps/sourcepawn-package.lock.json').read_text())
    archive = sdk.parent / 'sourcemod-linux.tar.gz'
    if not marker.is_file() or marker.read_text().strip() != lock['sha256']:
        raise ValueError('Managed SDK marker differs from lock; use make deps-smx with a fresh destination')
    if not archive.is_file() or digest(archive) != lock['sha256']:
        raise ValueError('Managed SDK archive missing or checksum mismatch')
    if inputs != archive_inputs(archive, compiler):
        raise ValueError('Managed SDK compiler/includes differ from pinned archive')
    return {**inputs, 'sdk_origin': 'locked-archive', 'sdk_package': lock}
