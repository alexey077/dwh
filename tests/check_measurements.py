import sys
from io import BytesIO
from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from experiments import Event, Experiments, PatroniAPIError, Workload, api, switching_metrics


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
def http_error(status, detail):
    return HTTPError(
        "http://localhost:8008/switchover", status, "rejected", {},
        BytesIO(detail.encode()),
    )


for status, detail in (
    (412, "switchover is not possible: no good candidates have been found"),
    (412, "leader name does not match"),
    (503, "Switchover status unknown"),
    (401, "authentication required"),
):
    with patch("experiments.urlopen", side_effect=http_error(status, detail)) as request:
        try:
            api("/switchover", "POST", {"leader": "pg1"}, timeout=60)
            raise AssertionError("An HTTP rejection was accepted")
        except PatroniAPIError as error:
            assert error.status == status and error.detail == detail
            assert detail in str(error) and str(status) in str(error)
        assert request.call_count == 1

with patch("experiments.urlopen", side_effect=URLError("timed out")) as request:
    try:
        api("/switchover", "POST", {"leader": "pg1"}, timeout=60)
        raise AssertionError("An unknown operation result was accepted")
    except RuntimeError as error:
        assert "operation may already have started" in str(error)
    assert request.call_count == 1

reply = MagicMock()
reply.__enter__.return_value.read.return_value = b'{"members": []}'
with patch("experiments.urlopen", side_effect=[URLError("unreachable"), reply]) as request:
    assert api("/cluster") == {"members": []}
    assert request.call_count == 2

reply = MagicMock()
reply.__enter__.return_value.read.return_value = b'{"synchronous_mode": false}'
with patch("experiments.urlopen", side_effect=[URLError("connection refused"), reply]) as request:
    assert api("/config", "PATCH", {"synchronous_mode": False}) == {"synchronous_mode": False}
    assert request.call_count == 2


def check_switchover(rejections=(), permanent=None):
    with TemporaryDirectory() as directory, patch("experiments.ROOT", Path(directory)):
        runner = Experiments(60, 90)
        load = Workload("E4", 90)
        load.started, load.finished, load.events = 0, 90, list(events)
        clock, attempts, addresses = [0.5], [], []
        pending = list(rejections)
        captured = None

        def sleep(seconds):
            clock[0] += seconds

        def address(node):
            addresses.append(node)
            return {"pg1": "172.18.0.5", "pg3": "172.18.0.7"}[node]

        def patroni(path, method="GET", body=None, node=None, timeout=4):
            if path == "/switchover":
                assert method == "POST" and body == {"leader": "pg1"}
                assert node == "pg1" and timeout >= 20
                attempts.append(dict(body))
                error = pending.pop(0) if pending else permanent
                if error:
                    raise error
                return {"response": 'Successfully switched over to "pg3"'}
            assert path in ("/cluster", "/primary")
            return {"members": [], "role": "primary", "state": "running"}

        with (
            patch("experiments.Workload", return_value=load),
            patch.object(load, "start", return_value=load),
            patch.object(load, "finish", return_value=load),
            patch("experiments.leader", return_value="pg1"),
            patch("experiments.wait_cluster"),
            patch("experiments.wait_new_leader", return_value="pg3"),
            patch("experiments.time.sleep", side_effect=sleep),
            patch("experiments.time.monotonic", side_effect=lambda: clock[0]),
            patch("experiments.api", side_effect=patroni),
            patch.object(runner, "address", side_effect=address),
        ):
            try:
                runner.switchover()
            except PatroniAPIError as error:
                captured = error

        saved_events = json.loads((runner.directory / "01-events.json").read_text())
        assert len(saved_events) == len(events)
        if captured:
            assert load.stop.is_set() and not runner.sections
            assert str(captured) in runner.output
        else:
            assert addresses == ["pg1", "pg3"]
            assert runner.sections[0][1]["rto_seconds"] == 10
            assert not load.stop.is_set()
        return attempts, clock[0], captured


temporary = PatroniAPIError(
    "pg1", "POST", "/switchover", 412,
    "switchover is not possible: no good candidates have been found",
)
attempts, _, error = check_switchover()
assert len(attempts) == 1 and error is None
attempts, _, error = check_switchover([temporary])
assert len(attempts) == 2 and error is None

for status, detail in (
    (412, "leader name does not match"),
    (503, "Switchover status unknown"),
):
    rejection = PatroniAPIError("pg1", "POST", "/switchover", status, detail)
    attempts, _, error = check_switchover([rejection])
    assert len(attempts) == 1 and error is rejection

attempts, elapsed, error = check_switchover(permanent=temporary)
assert 1 < len(attempts) <= 20 and elapsed <= 26 and error is temporary
print("Measurement arithmetic and switchover error handling passed; HA requires a live stand")
