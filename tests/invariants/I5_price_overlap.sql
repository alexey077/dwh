SET LOCAL ROLE test_writer;
INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country)
VALUES ('T-I5-MFG', 'Тестовый производитель', 'RU');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty, updated_at)
VALUES ('T-I5-SKU', 'Тестовый товар', 'T-I5-MFG', 'otc', false, 10, '2025-01-01Z');
INSERT INTO catalog.price (price_bk, sku, price_scope, scope_bk, price, valid_from, valid_to)
VALUES ('T-I5-PRICE-1', 'T-I5-SKU', 'chain', 'ALL', 100, '2025-01-01Z', '2025-07-01Z');
INSERT INTO catalog.price (price_bk, sku, price_scope, scope_bk, price, valid_from, valid_to)
VALUES ('T-I5-PRICE-2', 'T-I5-SKU', 'chain', 'ALL', 110, '2025-06-01Z', '2025-09-01Z');
