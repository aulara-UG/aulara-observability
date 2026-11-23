#!/usr/bin/env python3
import http.server
import os

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


if __name__ == "__main__":
    print(f"serving dump on 0.0.0.0:{PORT}", flush=True)
    http.server.HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
