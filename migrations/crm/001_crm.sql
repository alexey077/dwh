CREATE SCHEMA crm;

CREATE TABLE crm.loyalty_level (
    level_bk text PRIMARY KEY,
    level_name text NOT NULL,
    threshold_amount numeric(14,2) NOT NULL CHECK (threshold_amount >= 0),
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE crm.customer (
    customer_bk text PRIMARY KEY,
    full_name text,
    birth_year integer CHECK (birth_year BETWEEN 1900 AND 2100),
    sex text CHECK (sex IN ('M', 'F')),
    city text,
    region text,
    level_bk text REFERENCES crm.loyalty_level,
    registered_at timestamptz NOT NULL,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE crm.customer_history (
    customer_bk text NOT NULL REFERENCES crm.customer,
    valid_from timestamptz NOT NULL,
    valid_to timestamptz,
    attributes jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (customer_bk, valid_from),
    CHECK (valid_to IS NULL OR valid_to > valid_from)
);
CREATE UNIQUE INDEX customer_one_current ON crm.customer_history (customer_bk)
    WHERE valid_to IS NULL;

CREATE TABLE crm.contact (
    contact_bk text PRIMARY KEY,
    customer_bk text NOT NULL REFERENCES crm.customer,
    contact_type text NOT NULL CHECK (contact_type IN ('phone', 'email')),
    contact_value text,
    is_deleted boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (NOT is_deleted OR contact_value IS NULL)
);
CREATE INDEX contact_customer ON crm.contact (customer_bk);

CREATE TABLE crm.consent (
    consent_bk text PRIMARY KEY,
    customer_bk text NOT NULL REFERENCES crm.customer,
    consent_type text NOT NULL CHECK (consent_type IN ('personal_data', 'marketing')),
    granted_at timestamptz NOT NULL,
    revoked_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (revoked_at IS NULL OR revoked_at >= granted_at)
);
CREATE UNIQUE INDEX consent_one_active ON crm.consent (customer_bk, consent_type)
    WHERE revoked_at IS NULL;

CREATE TABLE crm.loyalty_card (
    card_bk text PRIMARY KEY,
    customer_bk text NOT NULL REFERENCES crm.customer,
    issued_at timestamptz NOT NULL,
    closed_at timestamptz,
    status text NOT NULL CHECK (status IN ('active', 'blocked', 'closed')),
    bonus_balance numeric(14,2) NOT NULL DEFAULT 0 CHECK (bonus_balance >= 0),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (closed_at IS NULL OR (closed_at >= issued_at AND status = 'closed')),
    CHECK (status <> 'closed' OR closed_at IS NOT NULL)
);
CREATE UNIQUE INDEX card_one_active ON crm.loyalty_card (customer_bk) WHERE status = 'active';

CREATE TABLE crm.privacy_event (
    event_bk text PRIMARY KEY,
    customer_bk text NOT NULL REFERENCES crm.customer,
    event_type text NOT NULL CHECK (event_type = 'anonymized'),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE FUNCTION crm.anonymize_customer() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.is_deleted AND NOT NEW.is_deleted THEN
        RAISE EXCEPTION 'Anonymization cannot be reversed';
    END IF;
    IF NEW.is_deleted THEN
        NEW.full_name := NULL;
        NEW.birth_year := NULL;
        NEW.sex := NULL;
        NEW.city := NULL;
        NEW.region := NULL;
        NEW.level_bk := NULL;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_anonymize BEFORE UPDATE ON crm.customer
    FOR EACH ROW EXECUTE FUNCTION crm.anonymize_customer();

CREATE FUNCTION crm.remember_customer() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    attrs jsonb;
BEGIN
    attrs := jsonb_build_object('birth_year', NEW.birth_year, 'sex', NEW.sex,
                               'city', NEW.city, 'region', NEW.region, 'level_bk', NEW.level_bk);
    IF TG_OP = 'UPDATE' THEN
        IF NEW.is_deleted AND NOT OLD.is_deleted THEN
            UPDATE crm.contact SET contact_value = NULL, is_deleted = true
            WHERE customer_bk = NEW.customer_bk;
            UPDATE crm.consent SET revoked_at = greatest(NEW.updated_at, granted_at)
            WHERE customer_bk = NEW.customer_bk AND revoked_at IS NULL;
            UPDATE crm.loyalty_card SET status = 'closed', closed_at = greatest(NEW.updated_at, issued_at)
            WHERE customer_bk = NEW.customer_bk AND closed_at IS NULL;
            UPDATE crm.customer_history SET attributes = '{}'
            WHERE customer_bk = NEW.customer_bk;
            INSERT INTO crm.privacy_event (event_bk, customer_bk, event_type)
            VALUES ('PRIVACY-' || NEW.customer_bk, NEW.customer_bk, 'anonymized');
        ELSIF attrs = jsonb_build_object('birth_year', OLD.birth_year, 'sex', OLD.sex,
                                        'city', OLD.city, 'region', OLD.region, 'level_bk', OLD.level_bk) THEN
            RETURN NULL;
        END IF;
        UPDATE crm.customer_history SET valid_to = NEW.updated_at
        WHERE customer_bk = NEW.customer_bk AND valid_to IS NULL;
    END IF;
    INSERT INTO crm.customer_history (customer_bk, valid_from, attributes, created_at, updated_at)
    VALUES (NEW.customer_bk, NEW.updated_at, CASE WHEN NEW.is_deleted THEN '{}'::jsonb ELSE attrs END,
            NEW.created_at, NEW.updated_at);
    RETURN NULL;
END;
$$;
CREATE TRIGGER customer_history AFTER INSERT OR UPDATE ON crm.customer
    FOR EACH ROW EXECUTE FUNCTION crm.remember_customer();

CREATE FUNCTION crm.guard_contact() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM crm.customer WHERE customer_bk = NEW.customer_bk AND NOT is_deleted FOR UPDATE;
    IF NOT FOUND THEN
        NEW.contact_value := NULL;
        NEW.is_deleted := true;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER c_contact_owner BEFORE INSERT OR UPDATE ON crm.contact
    FOR EACH ROW EXECUTE FUNCTION crm.guard_contact();

CREATE VIEW contract.v_customer AS
SELECT c.customer_bk, c.birth_year, c.sex, c.city, c.region,
       c.level_bk AS loyalty_level,
       EXISTS (SELECT 1 FROM crm.consent s WHERE s.customer_bk = c.customer_bk
               AND s.consent_type = 'marketing' AND s.revoked_at IS NULL) AS marketing_opt_in,
       c.registered_at, c.updated_at
FROM crm.customer c WHERE NOT c.is_deleted;

CREATE VIEW contract.v_loyalty_card AS
SELECT l.card_bk, l.customer_bk, l.issued_at, l.closed_at, l.status, l.bonus_balance, l.updated_at
FROM crm.loyalty_card l
JOIN crm.customer c USING (customer_bk)
WHERE NOT c.is_deleted;

SELECT core.install_guards('crm');
CREATE PUBLICATION crm_cdc FOR ALL TABLES;
