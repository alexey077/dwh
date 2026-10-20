SET LOCAL ROLE test_writer;
INSERT INTO pos.pharmacy (pharmacy_bk, pharmacy_name, region, city, address, opened_at, updated_at)
VALUES ('T-I12-PH', 'Тестовая аптека', 'R-01', 'Москва', 'Тестовая, 1', '2020-01-01', '2025-01-01Z');
INSERT INTO pos.cashier (cashier_bk, cashier_name) VALUES ('T-I12-CASHIER', 'Тестовый кассир');
INSERT INTO pos.cash_register (register_bk, pharmacy_bk) VALUES ('T-I12-REGISTER', 'T-I12-PH');
INSERT INTO pos.shift (shift_bk, register_bk, cashier_bk, opened_at)
VALUES ('T-I12-SHIFT', 'T-I12-REGISTER', 'T-I12-CASHIER', '2025-01-01Z');
INSERT INTO pos.batch_reference (batch_bk, sku, manufactured_date, expiry_date, received_at)
VALUES ('T-I12-BATCH', 'T-I12-SKU', '2024-01-01', '2027-01-01', '2025-01-01Z');
INSERT INTO pos.sku_reference (sku, valid_from, sku_name, is_rx)
VALUES ('T-I12-SKU', '2025-01-01Z', 'Тестовый товар', false);
INSERT INTO pos.price_reference (price_bk, sku, price_scope, scope_bk, price, currency, valid_from)
VALUES ('T-I12-PRICE', 'T-I12-SKU', 'chain', 'ALL', 100, 'RUB', '2025-01-01Z');
INSERT INTO pos.receipt (receipt_bk, pharmacy_bk, cashier_bk, shift_bk, receipt_dt,
                         doc_type, parent_receipt_bk, total_amount, discount_amount)
VALUES ('T-I12-SALE', 'T-I12-PH', 'T-I12-CASHIER', 'T-I12-SHIFT', '2025-06-01Z', 'sale',
        NULL, 100, 0);
INSERT INTO pos.receipt_line (receipt_bk, line_no, sku, batch_bk, price_bk, quantity, unit_price,
                              line_discount, line_amount, is_rx_snapshot, sku_name_snapshot)
VALUES ('T-I12-SALE', 1, 'T-I12-SKU', 'T-I12-BATCH', 'T-I12-PRICE', 1, 100,
        0, 100, false, 'Тестовый товар');
INSERT INTO pos.payment (receipt_bk, payment_no, payment_method, amount)
VALUES ('T-I12-SALE', 1, 'card', 99);
