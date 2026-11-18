#!/usr/bin/env python3
"""Stage existing native binaries, merge with SMX, validate and archive per platform."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path
from artifact_contract import clean_output, load_manifest, plugin_paths, selected_files, validate_artifact, sourcepawn_inputs, native_source_hashes, tree_files, validate_basename
from native_binary import validate_binary
from installer_docs import installer_docs, stage_docs, verify_docs
from release_receipt import receipt_path, read_receipt, validate_zip

BUILD_INFO = 'build-info.json'
COMPILE_LOG = 'compile.log'
NATIVE_COMPILE_LOG = 'native-compile.log'

ROOT=Path(__file__).resolve().parents[2]
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def binary_path(platform): return Path('addons/sourcemod/extensions/l4d2_speedwatch_core.ext.2.l4d2.'+('so' if platform=='linux' else 'dll'))
def exact_files(tree,expected):
    actual=tree_files(tree)
    if actual!=expected: raise ValueError(f'Unexpected/missing files in {tree}: {actual ^ expected}')
    for p in actual:
        if not (tree/p).stat().st_size: raise ValueError(f'Empty file: {p}')
def native_metadata(root, tree, platform):
    info=json.loads((tree/BUILD_INFO).read_text())
    return validate_native_info(root,tree,platform,info)
def validate_native_info(root,tree,platform,info):
    if info['platform']!=platform or info['architecture']!='x86': raise ValueError('Platform/architecture mismatch')
    if info['binary_sha256']!=digest(tree/binary_path(platform)): raise ValueError('Native binary hash mismatch')
    if info['sources']!=native_source_hashes(root): raise ValueError('Native binary is stale relative to sources')
    if info['dependencies']!=json.loads((root/'scripts/deps/dependencies.lock.json').read_text()): raise ValueError('Dependency lock mismatch')
    validate_binary(tree/binary_path(platform),platform)
    return info
def validate_tree(root,tree,platform,receipt):
    manifest=load_manifest(root)
    docs = installer_docs(root, platform + ' x86', receipt['project_sha'])
    expected=set(plugin_paths(manifest))|selected_files(root,manifest['artifact'])|{binary_path(platform)}|docs.keys()
    exact_files(tree,expected)
    validate_native_info(root,tree,platform,receipt['native_build'])
    smx_info=receipt['sourcepawn_build']
    verify_docs(tree, docs)
    if smx_info['inputs']!=sourcepawn_inputs(root): raise ValueError('SourcePawn build is stale')
    for relative,expected_hash in smx_info['binaries'].items():
        if digest(tree/relative)!=expected_hash: raise ValueError('SourcePawn binary hash mismatch')
    for relative,expected_hash in receipt['runtime_files'].items():
        if digest(tree/relative)!=expected_hash: raise ValueError('Runtime file hash mismatch: '+relative)
    for relative in selected_files(root,manifest['artifact']):
        if digest(tree/relative)!=digest(root/relative): raise ValueError('Stale source payload: '+str(relative))
    if set(receipt['runtime_files']) != {str(p).replace('\\','/') for p in expected}: raise ValueError('Incomplete runtime hashes')
    for relative in plugin_paths(manifest):
        if (tree/relative).read_bytes()[:4] != b'FFPS': raise ValueError('Invalid SourcePawn binary')
def validate(root,tree,platform):
    receipt=read_receipt(receipt_path(root,platform))
    validate_tree(root,tree,platform,receipt)
    archive=root/'dist/release'/receipt['archive_name']
    validate_basename(archive.stem)
    validate_zip(archive,receipt,platform,receipt['native_build'].get('project_sha'),root)

def stage(root,build,out,platform):
    if out==build or out in build.parents or build in out.parents:
        raise ValueError('Build and staging trees must be separate')
    binary=binary_path(platform)
    # AMBuild tree also contains object files; only package/ is distributable.
    package=build/'package'
    exact_files(package,{binary})
    for name in (BUILD_INFO,COMPILE_LOG):
        if not (build/name).is_file() or not (build/name).stat().st_size: raise ValueError('Missing native build metadata')
    scratch_info=json.loads((build/BUILD_INFO).read_text())
    if scratch_info['binary_sha256']!=digest(package/binary): raise ValueError('Native build hash mismatch')
    # Validate source and ABI before replacing the staging tree.
    if scratch_info['sources']!=native_source_hashes(root): raise ValueError('Native build is stale')
    if scratch_info['platform']!=platform: raise ValueError('Wrong platform')
    validate_binary(package/binary,platform)
    clean_output(root,out)
    shutil.copytree(package,out,dirs_exist_ok=True)
    shutil.copy2(build/BUILD_INFO,out/BUILD_INFO)
    shutil.copy2(build/COMPILE_LOG,out/NATIVE_COMPILE_LOG)
def release(root,smx,extension,out,platform,basename):
    validate_basename(basename)
    for source in (smx,extension):
        if out==source or out in source.parents or source in out.parents:
            raise ValueError('Release and input trees must be separate')
    validate_artifact(root,smx)
    binary=binary_path(platform)
    exact_files(extension,{binary,Path(NATIVE_COMPILE_LOG),Path(BUILD_INFO)})
    info=native_metadata(root,extension,platform)
    clean_output(root,out)
    shutil.copytree(smx,out,dirs_exist_ok=True)
    shutil.copytree(extension,out,dirs_exist_ok=True)
    smx_info=json.loads((out/'sourcepawn-build-info.json').read_text())
    for name in (COMPILE_LOG,NATIVE_COMPILE_LOG,BUILD_INFO,'sourcepawn-build-info.json'):
        (out/name).unlink()
    stage_docs(out, installer_docs(root, platform + ' x86', info.get('project_sha')))
    receipt={'schema':1,'platform':platform,'architecture':'x86',
             'project_sha':info.get('project_sha'),'native_build':info,'sourcepawn_build':smx_info,
             'runtime_files':{p.as_posix():digest(out/p) for p in tree_files(out)}}
    validate_tree(root,out,platform,receipt)
    destination=root/'dist/release';destination.mkdir(parents=True,exist_ok=True)
    archive=shutil.make_archive(str(destination/basename),'zip',root_dir=out)
    archive=Path(archive)
    receipt.update(archive_name=archive.name,archive_sha256=digest(archive))
    validate_zip(archive,receipt,platform,receipt['project_sha'],root)
    evidence=receipt_path(root,platform)
    evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps(receipt,indent=2)+'\n')
    print(archive)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['stage','release','validate']);p.add_argument('--platform',choices=['linux','windows'],required=True)
    p.add_argument('--root',default=str(ROOT));p.add_argument('--extension');p.add_argument('--smx');p.add_argument('--output');p.add_argument('--basename')
    a=p.parse_args();root=Path(a.root).resolve();out=(root/(a.output or ('dist/'+a.platform+'/artifact'))).resolve()
    if a.action=='stage': stage(root,(root/a.extension).resolve(),out,a.platform)
    elif a.action=='release': release(root,(root/a.smx).resolve(),(root/a.extension).resolve(),out,a.platform,a.basename)
    else: validate(root,out,a.platform);print('NATIVE_ARTIFACT_VALIDATION_OK')
