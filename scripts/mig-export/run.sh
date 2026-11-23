#!/bin/sh
set -eu
# Prefer grafana_ro: POSTGRES_PASSWORD is only seeded at first volume init and
# may drift from the Railway variable after rotations.
DUMP_USER="${DUMP_USER:-grafana_ro}"
DUMP_PASSWORD="${DUMP_PASSWORD:-$GRAFANA_DB_PASSWORD}"
echo "dumping from ${SERENEDB_HOST}:${SERENEDB_PORT} as ${DUMP_USER}"
PGPASSWORD="$DUMP_PASSWORD" pg_dump \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U "$DUMP_USER" \
  -d postgres \
  -Fc \
  --no-owner \
  --no-acl \
  -f /tmp/dump.dump
ls -la /tmp/dump.dump
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
        with open("/tmp/dump.dump", "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_args):
        return

http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
PY
