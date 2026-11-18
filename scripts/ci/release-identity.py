"""Resolve metadata only; never moves a tag or publishes."""
import argparse,json,os
from pathlib import Path
from release_identity import resolve


def main():
    p=argparse.ArgumentParser();p.add_argument('--ref',default='local');p.add_argument('--sha',default='');p.add_argument('--platform',choices=['linux','windows'],default='linux');a=p.parse_args()
    values=resolve(a.ref,a.sha);values['basename']=values[a.platform+'_basename']
    if os.environ.get('GITHUB_OUTPUT'):
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as out:
            out.write(''.join(f'{k}={v}\n' for k,v in values.items()))
    else:print(json.dumps(values,sort_keys=True))


if __name__ == '__main__':
    main()
