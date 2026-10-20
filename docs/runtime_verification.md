# Проверка Docker-стенда — 20.10.2026

Проверены переданные пользователем `check_after_failures.json` и журнал от `2026-10-20T10:32:59.223451+00:00`. Это разбор фактического запуска на пользовательском Docker Desktop; в окружении подготовки решения Docker Engine по-прежнему отсутствует.

**138 из 139 проверок успешно. Исходная автоматическая оценка — 19/21.** Единственная ошибка — `ha.running`; её причина и влияние на оценку разобраны в [заметке о чекере](checker_note.md). Исходные результаты не исправлялись.

SHA256 исходного JSON: `3ba0dd3f32f872db726275d25ebc839585be4df9b15d2fb586522270326acae2`.

SHA256 сырого журнала: `b43147a0cb0f9523f8b42ced746b365291ec9b1851e22c5164eeb2f73dd4235f`. [Точная копия журнала](experiments/20261020T103259Z-complete.md); [журнал с пояснениями](failover_journal.md).

## Разделы чекера

| Раздел | Успешно | Всего |
|---|---:|---:|
| contract | 14 | 14 |
| keys | 27 | 27 |
| volume | 14 | 14 |
| dq | 23 | 23 |
| cross | 10 | 10 |
| repl | 9 | 9 |
| inv | 15 | 15 |
| cdc | 16 | 16 |
| ha | 5 | 6 |
| realism | 5 | 5 |

## Исходные баллы

| Блок | Баллы в JSON |
|---|---:|
| база: стенд и контракт (4) | 4.0 |
| база: данные и целостность (4) | 4.0 |
| база: реплика и пул (2) | 2.0 |
| инварианты (5) | 5.0 |
| HA-кластер (2) | 0.0 |
| CDC-готовность (1 из 2) | 1.0 |
| карта склейки (1 из 2) | Не выставлены: ручная проверка |
| журнал решений ADR (1) | Не выставлены: ручная проверка |
| бонус: реалистичные данные (1) | 1.0 |
| бонус: журнал отказоустойчивости (1) | Не выставлены: ручная проверка |
| бонус: кворумный etcd (1) | Не выставлены: ручная проверка |
| бонус: одиночное выполнение (2) | 2.0 |

Четыре ручных балла относятся к карте склейки, ADR, журналу и кворумному etcd. При их полном зачёте и без изменения решения по HA получится 23/25. Для 25/25 преподаватель должен также признать расхождение чекера и засчитать 2 балла HA. Это возможный результат, а не уже выставленная оценка.

## Что подтверждено

- Контракт и ключи всех 14 представлений, все минимумы объёмов, C01–C23, X01–X10, I1–I12 и P1–P2.
- Две физические streaming-реплики и два активных физических слота; WAL receiver, догон реплики после дельты и равенство всех 14 отпечатков.
- Пул работает; HAProxy направляет запись на лидера, чтение на реплику. В API один лидер и две работающие реплики.
- Во всех четырёх базах подтверждены logical WAL, публикации всех таблиц и пригодный REPLICA IDENTITY. CDC-консьюмеры в это ДЗ не входят и не запускались.
- Все пять признаков реалистичности прошли. Секция volume измерила 24 500 документов до следующей seed_delta; затем repl.seed_delta_effect зафиксировала рост ещё на 500.

## Эксперименты

| Опыт | Результат из журнала |
|---|---|
| Э1 | 8 528 подтверждений за 60,014 с; 0 ошибок; 142,101 TPS; median 3,850 мс; p95 10,085 мс |
| Э2 | pg3 → pg1; RTO 34,953 с; 276 ошибок; потерянных подтверждённых ключей 0 |
| Э3 | pg3 вернулся репликой за 8,651 с; WAL от старта receiver 234 456 байт; способ начального восстановления требует полного лога |
| Э4 | pg1 → pg2; RTO 4,060 с; 186 ошибок; аварийное переключение было в 8,61 раза дольше |
| Э5 | sync: 140,700 TPS; p95 9,712 мс; RTO 32,955 с; потерянных подтверждённых ключей 0 |
| Э6 | один etcd: 1 479 подтверждений, 0 ошибок; два etcd: ошибка записи через 23,716 с, SELECT на реплике доступен |
| Э7 | 160 клиентов: 82 ошибки напрямую, 0 через PgBouncer; медиана подключения 199,748 и 79,424 мс |

