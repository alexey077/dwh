CREATE SCHEMA pos;

CREATE TABLE pos.pharmacy (
    pharmacy_bk text PRIMARY KEY,
    pharmacy_name text NOT NULL,
    region text NOT NULL,
    city text NOT NULL,
    address text NOT NULL,
    opened_at date NOT NULL,
    closed_at date,
    is_active boolean NOT NULL DEFAULT true,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (closed_at IS NULL OR closed_at >= opened_at)
);

CREATE TABLE pos.pharmacy_history (
    pharmacy_bk text NOT NULL REFERENCES pos.pharmacy,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    attributes jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (pharmacy_bk, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX pharmacy_history_one_current ON pos.pharmacy_history(pharmacy_bk) WHERE valid_to IS NULL;

CREATE TABLE pos.cashier (
    cashier_bk text PRIMARY KEY,
    cashier_name text NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE pos.cash_register (
    register_bk text PRIMARY KEY,
    pharmacy_bk text NOT NULL REFERENCES pos.pharmacy,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TRIGGER c_register_pharmacy BEFORE UPDATE ON pos.cash_register FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('pharmacy_bk');

CREATE TABLE pos.shift (
    shift_bk text PRIMARY KEY,
    register_bk text NOT NULL REFERENCES pos.cash_register,
    cashier_bk text NOT NULL REFERENCES pos.cashier,
    opened_at timestamptz NOT NULL,
    closed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (closed_at IS NULL OR closed_at > opened_at)
);
CREATE UNIQUE INDEX register_one_open_shift ON pos.shift(register_bk) WHERE closed_at IS NULL;
CREATE TRIGGER c_shift_owner BEFORE UPDATE ON pos.shift FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('register_bk', 'cashier_bk', 'opened_at');

CREATE TABLE pos.prescription (
    prescription_bk text PRIMARY KEY,
    customer_bk text,
    issued_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (expires_at > issued_at)
);

CREATE TABLE pos.batch_reference (
    batch_bk text PRIMARY KEY,
    sku text NOT NULL,
    manufactured_date date NOT NULL,
    expiry_date date NOT NULL,
    received_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (expiry_date > manufactured_date)
);

CREATE TABLE pos.sku_reference (
    sku text NOT NULL,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    sku_name text NOT NULL,
    is_rx boolean NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (sku, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);

CREATE TABLE pos.price_reference (
    price_bk text PRIMARY KEY,
    sku text NOT NULL,
    price_scope text NOT NULL CHECK (price_scope IN ('chain','region','pharmacy')),
    scope_bk text NOT NULL,
    price numeric(14,2) NOT NULL CHECK (price > 0),
    currency text NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE INDEX local_price_lookup ON pos.price_reference(sku, valid_from);

CREATE TABLE pos.receipt (
    receipt_bk text PRIMARY KEY,
    pharmacy_bk text NOT NULL REFERENCES pos.pharmacy,
    customer_bk text,
    cashier_bk text NOT NULL REFERENCES pos.cashier,
    shift_bk text NOT NULL REFERENCES pos.shift,
    receipt_dt timestamptz NOT NULL,
    doc_type text NOT NULL CHECK (doc_type IN ('sale','refund')),
    parent_receipt_bk text REFERENCES pos.receipt,
    total_amount numeric(16,2) NOT NULL CHECK (total_amount >= 0),
    discount_amount numeric(16,2) NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    currency text NOT NULL DEFAULT 'RUB' CHECK (currency ~ '^[A-Z]{3}$'),
    prescription_bk text REFERENCES pos.prescription,
    revision bigint NOT NULL DEFAULT 0,
    check_pending boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((doc_type = 'sale' AND parent_receipt_bk IS NULL)
        OR (doc_type = 'refund' AND parent_receipt_bk IS NOT NULL)),
    CHECK (parent_receipt_bk IS DISTINCT FROM receipt_bk)
);
CREATE INDEX receipt_parent ON pos.receipt(parent_receipt_bk) WHERE parent_receipt_bk IS NOT NULL;
CREATE INDEX receipt_date ON pos.receipt(receipt_dt);
CREATE TRIGGER b_receipt_payload BEFORE UPDATE ON pos.receipt FOR EACH ROW
    EXECUTE FUNCTION core.immutable_key('receipt_bk','pharmacy_bk','cashier_bk','shift_bk',
                                       'receipt_dt','doc_type','parent_receipt_bk','currency');

CREATE TABLE pos.receipt_line (
    receipt_bk text NOT NULL REFERENCES pos.receipt,
    line_no integer NOT NULL CHECK (line_no > 0),
    sku text NOT NULL,
    batch_bk text NOT NULL REFERENCES pos.batch_reference,
    price_bk text NOT NULL REFERENCES pos.price_reference,
    quantity numeric(14,3) NOT NULL CHECK (quantity > 0),
    unit_price numeric(14,2) NOT NULL CHECK (unit_price >= 0),
    line_discount numeric(16,2) NOT NULL DEFAULT 0 CHECK (line_discount >= 0),
    line_amount numeric(16,2) NOT NULL,
    is_rx_snapshot boolean NOT NULL,
    sku_name_snapshot text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (receipt_bk,line_no),
    CHECK (line_discount <= quantity * unit_price),
    CHECK (line_amount = quantity * unit_price - line_discount)
);
CREATE INDEX receipt_line_item ON pos.receipt_line(receipt_bk,sku);

CREATE TABLE pos.payment (
    receipt_bk text NOT NULL REFERENCES pos.receipt,
    payment_no integer NOT NULL CHECK (payment_no > 0),
    payment_method text NOT NULL CHECK (payment_method IN ('cash','card','bonus','certificate')),
    amount numeric(16,2) NOT NULL CHECK (amount >= 0),
    currency text NOT NULL DEFAULT 'RUB' CHECK (currency ~ '^[A-Z]{3}$'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY(receipt_bk,payment_no)
);

CREATE FUNCTION pos.remember_pharmacy() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    attrs jsonb;
BEGIN
    attrs := to_jsonb(NEW) - ARRAY['created_at','updated_at','pharmacy_bk'];
    IF TG_OP = 'UPDATE' THEN
        IF attrs = to_jsonb(OLD) - ARRAY['created_at','updated_at','pharmacy_bk'] THEN
            RETURN NULL;
        END IF;
        UPDATE pos.pharmacy_history SET valid_to = NEW.updated_at
        WHERE pharmacy_bk = NEW.pharmacy_bk AND valid_to IS NULL;
    END IF;
    INSERT INTO pos.pharmacy_history(pharmacy_bk,valid_from,attributes,created_at,updated_at)
    VALUES (NEW.pharmacy_bk,NEW.updated_at,attrs,NEW.created_at,NEW.updated_at);
    RETURN NULL;
END;
$$;
CREATE TRIGGER pharmacy_history AFTER INSERT OR UPDATE ON pos.pharmacy
    FOR EACH ROW EXECUTE FUNCTION pos.remember_pharmacy();

CREATE FUNCTION pos.prepare_receipt() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pos AS $$
DECLARE
    shift_row record;
    sale pos.receipt%ROWTYPE;
BEGIN
    SELECT s.cashier_bk, s.opened_at, s.closed_at, r.pharmacy_bk INTO STRICT shift_row
    FROM pos.shift s JOIN pos.cash_register r USING(register_bk) WHERE s.shift_bk = NEW.shift_bk;
    IF shift_row.pharmacy_bk <> NEW.pharmacy_bk OR shift_row.cashier_bk <> NEW.cashier_bk
       OR NEW.receipt_dt < shift_row.opened_at
       OR (shift_row.closed_at IS NOT NULL AND NEW.receipt_dt >= shift_row.closed_at) THEN
        RAISE EXCEPTION 'Receipt must belong to its register and an open shift';
    END IF;
    IF NEW.doc_type = 'refund' THEN
        UPDATE pos.receipt SET revision = revision + 1
        WHERE receipt_bk = NEW.parent_receipt_bk RETURNING * INTO STRICT sale;
        IF sale.doc_type <> 'sale' OR NEW.receipt_dt < sale.receipt_dt THEN
            RAISE EXCEPTION 'Refund must refer to an earlier sale';
        END IF;
    END IF;
    NEW.check_pending := true;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_prepare_receipt BEFORE INSERT OR UPDATE OF total_amount,discount_amount,prescription_bk,customer_bk
    ON pos.receipt FOR EACH ROW EXECUTE FUNCTION pos.prepare_receipt();

CREATE FUNCTION pos.dirty_document(document_bk text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pos AS $$
DECLARE
    parent_bk text;
BEGIN
    SELECT parent_receipt_bk INTO STRICT parent_bk FROM pos.receipt WHERE receipt_bk = document_bk;
    IF parent_bk IS NOT NULL THEN
        UPDATE pos.receipt SET revision = revision + 1 WHERE receipt_bk = parent_bk;
    END IF;
    UPDATE pos.receipt SET revision = revision + 1, check_pending = true WHERE receipt_bk = document_bk;
END;
$$;
REVOKE ALL ON FUNCTION pos.dirty_document(text) FROM PUBLIC;

CREATE FUNCTION pos.prepare_line() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pos AS $$
DECLARE
    document pos.receipt%ROWTYPE;
    item pos.batch_reference%ROWTYPE;
    sku_version pos.sku_reference%ROWTYPE;
    price_version pos.price_reference%ROWTYPE;
    recipe pos.prescription%ROWTYPE;
    reference_time timestamptz;
    region_bk text;
BEGIN
    PERFORM pos.dirty_document(NEW.receipt_bk);
    SELECT * INTO STRICT document FROM pos.receipt WHERE receipt_bk = NEW.receipt_bk;
    SELECT * INTO STRICT item FROM pos.batch_reference WHERE batch_bk = NEW.batch_bk;
    IF item.sku <> NEW.sku THEN
        RAISE EXCEPTION 'Line SKU does not match the batch';
    END IF;
    IF document.doc_type = 'sale' AND
       ((document.receipt_dt AT TIME ZONE 'UTC')::date > item.expiry_date OR document.receipt_dt < item.received_at) THEN
        RAISE EXCEPTION 'Cannot sell expired or not yet received batch %', NEW.batch_bk;
    END IF;
    IF NEW.is_rx_snapshot AND document.prescription_bk IS NULL THEN
        RAISE EXCEPTION 'Prescription is required for Rx item' USING ERRCODE = '23514';
    END IF;
    reference_time := document.receipt_dt;
    IF document.doc_type = 'refund' THEN
        SELECT receipt_dt INTO reference_time FROM pos.receipt WHERE receipt_bk = document.parent_receipt_bk;
        IF NOT EXISTS (SELECT 1 FROM pos.receipt_line WHERE receipt_bk = document.parent_receipt_bk
            AND sku = NEW.sku AND batch_bk = NEW.batch_bk AND unit_price = NEW.unit_price
            AND price_bk = NEW.price_bk AND is_rx_snapshot = NEW.is_rx_snapshot AND sku_name_snapshot = NEW.sku_name_snapshot) THEN
            RAISE EXCEPTION 'Refund snapshot must match its sale';
        END IF;
    END IF;
    SELECT * INTO sku_version FROM pos.sku_reference
    WHERE sku = NEW.sku AND valid_from <= reference_time AND (valid_to IS NULL OR reference_time < valid_to)
    ORDER BY valid_from DESC LIMIT 1;
    IF NOT FOUND OR sku_version.is_rx IS DISTINCT FROM NEW.is_rx_snapshot
       OR sku_version.sku_name IS DISTINCT FROM NEW.sku_name_snapshot THEN
        RAISE EXCEPTION 'SKU snapshot does not match its effective catalog version';
    END IF;
    IF document.doc_type = 'sale' THEN
        SELECT attributes ->> 'region' INTO region_bk FROM pos.pharmacy_history
        WHERE pharmacy_bk = document.pharmacy_bk AND valid_from <= reference_time
          AND (valid_to IS NULL OR reference_time < valid_to)
        ORDER BY valid_from DESC LIMIT 1;
        SELECT * INTO price_version FROM pos.price_reference p
        WHERE p.sku = NEW.sku AND p.valid_from <= reference_time
          AND (p.valid_to IS NULL OR reference_time < p.valid_to)
          AND ((p.price_scope = 'chain' AND p.scope_bk = 'ALL')
            OR (p.price_scope = 'region' AND p.scope_bk = region_bk)
            OR (p.price_scope = 'pharmacy' AND p.scope_bk = document.pharmacy_bk))
        ORDER BY CASE p.price_scope WHEN 'pharmacy' THEN 3 WHEN 'region' THEN 2 ELSE 1 END DESC LIMIT 1;
        IF NOT FOUND OR price_version.price_bk <> NEW.price_bk OR price_version.price <> NEW.unit_price
           OR price_version.currency <> document.currency THEN
            RAISE EXCEPTION 'Price snapshot does not match the effective scoped price';
        END IF;
        IF NEW.is_rx_snapshot THEN
            SELECT * INTO STRICT recipe FROM pos.prescription WHERE prescription_bk = document.prescription_bk;
            IF document.receipt_dt < recipe.issued_at OR document.receipt_dt >= recipe.expires_at
               OR (recipe.customer_bk IS NOT NULL AND recipe.customer_bk IS DISTINCT FROM document.customer_bk) THEN
                RAISE EXCEPTION 'Prescription is expired or belongs to another customer';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_prepare_line BEFORE INSERT OR UPDATE ON pos.receipt_line
    FOR EACH ROW EXECUTE FUNCTION pos.prepare_line();

CREATE FUNCTION pos.prepare_payment() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pos AS $$
DECLARE
    receipt_currency text;
BEGIN
    PERFORM pos.dirty_document(NEW.receipt_bk);
    SELECT currency INTO STRICT receipt_currency FROM pos.receipt WHERE receipt_bk = NEW.receipt_bk;
    IF receipt_currency <> NEW.currency THEN
        RAISE EXCEPTION 'Payment currency does not match its receipt';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_prepare_payment BEFORE INSERT OR UPDATE ON pos.payment
    FOR EACH ROW EXECUTE FUNCTION pos.prepare_payment();

CREATE FUNCTION pos.check_document() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pos AS $$
DECLARE
    document pos.receipt%ROWTYPE;
    total_lines numeric;
    total_discount numeric;
    total_payments numeric;
    line_count integer;
    payment_count integer;
    original_bk text;
    returned record;
    sold_qty numeric;
    sold_amount numeric;
BEGIN
    SELECT * INTO STRICT document FROM pos.receipt WHERE receipt_bk = NEW.receipt_bk FOR UPDATE;
    IF NOT document.check_pending THEN
        RETURN NULL;
    END IF;
    SELECT count(*), coalesce(sum(line_amount),0), coalesce(sum(line_discount),0)
    INTO line_count,total_lines,total_discount FROM pos.receipt_line WHERE receipt_bk = document.receipt_bk;
    IF line_count = 0 OR total_lines <> document.total_amount OR total_discount <> document.discount_amount THEN
        RAISE EXCEPTION 'I3: receipt % total does not match its lines', document.receipt_bk;
    END IF;
    SELECT count(*), coalesce(sum(amount),0) INTO payment_count,total_payments
    FROM pos.payment WHERE receipt_bk = document.receipt_bk;
    IF payment_count = 0 OR total_payments <> document.total_amount THEN
        RAISE EXCEPTION 'I12: receipt % total does not match its payments', document.receipt_bk;
    END IF;
    IF document.prescription_bk IS NULL AND EXISTS (SELECT 1 FROM pos.receipt_line
        WHERE receipt_bk = document.receipt_bk AND is_rx_snapshot) THEN
        RAISE EXCEPTION 'I10: prescription is required' USING ERRCODE = '23514';
    END IF;
    original_bk := coalesce(document.parent_receipt_bk, document.receipt_bk);
    FOR returned IN
        SELECT l.sku, sum(l.quantity) AS qty, sum(l.line_amount) AS amount
        FROM pos.receipt r JOIN pos.receipt_line l USING(receipt_bk)
        WHERE r.parent_receipt_bk = original_bk GROUP BY l.sku
    LOOP
        SELECT coalesce(sum(quantity),0), coalesce(sum(line_amount),0) INTO sold_qty,sold_amount
        FROM pos.receipt_line WHERE receipt_bk = original_bk AND sku = returned.sku;
        IF returned.qty > sold_qty OR returned.amount > sold_amount THEN
            RAISE EXCEPTION 'I11: refunds exceed original sale % for %', original_bk,returned.sku;
        END IF;
    END LOOP;
    UPDATE pos.receipt SET check_pending = false WHERE receipt_bk = document.receipt_bk;
    RETURN NULL;
END;
$$;
CREATE CONSTRAINT TRIGGER receipt_balanced AFTER INSERT OR UPDATE OF total_amount,discount_amount,prescription_bk,customer_bk
    ON pos.receipt DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pos.check_document();
CREATE CONSTRAINT TRIGGER lines_balanced AFTER INSERT OR UPDATE ON pos.receipt_line
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pos.check_document();
CREATE CONSTRAINT TRIGGER payments_balanced AFTER INSERT OR UPDATE ON pos.payment
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION pos.check_document();

CREATE FUNCTION pos.check_shift_close() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.closed_at IS NOT NULL AND EXISTS (SELECT 1 FROM pos.receipt
        WHERE shift_bk = NEW.shift_bk AND receipt_dt >= NEW.closed_at) THEN
        RAISE EXCEPTION 'Shift cannot close before its last receipt';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_shift_close BEFORE UPDATE OF closed_at ON pos.shift
    FOR EACH ROW EXECUTE FUNCTION pos.check_shift_close();

CREATE VIEW contract.v_pharmacy AS
SELECT pharmacy_bk,pharmacy_name,region,city,address,opened_at,closed_at,
       is_active AND NOT is_deleted AS is_active,updated_at FROM pos.pharmacy;
CREATE VIEW contract.v_receipt AS
SELECT receipt_bk,pharmacy_bk,customer_bk,cashier_bk,shift_bk,receipt_dt,doc_type,parent_receipt_bk,
       total_amount,discount_amount,currency,prescription_bk,updated_at FROM pos.receipt;
CREATE VIEW contract.v_receipt_line AS
SELECT receipt_bk,line_no,sku,batch_bk,quantity,unit_price,line_discount,line_amount,
       is_rx_snapshot,sku_name_snapshot,updated_at FROM pos.receipt_line;
CREATE VIEW contract.v_payment AS
SELECT receipt_bk,payment_no,payment_method,amount,currency,updated_at FROM pos.payment;

SELECT core.install_guards('pos');
CREATE PUBLICATION pos_cdc FOR ALL TABLES;
