# POS

Физическая схема БД `pos_service_db`. Модель разделена на блоки; повторяющиеся таблицы показаны полностью в каждом из них.

`PK` — первичный ключ, `FK` — внешний ключ в той же БД. Несколько полей с `PK` образуют один составной ключ. `NN` — `NOT NULL` (включая поля PK), `NULL` — ограничение `NOT NULL` в DDL не задано. Точность `numeric(p,s)` указана в комментарии к полю.

Все поля таблиц приведены явно, включая `created_at` и `updated_at`. У обоих тип `timestamptz`, обязательность NN и `DEFAULT clock_timestamp()`; `updated_at` меняется автоматически триггером `core.touch_row`. `GEN` — вычисляемое поле. Общие технические таблицы каждой БД показаны [отдельно](core.md).

Сплошная линия — FK входит в PK дочерней таблицы; пунктир — не входит. На стороне родителя указано «ровно один» или «ноль/один» по обязательности FK, на стороне дочерних строк — допустимое число ссылок. FK сам по себе не требует, чтобы у родителя уже были дочерние строки. Дополнительные требования триггеров описаны ниже.

Метки `BK` у полей обозначают логические межсервисные ссылки. Их адресаты описаны после диаграмм.

## Аптеки, кассы и смены

```mermaid
erDiagram
    direction TB
    PHARMACY ||--o{ PHARMACY_HISTORY : "pharmacy_bk"
    PHARMACY ||..o{ CASH_REGISTER : "pharmacy_bk"
    CASH_REGISTER ||..o{ SHIFT : "register_bk"
    CASHIER ||..o{ SHIFT : "cashier_bk"
    PHARMACY {
        text pharmacy_bk PK "NN"
        text pharmacy_name "NN"
        text region "NN"
        text city "NN"
        text address "NN"
        date opened_at "NN"
        date closed_at "NULL"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PHARMACY_HISTORY {
        text pharmacy_bk PK,FK "NN"
        timestamptz valid_from PK "NN"
        timestamptz valid_to "NULL"
        jsonb attributes "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CASH_REGISTER {
        text register_bk PK "NN"
        text pharmacy_bk FK "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CASHIER {
        text cashier_bk PK "NN"
        text cashier_name "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    SHIFT {
        text shift_bk PK "NN"
        text register_bk FK "NN"
        text cashier_bk FK "NN"
        timestamptz opened_at "NN"
        timestamptz closed_at "NULL"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Документы, позиции и оплаты

```mermaid
erDiagram
    direction TB
    PRESCRIPTION |o..o{ RECEIPT : "prescription_bk"
    RECEIPT ||--o{ RECEIPT_LINE : "receipt_bk"
    RECEIPT ||--o{ PAYMENT : "receipt_bk"
    RECEIPT {
        text receipt_bk PK "NN"
        text pharmacy_bk FK "NN"
        text customer_bk "NULL; BK: CRM.customer"
        text cashier_bk FK "NN"
        text shift_bk FK "NN"
        timestamptz receipt_dt "NN"
        text doc_type "NN"
        text parent_receipt_bk FK "NULL; refund: NN"
        numeric total_amount "NN; numeric(16,2)"
        numeric discount_amount "NN; numeric(16,2)"
        text currency "NN"
        text prescription_bk FK "NULL"
        bigint revision "NN"
        boolean check_pending "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    RECEIPT_LINE {
        text receipt_bk PK,FK "NN"
        integer line_no PK "NN"
        text sku "NN; BK: CAT.sku"
        text batch_bk FK "NN"
        text price_bk FK "NN"
        numeric quantity "NN; numeric(14,3)"
        numeric unit_price "NN; numeric(14,2)"
        numeric line_discount "NN; numeric(16,2)"
        numeric line_amount "NN; numeric(16,2)"
        boolean is_rx_snapshot "NN"
        text sku_name_snapshot "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PAYMENT {
        text receipt_bk PK,FK "NN"
        integer payment_no PK "NN"
        text payment_method "NN"
        numeric amount "NN; numeric(16,2)"
        text currency "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PRESCRIPTION {
        text prescription_bk PK "NN"
        text customer_bk "NULL; BK: CRM.customer"
        timestamptz issued_at "NN"
        timestamptz expires_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Ссылки заголовка документа

```mermaid
erDiagram
    direction TB
    PHARMACY ||..o{ RECEIPT : "pharmacy_bk"
    CASHIER ||..o{ RECEIPT : "cashier_bk"
    SHIFT ||..o{ RECEIPT : "shift_bk"
    RECEIPT |o..o{ RECEIPT : "parent_receipt_bk"
    PRESCRIPTION |o..o{ RECEIPT : "prescription_bk"
    CASHIER ||..o{ SHIFT : "cashier_bk"
    RECEIPT {
        text receipt_bk PK "NN"
        text pharmacy_bk FK "NN"
        text customer_bk "NULL; BK: CRM.customer"
        text cashier_bk FK "NN"
        text shift_bk FK "NN"
        timestamptz receipt_dt "NN"
        text doc_type "NN"
        text parent_receipt_bk FK "NULL; refund: NN"
        numeric total_amount "NN; numeric(16,2)"
        numeric discount_amount "NN; numeric(16,2)"
        text currency "NN"
        text prescription_bk FK "NULL"
        bigint revision "NN"
        boolean check_pending "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PHARMACY {
        text pharmacy_bk PK "NN"
        text pharmacy_name "NN"
        text region "NN"
        text city "NN"
        text address "NN"
        date opened_at "NN"
        date closed_at "NULL"
        boolean is_active "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CASHIER {
        text cashier_bk PK "NN"
        text cashier_name "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    SHIFT {
        text shift_bk PK "NN"
        text register_bk FK "NN"
        text cashier_bk FK "NN"
        timestamptz opened_at "NN"
        timestamptz closed_at "NULL"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PRESCRIPTION {
        text prescription_bk PK "NN"
        text customer_bk "NULL; BK: CRM.customer"
        timestamptz issued_at "NN"
        timestamptz expires_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Локальные версии каталога и партий

```mermaid
erDiagram
    direction TB
    BATCH_REFERENCE ||..o{ RECEIPT_LINE : "batch_bk"
    PRICE_REFERENCE ||..o{ RECEIPT_LINE : "price_bk"
    RECEIPT_LINE {
        text receipt_bk PK,FK "NN"
        integer line_no PK "NN"
        text sku "NN; BK: CAT.sku"
        text batch_bk FK "NN"
        text price_bk FK "NN"
        numeric quantity "NN; numeric(14,3)"
        numeric unit_price "NN; numeric(14,2)"
        numeric line_discount "NN; numeric(16,2)"
        numeric line_amount "NN; numeric(16,2)"
        boolean is_rx_snapshot "NN"
        text sku_name_snapshot "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    BATCH_REFERENCE {
        text batch_bk PK "NN; BK: WMS.batch"
        text sku "NN; BK: CAT.sku"
        date manufactured_date "NN"
        date expiry_date "NN"
        timestamptz received_at "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    SKU_REFERENCE {
        text sku PK "NN; BK: CAT.sku"
        timestamptz valid_from PK "NN"
        timestamptz valid_to "NULL"
        text sku_name "NN"
        boolean is_rx "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PRICE_REFERENCE {
        text price_bk PK "NN; BK: CAT.price"
        text sku "NN; BK: CAT.sku"
        text price_scope "NN"
        text scope_bk "NN; BK: pharmacy / region / ALL"
        numeric price "NN; numeric(14,2)"
        text currency "NN"
        timestamptz valid_from "NN"
        timestamptz valid_to "NULL"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Все физические FK

| Дочерняя таблица и поля | Родительская таблица и поля | Обязательность |
|---|---|---|
| `pos.cash_register(pharmacy_bk)` | `pos.pharmacy(pharmacy_bk)` | NN |
| `pos.payment(receipt_bk)` | `pos.receipt(receipt_bk)` | NN |
| `pos.pharmacy_history(pharmacy_bk)` | `pos.pharmacy(pharmacy_bk)` | NN |
| `pos.receipt(pharmacy_bk)` | `pos.pharmacy(pharmacy_bk)` | NN |
| `pos.receipt(cashier_bk)` | `pos.cashier(cashier_bk)` | NN |
| `pos.receipt(shift_bk)` | `pos.shift(shift_bk)` | NN |
| `pos.receipt(parent_receipt_bk)` | `pos.receipt(receipt_bk)` | NULL допускается |
| `pos.receipt(prescription_bk)` | `pos.prescription(prescription_bk)` | NULL допускается |
| `pos.receipt_line(receipt_bk)` | `pos.receipt(receipt_bk)` | NN |
| `pos.receipt_line(batch_bk)` | `pos.batch_reference(batch_bk)` | NN |
| `pos.receipt_line(price_bk)` | `pos.price_reference(price_bk)` | NN |
| `pos.shift(register_bk)` | `pos.cash_register(register_bk)` | NN |
| `pos.shift(cashier_bk)` | `pos.cashier(cashier_bk)` | NN |

## Межсервисные и полиморфные ссылки

| Поле | Логический адресат | Условие |
|---|---|---|
| `pos.receipt.customer_bk` | `crm.customer.customer_bk` | Покупка без карты допускает NULL. |
| `pos.prescription.customer_bk` | `crm.customer.customer_bk` | NULL означает рецепт без привязки к клиенту. |
| `pos.batch_reference.batch_bk` | `wms.batch.batch_bk` | Локальная копия партии. |
| `pos.batch_reference.sku` | `catalog.sku.sku` | SKU партии из WMS. |
| `pos.sku_reference.sku` | `catalog.sku.sku` | Версии SKU в локальной копии POS. |
| `pos.price_reference.price_bk` | `catalog.price.price_bk` | Копия версии цены каталога. |
| `pos.price_reference.sku` | `catalog.sku.sku` | SKU версии цены. |
| `pos.receipt_line.sku` | `catalog.sku.sku` | Версия SKU проверяется триггером на дату продажи. |
| `pos.price_reference.scope_bk` | `pos.pharmacy.pharmacy_bk / код региона / ALL` | Область локальной версии цены. |

## Ограничения и пояснения

`receipt.currency` обязательна, денежные поля имеют фиксированную точность. Документ связан с аптекой, кассиром и сменой отдельными FK. Триггер дополнительно проверяет согласованность этих ссылок и открытость смены.

`parent_receipt_bk` — настоящий FK на ту же таблицу `receipt`. Для продажи он NULL, для возврата обязателен. `prescription_bk` допускает NULL в общей модели, но для рецептурной позиции рецепт обязателен. Совокупный объём возвратов проверяется относительно исходной продажи.

`batch_reference`, `sku_reference` и `price_reference` — таблицы внутри POS. Физические FK позиции ведут к локальным партиям и ценам. У `receipt_line.sku` нет FK к `sku_reference`: подходящая версия выбирается по SKU и времени и проверяется триггером. Между `batch_reference.sku`, `price_reference.sku` и `sku_reference` физического FK также нет.

Позиция сохраняет цену, название и рецептурность на момент продажи. Суммы позиций и оплат проверяются отложенными constraint triggers при COMMIT. Поля `revision` и `check_pending` служат для сериализации возвратов и однократной проверки документа; приложение не может сбрасывать флаг проверки.
