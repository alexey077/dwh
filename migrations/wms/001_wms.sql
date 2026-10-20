CREATE SCHEMA wms;

CREATE TABLE wms.supplier (
    supplier_bk text PRIMARY KEY,
    supplier_name text NOT NULL,
    country text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE wms.distribution_center (
    dc_bk text PRIMARY KEY,
    dc_name text NOT NULL,
    region text NOT NULL,
    city text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE wms.location (
    location_type text NOT NULL CHECK (location_type IN ('dc', 'pharmacy')),
    location_bk text NOT NULL,
    dc_bk text REFERENCES wms.distribution_center,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (location_type, location_bk),
    CHECK (((location_type = 'dc' AND dc_bk = location_bk)
        OR (location_type = 'pharmacy' AND dc_bk IS NULL)) IS TRUE)
);

CREATE TABLE wms.batch (
    batch_bk text PRIMARY KEY,
    sku text NOT NULL,
    series_no text NOT NULL,
    manufactured_date date NOT NULL,
    expiry_date date NOT NULL,
    received_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    UNIQUE (sku, series_no),
    CHECK (expiry_date > manufactured_date),
    CHECK ((received_at AT TIME ZONE 'UTC')::date BETWEEN manufactured_date AND expiry_date)
);
CREATE TRIGGER c_batch_payload BEFORE UPDATE ON wms.batch FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('sku', 'series_no', 'manufactured_date', 'expiry_date', 'received_at');

CREATE TABLE wms.purchase (
    purchase_bk text PRIMARY KEY,
    supplier_bk text NOT NULL REFERENCES wms.supplier,
    dc_bk text NOT NULL REFERENCES wms.distribution_center,
    ordered_at timestamptz NOT NULL,
    expected_at timestamptz NOT NULL,
    currency text NOT NULL DEFAULT 'RUB' CHECK (currency ~ '^[A-Z]{3}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (expected_at >= ordered_at)
);
CREATE TRIGGER c_purchase_payload BEFORE UPDATE ON wms.purchase FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('supplier_bk', 'dc_bk', 'ordered_at', 'currency');

CREATE TABLE wms.purchase_line (
    purchase_bk text NOT NULL REFERENCES wms.purchase,
    line_no integer NOT NULL CHECK (line_no > 0),
    sku text NOT NULL,
    batch_bk text REFERENCES wms.batch,
    received_at timestamptz,
    quantity numeric(14,3) NOT NULL CHECK (quantity > 0),
    unit_cost numeric(14,2) NOT NULL CHECK (unit_cost >= 0),
    line_cost numeric(16,2) NOT NULL,
    revision bigint NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (purchase_bk, line_no),
    CHECK (line_cost = quantity * unit_cost),
    CHECK ((received_at IS NOT NULL) = (batch_bk IS NOT NULL))
);

CREATE TABLE wms.movement (
    movement_bk text PRIMARY KEY,
    batch_bk text NOT NULL REFERENCES wms.batch,
    movement_type text NOT NULL CHECK (movement_type IN ('receipt', 'transfer', 'sale_writeoff', 'return', 'writeoff')),
    src_type text CHECK (src_type IN ('dc', 'pharmacy', 'supplier')),
    src_bk text,
    dst_type text CHECK (dst_type IN ('dc', 'pharmacy', 'customer')),
    dst_bk text,
    qty numeric(14,3) NOT NULL CHECK (qty > 0),
    dispatched_at timestamptz,
    moved_at timestamptz NOT NULL,
    purchase_bk text,
    purchase_line_no integer,
    external_doc_bk text,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (purchase_bk, purchase_line_no) REFERENCES wms.purchase_line,
    CHECK ((src_type IS NULL) = (src_bk IS NULL)),
    CHECK ((dst_type IS NULL) = (dst_bk IS NULL)),
    CHECK ((purchase_bk IS NULL) = (purchase_line_no IS NULL)),
    CHECK (src_type IS NOT NULL OR dst_type IS NOT NULL),
    CHECK (src_type IS DISTINCT FROM dst_type OR src_bk IS DISTINCT FROM dst_bk),
    CHECK (dispatched_at IS NULL OR dispatched_at <= moved_at),
    CHECK (((movement_type = 'receipt' AND dst_type = 'dc' AND purchase_bk IS NOT NULL)
        OR (movement_type = 'transfer' AND src_type IN ('dc', 'pharmacy') AND dst_type IN ('dc', 'pharmacy'))
        OR (movement_type = 'sale_writeoff' AND src_type = 'pharmacy' AND dst_type = 'customer' AND external_doc_bk IS NOT NULL)
        OR (movement_type = 'return' AND src_type IS NULL AND dst_type = 'pharmacy' AND external_doc_bk IS NOT NULL)
        OR (movement_type = 'writeoff' AND src_type IN ('dc', 'pharmacy') AND dst_type IS NULL)) IS TRUE)
);
CREATE INDEX movement_purchase ON wms.movement (purchase_bk, purchase_line_no) WHERE purchase_bk IS NOT NULL;
CREATE INDEX movement_batch ON wms.movement (batch_bk, moved_at);

CREATE TABLE wms.stock (
    location_type text NOT NULL,
    location_bk text NOT NULL,
    batch_bk text NOT NULL REFERENCES wms.batch,
    qty_on_hand numeric(14,3) NOT NULL CHECK (qty_on_hand >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (location_type, location_bk, batch_bk),
    FOREIGN KEY (location_type, location_bk) REFERENCES wms.location
);

CREATE FUNCTION wms.check_purchase_line() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    item wms.batch%ROWTYPE;
    ordered timestamptz;
BEGIN
    SELECT ordered_at INTO STRICT ordered FROM wms.purchase WHERE purchase_bk = NEW.purchase_bk;
    IF NEW.batch_bk IS NOT NULL THEN
        SELECT * INTO STRICT item FROM wms.batch WHERE batch_bk = NEW.batch_bk;
        IF item.sku <> NEW.sku OR NEW.received_at < ordered THEN
            RAISE EXCEPTION 'Purchase line has an inconsistent batch or receipt time';
        END IF;
        IF (NEW.received_at AT TIME ZONE 'UTC')::date > item.expiry_date THEN
            RAISE EXCEPTION 'Cannot receive expired batch %', NEW.batch_bk;
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' AND OLD.batch_bk IS NOT NULL
       AND ROW(NEW.sku, NEW.batch_bk, NEW.received_at, NEW.quantity, NEW.unit_cost, NEW.line_cost)
           IS DISTINCT FROM ROW(OLD.sku, OLD.batch_bk, OLD.received_at, OLD.quantity, OLD.unit_cost, OLD.line_cost) THEN
        RAISE EXCEPTION 'Received purchase line is immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_purchase_line BEFORE INSERT OR UPDATE ON wms.purchase_line
    FOR EACH ROW EXECUTE FUNCTION wms.check_purchase_line();

CREATE FUNCTION wms.apply_movement() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, wms AS $$
DECLARE
    item wms.batch%ROWTYPE;
    line wms.purchase_line%ROWTYPE;
    order_row wms.purchase%ROWTYPE;
    location_row record;
    already_received numeric;
BEGIN
    SELECT * INTO STRICT item FROM wms.batch WHERE batch_bk = NEW.batch_bk;
    IF NEW.movement_type = 'receipt' THEN
        IF (NEW.moved_at AT TIME ZONE 'UTC')::date > item.expiry_date THEN
            RAISE EXCEPTION 'Cannot receive expired batch %', NEW.batch_bk;
        END IF;
        UPDATE wms.purchase_line SET revision = revision + 1
        WHERE purchase_bk = NEW.purchase_bk AND line_no = NEW.purchase_line_no
        RETURNING * INTO STRICT line;
        SELECT * INTO STRICT order_row FROM wms.purchase WHERE purchase_bk = NEW.purchase_bk;
        IF line.batch_bk IS DISTINCT FROM NEW.batch_bk OR order_row.dc_bk <> NEW.dst_bk
           OR NEW.src_type IS DISTINCT FROM 'supplier' OR order_row.supplier_bk IS DISTINCT FROM NEW.src_bk THEN
            RAISE EXCEPTION 'Receipt movement does not match its purchase';
        END IF;
        SELECT coalesce(sum(qty), 0) INTO already_received FROM wms.movement
        WHERE purchase_bk = NEW.purchase_bk AND purchase_line_no = NEW.purchase_line_no;
        IF already_received > line.quantity THEN
            RAISE EXCEPTION 'Received quantity exceeds the purchase line';
        END IF;
    END IF;

    FOR location_row IN
        SELECT kind, bk FROM (VALUES (NEW.src_type, NEW.src_bk), (NEW.dst_type, NEW.dst_bk)) AS q(kind, bk)
        WHERE kind IN ('dc', 'pharmacy') ORDER BY kind, bk
    LOOP
        INSERT INTO wms.stock (location_type, location_bk, batch_bk, qty_on_hand, created_at, updated_at)
        VALUES (location_row.kind, location_row.bk, NEW.batch_bk, 0, NEW.moved_at, NEW.moved_at)
        ON CONFLICT DO NOTHING;
        PERFORM 1 FROM wms.stock WHERE location_type = location_row.kind
          AND location_bk = location_row.bk AND batch_bk = NEW.batch_bk FOR UPDATE;
    END LOOP;
    IF NEW.src_type IN ('dc', 'pharmacy') THEN
        UPDATE wms.stock SET qty_on_hand = qty_on_hand - NEW.qty
        WHERE location_type = NEW.src_type AND location_bk = NEW.src_bk AND batch_bk = NEW.batch_bk;
    END IF;
    IF NEW.dst_type IN ('dc', 'pharmacy') THEN
        UPDATE wms.stock SET qty_on_hand = qty_on_hand + NEW.qty
        WHERE location_type = NEW.dst_type AND location_bk = NEW.dst_bk AND batch_bk = NEW.batch_bk;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER movement_stock AFTER INSERT ON wms.movement
    FOR EACH ROW EXECUTE FUNCTION wms.apply_movement();

CREATE FUNCTION wms.append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Movement ledger is append-only; add a compensating movement';
END;
$$;
CREATE TRIGGER c_movement_append_only BEFORE UPDATE ON wms.movement
    FOR EACH ROW EXECUTE FUNCTION wms.append_only();

CREATE VIEW contract.v_supplier AS
SELECT supplier_bk, supplier_name, country, is_active AND NOT is_deleted AS is_active, updated_at FROM wms.supplier;
CREATE VIEW contract.v_distribution_center AS
SELECT dc_bk, dc_name, region, city, is_active AND NOT is_deleted AS is_active, updated_at FROM wms.distribution_center;
CREATE VIEW contract.v_batch AS
SELECT batch_bk, sku, series_no, manufactured_date, expiry_date, received_at, updated_at FROM wms.batch;
CREATE VIEW contract.v_purchase_line AS
SELECT l.purchase_bk, l.line_no, p.supplier_bk, p.dc_bk, l.sku, l.batch_bk, p.ordered_at, l.received_at,
       l.quantity, l.unit_cost, l.line_cost, p.currency, greatest(l.updated_at, p.updated_at) AS updated_at
FROM wms.purchase_line l JOIN wms.purchase p USING (purchase_bk);
CREATE VIEW contract.v_movement AS
SELECT m.movement_bk, m.batch_bk, b.sku, m.movement_type, m.src_type, m.src_bk, m.dst_type, m.dst_bk,
       m.qty, m.dispatched_at, m.moved_at, m.updated_at
FROM wms.movement m JOIN wms.batch b USING (batch_bk);
CREATE VIEW contract.v_stock AS
SELECT s.location_type, s.location_bk, b.sku, s.batch_bk, s.qty_on_hand, s.updated_at
FROM wms.stock s JOIN wms.batch b USING (batch_bk);

SELECT core.install_guards('wms');
CREATE PUBLICATION wms_cdc FOR ALL TABLES;
