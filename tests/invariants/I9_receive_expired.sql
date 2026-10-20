SET LOCAL ROLE test_writer;
INSERT INTO wms.batch (batch_bk, sku, series_no, manufactured_date, expiry_date, received_at)
VALUES ('T-I9-BATCH', 'T-I9-SKU', 'T-I9-SERIES', '2024-01-01', '2025-01-31', '2025-02-01Z');
