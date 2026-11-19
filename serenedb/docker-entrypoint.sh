#!/bin/sh
set -eu

DATA_DIR="${SERENEDB_DATA_DIR:-/var/lib/serenedb}"
LISTEN="${SERENEDB_LISTEN:-postgres://0.0.0.0:7890,http://0.0.0.0:4318?api=otel}"
CPU_THREADS="${SERENEDB_CPU_THREADS:-2}"
IO_THREADS="${SERENEDB_IO_THREADS:-2}"

mkdir -p "$DATA_DIR"

serened "$DATA_DIR" \
  --listen="$LISTEN" \
  --cpu_threads="$CPU_THREADS" \
  --io_threads="$IO_THREADS" &
PID=$!

cleanup() {
  kill "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true
}
trap cleanup INT TERM

# Bootstrap roles + soft memory once the wire protocol is up (best-effort).
(
  sleep 2
  if [ -n "${POSTGRES_PASSWORD:-}" ] && [ -n "${OTEL_INGEST_PASSWORD:-}" ] && [ -n "${GRAFANA_DB_PASSWORD:-}" ]; then
    /bootstrap-roles.sh || echo "bootstrap warning: $?" >&2
  else
    echo "skip bootstrap (POSTGRES_PASSWORD / role passwords not all set)" >&2
  fi
) &

wait "$PID"
