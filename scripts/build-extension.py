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
ROOT=Path(__file__).resolve().parents[1]
from artifact_manifest import native_source_hashes
def run(cmd, log, **kwargs):
    p=subprocess.run(list(map(str,cmd)),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,**kwargs)
    print(p.stdout,end=''); log.write(p.stdout); log.flush()
    p.check_returncode()
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--platform',choices=['linux','windows'],required=True)
    p.add_argument('--deps');p.add_argument('--output');a=p.parse_args()
    if (a.platform=='windows') != (os.name=='nt'): p.error('Build must run on its native platform')
    deps=Path(a.deps or ROOT/'.deps'/('exts-'+a.platform)).resolve()
    output=Path(a.output or ROOT/'.build'/('exts-'+a.platform)).resolve()
    relative=output.relative_to(ROOT/'.build')
    if not relative.parts: raise ValueError('Cannot use the shared .build root as output')
    python=deps/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    ambuild=deps/'venv'/('Scripts/ambuild.exe' if os.name=='nt' else 'bin/ambuild')
    for path in (python,ambuild,deps/'hl2sdk-l4d2',deps/'sourcemod-1.12',deps/'mmsource-1.12'):
        if not path.exists(): raise RuntimeError('Missing explicit dependency: '+str(path))
    lock=json.loads((ROOT/'dependencies.lock.json').read_text())
    for name,spec in lock.items():
        revision=subprocess.check_output(['git','-C',str(deps/name),'rev-parse','HEAD'],text=True).strip()
        changed=subprocess.check_output(['git','-C',str(deps/name),'status','--porcelain','--untracked-files=no'],text=True).strip()
        if revision!=spec['revision'] or changed:
            raise RuntimeError('Dependency checkout differs from lock: '+name)
    if output.exists(): shutil.rmtree(output)
    output.mkdir(parents=True)
    with (output/'compile.log').open('w') as log:
        run([python,ROOT/'configure.py','--sdks','l4d2','--hl2sdk-root',deps,'--sm-path',deps/'sourcemod-1.12','--mms-path',deps/'mmsource-1.12','--enable-optimize'],log,cwd=output)
        run([ambuild,'--jobs','4'],log,cwd=output)
    suffix='dll' if os.name=='nt' else 'so'
    binary=output/'package/addons/sourcemod/extensions'/('l4d2_speedwatch_core.ext.'+suffix)
    from native_binary import validate_binary
    validate_binary(binary,a.platform)
    compiler=subprocess.check_output(['cl' if os.name=='nt' else os.environ.get('CXX','c++'),'/?' if os.name=='nt' else '--version'],stderr=subprocess.STDOUT,text=True)
    info={'platform':a.platform,'architecture':'x86','project_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
          'dependencies':json.loads((deps/'resolved.json').read_text()),
          'compiler_environment':{name:os.environ.get(name,'') for name in ('CC','CXX','CFLAGS','CXXFLAGS','LDFLAGS')},'compiler':compiler,'python':platform.python_version(),
          'sources':native_source_hashes(ROOT),'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
    (output/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
