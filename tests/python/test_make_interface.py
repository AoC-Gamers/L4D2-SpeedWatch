"""Source-only checkout, alternate cwd, spaces and caller-relative test output."""
import os,shlex,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

class MakeInterfaceTests(unittest.TestCase):
    def test_build_from_other_cwd_and_source_tree_without_git(self):
        with tempfile.TemporaryDirectory(prefix='speedwatch make ') as tmp:
            caller=Path(tmp)/'caller';caller.mkdir();root=Path(tmp)/'source tree';root.mkdir()
            for name in ['addons','scripts','tests/diagnostics']:shutil.copytree(ROOT/name,root/name)
            shutil.copy2(ROOT/'Makefile',root/'Makefile')
            spy=Path(tmp)/'compiler spy';(spy.parent/'include').mkdir(exist_ok=True)
            spy.write_text('#!'+sys.executable+'\nfrom pathlib import Path\nimport sys\nnext(Path(a[2:]) for a in sys.argv if a.startswith("-o")).write_bytes(b"FFPS-spy")\n')
            spy.chmod(0o755)
            result=subprocess.run(['make','--no-print-directory','-f',str(root/'Makefile'),'build-smx','SPCOMP='+str(spy)],cwd=caller,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertTrue((root/'.build/smx/addons/sourcemod/plugins/l4d2_speedwatch.smx').is_file())
            self.assertFalse((caller/'.build').exists());self.assertFalse((root/'.git').exists())
    def test_output_is_required_and_existing_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            caller=Path(tmp);(caller/'already').mkdir()
            for value in ['', 'already']:
                result=subprocess.run(['make','--no-print-directory','-f',str(ROOT/'Makefile'),'test','TEST_OUTPUT='+value],cwd=caller,capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
    def test_sonar_and_coverage_are_not_ci_product_jobs(self):
        text=(ROOT/'.github/workflows/sourcemod-build.yml').read_text().lower()
        self.assertNotIn('sonar',text);self.assertNotIn('coverage',text)
        recipe=(ROOT/'Makefile').read_text().split('test-ci:\n',1)[1].split('\n',2)[0]
        self.assertIn('tests/python',recipe)
