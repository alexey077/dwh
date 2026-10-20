# WMS: закупки и складской учёт

База `wms_service_db` хранит поставщиков, закупки, партии товаров, движения и остатки. Товар учитывается по партиям, поэтому можно проследить его путь от поставщика до аптеки и проверить срок годности.

[Обозначения на схемах](core.md#как-читать-схемы) и [технические поля](core.md#даты-создания-и-изменения) общие для всех сервисов.

## Закупки и партии

Заказ поставщику хранится в `purchase`. Он связан с поставщиком из `supplier` и распределительным центром из `distribution_center`, который должен принять товар. В заказе указаны даты оформления и ожидаемой поставки, а также валюта.

Позиции заказа хранятся в `purchase_line`: что заказали, в каком количестве и по какой закупочной цене. Позиция определяется номером заказа и номером строки — `(purchase_bk, line_no)`.

Таблица `batch` описывает партию товара: SKU, номер серии производителя, даты производства, годности и приёмки. Номер серии уникален в пределах SKU. Это означает, что повторить пару `(sku, series_no)` нельзя, но одинаковые номера серий у разных товаров допустимы.

До приёмки поля `batch_bk` и `received_at` в позиции заказа могут быть пустыми. Когда товар принят, они заполняются вместе и связывают позицию с конкретной партией. База проверяет соответствие SKU и срока годности.

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

## Где хранится товар и как устроен остаток

Таблица `location` объединяет два вида мест хранения: распределительные центры (`dc`) и аптеки (`pharmacy`). Место определяется парой `(location_type, location_bk)`. У записи распределительного центра заполнен `dc_bk`, который ссылается на `distribution_center`; у записи аптеки это поле пустое.

Таблица `stock` хранит количество одной партии в одном месте. Поэтому её первичный ключ состоит из трёх полей: `(location_type, location_bk, batch_bk)`. Первые два поля вместе ссылаются на `location`, а третье — на `batch`.

Остатки меняются автоматически при записи движения. Если товара не хватает, PostgreSQL отклоняет операцию: отрицательный остаток запрещён. Приложение не может напрямую исправить количество в `stock`; изменение оформляется отдельным движением.

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

## Движения, возвраты поставщику и списания

В `movement` записывается каждая операция с партией: приёмка, перемещение, продажа, возврат покупателя или списание. В записи указаны партия, количество, отправитель, получатель и время операции.

Приёмка обязательно связана с позицией закупки. Внешний ключ состоит из двух полей: `(purchase_bk, purchase_line_no)` ссылается на `(purchase_bk, line_no)` в `purchase_line`. У операций без закупки оба поля могут быть пустыми. Заполнить только одно из них нельзя.

Поля `src_type` и `dst_type` задают тип отправителя и получателя, а `src_bk` и `dst_bk` — их коды. Для мест хранения эти коды проверяются при обновлении остатка. Прямых FK от этих полей к `location` нет.

Время отгрузки записывается в `dispatched_at`, а время приёмки или завершения операции — в `moved_at`. Для поставок и перемещений генератор заполняет оба поля, чтобы по ним можно было посчитать время в пути. Сама таблица при этом допускает пустой `dispatched_at`.

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

Возврат поставщику и списания оформляются движением типа `writeoff`. Причина хранится в `writeoff_detail`:

| Причина | Значение `reason` | Дополнительное условие |
|---|---|---|
| Возврат поставщику | `supplier_return` | Указан поставщик, от которого ранее приняли эту партию |
| Брак | `damaged` | Поставщик в этой записи не указывается |
| Истёкший срок годности | `expired` | Дата списания позже даты годности партии; поставщик не указывается |

Для каждого движения `writeoff` нужна ровно одна запись с причиной. Для других типов движения такая запись запрещена. База проверяет это перед завершением транзакции, поэтому движение и его причину можно добавить вместе.

## Связи с каталогом и POS

| Что связываем | Поле в WMS | Откуда берётся код |
|---|---|---|
| Товар партии | `batch.sku` | `catalog.sku.sku` |
| Товар в закупке | `purchase_line.sku` | `catalog.sku.sku` |
| Аптеку как место хранения | `location.location_bk` при `location_type = pharmacy` | `pos.pharmacy.pharmacy_bk` |
| Продажу или возврат покупателя | `movement.external_doc_bk` | `pos.receipt.receipt_bk` |

Это связи по постоянным кодам между разными базами. Для них нет физических внешних ключей. У движений продажи и возврата покупателя `external_doc_bk` обязателен; у остальных операций он может быть пустым.
