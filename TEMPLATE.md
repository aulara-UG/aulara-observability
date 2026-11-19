# Aulara Observability Stack

**SereneDB + OpenTelemetry Collector + Grafana** — a production-ready observability backend on Railway.

Ingest metrics, logs, and traces over OTLP. Store them in [SereneDB](https://serenedb.com). Explore everything in Grafana.

## Architecture

```text
Your apps / agents
       │  OTLP (gRPC :4317 / HTTP :4318)
       ▼
┌──────────────────┐
│  otel-collector  │  multi-tenant Basic Auth → tenant.id
└────────┬─────────┘
         │  OTLP/HTTP + Basic Auth (private network)
         ▼
┌──────────────────┐         SQL (PG wire :7890)
│    serenedb      │ ◄──────────────────────── Grafana
└──────────────────┘
```

## What you get

| Service | Role |
|---------|------|
| **serenedb** | OTLP ingest + PostgreSQL-wire SQL store (volume-backed) |
| **otel-collector** | Public/private OTLP gateway, auth, batching, routing |
| **grafana** | Dashboards & Explore against SereneDB |

## Quick start after deploy

1. Open the **grafana** service URL and log in with `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD`.
2. Point apps at the collector:

```bash
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=https://<otel-collector-public-domain>
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20$(printf '%s' 'demo:changeme' | base64)
```

3. Set tenants on the collector via `OTEL_TENANTS` (comma-separated `user:password`). Each username becomes `resource.attributes["tenant.id"]`.

## Query examples

```sql
-- Logs for one tenant
SELECT timestamp, service_name, body
FROM otel_logs
WHERE resource_attributes->>'tenant.id' = 'demo'
ORDER BY timestamp DESC
LIMIT 100;

-- Host CPU
SELECT timestamp AS time, attributes->>'state' AS metric, value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND resource_attributes->>'tenant.id' = 'demo'
ORDER BY 1;
```

## Soft memory defaults

SereneDB is tuned for a small footprint (`cpu_threads` / `io_threads` = 2). Re-run soft-tune after major SereneDB redeploys if you use the optional tune job.

## Built by Aulara

Template maintained by **Aulara** for teams that want OTel-native observability without running Loki/Tempo/Mimir separately.

Website: [aulara.de](https://aulara.de)
