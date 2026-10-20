SET LOCAL ROLE test_writer;
INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country)
VALUES ('T-I6-MFG', 'Тестовый производитель', 'RU');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty, updated_at)
VALUES ('T-I6-SKU', 'Тестовый товар', 'T-I6-MFG', 'otc', false, 10, '2025-01-01Z');
INSERT INTO catalog.sku_history
    (sku, valid_from, sku_name, manufacturer_bk, category, is_rx, is_vital, pack_qty, is_active, is_deleted)
VALUES ('T-I6-SKU', '2025-06-01Z', 'Вторая текущая версия', 'T-I6-MFG', 'otc', false, false, 10, true, false);
