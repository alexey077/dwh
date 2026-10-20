#!/usr/bin/env python3
import json
import os
from pathlib import Path
import time
from urllib.request import urlopen

import psycopg2
import yaml

ROOT = Path(__file__).resolve().parents[1]


def query(dsn, statement, params=None):
    connection = psycopg2.connect(dsn, connect_timeout=3)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall()
    finally:
        connection.close()


def wait_ready(timeout=300):
    api = os.environ.get("PATRONI_API", "http://pg1:8008")
    contract = yaml.safe_load((ROOT / "hw01/hw01_contract.yaml").read_text())
    deadline = time.monotonic() + timeout
    last = ""
    while time.monotonic() < deadline:
        try:
            with urlopen(api + "/cluster", timeout=3) as response:
                cluster = json.load(response)
            members = cluster.get("members", [])
            if (
                len(members) != 3
                or sum(m.get("role") == "leader" for m in members) != 1
            ):
                raise RuntimeError("Patroni has not formed a three-node cluster")
            if any(m.get("state") not in ("running", "streaming") for m in members):
                raise RuntimeError("Some PostgreSQL nodes are not ready")
            for service, spec in contract["services"].items():
                database = f"{service}_service_db"
                for host, port, recovery in [
                    ("pgbouncer", 6432, False),
                    ("haproxy", 5001, True),
                ]:
                    dsn = f"postgresql://checker:checker@{host}:{port}/{database}"
                    if query(dsn, "SELECT pg_is_in_recovery()")[0][0] != recovery:
                        raise RuntimeError(f"Wrong route: {host}:{port}")
                    views = query(
                        dsn,
                        "SELECT table_name FROM information_schema.views WHERE table_schema='contract'",
                    )
                    if not set(spec["views"]).issubset({v[0] for v in views}):
                        raise RuntimeError(
                            f"Contract of {service} is not available on {host}"
                        )
            print(
                "Ready: 3 PostgreSQL nodes, 4 databases, contract, pool and replica route",
                flush=True,
            )
            return
        except (OSError, ValueError, psycopg2.Error, RuntimeError) as error:
            last = str(error).splitlines()[0]
            time.sleep(1)
    raise TimeoutError(f"Stand did not become ready: {last}")


if __name__ == "__main__":
    wait_ready()
