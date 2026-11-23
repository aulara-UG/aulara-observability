#!/bin/sh
set -eu
echo "dumping from ${SERENEDB_HOST}:${SERENEDB_PORT}"
PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
  -h "$SERENEDB_HOST" \
  -p "$SERENEDB_PORT" \
  -U postgres \
  -d postgres \
  -Fc \
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
