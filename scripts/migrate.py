#!/usr/bin/env python3
import argparse
import hashlib
import os
import time
from pathlib import Path

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn, parse_dsn


ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("crm", "catalog", "pos", "wms")


def database_dsn(dsn, name):
    return make_dsn(**(parse_dsn(dsn) | {"dbname": name}))


def create_roles(cursor):
    for name, password in (
        ("app", "app"),
        ("checker", "checker"),
        ("test_writer", "test_writer"),
    ):
        cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
        if not cursor.fetchone():
            cursor.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                    sql.Identifier(name), sql.Literal(password)
                )
            )
    cursor.execute("GRANT pg_monitor TO checker")
    cursor.execute("GRANT app TO test_writer")


def grant_access(cursor, service):
    for schema in (service, "core", "contract"):
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO app").format(sql.Identifier(schema))
        )
    cursor.execute("GRANT USAGE ON SCHEMA contract TO checker")
    cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA contract TO checker, app")
    cursor.execute(
        sql.SQL(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA {} TO app"
        ).format(sql.Identifier(service))
    )
    if service == "wms":
        cursor.execute("REVOKE INSERT, UPDATE, DELETE ON wms.stock FROM app")
    if service == "pos":
        cursor.execute("REVOKE UPDATE ON pos.receipt FROM app")
        cursor.execute(
            "GRANT UPDATE(customer_bk,total_amount,discount_amount,prescription_bk) ON pos.receipt TO app"
        )
        cursor.execute(
            "REVOKE INSERT, UPDATE, DELETE ON pos.batch_reference,pos.sku_reference,pos.price_reference FROM app"
        )
        cursor.execute(
            "GRANT INSERT, UPDATE ON pos.batch_reference,pos.sku_reference,pos.price_reference TO test_writer"
        )


def provision(dsn, services):
    deadline = time.monotonic() + 180
    while True:
        try:
            connection = psycopg2.connect(
                database_dsn(dsn, "postgres"), connect_timeout=3
            )
            connection.autocommit = True
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_is_in_recovery()")
                if cursor.fetchone()[0]:
                    connection.close()
                    raise psycopg2.OperationalError("Waiting for the primary route")
            break
        except psycopg2.OperationalError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            create_roles(cursor)
            for service in services:
                name = f"{service}_service_db"
                cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,))
                if not cursor.fetchone():
                    cursor.execute(
                        sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
                    )
    finally:
        connection.close()


def migrate(dsn, services):
    provision(dsn, services)
    for service in services:
        connection = psycopg2.connect(database_dsn(dsn, f"{service}_service_db"))
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext('hw01-migrate'))")
                cursor.execute("CREATE SCHEMA IF NOT EXISTS core")
                cursor.execute("""CREATE TABLE IF NOT EXISTS core.schema_migration (
                    filename text PRIMARY KEY, checksum text NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                    updated_at timestamptz NOT NULL DEFAULT clock_timestamp())""")
                paths = [
                    ROOT / "migrations/000_common.sql",
                    *sorted((ROOT / "migrations" / service).glob("*.sql")),
                ]
                for path in paths:
                    filename = str(path.relative_to(ROOT))
                    content = path.read_bytes()
                    checksum = hashlib.sha256(content).hexdigest()
                    cursor.execute(
                        "SELECT checksum FROM core.schema_migration WHERE filename = %s",
                        (filename,),
                    )
                    applied = cursor.fetchone()
                    if applied:
                        if applied[0] != checksum:
                            raise RuntimeError(f"Applied migration changed: {filename}")
                        continue
                    cursor.execute(content.decode())
                    cursor.execute(
                        "INSERT INTO core.schema_migration (filename, checksum) VALUES (%s, %s)",
                        (filename, checksum),
                    )
                    print(f"{service}: applied {filename}", flush=True)
                grant_access(cursor, service)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
        ),
    )
    parser.add_argument(
        "--services", nargs="+", choices=SERVICES, default=list(SERVICES)
    )
    args = parser.parse_args()
    migrate(args.dsn, args.services)
