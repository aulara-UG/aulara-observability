#!/bin/sh
set -eu
echo "waiting for dump at $DUMP_URL"
i=0
until curl -fsS -H "X-Mig-Token: $MIG_TOKEN" -o /tmp/dump.dump "$DUMP_URL"; do
  i=$((i + 1))
  if [ "$i" -gt 90 ]; then
    echo "dump not available after retries" >&2
    exit 1
  fi
  echo "retry_$i"
  sleep 5
done
ls -la /tmp/dump.dump
# otel_ingest has DML on otel_* (grafana_ro is SELECT-only).
RESTORE_USER="${RESTORE_USER:-otel_ingest}"
RESTORE_PASSWORD="${RESTORE_PASSWORD:-$OTEL_INGEST_PASSWORD}"
echo restoring as "$RESTORE_USER"
PGPASSWORD="$RESTORE_PASSWORD" pg_restore \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U "$RESTORE_USER" \
  -d postgres \
  --data-only \
  --disable-triggers \
  --no-owner \
  --no-acl \
  /tmp/dump.dump || true
echo verify
PGPASSWORD="$RESTORE_PASSWORD" psql \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U "$RESTORE_USER" \
  -d postgres \
  -c "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname LIKE 'otel_%' ORDER BY 1;"
echo done
sleep 3600
