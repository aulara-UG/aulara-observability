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
echo restoring
PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U postgres \
  -d postgres \
  --clean \
  --if-exists \
  --no-owner \
  --no-acl \
  /tmp/dump.dump || true
echo verify
PGPASSWORD="$POSTGRES_PASSWORD" psql \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U postgres \
  -d postgres \
  -c "SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname LIKE 'otel_%' ORDER BY 1;"
echo done
sleep 3600
