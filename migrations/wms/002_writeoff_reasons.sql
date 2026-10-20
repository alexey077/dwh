CREATE TABLE wms.writeoff_detail (
    movement_bk text PRIMARY KEY REFERENCES wms.movement,
    reason text NOT NULL CHECK (reason IN ('supplier_return', 'damaged', 'expired')),
    supplier_bk text REFERENCES wms.supplier,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK ((reason = 'supplier_return') = (supplier_bk IS NOT NULL))
);

CREATE TRIGGER a_touch BEFORE UPDATE ON wms.writeoff_detail
    FOR EACH ROW EXECUTE FUNCTION core.touch_row();
CREATE TRIGGER b_immutable BEFORE UPDATE ON wms.writeoff_detail
    FOR EACH ROW EXECUTE FUNCTION core.immutable_key('movement_bk');
CREATE TRIGGER c_payload BEFORE UPDATE ON wms.writeoff_detail
    FOR EACH ROW EXECUTE FUNCTION core.immutable_key('reason', 'supplier_bk');
CREATE TRIGGER z_no_delete BEFORE DELETE ON wms.writeoff_detail
    FOR EACH ROW EXECUTE FUNCTION core.no_delete();

CREATE FUNCTION wms.check_writeoff_detail() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, wms AS $$
DECLARE
    movement wms.movement%ROWTYPE;
    detail wms.writeoff_detail%ROWTYPE;
    item wms.batch%ROWTYPE;
BEGIN
    SELECT * INTO STRICT movement FROM wms.movement WHERE movement_bk = NEW.movement_bk;
    IF movement.movement_type <> 'writeoff' THEN
        RAISE EXCEPTION 'Writeoff detail must refer to an outgoing writeoff movement';
    END IF;
    SELECT * INTO detail FROM wms.writeoff_detail WHERE movement_bk = NEW.movement_bk;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Writeoff movement requires a reason';
    END IF;
    SELECT * INTO STRICT item FROM wms.batch WHERE batch_bk = movement.batch_bk;
    IF movement.moved_at < item.received_at THEN
        RAISE EXCEPTION 'Cannot dispose of a batch before its receipt';
    END IF;
    IF detail.reason = 'expired'
       AND (movement.moved_at AT TIME ZONE 'UTC')::date <= item.expiry_date THEN
        RAISE EXCEPTION 'Expired writeoff must happen after the expiry date';
    END IF;
    IF detail.reason = 'supplier_return' AND NOT EXISTS (
        SELECT 1 FROM wms.movement incoming
        JOIN wms.purchase purchase ON purchase.purchase_bk = incoming.purchase_bk
        WHERE incoming.batch_bk = movement.batch_bk
          AND incoming.movement_type = 'receipt'
          AND purchase.supplier_bk = detail.supplier_bk
          AND incoming.moved_at <= movement.moved_at
    ) THEN
        RAISE EXCEPTION 'Supplier return must refer to a supplier of this batch';
    END IF;
    RETURN NULL;
END;
$$;

CREATE CONSTRAINT TRIGGER writeoff_requires_detail AFTER INSERT ON wms.movement
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    WHEN (NEW.movement_type = 'writeoff')
    EXECUTE FUNCTION wms.check_writeoff_detail();
CREATE CONSTRAINT TRIGGER writeoff_detail_valid AFTER INSERT ON wms.writeoff_detail
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW
    EXECUTE FUNCTION wms.check_writeoff_detail();
