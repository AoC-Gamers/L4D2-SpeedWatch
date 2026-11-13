#!/usr/bin/env python3
"""Build the actual SDK-independent service and codec tests with native x86 flags."""
import argparse
import os
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--platform',choices=['linux','windows'],required=True);p.add_argument('--sanitize',action='store_true');p.add_argument('--deps');a=p.parse_args()
if (a.platform=='windows')!=(os.name=='nt'): p.error('Run tests on their native platform')
out=ROOT/'.build'/('tests-native-'+a.platform+('-sanitized' if a.sanitize else ''));out.mkdir(parents=True,exist_ok=True)
sources=[ROOT/'tests/native_core_tests.cpp',ROOT/'extension/telemetry/ObservationService.cpp',ROOT/'extension/api/SampleCodec.cpp']
binary=out/('core_tests.exe' if os.name=='nt' else 'core_tests')
if os.name=='nt': cmd=['cl','/nologo','/std:c++14','/EHsc','/W4','/WX',*map(str,sources),'/Fe:'+str(binary),'/Fo:'+str(out)+os.sep]
else:
    cmd=[os.environ.get('CXX','c++'),'-std=c++14','-Wall','-Wextra','-Werror','-O1','-g',
        *(['-fsanitize=address,undefined','-fno-omit-frame-pointer'] if a.sanitize else ['-m32']),
        *map(str,sources),'-o',str(binary)]
subprocess.run(cmd,check=True,cwd=out)
subprocess.run([str(binary)],check=True)

# SourceHook tests use the locked implementation, not a reimplementation of its chain.
if not a.sanitize:
    deps=Path(a.deps).resolve() if a.deps else ROOT/'.deps'/('exts-'+a.platform)
    hook=deps/'mmsource-1.12/core/sourcehook'
    sh_sources=[ROOT/'tests/sourcehook_observation_tests.cpp',ROOT/'extension/telemetry/ObservationService.cpp']
    sh_sources += [hook/f for f in ('sourcehook.cpp','sourcehook_impl_chookmaninfo.cpp','sourcehook_impl_chookidman.cpp',
        'sourcehook_impl_cproto.cpp','sourcehook_impl_cvfnptr.cpp','sourcehook_hookmangen.cpp','sourcehook_hookmangen_x86.cpp')]
    sh_binary=out/('sourcehook_tests.exe' if os.name=='nt' else 'sourcehook_tests')
    if os.name=='nt':
        sh_cmd=['cl','/nologo','/EHsc','/std:c++14','/I'+str(hook),'/DSH_COMP_MSVC',*map(str,sh_sources),'/Fe:'+str(sh_binary),'/Fo:'+str(out)+os.sep]
    else:
        sh_cmd=[os.environ.get('CXX','c++'),'-std=c++14','-m32','-fno-devirtualize','-DSH_COMP_GCC','-I'+str(hook),
                *map(str,sh_sources),'-o',str(sh_binary)]
    subprocess.run(sh_cmd,check=True,cwd=out)
    subprocess.run([str(sh_binary)],check=True)
