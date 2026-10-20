import os

import psycopg2


dsn = os.environ["CRM_TEST_DSN"]
connection = psycopg2.connect(dsn)
try:
    with connection.cursor() as cursor:
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.execute(
            "INSERT INTO crm.loyalty_level VALUES ('TEST-BASIC', 'Basic', 0, false, DEFAULT, DEFAULT)"
        )
        cursor.execute("""INSERT INTO crm.customer (customer_bk, full_name, city, level_bk, registered_at)
                          VALUES ('TEST-CUSTOMER', 'Test Name', 'Moscow', 'TEST-BASIC', '2026-01-01Z')""")
        cursor.execute("""INSERT INTO crm.contact (contact_bk, customer_bk, contact_type, contact_value)
                          VALUES ('TEST-CONTACT', 'TEST-CUSTOMER', 'email', 'test@example.invalid')""")
        cursor.execute("""INSERT INTO crm.loyalty_card (card_bk, customer_bk, issued_at, status)
                          VALUES ('TEST-CARD', 'TEST-CUSTOMER', '2026-01-01Z', 'active')""")
        cursor.execute(
            "SELECT updated_at FROM crm.customer WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        before = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE crm.customer SET city = 'Kazan' WHERE customer_bk = 'TEST-CUSTOMER' RETURNING updated_at"
        )
        assert cursor.fetchone()[0] > before
        cursor.execute(
            "SELECT count(*) FROM crm.customer_history WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        assert cursor.fetchone()[0] == 2
        cursor.execute("SAVEPOINT duplicate_card")
        try:
            cursor.execute("""INSERT INTO crm.loyalty_card (card_bk, customer_bk, issued_at, status)
                              VALUES ('TEST-CARD-2', 'TEST-CUSTOMER', '2026-01-01Z', 'active')""")
            raise AssertionError("Second active card accepted")
        except psycopg2.errors.UniqueViolation:
            cursor.execute("ROLLBACK TO SAVEPOINT duplicate_card")
        cursor.execute(
            "UPDATE crm.customer SET is_deleted = true WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        cursor.execute(
            "SELECT count(*) FROM contract.v_customer WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT count(*) FROM contract.v_loyalty_card WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        assert cursor.fetchone()[0] == 0
        cursor.execute(
            "SELECT count(*) FROM crm.customer WHERE customer_bk = 'TEST-CUSTOMER' AND full_name IS NULL"
        )
        assert cursor.fetchone()[0] == 1
        cursor.execute(
            "SELECT bool_and(contact_value IS NULL) FROM crm.contact WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        assert cursor.fetchone()[0] is True
        cursor.execute(
            "SELECT bool_and(attributes = '{}') FROM crm.customer_history WHERE customer_bk = 'TEST-CUSTOMER'"
        )
        assert cursor.fetchone()[0] is True
    print("CRM: history, updated_at, active-card uniqueness and anonymization passed")
finally:
    connection.rollback()
    connection.close()
