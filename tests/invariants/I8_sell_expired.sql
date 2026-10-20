SET LOCAL ROLE test_writer;
INSERT INTO pos.pharmacy (pharmacy_bk, pharmacy_name, region, city, address, opened_at, updated_at)
VALUES ('T-I8-PH', 'Тестовая аптека', 'R-01', 'Москва', 'Тестовая, 1', '2020-01-01', '2025-01-01Z');
INSERT INTO pos.cashier (cashier_bk, cashier_name) VALUES ('T-I8-CASHIER', 'Тестовый кассир');
INSERT INTO pos.cash_register (register_bk, pharmacy_bk) VALUES ('T-I8-REGISTER', 'T-I8-PH');
INSERT INTO pos.shift (shift_bk, register_bk, cashier_bk, opened_at)
VALUES ('T-I8-SHIFT', 'T-I8-REGISTER', 'T-I8-CASHIER', '2025-01-01Z');
INSERT INTO pos.batch_reference (batch_bk, sku, manufactured_date, expiry_date, received_at)
VALUES ('T-I8-BATCH', 'T-I8-SKU', '2024-01-01', '2025-05-01', '2025-01-01Z');
INSERT INTO pos.sku_reference (sku, valid_from, sku_name, is_rx)
VALUES ('T-I8-SKU', '2025-01-01Z', 'Тестовый товар', false);
INSERT INTO pos.price_reference (price_bk, sku, price_scope, scope_bk, price, currency, valid_from)
VALUES ('T-I8-PRICE', 'T-I8-SKU', 'chain', 'ALL', 100, 'RUB', '2025-01-01Z');
INSERT INTO pos.receipt (receipt_bk, pharmacy_bk, cashier_bk, shift_bk, receipt_dt,
                         doc_type, parent_receipt_bk, total_amount, discount_amount)
VALUES ('T-I8-SALE', 'T-I8-PH', 'T-I8-CASHIER', 'T-I8-SHIFT', '2025-06-01Z', 'sale',
        NULL, 100, 0);
INSERT INTO pos.receipt_line (receipt_bk, line_no, sku, batch_bk, price_bk, quantity, unit_price,
                              line_discount, line_amount, is_rx_snapshot, sku_name_snapshot)
VALUES ('T-I8-SALE', 1, 'T-I8-SKU', 'T-I8-BATCH', 'T-I8-PRICE', 1, 100,
        0, 100, false, 'Тестовый товар');
