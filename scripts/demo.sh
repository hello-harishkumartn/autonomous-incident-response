#!/usr/bin/env bash
# End-to-end CLI demo: set up the environment, inject an incident, run the
# agent to resolution, and print the result. No Docker, no API key, and no
# network access required — the LLM client falls back to the deterministic
# offline provider automatically.
#
# Usage:
#   scripts/demo.sh                     # bad_deployment (default: shows the approval gate)
#   scripts/demo.sh redis_failure       # any of the 10 scenario types
#   scripts/demo.sh --list              # list scenario types
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INCIDENT_TYPE="${1:-bad_deployment}"

echo "=================================================================="
echo " AIRE — Autonomous Incident Response Engineer — demo"
echo "=================================================================="

VENV_DIR="$REPO_ROOT/backend/.venv"
if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
  PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
elif [ -f "$VENV_DIR/bin/python" ]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
else
  echo "--> Setting up backend virtual environment (first run only)..."
  PY="$(command -v python3 || command -v python)"
  "$PY" -m venv "$VENV_DIR"
  if [ -f "$VENV_DIR/Scripts/python.exe" ]; then
    PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
  else
    PYTHON_BIN="$VENV_DIR/bin/python"
  fi
  "$PYTHON_BIN" -m pip install --upgrade pip -q
  "$PYTHON_BIN" -m pip install -r "$REPO_ROOT/backend/requirements.txt" -q
fi

cd "$REPO_ROOT"
echo "--> Using Python: $PYTHON_BIN"

if [ "$INCIDENT_TYPE" = "--list" ]; then
  "$PYTHON_BIN" scripts/inject_incident.py --list
  exit 0
fi

echo "--> Injecting incident: $INCIDENT_TYPE"
echo ""

set +e
"$PYTHON_BIN" scripts/inject_incident.py --type "$INCIDENT_TYPE" --seed 42 --investigate --approve-all
STATUS=$?
set -e

echo ""
echo "=================================================================="
if [ "$STATUS" -eq 0 ]; then
  echo " Demo complete: incident investigated and resolved."
else
  echo " Demo complete: incident did not resolve (see stopping reason above)."
fi
echo " Next steps:"
echo "   - Try another scenario:  scripts/demo.sh redis_failure"
echo "   - Run the benchmark:     python scripts/run_eval.py --trials 3"
echo "   - Watch it in a browser: see docs/DEMO.md"
echo "=================================================================="
exit "$STATUS"
