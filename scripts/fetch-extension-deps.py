#!/usr/bin/env python3
"""Fetch locked SDK sources; called only by explicit dependency targets."""
import argparse
import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--platform', choices=['linux','windows'], required=True)
p.add_argument('--destination')
a = p.parse_args()
dest = Path(a.destination or ROOT / '.deps' / ('exts-' + a.platform)).resolve()
lock = json.loads((ROOT / 'dependencies.lock.json').read_text())
def run(*cmd): subprocess.run(cmd, check=True)
def fetch(item):
    name, spec = item
    directory = dest / name
    if not directory.exists():
        directory.mkdir(parents=True)
        run('git','init',str(directory))
        run('git','-C',str(directory),'remote','add','origin','https://github.com/'+spec['repository']+'.git')
    current = subprocess.run(['git','-C',str(directory),'rev-parse','HEAD'],capture_output=True,text=True)
    if current.returncode == 0 and subprocess.check_output(['git','-C',str(directory),'status','--porcelain','--untracked-files=no'],text=True).strip():
        raise RuntimeError('Dirty tracked dependency: '+str(directory))
    if current.stdout.strip() != spec['revision']:
        if subprocess.check_output(['git','-C',str(directory),'status','--porcelain'],text=True).strip():
            raise RuntimeError('Dirty dependency: '+str(directory))
        run('git','-C',str(directory),'fetch','--depth','1','origin',spec['revision'])
        run('git','-C',str(directory),'checkout','--detach','FETCH_HEAD')
    if name == 'sourcemod-1.12':
        run('git','-C',str(directory),'submodule','update','--init','--depth','1','public/amtl','sourcepawn')
    elif name == 'mmsource-1.12':
        run('git','-C',str(directory),'submodule','update','--init','--recursive','--depth','1')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    list(executor.map(fetch, lock.items()))
venv = dest / 'venv'
if not venv.exists(): run(sys.executable,'-m','venv',str(venv))
python = venv / ('Scripts/python.exe' if a.platform == 'windows' else 'bin/python')
run(str(python),'-m','pip','install','--no-deps',str(dest/'ambuild'))
(dest/'resolved.json').write_text(json.dumps(lock,indent=2)+'\n')
