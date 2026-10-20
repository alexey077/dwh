CREATE INDEX consent_customer_updated ON crm.consent(customer_bk, updated_at DESC);

CREATE OR REPLACE VIEW contract.v_customer AS
SELECT c.customer_bk, c.birth_year, c.sex, c.city, c.region,
       c.level_bk AS loyalty_level,
       EXISTS (SELECT 1 FROM crm.consent s WHERE s.customer_bk = c.customer_bk
               AND s.consent_type = 'marketing' AND s.revoked_at IS NULL) AS marketing_opt_in,
       c.registered_at,
       greatest(c.updated_at, coalesce((SELECT max(s.updated_at) FROM crm.consent s
                                       WHERE s.customer_bk = c.customer_bk), c.updated_at)) AS updated_at
FROM crm.customer c WHERE NOT c.is_deleted;
