#!/usr/bin/env bash
# End-to-end smoke test against the OTel Collector (private or public).
set -euo pipefail

COLLECTOR_HTTP="${OTEL_COLLECTOR_HTTP:-http://otel-collector.railway.internal:4318}"
SERENEDB_HOST="${SERENEDB_HOST:-serenedb.railway.internal}"
SERENEDB_PORT="${SERENEDB_PORT:-7890}"
TENANT_ID="${OTEL_TENANT_ID:?OTEL_TENANT_ID required}"
TENANT_PASSWORD="${OTEL_TENANT_PASSWORD:?OTEL_TENANT_PASSWORD required}"
export PGPASSWORD="${POSTGRES_PASSWORD:?POSTGRES_PASSWORD required for SQL verification}"

TS_NS="$(python3 - <<'PY'
import time
print(int(time.time() * 1_000_000_000))
PY
)"
TRACE_ID="$(openssl rand -hex 16)"
SPAN_ID="$(openssl rand -hex 8)"
RUN_ID="smoke-$(date -u +%Y%m%dT%H%M%SZ)"

AUTH=(-u "${TENANT_ID}:${TENANT_PASSWORD}")

echo "== Test A: Collector health =="
curl -fsS "http://otel-collector.railway.internal:13133/" >/dev/null
echo "health_check ok"

echo "== Test A2: unauthenticated OTLP rejected =="
code=$(curl -sS -o /tmp/unauth.out -w "%{http_code}" -X POST "${COLLECTOR_HTTP}/v1/logs" \
  -H 'Content-Type: application/json' -d '{"resourceLogs":[]}' || true)
echo "unauth http=$code"
test "$code" = "401" -o "$code" = "403"

echo "== Test B: Log ingestion (tenant ${TENANT_ID}) =="
curl -fsS "${AUTH[@]}" -X POST "${COLLECTOR_HTTP}/v1/logs" \
  -H 'Content-Type: application/json' \
  -d "{
    \"resourceLogs\": [{
      \"resource\": {\"attributes\": [
        {\"key\": \"service.name\", \"value\": {\"stringValue\": \"smoke-test\"}}
      ]},
      \"scopeLogs\": [{
        \"logRecords\": [{
          \"timeUnixNano\": \"${TS_NS}\",
          \"severityNumber\": 17,
          \"severityText\": \"ERROR\",
          \"body\": {\"stringValue\": \"smoke test error ${RUN_ID}\"},
          \"attributes\": [
            {\"key\": \"run.id\", \"value\": {\"stringValue\": \"${RUN_ID}\"}}
          ]
        }]
      }]
    }]
  }" >/dev/null
echo "log export accepted"

echo "== Test C: Trace ingestion =="
END_NS=$((TS_NS + 2500000))
curl -fsS "${AUTH[@]}" -X POST "${COLLECTOR_HTTP}/v1/traces" \
  -H 'Content-Type: application/json' \
  -d "{
    \"resourceSpans\": [{
      \"resource\": {\"attributes\": [
        {\"key\": \"service.name\", \"value\": {\"stringValue\": \"smoke-test\"}}
      ]},
      \"scopeSpans\": [{
        \"spans\": [{
          \"traceId\": \"${TRACE_ID}\",
          \"spanId\": \"${SPAN_ID}\",
          \"name\": \"smoke-span\",
          \"kind\": 2,
          \"startTimeUnixNano\": \"${TS_NS}\",
          \"endTimeUnixNano\": \"${END_NS}\",
          \"status\": {\"code\": 2, \"message\": \"smoke error\"},
          \"attributes\": [
            {\"key\": \"run.id\", \"value\": {\"stringValue\": \"${RUN_ID}\"}}
          ]
        }]
      }]
    }]
  }" >/dev/null
echo "trace export accepted"

echo "== Test D: Metrics ingestion =="
curl -fsS "${AUTH[@]}" -X POST "${COLLECTOR_HTTP}/v1/metrics" \
  -H 'Content-Type: application/json' \
  -d "{
    \"resourceMetrics\": [{
      \"resource\": {\"attributes\": [
        {\"key\": \"service.name\", \"value\": {\"stringValue\": \"smoke-test\"}}
      ]},
      \"scopeMetrics\": [{
        \"metrics\": [{
          \"name\": \"smoke.test.gauge\",
          \"unit\": \"1\",
          \"gauge\": {
            \"dataPoints\": [{
              \"timeUnixNano\": \"${TS_NS}\",
              \"asDouble\": 42.5,
              \"attributes\": [
                {\"key\": \"run.id\", \"value\": {\"stringValue\": \"${RUN_ID}\"}}
              ]
            }]
          }
        }]
      }]
    }]
  }" >/dev/null
echo "metrics export accepted"

echo "Waiting for collector batch flush..."
sleep 8

echo "== SQL verification =="
psql -h "$SERENEDB_HOST" -p "$SERENEDB_PORT" -U postgres -d postgres -v ON_ERROR_STOP=1 <<SQL
SELECT count(*) AS log_hits FROM otel_logs WHERE body LIKE '%${RUN_ID}%';
SELECT count(*) AS tenant_hits FROM otel_logs
WHERE body LIKE '%${RUN_ID}%' AND resource_attributes->>'tenant.id' = '${TENANT_ID}';
SELECT count(*) AS trace_hits FROM otel_traces WHERE trace_id = '${TRACE_ID}';
SELECT count(*) AS metric_hits FROM otel_metrics_gauge
WHERE metric_name = 'smoke.test.gauge' AND resource_attributes->>'tenant.id' = '${TENANT_ID}';
SQL

echo "Smoke test finished for run ${RUN_ID} tenant ${TENANT_ID}"
