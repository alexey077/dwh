from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from cluster_status import ClusterStatus, StatusError


class ClusterStatusTests(unittest.TestCase):
    def setUp(self):
        self.nodes = {name: f"http://{name}:8008" for name in ("pg1", "pg2", "pg3")}
        members = [
            {
                "name": name,
                "role": "leader" if name == "pg1" else "replica",
                "state": "running" if name == "pg1" else "streaming",
            }
            for name in self.nodes
        ]
        self.data = {}
        for name, address in self.nodes.items():
            self.data[address + "/cluster"] = {"members": deepcopy(members)}
            self.data[address + "/patroni"] = {
                "state": "running",
                "role": "primary" if name == "pg1" else "replica",
                "replication_state": None if name == "pg1" else "streaming",
                "database_system_identifier": "123456",
                "patroni": {"name": name, "scope": "apteka108"},
            }

    def fetch(self, url):
        value = self.data[url]
        if isinstance(value, Exception):
            raise value
        return deepcopy(value)

    def snapshot(self):
        return ClusterStatus(self.nodes, self.fetch).snapshot()

    def test_live_process_and_replication_states_are_separate(self):
        member = self.snapshot()["members"][1]
        self.assertEqual(member["state"], "running")
        self.assertEqual(member["native_cluster_state"], "streaming")
        self.assertEqual(member["replication_state"], "streaming")
        self.assertEqual(member["state"], member["postgresql_status"]["state"])

    def test_unreachable_node_cannot_be_reported_healthy(self):
        self.data["http://pg2:8008/patroni"] = OSError("connection refused")
        with self.assertRaises(OSError):
            self.snapshot()

    def test_stopped_postgres_cannot_be_reported_healthy(self):
        self.data["http://pg2:8008/patroni"]["state"] = "stopped"
        with self.assertRaises(StatusError):
            self.snapshot()

    def test_replica_without_wal_receiver_is_rejected(self):
        self.data["http://pg2:8008/patroni"]["replication_state"] = None
        with self.assertRaises(StatusError):
            self.snapshot()

    def test_wrong_node_identity_is_rejected(self):
        self.data["http://pg2:8008/patroni"]["patroni"]["name"] = "pg3"
        with self.assertRaises(StatusError):
            self.snapshot()

    def test_wrong_cluster_is_rejected(self):
        self.data["http://pg2:8008/patroni"]["database_system_identifier"] = "other"
        with self.assertRaises(StatusError):
            self.snapshot()

    def test_dcs_role_must_match_live_postgres_role(self):
        self.data["http://pg1:8008/patroni"]["role"] = "replica"
        with self.assertRaises(StatusError):
            self.snapshot()


if __name__ == "__main__":
    unittest.main()
