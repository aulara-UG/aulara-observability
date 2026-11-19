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
| `serenedb-soft-tune` | [`./serenedb/soft-tune`](./serenedb/soft-tune) | Optional one-shot soft memory tune |

## Deploy

Use the Railway template (**Aulara Observability**) from the marketplace, or:

```bash
# after linking a project with the three main services
railway up ./serenedb --path-as-root --service serenedb
railway up ./otel-collector --path-as-root --service otel-collector
railway up ./grafana --path-as-root --service grafana
```

## Configure apps

### Private network (same Railway project)

```bash
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.railway.internal:4318
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic%20$(printf '%s' 'tenant:password' | base64)
```

### Public collector URL

Use the generated HTTPS domain on `otel-collector` with the same Basic Auth header.

### Multi-tenancy

Set on `otel-collector`:

```text
OTEL_TENANTS=demo:changeme,acme:secret
```

Authenticated username is stamped as `resource.attributes["tenant.id"]`.

## Soft memory (SereneDB)

Defaults: `--cpu_threads=2`, `--io_threads=2`. Optional SQL soft-tune sets `memory_limit≈768MB` (engine soft budget, not a hard OOM kill).

```bash
railway up ./serenedb/soft-tune --path-as-root --service serenedb-soft-tune
```

## License

Provided by Aulara for deploying observability stacks on Railway.
