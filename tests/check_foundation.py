import os

import psycopg2

minimums = {
    "crm": {"v_customer": 2400, "v_loyalty_card": 2100},
    "catalog": {"v_sku": 600, "v_price": 2016},
    "pos": {"v_pharmacy": 36},
    "wms": {
        "v_supplier": 12,
        "v_distribution_center": 4,
        "v_batch": 3600,
        "v_purchase_line": 7200,
        "v_movement": 28800,
        "v_stock": 25200,
    },
}
for service, views in minimums.items():
    with psycopg2.connect(os.environ[f"{service.upper()}_TEST_DSN"]) as connection:
        with connection.cursor() as cursor:
            for view, expected in views.items():
                cursor.execute(f"SELECT count(*) FROM contract.{view}")
                actual = cursor.fetchone()[0]
                assert actual == expected, (service, view, expected, actual)
                print(f"{service}.{view}: {actual}")
            if service == "wms":
                cursor.execute("""WITH flows AS (
                    SELECT dst_type kind,dst_bk bk,batch_bk,qty FROM wms.movement WHERE dst_type IN ('dc','pharmacy')
                    UNION ALL SELECT src_type,src_bk,batch_bk,-qty FROM wms.movement WHERE src_type IN ('dc','pharmacy')
                ) SELECT count(*) FROM (
                    SELECT kind,bk,batch_bk,sum(qty) qty FROM flows GROUP BY 1,2,3
                ) f FULL JOIN wms.stock s ON (s.location_type,s.location_bk,s.batch_bk)=(f.kind,f.bk,f.batch_bk)
                WHERE s.qty_on_hand IS DISTINCT FROM f.qty""")
                assert cursor.fetchone()[0] == 0
print("Foundation volumes and stock reconciliation passed")
