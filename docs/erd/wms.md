# WMS

Физическая схема БД `wms_service_db`. Модель разделена на блоки; повторяющиеся таблицы показаны полностью в каждом из них.

`PK` — первичный ключ, `FK` — внешний ключ в той же БД. Несколько полей с `PK` образуют один составной ключ. `NN` — `NOT NULL` (включая поля PK), `NULL` — ограничение `NOT NULL` в DDL не задано. Точность `numeric(p,s)` указана в комментарии к полю.

Все поля таблиц приведены явно, включая `created_at` и `updated_at`. У обоих тип `timestamptz`, обязательность NN и `DEFAULT clock_timestamp()`; `updated_at` меняется автоматически триггером `core.touch_row`. `GEN` — вычисляемое поле. Общие технические таблицы каждой БД показаны [отдельно](core.md).

Сплошная линия — FK входит в PK дочерней таблицы; пунктир — не входит. На стороне родителя указано «ровно один» или «ноль/один» по обязательности FK, на стороне дочерних строк — допустимое число ссылок. FK сам по себе не требует, чтобы у родителя уже были дочерние строки. Дополнительные требования триггеров описаны ниже.

Метки `BK` у полей обозначают логические межсервисные ссылки. Их адресаты описаны после диаграмм.

## Закупки и партии

