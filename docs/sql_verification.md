# Проверка SQL и данных — 20.10.2026

Среда: PGlite 0.5.10, pglite-socket 0.2.13. Выполнен неизменённый `hw01/hw01_check.py`, секции `contract,keys,volume,dq,cross,inv,realism`. Это проверка SQL на PostgreSQL в WASM. Docker, физическая репликация и HA здесь не запускались.

До проверки загружены базовые 24 000 документов и две разные дельты по 500. Повтор каждой фиксированной порции не изменил отпечатки 14 представлений. Количества POS/WMS и остатки из журнала сверены; история продаж и закупок покрывает год и текущий опорный месяц.

**Результат: 108/108.**

| Раздел | Проверка | Результат | Подтверждение |
|---|---|---|---|
| contract | `crm.v_customer` | OK | contract.v_customer: состав и типы колонок |
| contract | `crm.v_loyalty_card` | OK | contract.v_loyalty_card: состав и типы колонок |
| contract | `catalog.v_sku` | OK | contract.v_sku: состав и типы колонок |
| contract | `catalog.v_price` | OK | contract.v_price: состав и типы колонок |
| contract | `pos.v_pharmacy` | OK | contract.v_pharmacy: состав и типы колонок |
| contract | `pos.v_receipt` | OK | contract.v_receipt: состав и типы колонок |
| contract | `pos.v_receipt_line` | OK | contract.v_receipt_line: состав и типы колонок |
| contract | `pos.v_payment` | OK | contract.v_payment: состав и типы колонок |
| contract | `wms.v_supplier` | OK | contract.v_supplier: состав и типы колонок |
| contract | `wms.v_distribution_center` | OK | contract.v_distribution_center: состав и типы колонок |
| contract | `wms.v_batch` | OK | contract.v_batch: состав и типы колонок |
| contract | `wms.v_purchase_line` | OK | contract.v_purchase_line: состав и типы колонок |
| contract | `wms.v_movement` | OK | contract.v_movement: состав и типы колонок |
| contract | `wms.v_stock` | OK | contract.v_stock: состав и типы колонок |
| keys | `crm.v_customer.notnull` | OK | contract.v_customer: обязательные колонки без NULL |
| keys | `crm.v_customer.uk.customer_bk` | OK | contract.v_customer: (customer_bk) уникален |
| keys | `crm.v_loyalty_card.notnull` | OK | contract.v_loyalty_card: обязательные колонки без NULL |
| keys | `crm.v_loyalty_card.uk.card_bk` | OK | contract.v_loyalty_card: (card_bk) уникален |
| keys | `catalog.v_sku.notnull` | OK | contract.v_sku: обязательные колонки без NULL |
| keys | `catalog.v_sku.uk.sku` | OK | contract.v_sku: (sku) уникален |
| keys | `catalog.v_price.notnull` | OK | contract.v_price: обязательные колонки без NULL |
| keys | `pos.v_pharmacy.notnull` | OK | contract.v_pharmacy: обязательные колонки без NULL |
| keys | `pos.v_pharmacy.uk.pharmacy_bk` | OK | contract.v_pharmacy: (pharmacy_bk) уникален |
| keys | `pos.v_receipt.notnull` | OK | contract.v_receipt: обязательные колонки без NULL |
| keys | `pos.v_receipt.uk.receipt_bk` | OK | contract.v_receipt: (receipt_bk) уникален |
| keys | `pos.v_receipt_line.notnull` | OK | contract.v_receipt_line: обязательные колонки без NULL |
| keys | `pos.v_receipt_line.uk.receipt_bk_line_no` | OK | contract.v_receipt_line: (receipt_bk, line_no) уникален |
| keys | `pos.v_payment.notnull` | OK | contract.v_payment: обязательные колонки без NULL |
| keys | `pos.v_payment.uk.receipt_bk_payment_no` | OK | contract.v_payment: (receipt_bk, payment_no) уникален |
| keys | `wms.v_supplier.notnull` | OK | contract.v_supplier: обязательные колонки без NULL |
| keys | `wms.v_supplier.uk.supplier_bk` | OK | contract.v_supplier: (supplier_bk) уникален |
| keys | `wms.v_distribution_center.notnull` | OK | contract.v_distribution_center: обязательные колонки без NULL |
| keys | `wms.v_distribution_center.uk.dc_bk` | OK | contract.v_distribution_center: (dc_bk) уникален |
| keys | `wms.v_batch.notnull` | OK | contract.v_batch: обязательные колонки без NULL |
| keys | `wms.v_batch.uk.batch_bk` | OK | contract.v_batch: (batch_bk) уникален |
| keys | `wms.v_purchase_line.notnull` | OK | contract.v_purchase_line: обязательные колонки без NULL |
| keys | `wms.v_purchase_line.uk.purchase_bk_line_no` | OK | contract.v_purchase_line: (purchase_bk, line_no) уникален |
| keys | `wms.v_movement.notnull` | OK | contract.v_movement: обязательные колонки без NULL |
| keys | `wms.v_movement.uk.movement_bk` | OK | contract.v_movement: (movement_bk) уникален |
| keys | `wms.v_stock.notnull` | OK | contract.v_stock: обязательные колонки без NULL |
| keys | `wms.v_stock.uk.location_type_location_bk_batch_bk` | OK | contract.v_stock: (location_type, location_bk, batch_bk) уникален |
| volume | `crm.v_customer` | OK | фактически 2400 |
| volume | `crm.v_loyalty_card` | OK | фактически 2100 |
| volume | `catalog.v_sku` | OK | фактически 600 |
| volume | `catalog.v_price` | OK | фактически 2016 |
| volume | `pos.v_pharmacy` | OK | фактически 36 |
| volume | `pos.v_receipt` | OK | фактически 25000 |
| volume | `pos.v_receipt_line` | OK | фактически 97750 |
| volume | `pos.v_payment` | OK | фактически 29736 |
| volume | `wms.v_supplier` | OK | фактически 12 |
| volume | `wms.v_distribution_center` | OK | фактически 4 |
| volume | `wms.v_batch` | OK | фактически 3600 |
| volume | `wms.v_purchase_line` | OK | фактически 7200 |
| volume | `wms.v_movement` | OK | фактически 126550 |
| volume | `wms.v_stock` | OK | фактически 25200 |
| dq | `C01` | OK | [pos] Сумма чека совпадает с суммой позиций |
| dq | `C02` | OK | [pos] Сумма оплат совпадает с суммой документа |
| dq | `C03` | OK | [pos] line_amount = quantity * unit_price - line_discount |
| dq | `C04` | OK | [pos] Рецептурная позиция не продана без рецепта |
| dq | `C05` | OK | [pos] У возврата есть родительский документ, у продажи - нет |
| dq | `C06` | OK | [pos] Возврат не превышает проданное количество |
| dq | `C07` | OK | [pos] Все позиции ссылаются на существующий документ |
| dq | `C08` | OK | [pos] Чек ссылается на существующую аптеку |
| dq | `C09` | OK | [catalog] Интервалы действия цены не пересекаются |
| dq | `C10` | OK | [catalog] У цены ровно одна текущая версия на область действия |
| dq | `C11` | OK | [catalog] is_current согласован с valid_to |
| dq | `C12` | OK | [catalog] Цены положительны, валюта - трёхбуквенный код |
| dq | `C13` | OK | [wms] Срок годности строго позже даты производства |
| dq | `C14` | OK | [wms] Пара (sku, series_no) уникальна |
| dq | `C15` | OK | [wms] Остатки неотрицательны |
| dq | `C16` | OK | [wms] Перемещение - источник не равен получателю, количество положительно |
| dq | `C17` | OK | [wms] Отгрузка не позже приёмки |
| dq | `C18` | OK | [wms] line_cost = quantity * unit_cost, количество и цена положительны |
| dq | `C19` | OK | [wms] Принятая строка закупки имеет партию и дату приёмки |
| dq | `C20` | OK | [wms] Перемещения и остатки ссылаются на существующие партии |
| dq | `C21` | OK | [crm] Карта ссылается на существующего клиента |
| dq | `C22` | OK | [crm] У клиента не больше одной активной карты |
| dq | `C23` | OK | [crm] Бонусный баланс неотрицателен, закрытая карта не активна |
| cross | `X01` | OK | 0 значений без соответствия |
| cross | `X02` | OK | 0 значений без соответствия |
| cross | `X03` | OK | 0 значений без соответствия |
| cross | `X04` | OK | 0 значений без соответствия |
| cross | `X05` | OK | 0 значений без соответствия |
| cross | `X06` | OK | 0 значений без соответствия |
| cross | `X07` | OK | 0 партий продавались после истечения срока |
| cross | `X08` | OK | 0 из 3000 продаж без действующей цены |
| cross | `X09` | OK | 0 пар (sku, batch_bk) не совпадают со складом |
| cross | `X10` | OK | расхождение 0.09% (допуск 5.0%) |
| inv | `I1` | OK | ERROR:  duplicate key value violates unique constraint "sku_pkey" |
| inv | `I2` | OK | ERROR:  Business key sku.sku is immutable |
| inv | `I3` | OK | ERROR:  I3: receipt T-I3-SALE total does not match its lines |
| inv | `I4` | OK | ERROR:  new row for relation "receipt_line" violates check constraint "receipt_line_check1" |
| inv | `I5` | OK | ERROR:  conflicting key value violates exclusion constraint "price_sku_price_scope_scope_bk_tstzrange_excl" |
| inv | `I6` | OK | ERROR:  duplicate key value violates unique constraint "sku_history_one_current" |
| inv | `I7` | OK | ERROR:  new row for relation "stock" violates check constraint "stock_qty_on_hand_check" |
| inv | `I8` | OK | ERROR:  Cannot sell expired or not yet received batch T-I8-BATCH |
| inv | `I9` | OK | ERROR:  new row for relation "batch" violates check constraint "batch_check1" |
| inv | `I10` | OK | ERROR:  Prescription is required for Rx item |
| inv | `I11` | OK | ERROR:  I11: refunds exceed original sale T-I11-SALE for T-I11-SKU |
| inv | `I12` | OK | ERROR:  I12: receipt T-I12-SALE total does not match its payments |
| inv | `P1` | OK | P1: положительный тест возвращает ok = true |
| inv | `P2` | OK | P2: положительный тест возвращает ok = true |
| inv | `leakage` | OK | изменились:  |
| realism | `weekday` | OK | max/min по дням недели = 2.06 (нужно >= 1.25) |
| realism | `longtail` | OK | топ-10% SKU дают 66.1% выручки (нужно >= 50%) |
| realism | `pharmacy_cv` | OK | коэффициент вариации = 0.891 (нужно >= 0.15) |
| realism | `no_card` | OK | фактически 44.8% |
| realism | `refunds` | OK | фактически 3.00% |

Баллы частичного запуска не являются итоговой оценкой работы: необходим полный прогон на Docker-кластере и ручная проверка документации.
