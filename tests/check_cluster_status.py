import argparse
import json
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
URL = "http://localhost:8011"
PORTS = {"pg1": 8008, "pg2": 8009, "pg3": 8010}


def fetch(url):
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def check():
    data = fetch(URL + "/cluster")
    assert {member["name"] for member in data["members"]} == set(PORTS)
    assert sum(member["role"] == "leader" for member in data["members"]) == 1
    for member in data["members"]:
        upstream = fetch(f"http://localhost:{PORTS[member['name']]}/patroni")
        assert member["state"] == upstream["state"] == "running"
        assert member["replication_state"] == upstream.get("replication_state")
        if member["role"] != "leader":
            assert upstream["role"] == "replica"
            assert upstream["replication_state"] == "streaming"
    native = fetch(URL + "/native/cluster")
    assert {m["name"] for m in native["members"]} == set(PORTS)
    print("Live states match all three original Patroni node endpoints", flush=True)
    return data


def probe_failure(data):
    node = next(member["name"] for member in data["members"] if member["role"] != "leader")
    try:
        subprocess.run(["docker", "compose", "stop", "-t", "5", node], cwd=ROOT, check=True)
        try:
            fetch(URL + "/cluster")
        except HTTPError as error:
            assert error.code == 503, error.code
            print(f"Stopped {node}: cluster status correctly returned HTTP 503", flush=True)
        else:
            raise AssertionError("A stopped member was reported healthy")
    finally:
        subprocess.run(["docker", "compose", "start", node], cwd=ROOT, check=True)
        deadline = time.monotonic() + 150
        while True:
            try:
                restored = check()
                break
            except (OSError, ValueError, AssertionError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(1)
        print(f"Restarted {node}: three healthy nodes restored", flush=True)
        return restored


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe-failure", action="store_true")
    args = parser.parse_args()
    result = check()
    if args.probe_failure:
        result = probe_failure(result)
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/cluster_status.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
