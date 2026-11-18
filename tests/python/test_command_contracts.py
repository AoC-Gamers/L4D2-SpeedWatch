"""Run canonical command bodies with isolated files and controlled external tools."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts/package'))
sys.path.insert(0, str(ROOT/'scripts/ci'))


def command(relative):
    spec = importlib.util.spec_from_file_location(Path(relative).stem.replace('-', '_'), ROOT/relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommandContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='speedwatch command ')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def invoke(self, module, *args):
        with patch.object(sys, 'argv', ['command', *map(str, args)]):
            return module.main(self.root)

    def test_sourcemod_download_verifies_hash_and_reuses_verified_sdk(self):
        module = command('scripts/deps/fetch-sourcemod.py')
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode='w:gz') as package:
            entry = tarfile.TarInfo('addons/sourcemod/scripting/spcomp64')
            payload = b'compiler fixture, never executed'
            entry.size = len(payload)
            package.addfile(entry, io.BytesIO(payload))
            header = tarfile.TarInfo('addons/sourcemod/scripting/include/sourcemod.inc')
            header.size = len(payload)
            package.addfile(header, io.BytesIO(payload))
        content = archive.getvalue()
        lock = self.root/'scripts/deps/sourcepawn-package.lock.json'
        lock.parent.mkdir(parents=True)
        settings = {'url':'https://example.invalid/sdk.tar.gz', 'sha256':hashlib.sha256(content).hexdigest()}
        lock.write_text(json.dumps(settings))
        with patch.object(module.urllib.request, 'urlopen', side_effect=lambda *a, **kw: io.BytesIO(content)) as download:
            self.invoke(module)
            destination = self.root/'.deps/smx/sourcemod-linux'
            self.assertEqual((destination/'package.sha256').read_text().strip(), settings['sha256'])
            self.invoke(module)
            self.assertEqual(download.call_count, 1)
            (destination/'package.sha256').write_text('unverified')
            with self.assertRaisesRegex(RuntimeError, 'Existing unverified'):
                self.invoke(module)
            settings['sha256'] = '0'*64
            lock.write_text(json.dumps(settings))
            with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                self.invoke(module, '--destination', 'new/sdk')
        with self.assertRaises(SystemExit):
            self.invoke(module, '--version', '1.11')

    def test_extension_fetch_honors_pin_and_dirty_checkout_guards(self):
        module = command('scripts/deps/fetch-extension-deps.py')
        spec = {'repository':'example/sdk', 'revision':'a'*40}
        item = ('sourcemod-1.12', spec)
        current = subprocess.CompletedProcess([], 0, stdout=spec['revision'])
        with patch.object(module.subprocess, 'run', return_value=current) as run, patch.object(module.subprocess, 'check_output', return_value=''):
            module.fetch(item, self.root)
            calls = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any('init' in call for call in calls))
            self.assertFalse(any('fetch' in call for call in calls))
            self.assertTrue(any('submodule' in call and 'sourcepawn' in call for call in calls))
        with patch.object(module.subprocess, 'run', return_value=current), patch.object(module.subprocess, 'check_output', return_value=' M file'):
            with self.assertRaisesRegex(RuntimeError, 'Dirty tracked'):
                module.fetch(item, self.root)
        old = subprocess.CompletedProcess([], 1, stdout='')
        with patch.object(module.subprocess, 'run', return_value=old), patch.object(module.subprocess, 'check_output', return_value='?? untracked'):
            with self.assertRaisesRegex(RuntimeError, 'Dirty dependency'):
                module.fetch(item, self.root)
        with patch.object(module.subprocess, 'run', return_value=old) as run, patch.object(module.subprocess, 'check_output', return_value=''):
            module.fetch(('mmsource-1.12',spec), self.root)
            calls = [call.args[0] for call in run.call_args_list]
            self.assertTrue(any('fetch' in call and spec['revision'] in call for call in calls))
            self.assertTrue(any('checkout' in call and '--detach' in call for call in calls))
            self.assertTrue(any('--recursive' in call for call in calls))

    def test_extension_dependencies_record_lock_and_isolate_platform_venv(self):
        module = command('scripts/deps/fetch-extension-deps.py')
        lock = {'ambuild':{'repository':'example/ambuild', 'revision':'a'*40}}
        (self.root/'scripts/deps/dependencies.lock.json').parent.mkdir(parents=True,exist_ok=True)
        (self.root/'scripts/deps/dependencies.lock.json').write_text(json.dumps(lock))
        for platform in ('linux','windows'):
            dest = self.root/platform
            dest.mkdir()
            with patch.object(module, 'fetch') as fetch, patch.object(module, 'run') as run:
                self.invoke(module, '--platform', platform, '--destination', dest)
                fetch.assert_called_once_with(('ambuild',lock['ambuild']),dest)
                self.assertEqual(json.loads((dest/'resolved.json').read_text()), lock)
                self.assertIn('Scripts/python.exe' if platform=='windows' else 'bin/python', str(run.call_args.args))
                self.assertTrue(any('venv' in call.args for call in run.call_args_list))

    def test_api_compile_matrix_and_compiler_failure(self):
        module = command('scripts/build/build-api-tests.py')
        with patch.object(module.subprocess, 'run') as run:
            self.invoke(module, '--spcomp', 'sdk/spcomp64')
            calls = [call.args[0] for call in run.call_args_list]
            self.assertEqual(len(calls), 3)
            self.assertTrue(all('-E' in call for call in calls))
            self.assertIn('SPEEDWATCH_TEST_REQUIRED=1', calls[1])
            self.assertNotIn('SPEEDWATCH_TEST_REQUIRED=1', calls[0])
            self.assertIn('l4d2_speedwatch_test.sp', calls[1][1])
            self.assertIn('l4d2_speedwatch_core_test.sp', calls[2][1])
        with patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(2, ['compiler'])):
            with self.assertRaises(subprocess.CalledProcessError):
                self.invoke(module, '--spcomp', 'sdk/spcomp64')

    def test_clean_preserves_shared_and_other_platform_and_rejects_symlink(self):
        module = command('scripts/tools/clean-platform.py')
        # The command's default root is bypassed only for this isolated checkout.
        for path in ('.build/exts-linux/file','.build/exts-windows/file','.build/smx/file','dist/linux/artifact/file','.build/release-receipts/linux.json','.build/release-receipts/windows.json'):
            target = self.root/path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('keep')
        self.invoke(module, 'linux')
        self.assertFalse((self.root/'.build/exts-linux').exists())
        self.assertFalse((self.root/'dist/linux/artifact').exists())
        self.assertTrue((self.root/'.build/exts-windows/file').is_file())
        self.assertTrue((self.root/'.build/smx/file').is_file())
        self.assertFalse((self.root/'.build/release-receipts/linux.json').exists())
        self.assertTrue((self.root/'.build/release-receipts/windows.json').is_file())
        (self.root/'.build/exts-linux').symlink_to(self.root/'.build/smx', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.invoke(module, 'linux')
        with self.assertRaises(SystemExit):
            self.invoke(module, 'invalid')

    def test_release_identity_outputs_json_or_github_file_without_publishing(self):
        module = command('scripts/ci/release-identity.py')
        output = io.StringIO()
        with patch.dict(os.environ, {'GITHUB_OUTPUT':''}), contextlib.redirect_stdout(output), patch.object(sys,'argv',['identity','--ref','develop','--sha','a'*40,'--platform','windows']):
            module.main()
        self.assertEqual(json.loads(output.getvalue())['basename'], 'l4d2-speedwatch-develop-windows')
        path = self.root/'github-output'
        with patch.dict(os.environ, {'GITHUB_OUTPUT':str(path)}), patch.object(sys,'argv',['identity','--ref','main']):
            module.main()
        self.assertIn('release_tag=channel/latest\n', path.read_text())

    def test_artifact_validator_cli_delegates_and_propagates_rejection(self):
        module = command('scripts/package/validate-artifact.py')
        with patch.object(sys,'argv',['validate','--root',str(self.root),'--artifact','payload']), patch.object(module,'validate_artifact') as validate:
            self.assertEqual(module.main(),0)
            validate.assert_called_once_with(self.root,self.root/'payload')
        with patch.object(sys,'argv',['validate','--root',str(self.root)]), patch.object(module,'validate_artifact',side_effect=ValueError('unexpected payload')):
            with self.assertRaisesRegex(ValueError,'unexpected payload'):
                module.main()

    def test_msvc_filters_runner_variables_and_reports_missing_tools(self):
        module = command('scripts/build/setup-msvc.py')
        env = {'GITHUB_ENV':str(self.root/'github-env'), 'ProgramFiles(x86)':str(self.root/'programs'),
               'COMSPEC':'cmd.exe','UNCHANGED':'same'}
        install = self.root/'Visual Studio'
        vcvars = install/'VC/Auxiliary/Build/vcvarsall.bat'
        vcvars.parent.mkdir(parents=True)
        vcvars.write_text('fixture, never executed')
        response = '\n'.join(['Path=C:\\VC\\bin','INCLUDE=C:\\VC\\include','GITHUB_TOKEN=blocked',
                              'RUNNER_TEMP=blocked','NODE_OPTIONS=blocked','=C:=hidden','malformed','UNCHANGED=same'])
        with patch.object(module, 'os', types.SimpleNamespace(name='nt',environ=env)), patch.object(module.subprocess,'check_output', side_effect=[str(install),response]) as query:
            module.main()
        self.assertEqual((self.root/'github-env').read_text(), 'Path=C:\\VC\\bin\nINCLUDE=C:\\VC\\include\n')
        self.assertIn(' x86 >nul && set', query.call_args.args[0])
        for installation in ('',str(self.root/'missing')):
            with patch.object(module,'os',types.SimpleNamespace(name='nt',environ=env)), patch.object(module.subprocess,'check_output',return_value=installation):
                with self.assertRaises(SystemExit):module.main()
        with patch.object(module,'os',types.SimpleNamespace(name='posix')):
            with self.assertRaises(SystemExit):module.main()

    def test_native_driver_builds_validates_and_records_provenance(self):
        module = command('scripts/build/build-extension.py')
        import shutil
        compiler = shutil.which('cc')
        if not compiler:self.skipTest('C compiler required for ELF fixture')
        fixture = self.root/'fixture.so'
        subprocess.run([compiler,'-m32','-nostdlib','-shared','-x','c','-','-o',str(fixture)],
                       input='void GetSMExtAPI(void) {}\nvoid CreateInterface_MMS(void) {}\n',text=True,check=True,capture_output=True)
        lock = {'sdk':{'revision':'a'*40}}
        (self.root/'scripts/deps/dependencies.lock.json').parent.mkdir(parents=True,exist_ok=True)
        (self.root/'scripts/deps/dependencies.lock.json').write_text(json.dumps(lock))
        (self.root/'extension').mkdir()
        (self.root/'extension/unit.cpp').write_text('int fixture;')
        for name in ('AMBuildScript','configure.py','PackageScript'):
            (self.root/name).write_text('# fixture\n')
        for directory in ('scripts/package','scripts/build'):
            (self.root/directory).mkdir(parents=True)
        (self.root/'scripts/package/package-map.json').write_text('{}')
        deps = self.root/'.deps/exts-linux'
        for name in ('venv/bin/python','venv/bin/ambuild','hl2sdk-l4d2','sourcemod-1.12','mmsource-1.12'):
            path = deps/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.touch()
        (deps/'resolved.json').write_text(json.dumps(lock))
        calls = []
        def execute(args, **kwargs):
            calls.append(args)
            if args[0]=='git':
                text = str(self.root) if '--show-toplevel' in args else 'b'*40
                return subprocess.CompletedProcess(args,0,stdout=text+'\n',stderr='')
            if str(args[0]).endswith('/ambuild'):
                output = Path(kwargs['cwd'])/'package/addons/sourcemod/extensions/l4d2_speedwatch_core.ext.2.l4d2.so'
                output.parent.mkdir(parents=True)
                output.write_bytes(fixture.read_bytes())
            return subprocess.CompletedProcess(args,0,stdout='controlled build completed\n')
        def query(args, **kwargs):
            if args[0]=='git':return 'a'*40 if 'rev-parse' in args else ''
            return 'fixture GCC\n'
        with patch.object(module.subprocess,'run',side_effect=execute), patch.object(module.subprocess,'check_output',side_effect=query):
            self.invoke(module,'--platform','linux')
        info = json.loads((self.root/'.build/exts-linux/build-info.json').read_text())
        self.assertEqual(info['project_sha'],'b'*40)
        self.assertEqual(info['dependencies'],lock)
        self.assertEqual(info['binary_sha256'],hashlib.sha256(fixture.read_bytes()).hexdigest())
        self.assertTrue(any('--sdks' in call and 'l4d2' in call for call in calls))
        self.assertTrue(any(str(self.root/'scripts/build/export-compile-commands.py') in call for call in calls))
        for response in ('wrong-revision',' M changed'):
            with patch.object(module.subprocess,'check_output',return_value=response):
                with self.assertRaisesRegex(RuntimeError,'differs from lock'):
                    self.invoke(module,'--platform','linux')
        with self.assertRaises(ValueError):
            self.invoke(module,'--platform','linux','--output',str(self.root/'.build'))
        with self.assertRaises(RuntimeError):
            self.invoke(module,'--platform','linux','--deps',str(self.root/'missing'))
        with self.assertRaises(SystemExit):
            self.invoke(module,'--platform','windows')

    def test_compile_database_preserves_real_task_cwd_and_rejects_ambiguity(self):
        module = command('scripts/build/export-compile-commands.py')
        folder = self.root/'objects with spaces'
        folder.mkdir()
        (folder/'unit.cpp').write_text('int unit;')
        args = ['c++','-m32','-DORDER=1','-UORDER','-DORDER=2','-c','unit.cpp','-o','unit.o']
        node = types.SimpleNamespace(type='cxx', blob={'argv':args}, folder=types.SimpleNamespace(path=folder.name))
        other = types.SimpleNamespace(type='copy')
        tasks = [node,other]
        class Database:
            def __init__(self, path):self.path=path
            def connect(self):pass
            def query_commands(self, append):
                for task in tasks:append(task)
            def close(self):pass
        sdk = types.SimpleNamespace(database=types.SimpleNamespace(Database=Database),nodetypes=types.SimpleNamespace(Cxx='cxx'))
        with patch.dict(sys.modules,{'ambuild2':sdk}), patch.object(sys,'argv',['export','--build',str(self.root)]):
            module.main()
            data = json.loads((self.root/'compile_commands.json').read_text())
            self.assertEqual(data,[{'directory':str(folder),'file':str(folder/'unit.cpp'),'arguments':args}])
            (folder/'second.cpp').write_text('int second;')
            args.append('second.cpp')
            with self.assertRaisesRegex(ValueError,'Ambiguous'):module.main()
            tasks.clear()
            with self.assertRaisesRegex(ValueError,'no compilation'):module.main()
