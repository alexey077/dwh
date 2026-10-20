import argparse
import os
from pathlib import Path
import subprocess
import sys

import psycopg2
from psycopg2.extensions import make_dsn
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "hw01"))
from hw01_check import digest_sql


def service_dsn(service):
    return os.environ.get(f"{service.upper()}_TEST_DSN") or make_dsn(
        os.environ.get(
            "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
        ),
        dbname=f"{service}_service_db",
    )


def snapshot():
    contract = yaml.safe_load((ROOT / "hw01/hw01_contract.yaml").read_text())
    result = {}
    for service, spec in contract["services"].items():
        with psycopg2.connect(service_dsn(service)) as connection:
            with connection.cursor() as cursor:
                for view in spec["views"]:
                    cursor.execute(digest_sql(view))
                    result[f"{service}.{view}"] = cursor.fetchone()
    return result


def seed(*arguments):
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/seed.py"), *arguments],
        cwd=ROOT,
        check=True,
    )


def reconcile():
    with psycopg2.connect(service_dsn("wms")) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT external_doc_bk,batch_bk,movement_type,sum(qty)
                FROM wms.movement WHERE movement_type IN ('sale_writeoff','return') GROUP BY 1,2,3""")
            stock_events = {(r[0], r[1], r[2]): r[3] for r in cursor.fetchall()}
            cursor.execute("""WITH flows AS (
                SELECT dst_type kind,dst_bk bk,batch_bk,qty FROM wms.movement WHERE dst_type IN ('dc','pharmacy')
                UNION ALL SELECT src_type,src_bk,batch_bk,-qty FROM wms.movement WHERE src_type IN ('dc','pharmacy')
            ) SELECT count(*) FROM (SELECT kind,bk,batch_bk,sum(qty) qty FROM flows GROUP BY 1,2,3) f
              FULL JOIN wms.stock s ON (s.location_type,s.location_bk,s.batch_bk)=(f.kind,f.bk,f.batch_bk)
              WHERE s.qty_on_hand IS DISTINCT FROM f.qty""")
            assert cursor.fetchone()[0] == 0
            cursor.execute(
                "SELECT max(received_at)-min(received_at) FROM contract.v_purchase_line"
            )
            assert cursor.fetchone()[0].days >= 365
            cursor.execute(
                "SELECT date_trunc('month',max(received_at))::date FROM contract.v_purchase_line"
            )
            latest = cursor.fetchone()[0]
            cursor.execute(
                "SELECT reference_month FROM core.seed_run WHERE batch_bk='FOUNDATION'"
            )
            assert latest == cursor.fetchone()[0]
    with psycopg2.connect(service_dsn("pos")) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT l.receipt_bk,l.batch_bk,
                CASE r.doc_type WHEN 'sale' THEN 'sale_writeoff' ELSE 'return' END,sum(l.quantity)
                FROM pos.receipt_line l JOIN pos.receipt r USING(receipt_bk) GROUP BY 1,2,3""")
            assert stock_events == {(r[0], r[1], r[2]): r[3] for r in cursor.fetchall()}
            cursor.execute(
                "SELECT max(receipt_dt)-min(receipt_dt),count(DISTINCT to_char(receipt_dt,'YYYY-MM')) FROM pos.receipt"
            )
            duration, months = cursor.fetchone()
            assert duration.days >= 365 and months >= 13, (duration, months)
    print("POS/WMS quantities, stock ledger and history coverage reconciled")


parser = argparse.ArgumentParser()
parser.add_argument("--receipts", type=int, default=24000)
parser.add_argument("--smoke", action="store_true")
args = parser.parse_args()
count = args.receipts
seed("--seed", "42", "--receipts", str(count))
before = snapshot()
seed("--seed", "42", "--receipts", str(count))
assert before == snapshot(), "Same batch changed contract fingerprints"
print("Same-seed idempotence: all 14 fingerprints unchanged")
seed("--seed", "777", "--receipts", "500", "--batch-id", "DELTA-TEST")
after = snapshot()
assert after["pos.v_receipt"][0] == before["pos.v_receipt"][0] + 500
seed("--seed", "777", "--receipts", "500", "--batch-id", "DELTA-TEST")
assert after == snapshot(), "Repeated explicit delta changed the data"
seed("--seed", "777", "--receipts", "500", "--next-batch")
assert snapshot()["pos.v_receipt"][0] == after["pos.v_receipt"][0] + 500
print("Explicit and automatic delta batches passed")
if not args.smoke:
    reconcile()
