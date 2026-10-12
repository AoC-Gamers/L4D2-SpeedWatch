#!/usr/bin/env bash
set -euo pipefail

TASK_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACT_DIR="${SOURCEMOD_ARTIFACT_DIR:-$TASK_ROOT/dist/sourcemod/artifact}"
"${PYTHON:-python3}" "$TASK_ROOT/scripts/validate-artifact.py" --root "$TASK_ROOT" --artifact "$ARTIFACT_DIR"
