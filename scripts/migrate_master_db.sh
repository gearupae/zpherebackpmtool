#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ALEMBIC_DB_URL=postgresql+psycopg2://user:pass@host:5432/db \
#   ./migrate_master_db.sh

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
BACKEND_DIR=$(cd "$SCRIPT_DIR/.." && pwd)

if [[ -z "${ALEMBIC_DB_URL:-}" ]]; then
  echo "Error: ALEMBIC_DB_URL env var is required" >&2
  exit 1
fi

cd "$BACKEND_DIR"
# Alembic will pick up ALEMBIC_DB_URL via env.py override
alembic -c alembic.ini upgrade head

echo "Master DB migration complete."

