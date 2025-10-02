#!/usr/bin/env bash
set -euo pipefail

# Create the tenant database for an existing Organization ID.
# Usage:
#   ./create_tenant_db.sh <ORGANIZATION_ID>
#
# The backend must have access to the master DB as configured in backend/.env

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <ORGANIZATION_ID>" >&2
  exit 1
fi
ORG_ID="$1"

# Prefer a venv if present
if [[ -f "$BACKEND_DIR/venv/bin/activate" ]]; then
  source "$BACKEND_DIR/venv/bin/activate"
fi

python3 "$BACKEND_DIR/create_tenant_db.py" "$ORG_ID"
