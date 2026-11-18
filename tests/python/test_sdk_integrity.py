"""SDK identity regressions against real archive bytes and isolated Git checkouts."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/deps'))
from sourcepawn_sdk import describe_sdk, archive_inputs
spec=importlib.util.spec_from_file_location('native_sdk_driver',ROOT/'scripts/build/build-extension.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)


class SourcePawnSdkTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.sdk=self.root/'.deps/smx/sourcemod-linux'
        self.compiler=self.sdk/'addons/sourcemod/scripting/spcomp64'
        self.header=self.compiler.parent/'include/sourcemod.inc'
        self.header.parent.mkdir(parents=True)
        self.compiler.write_bytes(b'compiler fixture')
        self.header.write_bytes(b'header fixture')
        self.archive=self.sdk.parent/'sourcemod-linux.tar.gz'
        with tarfile.open(self.archive,'w:gz') as package:
            for path in (self.compiler,self.header):package.add(path,arcname=path.relative_to(self.sdk))
        self.lock={'sha256':hashlib.sha256(self.archive.read_bytes()).hexdigest(),'version':'fixture','url':'https://example.invalid/sdk'}
        lock=self.root/'scripts/deps/sourcepawn-package.lock.json';lock.parent.mkdir(parents=True);lock.write_text(json.dumps(self.lock))
        self.marker=self.sdk/'package.sha256';self.marker.write_text(self.lock['sha256'])

    def test_locked_archive_is_verified_and_external_sdk_is_not_claimed_as_locked(self):
        info=describe_sdk(self.root,self.compiler)
        self.assertEqual(info['sdk_origin'],'locked-archive')
        self.assertEqual(info['sdk_package'],self.lock)
        external=self.root/'external/sdk'
        (external/'include').mkdir(parents=True)
        (external/'spcomp').write_bytes(b'external compiler')
        (external/'include/sourcemod.inc').write_bytes(b'external header')
        actual=describe_sdk(self.root,external/'spcomp')
        self.assertEqual(actual['sdk_origin'],'external');self.assertIsNone(actual['sdk_package'])
        self.assertNotEqual(actual['compiler_sha256'],info['compiler_sha256'])

    def test_modified_compiler_headers_or_added_headers_cannot_reuse_lock(self):
        for path in (self.compiler,self.header,self.header.with_name('shadow.inc')):
            with self.subTest(path=path):
                original=path.read_bytes() if path.exists() else None
                path.write_bytes(b'altered SDK input')
                with self.assertRaisesRegex(ValueError,'differ from pinned archive'):describe_sdk(self.root,self.compiler)
                if original is None:path.unlink()
                else:path.write_bytes(original)

    def test_missing_marker_or_archive_and_archive_tampering_fail(self):
        self.marker.unlink()
        with self.assertRaisesRegex(ValueError,'marker'):describe_sdk(self.root,self.compiler)
        self.marker.write_text(self.lock['sha256'])
        original=self.archive.read_bytes();self.archive.unlink()
        with self.assertRaisesRegex(ValueError,'archive missing'):describe_sdk(self.root,self.compiler)
        self.archive.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):describe_sdk(self.root,self.compiler)

    def test_linked_inputs_and_archive_links_are_rejected(self):
        self.header.unlink();self.header.symlink_to(self.compiler)
        with self.assertRaisesRegex(ValueError,'symlink'):describe_sdk(self.root,self.compiler)
        archive=self.root/'linked.tar.gz'
        with tarfile.open(archive,'w:gz') as package:
            entry=tarfile.TarInfo('addons/sourcemod/scripting/spcomp64');entry.type=tarfile.SYMTYPE;entry.linkname='elsewhere';package.addfile(entry)
        with self.assertRaisesRegex(ValueError,'Invalid compiler input'):archive_inputs(archive,self.compiler)


class NativeSdkTests(unittest.TestCase):
    def test_untracked_and_ignored_headers_and_modified_sources_fail_before_build(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);deps=root/'deps';sdk=deps/'hl2sdk-l4d2';sdk.mkdir(parents=True)
            for name in ('sourcemod-1.12','mmsource-1.12'):(deps/name).mkdir()
            for name in ('python','ambuild'):(deps/name).touch()
            def git(*args):return subprocess.check_output(['git','-C',str(sdk),*args],text=True).strip()
            git('init','-q');(sdk/'tracked.h').write_text('pinned');(sdk/'.gitignore').write_text('ignored.h\n')
            git('add','.');git('-c','user.name=SDK Test','-c','user.email=test@example.invalid','commit','-qm','fixture')
            lock={'hl2sdk-l4d2':{'revision':git('rev-parse','HEAD')}}
            (root/'scripts/deps/dependencies.lock.json').parent.mkdir(parents=True,exist_ok=True)
            (root/'scripts/deps/dependencies.lock.json').write_text(json.dumps(lock))
            verify=lambda:driver.verify_dependencies(root,deps,deps/'python',deps/'ambuild')
            verify()
            for name in ('new.h','ignored.h','tracked.h'):
                path=sdk/name;old=path.read_text() if path.exists() else None
                path.write_text('unexpected input')
                with self.subTest(name=name),self.assertRaisesRegex(RuntimeError,'differs from lock'):verify()
                if old is None:path.unlink()
                else:path.write_text(old)

    def test_generated_ambuild_copies_must_match_tracked_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory=Path(temporary)/'ambuild';directory.mkdir()
            source=directory/'ambuild2/module.py';source.parent.mkdir();source.write_text('verified source')
            copy=directory/'build/lib/ambuild2/module.py';copy.parent.mkdir(parents=True);copy.write_text(source.read_text())
            tracked={'ambuild2/module.py'}
            self.assertTrue(driver.generated_ambuild_copy(directory,'build/lib/ambuild2/module.py',tracked))
            copy.write_text('modified copy')
            self.assertFalse(driver.generated_ambuild_copy(directory,'build/lib/ambuild2/module.py',tracked))
            self.assertFalse(driver.generated_ambuild_copy(directory,'build/lib/new.py',tracked))
            self.assertFalse(driver.generated_ambuild_copy(directory,'elsewhere/module.py',tracked))

    def create_nested_sdk(self, base):
        def git(directory,*args):
            return subprocess.check_output(['git','-C',str(directory),*args],text=True,stderr=subprocess.PIPE).strip()
        def init(directory):
            directory.mkdir(parents=True);git(directory,'init','-q')
            (directory/'tracked.h').write_text('pinned header')
            (directory/'.gitignore').write_text('ignored.h\n')
        def commit(directory):
            git(directory,'add','.')
            git(directory,'-c','user.name=SDK Test','-c','user.email=test@example.invalid','commit','-qm','fixture')
        leaf=base/'leaf';init(leaf);commit(leaf)
        upstream=base/'upstream';init(upstream)
        git(upstream,'-c','protocol.file.allow=always','submodule','add','-q',str(leaf),'vendor/deep');commit(upstream)
        deps=base/'deps';sdk=deps/'sourcemod-1.12';init(sdk)
        git(sdk,'-c','protocol.file.allow=always','submodule','add','-q',str(upstream),'public/amtl');commit(sdk)
        git(sdk,'-c','protocol.file.allow=always','submodule','update','--init','--recursive')
        for name in ('hl2sdk-l4d2','mmsource-1.12'):(deps/name).mkdir()
        for name in ('python','ambuild'):(deps/name).touch()
        (base/'scripts/deps/dependencies.lock.json').parent.mkdir(parents=True,exist_ok=True)
        (base/'scripts/deps/dependencies.lock.json').write_text(json.dumps({'sourcemod-1.12':{'revision':git(sdk,'rev-parse','HEAD')}}))
        return deps,sdk,git

    def test_submodule_headers_are_checked_at_every_depth(self):
        with tempfile.TemporaryDirectory(prefix='SDK submodules ') as temporary:
            base=Path(temporary);deps,sdk,_=self.create_nested_sdk(base)
            def verify():driver.verify_dependencies(base,deps,deps/'python',deps/'ambuild')
            verify()
            for module in (sdk/'public/amtl',sdk/'public/amtl/vendor/deep'):
                for name in ('ignored.h','untracked.h','tracked.h'):
                    with self.subTest(module=module,name=name):
                        path=module/name;original=path.read_bytes() if path.exists() else None
                        path.write_text('unexpected compiler input')
                        with self.assertRaisesRegex(RuntimeError,'differs from lock'):verify()
                        if original is None:path.unlink()
                        else:path.write_bytes(original)
                        verify()

    def test_submodule_wrong_revision_and_uninitialized_inputs_are_rejected(self):
        with tempfile.TemporaryDirectory(prefix='SDK submodules ') as temporary:
            base=Path(temporary);deps,sdk,git=self.create_nested_sdk(base)
            def verify():driver.verify_dependencies(base,deps,deps/'python',deps/'ambuild')
            verify()
            module=sdk/'public/amtl/vendor/deep';pinned=git(module,'rev-parse','HEAD')
            (module/'tracked.h').write_text('different revision');git(module,'add','tracked.h')
            git(module,'-c','user.name=SDK Test','-c','user.email=test@example.invalid','commit','-qm','different revision')
            with self.assertRaisesRegex(RuntimeError,'differs from lock'):verify()
            git(module,'checkout','--detach',pinned);verify()
            git(sdk/'public/amtl','submodule','deinit','-f','vendor/deep')
            verify()  # Optional submodules may remain absent or empty.
            (module/'ignored.h').write_text('input without a verified checkout')
            with self.assertRaisesRegex(RuntimeError,'files without an initialized checkout'):verify()
