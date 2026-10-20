#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p reports

if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--full" ) ]]; then
    printf 'Usage: ./scripts/verify.sh [--full]\n' >&2
    exit 2
fi

docker compose up -d --build
docker compose run --rm -T tools scripts/migrate.py
./scripts/wait_ready.sh
./scripts/seed.sh --seed 42
./scripts/check.sh --verbose
docker compose run --rm -T tools tests/assert_runtime_report.py reports/check_report.json

if [[ $# -eq 1 ]]; then
    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python tests/check_cluster_status.py --probe-failure
    .venv/bin/python scripts/experiments.py
    ./scripts/check.sh --verbose --json reports/check_after_failures.json
    docker compose run --rm -T tools tests/assert_runtime_report.py reports/check_after_failures.json
fi