```mermaid
erDiagram
    direction TB
    SUPPLIER ||..o{ PURCHASE : "supplier_bk"
    DISTRIBUTION_CENTER ||..o{ PURCHASE : "dc_bk"
    PURCHASE ||--o{ PURCHASE_LINE : "purchase_bk"
    BATCH |o..o{ PURCHASE_LINE : "batch_bk"
    SUPPLIER {
        text supplier_bk PK "NN"
        text supplier_name "NN"
        text country "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    DISTRIBUTION_CENTER {
        text dc_bk PK "NN"
        text dc_name "NN"
        text region "NN"
        text city "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PURCHASE {
        text purchase_bk PK "NN"
        text supplier_bk FK "NN"
        text dc_bk FK "NN"
        timestamptz ordered_at "NN"
        timestamptz expected_at "NN"
        text currency "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PURCHASE_LINE {
        text purchase_bk PK,FK "NN"
        integer line_no PK "NN"
        text sku "NN; BK: CAT.sku"
        text batch_bk FK "NULL"
        timestamptz received_at "NULL"
        numeric quantity "NN; numeric(14,3)"
        numeric unit_cost "NN; numeric(14,2)"
        numeric line_cost "NN; numeric(16,2)"
        bigint revision "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    BATCH {
        text batch_bk PK "NN"
        text sku "NN; BK: CAT.sku"
        text series_no "NN"
        date manufactured_date "NN"
        date expiry_date "NN"
        timestamptz received_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Локации и остатки

```mermaid
erDiagram
    direction TB
    DISTRIBUTION_CENTER |o..o{ LOCATION : "dc_bk"
    BATCH ||--o{ STOCK : "batch_bk"
    LOCATION ||--o{ STOCK : "location_type, location_bk"
    DISTRIBUTION_CENTER {
        text dc_bk PK "NN"
        text dc_name "NN"
        text region "NN"
        text city "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    LOCATION {
        text location_type PK "NN"
        text location_bk PK "NN; BK: POS pharmacy или WMS dc"
        text dc_bk FK "NULL"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    BATCH {
        text batch_bk PK "NN"
        text sku "NN; BK: CAT.sku"
        text series_no "NN"
        date manufactured_date "NN"
        date expiry_date "NN"
        timestamptz received_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    STOCK {
        text location_type PK,FK "NN"
        text location_bk PK,FK "NN"
        text batch_bk PK,FK "NN"
        numeric qty_on_hand "NN; numeric(14,3)"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Журнал и причины исходящих операций

```mermaid
erDiagram
    direction TB
    BATCH ||..o{ MOVEMENT : "batch_bk"
    PURCHASE_LINE |o..o{ MOVEMENT : "purchase_bk, purchase_line_no"
    BATCH |o..o{ PURCHASE_LINE : "batch_bk"
    MOVEMENT ||--o| WRITEOFF_DETAIL : "movement_bk"
    SUPPLIER |o..o{ WRITEOFF_DETAIL : "supplier_bk"
    MOVEMENT {
        text movement_bk PK "NN"
        text batch_bk FK "NN"
        text movement_type "NN"
        text src_type "NULL"
        text src_bk "NULL; BK в паре с src_type"
        text dst_type "NULL"
        text dst_bk "NULL; BK в паре с dst_type"
        numeric qty "NN; numeric(14,3)"
        timestamptz dispatched_at "NULL"
        timestamptz moved_at "NN"
        text purchase_bk FK "NULL"
        integer purchase_line_no FK "NULL"
        text external_doc_bk "NULL; BK: POS.receipt"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PURCHASE_LINE {
        text purchase_bk PK,FK "NN"
        integer line_no PK "NN"
        text sku "NN; BK: CAT.sku"
        text batch_bk FK "NULL"
        timestamptz received_at "NULL"
        numeric quantity "NN; numeric(14,3)"
        numeric unit_cost "NN; numeric(14,2)"
        numeric line_cost "NN; numeric(16,2)"
        bigint revision "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    BATCH {
        text batch_bk PK "NN"
        text sku "NN; BK: CAT.sku"
        text series_no "NN"
        date manufactured_date "NN"
        date expiry_date "NN"
        timestamptz received_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    WRITEOFF_DETAIL {
        text movement_bk PK,FK "NN"
        text reason "NN"
        text supplier_bk FK "NULL; supplier_return: NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    SUPPLIER {
        text supplier_bk PK "NN"
        text supplier_name "NN"
        text country "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Все физические FK

| Дочерняя таблица и поля | Родительская таблица и поля | Обязательность |
|---|---|---|
| `wms.location(dc_bk)` | `wms.distribution_center(dc_bk)` | NULL допускается |
| `wms.movement(batch_bk)` | `wms.batch(batch_bk)` | NN |
| `wms.movement(purchase_bk, purchase_line_no)` | `wms.purchase_line(purchase_bk, line_no)` | NULL допускается |
| `wms.purchase(supplier_bk)` | `wms.supplier(supplier_bk)` | NN |
| `wms.purchase(dc_bk)` | `wms.distribution_center(dc_bk)` | NN |
| `wms.purchase_line(purchase_bk)` | `wms.purchase(purchase_bk)` | NN |
| `wms.purchase_line(batch_bk)` | `wms.batch(batch_bk)` | NULL допускается |
| `wms.stock(batch_bk)` | `wms.batch(batch_bk)` | NN |
| `wms.stock(location_type, location_bk)` | `wms.location(location_type, location_bk)` | NN |
| `wms.writeoff_detail(movement_bk)` | `wms.movement(movement_bk)` | NN |
| `wms.writeoff_detail(supplier_bk)` | `wms.supplier(supplier_bk)` | NULL допускается |

## Межсервисные и полиморфные ссылки

| Поле | Логический адресат | Условие |
|---|---|---|
| `wms.batch.sku` | `catalog.sku.sku` | Первичный владелец SKU — каталог. |
| `wms.purchase_line.sku` | `catalog.sku.sku` | Закупаемый SKU. |
| `wms.location.location_bk` | `pos.pharmacy.pharmacy_bk для pharmacy` | Для dc совпадает с dc_bk; ключ локации составной. |
| `wms.movement.external_doc_bk` | `pos.receipt.receipt_bk` | Для продаж и возвратов покупателей; для остальных операций может быть NULL. |

## Ограничения и пояснения

`UNIQUE (sku, series_no)` относится к паре полей партии. Ни SKU, ни номер серии по отдельности не объявлены уникальными.

Связь `movement` → `purchase_line` составная: `(purchase_bk, purchase_line_no)` → `(purchase_bk, line_no)`. Оба поля могут быть NULL для операций без закупки; CHECK запрещает заполнить только одно из них. У приёмки ссылка обязательна по типу движения.

Остаток имеет составной PK `(location_type, location_bk, batch_bk)`. Ссылка на локацию тоже составная: `(location_type, location_bk)` → `location`. `location.dc_bk` допускает NULL в общей схеме: он заполнен для РЦ и отсутствует для аптеки.

`src_type/src_bk` и `dst_type/dst_bk` проверяются как пары; физического FK на `location` у этих полей нет. Допустимые направления заданы CHECK; существование внутренних локаций проверяется при создании остатка триггером. `dispatched_at` допускает NULL в DDL. Генератор заполняет время отгрузки для поставок и перемещений; отдельного NOT NULL или условного ограничения для transfer в схеме нет.

Для любого `writeoff` к COMMIT требуется ровно одна строка `writeoff_detail`, а для других типов движения объяснение запрещено. `supplier_bk` обязателен только при `reason = supplier_return`; получатель проверяется по ранее принятой партии. Брак и просрочка различаются причинами; просроченное списание возможно только после `expiry_date`.

Остатки меняются триггером в той же транзакции, что и движение. CHECK не допускает отрицательного значения. Приложению запрещено напрямую менять остатки; исправление оформляется компенсирующим движением.
