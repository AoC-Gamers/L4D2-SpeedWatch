"""Run the local Linux suite through Make, with a fresh caller-relative output."""
import argparse,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--caller',default=str(Path.cwd()));p.add_argument('--make',default='make');a=p.parse_args()
if not a.output: p.error('TEST_OUTPUT must name a new directory')
out=(Path(a.caller)/a.output).resolve();out.mkdir(parents=True,exist_ok=False)
results=[]
for target in ['build-smx','build-api-test','test-ci','test-exts-linux']:
    with (out/(target+'.log')).open('w') as log:
        result=subprocess.run([a.make,'--no-print-directory','-f',str(ROOT/'Makefile'),target],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    results.append({'target':target,'exit_code':result.returncode})
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    if result.returncode: raise SystemExit(result.returncode)
print('LOCAL_TESTS_OK',out)
