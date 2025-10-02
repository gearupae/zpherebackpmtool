#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   API_BASE_URL=https://api.example.com \
#   ADMIN_TOKEN=$YOUR_ADMIN_BEARER_TOKEN \
#   ./sync_all_tenants.sh

if [[ -z "${API_BASE_URL:-}" ]]; then
  echo "Error: API_BASE_URL env var is required" >&2
  exit 1
fi
if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "Error: ADMIN_TOKEN env var is required" >&2
  exit 1
fi

URL="$API_BASE_URL/admin/tenants/migrations/sync-all"
echo "Syncing tenant schemas via: $URL"

HTTP_CODE=$(curl -sS -o /tmp/sync_all_resp.json -w "%{http_code}" \
  -X POST "$URL" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json")

if [[ "$HTTP_CODE" != "200" ]]; then
  echo "Sync-all request failed with HTTP $HTTP_CODE" >&2
  echo "Response:"
  cat /tmp/sync_all_resp.json
  exit 1
fi

echo "Sync-all completed successfully. Response:"
cat /tmp/sync_all_resp.json

