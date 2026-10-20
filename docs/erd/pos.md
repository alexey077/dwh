# POS

`PK` — первичный ключ, `FK` — связь внутри POS. Поля обязательны, кроме помеченных `nullable`. Во всех таблицах есть обязательные технические поля `created_at`, `updated_at`.

```mermaid
erDiagram
    PHARMACY ||--o{ CASH_REGISTER : registers
    PHARMACY ||--|{ PHARMACY_HISTORY : versions
    CASH_REGISTER ||--o{ SHIFT : shifts
    CASHIER ||--o{ SHIFT : works
    SHIFT ||--o{ RECEIPT : documents
    PHARMACY {
        text pharmacy_bk PK
        text pharmacy_name
        text region
        text city
        text address
        date opened_at
        date closed_at "nullable"
        boolean is_active
        boolean is_deleted
    }
    PHARMACY_HISTORY {
        text pharmacy_bk PK,FK
        timestamptz valid_from PK
        timestamptz valid_to "nullable"
        jsonb attributes
    }
    CASH_REGISTER {
        text register_bk PK
        text pharmacy_bk FK
        boolean is_deleted
    }
    CASHIER {
        text cashier_bk PK
        text cashier_name
        boolean is_deleted
    }
    SHIFT {
        text shift_bk PK
        text register_bk FK
        text cashier_bk FK
        timestamptz opened_at
        timestamptz closed_at "nullable"
    }
    RECEIPT {
        text receipt_bk PK
        text pharmacy_bk FK
        text cashier_bk FK
        text shift_bk FK
        text customer_bk "nullable, logical CRM BK"
        timestamptz receipt_dt
        text doc_type
        text parent_receipt_bk FK "nullable for sale"
        numeric total_amount
        numeric discount_amount
        text currency
        text prescription_bk FK "nullable"
        bigint revision
        boolean check_pending
    }
```

```mermaid
erDiagram
    RECEIPT ||--|{ RECEIPT_LINE : items
    RECEIPT ||--|{ PAYMENT : payments
    PRESCRIPTION o|--o{ RECEIPT : authorizes
    BATCH_REFERENCE ||--o{ RECEIPT_LINE : batch
    RECEIPT {
        text receipt_bk PK
    }
    RECEIPT_LINE {
        text receipt_bk PK,FK
        int line_no PK
        text sku "logical CAT BK"
        text batch_bk FK "copy of WMS BK"
        text price_bk FK
        numeric quantity
        numeric unit_price
        numeric line_discount
        numeric line_amount
        boolean is_rx_snapshot
        text sku_name_snapshot
    }
    PAYMENT {
        text receipt_bk PK,FK
        int payment_no PK
        text payment_method
        numeric amount
        text currency
    }
    PRESCRIPTION {
        text prescription_bk PK
        text customer_bk "nullable, logical CRM BK"
        timestamptz issued_at
        timestamptz expires_at
    }
    BATCH_REFERENCE {
        text batch_bk PK
        text sku "logical CAT BK"
        date manufactured_date
        date expiry_date
        timestamptz received_at
    }
```

Локальные версии каталога и связь с позицией:

```mermaid
erDiagram
    CAT_SKU ||..o{ SKU_REFERENCE : logical_sku
    CAT_PRICE ||..o| PRICE_REFERENCE : logical_price
    PRICE_REFERENCE ||--o{ RECEIPT_LINE : price_version
    CAT_SKU {
        text sku PK "external CAT BK"
    }
    CAT_PRICE {
        text price_bk PK "external CAT BK"
    }
    SKU_REFERENCE {
        text sku PK "logical CAT BK"
        timestamptz valid_from PK
        timestamptz valid_to "nullable"
        text sku_name
        boolean is_rx
    }
    PRICE_REFERENCE {
        text price_bk PK
        text sku "logical CAT BK"
        text price_scope
        text scope_bk "ALL, region or logical POS pharmacy BK"
        numeric price
        text currency
        timestamptz valid_from
        timestamptz valid_to "nullable"
    }
    RECEIPT_LINE {
        text receipt_bk PK,FK
        int line_no PK
        text price_bk FK
    }
```

Пунктир обозначает логический BK между сервисами. Физический FK price_bk ведёт к локальной PRICE_REFERENCE; версия SKU выбирается по SKU и времени продажи.

Локальные ссылки `batch_reference`, `sku_reference`, `price_reference` наполняются из WMS и каталога приложением. Физические FK ведут только к этим копиям внутри POS. Первичные владельцы BK остаются в исходных сервисах.

Позиция хранит исторические цену, название и рецептурность. Изменение каталога не пересчитывает старые документы. И суммы позиций, и суммы оплат проверяются отложенными constraint triggers при завершении транзакции. Возврат ссылается на продажу; изменение счётчика `revision` исходной продажи сериализует конкурентные возвраты. Внутренний флаг проверки приложение менять не может.
