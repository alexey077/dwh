#!/usr/bin/env python3
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from psycopg2.extensions import make_dsn, parse_dsn
import yaml


ROOT = Path(__file__).resolve().parents[1]


def container_submission(source):
    for role, connections in source["connections"].items():
        host = "pgbouncer" if role in ("master", "writer") else "haproxy"
        port = 6432 if host == "pgbouncer" else 5001 if role == "replica" else 5000
        for service, dsn in connections.items():
            connections[service] = make_dsn(
                **(parse_dsn(dsn) | {"host": host, "port": str(port)})
            )
    for key, host, port in [
        ("pooler_dsn", "pgbouncer", 6432),
        ("haproxy_rw_dsn", "haproxy", 5000),
        ("haproxy_ro_dsn", "haproxy", 5001),
    ]:
        source["ha"][key] = make_dsn(
            **(parse_dsn(source["ha"][key]) | {"host": host, "port": str(port)})
        )
    source["ha"]["patroni_api"] = os.environ.get(
        "CLUSTER_STATUS_API", "http://cluster-status:8011"
    )
    return source


def main():
    source = yaml.safe_load((ROOT / "hw01_submission.yaml").read_text())
    if os.environ.get("DWH_CONTAINER") == "1":
        source = container_submission(source)
    (ROOT / "reports").mkdir(exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        prefix=".container-submission-",
        dir=ROOT,
        delete=False,
    ) as handle:
        yaml.safe_dump(source, handle, allow_unicode=True, sort_keys=False)
        path = Path(handle.name)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "hw01/hw01_check.py"),
                "--submission",
                str(path),
                "--json",
                str(ROOT / "reports/check_report.json"),
                *sys.argv[1:],
            ],
            cwd=ROOT,
        )
        return result.returncode
    finally:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.exit(main())
