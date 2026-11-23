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

exec python3 - <<'PY'
import os
import http.server

TOKEN = os.environ["MIG_TOKEN"]
PORT = int(os.environ.get("PORT", "8080"))

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get("X-Mig-Token") != TOKEN:
            self.send_response(401)
            self.end_headers()
            return
        with open("/tmp/dump.tgz", "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/gzip")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        return

http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
PY
