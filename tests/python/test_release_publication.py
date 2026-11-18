"""Exercise channel orchestration with gh/Git doubles; never contact GitHub."""
import hashlib,importlib.util,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'scripts/ci'))
from release_identity import resolve
spec=importlib.util.spec_from_file_location('publisher',ROOT/'scripts/ci/publish-channel.py');publisher=importlib.util.module_from_spec(spec);spec.loader.exec_module(publisher)
from installer_docs import documentation_paths
from release_receipt import sourcepawn_payload
SHA='a'*40;RUN='https://github.com/example/product/actions/runs/123'

class ReleasePublicationTests(unittest.TestCase):
    def pair(self,root,ref='develop',sha=SHA):
        info=resolve(ref,SHA)
        for platform in ['linux','windows']:
            with zipfile.ZipFile(root/(info[platform+'_basename']+'.zip'),'w') as z:
                z.writestr('payload','valid')
                required = {name.as_posix() for name in documentation_paths(ROOT)} | sourcepawn_payload(ROOT)
                payloads = {name: b'text' for name in required}
                payloads['LICENSE'] = (ROOT / 'LICENSE').read_bytes()
                for name, content in payloads.items():
                    z.writestr(name, content)
            archive=root/(info[platform+'_basename']+'.zip')
            receipts=root/'receipts';receipts.mkdir(exist_ok=True)
            receipt={'schema':1,'platform':platform,'architecture':'x86','project_sha':sha,'archive_name':archive.name,
                     'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                     'runtime_files':{'payload':hashlib.sha256(b'valid').hexdigest(),
                                      **{name:hashlib.sha256(content).hexdigest() for name, content in payloads.items()}}}
            (receipts/(platform+'.json')).write_text(json.dumps(receipt))
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
                    upload=next(a for a in calls if a[:3]==['gh','release','upload'])
                    self.assertEqual(len([a for a in upload if a.endswith('.zip')]),2)
                    self.assertFalse(any(a.endswith('.json') for a in upload))
    def test_release_list_failure_aborts_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.pair(root);calls=[]
            def fail(args,**kwargs):calls.append(args);raise subprocess.CalledProcessError(1,args)
            with self.assertRaises(subprocess.CalledProcessError):publisher.publish('develop',SHA,RUN,'1',root,fail)
            self.assertEqual(len(calls),1);self.assertEqual(calls[0][1],'api')

    def test_missing_receipt_and_modified_zip_abort_before_network(self):
        for mode in ('missing-receipt','modified-zip','wrong-platform'):
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);self.pair(root);calls=[]
                receipt_path=root/'receipts/linux.json'
                if mode=='missing-receipt':receipt_path.unlink()
                elif mode=='modified-zip':
                    archive=root/(resolve('develop')['linux_basename']+'.zip')
                    archive.write_bytes(archive.read_bytes()+b'changed')
                else:
                    receipt=json.loads(receipt_path.read_text());receipt['platform']='windows';receipt_path.write_text(json.dumps(receipt))
                with self.assertRaises((ValueError,FileNotFoundError)):
                    publisher.publish('develop',SHA,RUN,'1',root,runner=lambda *a,**k:calls.append(a))
                self.assertEqual(calls,[])

    def test_metadata_or_unsafe_members_rejected_even_with_updated_receipt_hashes(self):
        for name in ('build-info.json','sourcepawn-build-info.json','package-map.json','source.sp','../escape','C:/escape','nested\\escape'):
            with self.subTest(name=name),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);self.pair(root);calls=[]
                archive=root/(resolve('develop')['linux_basename']+'.zip')
                with zipfile.ZipFile(archive,'a') as packaged:packaged.writestr(name,'invalid')
                path=root/'receipts/linux.json';receipt=json.loads(path.read_text())
                receipt['archive_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
                receipt['runtime_files'][name]=hashlib.sha256(b'invalid').hexdigest();path.write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):publisher.publish('develop',SHA,RUN,'1',root,runner=lambda *a,**k:calls.append(a))
                self.assertEqual(calls,[])
