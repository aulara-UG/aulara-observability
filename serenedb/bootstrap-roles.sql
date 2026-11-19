-- Idempotent role bootstrap for OTLP ingest + Grafana read-only access.
-- Invoked with psql -v otel_user=... -v otel_pw=... -v grafana_user=... -v grafana_pw=...

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'otel_user', :'otel_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'otel_user')\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'otel_user', :'otel_pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'otel_user')\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'grafana_user', :'grafana_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'grafana_user')\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'grafana_user', :'grafana_pw')
WHERE EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'grafana_user')\gexec

GRANT CONNECT ON DATABASE postgres TO :"otel_user";
GRANT CONNECT ON DATABASE postgres TO :"grafana_user";
GRANT USAGE ON SCHEMA public TO :"otel_user";
GRANT USAGE ON SCHEMA public TO :"grafana_user";

-- otel_* tables are created by the ?api=otel listener at startup.
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
  otel_logs,
  otel_traces,
  otel_metrics_gauge,
  otel_metrics_sum,
  otel_metrics_histogram,
  otel_metrics_exponential_histogram,
  otel_metrics_summary
TO :"otel_user";

GRANT SELECT ON TABLE
  otel_logs,
  otel_traces,
  otel_metrics_gauge,
  otel_metrics_sum,
  otel_metrics_histogram,
  otel_metrics_exponential_histogram,
  otel_metrics_summary
TO :"grafana_user";
