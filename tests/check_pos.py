import os
from pathlib import Path

import psycopg2


root = Path(__file__).resolve().parents[1]
fixture = (root / "tests/invariants/I11_refund_excess.sql").read_text()
fixture = fixture.replace("T-I11", "T-POS-VALID")
fixture = fixture.replace("200", "100").replace("PRICE', 2, 100", "PRICE', 1, 100")
connection = psycopg2.connect(os.environ["POS_TEST_DSN"])
try:
    with connection.cursor() as cursor:
        cursor.execute(fixture)
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute(
            "SELECT count(*) FROM pos.receipt WHERE receipt_bk LIKE 'T-POS-VALID-%' AND NOT check_pending"
        )
        assert cursor.fetchone()[0] == 2
        cursor.execute(
            "UPDATE pos.sku_reference SET sku_name = 'Новое имя' WHERE sku = 'T-POS-VALID-SKU'"
        )
        cursor.execute(
            "SELECT bool_and(sku_name_snapshot = 'Тестовый товар') FROM contract.v_receipt_line WHERE sku = 'T-POS-VALID-SKU'"
        )
        assert cursor.fetchone()[0] is True
    print("POS: balanced sale and refund accepted; historical snapshots stay unchanged")
finally:
    connection.rollback()
    connection.close()
