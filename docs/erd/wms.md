# WMS

Все показанные поля обязательны, кроме помеченных `nullable`. Во всех таблицах обязательны `created_at`, `updated_at`. Ссылки FK существуют только внутри WMS.

```mermaid
erDiagram
    SUPPLIER ||--o{ PURCHASE : supplies
    DISTRIBUTION_CENTER ||--o{ PURCHASE : receives
    PURCHASE ||--|{ PURCHASE_LINE : lines
    PURCHASE_LINE }o--o| BATCH : received_batch
    SUPPLIER {
        text supplier_bk PK
        text supplier_name
        text country
        boolean is_active
        boolean is_deleted
    }
    DISTRIBUTION_CENTER {
        text dc_bk PK
        text dc_name
        text region
        text city
        boolean is_active
        boolean is_deleted
    }
    PURCHASE {
        text purchase_bk PK
        text supplier_bk FK
        text dc_bk FK
        timestamptz ordered_at
        timestamptz expected_at
        text currency
    }
    PURCHASE_LINE {
        text purchase_bk PK,FK
        int line_no PK
        text sku "logical CAT BK"
        text batch_bk FK "nullable"
        timestamptz received_at "nullable"
        numeric quantity
        numeric unit_cost
        numeric line_cost
        bigint revision
    }
    BATCH {
        text batch_bk PK
        text sku "logical CAT BK"
        text series_no "UK together with sku"
        date manufactured_date
        date expiry_date
        timestamptz received_at
    }
```

```mermaid
erDiagram
    BATCH ||--o{ MOVEMENT : moves
    BATCH ||--o{ STOCK : balances
    LOCATION ||--o{ STOCK : holds
    LOCATION {
        text location_type PK
        text location_bk PK "DC or logical POS BK"
        text dc_bk FK "nullable for pharmacy"
        boolean is_deleted
    }
    STOCK {
        text location_type PK,FK
        text location_bk PK,FK
        text batch_bk PK,FK
        numeric qty_on_hand
    }
    MOVEMENT {
        text movement_bk PK
        text batch_bk FK
        text movement_type
        text src_type "nullable"
        text src_bk "nullable"
        text dst_type "nullable"
        text dst_bk "nullable"
        numeric qty
        timestamptz dispatched_at "nullable"
        timestamptz moved_at
        text purchase_bk FK "nullable"
        int purchase_line_no FK "nullable"
        text external_doc_bk "nullable, logical POS BK"
    }
    BATCH {
        text batch_bk PK
    }
```

Остаток меняет триггер журнала в той же транзакции, что и движение. Строки локаций блокируются в одном порядке, списание проверяется через `CHECK (qty_on_hand >= 0)`. Приложение не получает прямых прав изменения остатков. Исправление движения — новое компенсирующее движение. `external_doc_bk` связывает списание или возврат с кассовым документом POS без межбазового FK.

## Возвраты поставщикам и списания

```mermaid
erDiagram
    MOVEMENT ||--o| WRITEOFF_DETAIL : explains
    SUPPLIER o|--o{ WRITEOFF_DETAIL : receives_return
    MOVEMENT {
        text movement_bk PK
        text batch_bk FK
        numeric qty
        timestamptz dispatched_at "nullable"
        timestamptz moved_at
    }
    WRITEOFF_DETAIL {
        text movement_bk PK,FK
        text reason "supplier_return, damaged, expired"
        text supplier_bk FK "nullable except supplier_return"
    }
    SUPPLIER {
        text supplier_bk PK
    }
```

Для writeoff объяснение обязательно к COMMIT. Внешний получатель возврата хранится в writeoff_detail.supplier_bk; в фиксированном контракте это исходящий writeoff с dst_type/dst_bk = NULL. Возврат покупателя остаётся отдельным типом return и направлением в аптеку. Причины damaged и expired различаются; expired допускается только после expiry_date. Объяснение и движение неизменяемы, технические поля обязательны.
