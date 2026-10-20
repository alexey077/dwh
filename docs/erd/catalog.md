# Каталог

`PK` — первичный ключ, `FK` — ссылка внутри каталога, `NN` — NOT NULL. Во всех таблицах есть обязательные `created_at`, `updated_at`.

```mermaid
erDiagram
    MANUFACTURER ||--o{ SKU : produces
    DRUG_FORM o|--o{ SKU : form
    SKU ||--o{ SKU_INN : substances
    INN ||--o{ SKU_INN : ingredients
    SKU ||--|{ SKU_HISTORY : versions
    SKU ||--o{ PRICE : prices
    MANUFACTURER {
        text manufacturer_bk PK "NN"
        text manufacturer_name "NN"
        text country "NN"
        boolean is_deleted "NN"
    }
    DRUG_FORM {
        text form_bk PK "NN"
        text form_name "NN"
        boolean is_deleted "NN"
    }
    INN {
        text inn_bk PK "NN"
        text inn_name "NN"
        boolean is_deleted "NN"
    }
    SKU {
        text sku PK "NN"
        text sku_name "NN"
        text manufacturer_bk FK "NN"
        text form_bk FK "nullable"
        text category "NN"
        boolean is_rx "NN"
        boolean is_vital "NN"
        numeric pack_qty "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
    }
    SKU_INN {
        text sku PK,FK "NN"
        text inn_bk PK,FK "NN"
        boolean is_deleted "NN"
    }
    SKU_HISTORY {
        text sku PK,FK "NN"
        timestamptz valid_from PK "NN"
        timestamptz valid_to "nullable"
        text sku_name "NN"
        text manufacturer_bk FK "NN"
        text form_bk FK "nullable"
        text category "NN"
        boolean is_rx "NN"
        boolean is_vital "NN"
        numeric pack_qty "NN"
        boolean is_active "NN"
        boolean is_deleted "NN"
        boolean is_current "NN, generated"
    }
    PRICE {
        text price_bk PK "NN"
        text sku FK "NN"
        text price_scope "NN"
        text scope_bk "NN, logical BK"
        numeric price "NN"
        text currency "NN"
        timestamptz valid_from "NN"
        timestamptz valid_to "nullable"
        boolean is_current "NN, generated"
    }
```

`SKU` логически используется в POS и WMS. `PRICE.scope_bk` содержит `ALL`, код региона или `POS.pharmacy.pharmacy_bk`, в зависимости от `price_scope`. Между базами нет FK.

Для одного SKU и одной области цены интервалы `[valid_from, valid_to)` не пересекаются. Текущая версия определяется через `valid_to IS NULL`; время чтения не влияет на контракт. Функция `catalog.price_at` выбирает цену в порядке аптека → регион → сеть.
