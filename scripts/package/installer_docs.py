"""Render the selected installer documentation and verify its legal texts."""
from pathlib import Path
import re

from artifact_contract import load_manifest, safe_path

LICENSE_PATH = Path('LICENSE')
LICENSE_MARKERS = (
    b'Version 3, 29 June 2007',
    b'SpeedWatch uses the following third-party components:',
    b'SOURCEMOD LICENSE INFORMATION',
    b'Version 2, June 1991',
    b'Metamod:Source is distributed under the "zLib/libpng" license',
    b'Copyright (C) 2013-2014, David Anderson and AlliedModders LLC',
    b'GCC RUNTIME LIBRARY EXCEPTION',
    b'Version 2.1, February 1999',
)


def documentation_paths(root):
    return {Path(name) for name in load_manifest(root)['documentation']}


def verify_license(data):
    for marker in LICENSE_MARKERS:
        if marker not in data:
            raise ValueError(f'Invalid license text: missing {marker.decode("ascii")} in {LICENSE_PATH}')


def installer_docs(root, platform, sha):
    if sha is not None and not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Invalid installer source revision')
    repository = 'https://github.com/AoC-Gamers/L4D2-SpeedWatch'
    revision = sha or 'local sin SHA de Git'
    docs = f'{repository}/blob/{sha}' if sha else f'{repository}/blob/develop'
    template = root / 'docs/build/installation-package.md'
    readme = (template.read_text(encoding='utf-8').replace('@REVISION@', revision)
              .replace('@PLATFORM@', platform).replace('@DOCS@', docs))
    if sha is None:
        readme += '\nLos enlaces apuntan a la documentación de desarrollo.\n'
    readme_path = Path('README.md')
    content = {readme_path: readme.encode('utf-8')}
    for relative in documentation_paths(root) - {readme_path}:
        safe_path(root, relative)
        data = (root / relative).read_bytes()
        if relative == LICENSE_PATH:
            verify_license(data)
        content[relative] = data
    return content


def stage_docs(destination, content):
    for relative, data in content.items():
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def verify_docs(tree, content):
    for relative, data in content.items():
        if (tree / relative).read_bytes() != data:
            raise ValueError(f'Installer documentation differs from source: {relative}')
