"""Check source-table CDC prerequisites and application access boundaries."""

import os
import re

import psycopg2
from psycopg2.extensions import make_dsn


total = 0
for service in ("crm", "catalog", "pos", "wms"):
    dsn = os.environ.get(f"{service.upper()}_TEST_DSN") or make_dsn(
        os.environ.get(
            "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
        ),
        dbname=f"{service}_service_db",
    )
    with psycopg2.connect(dsn) as connection, connection.cursor() as cursor:
        cursor.execute(
            """SELECT c.oid, n.nspname || '.' || c.relname
               FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
               WHERE c.relkind='r' AND n.nspname IN (%s, 'core')""",
            (service,),
        )
        tables = cursor.fetchall()
        assert tables, service
        for oid, name in tables:
            cursor.execute(
                "SELECT EXISTS (SELECT FROM pg_index WHERE indrelid=%s AND indisprimary)",
                (oid,),
            )
            assert cursor.fetchone()[0], f"{name}: no primary key"
            cursor.execute(
                """SELECT count(*) FROM pg_attribute WHERE attrelid=%s
                   AND attname IN ('created_at','updated_at') AND attnotnull
                   AND atttypid='timestamptz'::regtype""",
                (oid,),
            )
            assert cursor.fetchone()[0] == 2, f"{name}: technical timestamps"
            cursor.execute(
                """SELECT count(*) FROM pg_trigger WHERE tgrelid=%s
                   AND NOT tgisinternal AND tgenabled='O'
                   AND tgname IN ('a_touch','b_immutable','z_no_delete')""",
                (oid,),
            )
            assert cursor.fetchone()[0] == 3, f"{name}: missing guards"
        cursor.execute(
            "SELECT puballtables FROM pg_publication WHERE pubname=%s",
            (f"{service}_cdc",),
        )
        assert cursor.fetchone() == (True,), f"{service}: CDC publication"
        cursor.execute(
            "SELECT viewname, definition FROM pg_views WHERE schemaname='contract'"
        )
        for name, definition in cursor.fetchall():
            assert not re.search(
                r"\b(now|clock_timestamp|current_date|random)\b", definition, re.I
            ), f"{name}: time-dependent contract"
            cursor.execute(
                "SELECT has_table_privilege('checker', %s, 'SELECT')",
                (f"contract.{name}",),
            )
            assert cursor.fetchone()[0], f"{name}: checker access"
        if service == "wms":
            for privilege in ("INSERT", "UPDATE", "DELETE"):
                cursor.execute(
                    "SELECT has_table_privilege('app','wms.stock',%s)", (privilege,)
                )
                assert not cursor.fetchone()[0], f"Stock allows direct {privilege}"
        if service == "pos":
            for role in ("app", "test_writer"):
                cursor.execute(
                    "SELECT has_column_privilege(%s,'pos.receipt','check_pending','UPDATE')",
                    (role,),
                )
                assert not cursor.fetchone()[0], f"{role}: deferred guard bypass"
        total += len(tables)
        print(f"{service}: {len(tables)} source tables, contract access and CDC DDL OK")
print(f"Schema prerequisites passed for {total} tables; physical CDC was not tested")
