"""Explicit publication only: validated pair, tag, draft upload, then publish."""
import argparse,datetime,re,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'package'))
from release_receipt import read_receipt, validate_zip
from release_identity import resolve

def validate_release_pair(pair, sha, receipts):
    for path in pair:
        if not path.is_file() or not path.stat().st_size:raise ValueError('Both validated release ZIPs must exist')
    for platform,path in zip(('linux','windows'),pair):
        receipt=read_receipt(receipts/(platform+'.json'))
        validate_zip(path,receipt,platform,sha,Path(__file__).resolve().parents[2])

def publish(ref,sha,run_url,attempt,assets,runner=subprocess.run,receipts=None):
    info=resolve(ref,sha)
    if not info['release_tag'] or not re.fullmatch(r'[0-9a-f]{40}',sha):raise ValueError('Publication requires a supported ref and full SHA')
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+',run_url) or not str(attempt).isdigit():raise ValueError('Invalid CI evidence')
    pair=[assets/(info[platform+'_basename']+'.zip') for platform in ('linux','windows')]
    validate_release_pair(pair,sha,receipts if receipts is not None else assets/'receipts')
    def run(args):return runner(args,check=True,text=True,capture_output=True)
    # Access/list failures abort before any mutation. API pagination avoids assuming
    # channel releases appear among only the first N records.
    listing=run(['gh','api','--paginate','repos/{owner}/{repo}/releases','--jq','.[].tag_name'])
    existing=info['release_tag'] in listing.stdout.splitlines()
    tag=info['release_tag']
    if ref in {'main','develop'}:
        run(['git','config','user.name','github-actions[bot]'])
        run(['git','config','user.email','41898282+github-actions[bot]@users.noreply.github.com'])
        run(['git','tag','-f',tag,sha]);run(['git','push','origin','refs/tags/'+tag,'--force'])
    notes='\n'.join([f"Actualización de {info['release_name']}.",'Fecha de actualización (UTC): '+datetime.datetime.now(datetime.timezone.utc).isoformat(),f"Commit: [{sha}]({run_url.split('/actions/runs/')[0]}/commit/{sha})",f'Ejecución de CI: {run_url} (intento {attempt})'])
    if ref in {'main','develop'}:
        if existing:run(['gh','release','delete',tag,'--yes'])
        run(['gh','release','create',tag,'--title',info['release_name'],'--draft','--latest=false','--target',sha,'--notes',notes])
    elif not existing:
        run(['gh','release','create',tag,'--title',info['release_name'],'--draft','--latest=false','--target',sha,'--notes',notes])
    run(['gh','release','upload',tag,*map(str,pair),'--clobber'])
    run(['gh','release','edit',tag,'--draft=false','--prerelease='+info['prerelease'],'--latest='+info['latest']])

def main():
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--ref',required=True);p.add_argument('--sha',required=True);p.add_argument('--run-url',required=True);p.add_argument('--attempt',required=True);p.add_argument('--assets',type=Path,default=Path('dist/release'));p.add_argument('--receipts',type=Path,default=Path('.build/release-receipts'));a=p.parse_args()
    if not a.publish:p.error('Explicit --publish is required')
    publish(a.ref,a.sha,a.run_url,a.attempt,a.assets,receipts=a.receipts)
if __name__=='__main__':main()
