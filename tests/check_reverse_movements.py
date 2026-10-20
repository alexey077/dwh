import os
from uuid import uuid4

import psycopg2
from psycopg2.extensions import make_dsn


DSN = os.environ.get("WMS_TEST_DSN") or make_dsn(
    os.environ.get(
        "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
    ),
    dbname="wms_service_db",
)


def expect_failure(reason, supplier, sqlstate="P0001", overspend=False):
    key = "CHECK-WRITEOFF-" + uuid4().hex
    connection = psycopg2.connect(DSN)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL ROLE test_writer")
            cursor.execute(
                """SELECT m.batch_bk,m.src_type,m.src_bk,m.moved_at,s.qty_on_hand
                   FROM wms.movement m JOIN wms.writeoff_detail d USING(movement_bk)
                   JOIN wms.stock s ON (s.batch_bk,s.location_type,s.location_bk)
                                      =(m.batch_bk,m.src_type,m.src_bk)
                   WHERE d.reason='supplier_return'"""
            )
            batch, kind, location, at_time, stock = cursor.fetchone()
            cursor.execute(
                """INSERT INTO wms.movement
                   (movement_bk,batch_bk,movement_type,src_type,src_bk,qty,moved_at)
                   VALUES (%s,%s,'writeoff',%s,%s,%s,%s)""",
                (key, batch, kind, location, stock + 1 if overspend else 1, at_time),
            )
            if reason is not None:
                cursor.execute(
                    "INSERT INTO wms.writeoff_detail(movement_bk,reason,supplier_bk) VALUES (%s,%s,%s)",
                    (key, reason, supplier),
                )
        connection.commit()
    except psycopg2.Error as error:
        connection.rollback()
        assert error.pgcode == sqlstate, (error.pgcode, error)
        print(f"Rejected {reason or 'missing reason'}: SQLSTATE {error.pgcode}")
    else:
        raise AssertionError("Invalid writeoff was committed")
    finally:
        connection.close()
    with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM wms.movement WHERE movement_bk=%s", (key,))
        assert cursor.fetchone()[0] == 0, "Rejected movement leaked"


with psycopg2.connect(DSN) as connection, connection.cursor() as cursor:
    cursor.execute(
        """SELECT d.reason,d.supplier_bk,m.qty,m.moved_at,b.expiry_date
           FROM wms.writeoff_detail d JOIN wms.movement m USING(movement_bk)
           JOIN wms.batch b USING(batch_bk)"""
    )
    rows = {row[0]: row[1:] for row in cursor.fetchall()}
    assert set(rows) == {"supplier_return", "damaged", "expired"}
    assert rows["supplier_return"][0] == "SUP-001"
    assert rows["expired"][2].date() > rows["expired"][3]
    cursor.execute(
        """WITH flows AS (
             SELECT dst_type kind,dst_bk bk,batch_bk,qty FROM wms.movement
             WHERE batch_bk LIKE 'BATCH-REVERSE-%' AND dst_type IN ('dc','pharmacy')
             UNION ALL
             SELECT src_type,src_bk,batch_bk,-qty FROM wms.movement
             WHERE batch_bk LIKE 'BATCH-REVERSE-%' AND src_type IN ('dc','pharmacy')
           ), totals AS (SELECT kind,bk,batch_bk,sum(qty) qty FROM flows GROUP BY 1,2,3)
           SELECT count(*) FROM totals t JOIN wms.stock s
           ON (s.location_type,s.location_bk,s.batch_bk)=(t.kind,t.bk,t.batch_bk)
           WHERE s.qty_on_hand <> t.qty OR s.qty_on_hand < 0"""
    )
    assert cursor.fetchone()[0] == 0
print("Supplier return, damaged and expired writeoffs reconcile with stock")

expect_failure(None, None)
expect_failure("supplier_return", "SUP-002")
expect_failure("expired", None)
expect_failure("supplier_return", "SUP-001", "23514", overspend=True)
