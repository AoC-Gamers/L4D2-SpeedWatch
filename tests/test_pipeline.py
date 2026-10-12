"""Exercise production selection and release rejection without a game server."""
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ProductionPipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name in ("addons", "docs"):
            shutil.copytree(ROOT / name, self.root / name)
        for name in ("README.md", "LICENSE", "plugin-package-map.json"):
            shutil.copy2(ROOT / name, self.root / name)
        # A compiler spy fails if the relocated diagnostic entrypoint is selected.
        (self.root / "addons/sourcemod/scripting/l4d2_speedwatch_test.sp").write_text("invalid test source\n")
        self.compiler = self.root / "deps/sdk/spcomp64"
        (self.compiler.parent / "include").mkdir(parents=True)
        self.compiler.write_text(f"#!{sys.executable}\n" + '''import sys
from pathlib import Path
source = Path(sys.argv[1])
with (Path(__file__).parent / 'invocations.txt').open('a') as log:
    log.write(source.name + '\\n')
if source.name != 'l4d2_speedwatch.sp' or '-E' not in sys.argv:
    raise SystemExit(7)
output = next(Path(arg[2:]) for arg in sys.argv if arg.startswith('-o'))
output.write_bytes(b'compiler-spy-production-output')
print('compiler spy completed')
''')
        self.compiler.chmod(0o755)

    def tool(self, script, *args, success=True):
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / script), *map(str, args)],
                                cwd=self.root, capture_output=True, text=True, check=False)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def build(self):
        return self.tool("build-local.py", "--root", self.root, "--spcomp", self.compiler)

    def stage(self, success=True):
        return self.tool("stage-artifact.py", self.root, self.root / ".build/smx",
                         self.root / "deps/build-smx-compile.log", success=success)

    def test_build_selects_only_production_and_removes_stale_test_binary(self):
        stale = self.root / ".build/smx/addons/sourcemod/plugins/l4d2_speedwatch_test.smx"
        stale.parent.mkdir(parents=True)
        stale.write_bytes(b"stale-test")
        self.build()
        self.assertEqual((self.compiler.parent / "invocations.txt").read_text(), "l4d2_speedwatch.sp\n")
        self.assertEqual([p.name for p in (self.root / ".build/smx").rglob("*.smx")], ["l4d2_speedwatch.smx"])
        self.assertFalse((self.root / ".build/smx/addons/sourcemod/scripting/l4d2_speedwatch_test.sp").exists())

    def test_release_has_only_production_binary_and_required_payload(self):
        self.build()
        self.stage()
        self.tool("package-release.py", "--root", self.root, "--basename", "test-release")
        with zipfile.ZipFile(self.root / "dist/release/test-release.zip") as archive:
            files = archive.namelist()
            self.assertIsNone(archive.testzip())
            self.assertEqual([p for p in files if p.endswith(".smx")],
                             ["addons/sourcemod/plugins/l4d2_speedwatch.smx"])
            for name in ("README.md", "LICENSE", "compile.log", "docs/index.md",
                         "addons/sourcemod/scripting/include/l4d2_speedwatch.inc",
                         "addons/sourcemod/translations/l4d2_speedwatch.phrases.txt"):
                self.assertIn(name, files)
            self.assertFalse(any("speedwatch_test" in p for p in files))

    def test_staging_and_release_reject_unexpected_test_binary(self):
        self.build()
        rogue = self.root / ".build/smx/addons/sourcemod/plugins/l4d2_speedwatch_test.smx"
        rogue.write_bytes(b"unexpected-test")
        self.assertIn("Unexpected artifact files", self.stage(success=False).stderr)
        rogue.unlink()
        self.stage()
        rogue = self.root / "dist/sourcemod/artifact/addons/sourcemod/plugins/l4d2_speedwatch_test.smx"
        rogue.write_bytes(b"unexpected-test")
        self.tool("package-release.py", "--root", self.root, "--basename", "bad-release", success=False)
        self.assertFalse((self.root / "dist/release/bad-release.zip").exists())

    def test_compile_failure_stops_pipeline_and_preserves_diagnostics(self):
        self.compiler.write_text(f"#!{sys.executable}\nprint('compiler failed deliberately')\nraise SystemExit(2)\n")
        self.tool("build-local.py", "--root", self.root, "--spcomp", self.compiler, success=False)
        self.assertIn("compiler failed deliberately", (self.root / "deps/build-smx-compile.log").read_text())
        self.stage(success=False)


if __name__ == "__main__":
    unittest.main()
