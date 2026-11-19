# Deploy and Host Grafana OpenTelemetry Stack by Aulara on Railway

**Aulara**’s **Grafana OpenTelemetry** stack: **OpenTelemetry Collector** + **SereneDB** + **Grafana** — a lightweight **LGTM**-style alternative (without Loki/Tempo/Mimir).

Built by [Aulara](https://aulara.de).

```text
Apps / agents  --OTLP-->  otel-collector  --OTLP/HTTP-->  serenedb  <--SQL--  grafana
```

## About Hosting Grafana OpenTelemetry Stack by Aulara

| Service | Role |
|---------|------|
| **serenedb** | OTLP ingest + PostgreSQL-wire SQL store (volume-backed) |
| **otel-collector** | OpenTelemetry Collector / OTLP gateway, Basic Auth multi-tenancy |
| **grafana** | Grafana Explore & dashboards |
| **serenedb-soft-tune** | Optional soft memory tune for SereneDB |

Source: [github.com/aulara-UG/aulara-observability](https://github.com/aulara-UG/aulara-observability)

## Why Deploy Grafana OpenTelemetry Stack by Aulara

- **Grafana** + **OpenTelemetry** metrics, logs, and traces in one Railway deploy
- LGTM-like observability without operating Loki / Tempo / Mimir
- Multi-tenant OTLP via `OTEL_TENANTS` → `tenant.id`
- SQL over Postgres wire for Grafana and tooling
- Soft SereneDB memory defaults for lower Railway cost

## Common Use Cases

- Host **Grafana** and an **OpenTelemetry Collector** backend on Railway
- Replace or simplify classic **LGTM** stacks for startups
- Public OTLP ingest from Linux / Kubernetes agents
- Multi-tenant SaaS telemetry
- OTLP demos and staging environments

## Dependencies for Grafana OpenTelemetry Stack by Aulara Hosting

- Railway account (Hobby or Pro recommended)
- OpenTelemetry / OTLP clients (SDK, otelcol-contrib, …)
- Optional public domains for Grafana and the collector

### Deployment Dependencies

- SereneDB volume `/var/lib/serenedb`, Grafana volume `/var/lib/grafana`
- Private networking between collector, SereneDB, and Grafana
- **Auto-wired:** Grafana/collector connect to SereneDB via `${{serenedb.*}}`; Grafana URL via `${{RAILWAY_PUBLIC_DOMAIN}}`
- **You set once at deploy:** SereneDB passwords (`POSTGRES_PASSWORD`, ingest/Grafana DB roles), Grafana admin password, and `OTEL_TENANTS` (`user:password` pairs)
- Grafana footprint knobs are baked into the image — not prompted at deploy
