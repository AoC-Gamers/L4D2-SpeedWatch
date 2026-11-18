"""Real x86 GCC counters, merged with zero-hit units from actual build commands."""
import argparse,importlib.util,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/helpers'))
import native_coverage as coverage
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--caller',required=True);p.add_argument('--compile-commands',required=True);a=p.parse_args()
if not a.output:p.error('TEST_OUTPUT must name a new directory')
out=(Path(a.caller)/a.output).resolve();out.mkdir(parents=True,exist_ok=False)
start=coverage.source_state(ROOT);env={k:v for k,v in os.environ.items() if not k.startswith('SONAR_')}
spec=importlib.util.spec_from_file_location('make_sonar',ROOT/'scripts/tools/make_sonar.py');sonar=importlib.util.module_from_spec(spec);spec.loader.exec_module(sonar)
entries=sonar.compilation_database(ROOT,a.compile_commands)
flags='-m32 --coverage -fprofile-abs-path'
with (out/'tests.log').open('w') as log:
 subprocess.run([sys.executable,str(ROOT/'tests/runners/run-native-tests.py'),'--platform','linux','--coverage','--output',str(out/'native')],env=env,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
merged={};raw=out/'gcov-json';raw.mkdir();inputs=[]
for i,counter in enumerate(sorted((out/'native').glob('*.gcda'))):
 payload=coverage.read_gcov(counter,ROOT);coverage.merge_lines(ROOT,payload,merged)
 (raw/f'test-{i}.json').write_text(json.dumps(payload));inputs.append({'counter':str(counter.relative_to(out)),'sha256':coverage.digest(counter)})
if not inputs:raise ValueError('No executed GCC counters')
baseline=out/'unexecuted-product';baseline.mkdir()
with (out/'baseline.log').open('w') as log:
 for i,entry in enumerate(entries):
  args=[];iterator=iter(entry['arguments'])
  for arg in iterator:
   if arg in {'-o','-MF','-MT','-MQ'}:next(iterator)
   elif arg not in {'-MD','-MMD','-MP'}:args.append(arg)
  obj=baseline/f'unit-{i}.o';args+=['--coverage','-fprofile-abs-path','-O0','-o',str(obj)]
  subprocess.run(args,cwd=entry['directory'],env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
  payload=coverage.read_gcov(obj.with_suffix('.gcno'),ROOT);coverage.merge_lines(ROOT,payload,merged,baseline=True)
  (raw/f'baseline-{i}.json').write_text(json.dumps(payload))
if start!=coverage.source_state(ROOT):raise ValueError('Sources changed during coverage')
report=out/'coverage.xml';coverage.write_report(report,merged)
receipt={'schema':1,'kind':'native','source_state':start,'report':report.name,'report_sha256':coverage.digest(report),'all_suites_passed':True,'test_flags':flags,'counter_inputs':inputs,'product_units':len(entries),'runtime_acceptance':False}
(out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('NATIVE_COVERAGE_OK',sum(sum(rows.values()) for rows in merged.values()),'/',sum(len(rows) for rows in merged.values()))