Три RTO независимо пересчитаны по monotonic timestamps последних старых и первых новых подтверждений в сыром журнале и совпали с таблицами. Полные массивы событий и подтверждённых ключей не переданы: median, p95, общее число ошибок и проверка потерь взяты из результата скрипта и независимо по всем событиям не пересчитывались. Нулевые потери async в одном опыте не означают гарантии отсутствия потерь при других авариях.

## Что ещё нужно для сдачи

1. Уточнить способ возврата старых лидеров полными фрагментами логов. `pg_rewind_call_in_log=False` отражает поиск в последних 80 строках, а не доказанное отсутствие rewind. Команды приведены в журнале.
2. Показать преподавателю расхождение `ha.running`: официальный чекер пока снимает 2 балла, хотя streaming-реплики и маршруты работают. Текущий master курса проверен, этот код в нём не исправлен.
3. Сделать репозиторий приватным, опубликовать ветку hw1 и выдать доступ mgcrp. На последней проверке GitHub репозиторий публичный, существует только main. Публикация новых рабочих материалов в открытый репозиторий ранее заблокирована автоматической проверкой.
4. Проверить опубликованный чистый клон и CI. Представленные результаты относятся к полученному пользователем архиву, а не к уже опубликованной ветке. Отдельная многопроцессная проверка конкурентных списаний и возвратов не представлена.

## Все проверки без изменения результата

