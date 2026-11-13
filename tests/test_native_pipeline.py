"""Binary/package validation without game binaries, SDK or network access."""
import importlib.util
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from native_binary import validate_binary
spec=importlib.util.spec_from_file_location('native_package',ROOT/'scripts/package-native.py')
package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
from artifact_manifest import sourcepawn_inputs
class NativePipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        for name in ('scripts','addons','extension'):
            shutil.copytree(ROOT/name,self.root/name,ignore=shutil.ignore_patterns('__pycache__'))
        for name in ('plugin-package-map.json','dependencies.lock.json','AMBuildScript','configure.py','PackageScript','LICENSE'):
            shutil.copy2(ROOT/name,self.root/name)
        self.smx=self.root/'.build/smx';self.smx.mkdir(parents=True)
        from artifact_manifest import load_manifest,selected_files,copy_files
        copy_files(self.root,self.smx,selected_files(self.root,load_manifest(self.root)['artifact']))
        plugin=self.smx/'addons/sourcemod/plugins/l4d2_speedwatch.smx';plugin.parent.mkdir(parents=True);plugin.write_bytes(b'FFPS-fixture-not-a-real-plugin')
        shutil.copy2(self.root/'LICENSE',self.smx/'LICENSE');(self.smx/'compile.log').write_text('fixture compiler\n')
        smx_info={'inputs':sourcepawn_inputs(self.root),'binaries':{'addons/sourcemod/plugins/l4d2_speedwatch.smx':package.digest(plugin)}}
        (self.smx/'sourcepawn-build-info.json').write_text(json.dumps(smx_info))
        self.build=self.root/'.build/native';self.bin=self.build/'package'/package.binary_path('linux');self.bin.parent.mkdir(parents=True)
        # Tiny ELF fixture with SDK-required exports, no runtime or game code.
        compiler=shutil.which('cc')
        if not compiler: self.skipTest('C compiler required for ELF fixture')
        source=self.root/'fixture.c';source.write_text('void GetSMExtAPI(void) {}\nvoid CreateInterface_MMS(void) {}\n')
        subprocess.run([compiler,'-m32','-nostdlib','-shared',str(source),'-o',str(self.bin)],check=True,capture_output=True)
        info={'platform':'linux','architecture':'x86','binary_sha256':package.digest(self.bin),'dependencies':json.loads((self.root/'dependencies.lock.json').read_text()),
              'sources':package.native_source_hashes(self.root)}
        (self.build/'build-info.json').write_text(json.dumps(info));(self.build/'compile.log').write_text('ELF fixture, not SDK build\n')
        self.stage=self.root/'.build/package-exts-linux';self.out=self.root/'dist/artifact-linux'
    def stage_native(self): package.stage(self.root,self.build,self.stage,'linux')
    def release(self): package.release(self.root,self.smx,self.stage,self.out,'linux','test-linux')
    def test_package_without_sdk_and_reject_payload_leaks(self):
        self.stage_native();self.release();package.validate(self.root,self.out,'linux')
        self.assertTrue((self.root/'dist/release/test-linux.zip').is_file())
        self.assertFalse((self.root/'.deps').exists())
        rogue=self.out/'README.md';rogue.write_text('unexpected')
        with self.assertRaises(ValueError):package.validate(self.root,self.out,'linux')
    def test_wrong_architecture_and_missing_exports(self):
        validate_binary(self.bin,'linux')
        data=bytearray(self.bin.read_bytes());data[4]=2;self.bin.write_bytes(data)
        with self.assertRaises(ValueError):validate_binary(self.bin,'linux')
        with self.assertRaises(ValueError):validate_binary(self.bin,'windows')
        data[4]=1;data=data.replace(b'GetSMExtAPI',b'NotSMExtAPI');self.bin.write_bytes(data)
        with self.assertRaises(ValueError):validate_binary(self.bin,'linux')
    def test_stale_empty_and_duplicate_extension_rejected(self):
        self.bin.write_bytes(b'')
        with self.assertRaises(ValueError):self.stage_native()
        self.bin.write_bytes(b'fake')
        with self.assertRaises(ValueError):self.stage_native()
        (self.bin.parent/'l4d2_speedwatch_core.ext.dll').write_bytes(b'wrong platform')
        with self.assertRaises(ValueError):self.stage_native()
    def test_stale_sources_or_modified_smx_rejected(self):
        self.stage_native();self.release()
        (self.out/'addons/sourcemod/plugins/l4d2_speedwatch.smx').write_bytes(b'FFPS-modified')
        with self.assertRaises(ValueError):package.validate(self.root,self.out,'linux')
        (self.root/'extension/extension.cpp').write_text('// changed')
        with self.assertRaises(ValueError):self.stage_native()
    def test_platform_outputs_are_independent(self):
        other=self.root/'.build/exts-windows/sentinel';other.parent.mkdir(parents=True);other.write_text('keep')
        self.stage_native();self.release();self.assertEqual(other.read_text(),'keep')
        (self.root/'addons/sourcemod/scripting/l4d2_speedwatch.sp').write_text('// stale smx')
        with self.assertRaises(ValueError):self.release()

class PeMetadataTests(unittest.TestCase):
    def test_pe32_exports_and_wrong_architecture(self):
        data=bytearray(1024);data[:2]=b'MZ';struct.pack_into('<I',data,60,128)
        data[128:132]=b'PE\0\0';struct.pack_into('<HH',data,132,0x14c,1)
        struct.pack_into('<HH',data,148,224,0x2000);struct.pack_into('<H',data,152,0x10b)
        struct.pack_into('<II',data,248,4096,128)
        struct.pack_into('<8s6I2HI',data,376,b'.rdata\0\0',512,4096,512,512,0,0,0,0,0x40000040)
        struct.pack_into('<I',data,536,2);struct.pack_into('<I',data,544,4160)
        struct.pack_into('<II',data,576,4200,4220)
        data[616:627]=b'GetSMExtAPI';data[636:655]=b'CreateInterface_MMS'
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'fixture.dll';path.write_bytes(data);validate_binary(path,'windows')
            struct.pack_into('<H',data,132,0x8664);path.write_bytes(data)
            with self.assertRaises(ValueError):validate_binary(path,'windows')

if __name__=='__main__':unittest.main()
