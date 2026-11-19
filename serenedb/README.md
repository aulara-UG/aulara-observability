# SereneDB (OTLP + PostgreSQL wire)

Pinned base: `serenedb/serenedb:26.11.9.1`

## Listeners

| Protocol | Bind | Purpose |
|----------|------|---------|
| PostgreSQL wire | `0.0.0.0:7890` | SQL / Grafana |
| OTLP/HTTP | `0.0.0.0:4318` | `?api=otel` ingest |

Data directory: `/var/lib/serenedb` (Railway volume `serenedb-volume`).

## Docker notes

The official image entrypoint appends its own `--listen`, which would drop the OTLP listener. This Dockerfile replaces `ENTRYPOINT` with `serened` and sets `CMD` for both listeners.

Railway volumes are root-owned; the image runs as `USER root` so lockfiles can be created on the mount.

## Roles

Created by the one-shot `role-bootstrap` service:

- `otel_ingest` — OTLP Basic Auth + DML on `otel_*`
- `grafana_ro` — `SELECT` on `otel_*`

Superuser password is seeded once via `POSTGRES_PASSWORD` at first data-dir init.

## Soft memory tuning (no Railway hard RAM cap)

SereneDB defaults to a large thread pool and `memory_limit ≈ 80%` of visible RAM, so it happily grows on Railway. Prefer **engine soft limits**:

| Knob | Default here | Effect |
|------|--------------|--------|
| `--cpu_threads` / `--io_threads` | `2` / `2` | Lower write peaks (`≈ segment_memory_max × threads`) |
| `SET memory_limit` | `768MB` | Engine bounds itself (spill/limit), process stays up |
| `SET GLOBAL threads` | `2` | Query/write parallelism |
| `segment_memory_max` (table) | still `256MB` on existing `otel_*` | Fixed at `CREATE TABLE`; recreate to lower |

Override at deploy: `SERENEDB_CPU_THREADS`, `SERENEDB_IO_THREADS`.

Apply SQL soft settings after deploy:

```bash
railway up ./serenedb/soft-tune --path-as-root --service role-bootstrap -m "serenedb soft memory tune"
```

(or a dedicated one-shot service). Pass `POSTGRES_PASSWORD` from SereneDB.
