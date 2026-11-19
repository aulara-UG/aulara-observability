#!/usr/bin/env bash
# Apply zero-config template variables (secrets + cross-service refs).
# Run while logged into the Aulara Railway workspace that owns the project.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-f1e0d68a-54ca-4cb8-ba26-e35e7542d688}"
ENV="${ENV:-production}"

echo "Applying template vars on project=$PROJECT_ID env=$ENV"

railway variable set --service serenedb --environment "$ENV" --project "$PROJECT_ID" --skip-deploys \
  'POSTGRES_PASSWORD=${{secret()}}' \
  'OTEL_INGEST_USER=otel_ingest' \
  'OTEL_INGEST_PASSWORD=${{secret()}}' \
  'GRAFANA_DB_USER=grafana_ro' \
  'GRAFANA_DB_PASSWORD=${{secret()}}' \
  'SERENEDB_DATA_DIR=/var/lib/serenedb' \
  'SERENEDB_CPU_THREADS=2' \
  'SERENEDB_IO_THREADS=2' \
  'SERENEDB_MEMORY_LIMIT=768MB'

railway variable set --service grafana --environment "$ENV" --project "$PROJECT_ID" --skip-deploys \
  'GF_SECURITY_ADMIN_USER=admin' \
  'GF_SECURITY_ADMIN_PASSWORD=${{secret()}}' \
  'GF_SERVER_ROOT_URL=https://${{RAILWAY_PUBLIC_DOMAIN}}' \
  'SERENEDB_HOST=${{serenedb.RAILWAY_PRIVATE_DOMAIN}}' \
  'SERENEDB_PORT=7890' \
  'GRAFANA_DB_USER=${{serenedb.GRAFANA_DB_USER}}' \
  'GRAFANA_DB_PASSWORD=${{serenedb.GRAFANA_DB_PASSWORD}}' \
  'PORT=3000'

# Remove Grafana knobs now baked into the image (ignore missing)
for k in GF_ALERTING_ENABLED GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES GF_ANALYTICS_CHECK_FOR_UPDATES \
  GF_ANALYTICS_REPORTING_ENABLED GF_AUTH_ANONYMOUS_ENABLED GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH \
  GF_DATABASE_WAL GF_DATAPROXY_LOGGING GF_EXPLORE_ENABLED GF_HELP_ENABLED GF_INSTALL_PLUGINS \
  GF_LIVE_MAX_CONNECTIONS GF_LOG_LEVEL GF_NEWS_NEWS_FEED_ENABLED GF_PROFILE_ENABLED \
  GF_SERVER_ENABLE_GZIP GF_SERVER_HTTP_PORT GF_UNIFIED_ALERTING_ENABLED GF_USERS_ALLOW_SIGN_UP \
  GOGC GOMEMLIMIT; do
  railway variable delete "$k" --service grafana --environment "$ENV" --project "$PROJECT_ID" >/dev/null 2>&1 || true
done

railway variable set --service otel-collector --environment "$ENV" --project "$PROJECT_ID" --skip-deploys \
  'OTEL_INGEST_USER=${{serenedb.OTEL_INGEST_USER}}' \
  'OTEL_INGEST_PASSWORD=${{serenedb.OTEL_INGEST_PASSWORD}}' \
  'SERENEDB_OTLP_ENDPOINT=http://${{serenedb.RAILWAY_PRIVATE_DOMAIN}}:4318' \
  'OTEL_HTPASSWD_FILE=/tmp/otel.htpasswd' \
  'OTEL_TENANTS=demo:${{secret(24)}}'

if railway variable list --service serenedb-soft-tune --environment "$ENV" --project "$PROJECT_ID" --json >/dev/null 2>&1; then
  railway variable set --service serenedb-soft-tune --environment "$ENV" --project "$PROJECT_ID" --skip-deploys \
    'POSTGRES_PASSWORD=${{serenedb.POSTGRES_PASSWORD}}'
fi

echo "Done. Redeploy services, then: railway templates create && railway templates publish ..."
