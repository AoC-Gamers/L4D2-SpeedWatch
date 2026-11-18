#!/usr/bin/env python3
"""AMBuild driver. Never downloads SDKs; platform outputs and metadata are isolated."""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts/package"))
from artifact_contract import native_source_hashes
def run(cmd, log, **kwargs):
    p=subprocess.run(list(map(str,cmd)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,**kwargs)
    print(p.stdout,end=''); log.write(p.stdout); log.flush()
    p.check_returncode()
def generated_ambuild_copy(directory, name, tracked):
    if not name.startswith('build/lib/'):
        return False
    original = name.removeprefix('build/lib/')
    source, generated = directory/original, directory/name
    return (original in tracked and source.is_file() and generated.is_file()
            and not source.is_symlink() and not generated.is_symlink()
            and source.read_bytes() == generated.read_bytes())

def extra_build_inputs(directory):
    # Include ignored files too: an ignored header can still shadow a locked one.
    files = subprocess.check_output(['git','-C',str(directory),'ls-files','--others','-z'],text=True)
    tracked = set(subprocess.check_output(['git','-C',str(directory),'ls-files','--cached','-z'],text=True).split('\0'))
    suffixes = {'.h','.hpp','.hxx','.hh','.inc','.inl','.c','.cc','.cpp','.cxx','.py','.a','.lib','.so','.dll','.o','.obj'}
    unexpected = []
    for name in files.split('\0'):
        if not name or Path(name).suffix.lower() not in suffixes:
            continue
        if directory.name == 'ambuild' and generated_ambuild_copy(directory,name,tracked):
            continue
        unexpected.append(name)
    return unexpected

def checkout_submodules(directory):
    entries = subprocess.check_output(['git','-C',str(directory),'ls-files','--stage','-z'],text=True)
    for entry in entries.split('\0'):
        if not entry:
            continue
        metadata, _, name = entry.partition('\t')
        mode, revision, stage = metadata.split()
        if mode != '160000':
            continue
        child = directory/name
        if stage != '0' or child.is_symlink():
            raise RuntimeError('SDK submodule invalid: '+name)
        if not (child/'.git').exists():
            if child.exists() and any(child.iterdir()):
                raise RuntimeError('SDK submodule has files without an initialized checkout: '+name)
            continue
        yield child, revision


def verify_checkout(directory, expected_revision, allow_metadata=False):
    revision=subprocess.check_output(['git','-C',str(directory),'rev-parse','HEAD'],text=True).strip()
    changed=subprocess.check_output(['git','-C',str(directory),'status','--porcelain','--untracked-files=all','--ignore-submodules=none'],text=True).strip()
    if allow_metadata:
        generated = {'?? AMBuild.egg-info/' + part for part in ('PKG-INFO','SOURCES.txt','dependency_links.txt','entry_points.txt','not-zip-safe','top_level.txt')}
        changed = '\n'.join(line for line in changed.splitlines() if line not in generated)
    if revision != expected_revision or changed or extra_build_inputs(directory):
        raise RuntimeError('Dependency checkout differs from lock: '+str(directory))
    for child, child_revision in checkout_submodules(directory):
        verify_checkout(child,child_revision)


def verify_dependencies(root,deps,python,ambuild):
    for path in (python,ambuild,deps/'hl2sdk-l4d2',deps/'sourcemod-1.12',deps/'mmsource-1.12'):
        if not path.exists(): raise RuntimeError('Missing explicit dependency: '+str(path))
    lock=json.loads((root/'scripts/deps/dependencies.lock.json').read_text())
    for name,spec in lock.items():
        verify_checkout(deps/name,spec['revision'],allow_metadata=name == 'ambuild')

def main(root=ROOT):
    p=argparse.ArgumentParser();p.add_argument('--platform',choices=['linux','windows'],required=True)
    p.add_argument('--deps');p.add_argument('--output');a=p.parse_args()
    if (a.platform=='windows') != (os.name=='nt'): p.error('Build must run on its native platform')
    deps=Path(a.deps or root/'.deps'/('exts-'+a.platform)).resolve()
    output=Path(a.output or root/'.build'/('exts-'+a.platform)).resolve()
    relative=output.relative_to(root/'.build')
    if not relative.parts: raise ValueError('Cannot use the shared .build root as output')
    python=deps/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    ambuild=deps/'venv'/('Scripts/ambuild.exe' if os.name=='nt' else 'bin/ambuild')
    verify_dependencies(root,deps,python,ambuild)
    if output.exists(): shutil.rmtree(output)
    output.mkdir(parents=True)
    with (output/'compile.log').open('w') as log:
        run([python,root/'configure.py','--sdks','l4d2','--hl2sdk-root',deps,'--sm-path',deps/'sourcemod-1.12','--mms-path',deps/'mmsource-1.12','--enable-optimize'],log,cwd=output)
        run([ambuild,'--jobs','4'],log,cwd=output)
        run([python,root/'scripts/build/export-compile-commands.py','--build',output],log)
    suffix='dll' if os.name=='nt' else 'so'
    binary=output/'package/addons/sourcemod/extensions'/('l4d2_speedwatch_core.ext.2.l4d2.'+suffix)
    from native_binary import validate_binary
    validate_binary(binary,a.platform)
    compiler=subprocess.check_output(['cl' if os.name=='nt' else os.environ.get('CXX','c++'),'/?' if os.name=='nt' else '--version'],stderr=subprocess.STDOUT,text=True)
    revision=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True)
    top=subprocess.run(['git','rev-parse','--show-toplevel'],cwd=root,capture_output=True,text=True)
    project_sha=revision.stdout.strip() if revision.returncode==0 and top.returncode==0 and Path(top.stdout.strip()).resolve()==root else None
    info={'platform':a.platform,'architecture':'x86','project_sha':project_sha,
          'dependencies':json.loads((deps/'resolved.json').read_text()),
          'compiler_environment':{name:os.environ.get(name,'') for name in ('CC','CXX','CFLAGS','CXXFLAGS','LDFLAGS')},'compiler':compiler,'python':platform.python_version(),
          'sources':native_source_hashes(root),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
    (output/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')

if __name__ == '__main__':
    main()
