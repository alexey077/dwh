# CRM

Физическая схема БД `crm_service_db`. Модель разделена на блоки; повторяющиеся таблицы показаны полностью в каждом из них.

`PK` — первичный ключ, `FK` — внешний ключ в той же БД. Несколько полей с `PK` образуют один составной ключ. `NN` — `NOT NULL` (включая поля PK), `NULL` — ограничение `NOT NULL` в DDL не задано. Точность `numeric(p,s)` указана в комментарии к полю.

Все поля таблиц приведены явно, включая `created_at` и `updated_at`. У обоих тип `timestamptz`, обязательность NN и `DEFAULT clock_timestamp()`; `updated_at` меняется автоматически триггером `core.touch_row`. `GEN` — вычисляемое поле. Общие технические таблицы каждой БД показаны [отдельно](core.md).

Сплошная линия — FK входит в PK дочерней таблицы; пунктир — не входит. На стороне родителя указано «ровно один» или «ноль/один» по обязательности FK, на стороне дочерних строк — допустимое число ссылок. FK сам по себе не требует, чтобы у родителя уже были дочерние строки. Дополнительные требования триггеров описаны ниже.

Метки `BK` у полей обозначают логические межсервисные ссылки. Их адресаты описаны после диаграмм.

## Клиент, уровень и история

```mermaid
erDiagram
    direction TB
    LOYALTY_LEVEL |o..o{ CUSTOMER : "level_bk"
    CUSTOMER ||--o{ CUSTOMER_HISTORY : "customer_bk"
    CUSTOMER ||..o{ CONTACT : "customer_bk"
    LOYALTY_LEVEL {
        text level_bk PK "NN"
        text level_name "NN"
        numeric threshold_amount "NN; numeric(14,2)"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CUSTOMER {
        text customer_bk PK "NN"
        text full_name "NULL"
        integer birth_year "NULL"
        text sex "NULL"
        text city "NULL"
        text region "NULL"
        text level_bk FK "NULL"
        timestamptz registered_at "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CUSTOMER_HISTORY {
        text customer_bk PK,FK "NN"
        timestamptz valid_from PK "NN"
        timestamptz valid_to "NULL"
        jsonb attributes "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CONTACT {
        text contact_bk PK "NN"
        text customer_bk FK "NN"
        text contact_type "NN"
        text contact_value "NULL"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Карты, согласия и обезличивание

```mermaid
erDiagram
    direction TB
    CUSTOMER ||..o{ LOYALTY_CARD : "customer_bk"
    CUSTOMER ||..o{ CONSENT : "customer_bk"
    CUSTOMER ||..o{ PRIVACY_EVENT : "customer_bk"
    CUSTOMER {
        text customer_bk PK "NN"
        text full_name "NULL"
        integer birth_year "NULL"
        text sex "NULL"
        text city "NULL"
        text region "NULL"
        text level_bk FK "NULL"
        timestamptz registered_at "NN"
        boolean is_deleted "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    LOYALTY_CARD {
        text card_bk PK "NN"
        text customer_bk FK "NN"
        timestamptz issued_at "NN"
        timestamptz closed_at "NULL"
        text status "NN"
        numeric bonus_balance "NN; numeric(14,2)"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    CONSENT {
        text consent_bk PK "NN"
        text customer_bk FK "NN"
        text consent_type "NN"
        timestamptz granted_at "NN"
        timestamptz revoked_at "NULL"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
    PRIVACY_EVENT {
        text event_bk PK "NN"
        text customer_bk FK "NN"
        text event_type "NN"
        timestamptz created_at "NN"
        timestamptz updated_at "NN"
    }
```

## Все физические FK

| Дочерняя таблица и поля | Родительская таблица и поля | Обязательность |
|---|---|---|
| `crm.consent(customer_bk)` | `crm.customer(customer_bk)` | NN |
| `crm.contact(customer_bk)` | `crm.customer(customer_bk)` | NN |
| `crm.customer(level_bk)` | `crm.loyalty_level(level_bk)` | NULL допускается |
| `crm.customer_history(customer_bk)` | `crm.customer(customer_bk)` | NN |
| `crm.loyalty_card(customer_bk)` | `crm.customer(customer_bk)` | NN |
| `crm.privacy_event(customer_bk)` | `crm.customer(customer_bk)` | NN |

## Ограничения и пояснения

У клиента не больше одной активной карты и одного действующего согласия каждого типа. Эти ограничения заданы частичными уникальными индексами. История клиента имеет составной PK `(customer_bk, valid_from)`; открытая версия только одна.

Обезличивание сохраняет строку клиента, но очищает персональные атрибуты, контакты и старые версии, закрывает карты и согласия. `privacy_event` передаёт событие будущему DWH. Удалённый клиент и его карты скрываются из контракта.

Обратная межсервисная ссылка: `pos.receipt.customer_bk` и `pos.prescription.customer_bk` используют `crm.customer.customer_bk`; в POS они допускают NULL.
