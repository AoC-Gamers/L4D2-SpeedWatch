import argparse
from pathlib import Path
import subprocess
p=argparse.ArgumentParser();p.add_argument('--spcomp',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];compiler=(root/a.spcomp).resolve()
out=root/'.build/tests';out.mkdir(parents=True,exist_ok=True)
for name,defines in [('l4d2_speedwatch_test',[]),('l4d2_speedwatch_test_required',['SPEEDWATCH_TEST_REQUIRED=1']),('l4d2_speedwatch_core_test',[])]:
    source='l4d2_speedwatch_test' if name.endswith('_required') else name
    subprocess.run([str(compiler),str(root/'addons/sourcemod/scripting'/f'{source}.sp'),
        '-i'+str(root/'addons/sourcemod/scripting/include'),'-i'+str(compiler.parent/'include'),'-o'+str(out/f'{name}.smx'),'-E',*defines],check=True)
