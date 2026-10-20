CREATE SCHEMA catalog;
CREATE EXTENSION btree_gist;

CREATE TABLE catalog.manufacturer (
    manufacturer_bk text PRIMARY KEY,
    manufacturer_name text NOT NULL,
    country text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE catalog.inn (
    inn_bk text PRIMARY KEY,
    inn_name text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE catalog.drug_form (
    form_bk text PRIMARY KEY,
    form_name text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE catalog.sku (
    sku text PRIMARY KEY,
    sku_name text NOT NULL,
    manufacturer_bk text NOT NULL REFERENCES catalog.manufacturer,
    form_bk text REFERENCES catalog.drug_form,
    category text NOT NULL CHECK (category IN ('rx', 'otc', 'supplement', 'device', 'cosmetics')),
    is_rx boolean NOT NULL,
    is_vital boolean NOT NULL DEFAULT false,
    pack_qty numeric(12,3) NOT NULL CHECK (pack_qty > 0),
    is_active boolean NOT NULL DEFAULT true,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((category = 'rx') = is_rx)
);

CREATE TABLE catalog.sku_inn (
    sku text NOT NULL REFERENCES catalog.sku,
    inn_bk text NOT NULL REFERENCES catalog.inn,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (sku, inn_bk)
);

CREATE TABLE catalog.sku_history (
    sku text NOT NULL REFERENCES catalog.sku,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    sku_name text NOT NULL,
    manufacturer_bk text NOT NULL REFERENCES catalog.manufacturer,
    form_bk text REFERENCES catalog.drug_form,
    category text NOT NULL,
    is_rx boolean NOT NULL,
    is_vital boolean NOT NULL,
    pack_qty numeric(12,3) NOT NULL CHECK (pack_qty > 0),
    is_active boolean NOT NULL,
    is_deleted boolean NOT NULL,
    is_current boolean GENERATED ALWAYS AS (valid_to IS NULL) STORED,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (sku, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX sku_history_one_current ON catalog.sku_history (sku) WHERE is_current;

CREATE TABLE catalog.price (
    price_bk text PRIMARY KEY,
    sku text NOT NULL REFERENCES catalog.sku,
    price_scope text NOT NULL CHECK (price_scope IN ('chain', 'region', 'pharmacy')),
    scope_bk text NOT NULL,
    price numeric(14,2) NOT NULL CHECK (price > 0),
    currency text NOT NULL DEFAULT 'RUB' CHECK (currency ~ '^[A-Z]{3}$'),
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    is_current boolean GENERATED ALWAYS AS (valid_to IS NULL) STORED,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (valid_to IS NULL OR valid_to > valid_from),
    CHECK ((price_scope = 'chain' AND scope_bk = 'ALL') OR price_scope <> 'chain'),
    EXCLUDE USING gist (sku WITH =, price_scope WITH =, scope_bk WITH =,
                        tstzrange(valid_from, valid_to, '[)') WITH &&)
);
CREATE UNIQUE INDEX price_one_current ON catalog.price (sku, price_scope, scope_bk) WHERE is_current;
CREATE TRIGGER c_price_payload BEFORE UPDATE ON catalog.price FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('sku', 'price_scope', 'scope_bk', 'price', 'currency', 'valid_from');

CREATE FUNCTION catalog.remember_sku() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.sku_name, NEW.manufacturer_bk, NEW.form_bk, NEW.category, NEW.is_rx,
               NEW.is_vital, NEW.pack_qty, NEW.is_active, NEW.is_deleted)
           IS NOT DISTINCT FROM
           ROW(OLD.sku_name, OLD.manufacturer_bk, OLD.form_bk, OLD.category, OLD.is_rx,
               OLD.is_vital, OLD.pack_qty, OLD.is_active, OLD.is_deleted) THEN
            RETURN NULL;
        END IF;
        UPDATE catalog.sku_history SET valid_to = NEW.updated_at
        WHERE sku = NEW.sku AND is_current;
    END IF;
    INSERT INTO catalog.sku_history
        (sku, valid_from, sku_name, manufacturer_bk, form_bk, category, is_rx, is_vital,
         pack_qty, is_active, is_deleted, created_at, updated_at)
    VALUES (NEW.sku, NEW.updated_at, NEW.sku_name, NEW.manufacturer_bk, NEW.form_bk,
            NEW.category, NEW.is_rx, NEW.is_vital, NEW.pack_qty, NEW.is_active, NEW.is_deleted,
            NEW.created_at, NEW.updated_at);
    RETURN NULL;
END;
$$;
CREATE TRIGGER sku_history AFTER INSERT OR UPDATE ON catalog.sku
    FOR EACH ROW EXECUTE FUNCTION catalog.remember_sku();

CREATE FUNCTION catalog.price_at(item_sku text, region_bk text, pharmacy_bk text, at_time timestamptz)
RETURNS TABLE (price numeric, currency text)
LANGUAGE sql STABLE AS $$
    SELECT p.price, p.currency
    FROM catalog.price p
    WHERE p.sku = item_sku AND p.valid_from <= at_time
      AND (p.valid_to IS NULL OR at_time < p.valid_to)
      AND ((p.price_scope = 'chain' AND p.scope_bk = 'ALL')
        OR (p.price_scope = 'region' AND p.scope_bk = region_bk)
        OR (p.price_scope = 'pharmacy' AND p.scope_bk = pharmacy_bk))
    ORDER BY CASE p.price_scope WHEN 'pharmacy' THEN 3 WHEN 'region' THEN 2 ELSE 1 END DESC
    LIMIT 1;
$$;

CREATE VIEW contract.v_sku AS
SELECT s.sku, s.sku_name,
       (SELECT string_agg(i.inn_name, ' + ' ORDER BY i.inn_name)
        FROM catalog.sku_inn si JOIN catalog.inn i USING (inn_bk)
        WHERE si.sku = s.sku AND NOT si.is_deleted) AS inn_name,
       m.manufacturer_name, f.form_name AS drug_form,
       s.category, s.is_rx, s.is_vital, s.pack_qty,
       s.is_active AND NOT s.is_deleted AS is_active, s.updated_at
FROM catalog.sku s
JOIN catalog.manufacturer m USING (manufacturer_bk)
LEFT JOIN catalog.drug_form f USING (form_bk);

CREATE VIEW contract.v_price AS
SELECT sku, price_scope, scope_bk, price, currency, valid_from, valid_to, is_current, updated_at
FROM catalog.price;

SELECT core.install_guards('catalog');
CREATE PUBLICATION catalog_cdc FOR ALL TABLES;
