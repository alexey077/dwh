import os

import psycopg2


connection = psycopg2.connect(os.environ["WMS_TEST_DSN"])
try:
    with connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO wms.supplier (supplier_bk,supplier_name,country) VALUES ('TEST-SUP','Supplier','RU')"
        )
        cursor.execute(
            "INSERT INTO wms.distribution_center (dc_bk,dc_name,region,city) VALUES ('TEST-DC','DC','R-01','City')"
        )
        cursor.execute(
            "INSERT INTO wms.location(location_type,location_bk,dc_bk) VALUES ('dc','TEST-DC','TEST-DC'),('pharmacy','TEST-PH',NULL)"
        )
        cursor.execute("""INSERT INTO wms.batch(batch_bk,sku,series_no,manufactured_date,expiry_date,received_at)
                          VALUES ('TEST-BATCH','TEST-SKU','TEST-SERIES','2025-01-01','2027-01-01','2025-02-01Z')""")
        cursor.execute("""INSERT INTO wms.purchase(purchase_bk,supplier_bk,dc_bk,ordered_at,expected_at)
                          VALUES ('TEST-PO','TEST-SUP','TEST-DC','2025-01-20Z','2025-02-01Z')""")
        cursor.execute("""INSERT INTO wms.purchase_line(purchase_bk,line_no,sku,batch_bk,received_at,quantity,unit_cost,line_cost)
                          VALUES ('TEST-PO',1,'TEST-SKU','TEST-BATCH','2025-02-01Z',10,20,200)""")
        cursor.execute("""INSERT INTO wms.movement(movement_bk,batch_bk,movement_type,src_type,src_bk,dst_type,dst_bk,
                          qty,moved_at,purchase_bk,purchase_line_no)
                          VALUES ('TEST-RECEIPT','TEST-BATCH','receipt','supplier','TEST-SUP','dc','TEST-DC',10,
                          '2025-02-01Z','TEST-PO',1)""")
        cursor.execute("""INSERT INTO wms.movement(movement_bk,batch_bk,movement_type,src_type,src_bk,dst_type,dst_bk,qty,moved_at)
                          VALUES ('TEST-TRANSFER','TEST-BATCH','transfer','dc','TEST-DC','pharmacy','TEST-PH',4,'2025-02-02Z')""")
        cursor.execute(
            "SELECT location_bk,qty_on_hand FROM wms.stock ORDER BY location_bk"
        )
        assert cursor.fetchall() == [("TEST-DC", 6), ("TEST-PH", 4)]
        for statement in [
            """INSERT INTO wms.movement(movement_bk,batch_bk,movement_type,dst_type,dst_bk,qty,moved_at)
               VALUES ('TEST-BAD-TRANSFER','TEST-BATCH','transfer','pharmacy','TEST-PH',5,'2025-02-03Z')""",
            """INSERT INTO wms.movement(movement_bk,batch_bk,movement_type,src_type,src_bk,qty,moved_at)
               VALUES ('TEST-EXCESS','TEST-BATCH','writeoff','pharmacy','TEST-PH',5,'2025-02-03Z')""",
            """INSERT INTO wms.batch(batch_bk,sku,series_no,manufactured_date,expiry_date,received_at)
               VALUES ('TEST-EXPIRED','TEST-SKU','TEST-EXPIRED','2024-01-01','2024-02-01','2025-02-01Z')""",
        ]:
            cursor.execute("SAVEPOINT invalid_stock")
            try:
                cursor.execute(statement)
                raise AssertionError("Invalid stock operation accepted")
            except psycopg2.Error as error:
                assert error.pgcode == "23514", (error.pgcode, str(error))
                cursor.execute("ROLLBACK TO SAVEPOINT invalid_stock")
        cursor.execute(
            "SELECT qty_on_hand FROM wms.stock WHERE location_bk = 'TEST-PH'"
        )
        assert cursor.fetchone()[0] == 4
    print("WMS: receipt, transfer, atomic stock debit and expiry check passed")
finally:
    connection.rollback()
    connection.close()
