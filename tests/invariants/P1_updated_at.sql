SET LOCAL ROLE test_writer;
INSERT INTO catalog.manufacturer (manufacturer_bk, manufacturer_name, country)
VALUES ('T-P1-MFG', 'Тестовый производитель', 'RU');
INSERT INTO catalog.sku (sku, sku_name, manufacturer_bk, category, is_rx, pack_qty, updated_at)
VALUES ('T-P1-SKU', 'Тестовый товар', 'T-P1-MFG', 'otc', false, 10, '2025-01-01Z');
CREATE TEMP TABLE p1_before ON COMMIT DROP AS
SELECT updated_at FROM catalog.sku WHERE sku = 'T-P1-SKU';
UPDATE catalog.sku SET sku_name = 'Новое название' WHERE sku = 'T-P1-SKU';
SELECT s.updated_at > b.updated_at AS ok
FROM catalog.sku s CROSS JOIN p1_before b WHERE s.sku = 'T-P1-SKU';
