SET LOCAL ROLE test_writer;
INSERT INTO crm.customer (customer_bk, full_name, city, registered_at)
VALUES ('T-P2-CUSTOMER', 'Тестовый клиент', 'Москва', '2025-01-01Z');
INSERT INTO crm.contact (contact_bk, customer_bk, contact_type, contact_value)
VALUES ('T-P2-CONTACT', 'T-P2-CUSTOMER', 'email', 'test@example.invalid');
UPDATE crm.customer SET is_deleted = true WHERE customer_bk = 'T-P2-CUSTOMER';
SELECT
    NOT EXISTS (SELECT 1 FROM contract.v_customer WHERE customer_bk = 'T-P2-CUSTOMER')
    AND EXISTS (SELECT 1 FROM crm.customer WHERE customer_bk = 'T-P2-CUSTOMER' AND is_deleted AND full_name IS NULL)
    AND EXISTS (SELECT 1 FROM crm.contact WHERE contact_bk = 'T-P2-CONTACT' AND contact_value IS NULL AND is_deleted)
    AND NOT EXISTS (SELECT 1 FROM crm.customer_history WHERE customer_bk = 'T-P2-CUSTOMER' AND attributes <> '{}')
    AS ok;
