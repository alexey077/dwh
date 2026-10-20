# Источники

Основной источник — материалы курса Modern Storages and Data Warehousing, ФТиАД ВШЭ, 2026.

Зафиксированная ревизия: `e97e7476cf9f5e456e950967d53afc48145d1f21`.

| Материал | Использование |
|---|---|
| [Условие и комплект hw01](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/hw01) | Требования, контракт, инварианты, критерии и самопроверка |
| [Семинар 1](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week01/sem) | Docker Compose, отдельные базы, автоматическая инициализация |
| [Семинар 2](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week02/sem) | Физическая репликация, PgBouncer, Patroni, etcd, HAProxy |
| [Демонстрация Patroni](https://github.com/mgcrp/hse_ftda_dwh_course_2026/tree/e97e7476cf9f5e456e950967d53afc48145d1f21/week02/sem/demo4_ha_patroni) | Основа топологии и конфигурации кластера |

Для вспомогательной проверки SQL в окружении без Docker использована [документация PGlite](https://pglite.dev/docs/pglite-socket) и [расширения btree_gist](https://pglite.dev/extensions/). Этот инструмент относится к локальной проверке, итоговый стенд строится на PostgreSQL и Patroni из семинара 2.

Для проверки различий со штатным REST API использована [официальная документация Patroni 4.1.5](https://patroni.readthedocs.io/en/latest/rest_api.html#cluster-status-endpoints). Состояние процесса и репликации разделено в сервисе статуса; решение описано в [ADR 007](adr/007_cluster_status.md).

Для проверки состава образа PgBouncer прочитаны [Dockerfile тега v1.25.2-p0](https://github.com/edoburu/docker-pgbouncer/blob/v1.25.2-p0/Dockerfile) и его entrypoint. Подтверждены пользователь `postgres`, наличие PostgreSQL client и возможность передать готовые конфигурационные файлы.

При исправлении измерений failover использована [документация PostgreSQL 18 по сетевым функциям](https://www.postgresql.org/docs/18/functions-net.html): приведение `inet` к `text` включает маску, а `host(inet)` возвращает адрес без маски.

При разделении состояния процесса PostgreSQL и состояния репликации использованы [объяснение разработчика Patroni](https://github.com/patroni/patroni/discussions/3342) и [исходная функция cluster_as_json версии 4.1.5](https://github.com/patroni/patroni/blob/v4.1.5/patroni/utils.py). Сервис наблюдения получает живые ответы /patroni каждого узла; источник поля state указан в ответе API и ADR 007.
