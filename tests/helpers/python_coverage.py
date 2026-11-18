"""Enumerate all Python product files using coverage.py executable statements."""
import argparse,json
from pathlib import Path

def collect(root,measurement):
    files={}
    for path in sorted((root/'scripts').rglob('*.py')):
        _,statements,excluded,missing,_=measurement.analysis2(str(path.resolve()))
        statements=set(statements)-set(excluded);missing=set(missing)&statements
        files[path.relative_to(root).as_posix()]={'executed_lines':sorted(statements-missing),'missing_lines':sorted(missing),'excluded_lines':sorted(excluded)}
    if not files:raise ValueError('No Python product scripts')
    return {'files':files}

def main():
    import coverage
    if coverage.__version__!='7.13.5':raise ValueError('Unsupported coverage producer')
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);p.add_argument('--config',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    measurement=coverage.Coverage(config_file=a.config);measurement.load()
    a.output.write_text(json.dumps(collect(a.root.resolve(),measurement),indent=2)+'\n')
if __name__=='__main__':main()
