"""Negative product-package controls: paths, content, cases and source provenance."""
import importlib.util,json,os,sys,tempfile,unittest
from pathlib import Path, PureWindowsPath
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/package'))
import artifact_contract as contract

class ArtifactContractTests(unittest.TestCase):
    def test_manifest_unknown_keys_and_component_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'scripts/package/package-map.json';p.parent.mkdir(parents=True)
            for build in [{'plugins':{'root':['../escape']},'extensions':{}},{'plugins':{'root':['safe']},'extensions':{},'ignored':{}}]:
                p.write_text(json.dumps({'build':build,'artifact':{},'documentation':['README.md','LICENSE','CHANGELOG.md']}))
                with self.assertRaises(ValueError):contract.load_manifest(root)
    def test_artifact_traversal_absolute_and_case_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'safe').write_text('safe')
            for name in ['../safe','/etc/passwd','C:\\secret','a\\b']:
                with self.subTest(name=name),self.assertRaises(ValueError):contract.selected_files(root,{'files':[name]})
            (root/'Safe').write_text('case')
            with self.assertRaises(ValueError):contract.selected_files(root,{'files':['safe','Safe']})
            with self.assertRaises(ValueError):contract.tree_files(root)
    def test_windows_relative_paths_and_anchored_escape_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            contract.safe_path(root,PureWindowsPath('addons/sourcemod/scripting'))
            for name in ('C:/outside','C:outside','/outside','//server/share/file','addons/../outside'):
                with self.subTest(name=name),self.assertRaises(ValueError):
                    contract.safe_path(root,PureWindowsPath(name))
    @unittest.skipIf(os.name=='nt','POSIX link and special-file fixture')
    def test_links_and_special_files_are_not_silently_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'file').write_text('safe');(root/'link').symlink_to(root/'file')
            with self.assertRaises(ValueError):contract.tree_files(root)
            with self.assertRaises(ValueError):contract.selected_files(root,{'files':['link']})
            (root/'link').unlink();os.mkfifo(root/'pipe')
            with self.assertRaises(ValueError):contract.tree_files(root)
    def test_clean_and_basename_reject_shared_roots_and_shell_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.build').mkdir()
            with self.assertRaises(ValueError):contract.clean_output(root,root/'.build')
            for name in ['../archive','a/b','a\\b','archive;echo-bad','$(id)','', '.']:
                with self.assertRaises(ValueError):contract.validate_basename(name)
