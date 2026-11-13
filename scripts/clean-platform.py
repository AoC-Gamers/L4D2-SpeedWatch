import shutil
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
platform=sys.argv[1]
if platform not in ('linux','windows'): raise SystemExit('Invalid platform')
for prefix in ('.build/exts-', '.build/package-exts-', '.build/tests-native-', 'dist/artifact-'):
    shutil.rmtree(root/(prefix+platform),ignore_errors=True)
# Shared SMX outputs are deliberately preserved, safe for concurrent platform work.
