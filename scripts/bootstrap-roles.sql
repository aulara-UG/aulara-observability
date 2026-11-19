-- Idempotent role bootstrap. Run as postgres superuser.
-- Substitutions are applied by bootstrap-roles.sh before execution.

CREATE ROLE otel_ingest LOGIN PASSWORD '__OTEL_INGEST_PASSWORD__';
-- ignore if exists: handled by shell wrapper

CREATE ROLE grafana_ro LOGIN PASSWORD '__GRAFANA_DB_PASSWORD__';
