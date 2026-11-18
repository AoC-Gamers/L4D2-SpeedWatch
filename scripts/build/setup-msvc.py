#!/usr/bin/env python3
"""Export the installed MSVC x86 environment to subsequent GitHub Actions steps."""
import os
from pathlib import Path
import subprocess


def main():
    if os.name != "nt":
        raise SystemExit("MSVC setup requires a Windows runner")
    github_env = Path(os.environ["GITHUB_ENV"])
    vswhere = Path(os.environ["ProgramFiles(x86)"]) / "Microsoft Visual Studio/Installer/vswhere.exe"
    installation = subprocess.check_output([
        str(vswhere), "-latest", "-products", "*", "-requires",
        "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath",
    ], text=True).strip()
    if not installation:
        raise SystemExit("No Visual Studio installation with x86 C++ tools found")
    vcvars = Path(installation) / "VC/Auxiliary/Build/vcvarsall.bat"
    if not vcvars.is_file():
        raise SystemExit(f"Missing MSVC initialization script: {vcvars}")
    # cmd.exe /s /c needs an outer quote pair around a quoted executable path.
    command = f'"{os.environ["COMSPEC"]}" /d /s /c ""{vcvars}" x86 >nul && set"'
    environment = subprocess.check_output(command, text=True)
    updates = []
    for line in environment.splitlines():
        name, separator, value = line.partition("=")
        if not separator or not name or name.upper().startswith(("GITHUB_", "RUNNER_")):
            continue
        if name.upper() == "NODE_OPTIONS" or os.environ.get(name) == value:
            continue
        updates.append(f"{name}={value}\n")
    with github_env.open("a", encoding="utf-8", newline="\n") as output:
        output.writelines(updates)
    print("MSVC x86 environment initialized for subsequent steps")


if __name__ == "__main__":
    main()
