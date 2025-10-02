#!/usr/bin/env bash
# Run list_admin_users.py with a sanitized environment so backend settings load cleanly.
# This avoids frontend REACT_APP_* vars being picked up by pydantic.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"
# Use backend virtualenv Python if available
PYBIN="$REPO_ROOT/backend/venv/bin/python"
if [ -x "$PYBIN" ]; then
  "$PYBIN" backend/scripts/list_admin_users.py
else
  python3 backend/scripts/list_admin_users.py
fi

