#!/usr/bin/env python3
import json
import os
import time
from urllib.request import urlopen

import psycopg2
from psycopg2.extensions import make_dsn, parse_dsn
from wait_ready import query


def wait_for_replay(timeout=120):
    api = os.environ.get("PATRONI_API", "http://pg1:8008")
    dsn = os.environ.get(
        "ADMIN_DSN", "postgresql://postgres:postgres@haproxy:5000/postgres"
    )
    target = query(dsn, "SELECT pg_current_wal_lsn()::text")[0][0]
    settings = parse_dsn(dsn)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(api + "/cluster", timeout=3) as response:
                members = json.load(response).get("members", [])
            replicas = [m for m in members if m.get("role") != "leader"]
            caught = 0
            for member in replicas:
                replica_dsn = make_dsn(
                    **(
                        settings
                        | {
                            "host": member["host"],
                            "port": str(member.get("port", 5432)),
                            "dbname": "postgres",
                        }
                    )
                )
                result = query(
                    replica_dsn,
                    "SELECT pg_is_in_recovery() AND pg_last_wal_replay_lsn() >= %s::pg_lsn",
                    (target,),
                )
                caught += result[0][0] is True
            if len(replicas) == 2 and caught == 2:
                print(f"Both replicas replayed WAL through {target}", flush=True)
                return
        except (OSError, ValueError, KeyError, psycopg2.Error) as error:
            print(f"Waiting for WAL replay: {str(error).splitlines()[0]}", flush=True)
        time.sleep(1)
    raise TimeoutError(f"Replicas did not replay WAL through {target}")


if __name__ == "__main__":
    wait_for_replay()
