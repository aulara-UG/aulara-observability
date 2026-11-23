# Deploy and Host Grafana OpenTelemetry Stack by Aulara on Railway

**Aulara**’s **Grafana OpenTelemetry** stack: **OpenTelemetry Collector** + **SereneDB** + **Grafana** — a lightweight **LGTM**-style alternative (without Loki/Tempo/Mimir). Deploy once; secrets and private networking are auto-wired.

Built by [Aulara](https://aulara.de).

```text
Apps / agents  --OTLP-->  otel-collector  --OTLP/HTTP-->  serenedb  <--SQL--  grafana
```

## About Hosting Grafana OpenTelemetry Stack by Aulara

Hosting this stack means running three services on Railway: **SereneDB** (volume-backed OTLP ingest + PostgreSQL-wire SQL), an **OpenTelemetry Collector** gateway with Basic Auth multi-tenancy, and **Grafana** for Explore and dashboards. Traffic between services uses Railway private networking. Public HTTPS domains are optional for Grafana and OTLP ingest. Passwords and a demo tenant are generated at deploy time; SereneDB engine memory is left at upstream defaults so you size the Railway service yourself.

| Service | Role |
|---------|------|
| **serenedb** | OTLP ingest + PostgreSQL-wire SQL store (volume-backed) |
| **otel-collector** | OpenTelemetry Collector / OTLP gateway, Basic Auth multi-tenancy |
| **grafana** | Grafana Explore & dashboards |

Source: [github.com/aulara-UG/aulara-observability](https://github.com/aulara-UG/aulara-observability)

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
- **Secrets:** passwords and a demo `OTEL_TENANTS` entry are generated with `${{secret()}}` at deploy
- Grafana footprint knobs and static usernames/ports are baked into the images
- SereneDB engine memory is left at SereneDB defaults; size the Railway service (and optional SQL `memory_limit`) yourself

### Why Deploy Grafana OpenTelemetry Stack by Aulara on Railway?

Railway is a singular platform to deploy your infrastructure stack. Railway will host your infrastructure so you don't have to deal with configuration, while allowing you to vertically and horizontally scale it. By deploying Grafana OpenTelemetry Stack by Aulara on Railway, you are one step closer to supporting a complete full-stack application with minimal burden. Host your servers, databases, AI agents, and more on Railway.
