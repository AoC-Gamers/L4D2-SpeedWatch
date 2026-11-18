"""Offline coverage contract tests; fixture hits are never product measurements."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('coverage_contract',ROOT/'tests/helpers/native_coverage.py');coverage=importlib.util.module_from_spec(spec);spec.loader.exec_module(coverage)

class CoverageContractTests(unittest.TestCase):
    def fixture(self,root):
        (root/'extension').mkdir();(root/'extension/unit.cpp').write_text('int value;\nint other;\n')
        report=root/'coverage.xml';coverage.write_report(report,{'extension/unit.cpp':{1:True,2:False}})
        receipt={'schema':1,'kind':'native','source_state':coverage.source_state(root),'report':report.name,'report_sha256':coverage.digest(report),'all_suites_passed':True,'test_flags':'-m32 --coverage -fprofile-abs-path'}
        path=root/'receipt.json';path.write_text(json.dumps(receipt));return path,report,receipt
    def test_current_report_and_stale_source_or_altered_xml(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path,report,data=self.fixture(root)
            self.assertEqual(coverage.validate_receipt(root,path),report)
            report.write_text(report.read_text()+' ')
            with self.assertRaises(ValueError):coverage.validate_receipt(root,path)
            path,report,data=self.fixture_again(root)
            (root/'extension/unit.cpp').write_text('changed\n')
            with self.assertRaises(ValueError):coverage.validate_receipt(root,path)
    def fixture_again(self,root):
        (root/'extension').rename(root/'prior');result=self.fixture(root);return result
    def test_non_product_duplicate_or_invalid_rows_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);path,report,data=self.fixture(root)
            for xml in ['<coverage version="1"><file path="../escape.cpp"/></coverage>', '<coverage version="1"><file path="extension/unit.cpp"><lineToCover lineNumber="0" covered="true"/></file></coverage>', '<coverage version="1"><file path="extension/unit.cpp"/><file path="extension/unit.cpp"/></coverage>']:
                report.write_text(xml);data['report_sha256']=coverage.digest(report);path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):coverage.validate_receipt(root,path)
    def test_merge_keeps_zero_hit_lines_and_rejects_fabricated_baseline_hits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);merged={}
            payload={'current_working_directory':str(root),'files':[{'file':'extension/unit.cpp','lines':[{'line_number':1,'count':0},{'line_number':2,'count':0}]}]}
            coverage.merge_lines(root,payload,merged,baseline=True)
            self.assertEqual(merged,{'extension/unit.cpp':{1:False,2:False}})
            payload['files'][0]['lines'][0]['count']=1
            with self.assertRaises(ValueError):coverage.merge_lines(root,payload,merged,baseline=True)
