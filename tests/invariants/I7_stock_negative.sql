SET LOCAL ROLE test_writer;
INSERT INTO wms.supplier (supplier_bk, supplier_name, country) VALUES ('T-I7-SUP', 'Поставщик', 'RU');
INSERT INTO wms.distribution_center (dc_bk, dc_name, region, city) VALUES ('T-I7-DC', 'РЦ', 'R-01', 'Москва');
INSERT INTO wms.location (location_type, location_bk, dc_bk) VALUES ('dc', 'T-I7-DC', 'T-I7-DC');
INSERT INTO wms.batch (batch_bk, sku, series_no, manufactured_date, expiry_date, received_at)
VALUES ('T-I7-BATCH', 'T-I7-SKU', 'T-I7-SERIES', '2024-01-01', '2027-01-01', '2025-02-01Z');
INSERT INTO wms.purchase (purchase_bk, supplier_bk, dc_bk, ordered_at, expected_at)
VALUES ('T-I7-PO', 'T-I7-SUP', 'T-I7-DC', '2025-01-20Z', '2025-02-01Z');
INSERT INTO wms.purchase_line (purchase_bk, line_no, sku, batch_bk, received_at, quantity, unit_cost, line_cost)
VALUES ('T-I7-PO', 1, 'T-I7-SKU', 'T-I7-BATCH', '2025-02-01Z', 10, 20, 200);
INSERT INTO wms.movement (movement_bk, batch_bk, movement_type, src_type, src_bk, dst_type, dst_bk,
                         qty, moved_at, purchase_bk, purchase_line_no)
VALUES ('T-I7-IN', 'T-I7-BATCH', 'receipt', 'supplier', 'T-I7-SUP', 'dc', 'T-I7-DC',
        10, '2025-02-01Z', 'T-I7-PO', 1);
INSERT INTO wms.movement (movement_bk, batch_bk, movement_type, src_type, src_bk, qty, moved_at)
VALUES ('T-I7-OUT', 'T-I7-BATCH', 'writeoff', 'dc', 'T-I7-DC', 11, '2025-02-02Z');
