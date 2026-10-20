SET LOCAL ROLE test_writer;
INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country)
VALUES ('T-I2-MFG', 'Тестовый производитель', 'RU');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty, updated_at)
VALUES ('T-I2-SKU', 'Тестовый товар', 'T-I2-MFG', 'otc', false, 10, '2025-01-01Z');
UPDATE catalog.sku SET sku = 'T-I2-CHANGED' WHERE sku = 'T-I2-SKU';
