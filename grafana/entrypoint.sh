#!/bin/sh
set -eu
# Railway volumes are root-owned; Grafana runs as uid 472 by default.
mkdir -p /var/lib/grafana/plugins /var/lib/grafana/dashboards
chown -R 472:0 /var/lib/grafana || true
chmod -R u+rwX,g+rwX /var/lib/grafana || true
exec /run.sh "$@"
