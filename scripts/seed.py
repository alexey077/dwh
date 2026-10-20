#!/usr/bin/env python3
import argparse
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import hashlib
from itertools import accumulate
import json
import os
import random
import re

import psycopg2
from psycopg2 import sql
from psycopg2.extras import Json, execute_values

from migrate import database_dsn


SERVICES = ("crm", "catalog", "wms", "pos")
UTC = timezone.utc
CITIES = (
    "Москва",
    "Санкт-Петербург",
    "Казань",
    "Новосибирск",
    "Екатеринбург",
    "Самара",
    "Нижний Новгород",
    "Пермь",
    "Омск",
    "Уфа",
    "Краснодар",
    "Воронеж",
)
INNS = (
    "Амоксициллин",
    "Метформин",
    "Парацетамол",
    "Ибупрофен",
    "Лоратадин",
    "Аскорбиновая кислота",
    "Дротаверин",
    "Панкреатин",
    "Омепразол",
    "Ацетилсалициловая кислота",
)


def amount(cents):
    return Decimal(cents) / 100


def insert_rows(cursor, table, columns, rows, suffix=""):
    rows = list(rows)
    if not rows:
        return
    statement = sql.SQL("INSERT INTO {} ({}) VALUES %s {}").format(
        sql.Identifier(*table.split(".")),
        sql.SQL(",").join(map(sql.Identifier, columns)),
        sql.SQL(suffix),
    )
    execute_values(cursor, statement.as_string(cursor), rows, page_size=500)


class Loader:
    def __init__(self, base_dsn):
        self.connections = {}
        for service in SERVICES:
            dsn = os.environ.get(f"ADMIN_DSN_{service.upper()}") or database_dsn(
                base_dsn, f"{service}_service_db"
            )
            connection = psycopg2.connect(
                dsn, connect_timeout=15, application_name="hw01_seed"
            )
            with connection.cursor() as cursor:
                cursor.execute("SET TIME ZONE 'UTC'")
            connection.commit()
            self.connections[service] = connection

    def query(self, service, statement, params=None):
        with self.connections[service].cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall()

    def step(self, service, batch, seed, count, month, parameters, work):
        connection = self.connections[service]
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT seed,receipt_count,reference_month,parameters FROM core.seed_run WHERE batch_bk=%s",
                    (batch,),
                )
                previous = cursor.fetchone()
                if previous:
                    if previous != (seed, count, month, parameters):
                        raise ValueError(
                            f"Batch {batch} already has different parameters in {service}"
                        )
                    connection.rollback()
                    print(f"{service}: {batch} already loaded", flush=True)
                    return False
                work(cursor)
                cursor.execute(
                    """INSERT INTO core.seed_run(batch_bk,seed,receipt_count,reference_month,parameters)
                                  VALUES (%s,%s,%s,%s,%s)""",
                    (batch, seed, count, month, Json(parameters)),
                )
            connection.commit()
            print(f"{service}: {batch} committed", flush=True)
            return True
        except Exception:
            connection.rollback()
            raise

    def reference_month(self, requested):
        found = set()
        for service in SERVICES:
            rows = self.query(
                service,
                "SELECT reference_month FROM core.seed_run WHERE batch_bk='FOUNDATION'",
            )
            found.update(row[0] for row in rows)
        if len(found) > 1:
            raise RuntimeError("Services contain different reference months")
        if found:
            month = found.pop()
            if requested and requested != month:
                raise ValueError("Reference month cannot change within a dataset")
            return month
        return requested or date.today().replace(day=1)

    def close(self):
        for connection in self.connections.values():
            connection.close()