| Раздел | ID | Результат | Подробность исходного отчёта |
|---|---|---|---|
| contract | `crm.v_customer` | OK | — |
| contract | `crm.v_loyalty_card` | OK | — |
| contract | `catalog.v_sku` | OK | — |
| contract | `catalog.v_price` | OK | — |
| contract | `pos.v_pharmacy` | OK | — |
| contract | `pos.v_receipt` | OK | — |
| contract | `pos.v_receipt_line` | OK | — |
| contract | `pos.v_payment` | OK | — |
| contract | `wms.v_supplier` | OK | — |
| contract | `wms.v_distribution_center` | OK | — |
| contract | `wms.v_batch` | OK | — |
| contract | `wms.v_purchase_line` | OK | — |
| contract | `wms.v_movement` | OK | — |
| contract | `wms.v_stock` | OK | — |
| keys | `crm.v_customer.notnull` | OK | — |
| keys | `crm.v_customer.uk.customer_bk` | OK | — |
| keys | `crm.v_loyalty_card.notnull` | OK | — |
| keys | `crm.v_loyalty_card.uk.card_bk` | OK | — |
| keys | `catalog.v_sku.notnull` | OK | — |
| keys | `catalog.v_sku.uk.sku` | OK | — |
| keys | `catalog.v_price.notnull` | OK | — |
| keys | `pos.v_pharmacy.notnull` | OK | — |
| keys | `pos.v_pharmacy.uk.pharmacy_bk` | OK | — |
| keys | `pos.v_receipt.notnull` | OK | — |
| keys | `pos.v_receipt.uk.receipt_bk` | OK | — |
| keys | `pos.v_receipt_line.notnull` | OK | — |
| keys | `pos.v_receipt_line.uk.receipt_bk_line_no` | OK | — |
| keys | `pos.v_payment.notnull` | OK | — |
| keys | `pos.v_payment.uk.receipt_bk_payment_no` | OK | — |
| keys | `wms.v_supplier.notnull` | OK | — |
| keys | `wms.v_supplier.uk.supplier_bk` | OK | — |
| keys | `wms.v_distribution_center.notnull` | OK | — |
| keys | `wms.v_distribution_center.uk.dc_bk` | OK | — |
| keys | `wms.v_batch.notnull` | OK | — |
| keys | `wms.v_batch.uk.batch_bk` | OK | — |
| keys | `wms.v_purchase_line.notnull` | OK | — |
| keys | `wms.v_purchase_line.uk.purchase_bk_line_no` | OK | — |
| keys | `wms.v_movement.notnull` | OK | — |
| keys | `wms.v_movement.uk.movement_bk` | OK | — |
| keys | `wms.v_stock.notnull` | OK | — |
| keys | `wms.v_stock.uk.location_type_location_bk_batch_bk` | OK | — |
| volume | `crm.v_customer` | OK | фактически 2400 |
| volume | `crm.v_loyalty_card` | OK | фактически 2100 |
| volume | `catalog.v_sku` | OK | фактически 600 |
| volume | `catalog.v_price` | OK | фактически 2016 |
| volume | `pos.v_pharmacy` | OK | фактически 36 |
| volume | `pos.v_receipt` | OK | фактически 24500 |
| volume | `pos.v_receipt_line` | OK | фактически 95795 |
| volume | `pos.v_payment` | OK | фактически 29150 |
| volume | `wms.v_supplier` | OK | фактически 12 |
| volume | `wms.v_distribution_center` | OK | фактически 4 |
| volume | `wms.v_batch` | OK | фактически 3600 |
| volume | `wms.v_purchase_line` | OK | фактически 7200 |
| volume | `wms.v_movement` | OK | фактически 124595 |
| volume | `wms.v_stock` | OK | фактически 25200 |
| dq | `C01` | OK | — |
| dq | `C02` | OK | — |
| dq | `C03` | OK | — |
| dq | `C04` | OK | — |
| dq | `C05` | OK | — |
| dq | `C06` | OK | — |
| dq | `C07` | OK | — |
| dq | `C08` | OK | — |
| dq | `C09` | OK | — |
| dq | `C10` | OK | — |
| dq | `C11` | OK | — |
| dq | `C12` | OK | — |
| dq | `C13` | OK | — |
| dq | `C14` | OK | — |
| dq | `C15` | OK | — |
| dq | `C16` | OK | — |
| dq | `C17` | OK | — |
| dq | `C18` | OK | — |
| dq | `C19` | OK | — |
| dq | `C20` | OK | — |
| dq | `C21` | OK | — |
| dq | `C22` | OK | — |
| dq | `C23` | OK | — |
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
| repl | `pg_stat_replication` | OK | строк в pg_stat_replication: 2; pg1:streaming/async; pg2:streaming/async |
| repl | `slots` | OK | pg1(physical, active=True); pg2(physical, active=True) |
| repl | `in_recovery` | OK | — |
| repl | `wal_receiver` | OK | status=streaming |
| repl | `seed_delta` | OK | — |
| repl | `seed_delta_effect` | OK | чеков добавлено: 500 |
| repl | `catchup` | OK | master_lsn=0/1855D928 |
| repl | `digests` | OK | — |
| repl | `pooler` | OK | — |
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
| inv | `P1` | OK | — |
| inv | `P2` | OK | — |
| inv | `leakage` | OK | изменились:  |
| cdc | `crm.wal_level` | OK | фактически logical |
| cdc | `crm.publication` | OK | crm_cdc(all=True) |
| cdc | `crm.pub_coverage` | OK | FOR ALL TABLES |
| cdc | `crm.replica_identity` | OK | — |
| cdc | `catalog.wal_level` | OK | фактически logical |
| cdc | `catalog.publication` | OK | catalog_cdc(all=True) |
| cdc | `catalog.pub_coverage` | OK | FOR ALL TABLES |
| cdc | `catalog.replica_identity` | OK | — |
| cdc | `pos.wal_level` | OK | фактически logical |
| cdc | `pos.publication` | OK | pos_cdc(all=True) |
| cdc | `pos.pub_coverage` | OK | FOR ALL TABLES |
| cdc | `pos.replica_identity` | OK | — |
| cdc | `wms.wal_level` | OK | фактически logical |
| cdc | `wms.publication` | OK | wms_cdc(all=True) |
| cdc | `wms.pub_coverage` | OK | FOR ALL TABLES |
| cdc | `wms.replica_identity` | OK | — |
| ha | `members` | OK | pg1:replica/streaming; pg2:replica/streaming; pg3:leader/running |
| ha | `leader` | OK | лидеров: 1 |
| ha | `running` | FAIL | running 1 из 3 |
| ha | `haproxy_rw_dsn` | OK | pg_is_in_recovery() = False |
| ha | `haproxy_ro_dsn` | OK | pg_is_in_recovery() = True |
| ha | `journal` | OK (примечание чекера) | содержимое проверяется преподавателем вручную |
| realism | `weekday` | OK | max/min по дням недели = 2.04 (нужно >= 1.25) |
| realism | `longtail` | OK | топ-10% SKU дают 66.1% выручки (нужно >= 50%) |
| realism | `pharmacy_cv` | OK | коэффициент вариации = 0.895 (нужно >= 0.15) |
| realism | `no_card` | OK | фактически 44.9% |
| realism | `refunds` | OK | фактически 3.00% |
