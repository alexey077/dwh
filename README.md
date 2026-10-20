# Домашнее задание №1. Источники данных аптечной сети

Шутов Алексей (`alexey077`). Работа выполнена индивидуально. Ветка сдачи — `hw1`.

В проекте четыре отдельные базы PostgreSQL: CRM, каталог, POS и WMS. Они хранят клиентов и карты лояльности, товары и историю цен, кассовые документы, закупки и складские движения. Сервисы связываются по постоянным business keys; межбазовых FK нет. Во всех четырёх базах есть схема `contract` с представлениями из задания.

Стенд состоит из трёх узлов PostgreSQL 18 под Patroni, трёх etcd, HAProxy и PgBouncer. По умолчанию репликация асинхронная. HAProxy направляет запись на лидера, чтение — на реплики. PgBouncer работает в режиме transaction.

## Запуск и проверка

Нужны Git, Bash и Docker с Compose v2.

```bash
git clone --branch hw1 --single-branch https://github.com/alexey077/dwh.git
cd dwh
docker compose up -d
./scripts/verify.sh
```

При запуске контейнер `init` автоматически создаёт четыре базы и применяет миграции. `verify.sh` дожидается готовности стенда, загружает данные и запускает официальный чекер. Отчёт сохраняется в `reports/check_report.json`. Исходный чекер находится в `hw01/hw01_check.py` и не изменён; обёртка подставляет адреса сервисов внутри Docker.

Для повторной проверки уже поднятого стенда используется `./scripts/check.sh --verbose`.

Эксперименты Э1–Э7 и проверка после восстановления кластера запускаются отдельно:

```bash
./scripts/verify.sh --full
```

Для этого режима нужен Python 3 с модулем `venv`; проверенная версия — 3.12. Скрипт создаёт окружение и устанавливает зависимости. Результаты сохраняются в `docs/failover_journal.md`, подробные логи — в `reports/ha-*/`, итоговый отчёт — в `reports/check_after_failures.json`.

## Подключения

Адреса ниже доступны с компьютера, на котором запущен Docker. Порт 6432 — PgBouncer, 5000 — запись через HAProxy, 5001 — чтение с реплик.

| Подключение | Connection string |
|---|---|
| CRM, PgBouncer | `postgresql://checker:checker@localhost:6432/crm_service_db` |
| Каталог, PgBouncer | `postgresql://checker:checker@localhost:6432/catalog_service_db` |
| POS, PgBouncer | `postgresql://checker:checker@localhost:6432/pos_service_db` |
| WMS, PgBouncer | `postgresql://checker:checker@localhost:6432/wms_service_db` |
| CRM, HAProxy, запись | `postgresql://postgres:postgres@localhost:5000/crm_service_db` |
| Каталог, HAProxy, запись | `postgresql://postgres:postgres@localhost:5000/catalog_service_db` |
| POS, HAProxy, запись | `postgresql://postgres:postgres@localhost:5000/pos_service_db` |
| WMS, HAProxy, запись | `postgresql://postgres:postgres@localhost:5000/wms_service_db` |
| CRM, HAProxy, чтение | `postgresql://checker:checker@localhost:5001/crm_service_db` |
| Каталог, HAProxy, чтение | `postgresql://checker:checker@localhost:5001/catalog_service_db` |
| POS, HAProxy, чтение | `postgresql://checker:checker@localhost:5001/pos_service_db` |
| WMS, HAProxy, чтение | `postgresql://checker:checker@localhost:5001/wms_service_db` |
| pg1 напрямую, база POS | `postgresql://postgres:postgres@localhost:5432/pos_service_db` |
| pg2 напрямую, база POS | `postgresql://postgres:postgres@localhost:5433/pos_service_db` |
| pg3 напрямую, база POS | `postgresql://postgres:postgres@localhost:5434/pos_service_db` |

Роль `checker` читает контракт и состояние кластера. Роль приложения — `app/app`, роль негативных тестов — `test_writer/test_writer`. Прямые порты закреплены за узлами, роли которых меняются при failover. Для подключения к другой базе напрямую заменяется имя базы в конце строки.

Patroni API узлов: `http://localhost:8008/cluster`, `http://localhost:8009/cluster`, `http://localhost:8010/cluster`. Учётные данные для изменения настроек — `patroni/patroni`. Статистика HAProxy: `http://localhost:7005/`.

В манифесте используется сводный статус `http://localhost:8011/cluster`: он проверяет состояние процесса и репликации каждого узла. Исходный ответ Patroni доступен по `http://localhost:8011/native/cluster`. Причина отдельного сервиса описана в [ADR 007](docs/adr/007_cluster_status.md).

## Модель и данные

На каждой таблице есть `created_at` и `updated_at`; дата изменения обновляется триггером. Деньги хранятся в `numeric` с фиксированной точностью. Цены, атрибуты SKU, клиентов и аптек имеют историю. В позиции чека сохраняются цена, название и рецептурность на момент операции. Ограничения схемы защищают суммы документов и оплат, возвраты, рецептурные продажи, сроки годности и остатки.

В базовой загрузке 2 400 клиентов, 2 100 карт, 600 SKU, 2 016 версий цен, 36 аптек, 12 поставщиков, 4 РЦ и 24 000 кассовых документов. История покрывает не меньше 12 месяцев. Повтор той же порции не создаёт дублей; генератор также умеет добавлять новые порции. Опорный месяц фиксируется при первой загрузке.

Для реалистичности использованы неравномерные распределения. Веса дней недели: понедельник–четверг — 1, пятница — 1,2, суббота — 2, воскресенье — 1,8. Первые 60 из 600 SKU имеют вес 18 против 1 у остальных. Первые шесть аптек имеют вес 5 против 1 у остальных. Вероятность покупки без карты — 45%, возвраты составляют 3% документов.

Для CDC настроены `wal_level=logical` и публикации всех таблиц каждой базы. На таблицах есть первичные ключи, используется `REPLICA IDENTITY DEFAULT`. Обезличивание клиента фиксируется отдельным событием для будущего DWH.

## Допущения

- Одно перемещение партии в аптеку считается одним заказом доставки. Для оценки задержки такого перемещения принят SLA 12 часов.
- Локальные копии SKU, цен и партий в POS обновляет генератор перед загрузкой порции. Постоянный обмен изменениями между сервисами относится к дальнейшей разработке.
- Все контейнеры работают на одном Docker-хосте. Эксперименты проверяют отказы отдельных узлов и сервисов; резервное копирование и отказ всего хоста в работе не моделируются.

## Документация

- ER-диаграммы: [CRM](docs/erd/crm.md), [каталог](docs/erd/catalog.md), [POS](docs/erd/pos.md), [WMS](docs/erd/wms.md), [общие технические таблицы](docs/erd/core.md).
- [Восемь архитектурных решений](docs/adr/) и [карта склейки источников](docs/dwh_mapping.md).
- [Журнал отказоустойчивости](docs/failover_journal.md) с измерениями и исходным выводом.
- [Соответствие требованиям](docs/requirements.md) и [использованные источники](docs/sources.md).

Манифест сдачи — [hw01_submission.yaml](hw01_submission.yaml), DDL — [migrations/](migrations/), 12 негативных и 2 положительных теста — [tests/invariants/](tests/invariants/).
