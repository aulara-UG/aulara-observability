# Deploy and Host Aulara Observability on Railway

**Aulara Observability** is a general-purpose observability stack: **SereneDB** for storage, **OpenTelemetry Collector** for ingest, and **Grafana** for dashboards.

Built by [Aulara](https://aulara.de).

```text
Apps / agents  --OTLP-->  otel-collector  --OTLP/HTTP-->  serenedb  <--SQL--  grafana
```

## About Hosting Aulara Observability

This template provisions three always-on services (plus an optional soft-tune one-shot):

| Service | Role |
|---------|------|
| **serenedb** | OTLP ingest + PostgreSQL-wire SQL store (volume-backed) |
| **otel-collector** | OTLP gateway with Basic Auth multi-tenancy (`tenant.id`) |
| **grafana** | Explore & dashboards against SereneDB |
| **serenedb-soft-tune** | Optional one-shot soft memory tune for SereneDB |

After deploy, open the Grafana public URL and send OTLP to the collector (private network or public domain) with Basic Auth.

Source: [github.com/aulara-UG/aulara-observability](https://github.com/aulara-UG/aulara-observability)

## Why Deploy Aulara Observability

- OTel-native metrics, logs, and traces without running Loki / Tempo / Mimir separately
- Multi-tenant ingest via `OTEL_TENANTS` (username → `tenant.id`)
- SQL access over Postgres wire for Grafana and custom tools
- Soft SereneDB memory defaults for lower Railway RAM cost
- Maintained as a reusable base for Aulara customer observability offerings

## Common Use Cases

- Central observability backend for apps on Railway
- Ingest from external Linux hosts / Kubernetes via public OTLP + Basic Auth
- Multi-tenant SaaS telemetry (one stack, many `tenant.id` values)
- Replace or complement Prometheus/Loki/Tempo for lighter startups
- Demo / staging environment for OpenTelemetry pipelines

## Dependencies for Aulara Observability Hosting

- Railway account (Hobby or Pro recommended for volumes + public domains)
- OTLP-capable clients or agents (OpenTelemetry SDK, otelcol-contrib, etc.)
- Optional: DNS / public domain on `otel-collector` and `grafana`

### Deployment Dependencies

- **SereneDB** volume at `/var/lib/serenedb`
- **Grafana** volume at `/var/lib/grafana`
- Private networking between `otel-collector` ↔ `serenedb` ↔ `grafana`
- Service variables: `POSTGRES_PASSWORD`, `OTEL_TENANTS`, `GF_SECURITY_ADMIN_USER`, `GF_SECURITY_ADMIN_PASSWORD`, SereneDB/Grafana DB role passwords (see `.env.example` in the repo)