class Foundation:
    def __init__(self, month):
        self.month = month
        self.anchor = datetime.combine(month, time(), UTC)
        self.start = self.anchor - timedelta(days=365)
        self.current_from = self.anchor - timedelta(days=120)
        self.pharmacies = [
            (
                f"PH-{i + 1:04d}",
                f"Аптека 108 №{i + 1}",
                f"REG-{i % 12 + 1:02d}",
                CITIES[i % 12],
                f"Аптечная улица, {i + 1}",
                date(2020, 1, 1),
                self.start,
                self.start,
            )
            for i in range(36)
        ]

    def sku(self, index, old=False):
        category = (
            "rx",
            "rx",
            "otc",
            "otc",
            "otc",
            "supplement",
            "supplement",
            "device",
            "cosmetics",
            "cosmetics",
        )[index % 10]
        is_rx = category == "rx"
        if old and index >= 588 and is_rx:
            category, is_rx = "otc", False
        if category in ("rx", "otc"):
            title = (
                f"{INNS[index % 10]} {50 + (index % 4) * 50} мг, упаковка №{index + 1}"
            )
        else:
            title = {
                "supplement": "Витаминный комплекс",
                "device": "Медицинское изделие",
                "cosmetics": "Средство ухода",
            }[category] + f" №{index + 1}"
        if old and (index % 19 == 0 or index >= 588):
            title += " — прежняя упаковка"
        return (
            f"SKU-{index + 1:06d}",
            title,
            f"MFG-{index % 24 + 1:03d}",
            f"FORM-{index % 4 + 1}" if category in ("rx", "otc") else None,
            category,
            is_rx,
            index % 7 == 0,
            Decimal(10 * (index % 3 + 1)),
            True,
            False,
        )

    def batch(self, index, slot):
        received = (
            self.start
            - timedelta(days=20 + (index * 3 + slot) % 20)
            + timedelta(hours=10)
        )
        return (
            f"BATCH-{self.month:%Y%m}-{index + 1:06d}-{slot + 1}",
            f"SKU-{index + 1:06d}",
            f"SER-{self.month:%Y%m}-{index + 1:06d}-{slot + 1}",
            received.date() - timedelta(days=60),
            received.date() + timedelta(days=1095),
            received,
            received,
            received,
        )

    def load_crm(self, cursor):
        insert_rows(
            cursor,
            "crm.loyalty_level",
            ("level_bk", "level_name", "threshold_amount"),
            [
                ("BASE", "Базовый", 0),
                ("SILVER", "Серебряный", 10000),
                ("GOLD", "Золотой", 50000),
            ],
        )
        customers, histories, contacts, cards, consents = [], [], [], [], []
        for i in range(2400):
            customer = f"CUSTOMER-{i + 1:06d}"
            registered = self.start - timedelta(days=300 + i % 200)
            current = self.start + timedelta(days=80 + i % 100)
            level = ("BASE", "SILVER", "GOLD")[i % 3]
            city, region = CITIES[i % 12], f"REG-{i % 12 + 1:02d}"
            customers.append(
                (
                    customer,
                    f"Покупатель {i + 1:06d}",
                    1955 + i % 50,
                    "M" if i % 2 else "F",
                    city,
                    region,
                    level,
                    registered,
                    registered,
                    current,
                )
            )
            histories.append(
                (
                    customer,
                    registered,
                    current,
                    Json(
                        {
                            "birth_year": 1955 + i % 50,
                            "sex": "M" if i % 2 else "F",
                            "city": city,
                            "region": region,
                            "level_bk": "BASE",
                        }
                    ),
                    registered,
                    registered,
                )
            )
            contacts.append(
                (
                    f"CONTACT-{i + 1:06d}",
                    customer,
                    "email",
                    f"customer{i + 1}@example.invalid",
                    registered,
                    registered,
                )
            )
            consents.append(
                (
                    f"CONSENT-PD-{i + 1:06d}",
                    customer,
                    "personal_data",
                    registered,
                    None,
                    registered,
                    registered,
                )
            )
            if i % 10 < 6:
                consents.append(
                    (
                        f"CONSENT-MKT-{i + 1:06d}",
                        customer,
                        "marketing",
                        registered,
                        None,
                        registered,
                        registered,
                    )
                )
            else:
                consents.append(
                    (
                        f"CONSENT-MKT-{i + 1:06d}",
                        customer,
                        "marketing",
                        registered,
                        current,
                        registered,
                        current,
                    )
                )
            if i < 1800:
                issued = current if i < 300 else registered
                cards.append(
                    (
                        f"CARD-{i + 1:06d}",
                        customer,
                        issued,
                        None,
                        "active",
                        amount(500000 + i * 31),
                        issued,
                        issued,
                    )
                )
            if i < 300:
                cards.append(
                    (
                        f"CARD-OLD-{i + 1:06d}",
                        customer,
                        registered,
                        current,
                        "closed",
                        Decimal(0),
                        registered,
                        current,
                    )
                )
        insert_rows(
            cursor,
            "crm.customer",
            (
                "customer_bk",
                "full_name",
                "birth_year",
                "sex",
                "city",
                "region",
                "level_bk",
                "registered_at",
                "created_at",
                "updated_at",
            ),
            customers,
        )
        insert_rows(
            cursor,
            "crm.customer_history",
            (
                "customer_bk",
                "valid_from",
                "valid_to",
                "attributes",
                "created_at",
                "updated_at",
            ),
            histories,
        )
        insert_rows(
            cursor,
            "crm.contact",
            (
                "contact_bk",
                "customer_bk",
                "contact_type",
                "contact_value",
                "created_at",
                "updated_at",
            ),
            contacts,
        )
        insert_rows(
            cursor,
            "crm.consent",
            (
                "consent_bk",
                "customer_bk",
                "consent_type",
                "granted_at",
                "revoked_at",
                "created_at",
                "updated_at",
            ),
            consents,
        )
        insert_rows(
            cursor,
            "crm.loyalty_card",
            (
                "card_bk",
                "customer_bk",
                "issued_at",
                "closed_at",
                "status",
                "bonus_balance",
                "created_at",
                "updated_at",
            ),
            cards,
        )

    def load_catalog(self, cursor):
        insert_rows(
            cursor,
            "catalog.manufacturer",
            ("manufacturer_bk", "manufacturer_name", "country"),
            [
                (
                    f"MFG-{i + 1:03d}",
                    f"Фармпроизводитель {i + 1}",
                    ("RU", "IN", "DE")[i % 3],
                )
                for i in range(24)
            ],
        )
        insert_rows(
            cursor,
            "catalog.drug_form",
            ("form_bk", "form_name"),
            [
                (f"FORM-{i + 1}", name)
                for i, name in enumerate(("Таблетки", "Капсулы", "Раствор", "Мазь"))
            ],
        )
        insert_rows(
            cursor,
            "catalog.inn",
            ("inn_bk", "inn_name"),
            [(f"INN-{i + 1:03d}", name) for i, name in enumerate(INNS)],
        )
        insert_rows(
            cursor,
            "catalog.sku",
            (
                "sku",
                "sku_name",
                "manufacturer_bk",
                "form_bk",
                "category",
                "is_rx",
                "is_vital",
                "pack_qty",
                "is_active",
                "is_deleted",
                "created_at",
                "updated_at",
            ),
            [self.sku(i) + (self.start, self.current_from) for i in range(600)],
        )
        histories, ingredients, prices = [], [], []
        boundaries = [
            self.start,
            self.start + timedelta(days=120),
            self.start + timedelta(days=240),
            None,
        ]
        for i in range(600):
            item = self.sku(i, old=True)
            histories.append(
                (
                    item[0],
                    self.start,
                    self.current_from,
                    *item[1:],
                    self.start,
                    self.start,
                )
            )
            if item[4] in ("rx", "otc"):
                ingredients.append((item[0], f"INN-{i % 10 + 1:03d}"))
                if i % 17 == 0:
                    ingredients.append((item[0], f"INN-{(i + 1) % 10 + 1:03d}"))
            scopes = [("chain", "ALL", 100)]
            if i < 60:
                scopes.append(("region", f"REG-{i % 12 + 1:02d}", 95))
            if i < 12:
                scopes.append(("pharmacy", f"PH-{i + 1:04d}", 92))
            for scope, key, multiplier in scopes:
                for version in range(3):
                    cents = ((10000 + (i % 60) * 625) * (90 + 5 * version) + 50) // 100
                    cents = (cents * multiplier + 50) // 100
                    prices.append(
                        (
                            f"PRICE-{i + 1:06d}-{scope}-{key}-{version + 1}",
                            item[0],
                            scope,
                            key,
                            amount(cents),
                            "RUB",
                            boundaries[version],
                            boundaries[version + 1],
                            boundaries[version],
                            boundaries[version],
                        )
                    )
        insert_rows(
            cursor,
            "catalog.sku_history",
            (
                "sku",
                "valid_from",
                "valid_to",
                "sku_name",
                "manufacturer_bk",
                "form_bk",
                "category",
                "is_rx",
                "is_vital",
                "pack_qty",
                "is_active",
                "is_deleted",
                "created_at",
                "updated_at",
            ),
            histories,
        )
        insert_rows(cursor, "catalog.sku_inn", ("sku", "inn_bk"), ingredients)
        insert_rows(
            cursor,
            "catalog.price",
            (
                "price_bk",
                "sku",
                "price_scope",
                "scope_bk",
                "price",
                "currency",
                "valid_from",
                "valid_to",
                "created_at",
                "updated_at",
            ),
            prices,
        )

    def load_wms(self, cursor):
        insert_rows(
            cursor,
            "wms.supplier",
            ("supplier_bk", "supplier_name", "country"),
            [(f"SUP-{i + 1:03d}", f"Дистрибьютор {i + 1}", "RU") for i in range(12)],
        )
        centers = [
            (f"DC-{i + 1:03d}", f"Распредцентр {i + 1}", f"REG-{i + 1:02d}", CITIES[i])
            for i in range(4)
        ]
        insert_rows(
            cursor,
            "wms.distribution_center",
            ("dc_bk", "dc_name", "region", "city"),
            centers,
        )
        insert_rows(
            cursor,
            "wms.location",
            ("location_type", "location_bk", "dc_bk"),
            [("dc", row[0], row[0]) for row in centers]
            + [("pharmacy", p[0], None) for p in self.pharmacies],
        )
        batches, orders, lines, receipts, transfers = [], [], [], [], []
        for i in range(600):
            allocation = 800 if i < 60 else 100
            unit_cost = amount((10000 + (i % 60) * 625) * 60 // 100)
            for slot in range(6):
                batch = self.batch(i, slot)
                batches.append(batch)
                batch_bk, sku, _, _, _, received, _, _ = batch
                purchase_prefix, dc, supplier = (
                    f"PO-{self.month:%Y%m}-{i + 1:06d}-{slot + 1}",
                    f"DC-{(i + slot) % 4 + 1:03d}",
                    f"SUP-{(i + slot) % 12 + 1:03d}",
                )
                for number in (1, 2):
                    purchase = f"{purchase_prefix}-{number}"
                    at_time = (
                        received
                        if number == 1
                        else self.start + timedelta(days=(i * 6 + slot) % 366, hours=10)
                    )
                    ordered = at_time - timedelta(days=3 + (i % 3))
                    quantity = allocation * (7 if number == 1 else 1)
                    orders.append(
                        (
                            purchase,
                            supplier,
                            dc,
                            ordered,
                            at_time + timedelta(hours=(i % 4 - 1) * 12),
                            "RUB",
                            ordered,
                            ordered,
                        )
                    )
                    lines.append(
                        (
                            purchase,
                            1,
                            sku,
                            batch_bk,
                            at_time,
                            quantity,
                            unit_cost,
                            quantity * unit_cost,
                            ordered,
                            at_time,
                        )
                    )
                    receipts.append(
                        (
                            f"MOV-IN-{batch_bk}-{number}",
                            batch_bk,
                            "receipt",
                            "supplier",
                            supplier,
                            "dc",
                            dc,
                            quantity,
                            ordered + timedelta(hours=12),
                            at_time,
                            purchase,
                            1,
                            None,
                            at_time,
                            at_time,
                        )
                    )
                for pharmacy_index in range(slot * 6, slot * 6 + 6):
                    pharmacy = self.pharmacies[pharmacy_index][0]
                    dispatched = received + timedelta(days=2, hours=pharmacy_index % 3)
                    arrived = dispatched + timedelta(hours=6 + pharmacy_index % 12)
                    transfers.append(
                        (
                            f"MOV-TR-{batch_bk}-{pharmacy}",
                            batch_bk,
                            "transfer",
                            "dc",
                            dc,
                            "pharmacy",
                            pharmacy,
                            allocation,
                            dispatched,
                            arrived,
                            None,
                            None,
                            None,
                            dispatched,
                            arrived,
                        )
                    )
        insert_rows(
            cursor,
            "wms.batch",
            (
                "batch_bk",
                "sku",
                "series_no",
                "manufactured_date",
                "expiry_date",
                "received_at",
                "created_at",
                "updated_at",
            ),
            batches,
        )
        insert_rows(
            cursor,
            "wms.purchase",
            (
                "purchase_bk",
                "supplier_bk",
                "dc_bk",
                "ordered_at",
                "expected_at",
                "currency",
                "created_at",
                "updated_at",
            ),
            orders,
        )
        insert_rows(
            cursor,
            "wms.purchase_line",
            (
                "purchase_bk",
                "line_no",
                "sku",
                "batch_bk",
                "received_at",
                "quantity",
                "unit_cost",
                "line_cost",
                "created_at",
                "updated_at",
            ),
            lines,
        )
        columns = (
            "movement_bk",
            "batch_bk",
            "movement_type",
            "src_type",
            "src_bk",
            "dst_type",
            "dst_bk",
            "qty",
            "dispatched_at",
            "moved_at",
            "purchase_bk",
            "purchase_line_no",
            "external_doc_bk",
            "created_at",
            "updated_at",
        )
        insert_rows(cursor, "wms.movement", columns, receipts)
        insert_rows(cursor, "wms.movement", columns, transfers)

    def load_pos(self, cursor, loader):
        insert_rows(
            cursor,
            "pos.pharmacy",
            (
                "pharmacy_bk",
                "pharmacy_name",
                "region",
                "city",
                "address",
                "opened_at",
                "created_at",
                "updated_at",
            ),
            self.pharmacies,
        )
        insert_rows(
            cursor,
            "pos.cash_register",
            ("register_bk", "pharmacy_bk"),
            [(f"REGISTER-{i + 1:04d}", p[0]) for i, p in enumerate(self.pharmacies)],
        )
        insert_rows(
            cursor,
            "pos.cashier",
            ("cashier_bk", "cashier_name"),
            [
                (f"CASHIER-{i + 1:04d}-{number}", f"Кассир {i + 1}-{number}")
                for i in range(36)
                for number in (1, 2)
            ],
        )
        sku_rows = loader.query(
            "catalog",
            "SELECT sku,valid_from,valid_to,sku_name,is_rx,created_at,updated_at FROM catalog.sku_history ORDER BY sku,valid_from",
        )
        price_rows = loader.query(
            "catalog",
            "SELECT price_bk,sku,price_scope,scope_bk,price,currency,valid_from,valid_to,created_at,updated_at FROM catalog.price ORDER BY price_bk",
        )
        batch_rows = loader.query(
            "wms",
            "SELECT batch_bk,sku,manufactured_date,expiry_date,received_at,created_at,updated_at FROM wms.batch ORDER BY batch_bk",
        )
        insert_rows(
            cursor,
            "pos.sku_reference",
            (
                "sku",
                "valid_from",
                "valid_to",
                "sku_name",
                "is_rx",
                "created_at",
                "updated_at",
            ),
            sku_rows,
        )
        insert_rows(
            cursor,
            "pos.price_reference",
            (
                "price_bk",
                "sku",
                "price_scope",
                "scope_bk",
                "price",
                "currency",
                "valid_from",
                "valid_to",
                "created_at",
                "updated_at",
            ),
            price_rows,
        )
        insert_rows(
            cursor,
            "pos.batch_reference",
            (
                "batch_bk",
                "sku",
                "manufactured_date",
                "expiry_date",
                "received_at",
                "created_at",
                "updated_at",
            ),
            batch_rows,
        )

    def load_reverse_movements(self, cursor):
        for reason in ("supplier_return", "damaged", "expired"):
            suffix = f"{self.month:%Y%m}-{reason.upper()}"
            batch, purchase = f"BATCH-REVERSE-{suffix}", f"PO-REVERSE-{suffix}"
            received = (
                self.start + timedelta(days=20, hours=10)
                if reason == "expired"
                else self.anchor - timedelta(days=20) + timedelta(hours=10)
            )
            expiry = (
                received.date() + timedelta(days=30)
                if reason == "expired"
                else self.month + timedelta(days=365)
            )
            ordered = received - timedelta(days=3)
            cursor.execute(
                """INSERT INTO wms.batch
                   (batch_bk,sku,series_no,manufactured_date,expiry_date,received_at,created_at,updated_at)
                   VALUES (%s,'SKU-000001',%s,%s,%s,%s,%s,%s)""",
                (
                    batch,
                    f"REVERSE-{suffix}",
                    received.date() - timedelta(days=30),
                    expiry,
                    received,
                    received,
                    received,
                ),
            )
            cursor.execute(
                """INSERT INTO wms.purchase
                   (purchase_bk,supplier_bk,dc_bk,ordered_at,expected_at,currency,created_at,updated_at)
                   VALUES (%s,'SUP-001','DC-001',%s,%s,'RUB',%s,%s)""",
                (purchase, ordered, received, ordered, ordered),
            )
            cursor.execute(
                """INSERT INTO wms.purchase_line
                   (purchase_bk,line_no,sku,batch_bk,received_at,quantity,unit_cost,line_cost,created_at,updated_at)
                   VALUES (%s,1,'SKU-000001',%s,%s,20,50,1000,%s,%s)""",
                (purchase, batch, received, ordered, received),
            )
            cursor.execute(
                """INSERT INTO wms.movement
                   (movement_bk,batch_bk,movement_type,src_type,src_bk,dst_type,dst_bk,qty,
                    dispatched_at,moved_at,purchase_bk,purchase_line_no,created_at,updated_at)
                   VALUES (%s,%s,'receipt','supplier','SUP-001','dc','DC-001',20,%s,%s,%s,1,%s,%s)""",
                (
                    f"MOV-IN-REVERSE-{suffix}",
                    batch,
                    ordered + timedelta(hours=12),
                    received,
                    purchase,
                    received,
                    received,
                ),
            )
            if reason == "supplier_return":
                source_type, source_bk, quantity = "dc", "DC-001", 10
            else:
                dispatched = received + timedelta(days=1)
                arrived = dispatched + timedelta(hours=6)
                cursor.execute(
                    """INSERT INTO wms.movement
                       (movement_bk,batch_bk,movement_type,src_type,src_bk,dst_type,dst_bk,qty,
                        dispatched_at,moved_at,created_at,updated_at)
                       VALUES (%s,%s,'transfer','dc','DC-001','pharmacy','PH-0001',10,%s,%s,%s,%s)""",
                    (
                        f"MOV-TR-REVERSE-{suffix}",
                        batch,
                        dispatched,
                        arrived,
                        arrived,
                        arrived,
                    ),
                )
                source_type, source_bk = "pharmacy", "PH-0001"
                quantity = 10 if reason == "expired" else 4
            occurred = (
                datetime.combine(expiry + timedelta(days=1), time(12), UTC)
                if reason == "expired"
                else received + timedelta(days=3)
            )
            movement = f"MOV-OUT-REVERSE-{suffix}"
            cursor.execute(
                """INSERT INTO wms.movement
                   (movement_bk,batch_bk,movement_type,src_type,src_bk,qty,
                    dispatched_at,moved_at,created_at,updated_at)
                   VALUES (%s,%s,'writeoff',%s,%s,%s,%s,%s,%s,%s)""",
                (
                    movement,
                    batch,
                    source_type,
                    source_bk,
                    quantity,
                    occurred - timedelta(hours=1),
                    occurred,
                    occurred,
                    occurred,
                ),
            )
            cursor.execute(
                """INSERT INTO wms.writeoff_detail(movement_bk,reason,supplier_bk,created_at,updated_at)
                   VALUES (%s,%s,%s,%s,%s)""",
                (
                    movement,
                    reason,
                    "SUP-001" if reason == "supplier_return" else None,
                    occurred,
                    occurred,
                ),
            )

    def load(self, loader):
        parameters = {"kind": "foundation", "version": 1}
        for service, work in [
            ("crm", self.load_crm),
            ("catalog", self.load_catalog),
            ("wms", self.load_wms),
            ("pos", lambda cursor: self.load_pos(cursor, loader)),
        ]:
            loader.step(service, "FOUNDATION", 0, 0, self.month, parameters, work)
        loader.step(
            "wms",
            "REVERSE-FLOWS-V1",
            0,
            0,
            self.month,
            {"kind": "reverse_movements", "version": 1},
            self.load_reverse_movements,
        )


def sync_references(cursor, loader):
    specs = [
        (
            "catalog",
            "pos.sku_reference",
            ("sku", "valid_from"),
            (
                "sku",
                "valid_from",
                "valid_to",
                "sku_name",
                "is_rx",
                "created_at",
                "updated_at",
            ),
            "SELECT sku,valid_from,valid_to,sku_name,is_rx,created_at,updated_at FROM catalog.sku_history",
        ),
        (
            "catalog",
            "pos.price_reference",
            ("price_bk",),
            (
                "price_bk",
                "sku",
                "price_scope",
                "scope_bk",
                "price",
                "currency",
                "valid_from",
                "valid_to",
                "created_at",
                "updated_at",
            ),
            "SELECT price_bk,sku,price_scope,scope_bk,price,currency,valid_from,valid_to,created_at,updated_at FROM catalog.price",
        ),
        (
            "wms",
            "pos.batch_reference",
            ("batch_bk",),
            (
                "batch_bk",
                "sku",
                "manufactured_date",
                "expiry_date",
                "received_at",
                "created_at",
                "updated_at",
            ),
            "SELECT batch_bk,sku,manufactured_date,expiry_date,received_at,created_at,updated_at FROM wms.batch",
        ),
    ]
    for service, table, keys, columns, query in specs:
        changed = [
            name for name in columns if name not in (*keys, "created_at", "updated_at")
        ]
        table_name = table.split(".")[1]
        assignments = ",".join(f"{name}=EXCLUDED.{name}" for name in changed)
        current = ",".join(f"{table_name}.{name}" for name in changed)
        incoming = ",".join(f"EXCLUDED.{name}" for name in changed)
        suffix = f"ON CONFLICT ({','.join(keys)}) DO UPDATE SET {assignments} WHERE ROW({current}) IS DISTINCT FROM ROW({incoming})"
        insert_rows(cursor, table, columns, loader.query(service, query), suffix)


class SalesPlan:
    def __init__(self, loader, foundation, seed, batch, count):
        self.foundation = foundation
        self.batch = batch
        rng = random.Random(
            int.from_bytes(
                hashlib.sha256(f"{seed}:{batch}".encode()).digest()[:8], "big"
            )
        )
        self.documents, self.lines, self.payments, self.recipes, self.movements = (
            [],
            [],
            [],
            [],
            [],
        )
        self.shifts = {}
        versions, prices, regions = (
            defaultdict(list),
            defaultdict(list),
            defaultdict(list),
        )
        for sku, vf, vt, name, rx in loader.query(
            "catalog",
            "SELECT sku,valid_from,valid_to,sku_name,is_rx FROM catalog.sku_history ORDER BY sku,valid_from",
        ):
            versions[sku].append((vf, vt, name, rx))
        for row in loader.query(
            "catalog",
            "SELECT sku,price_bk,price_scope,scope_bk,price,currency,valid_from,valid_to FROM catalog.price",
        ):
            prices[row[0]].append(row[1:])
        for pharmacy, vf, vt, attrs in loader.query(
            "pos",
            "SELECT pharmacy_bk,valid_from,valid_to,attributes FROM pos.pharmacy_history ORDER BY pharmacy_bk,valid_from",
        ):
            regions[pharmacy].append((vf, vt, attrs["region"]))
        customers = [
            r[0]
            for r in loader.query(
                "crm",
                """SELECT DISTINCT c.customer_bk
            FROM contract.v_customer c JOIN crm.loyalty_card l USING(customer_bk)
            WHERE l.issued_at <= %s AND (l.closed_at IS NULL OR l.closed_at > %s)
            ORDER BY c.customer_bk""",
                (foundation.start, foundation.start),
            )
        ]
        if not customers:
            raise ValueError("No customers with a card during the dataset history")
        days = [foundation.start + timedelta(days=i) for i in range(366)]
        day_weights = [(1, 1, 1, 1, 1.2, 2, 1.8)[day.weekday()] for day in days]
        sku_weights = list(accumulate(18 if i < 60 else 1 for i in range(600)))
        sale_count = count - round(count * 0.03)
        sales = []
        for number in range(sale_count):
            pharmacy_index = rng.choices(range(36), weights=[5] * 6 + [1] * 30, k=1)[0]
            pharmacy = foundation.pharmacies[pharmacy_index][0]
            at_time = rng.choices(days, weights=day_weights, k=1)[0] + timedelta(
                hours=rng.randrange(9, 21),
                minutes=rng.randrange(60),
                seconds=rng.randrange(60),
            )
            if number == 0:
                at_time = foundation.start + timedelta(hours=10)
            elif number == sale_count - 1:
                at_time = foundation.anchor + timedelta(hours=20)
            region = next(
                region
                for vf, vt, region in regions[pharmacy]
                if vf <= at_time and (vt is None or at_time < vt)
            )
            customer = None if rng.random() < 0.45 else rng.choice(customers)
            receipt_bk = f"RCPT-{at_time:%Y%m%d}-{batch}-{number + 1:06d}"
            items, used = [], set()
            for line_no in range(1, 5):
                while True:
                    index = rng.choices(range(600), cum_weights=sku_weights, k=1)[0]
                    if index not in used:
                        used.add(index)
                        break
                sku = f"SKU-{index + 1:06d}"
                _, _, name, rx = next(
                    v
                    for v in versions[sku]
                    if v[0] <= at_time and (v[1] is None or at_time < v[1])
                )
                candidates = [
                    p
                    for p in prices[sku]
                    if p[5] <= at_time
                    and (p[6] is None or at_time < p[6])
                    and (p[1], p[2])
                    in (("chain", "ALL"), ("region", region), ("pharmacy", pharmacy))
                ]
                price = max(
                    candidates,
                    key=lambda p: {"chain": 1, "region": 2, "pharmacy": 3}[p[1]],
                )
                cents = int(price[3] * 100)
                quantity = rng.choices((1, 2, 3), weights=(80, 17, 3), k=1)[0]
                discount_rate = (
                    rng.choices((0, 5, 10), weights=(70, 20, 10), k=1)[0]
                    if customer
                    else 0
                )
                discount = quantity * cents * discount_rate // 100
                batch_bk = foundation.batch(index, pharmacy_index // 6)[0]
                items.append(
                    (
                        receipt_bk,
                        line_no,
                        sku,
                        batch_bk,
                        price[0],
                        quantity,
                        amount(cents),
                        amount(discount),
                        amount(quantity * cents - discount),
                        rx,
                        name,
                        at_time,
                        at_time,
                    )
                )
            recipe = (
                f"RX-{batch}-{number + 1:06d}"
                if any(item[9] for item in items)
                else None
            )
            if recipe:
                self.recipes.append(
                    (
                        recipe,
                        customer,
                        at_time - timedelta(days=1),
                        at_time + timedelta(days=30),
                        at_time,
                        at_time,
                    )
                )
            total = sum(item[8] for item in items)
            discount = sum(item[7] for item in items)
            shift, cashier = self.shift(pharmacy_index, at_time)
            document = (
                receipt_bk,
                pharmacy,
                customer,
                cashier,
                shift,
                at_time,
                "sale",
                None,
                total,
                discount,
                "RUB",
                recipe,
                at_time,
                at_time,
            )
            self.documents.append(document)
            self.lines.extend(items)
            primary = rng.choices(("cash", "card"), weights=(25, 75), k=1)[0]
            if rng.random() < 0.2:
                secondary = (
                    "bonus" if customer and rng.random() < 0.6 else "certificate"
                )
                part = amount(max(1, int(total * 100) // 10))
                self.payments.extend(
                    [
                        (receipt_bk, 1, primary, total - part, "RUB", at_time, at_time),
                        (receipt_bk, 2, secondary, part, "RUB", at_time, at_time),
                    ]
                )
            else:
                self.payments.append(
                    (receipt_bk, 1, primary, total, "RUB", at_time, at_time)
                )
            sales.append((document, items, pharmacy_index))
        for number, (original, items, pharmacy_index) in enumerate(
            rng.sample(sales, count - sale_count), start=sale_count + 1
        ):
            at_time = min(
                original[5] + timedelta(days=rng.randrange(1, 8)),
                foundation.anchor + timedelta(days=1, seconds=-1),
            )
            receipt_bk = f"RCPT-{at_time:%Y%m%d}-{batch}-{number:06d}"
            old = items[0]
            item = (receipt_bk, 1, *old[2:11], at_time, at_time)
            shift, cashier = self.shift(pharmacy_index, at_time)
            self.documents.append(
                (
                    receipt_bk,
                    original[1],
                    original[2],
                    cashier,
                    shift,
                    at_time,
                    "refund",
                    original[0],
                    item[8],
                    item[7],
                    "RUB",
                    original[11],
                    at_time,
                    at_time,
                )
            )
            self.lines.append(item)
            self.payments.append(
                (receipt_bk, 1, "card", item[8], "RUB", at_time, at_time)
            )
        documents = {d[0]: d for d in self.documents}
        for item in self.lines:
            document = documents[item[0]]
            is_sale = document[6] == "sale"
            src_type, src_bk = ("pharmacy", document[1]) if is_sale else (None, None)
            dst_type, dst_bk = (
                ("customer", document[2] or "ANONYMOUS")
                if is_sale
                else ("pharmacy", document[1])
            )
            self.movements.append(
                (
                    f"MOV-{item[0]}-{item[1]}",
                    item[3],
                    "sale_writeoff" if is_sale else "return",
                    src_type,
                    src_bk,
                    dst_type,
                    dst_bk,
                    item[5],
                    document[5],
                    document[5],
                    None,
                    None,
                    document[0],
                    document[5],
                    document[5],
                )
            )
        self.movements.sort(key=lambda row: (row[9], row[0]))
        self.fingerprint = hashlib.sha256(
            json.dumps(
                [self.documents, self.lines, self.payments],
                default=str,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    def shift(self, pharmacy_index, at_time):
        key = f"SHIFT-{pharmacy_index + 1:04d}-{at_time:%Y%m%d}"
        cashier = (
            f"CASHIER-{pharmacy_index + 1:04d}-{at_time.date().toordinal() % 2 + 1}"
        )
        opened = datetime.combine(at_time.date(), time(), UTC)
        self.shifts[key] = (
            key,
            f"REGISTER-{pharmacy_index + 1:04d}",
            cashier,
            opened,
            opened + timedelta(days=1),
            opened,
            opened,
        )
        return key, cashier

    def load_wms(self, cursor):
        insert_rows(
            cursor,
            "wms.movement",
            (
                "movement_bk",
                "batch_bk",
                "movement_type",
                "src_type",
                "src_bk",
                "dst_type",
                "dst_bk",
                "qty",
                "dispatched_at",
                "moved_at",
                "purchase_bk",
                "purchase_line_no",
                "external_doc_bk",
                "created_at",
                "updated_at",
            ),
            self.movements,
        )

    def load_pos(self, cursor, loader):
        sync_references(cursor, loader)
        insert_rows(
            cursor,
            "pos.shift",
            (
                "shift_bk",
                "register_bk",
                "cashier_bk",
                "opened_at",
                "closed_at",
                "created_at",
                "updated_at",
            ),
            sorted(self.shifts.values()),
            "ON CONFLICT DO NOTHING",
        )
        insert_rows(
            cursor,
            "pos.prescription",
            (
                "prescription_bk",
                "customer_bk",
                "issued_at",
                "expires_at",
                "created_at",
                "updated_at",
            ),
            self.recipes,
        )
        insert_rows(
            cursor,
            "pos.receipt",
            (
                "receipt_bk",
                "pharmacy_bk",
                "customer_bk",
                "cashier_bk",
                "shift_bk",
                "receipt_dt",
                "doc_type",
                "parent_receipt_bk",
                "total_amount",
                "discount_amount",
                "currency",
                "prescription_bk",
                "created_at",
                "updated_at",
            ),
            self.documents,
        )
        insert_rows(
            cursor,
            "pos.receipt_line",
            (
                "receipt_bk",
                "line_no",
                "sku",
                "batch_bk",
                "price_bk",
                "quantity",
                "unit_price",
                "line_discount",
                "line_amount",
                "is_rx_snapshot",
                "sku_name_snapshot",
                "created_at",
                "updated_at",
            ),
            self.lines,
        )
        insert_rows(
            cursor,
            "pos.payment",
            (
                "receipt_bk",
                "payment_no",
                "payment_method",
                "amount",
                "currency",
                "created_at",
                "updated_at",
            ),
            self.payments,
        )
        cursor.execute(
            "ANALYZE pos.receipt; ANALYZE pos.receipt_line; ANALYZE pos.payment"
        )
        print(
            "pos: rows loaded and statistics updated before deferred checks", flush=True
        )


def load_sales(loader, foundation, args):
    sequence = 0
    if args.next_batch:
        sequence = loader.query(
            "pos",
            """SELECT coalesce(max((parameters->>'sequence')::integer),0)+1
            FROM core.seed_run WHERE parameters->>'kind'='receipts' AND batch_bk LIKE 'DELTA-%'""",
        )[0][0]
    batch = args.batch_id or (
        f"DELTA-{sequence:06d}"
        if args.next_batch
        else f"SEED-{args.seed}-{args.receipts}"
    )
    if not re.fullmatch(r"[A-Za-z0-9_-]+", batch):
        raise ValueError(
            "Batch ID may contain only letters, digits, underscores and hyphens"
        )
    query = "SELECT seed,receipt_count,reference_month,parameters FROM core.seed_run WHERE batch_bk=%s"
    pos_run = loader.query("pos", query, (batch,))
    if pos_run:
        wms_run = loader.query("wms", query, (batch,))
        if pos_run != wms_run or pos_run[0][:3] != (
            args.seed,
            args.receipts,
            foundation.month,
        ):
            raise RuntimeError(f"Completed batch {batch} has inconsistent parameters")
        print(f"{batch}: already complete; no data changed", flush=True)
        return
    plan = SalesPlan(loader, foundation, args.seed, batch, args.receipts)
    parameters = {
        "kind": "receipts",
        "version": 1,
        "sequence": sequence,
        "plan_sha256": plan.fingerprint,
    }
    loader.step(
        "wms",
        batch,
        args.seed,
        args.receipts,
        foundation.month,
        parameters,
        plan.load_wms,
    )
    loader.step(
        "pos",
        batch,
        args.seed,
        args.receipts,
        foundation.month,
        parameters,
        lambda cursor: plan.load_pos(cursor, loader),
    )
    print(
        f"{batch}: {len(plan.documents)} documents, {len(plan.lines)} lines, {len(plan.payments)} payments",
        flush=True,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--receipts", type=int, default=24000)
    parser.add_argument("--batch-id")
    parser.add_argument("--next-batch", action="store_true")
    parser.add_argument("--foundation-only", action="store_true")
    parser.add_argument("--reference-month", type=date.fromisoformat)
    parser.add_argument(
        "--dsn",
        default=os.environ.get(
            "ADMIN_DSN", "postgresql://postgres:postgres@localhost:5000/postgres"
        ),
    )
    args = parser.parse_args()
    if args.receipts < 0:
        parser.error("--receipts must be nonnegative")
    if args.reference_month and args.reference_month.day != 1:
        parser.error("--reference-month must be the first day of a month")
    loader = Loader(args.dsn)
    try:
        loader.query("pos", "SELECT pg_advisory_lock(hashtext('hw01-seed'))")
        month = loader.reference_month(args.reference_month)
        foundation = Foundation(month)
        foundation.load(loader)
        if args.foundation_only:
            return
        if args.batch_id and args.next_batch:
            parser.error("--batch-id and --next-batch are mutually exclusive")
        load_sales(loader, foundation, args)
    finally:
        loader.close()


if __name__ == "__main__":
    main()
