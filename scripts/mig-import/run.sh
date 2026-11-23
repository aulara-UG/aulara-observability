#!/bin/sh
set -eu
RESTORE_USER="${RESTORE_USER:-otel_ingest}"
RESTORE_PASSWORD="${RESTORE_PASSWORD:-$OTEL_INGEST_PASSWORD}"
HOST="${SERENEDB_HOST}"
PORT="${SERENEDB_PORT:-7890}"

echo "waiting for dump at $DUMP_URL"
i=0
until curl -fsS -H "X-Mig-Token: $MIG_TOKEN" -o /tmp/dump.tgz "$DUMP_URL"; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then
    echo "dump not available after retries" >&2
    exit 1
  fi
  echo "retry_$i"
  sleep 5
done
ls -la /tmp/dump.tgz
mkdir -p /tmp/dump
tar -xzf /tmp/dump.tgz -C /tmp

echo "restoring as $RESTORE_USER"
if [ ! -f /tmp/dump/tables.txt ]; then
  echo "tables.txt missing from dump" >&2
  exit 1
fi

while IFS= read -r table || [ -n "$table" ]; do
  [ -z "$table" ] && continue
  file="/tmp/dump/${table}.csv"
  if [ ! -f "$file" ]; then
    echo "missing $file" >&2
    continue
  fi
  echo "delete+copy $table"
  # otel_ingest has DELETE/INSERT but not necessarily TRUNCATE.
  PGPASSWORD="$RESTORE_PASSWORD" psql -h "$HOST" -p "$PORT" -U "$RESTORE_USER" -d postgres -v ON_ERROR_STOP=1 \
    -c "DELETE FROM ${table};" \
    -c "\\copy ${table} FROM '${file}' WITH (FORMAT csv, HEADER true)"
done < /tmp/dump/tables.txt

echo verify
PGPASSWORD="$RESTORE_PASSWORD" psql -h "$HOST" -p "$PORT" -U "$RESTORE_USER" -d postgres \
  -c "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname LIKE 'otel_%' ORDER BY 1;"
echo done
sleep 3600
