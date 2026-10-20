SET LOCAL ROLE test_writer;
INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country)
VALUES ('T-I1-MFG', 'Тестовый производитель', 'RU');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty, updated_at)
VALUES ('T-I1-SKU', 'Тестовый товар', 'T-I1-MFG', 'otc', false, 10, '2025-01-01Z');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty)
VALUES ('T-I1-SKU', 'Другая строка с тем же ключом', 'T-I1-MFG', 'otc', false, 10);
