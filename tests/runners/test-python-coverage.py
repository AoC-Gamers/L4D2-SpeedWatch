"""Measure actual Python product execution, including subprocesses, not fixtures."""
import argparse,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/helpers'))
import native_coverage as common
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--caller',required=True);a=p.parse_args()
if not a.output:p.error('TEST_OUTPUT must name a new directory')
python=ROOT/'.deps/test-coverage'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if not python.is_file():raise RuntimeError('Run make deps-test-coverage explicitly first')
out=(Path(a.caller)/a.output).resolve();out.mkdir(parents=True,exist_ok=False);before=common.source_state(ROOT)
config=out/'coverage.ini';config.write_text('[run]\nsource = '+str(ROOT/'scripts')+'\nparallel = true\npatch = subprocess\ndata_file = '+str(out/'.coverage')+'\n')
env={k:v for k,v in os.environ.items() if not k.startswith('SONAR_')}
with (out/'tests.log').open('w') as log:
 for suite,pattern in (('tests/python','test_*.py'),('tests/tooling','*test.py')):
  subprocess.run([str(python),'-m','coverage','run','--rcfile',str(config),'-m','unittest','discover','-s',suite,'-p',pattern,'-v'],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([str(python),'-m','coverage','combine','--rcfile',str(config)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
 subprocess.run([str(python),str(ROOT/'tests/helpers/python_coverage.py'),'--root',str(ROOT),'--config',str(config),'--output',str(out/'coverage.json')],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
merged={}
for name,data in json.loads((out/'coverage.json').read_text())['files'].items():
 path=(ROOT/name).resolve()
 if path.is_relative_to(ROOT/'scripts'):
  hits=set(data['executed_lines']);merged[path.relative_to(ROOT).as_posix()]={n:n in hits for n in hits|set(data['missing_lines'])}
if before!=common.source_state(ROOT):raise ValueError('Sources changed during coverage')
report=out/'coverage.xml';common.write_report(report,merged)
receipt={'schema':1,'kind':'python','coverage_version':'7.13.5','source_state':before,'report':report.name,'report_sha256':common.digest(report),'all_suites_passed':True,'runtime_acceptance':False}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PYTHON_COVERAGE_OK',out)
