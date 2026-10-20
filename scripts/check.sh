#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports
if [[ "${DWH_CONTAINER:-0}" == "1" ]]; then
    exec python scripts/check.py "$@"
fi
exec docker compose run --rm -T tools scripts/check.py "$@"
