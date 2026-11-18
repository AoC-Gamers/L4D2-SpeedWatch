"""Exercise channel orchestration with gh/Git doubles; never contact GitHub."""
import hashlib,importlib.util,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/ci'))
from release_identity import resolve
spec=importlib.util.spec_from_file_location('publisher',ROOT/'scripts/ci/publish-channel.py');publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
SHA='a'*40;RUN='https://github.com/example/product/actions/runs/123'

class ReleasePublicationTests(unittest.TestCase):
    def pair(self,root,ref='develop',sha=SHA):
        info=resolve(ref,SHA)
        for platform in ['linux','windows']:
            with zipfile.ZipFile(root/(info[platform+'_basename']+'.zip'),'w') as z:
                z.writestr('payload','valid')
                z.writestr('build-info.json',json.dumps({'platform':platform,'architecture':'x86','project_sha':sha,'runtime_files':{'payload':hashlib.sha256(b'valid').hexdigest()}}))
    def test_names_channels_versions_and_unpublishable_pr(self):
        self.assertEqual(resolve('main')['linux_basename'],'l4d2-speedwatch-latest-linux')
        self.assertEqual(resolve('develop')['windows_basename'],'l4d2-speedwatch-develop-windows')
        self.assertEqual(resolve('v1.2.3')['linux_basename'],'l4d2-speedwatch-1.2.3-linux')
        self.assertEqual(resolve('feature',SHA)['release_tag'],'')
        with self.assertRaises(ValueError):resolve('feature','1234567bad')
    def test_pair_validation_precedes_any_network_or_tag_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            calls=[]
            with self.assertRaises(ValueError):publisher.publish('develop',SHA,RUN,'1',Path(tmp),runner=lambda *a,**k:calls.append(a))
            self.pair(Path(tmp),sha='b'*40)
            with self.assertRaises(ValueError):publisher.publish('develop',SHA,RUN,'1',Path(tmp),runner=lambda *a,**k:calls.append(a))
            self.assertEqual(calls,[])
    def test_draft_upload_then_publish_and_failed_upload_stays_draft(self):
        for fail in [False,True]:
            with self.subTest(fail=fail),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);self.pair(root);calls=[]
                def run(args,**kwargs):
                    calls.append(args)
                    if fail and args[:3]==['gh','release','upload']:raise subprocess.CalledProcessError(1,args)
                    return subprocess.CompletedProcess(args,0,stdout='channel/develop\n',stderr='')
                if fail:
                    with self.assertRaises(subprocess.CalledProcessError):publisher.publish('develop',SHA,RUN,'1',root,run)
                    self.assertFalse(any(args[:3]==['gh','release','edit'] for args in calls))
                else:
                    publisher.publish('develop',SHA,RUN,'1',root,run)
                    kinds=[args[2] for args in calls if args[:2]==['gh','release']]
                    self.assertEqual(kinds,['delete','create','upload','edit'])
                    self.assertIn('--draft',next(a for a in calls if a[:3]==['gh','release','create']))
                    self.assertIn('--latest=false',calls[-1]);self.assertIn('--prerelease=true',calls[-1])
                    self.assertNotIn('--cleanup-tag',sum(calls,[]))
    def test_release_list_failure_aborts_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.pair(root);calls=[]
            def fail(args,**kwargs):calls.append(args);raise subprocess.CalledProcessError(1,args)
            with self.assertRaises(subprocess.CalledProcessError):publisher.publish('develop',SHA,RUN,'1',root,fail)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0][1],'api')
