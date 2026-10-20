#!/usr/bin/env python3
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import math
import platform
from ipaddress import ip_interface
from pathlib import Path
import shlex
import shutil
import statistics
import subprocess
import threading
import time
from urllib.error import URLError
from urllib.request import Request, urlopen
import uuid

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
NODES = ("pg1", "pg2", "pg3")
API_PORTS = dict(zip(NODES, (8008, 8009, 8010)))
DB_PORTS = dict(zip(NODES, (5432, 5433, 5434)))
RW = "postgresql://postgres:postgres@localhost:5000/pos_service_db"
RO = "postgresql://postgres:postgres@localhost:5001/pos_service_db"
POOL = "postgresql://postgres:postgres@localhost:6432/pos_service_db"


METRIC_LABELS = {
    'acknowledged': 'Подтверждено транзакций',
    'errors': 'Ошибок',
    'seconds': 'Длительность, с',
    'tps': 'Транзакций в секунду',
    'median_ms': 'Медианная задержка, мс',
    'p95_ms': 'p95 задержки, мс',
    'rto_seconds': 'Пауза записи (RTO), с',
    'errors_in_gap': 'Ошибок за паузу',
    'old_leader': 'Старый лидер',
    'new_leader': 'Новый лидер',
    'lost_acknowledged': 'Потеряно подтверждённых транзакций',
    'last_old_ack': 'Последний ACK старого лидера (UTC)',
    'first_new_ack': 'Первый ACK нового лидера (UTC)',
    'seconds_until_caught_up': 'Время возврата и догона, с',
    'role': 'Роль после возврата',
    'wal_since_receiver_start_bytes': 'WAL от начала текущего приёма, байт',
    'pg_rewind_call_in_log': 'pg_rewind найден в логе',
    'async_tps': 'TPS async',
    'sync_tps': 'TPS sync',
    'async_p95_ms': 'p95 async, мс',
    'sync_p95_ms': 'p95 sync, мс',
    'async_rto': 'RTO async, с',
    'sync_rto': 'RTO sync, с',
    'async_lost': 'Потеряно подтверждений async',
    'sync_lost': 'Потеряно подтверждений sync',
    'one_node_loss_acknowledged': 'Подтверждено при потере одного etcd',
    'one_node_loss_errors': 'Ошибок при потере одного etcd',
    'two_node_loss_write_failure_seconds': 'Время до ошибки записи после потери второго etcd, с',
    'replica_read_available': 'Чтение с реплики доступно',
    'direct_first_error_at': 'Первое число клиентов с ошибкой напрямую',
    'pool_first_error_at': 'Первое число клиентов с ошибкой через пул',
    'direct_40_errors': 'Напрямую, 40 клиентов: ошибок',
    'direct_40_connect_median_ms': 'Напрямую, 40 клиентов: медиана подключения, мс',
    'pool_40_errors': 'Через пул, 40 клиентов: ошибок',
    'pool_40_connect_median_ms': 'Через пул, 40 клиентов: медиана подключения, мс',
    'direct_80_errors': 'Напрямую, 80 клиентов: ошибок',
    'direct_80_connect_median_ms': 'Напрямую, 80 клиентов: медиана подключения, мс',
    'pool_80_errors': 'Через пул, 80 клиентов: ошибок',
    'pool_80_connect_median_ms': 'Через пул, 80 клиентов: медиана подключения, мс',
    'direct_160_errors': 'Напрямую, 160 клиентов: ошибок',
    'direct_160_connect_median_ms': 'Напрямую, 160 клиентов: медиана подключения, мс',
    'pool_160_errors': 'Через пул, 160 клиентов: ошибок',
    'pool_160_connect_median_ms': 'Через пул, 160 клиентов: медиана подключения, мс',
}

JOURNAL_TITLES = {
    "Э1. Async baseline": "Э1. Нагрузка без отказов (async)",
    "Э5. Sync baseline": "Э5.1. Нагрузка в синхронном режиме",
    "Э5. Sync failover": "Э5.2. Авария в синхронном режиме",
    "Э5. Возврат sync-узла": "Э5.3. Возврат узла",
    "Э5. Цена синхронной репликации": "Э5.4. Сравнение async и sync",
}


def now():
    return datetime.now(timezone.utc).isoformat()


