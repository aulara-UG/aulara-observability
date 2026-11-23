# Aulara Observability Stack

**SereneDB + OpenTelemetry Collector + Grafana** — general-purpose observability on [Railway](https://railway.com).

Built and published by **[Aulara](https://aulara.de)**.

```text
Apps / agents  --OTLP-->  otel-collector  --OTLP/HTTP-->  serenedb  <--SQL--  grafana
```

## Services

| Service | Path | Role |
|---------|------|------|
| `serenedb` | [`./serenedb`](./serenedb) | OTLP + PostgreSQL-wire store (volume) |
| `otel-collector` | [`./otel-collector`](./otel-collector) | OTLP gateway, Basic Auth multi-tenancy |
| `grafana` | [`./grafana`](./grafana) | Dashboards & Explore |

## Deploy

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/deploy/grafana-opentelemetry-stack-by-aulara)

Marketplace: **Grafana OpenTelemetry Stack by Aulara**. One-click deploy — secrets and cross-service wiring are auto-filled (`${{secret()}}`, `${{serenedb.*}}`). Edit `OTEL_TENANTS` only when you need more tenants.

Or deploy from this repo:

```bash
railway up ./serenedb --path-as-root --service serenedb
railway up ./otel-collector --path-as-root --service otel-collector
railway up ./grafana --path-as-root --service grafana
./scripts/apply-template-vars.sh
```

## Configure apps

### Private network (same Railway project)

```bash
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.railway.internal:4318
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20$(printf '%s' 'tenant:password' | base64)
```

### Public collector URL

Use the generated HTTPS domain on `otel-collector` (OTLP/HTTP on port 4318) with the same Basic Auth header.

### Multi-tenancy

Template ships with a generated `demo:<random>` tenant. Add more on `otel-collector`:

```text
OTEL_TENANTS=demo:xxxx,acme:secret
```

Authenticated username is stamped as `resource.attributes["tenant.id"]`.

## SereneDB sizing

Process defaults: `--cpu_threads=2`, `--io_threads=2` (override with `SERENEDB_CPU_THREADS` / `SERENEDB_IO_THREADS` on the service if needed). Engine memory (`memory_limit` and related SQL settings) is left to SereneDB defaults — tune yourself if you need a smaller Railway footprint.

## License

Provided by Aulara for deploying observability stacks on Railway.
