"""Exercise the real Makefile dependency order with instrumented staging commands."""
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = '''
from pathlib import Path
import os
import sys
import time

script, *args = sys.argv[1:]
if script == "scripts/stage-artifact.py":
    stage = "smx"
elif script == "scripts/package-native.py" and args[0] == "stage":
    stage = "native"
elif script == "scripts/package-native.py" and args[0] == "release":
    Path("release.started").touch()
    missing = [name for name in ("smx.ready", "native.ready") if not Path(name).exists()]
    if missing:
        raise SystemExit("Release started before staging finished: " + str(missing))
    Path("release.done").touch()
    raise SystemExit(0)
else:
    raise SystemExit("Unexpected build/download command: " + script)
if os.environ.get("SPEEDWATCH_FAIL_STAGE") == stage:
    raise SystemExit(17)
time.sleep(0.2)
Path(stage + ".ready").touch()
'''


@unittest.skipUnless(shutil.which("make"), "GNU Make required for dependency-order tests")
class MakeReleaseTests(unittest.TestCase):
    def run_release(self, jobs, failure=None):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        shutil.copy2(ROOT / "Makefile", root / "Makefile")
        driver = root / "driver.py"
        driver.write_text(DRIVER)
        environment = os.environ.copy()
        environment.pop("SPEEDWATCH_FAIL_STAGE", None)
        environment.pop("MAKEFLAGS", None)
        environment.pop("MFLAGS", None)
        if failure:
            environment["SPEEDWATCH_FAIL_STAGE"] = failure
        result = subprocess.run([
            "make", f"-j{jobs}", "release",
            f"PYTHON={shlex.quote(sys.executable)} {shlex.quote(str(driver))}",
        ], cwd=root, env=environment, text=True, capture_output=True, timeout=15)
        return root, result

    def test_release_waits_for_both_packages_in_serial_and_parallel(self):
        for jobs in (1, 3):
            with self.subTest(jobs=jobs):
                root, result = self.run_release(jobs)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue((root / "release.done").is_file())

    def test_failed_package_prevents_release(self):
        for failure in ("smx", "native"):
            with self.subTest(failure=failure):
                root, result = self.run_release(3, failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((root / "release.started").exists())


if __name__ == "__main__":
    unittest.main()
