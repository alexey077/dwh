from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from threading import Barrier
from uuid import uuid4

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from migrate import grant_access


ADMIN = os.environ.get(
    "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
)


@contextmanager
def test_database(service):
    name = f"hw01_check_{uuid4().hex[:12]}_{service}"
    admin = psycopg2.connect(make_dsn(ADMIN, dbname="postgres"))
    admin.autocommit = True
    created = False
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
            created = True
        dsn = make_dsn(ADMIN, dbname=name)
        with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE 'UTC'")
            for path in [
                ROOT / "migrations/000_common.sql",
                *sorted((ROOT / "migrations" / service).glob("*.sql")),
            ]:
                cursor.execute(path.read_text())
            grant_access(cursor, service)
            path = (
                ROOT
                / "tests/invariants"
                / (
                    "I7_stock_negative.sql"
                    if service == "wms"
                    else "I11_refund_excess.sql"
                )
            )
            marker = (
                "INSERT INTO wms.movement ("
                if service == "wms"
                else "INSERT INTO pos.receipt ("
            )
            fixture = path.read_text().rsplit(marker, 1)[0]
            cursor.execute(fixture)
        yield dsn
    finally:
        if created:
            assert name.startswith("hw01_check_") and name not in (
                "crm_service_db",
                "catalog_service_db",
                "pos_service_db",
                "wms_service_db",
            )
            with admin.cursor() as cursor:
                cursor.execute(
                    sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                        sql.Identifier(name)
                    )
                )
        admin.close()


def compete(dsn, operation):
    barrier = Barrier(2)

    def worker(number):
        connection = psycopg2.connect(dsn, connect_timeout=10)
        pid = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE test_writer")
                cursor.execute("SET LOCAL lock_timeout='10s'")
                cursor.execute("SET LOCAL statement_timeout='20s'")
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
                barrier.wait(timeout=10)
                operation(cursor, number)
            connection.commit()
            return {"result": "committed", "backend_pid": pid}
        except psycopg2.Error as error:
            connection.rollback()
            return {"result": error.pgcode, "backend_pid": pid}
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, (1, 2)))
    assert len({result["backend_pid"] for result in results}) == 2
    return results


def writeoff(cursor, number):
    key = f"CONCURRENT-WRITEOFF-{number}"
    cursor.execute(
        """INSERT INTO wms.movement
           (movement_bk,batch_bk,movement_type,src_type,src_bk,qty,moved_at)
           VALUES (%s,'T-I7-BATCH','writeoff','dc','T-I7-DC',7,'2025-02-02Z')""",
        (key,),
    )
    cursor.execute(
        "INSERT INTO wms.writeoff_detail(movement_bk,reason) VALUES (%s,'damaged')",
        (key,),
    )


def refund(cursor, number):
    key = f"CONCURRENT-REFUND-{number}"
    cursor.execute(
        """INSERT INTO pos.receipt
           (receipt_bk,pharmacy_bk,cashier_bk,shift_bk,receipt_dt,doc_type,
            parent_receipt_bk,total_amount,discount_amount)
           VALUES (%s,'T-I11-PH','T-I11-CASHIER','T-I11-SHIFT','2025-06-02Z',
                   'refund','T-I11-SALE',100,0)""",
        (key,),
    )
    cursor.execute(
        """INSERT INTO pos.receipt_line
           (receipt_bk,line_no,sku,batch_bk,price_bk,quantity,unit_price,line_discount,
            line_amount,is_rx_snapshot,sku_name_snapshot)
           VALUES (%s,1,'T-I11-SKU','T-I11-BATCH','T-I11-PRICE',1,100,0,100,false,'Тестовый товар')""",
        (key,),
    )
    cursor.execute(
        "INSERT INTO pos.payment(receipt_bk,payment_no,payment_method,amount) VALUES (%s,1,'card',100)",
        (key,),
    )


evidence = {}
with test_database("wms") as dsn:
    results = compete(dsn, writeoff)
    assert sorted(result["result"] for result in results) == ["23514", "committed"], (
        results
    )
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT qty_on_hand FROM wms.stock WHERE batch_bk='T-I7-BATCH'")
        assert cursor.fetchone()[0] == 3
    evidence["stock"] = {
        "initial": 10,
        "requested_each": 7,
        "remaining": 3,
        "workers": results,
    }
    print("Concurrent writeoffs: one committed, one rejected with 23514; stock=3")

with test_database("pos") as dsn:
    results = compete(dsn, refund)
    assert sorted(result["result"] for result in results) == ["P0001", "committed"], (
        results
    )
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT coalesce(sum(l.quantity),0)
               FROM pos.receipt r JOIN pos.receipt_line l USING(receipt_bk)
               WHERE r.parent_receipt_bk='T-I11-SALE'"""
        )
        assert cursor.fetchone()[0] == 1
    evidence["refund"] = {
        "sold": 1,
        "requested_each": 1,
        "returned": 1,
        "workers": results,
    }
    print("Concurrent refunds: one committed, one rejected with P0001; returned=1")

(ROOT / "reports").mkdir(exist_ok=True)
(ROOT / "reports/concurrency.json").write_text(json.dumps(evidence, indent=2) + "\n")
print(
    "Temporary verification databases were removed; four source databases were preserved"
)
