#!/bin/sh
set -eu
# Railway healthchecks probe $PORT; Grafana listens on GF_SERVER_HTTP_PORT.
# Keep them aligned so marketplace deploys pass healthchecks.
export GF_SERVER_HTTP_PORT="${PORT:-${GF_SERVER_HTTP_PORT:-3000}}"
export PORT="$GF_SERVER_HTTP_PORT"

# Railway volumes are root-owned; Grafana runs as uid 472 by default.
mkdir -p /var/lib/grafana/plugins /var/lib/grafana/dashboards
chown -R 472:0 /var/lib/grafana || true
chmod -R u+rwX,g+rwX /var/lib/grafana || true
exec /run.sh "$@"
