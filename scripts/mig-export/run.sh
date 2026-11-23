#!/bin/sh
set -eu
# SereneDB is Postgres-wire compatible but not pg_dump-compatible.
DUMP_USER="${DUMP_USER:-grafana_ro}"
DUMP_PASSWORD="${DUMP_PASSWORD:-$GRAFANA_DB_PASSWORD}"
HOST="${SERENEDB_HOST}"
PORT="${SERENEDB_PORT:-7890}"
OUT=/tmp/dump
mkdir -p "$OUT"

TABLES="otel_logs otel_traces otel_metrics_gauge otel_metrics_sum otel_metrics_histogram otel_metrics_exponential_histogram otel_metrics_summary"

echo "listing tables as ${DUMP_USER}@${HOST}:${PORT}"
PGPASSWORD="$DUMP_PASSWORD" psql -h "$HOST" -p "$PORT" -U "$DUMP_USER" -d postgres -Atc \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE 'otel_%' ORDER BY 1;" \
  | tee "$OUT/tables.txt"

echo "copying tables"
while IFS= read -r table || [ -n "$table" ]; do
  [ -z "$table" ] && continue
  echo "copy $table"
  PGPASSWORD="$DUMP_PASSWORD" psql -h "$HOST" -p "$PORT" -U "$DUMP_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "\\copy ${table} TO '${OUT}/${table}.csv' WITH (FORMAT csv, HEADER true)"
done < "$OUT/tables.txt"

(cd /tmp && tar -czf /tmp/dump.tgz dump)
ls -la /tmp/dump.tgz
echo dump_ok
exec python3 /serve.py
