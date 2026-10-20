# POS

`PK` — первичный ключ, `FK` — связь внутри POS. Поля обязательны, кроме помеченных `nullable`. Во всех таблицах есть обязательные технические поля `created_at`, `updated_at`.

```mermaid
erDiagram
    PHARMACY ||--o{ CASH_REGISTER : registers
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

Остальные таблицы:

| Таблица | Ключ | Обязательные поля | Необязательные поля |
|---|---|---|---|
| `pharmacy_history` | `(pharmacy_bk text FK, valid_from timestamptz)` PK | `attributes jsonb` | `valid_to timestamptz` |
| `sku_reference` | `(sku text, valid_from timestamptz)` PK | `sku_name text`, `is_rx boolean` | `valid_to timestamptz` |
| `price_reference` | `price_bk text` PK | `sku text`, `price_scope text`, `scope_bk text`, `price numeric(14,2)`, `currency text`, `valid_from timestamptz` | `valid_to timestamptz` |

Локальные ссылки `batch_reference`, `sku_reference`, `price_reference` наполняются из WMS и каталога приложением. Физические FK ведут только к этим копиям внутри POS. Первичные владельцы BK остаются в исходных сервисах.

Позиция хранит исторические цену, название и рецептурность. Изменение каталога не пересчитывает старые документы. И суммы позиций, и суммы оплат проверяются отложенными constraint triggers при завершении транзакции. Возврат ссылается на продажу; изменение счётчика `revision` исходной продажи сериализует конкурентные возвраты. Внутренний флаг проверки приложение менять не может.
