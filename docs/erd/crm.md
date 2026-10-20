# CRM

`PK` — первичный ключ, `FK` — ссылка внутри сервиса, `UK` — уникальность, `NN` — NOT NULL. Технические `created_at` и `updated_at` обязательны во всех таблицах.

```mermaid
erDiagram
    CUSTOMER ||--o{ CONTACT : contacts
    CUSTOMER ||--o{ CONSENT : consents
    CUSTOMER ||--o{ LOYALTY_CARD : cards
    CUSTOMER ||--|{ CUSTOMER_HISTORY : versions
    LOYALTY_LEVEL o|--o{ CUSTOMER : level
    CUSTOMER ||--o{ PRIVACY_EVENT : anonymization
    CUSTOMER {
        text customer_bk PK "NN"
        text full_name "nullable"
        int birth_year "nullable"
        text sex "nullable"
        text city "nullable"
        text region "nullable"
        text level_bk FK "nullable"
        timestamptz registered_at "NN"
        boolean is_deleted "NN"
    }
    CONTACT {
        text contact_bk PK "NN"
        text customer_bk FK "NN"
        text contact_type "NN"
        text contact_value "nullable after anonymization"
        boolean is_deleted "NN"
    }
    CONSENT {
        text consent_bk PK "NN"
        text customer_bk FK "NN"
        text consent_type "NN"
        timestamptz granted_at "NN"
        timestamptz revoked_at "nullable"
    }
    LOYALTY_CARD {
        text card_bk PK "NN"
        text customer_bk FK "NN"
        timestamptz issued_at "NN"
        timestamptz closed_at "nullable"
        text status "NN"
        numeric bonus_balance "NN"
    }
    CUSTOMER_HISTORY {
        text customer_bk PK,FK "NN"
        timestamptz valid_from PK "NN"
        timestamptz valid_to "nullable"
        jsonb attributes "NN"
    }
    LOYALTY_LEVEL {
        text level_bk PK "NN"
        text level_name "NN"
        numeric threshold_amount "NN"
        boolean is_deleted "NN"
    }
    PRIVACY_EVENT {
        text event_bk PK "NN"
        text customer_bk FK "NN"
        text event_type "NN"
    }
```

Межсервисная ссылка: `POS.receipt.customer_bk` логически ссылается на `CRM.customer.customer_bk`; физического FK между базами нет. Покупка без карты допускает NULL.

У клиента не больше одной активной карты и одного действующего согласия каждого типа. История города и уровня хранится интервалами. Обезличивание очищает контакты и историю, закрывает карты и согласия, создаёт событие для последующей обработки в DWH. Удалённый клиент и его карты скрыты из контракта.
