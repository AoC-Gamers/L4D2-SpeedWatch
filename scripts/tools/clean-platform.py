import shutil
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/"scripts/package"))
from artifact_contract import safe_path


def main(root=root):
    platform=sys.argv[1]
    if platform not in ('linux','windows'): raise SystemExit('Invalid platform')
    receipt=root/'.build/release-receipts'/(platform+'.json')
    safe_path(root,receipt.relative_to(root))
    receipt.unlink(missing_ok=True)
    for prefix in ('.build/exts-', '.build/package-exts-', '.build/tests-native-', 'dist/'):
        target=root/(prefix+platform)
        if prefix=='dist/': target=target/'artifact'
        safe_path(root,target.relative_to(root))
        shutil.rmtree(target,ignore_errors=True)
    # Shared SMX outputs are deliberately preserved, safe for concurrent platform work.


if __name__ == '__main__':
    main()
