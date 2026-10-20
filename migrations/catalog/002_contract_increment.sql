CREATE OR REPLACE VIEW contract.v_sku AS
SELECT s.sku, s.sku_name,
       (SELECT string_agg(i.inn_name, ' + ' ORDER BY i.inn_name)
        FROM catalog.sku_inn si JOIN catalog.inn i USING (inn_bk)
        WHERE si.sku = s.sku AND NOT si.is_deleted) AS inn_name,
       m.manufacturer_name, f.form_name AS drug_form,
       s.category, s.is_rx, s.is_vital, s.pack_qty,
       s.is_active AND NOT s.is_deleted AS is_active,
       greatest(s.updated_at, m.updated_at, coalesce(f.updated_at, s.updated_at),
                coalesce((SELECT max(greatest(si.updated_at, i.updated_at))
                          FROM catalog.sku_inn si JOIN catalog.inn i USING (inn_bk)
                          WHERE si.sku = s.sku), s.updated_at)) AS updated_at
FROM catalog.sku s
JOIN catalog.manufacturer m USING (manufacturer_bk)
LEFT JOIN catalog.drug_form f USING (form_bk);