def query(dsn, statement, params=None):
    connection = psycopg2.connect(dsn, connect_timeout=3)
    try:
        connection.autocommit = True
        with connection.cursor() as cursor:
            cursor.execute(statement, params)
            return cursor.fetchall() if cursor.description else []
    finally:
        connection.close()


def api(path, method="GET", body=None, node=None):
    nodes = (node,) if node else NODES
    last = None
    for member in nodes:
        request = Request(
            f"http://localhost:{API_PORTS[member]}{path}",
            data=json.dumps(body).encode() if body is not None else None,
            method=method,
        )
        request.add_header(
            "Authorization", "Basic " + base64.b64encode(b"patroni:patroni").decode()
        )
        request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=4) as response:
                text = response.read().decode()
                try:
                    return json.loads(text)
                except ValueError:
                    return {"response": text}
        except (OSError, URLError) as error:
            last = error
    raise RuntimeError(f"Patroni API is unavailable: {last}")


def leader():
    members = api("/cluster").get("members", [])
    names = [m["name"] for m in members if m.get("role") == "leader"]
    if len(names) != 1:
        raise RuntimeError(f"Expected one leader, got {names}")
    return names[0]


def wait_cluster(timeout=180):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            members = api("/cluster")["members"]
            for name in NODES:
                api("/health", node=name)
            if (
                len(members) == 3
                and sum(m.get("role") == "leader" for m in members) == 1
                and all(m.get("state") in ("running", "streaming") for m in members)
            ):
                if (
                    query(RW, "SELECT pg_is_in_recovery()")[0][0] is False
                    and query(RO, "SELECT pg_is_in_recovery()")[0][0] is True
                ):
                    return members
        except (OSError, RuntimeError, KeyError, psycopg2.Error):
            pass
        time.sleep(1)
    raise TimeoutError("Cluster did not return to three healthy nodes")


def wait_new_leader(previous, timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            candidate = leader()
            if candidate != previous:
                api("/primary", node=candidate)
                if query(RW, "SELECT pg_is_in_recovery()")[0][0] is False:
                    return candidate
        except (OSError, RuntimeError, psycopg2.Error):
            pass
        time.sleep(0.5)
    raise TimeoutError("A new writable leader did not appear")


@dataclass
class Event:
    at: str
    monotonic: float
    duration_ms: float
    ok: bool
    key: str
    node: str = ""
    error: str = ""


class Workload:
    def __init__(self, label, seconds, workers=4):
        self.label, self.seconds, self.workers = label, seconds, workers
        self.events = []
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.threads = []

    def worker(self):
        connection = None
        deadline = time.monotonic() + self.seconds
        try:
            while time.monotonic() < deadline and not self.stop.is_set():
                key = self.label + "-" + uuid.uuid4().hex
                started = time.monotonic()
                node, error, ok = "", "", False
                try:
                    if connection is None or connection.closed:
                        connection = psycopg2.connect(POOL, connect_timeout=3)
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL statement_timeout='5s'")
                        cursor.execute(
                            """INSERT INTO core.ha_probe(probe_bk,payload)
                            VALUES (%s,%s) RETURNING host(inet_server_addr())""",
                            (key, self.label),
                        )
                        node = cursor.fetchone()[0]
                    connection.commit()
                    ok = True
                except psycopg2.Error as exc:
                    error = str(exc).splitlines()[0]
                    if connection is not None:
                        connection.close()
                    connection = None
                finished = time.monotonic()
                event = Event(
                    now(), finished, (finished - started) * 1000, ok, key, node, error
                )
                with self.lock:
                    self.events.append(event)
                self.stop.wait(0.02 if ok else 0.05)
        finally:
            if connection is not None:
                connection.close()

    def start(self):
        self.started = time.monotonic()
        for _ in range(self.workers):
            thread = threading.Thread(target=self.worker, daemon=True)
            thread.start()
            self.threads.append(thread)
        return self

    def finish(self):
        for thread in self.threads:
            thread.join(self.seconds + 10)
            if thread.is_alive():
                self.stop.set()
                raise TimeoutError("Write worker did not stop")
        self.finished = time.monotonic()
        self.events.sort(key=lambda event: event.monotonic)
        return self

    def metrics(self):
        successful = [e.duration_ms for e in self.events if e.ok]
        if not successful:
            raise RuntimeError("No transaction was acknowledged")
        ordered = sorted(successful)
        return {
            "acknowledged": len(successful),
            "errors": sum(not e.ok for e in self.events),
            "seconds": round(self.finished - self.started, 3),
            "tps": round(len(successful) / (self.finished - self.started), 3),
            "median_ms": round(statistics.median(successful), 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1], 3),
        }


