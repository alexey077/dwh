#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${DWH_CONTAINER:-0}" == "1" ]]; then
    exec python scripts/wait_ready.py
fi
exec docker compose run --rm -T tools scripts/wait_ready.py
