"""Explicit publication only: validated pair, tag, draft upload, then publish."""
import argparse,datetime,hashlib,json,os,re,subprocess,zipfile
from pathlib import Path
from release_identity import resolve

def validate_release_zip(path, platform, sha):
    with zipfile.ZipFile(path) as archive:
        payload=json.loads(archive.read('build-info.json'))
        if payload.get('project_sha')!=sha or payload.get('platform')!=platform or payload.get('architecture')!='x86':raise ValueError('ZIP commit/platform mismatch')
        names=archive.namelist()
        if len(names)!=len(set(names)) or len({n.casefold() for n in names})!=len(names):raise ValueError('Duplicate ZIP members')
        files={name for name in names if not name.endswith('/')}
        if files!=set(payload['runtime_files'])|{'build-info.json'}:raise ValueError('Unexpected ZIP payload')
        if any(Path(name).is_absolute() or '..' in Path(name).parts or '\\' in name for name in names):raise ValueError('Unsafe ZIP path')
        for name,expected in payload['runtime_files'].items():
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:raise ValueError('ZIP payload hash mismatch')


def validate_release_pair(pair, sha):
    for path in pair:
        if not path.is_file() or not path.stat().st_size:raise ValueError('Both validated release ZIPs must exist')
    for platform,path in zip(('linux','windows'),pair):
        validate_release_zip(path,platform,sha)

def publish(ref,sha,run_url,attempt,assets,runner=subprocess.run):
    info=resolve(ref,sha)
    if not info['release_tag'] or not re.fullmatch(r'[0-9a-f]{40}',sha):raise ValueError('Publication requires a supported ref and full SHA')
    if not re.fullmatch(r'https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/actions/runs/\d+',run_url) or not str(attempt).isdigit():raise ValueError('Invalid CI evidence')
    pair=[assets/(info[platform+'_basename']+'.zip') for platform in ('linux','windows')]
    validate_release_pair(pair,sha)
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
    p=argparse.ArgumentParser();p.add_argument('--publish',action='store_true');p.add_argument('--ref',required=True);p.add_argument('--sha',required=True);p.add_argument('--run-url',required=True);p.add_argument('--attempt',required=True);p.add_argument('--assets',type=Path,default=Path('dist/release'));a=p.parse_args()
    if not a.publish:p.error('Explicit --publish is required')
    publish(a.ref,a.sha,a.run_url,a.attempt,a.assets)
if __name__=='__main__':main()
