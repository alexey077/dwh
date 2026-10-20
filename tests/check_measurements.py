import sys
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experiments import Event, Experiments, Workload, switching_metrics


events = [
    Event("old-ack", 10, 1, True, "a", "172.18.0.5"),
    Event("failure-1", 11, 2, False, "b", error="disconnected"),
    Event("failure-2", 19, 2, False, "c", error="disconnected"),
    Event("new-ack", 20, 1, True, "d", "172.18.0.7"),
    Event("late-old-ack", 20.1, 1, True, "e", "172.18.0.5"),
]
metrics = switching_metrics(events, "172.18.0.5", "172.18.0.7", 10.5)
assert metrics["rto_seconds"] == 10
assert metrics["errors_in_gap"] == 2
assert metrics["last_old_ack"] == "old-ack"
assert metrics["first_new_ack"] == "new-ack"

cidr_events = [replace(e, node=e.node + "/32") if e.ok else e for e in events]
assert switching_metrics(cidr_events, "172.18.0.5", "172.18.0.7", 10.5) == metrics
assert switching_metrics(events, "172.18.0.5/32", "172.18.0.7/32", 10.5) == metrics

ipv6_events = [
    replace(
        e,
        node="2001:0db8:0:0:0:0:0:5/128"
        if e.node.endswith(".5")
        else "2001:db8::7/128",
    )
    if e.ok
    else e
    for e in events
]
assert switching_metrics(ipv6_events, "2001:db8::5", "2001:db8::7", 10.5) == metrics

try:
    switching_metrics(events[:3], "172.18.0.5", "172.18.0.7", 10.5)
    raise AssertionError("Missing recovery was reported as a measured RTO")
except RuntimeError:
    pass

try:
    switching_metrics(events[1:], "172.18.0.5", "172.18.0.7", 10.5)
    raise AssertionError("Missing old-leader acknowledgement was accepted")
except RuntimeError:
    pass

load = Workload("unit", 10)
load.started, load.finished = 0, 10
load.events = [Event(str(i), i, i, True, str(i), "node") for i in range(1, 21)]
load.events += [Event("error", 21, 100, False, "x", error="test")]
metrics = load.metrics()
assert metrics["acknowledged"] == 20 and metrics["errors"] == 1
assert metrics["tps"] == 2 and metrics["median_ms"] == 10.5 and metrics["p95_ms"] == 19

with TemporaryDirectory() as directory, patch("experiments.ROOT", Path(directory)):
    runner = Experiments(60, 90)
    failed_load = Workload("test-missing-recovery", 90)
    failed_load.started, failed_load.finished = 0, 25
    failed_load.events = cidr_events[:3]
    with (
        patch("experiments.Workload", return_value=failed_load),
        patch.object(failed_load, "start", return_value=failed_load),
        patch.object(failed_load, "finish", return_value=failed_load),
        patch("experiments.leader", return_value="pg2"),
        patch("experiments.wait_new_leader", return_value="pg3"),
        patch("experiments.time.sleep"),
        patch("experiments.time.monotonic", return_value=10.5),
        patch.object(runner, "address", side_effect=["172.18.0.5", "172.18.0.7"]),
        patch.object(runner, "crash"),
        patch.object(runner, "command", return_value="synthetic log"),
    ):
        try:
            runner.failover("test-missing-recovery")
            raise AssertionError("Missing recovery was accepted in the orchestrator")
        except RuntimeError as error:
            assert "No acknowledged transaction on the new leader" in str(error)
    captured = json.loads((runner.directory / "01-events.json").read_text())
    assert len(captured) == 3 and captured[0]["node"] == "172.18.0.5/32"
    assert captured[0]["key"] == "a" and not captured[-1]["ok"]
print("Measurement arithmetic passed; this test does not run HA experiments")
