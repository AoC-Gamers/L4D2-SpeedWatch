# Adapted from AoC-Gamers/SteamWorks (GPL-3.0-or-later); see docs/build/sonar.md.
"""GCC line counters and source-bound Sonar generic coverage. No estimates."""
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

# Only successful, unmodified executables contribute counters. Negative-control
# binaries remain mandatory tests, but are never inputs to the coverage report.


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_state(root):
    paths = []
    for area in ("extension", "scripts", "tests", "addons"):
        paths += [p for p in (root / area).rglob("*") if p.is_file()
                  and "__pycache__" not in p.parts and p.suffix != ".pyc"]
    paths += [root / p for p in ("Makefile", "configure.py", "AMBuildScript", "PackageScript", "scripts/deps/dependencies.lock.json", "scripts/deps/sourcepawn-package.lock.json", ".env.example", ".env.secret.example")
              if (root / p).is_file()]
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(paths)}



def read_gcov(counter, cwd, gcov="gcov"):
    p = subprocess.run([gcov, "--json-format", "--stdout", str(counter)], cwd=cwd,
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


def merge_lines(root, payload, merged, baseline=False):
    for file in payload["files"]:
        path = (Path(payload["current_working_directory"]) / file["file"]).resolve()
        if not path.is_relative_to(root / "extension"):
            continue
        length = len(path.read_text().splitlines())
        rows = merged.setdefault(path.relative_to(root).as_posix(), {})
        for row in file["lines"]:
            number, count = row["line_number"], row["count"]
            if type(number) is not int or not 1 <= number <= length or type(count) is not int or count < 0:
                raise ValueError("Invalid compiler coverage row")
            if baseline and count:
                raise ValueError("Unexecuted product object unexpectedly has hits")
            # Across multiple tested configurations a line is covered if at
            # least one successful production-code execution reaches it.
            rows[number] = rows.get(number, False) or count > 0


def write_report(path, lines):
    if not lines or not any(any(rows.values()) for rows in lines.values()):
        raise ValueError("No executed production lines in coverage")
    report = ET.Element("coverage", version="1")
    for name, rows in sorted(lines.items()):
        file = ET.SubElement(report, "file", path=name)
        for number, hit in sorted(rows.items()):
            ET.SubElement(file, "lineToCover", lineNumber=str(number), covered=str(hit).lower())
    ET.indent(report)
    ET.ElementTree(report).write(path, encoding="utf-8", xml_declaration=True)


def validate_receipt(root, receipt_path, kind="native"):
    receipt_path = Path(receipt_path)
    if not receipt_path.is_absolute():
        receipt_path = root / receipt_path
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema") != 1 or receipt.get("source_state") != source_state(root):
        raise ValueError("Coverage source state is stale or incomplete")
    report = (receipt_path.parent / receipt["report"]).resolve()
    if report.parent != receipt_path.parent.resolve() or digest(report) != receipt["report_sha256"]:
        raise ValueError("Coverage report changed")
    if receipt.get("kind", "native") != kind or not receipt.get("all_suites_passed"):
        raise ValueError("Coverage tests failed or report kind does not match")
    if kind == "native" and receipt.get("test_flags") != "-m32 --coverage -fprofile-abs-path":
        raise ValueError("Coverage tests were not x86 instrumented")
    if kind == "python" and receipt.get("coverage_version") != "7.13.5":
        raise ValueError("Unsupported Python coverage producer")
    area = root / ("scripts" if kind == "python" else "extension")
    try:
        xml = ET.parse(report).getroot()
    except ET.ParseError as error:
        raise ValueError("Invalid coverage XML") from error
    seen = set()
    if xml.tag != "coverage" or xml.get("version") != "1":
        raise ValueError("Invalid coverage XML")
    for file in xml:
        name = file.get("path", "")
        p = (root / name).resolve()
        if file.tag != "file" or name in seen or not p.is_relative_to(area):
            raise ValueError("Coverage includes duplicate or non-product files")
        seen.add(name)
        count = len(p.read_text().splitlines())
        numbers = set()
        for row in file:
            n = int(row.get("lineNumber", "0"))
            if row.tag != "lineToCover" or not 1 <= n <= count or n in numbers or row.get("covered") not in {"true", "false"}:
                raise ValueError("Invalid coverage line")
            numbers.add(n)
    if not seen:
        raise ValueError("Empty coverage report")
    return report
