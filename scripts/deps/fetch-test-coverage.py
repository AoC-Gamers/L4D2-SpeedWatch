"""Explicit isolated Python coverage dependency; never called by build/test/CI."""
from pathlib import Path
import os,subprocess,sys,venv


def main(root=Path(__file__).resolve().parents[2]):
    dest=root/'.deps/test-coverage'
    if not dest.exists():venv.EnvBuilder(with_pip=True).create(dest)
    python=dest/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(python),'-m','pip','install','coverage==7.13.5'],check=True)


if __name__ == '__main__':
    main()
