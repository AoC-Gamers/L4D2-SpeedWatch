# Adapted from AoC-Gamers/SteamWorks (GPL-3.0-or-later); see docs/build/sonar.md.
"""Exercise Make/script orchestration without a Sonar server or real credentials."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("make_sonar", ROOT / "scripts/tools/make_sonar.py")
sonar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sonar)


class SonarToolingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sonar tooling ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "sources with spaces"
        self.root.mkdir()
        for relative in ("Makefile", "scripts/tools/make_sonar.py", ".env.example", "tests/helpers/native_coverage.py"):
            dest = self.root / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, dest)
        (self.root / "extension").mkdir()
        self.source = self.root / "extension/unit.cpp"
        self.source.write_text("int value;\n")
        self.db = self.root / "build/compile_commands.json"
        self.db.parent.mkdir()
        self.entry = {"directory": str(self.root), "file": str(self.source),
                      "arguments": ["g++", "-m32", "-DTEST=1", "-c", str(self.source)]}
        self.db.write_text(json.dumps([self.entry]))
        (self.root / ".env").write_text((ROOT / '.env.example').read_text().replace('SONAR_PROJECT_KEY=L4D2-SpeedWatch\n','SONAR_PROJECT_KEY=L4D2-SpeedWatch-test\n'))
        (self.root / ".env.secret").write_text('SONAR_TOKEN="test-only-token"\n')
        (self.root / ".env.secret").chmod(0o600)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.trace = self.root / "calls.jsonl"
        self.system_include = self.root / 'compiler system headers'
        self.system_include.mkdir()
        compiler = self.bin / "g++"
        compiler.write_text(f'''#!{sys.executable}
import os,sys
if os.environ.get('SONAR_TOKEN') or os.environ.get('COMPILER_FAIL') or '-m32' not in sys.argv:
 sys.exit(2)
print('#define __GNUC__ 15\\n#define __GNUC_MINOR__ 7\\n#define __GNUC_PATCHLEVEL__ 2\\n#define __linux__ 1\\n#define __i386__ 1\\n#define __SIZEOF_POINTER__ 4')
if '-DTEST=1' in sys.argv: print('#define TEST 1')
print('#include <...> search starts here:\\n '+{str(self.system_include)!r}+'\\nEnd of search list.',file=sys.stderr)
''')
        compiler.chmod(0o755)
        for tool in ("cppcheck", "sonar-scanner"):
            script = self.bin / tool
            script.write_text(f'''#!{sys.executable}
import json,os,sys
tool={tool!r}
with open(os.environ['TEST_TRACE'],'a') as f:
 f.write(json.dumps({{'tool':tool,'argv':sys.argv[1:],'cwd':os.getcwd(),'token':os.environ.get('SONAR_TOKEN')}})+'\\n')
if tool=='cppcheck':
 xml='<results version="2"><errors><error id="preprocessorErrorDirective"/></errors></results>' if os.environ.get('PREPROCESSOR_ERROR') else '<results version="2"><errors/></results>'
 print('bad xml' if os.environ.get('BAD_XML') else xml,file=sys.stderr)
 sys.exit(int(os.environ.get('CPPCHECK_CODE','0')))
print('scanner saw '+os.environ.get('SONAR_TOKEN',''))
if os.environ.get('SCANNER_ANALYSIS_ERROR'): print('ERROR preprocessor: missing include directory',file=sys.stderr)
sys.exit(int(os.environ.get('SCANNER_CODE','0')))
''')
            script.chmod(0o755)

    def make(self, target="sonar", **extra):
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("SONAR_") and k not in {"MAKEFLAGS", "MFLAGS", "MAKEOVERRIDES"}}
        env.update(PATH=str(self.bin) + os.pathsep + os.defpath, TEST_TRACE=str(self.trace))
        env.update(extra)
        return subprocess.run(["make", "--no-print-directory", "-s", "-f", str(self.root / "Makefile"),
                               target, f"LINUX_BUILD_DIR={self.db.parent}"], cwd=self.temp.name,
                              env=env, capture_output=True, text=True)

    def calls(self):
        return [json.loads(line) for line in self.trace.read_text().splitlines()] if self.trace.exists() else []

    def test_real_gcc_context_keeps_machine_and_feature_flags_without_build_outputs(self):
        compiler = shutil.which('g++', path=os.defpath)
        self.assertIsNotNone(compiler, 'The native test toolchain requires GCC')
        obj, dependency = self.root / 'must-not-create.o', self.root / 'must-not-create.d'
        entry = {**self.entry, 'arguments': [compiler, '-m32', '-std=c++14', '-msse',
                 '-fno-exceptions', '-fno-rtti', '-fPIC', '-O2', '-DTEST=1',
                 '-DFEATURE=1', '-UFEATURE', '-DFEATURE=2',
                 '-MD', '-MF', str(dependency), '-MT', str(obj), '-c', str(self.source), '-o', str(obj)]}
        entries, context = sonar.compiler_identity([entry], dict(os.environ))
        self.assertNotIn('__EXCEPTIONS', context['defines'])
        self.assertNotIn('__GXX_RTTI', context['defines'])
        for name, value in (('__SSE__', '1'), ('__PIC__', '2'), ('__OPTIMIZE__', '1'),
                            ('__SIZEOF_POINTER__', '4'), ('TEST', '1'), ('FEATURE', '2')):
            self.assertEqual(context['defines'][name], value, name)
        self.assertIn('-fno-exceptions', entries[0]['arguments'])
        self.assertFalse(obj.exists())
        self.assertFalse(dependency.exists())
        baseline = {**self.entry, 'arguments': [compiler, '-m32', '-std=c++14', '-c', str(self.source)]}
        _, defaults = sonar.compiler_identity([baseline], dict(os.environ))
        self.assertEqual(defaults['defines']['__EXCEPTIONS'], '1')

    def test_real_gcc_context_resolves_relative_flags_in_compilation_directory(self):
        compiler = shutil.which('g++', path=os.defpath)
        relative = self.root / 'relative'; relative.mkdir()
        entry = {**self.entry, 'arguments': [compiler, '-m32', '-Irelative',
                 '-DVALUE=2', '-c', 'extension/unit.cpp', '-o', 'unit.o']}
        query = sonar.compiler_query(entry)
        self.assertNotIn('extension/unit.cpp', query)
        self.assertNotIn('unit.o', query)
        entries, context = sonar.compiler_identity([entry], dict(os.environ))
        self.assertIn(str(relative), context['includes'])
        self.assertEqual(context['defines']['VALUE'], '2')
        self.assertFalse((self.root / 'unit.o').exists())

    def test_compiler_cache_keeps_distinct_working_directories(self):
        compiler = shutil.which('g++', path=os.defpath)
        entries = []
        for name in ('one', 'two'):
            folder = self.root / name; (folder / 'relative').mkdir(parents=True)
            source = folder / 'unit.cpp'; source.write_text('int value;\n')
            entries.append({'directory': str(folder), 'file': str(source),
                            'arguments': [compiler, '-m32', '-Irelative', '-c', 'unit.cpp']})
        _, context = sonar.compiler_identity(entries, dict(os.environ))
        self.assertIn(str(self.root / 'one/relative'), context['includes'])
        self.assertIn(str(self.root / 'two/relative'), context['includes'])

    def canonical(self, action="analyze", **extra):
        # Exercise the actual imported product, not its temporary CLI copy.
        env = {k: v for k, v in os.environ.items() if not k.startswith("SONAR_")}
        env.update(PATH=str(self.bin) + os.pathsep + os.defpath, TEST_TRACE=str(self.trace))
        env.update(extra)
        with patch.dict(os.environ, env, clear=True):
            sonar.run(action, str(self.db), root=self.root)

    def test_canonical_orchestrator_validates_tools_and_propagates_failures(self):
        self.canonical()
        self.assertEqual([c['tool'] for c in self.calls()], ['cppcheck', 'sonar-scanner'])
        for extra in ({'CPPCHECK_CODE':'2'}, {'BAD_XML':'1'}, {'PREPROCESSOR_ERROR':'1'},
                      {'SCANNER_CODE':'3'}, {'SCANNER_ANALYSIS_ERROR':'1'}, {'COMPILER_FAIL':'1'}, {'SONAR_TOKEN':''}):
            with self.subTest(extra=extra), self.assertRaises(sonar.SonarError):
                self.canonical(**extra)
        self.canonical(action='cppcheck')

    def test_canonical_orchestrator_imports_current_coverage_and_rejects_stale_sources(self):
        receipt, report = self.coverage_receipt()
        self.canonical(SONAR_COVERAGE_RECEIPT=str(receipt))
        self.assertIn('-Dsonar.coverageReportPaths=' + str(report), self.calls()[-1]['argv'])
        self.source.write_text('int changed;\n')
        with self.assertRaises(ValueError):
            self.canonical(SONAR_COVERAGE_RECEIPT=str(receipt))

    def test_python_and_native_reports_are_imported_together_without_aliasing(self):
        receipt, native_report = self.coverage_receipt()
        payload = json.loads(receipt.read_text())
        python_report = receipt.parent / 'python.xml'
        python_report.write_text('<?xml version="1.0"?><coverage version="1"><file path="scripts/tools/make_sonar.py"><lineToCover lineNumber="1" covered="true"/></file></coverage>')
        payload.update(kind='python', coverage_version='7.13.5', report=python_report.name,
                       report_sha256=hashlib.sha256(python_report.read_bytes()).hexdigest())
        python_receipt = receipt.parent / 'python-receipt.json'
        python_receipt.write_text(json.dumps(payload))
        self.canonical(SONAR_COVERAGE_RECEIPT=str(receipt), SONAR_PYTHON_COVERAGE_RECEIPT=str(python_receipt))
        self.assertIn('-Dsonar.coverageReportPaths=' + str(native_report) + ',' + str(python_report), self.calls()[-1]['argv'])
        with self.assertRaises(ValueError):
            self.canonical(SONAR_PYTHON_COVERAGE_RECEIPT=str(receipt))

    def coverage_receipt(self):
        spec = importlib.util.spec_from_file_location('coverage_fixture', self.root / 'tests/helpers/native_coverage.py')
        helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
        folder = self.root / 'coverage'; folder.mkdir()
        report = folder / 'coverage.xml'
        helper.write_report(report, {'extension/unit.cpp': {1: True}})
        receipt = folder / 'receipt.json'
        receipt.write_text(json.dumps({'schema': 1, 'source_state': helper.source_state(self.root),
                                      'report': report.name, 'report_sha256': helper.digest(report),
                                      'all_suites_passed': True,
                                      'test_flags': '-m32 --coverage -fprofile-abs-path'}))
        return receipt, report

    def test_valid_coverage_is_forwarded_to_scanner(self):
        receipt, report = self.coverage_receipt()
        result = self.make(SONAR_COVERAGE_RECEIPT=str(receipt))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('-Dsonar.coverageReportPaths=' + str(report), self.calls()[-1]['argv'])

    def test_stale_or_tampered_coverage_stops_before_tools(self):
        receipt, report = self.coverage_receipt()
        report.write_text('tampered')
        result = self.make(SONAR_COVERAGE_RECEIPT=str(receipt))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        self.source.write_text('int changed;\n')
        result = self.make(SONAR_COVERAGE_RECEIPT=str(receipt))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_make_scans_in_source_root_and_keeps_token_out_of_argv_and_report(self):
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stderr)
        local, remote = self.calls()
        self.assertEqual([local['tool'], remote['tool']], ['cppcheck', 'sonar-scanner'])
        self.assertIsNone(local['token'])
        self.assertEqual(remote['token'], 'test-only-token')
        self.assertEqual(remote['cwd'], str(self.root))
        self.assertNotIn('test-only-token', result.stdout + result.stderr + ' '.join(remote['argv']))
        self.assertIn('-Dsonar.projectKey=L4D2-SpeedWatch-test', remote['argv'])
        self.assertIn('-Dsonar.qualitygate.wait=true', remote['argv'])
        self.assertIn('--platform=unix32', local['argv'])
        database = Path(next(a.split('=', 1)[1] for a in local['argv'] if a.startswith('--project=')))
        self.assertIn('-DTEST=1', json.loads(database.read_text())[0]['arguments'])
        self.assertIn('-D__GNUC__=15', json.loads(database.read_text())[0]['arguments'])
        self.assertIn('-D__GNUC_MINOR__=7', json.loads(database.read_text())[0]['arguments'])
        self.assertIn('-D__linux__=1', json.loads(database.read_text())[0]['arguments'])
        self.assertIn('-D__SIZEOF_POINTER__=4', json.loads(database.read_text())[0]['arguments'])
        self.assertNotIn('test-only-token', database.read_text())
        cxx_path = Path(next(a.split('=',1)[1] for a in remote['argv'] if a.startswith('-Dsonar.cxx.jsonCompilationDatabase=')))
        cxx = json.loads(cxx_path.read_text())
        self.assertEqual(cxx[0]['file'], '__global__')
        self.assertEqual(cxx[0]['defines']['TEST'], '1')
        self.assertEqual(cxx[0]['defines']['__SIZEOF_POINTER__'], '4')
        self.assertIn(str(self.system_include), cxx[0]['includes'])
        self.assertFalse(any(e['file'] == '__global__' for e in json.loads(database.read_text())))

    def test_local_cppcheck_needs_no_server_or_token(self):
        (self.root / '.env').unlink()
        (self.root / '.env.secret').unlink()
        result = self.make('sonar-cppcheck')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c['tool'] for c in self.calls()], ['cppcheck'])

    def test_project_properties_are_supplied_from_env_without_a_properties_file(self):
        self.assertFalse((self.root/'sonar-project.properties').exists())
        result=self.make(SONAR_SOURCE_ENCODING='UTF-8',SONAR_SOURCES='extension,scripts',SONAR_EXCLUSIONS='**/__pycache__/**')
        self.assertEqual(result.returncode,0,result.stderr)
        args=self.calls()[-1]['argv']
        for option in ['-Dsonar.sourceEncoding=UTF-8','-Dsonar.sources=extension,scripts','-Dsonar.exclusions=**/__pycache__/**','-Dsonar.cxx.file.suffixes=.c,.cc,.cpp,.cxx,.h,.hh,.hpp,.hxx','-Dsonar.cxx.errorRecoveryEnabled=false']:
            self.assertIn(option,args)

    def test_parser_recovery_or_missing_project_settings_stop_before_tools(self):
        for overrides in [{'SONAR_CXX_ERROR_RECOVERY_ENABLED':'true'},{'SONAR_SOURCES':''}]:
            with self.subTest(overrides=overrides):
                result=self.make(**overrides)
                self.assertNotEqual(result.returncode,0)
                self.assertEqual(self.calls(),[])

    def test_explicit_environment_overrides_files(self):
        result = self.make(SONAR_PROJECT_KEY='override', SONAR_TOKEN='environment-token')
        self.assertEqual(result.returncode, 0, result.stderr)
        remote = self.calls()[-1]
        self.assertEqual(remote['token'], 'environment-token')
        self.assertIn('-Dsonar.projectKey=override', remote['argv'])
        self.assertNotIn('environment-token', result.stdout + result.stderr)

    def test_environment_files_are_data_not_shell(self):
        config=self.root / '.env'
        config.write_text(config.read_text().replace('SONAR_PROJECT_NAME=L4D2-SpeedWatch\n','SONAR_PROJECT_NAME="$(touch injected-marker)"\n'))
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('-Dsonar.projectName=$(touch injected-marker)', self.calls()[-1]['argv'])
        self.assertFalse((self.root / 'injected-marker').exists())

    def test_incomplete_or_unsafe_context_stops_before_tools(self):
        for override in ({'SONAR_TOKEN': ''}, {'SONAR_HOST_URL': 'https://user:secret@example.invalid'},
                         {'SONAR_HOST_URL': 'http://example.invalid'}, {'SONAR_QUALITY_GATE_TIMEOUT': '0'}):
            with self.subTest(override=override):
                result = self.make(**override)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.calls(), [])
                self.assertNotIn('test-only-token', result.stdout + result.stderr)

    def test_nonsecret_file_cannot_supply_token(self):
        with (self.root / '.env').open('a') as f:
            f.write('SONAR_TOKEN=misplaced-secret\n')
        result = self.make()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])
        self.assertNotIn('misplaced-secret', result.stdout + result.stderr)

    def test_x64_or_incomplete_database_rejected_before_tools(self):
        for entries in ([], [{**self.entry, 'arguments': ['g++', '-m64']} ]):
            self.db.write_text(json.dumps(entries))
            result = self.make()
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.calls(), [])

    def test_failed_cppcheck_or_invalid_xml_never_runs_scanner(self):
        for override in ({'CPPCHECK_CODE': '2'}, {'BAD_XML': '1'}, {'PREPROCESSOR_ERROR':'1'}):
            if self.trace.exists():
                self.trace.unlink()
            result = self.make(**override)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual([c['tool'] for c in self.calls()], ['cppcheck'])
            self.assertFalse(list((self.root / '.build/sonar').glob('*/cppcheck.xml')))

    def test_scanner_failure_propagates_without_exposing_token(self):
        result = self.make(SCANNER_CODE='7')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('test-only-token', result.stdout + result.stderr)

    def test_external_compilation_units_are_not_indexed(self):
        entries = [self.entry, {'directory': str(self.root), 'file': '/sdk/vendor.cpp', 'arguments': ['g++']}]
        self.db.write_text(json.dumps(entries))
        result = self.make()
        self.assertEqual(result.returncode, 0, result.stderr)
        local = self.calls()[0]
        path = Path(next(a.split('=', 1)[1] for a in local['argv'] if a.startswith('--project=')))
        self.assertEqual(len(json.loads(path.read_text())), 1)

    def test_compiler_query_failure_prevents_analysis(self):
        result = self.make(COMPILER_FAIL='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_tool_paths_are_resolved_from_sources_not_callers_cwd(self):
        result = self.make(SONAR_CPPCHECK='bin/cppcheck', SONAR_SCANNER='bin/sonar-scanner')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([c['tool'] for c in self.calls()], ['cppcheck','sonar-scanner'])


if __name__ == '__main__':
    unittest.main(verbosity=2)

class AnalysisGuardTests(unittest.TestCase):
    def test_configuration_rejects_public_token_and_loose_secret_permissions(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            (root/'.env').write_text('SONAR_TOKEN=must-not-load\n')
            with self.assertRaises(sonar.SonarError):sonar.configuration(root)
            (root/'.env').write_text('IGNORED=value\nSONAR_PROJECT_KEY="configured"\n')
            (root/'.env.secret').write_text('SONAR_TOKEN=fixture\n')
            (root/'.env.secret').chmod(0o644)
            if os.name!='nt':
                with self.assertRaises(sonar.SonarError):sonar.configuration(root)
            (root/'.env.secret').chmod(0o600)
            with patch.dict(os.environ,{'SONAR_PROJECT_KEY':'explicit'},clear=True):
                settings=sonar.configuration(root)
            self.assertEqual(settings['SONAR_PROJECT_KEY'],'explicit')
            self.assertEqual(settings['SONAR_TOKEN'],'fixture')
            self.assertNotIn('IGNORED',settings)

    def test_scanner_context_preserves_https_and_gate_requirements(self):
        env={'SONAR_HOST_URL':'https://example.invalid','SONAR_TOKEN':'fixture','SONAR_PROJECT_KEY':'key','SONAR_PROJECT_NAME':'name'}
        for change in ({'SONAR_HOST_URL':'https://user:password@example.invalid'},
                       {'SONAR_HOST_URL':'https://example.invalid?secret=value'},
                       {'SONAR_HOST_URL':'http://example.invalid'},
                       {'SONAR_QUALITY_GATE_WAIT':'false'},{'SONAR_QUALITY_GATE_TIMEOUT':'0'},
                       {'SONAR_PROJECT_KEY':' '},{'SONAR_PROJECT_NAME':''}):
            with self.subTest(change=change),self.assertRaises(sonar.SonarError):
                sonar.scanner_context({**env,**change})
        self.assertEqual(sonar.scanner_context({**env,'SONAR_HOST_URL':'http://localhost:9000'})[0],'http://localhost:9000')
        with self.assertRaises(sonar.SonarError):sonar.scanner_properties({})
        self.assertEqual(sonar.redact('fixture Zml4dHVyZTo=', 'fixture'),'[REDACTED] [REDACTED]')

    def test_database_rejects_incomplete_or_foreign_architecture_and_keeps_command_order(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);(root/'extension').mkdir();source=root/'extension/unit.cpp';source.touch()
            path=root/'compile.json'
            entry={'directory':str(root),'file':str(source),'command':'c++ -m32 -DFEATURE=1 -UFEATURE -DFEATURE=2 -c extension/unit.cpp'}
            path.write_text(json.dumps([entry,{'directory':str(root),'file':'sdk.cpp'}]))
            result=sonar.compilation_database(root,Path('compile.json'))
            self.assertEqual(result[0]['arguments'][2:5],['-DFEATURE=1','-UFEATURE','-DFEATURE=2'])
            for payload in ({},[],[{**entry,'directory':'.'}],[{**entry,'command':'c++ -m64 -c extension/unit.cpp'}]):
                path.write_text(json.dumps(payload))
                with self.assertRaises(sonar.SonarError):sonar.compilation_database(root,path)
            with self.assertRaises(sonar.SonarError):sonar.compilation_database(root,root/'missing.json')
            with self.assertRaises(sonar.SonarError):sonar.executable('not-a-real-tool-80',root)
            self.assertEqual(Path(sonar.executable(sys.executable,root)),Path(sys.executable).resolve())

    def test_invalid_xml_and_cli_failures_cannot_report_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for xml in ('<results/>','<unexpected><errors/></unexpected>'):
                result=subprocess.CompletedProcess([],0,stdout='',stderr=xml)
                with self.assertRaises(sonar.SonarError):sonar.validate_cppcheck(result,root,root,'')
        for failure in (None,sonar.SonarError('controlled failure'),OSError('must not appear')):
            with patch.object(sys,'argv',['sonar','cppcheck','--compile-commands','fixture.json']),patch.object(sonar,'run',side_effect=failure) as run,patch('sys.stderr',new_callable=__import__('io').StringIO) as error:
                self.assertEqual(sonar.main(),0 if failure is None else 1)
                run.assert_called_once_with('cppcheck','fixture.json')
                self.assertNotIn('must not appear',error.getvalue())
