FROM postgres:18

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-venv ca-certificates curl \
    && python3 -m venv /opt/patroni \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /build/requirements.txt
COPY infra/patroni/requirements.txt /build/infra/patroni/requirements.txt
RUN /opt/patroni/bin/pip install --no-cache-dir -r /build/infra/patroni/requirements.txt

ENV PATH="/opt/patroni/bin:/usr/lib/postgresql/18/bin:${PATH}" \
    PATRONICTL_CONFIG_FILE=/etc/patroni.yml \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY infra/patroni/patroni.yml /etc/patroni.yml
RUN chmod 0644 /etc/patroni.yml

USER postgres
ENTRYPOINT ["patroni", "/etc/patroni.yml"]
