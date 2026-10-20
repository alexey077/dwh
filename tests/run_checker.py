import argparse
import os
from pathlib import Path
import subprocess
import sys

import yaml

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--sections", default="contract,keys,inv")
args = parser.parse_args()
submission = yaml.safe_load((root / "hw01_submission.yaml").read_text())
for role in ("master", "replica", "admin", "writer"):
    submission["connections"][role] = {
        service: os.environ[f"{service.upper()}_TEST_DSN"]
        for service in ("crm", "catalog", "pos", "wms")
    }
manifest = root / ".dev-submission.yaml"
manifest.write_text(yaml.safe_dump(submission, allow_unicode=True, sort_keys=False))
(root / "reports").mkdir(exist_ok=True)
try:
    subprocess.run(
        [
            sys.executable,
            str(root / "hw01/hw01_check.py"),
            "--submission",
            str(manifest),
            "--sections",
            args.sections,
            "--json",
            str(root / "reports/aux-sql-check.json"),
            "--verbose",
        ],
        cwd=root,
        check=True,
    )
finally:
    manifest.unlink(missing_ok=True)
