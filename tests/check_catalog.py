import os

import psycopg2


connection = psycopg2.connect(os.environ["CATALOG_TEST_DSN"])
try:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country) VALUES ('TEST-MFG', 'Test', 'RU')"
        )
        cursor.execute("""INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty)
                          VALUES ('TEST-SKU', 'Test item', 'TEST-MFG', 'otc', false, 10)""")
        for scope, key, amount in [
            ("chain", "ALL", 100),
            ("region", "R-01", 90),
            ("pharmacy", "PH-01", 80),
        ]:
            cursor.execute(
                """INSERT INTO catalog.price
                              (price_bk, sku, price_scope, scope_bk, price, valid_from, valid_to)
                              VALUES (%s, 'TEST-SKU', %s, %s, %s, '2025-01-01Z', '2026-01-01Z')""",
                (f"TEST-{scope}", scope, key, amount),
            )
        cursor.execute(
            "SELECT price FROM catalog.price_at('TEST-SKU', 'R-01', 'PH-01', '2025-06-01Z')"
        )
        assert cursor.fetchone()[0] == 80
        cursor.execute(
            "SELECT price FROM catalog.price_at('TEST-SKU', 'R-01', 'PH-02', '2025-06-01Z')"
        )
        assert cursor.fetchone()[0] == 90
        cursor.execute(
            "SELECT price FROM catalog.price_at('TEST-SKU', 'R-02', 'PH-02', '2025-06-01Z')"
        )
        assert cursor.fetchone()[0] == 100

        cases = [
            ("P0001", "UPDATE catalog.sku SET sku = 'CHANGED' WHERE sku = 'TEST-SKU'"),
            (
                "P0001",
                "UPDATE catalog.price SET price = 200 WHERE price_bk = 'TEST-chain'",
            ),
            (
                "23P01",
                """INSERT INTO catalog.price
                         (price_bk, sku, price_scope, scope_bk, price, valid_from, valid_to)
                         VALUES ('TEST-OVERLAP', 'TEST-SKU', 'chain', 'ALL', 110, '2025-06-01Z', '2025-08-01Z')""",
            ),
            (
                "23505",
                """INSERT INTO catalog.sku_history
                         (sku, valid_from, sku_name, manufacturer_bk, category, is_rx, is_vital, pack_qty, is_active, is_deleted)
                         VALUES ('TEST-SKU', '2030-01-01Z', 'Other', 'TEST-MFG', 'otc', false, false, 10, true, false)""",
            ),
        ]
        for expected, statement in cases:
            cursor.execute("SAVEPOINT invariant_case")
            try:
                cursor.execute(statement)
                raise AssertionError(f"Expected {expected}")
            except psycopg2.Error as error:
                assert error.pgcode == expected, (expected, error.pgcode, str(error))
                cursor.execute("ROLLBACK TO SAVEPOINT invariant_case")
        cursor.execute(
            "UPDATE catalog.sku SET sku_name = 'New name' WHERE sku = 'TEST-SKU'"
        )
        cursor.execute(
            "SELECT count(*), count(*) FILTER (WHERE is_current) FROM catalog.sku_history WHERE sku = 'TEST-SKU'"
        )
        assert cursor.fetchone() == (2, 1)
    print(
        "Catalog: key immutability, price overlap, current version, scope priority and history passed"
    )
finally:
    connection.rollback()
    connection.close()
