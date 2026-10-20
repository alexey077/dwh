import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser(description="Require the complete original checker report")
parser.add_argument("report", type=Path)
args = parser.parse_args()
report = json.loads(args.report.read_text())
required = {"contract", "keys", "volume", "dq", "cross", "repl", "inv", "cdc", "ha", "realism"}
sections = {check["section"] for check in report["checks"]}
if sections != required:
    raise SystemExit(f"Incomplete checker run: sections {sorted(sections)}")
failures = [check for check in report["checks"] if not check["ok"]]
if failures:
    raise SystemExit(
        "Runtime failures: "
        + ", ".join(f"{check['section']}.{check['id']}: {check['detail']}" for check in failures)
    )
automatic = sum(value for value in report["scores"].values() if value is not None)
if automatic != 21:
    raise SystemExit(f"Expected all 21 automatic points, got {automatic}")
print(f"All {len(report['checks'])} official checks passed; automatic score 21/21")
