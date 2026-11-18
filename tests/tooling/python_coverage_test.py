"""Offline enumeration regression; fixture counters are not product coverage."""
import importlib.util,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('python_coverage',ROOT/'tests/helpers/python_coverage.py');producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)

class PythonCoverageTests(unittest.TestCase):
    def test_scripts_without_init_are_retained_as_uncovered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'scripts/build').mkdir(parents=True)
            (root/'scripts/build/unexecuted.py').write_text('first=1\nsecond=2\n')
            (root/'scripts/used.py').write_text('used=1\n')
            (root/'tests').mkdir();(root/'tests/test_fixture.py').write_text('ignored=1\n')
            calls=[]
            class Measurement:
                def analysis2(self,path):
                    calls.append(path)
                    if path.endswith('unexecuted.py'):return path,[1,2],[],[1,2],'1-2'
                    return path,[1],[],[],''
            result=producer.collect(root,Measurement())['files']
            self.assertEqual(set(result),{'scripts/used.py','scripts/build/unexecuted.py'})
            self.assertEqual(result['scripts/build/unexecuted.py']['executed_lines'],[])
            self.assertEqual(result['scripts/build/unexecuted.py']['missing_lines'],[1,2])
            self.assertEqual(len(calls),2)


class CoverageDependencyTests(unittest.TestCase):
    def test_coverage_dependency_is_pinned_and_reuses_venv(self):
        spec = importlib.util.spec_from_file_location('coverage_dependency',ROOT/'scripts/deps/fetch-test-coverage.py')
        module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        temporary = tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        dest = root/'.deps/test-coverage'
        with patch.object(module.venv, 'EnvBuilder') as builder, patch.object(module.subprocess, 'run') as run:
            module.main(root)
            builder.return_value.create.assert_called_once_with(dest)
            self.assertIn('coverage==7.13.5', run.call_args.args[0])
            self.assertTrue(run.call_args.kwargs['check'])
            dest.mkdir(parents=True)
            builder.reset_mock()
            module.main(root)
            builder.assert_not_called()
