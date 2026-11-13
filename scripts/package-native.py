#!/usr/bin/env python3
"""Stage existing native binaries, merge with SMX, validate and archive per platform."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from artifact_manifest import clean_output, load_manifest, plugin_paths, selected_files, validate_artifact, sourcepawn_inputs, native_source_hashes
from native_binary import validate_binary
ROOT=Path(__file__).resolve().parents[1]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def binary_path(platform): return Path('addons/sourcemod/extensions/l4d2_speedwatch_core.ext.'+('so' if platform=='linux' else 'dll'))
def exact_files(tree,expected):
    actual={p.relative_to(tree) for p in tree.rglob('*') if p.is_file()}
    if actual!=expected: raise ValueError(f'Unexpected/missing files in {tree}: {actual ^ expected}')
    for p in actual:
        if not (tree/p).stat().st_size: raise ValueError(f'Empty file: {p}')
def native_metadata(root, tree, platform):
    info=json.loads((tree/'build-info.json').read_text())
    if info['platform']!=platform or info['architecture']!='x86': raise ValueError('Platform/architecture mismatch')
    if info['binary_sha256']!=digest(tree/binary_path(platform)): raise ValueError('Native binary hash mismatch')
    if info['sources']!=native_source_hashes(root): raise ValueError('Native binary is stale relative to sources')
    if info['dependencies']!=json.loads((root/'dependencies.lock.json').read_text()): raise ValueError('Dependency lock mismatch')
    validate_binary(tree/binary_path(platform),platform)
    return info
def validate(root,tree,platform):
    manifest=load_manifest(root)
    expected=set(plugin_paths(manifest))|selected_files(root,manifest['artifact'])|{binary_path(platform),Path('LICENSE'),Path('compile.log'),Path('native-compile.log'),Path('build-info.json'),Path('sourcepawn-build-info.json')}
    exact_files(tree,expected)
    info=native_metadata(root,tree,platform)
    smx_info=json.loads((tree/'sourcepawn-build-info.json').read_text())
    if smx_info['inputs']!=sourcepawn_inputs(root): raise ValueError('SourcePawn build is stale')
    for relative,expected_hash in smx_info['binaries'].items():
        if digest(tree/relative)!=expected_hash: raise ValueError('SourcePawn binary hash mismatch')
    for relative,expected_hash in info['runtime_files'].items():
        if digest(tree/relative)!=expected_hash: raise ValueError('Runtime file hash mismatch: '+relative)
    for relative in selected_files(root,manifest['artifact']):
        if digest(tree/relative)!=digest(root/relative): raise ValueError('Stale source payload: '+str(relative))
    if set(info['runtime_files']) != {str(p).replace('\\','/') for p in expected if p!=Path('build-info.json')}: raise ValueError('Incomplete runtime hashes')
    for relative in plugin_paths(manifest):
        if (tree/relative).read_bytes()[:4] != b'FFPS': raise ValueError('Invalid SourcePawn binary')
def stage(root,build,out,platform):
    if out==build or out in build.parents or build in out.parents:
        raise ValueError('Build and staging trees must be separate')
    binary=binary_path(platform)
    # AMBuild tree also contains object files; only package/ is distributable.
    package=build/'package'
    exact_files(package,{binary})
    for name in ('build-info.json','compile.log'):
        if not (build/name).is_file() or not (build/name).stat().st_size: raise ValueError('Missing native build metadata')
    scratch_info=json.loads((build/'build-info.json').read_text())
    if scratch_info['binary_sha256']!=digest(package/binary): raise ValueError('Native build hash mismatch')
    # Validate source and ABI before replacing the staging tree.
    if scratch_info['sources']!=native_source_hashes(root): raise ValueError('Native build is stale')
    if scratch_info['platform']!=platform: raise ValueError('Wrong platform')
    validate_binary(package/binary,platform)
    clean_output(root,out)
    shutil.copytree(package,out,dirs_exist_ok=True)
    shutil.copy2(build/'build-info.json',out/'build-info.json')
    shutil.copy2(build/'compile.log',out/'native-compile.log')
def release(root,smx,extension,out,platform,basename):
    if not basename or Path(basename).name!=basename or basename in ('.','..'): raise ValueError('Invalid basename')
    for source in (smx,extension):
        if out==source or out in source.parents or source in out.parents:
            raise ValueError('Release and input trees must be separate')
    validate_artifact(root,smx)
    binary=binary_path(platform)
    exact_files(extension,{binary,Path('native-compile.log'),Path('build-info.json')})
    info=native_metadata(root,extension,platform)
    clean_output(root,out)
    shutil.copytree(smx,out,dirs_exist_ok=True)
    shutil.copytree(extension,out,dirs_exist_ok=True)
    info['sourcepawn_compiler_log']=(smx/'compile.log').read_text()
    info['runtime_files']={str(p.relative_to(out)).replace('\\','/'):digest(p) for p in out.rglob('*') if p.is_file() and p.name!='build-info.json'}
    (out/'build-info.json').write_text(json.dumps(info,indent=2)+'\n')
    validate(root,out,platform)
    destination=root/'dist/release';destination.mkdir(parents=True,exist_ok=True)
    archive=shutil.make_archive(str(destination/basename),'zip',root_dir=out)
    print(archive)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','release','validate']);p.add_argument('--platform',choices=['linux','windows'],required=True)
    p.add_argument('--root',default=str(ROOT));p.add_argument('--extension');p.add_argument('--smx');p.add_argument('--output');p.add_argument('--basename')
    a=p.parse_args();root=Path(a.root).resolve();out=(root/(a.output or ('dist/artifact-'+a.platform))).resolve()
    if a.action=='stage': stage(root,(root/a.extension).resolve(),out,a.platform)
    elif a.action=='release': release(root,(root/a.smx).resolve(),(root/a.extension).resolve(),out,a.platform,a.basename)
    else: validate(root,out,a.platform);print('NATIVE_ARTIFACT_VALIDATION_OK')