def switching_metrics(events, old_ip, new_ip, fault_at):
    old_ip, new_ip = str(ip_interface(old_ip).ip), str(ip_interface(new_ip).ip)
    acknowledged = [(e, str(ip_interface(e.node).ip)) for e in events if e.ok]
    recovered = [
        e
        for e, address in acknowledged
        if address == new_ip and e.monotonic >= fault_at
    ]
    if not recovered:
        observed = ", ".join(sorted({address for _, address in acknowledged})) or "none"
        raise RuntimeError(
            f"No acknowledged transaction on the new leader {new_ip}; "
            f"observed acknowledged nodes: {observed}"
        )
    first = min(recovered, key=lambda e: e.monotonic)
    previous = [
        e
        for e, address in acknowledged
        if address == old_ip and e.monotonic <= first.monotonic
    ]
    if not previous:
        raise RuntimeError("No acknowledged transaction on the previous leader")
    last = max(previous, key=lambda e: e.monotonic)
    return {
        "last_old_ack": last.at,
        "first_new_ack": first.at,
        "rto_seconds": round(first.monotonic - last.monotonic, 3),
        "errors_in_gap": sum(
            not e.ok and last.monotonic <= e.monotonic <= first.monotonic
            for e in events
        ),
    }


class Experiments:
    def __init__(self, seconds, window):
        self.seconds, self.window = seconds, window
        self.completed = False
        self.machine = {}
        self.sections = []
        self.directory = (
            ROOT
            / "reports"
            / ("ha-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
        )
        self.directory.mkdir(parents=True)
        self.output = []
        self.policies = {}
        self.original = None
        self.archive = ROOT / "docs/experiments" / self.directory.name
        self.archive.mkdir(parents=True)
        previous = ROOT / "docs/failover_journal.md"
        if previous.exists():
            (self.directory / "previous-journal.md").write_text(previous.read_text())

    def command(self, args, check=True):
        command = ["docker", "compose", *args]
        self.output.append("$ " + shlex.join(command))
        result = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=180,
        )
        self.output.append(result.stdout.strip())
        if check and result.returncode:
            raise RuntimeError(
                f"Command failed ({result.returncode}): {shlex.join(command)}"
            )
        return result.stdout.strip()

    def docker(self, args):
        self.output.append("$ " + shlex.join(["docker", *args]))
        result = subprocess.run(
            ["docker", *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            timeout=30,
        )
        self.output.append(result.stdout.strip())
        return result.stdout.strip()

    def address(self, node):
        identifier = self.command(["ps", "-q", node])
        return self.docker(
            [
                "inspect",
                "--format",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
                identifier,
            ]
        )

    def crash(self, node):
        identifier = self.command(["ps", "-q", node])
        policy = json.loads(
            self.docker(
                [
                    "inspect",
                    "--format",
                    "{{json .HostConfig.RestartPolicy}}",
                    identifier,
                ]
            )
        )
        self.policies[node] = policy["Name"] + (
            f":{policy['MaximumRetryCount']}"
            if policy["Name"] == "on-failure" and policy["MaximumRetryCount"]
            else ""
        )
        self.docker(["update", "--restart=no", identifier])
        self.docker(["kill", "--signal=KILL", identifier])

    def record_events(self, events):
        rows = sorted(events, key=lambda e: e.monotonic)
        (self.directory / f"{len(self.sections) + 1:02d}-events.json").write_text(
            json.dumps([asdict(e) for e in rows], ensure_ascii=False, indent=2)
        )
        return rows

    def save(self, title, metrics, conclusion, events=None):
        raw = list(self.output)
        self.output.clear()
        if events:
            rows = self.record_events(events)
            errors = [e for e in rows if not e.ok]
            if "first_new_ack" in metrics:
                first = next(
                    e for e in rows if e.at == metrics["first_new_ack"] and e.ok
                )
                last = next(e for e in rows if e.at == metrics["last_old_ack"] and e.ok)
                sample = [e for e in rows if e.ok and e.monotonic <= last.monotonic][
                    -4:
                ]
                sample += [
                    e
                    for e in errors
                    if last.monotonic <= e.monotonic <= first.monotonic
                ][:4]
                sample += [e for e in rows if e.ok and e.monotonic >= first.monotonic][
                    :4
                ]
            else:
                sample = (
                    rows[:4] + errors[:4] + rows[-4:]
                    if errors
                    else rows[:6] + rows[-6:]
                )
            raw.extend(json.dumps(asdict(e), ensure_ascii=False) for e in sample)
        self.sections.append((title, metrics, conclusion, raw))
        self.write_journal()
        print(JOURNAL_TITLES.get(title, title) + ": " + conclusion, flush=True)

    def write_journal(self, failure=None):
        lines = [
            "# Журнал отказоустойчивости",
            "",
            "Время формирования: " + now(),
            "",
            "Топология: 3 PostgreSQL 18 под Patroni 4.1.5, 3 etcd, HAProxy и PgBouncer. "
            "Режим в начале экспериментов — async. Параметры Patroni: ttl=30, loop_wait=10, retry_timeout=10.",
            "",
            "RTO — интервал между последним подтверждением старого лидера и первым подтверждением нового. "
            "Он включает дискретность нагрузки. Потеря проверяется только для транзакций, подтверждённых клиенту.",
            "",
        ]
        lines += ["## 0. Стенд", "", "| Параметр | Значение |", "|---|---|"]
        lines += [f"| {name} | {str(value).replace('|', '/')} |" for name, value in self.machine.items()]
        lines += [
            "", "```mermaid", "flowchart TD",
            '    client["Клиент"] --> pool["PgBouncer :6432"]',
            '    pool --> proxy["HAProxy :5000 / :5001"]',
            '    proxy --> pg1["pg1 / Patroni"]',
            '    proxy --> pg2["pg2 / Patroni"]',
            '    proxy --> pg3["pg3 / Patroni"]',
            '    pg1 -.-> dcs["etcd1 + etcd2 + etcd3, кворум 2/3"]',
            "    pg2 -.-> dcs", "    pg3 -.-> dcs", "```", "",
            "Нагрузка записи: 4 клиента, INSERT + COMMIT и пауза после успеха 20 мс.", "",
        ]
        for title, metrics, conclusion, raw in self.sections:
            command = (
                f".venv/bin/python scripts/experiments.py --seconds {self.seconds} "
                f"--event-window {self.window}"
            )
            lines += [
                "## " + JOURNAL_TITLES.get(title, title), "",
                "Этап общего сценария:", "",
                "```bash", command, "```", "",
                "| Метрика | Значение |", "|---|---|",
            ]
            lines += [f"| {METRIC_LABELS.get(key, key)} | {value} |" for key, value in metrics.items()]
            lines += ["", conclusion, ""]
            if raw:
                lines += ["<details>", "<summary>Фрагмент исходного вывода</summary>", "", "```text", *raw, "```", "", "</details>", ""]
        if failure:
            lines += [
                "## Незавершённая проверка",
                "",
                str(failure),
                "",
                "```text",
                *self.output,
                "```",
                "",
            ]
        lines += [
            "## Итоговая таблица",
            "",
            "| Отказ | Кто восстанавливает | Измеренная цена |",
            "|---|---|---|",
        ]
        measured = {title: metrics for title, metrics, _, _ in self.sections}
        crash = measured.get("Э2. Аварийная потеря лидера", {})
        planned = measured.get("Э4. Плановое переключение", {})
        synchronous = measured.get("Э5. Цена синхронной репликации", {})
        flood = measured.get("Э7. Наплыв подключений", {})
        quorum = measured.get("Э6. Кворум etcd", {})
        value = lambda data, key: data.get(key, "не измерено")
        lines += [
            f"| Наплыв 160 клиентов | PgBouncer | ошибок напрямую: {value(flood, 'direct_160_errors')}; через пул: {value(flood, 'pool_160_errors')} |",
            f"| Потеря лидера | Patroni и кворум etcd | RTO: {value(crash, 'rto_seconds')} с; ошибок в окне: {value(crash, 'errors_in_gap')} |",
            f"| Плановая смена лидера | Patroni и HAProxy | RTO: {value(planned, 'rto_seconds')} с |",
            f"| Подтверждённые транзакции | Репликация | потеря async: {value(synchronous, 'async_lost')}; sync: {value(synchronous, 'sync_lost')} |",
            f"| Потеря одного etcd | Кворум 2/3 | ошибок записи: {value(quorum, 'one_node_loss_errors')} |",
            "| Логическое удаление | Резервная копия и восстановление | Не измерялось; бэкапы в этот стенд не включены |",
            "| Отказ целого ЦОД | Отдельная площадка | Не моделировался |",
            "",
        ]
        if crash and planned:
            ratio = (
                crash["rto_seconds"] / planned["rto_seconds"]
                if planned["rto_seconds"]
                else None
            )
            lines += [
                f"Аварийное переключение было в {ratio:.2f} раза дольше планового."
                if ratio is not None else "Отношение RTO не определено.",
                "",
            ]
        if synchronous and flood:
            lines += [
                "## Изменения после измерений",
                "",
                f"1. Для денежных операций рассмотрел бы sync: p95 изменился с {synchronous['async_p95_ms']} до {synchronous['sync_p95_ms']} мс; фактическая потеря указана в таблице. Нулевые потери async в одном опыте не гарантируют их отсутствие при другом отказе.",
                f"2. Оставил бы приложение за пулом: при 160 клиентах напрямую получено {flood['direct_160_errors']} ошибок, через пул — {flood['pool_160_errors']}. Перед увеличением серверных лимитов проверил бы одновременную нагрузку четырёх баз.",
                f"3. Для уменьшения наблюдавшегося аварийного RTO {crash['rto_seconds']} с проверил бы меньший ttl вместе с loop_wait и retry_timeout. Перед применением нужны отдельные тесты сетевых задержек; в этом запуске параметры не менялись.",
                "",
            ]
        lines += [
            "## Ограничения",
            "",
            "Репликация не восстанавливает случайное логическое удаление и не заменяет резервные копии. "
            "В этом стенде HAProxy и PgBouncer по одному экземпляру; отказ целого узла Docker или ЦОД отдельно не моделируется.",
        ]
        lines += [
            "", "## Пояснения к измерениям", "",
            "Аварийный RTO включает обнаружение отказа, ожидание лидерского TTL, promotion "
            "и восстановление клиентского маршрута. При switchover лидер передаёт роль сам. "
            "RTO между ACK включает дискретность нагрузки.", "",
            "Async/sync сравнивались одним последовательным прогоном на разных лидерах. "
            "Меньший p95 sync не означает ускорения записи. Нулевая потеря async в одном "
            "опыте не гарантирует сохранность последнего WAL при другой аварии.", "",
            "WAL при rejoin отсчитывается от start LSN текущего receiver, это не полный объём "
            "pg_rewind; способ восстановления подтверждают строки Patroni. В Э6 время включает "
            "остановку второго etcd и проверку чтения. В Э7 время подключения не включает "
            "всё ожидание выполнения транзакции.", "",
        ]
        target = ROOT / "docs/failover_journal.md"
        if not self.sections:
            if failure:
                (self.archive / "failure.md").write_text("\n".join(lines) + "\n")
            return
        text = "\n".join(lines) + "\n"
        (self.directory / "journal.md").write_text(text)
        (self.archive / "journal.md").write_text(text)
        if self.completed and not failure:
            target.write_text(text)

    def prepare(self):
        compose_version = self.command(["version"])
        docker_info = self.docker(
            [
                "info",
                "--format",
                "CPU={{.NCPU}} RAM={{.MemTotal}} OS={{.OperatingSystem}} ARCH={{.Architecture}} Docker={{.ServerVersion}} Storage={{.Driver}}",
            ]
        )
        wait_cluster()
        version = query(RW, "SHOW server_version")[0][0]
        if int(version.split(".")[0]) != 18:
            raise RuntimeError(f"Expected PostgreSQL 18, got {version}")
        self.output += [
            "SELECT version(): " + query(RW, "SELECT version()")[0][0],
            "Patroni: "
            + json.dumps(api("/patroni").get("patroni", {}), ensure_ascii=False),
        ]
        disk = shutil.disk_usage(ROOT)
        self.machine = {
            "ОС скрипта": platform.platform(),
            "Docker Compose": compose_version,
            "Ресурсы Docker": docker_info,
            "PostgreSQL": query(RW, "SELECT version()")[0][0],
            "Patroni": json.dumps(api("/patroni").get("patroni", {})),
            "Диск проекта: всего / свободно, байт": f"{disk.total} / {disk.free}",
        }
        self.original = api("/config")
        api(
            "/config",
            "PATCH",
            {
                "synchronous_mode": False,
                "synchronous_mode_strict": False,
                "failsafe_mode": False,
            },
        )
        query(
            RW,
            """CREATE TABLE IF NOT EXISTS core.ha_probe (
            probe_bk text PRIMARY KEY,payload text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
            updated_at timestamptz NOT NULL DEFAULT clock_timestamp())""",
        )
        query(
            RW,
            """DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgrelid='core.ha_probe'::regclass AND tgname='a_touch') THEN
                CREATE TRIGGER a_touch BEFORE UPDATE ON core.ha_probe FOR EACH ROW EXECUTE FUNCTION core.touch_row();
                CREATE TRIGGER b_immutable BEFORE UPDATE ON core.ha_probe FOR EACH ROW EXECUTE FUNCTION core.immutable_key('probe_bk');
                CREATE TRIGGER z_no_delete BEFORE DELETE ON core.ha_probe FOR EACH ROW EXECUTE FUNCTION core.no_delete();
            END IF;
        END $$""",
        )

    def baseline(self, label):
        load = Workload(label, self.seconds).start().finish()
        metrics = load.metrics()
        self.save(
            label,
            metrics,
            f"За {metrics['seconds']} с подтверждено {metrics['acknowledged']} транзакций. "
            f"Скорость — {metrics['tps']} TPS, p95 — {metrics['p95_ms']} мс; ошибок — {metrics['errors']}.",
            load.events,
        )
        return metrics

    def failover(self, label):
        old = leader()
        old_ip = self.address(old)
        load = Workload(label, self.window).start()
        time.sleep(10)
        fault_at = time.monotonic()
        self.crash(old)
        new = wait_new_leader(old)
        new_ip = self.address(new)
        load.finish()
        self.record_events(load.events)
        self.output.append(f"Leader addresses: {old}={old_ip}, {new}={new_ip}")
        self.command(["logs", "--no-color", "--tail", "50", new])
        metrics = load.metrics() | switching_metrics(
            load.events, old_ip, new_ip, fault_at
        )
        acknowledged = [e.key for e in load.events if e.ok]
        surviving = {
            r[0]
            for r in query(
                RW,
                "SELECT probe_bk FROM core.ha_probe WHERE probe_bk=ANY(%s)",
                (acknowledged,),
            )
        }
        metrics |= {
            "old_leader": old,
            "new_leader": new,
            "lost_acknowledged": len(set(acknowledged) - surviving),
        }
        self.save(
            label,
            metrics,
            "Новым лидером стал "
            + new
            + ". Потери подтверждённых транзакций сверены по probe_bk.",
            load.events,
        )
        return old, metrics

    def rejoin(self, old, label="Э3. Возврат узла"):
        started = time.monotonic()
        since = now()
        self.command(["start", old])
        wait_cluster()
        direct = (
            f"postgresql://postgres:postgres@localhost:{DB_PORTS[old]}/pos_service_db"
        )
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            target = query(RW, "SELECT pg_current_wal_lsn()::text")[0][0]
            if query(
                direct,
                "SELECT pg_is_in_recovery() AND pg_last_wal_replay_lsn()>=%s::pg_lsn",
                (target,),
            )[0][0]:
                break
            time.sleep(0.5)
        else:
            raise TimeoutError("Returned replica did not catch up")
        wal = query(
            direct,
            "SELECT pg_wal_lsn_diff(pg_last_wal_replay_lsn(),receive_start_lsn) FROM pg_stat_wal_receiver",
        )[0][0]
        logs = self.command(
            ["logs", "--no-color", "--since", since, old]
        )
        rewind = any(
            s in logs.lower()
            for s in ("running pg_rewind", "pg_rewind exit code", "pg_rewind stdout")
        )
        self.save(
            label,
            {
                "seconds_until_caught_up": round(time.monotonic() - started, 3),
                "role": "replica",
                "wal_since_receiver_start_bytes": int(wal),
                "pg_rewind_call_in_log": rewind,
            },
            "Узел вернулся репликой. Объём WAL посчитан от start LSN текущего WAL receiver; метод восстановления виден в сыром логе.",
        )

    def switchover(self):
        old = leader()
        candidate = next(n for n in NODES if n != old)
        old_ip, new_ip = self.address(old), self.address(candidate)
        load = Workload("E4", self.window).start()
        time.sleep(10)
        fault_at = time.monotonic()
        body = {"leader": old, "candidate": candidate}
        self.output.append("POST /switchover " + json.dumps(body))
        self.output.append(
            json.dumps(api("/switchover", "POST", body, node=old), ensure_ascii=False)
        )
        new = wait_new_leader(old)
        if new != candidate:
            raise RuntimeError("Switchover selected an unexpected candidate")
        load.finish()
        self.record_events(load.events)
        metrics = load.metrics() | switching_metrics(
            load.events, old_ip, new_ip, fault_at
        )
        self.save(
            "Э4. Плановое переключение",
            metrics,
            "Измерен перерыв между подтверждениями при плановой смене лидера.",
            load.events,
        )
        wait_cluster()

    def quorum(self):
        api(
            "/config",
            "PATCH",
            {
                "synchronous_mode": False,
                "synchronous_mode_strict": False,
                "failsafe_mode": False,
            },
        )
        self.command(["stop", "etcd1"])
        one = Workload("E6-one-etcd", 10).start().finish()
        one_metrics = one.metrics()
        if one_metrics["errors"]:
            raise RuntimeError("Writes failed after losing only one etcd node")
        self.command(
            [
                "exec",
                "-T",
                "etcd3",
                "etcdctl",
                "--endpoints=http://etcd1:2379,http://etcd2:2379,http://etcd3:2379",
                "endpoint",
                "health",
            ],
            check=False,
        )
        started = time.monotonic()
        self.command(["stop", "etcd2"])
        failed = None
        while time.monotonic() - started < 90:
            try:
                query(
                    RW,
                    "INSERT INTO core.ha_probe(probe_bk,payload) VALUES (%s,'E6-two')",
                    ("E6-" + uuid.uuid4().hex,),
                )
            except psycopg2.Error as error:
                failed = str(error).splitlines()[0]
                break
            time.sleep(0.5)
        if failed is None:
            raise RuntimeError("Writes did not stop after quorum loss")
        read_ok = query(RO, "SELECT pg_is_in_recovery()")[0][0] is True
        if not read_ok:
            raise RuntimeError("Replica read route failed during DCS loss")
        unavailable_after = round(time.monotonic() - started, 3)
        self.output += ["First write failure: " + failed]
        self.command(["logs", "--no-color", "--tail", "35", *NODES])
        self.command(["start", "etcd2", "etcd1"])
        wait_cluster()
        self.save(
            "Э6. Кворум etcd",
            {
                "one_node_loss_acknowledged": one_metrics["acknowledged"],
                "one_node_loss_errors": one_metrics["errors"],
                "two_node_loss_write_failure_seconds": unavailable_after,
                "replica_read_available": read_ok,
            },
            "Один отказ оставил кворум 2/3; при двух отказах запись остановилась, чтение реплики сохранилось.",
            one.events,
        )

    def flood(self):
        direct = f"postgresql://postgres:postgres@localhost:{DB_PORTS[leader()]}/pos_service_db"
        metrics = {}
        for label, dsn in [("direct", direct), ("pool", POOL)]:
            for clients in (40, 80, 160):
                barrier = threading.Barrier(clients)

                def client(_):
                    connection = None
                    barrier.wait(timeout=30)
                    started = time.monotonic()
                    try:
                        connection = psycopg2.connect(dsn, connect_timeout=10)
                        connected = time.monotonic()
                        with connection.cursor() as cursor:
                            cursor.execute("SELECT pg_sleep(1)")
                        connection.commit()
                        return True, (connected - started) * 1000, ""
                    except psycopg2.Error as error:
                        return (
                            False,
                            (time.monotonic() - started) * 1000,
                            str(error).splitlines()[0],
                        )
                    finally:
                        if connection is not None:
                            connection.close()

                with ThreadPoolExecutor(max_workers=clients) as executor:
                    rows = list(executor.map(client, range(clients)))
                errors = [r[2] for r in rows if not r[0]]
                metrics[f"{label}_{clients}_errors"] = len(errors)
                connected = [r[1] for r in rows if r[0]]
                metrics[f"{label}_{clients}_connect_median_ms"] = (
                    round(statistics.median(connected), 3)
                    if connected
                    else "не измерено"
                )
                self.output.append(
                    json.dumps(
                        {
                            "route": label,
                            "clients": clients,
                            "ok": len(rows) - len(errors),
                            "errors": len(errors),
                            "first_error": errors[0] if errors else None,
                        },
                        ensure_ascii=False,
                    )
                )
        for label in ("direct", "pool"):
            metrics[f"{label}_first_error_at"] = next(
                (n for n in (40, 80, 160) if metrics[f"{label}_{n}_errors"]),
                "не наблюдалось до 160",
            )
        if metrics["direct_160_errors"] == 0 or metrics["pool_160_errors"]:
            raise RuntimeError("Flood did not demonstrate the expected pool effect")
        self.save(
            "Э7. Наплыв подключений",
            metrics,
            "Сравнены одинаковые группы клиентов. В transaction pooling состояние сессии не переносится между транзакциями; SET LOCAL и временные объекты используются внутри одной транзакции.",
        )

    def restore(self):
        for node, policy in self.policies.items():
            identifier = self.command(["ps", "-a", "-q", node])
            self.docker(["update", f"--restart={policy}", identifier])
        self.command(["start", "etcd1", "etcd2", "etcd3", *NODES])
        if self.original is not None:
            api(
                "/config",
                "PATCH",
                {
                    key: self.original.get(key)
                    for key in (
                        "synchronous_mode",
                        "synchronous_mode_strict",
                        "synchronous_node_count",
                        "failsafe_mode",
                    )
                },
            )
        wait_cluster()

    def run(self):
        failure = None
        try:
            self.prepare()
            asynchronous = self.baseline("Э1. Async baseline")
            old, async_crash = self.failover("Э2. Аварийная потеря лидера")
            self.rejoin(old)
            self.switchover()
            body = {
                "synchronous_mode": True,
                "synchronous_mode_strict": True,
                "synchronous_node_count": 1,
            }
            self.output.append("PATCH /config " + json.dumps(body))
            api("/config", "PATCH", body)
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if query(
                    RW,
                    "SELECT count(*) FROM pg_stat_replication WHERE sync_state IN ('sync','quorum')",
                )[0][0]:
                    break
                time.sleep(1)
            else:
                raise TimeoutError("No synchronous standby appeared")
            synchronous = self.baseline("Э5. Sync baseline")
            old, sync_crash = self.failover("Э5. Sync failover")
            self.rejoin(old, "Э5. Возврат sync-узла")
            self.save(
                "Э5. Цена синхронной репликации",
                {
                    "async_tps": asynchronous["tps"],
                    "sync_tps": synchronous["tps"],
                    "async_p95_ms": asynchronous["p95_ms"],
                    "sync_p95_ms": synchronous["p95_ms"],
                    "async_rto": async_crash["rto_seconds"],
                    "sync_rto": sync_crash["rto_seconds"],
                    "async_lost": async_crash["lost_acknowledged"],
                    "sync_lost": sync_crash["lost_acknowledged"],
                },
                "Это измерения данного запуска; синхронный режим подтверждает запись на одной реплике до ответа клиенту.",
            )
            self.quorum()
            self.flood()
        except Exception as error:
            failure = error
            raise
        finally:
            try:
                self.restore()
            except Exception as error:
                failure = error
                raise
            finally:
                self.completed = failure is None
                self.write_journal(failure)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Э1–Э7 на локальном Docker-стенде с сохранением реальных измерений"
    )
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--event-window", type=int, default=90)
    args = parser.parse_args()
    if not shutil.which("docker"):
        parser.error("Docker CLI is required")
    if args.seconds < 10 or args.event_window < 60:
        parser.error("Use at least 10 seconds for baseline and 60 for failover windows")
    Experiments(args.seconds, args.event_window).run()
