# Источники

Основной источник — материалы курса Modern Storages and Data Warehousing, ФТиАД ВШЭ, 2026.

Зафиксированная ревизия: `e97e7476cf9f5e456e950967d53afc48145d1f21`.

| Материал | Использование |
|---|---|
| [Условие и комплект hw01](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/hw01) | Требования, контракт, инварианты, критерии и самопроверка |
| [Семинар 1](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week01/sem) | Docker Compose, отдельные базы, автоматическая инициализация |
| [Семинар 2](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week02/sem) | Физическая репликация, PgBouncer, Patroni, etcd, HAProxy |
| [Демонстрация Patroni](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week02/sem/demo4_ha_patroni) | Основа топологии и конфигурации кластера |

## Документация инструментов

| Источник | Для чего использован |
|---|---|
| [Patroni REST API](https://patroni.readthedocs.io/en/latest/rest_api.html#cluster-status-endpoints) | Проверка ролей, состояния PostgreSQL и состояния репликации |
| [Обсуждение состояния реплик](https://github.com/patroni/patroni/discussions/3342), [cluster_as_json в Patroni 4.1.5](https://github.com/patroni/patroni/blob/v4.1.5/patroni/utils.py) | Различие ответов `/cluster` и `/patroni`; [ADR 007](adr/007_cluster_status.md) |
| [Dockerfile PgBouncer v1.25.2-p0](https://github.com/edoburu/docker-pgbouncer/blob/v1.25.2-p0/Dockerfile) | Пользователь контейнера, PostgreSQL client и подключение готовых конфигураций |
| [Сетевые функции PostgreSQL 18](https://www.postgresql.org/docs/18/functions-net.html) | Сопоставление адресов узлов при измерении RTO: `host(inet)` возвращает адрес без маски |
| [PGlite socket](https://pglite.dev/docs/pglite-socket), [btree_gist](https://pglite.dev/extensions/) | Первичная проверка SQL до запуска Docker; в итоговом стенде PGlite не используется |

Схемы сервисов, генератор и тесты написаны для этого проекта. Исходное условие, контракт и официальный чекер находятся в `hw01/` без изменений.
