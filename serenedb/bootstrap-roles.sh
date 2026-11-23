#!/bin/sh
# Idempotent role bootstrap (runs from serenedb entrypoint after listen is up).
set -eu

HOST="${SERENEDB_BOOTSTRAP_HOST:-127.0.0.1}"
PORT="${SERENEDB_PORT:-7890}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"
OTEL_USER="${OTEL_INGEST_USER:-otel_ingest}"
GRAFANA_USER="${GRAFANA_DB_USER:-grafana_ro}"
OTEL_PW="${OTEL_INGEST_PASSWORD:?OTEL_INGEST_PASSWORD is required}"
GRAFANA_PW="${GRAFANA_DB_PASSWORD:?GRAFANA_DB_PASSWORD is required}"

if ! command -v psql >/dev/null 2>&1; then
  echo "psql not available; skip role bootstrap" >&2
  exit 0
fi

i=0
until psql -h "$HOST" -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 -c 'SELECT 1' >/dev/null 2>&1; do
  i=$((i + 1))
  [ "$i" -gt 60 ] && { echo "SereneDB not ready for bootstrap" >&2; exit 1; }
  sleep 1
done

psql -h "$HOST" -p "$PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 \
  -v otel_user="$OTEL_USER" \
  -v grafana_user="$GRAFANA_USER" \
  -v otel_pw="$OTEL_PW" \
  -v grafana_pw="$GRAFANA_PW" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'otel_user', :'otel_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'otel_user')\gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'otel_user', :'otel_pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'otel_user')\gexec
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'grafana_user', :'grafana_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'grafana_user')\gexec
SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'grafana_user', :'grafana_pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'grafana_user')\gexec

GRANT CONNECT ON DATABASE postgres TO :"otel_user";
GRANT CONNECT ON DATABASE postgres TO :"grafana_user";
GRANT USAGE ON SCHEMA public TO :"otel_user";
GRANT USAGE ON SCHEMA public TO :"grafana_user";

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_logs TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_traces TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_metrics_gauge TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_metrics_sum TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_metrics_histogram TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_metrics_exponential_histogram TO :"otel_user";
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE otel_metrics_summary TO :"otel_user";

GRANT SELECT ON TABLE otel_logs TO :"grafana_user";
GRANT SELECT ON TABLE otel_traces TO :"grafana_user";
GRANT SELECT ON TABLE otel_metrics_gauge TO :"grafana_user";
GRANT SELECT ON TABLE otel_metrics_sum TO :"grafana_user";
GRANT SELECT ON TABLE otel_metrics_histogram TO :"grafana_user";
GRANT SELECT ON TABLE otel_metrics_exponential_histogram TO :"grafana_user";
GRANT SELECT ON TABLE otel_metrics_summary TO :"grafana_user";
SQL

echo "Role bootstrap complete."
