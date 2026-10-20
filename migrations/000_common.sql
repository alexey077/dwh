CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS contract;

CREATE TABLE IF NOT EXISTS core.schema_migration (
    filename text PRIMARY KEY,
    checksum text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE core.seed_run (
    batch_bk text PRIMARY KEY,
    seed bigint NOT NULL,
    receipt_count integer NOT NULL CHECK (receipt_count >= 0),
    reference_month date NOT NULL,
    parameters jsonb NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION core.touch_row() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.created_at := OLD.created_at;
    NEW.updated_at := greatest(clock_timestamp(), OLD.updated_at + interval '1 microsecond');
    RETURN NEW;
END;
$$;

CREATE FUNCTION core.immutable_key() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    column_name text;
BEGIN
    FOREACH column_name IN ARRAY TG_ARGV LOOP
        IF to_jsonb(NEW) -> column_name IS DISTINCT FROM to_jsonb(OLD) -> column_name THEN
            RAISE EXCEPTION 'Business key %.% is immutable', TG_TABLE_NAME, column_name;
        END IF;
    END LOOP;
    RETURN NEW;
END;
$$;

CREATE FUNCTION core.no_delete() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Physical deletion from % is forbidden; use a state change', TG_TABLE_NAME;
END;
$$;

CREATE FUNCTION core.install_guards(service_schema text) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    item record;
    keys text;
BEGIN
    FOR item IN
        SELECT n.nspname, c.relname, c.oid
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r' AND n.nspname IN (service_schema, 'core')
    LOOP
        SELECT string_agg(quote_literal(a.attname), ', ' ORDER BY k.ordinality)
        INTO keys
        FROM pg_index i
        CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality)
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
        WHERE i.indrelid = item.oid AND i.indisprimary;

        EXECUTE format('CREATE TRIGGER a_touch BEFORE UPDATE ON %I.%I
                        FOR EACH ROW EXECUTE FUNCTION core.touch_row()', item.nspname, item.relname);
        IF keys IS NOT NULL THEN
            EXECUTE format('CREATE TRIGGER b_immutable BEFORE UPDATE ON %I.%I
                            FOR EACH ROW EXECUTE FUNCTION core.immutable_key(%s)',
                            item.nspname, item.relname, keys);
        END IF;
        EXECUTE format('CREATE TRIGGER z_no_delete BEFORE DELETE ON %I.%I
                        FOR EACH ROW EXECUTE FUNCTION core.no_delete()', item.nspname, item.relname);
    END LOOP;
END;
$$;
