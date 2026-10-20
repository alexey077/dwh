#!/usr/bin/env python3
"""Read-only cluster status using the process state reported by each Patroni node."""

from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from urllib.parse import urlsplit
from urllib.request import urlopen


NODES = {name: f"http://{name}:8008" for name in ("pg1", "pg2", "pg3")}


class StatusError(RuntimeError):
    pass


def read_json(url):
    with urlopen(url, timeout=3) as response:
        return json.load(response)


class ClusterStatus:
    def __init__(self, nodes=None, fetch=read_json):
        self.nodes = nodes or NODES
        self.fetch = fetch

    def native_cluster(self):
        errors = []
        for name, address in self.nodes.items():
            try:
                data = self.fetch(address + "/cluster")
                if not isinstance(data.get("members"), list):
                    raise ValueError("Missing members")
                return data
            except (OSError, ValueError, KeyError, TypeError) as error:
                errors.append(f"{name}: {error}")
        raise StatusError("; ".join(errors))

    def snapshot(self):
        native = self.native_cluster()
        members = native["members"]
        names = [member.get("name") for member in members]
        if len(names) != len(self.nodes) or set(names) != set(self.nodes):
            raise StatusError("Patroni does not report the expected three members")
        if sum(member.get("role") == "leader" for member in members) != 1:
            raise StatusError("Patroni does not report exactly one leader")
        with ThreadPoolExecutor(max_workers=len(self.nodes)) as executor:
            futures = {
                name: executor.submit(self.fetch, address + "/patroni")
                for name, address in self.nodes.items()
            }
            statuses = {name: future.result() for name, future in futures.items()}
        result, identifiers, scopes = [], set(), set()
        for member in members:
            name = member["name"]
            status = statuses[name]
            identity = status.get("patroni", {})
            if identity.get("name") != name:
                raise StatusError(f"{name}: unexpected Patroni identity")
            identifier = status.get("database_system_identifier")
            if not identifier or not identity.get("scope"):
                raise StatusError(f"{name}: missing PostgreSQL cluster identity")
            identifiers.add(str(identifier))
            scopes.add(identity["scope"])
            if status.get("state") != "running":
                raise StatusError(f"{name}: PostgreSQL state is {status.get('state')}")
            if member["role"] == "leader":
                if status.get("role") not in ("primary", "master"):
                    raise StatusError(f"{name}: DCS leader is not a PostgreSQL primary")
            elif (
                status.get("role") != "replica"
                or status.get("replication_state") != "streaming"
            ):
                raise StatusError(f"{name}: standby is not receiving WAL")
            result.append(
                member
                | {
                    "native_cluster_state": member.get("state"),
                    "state": status["state"],
                    "replication_state": status.get("replication_state"),
                    "postgresql_status": status,
                }
            )
        if len(identifiers) != 1 or len(scopes) != 1:
            raise StatusError("Nodes belong to different PostgreSQL/Patroni clusters")
        return native | {
            "members": result,
            "scope": scopes.pop(),
            "state_source": "Patroni /patroni.state",
        }


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path not in ("/cluster", "/native/cluster", "/health"):
            self.reply(404, {"error": "Unknown endpoint"})
            return
        try:
            data = (
                self.server.status.native_cluster()
                if path == "/native/cluster"
                else self.server.status.snapshot()
            )
            self.reply(200, data)
        except (OSError, ValueError, KeyError, TypeError, StatusError) as error:
            self.reply(503, {"error": str(error)})

    def reply(self, status, data):
        content = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8011"))), Handler)
    server.status = ClusterStatus()
    server.serve_forever()
