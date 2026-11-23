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

Created automatically by `bootstrap-roles.sh` on SereneDB startup (when passwords are set):

- `otel_ingest` — OTLP Basic Auth + DML on `otel_*`
- `grafana_ro` — `SELECT` on `otel_*`

Superuser password is seeded once via `POSTGRES_PASSWORD` at first data-dir init.

## Sizing

Process thread defaults: `--cpu_threads=2`, `--io_threads=2` (override with `SERENEDB_CPU_THREADS` / `SERENEDB_IO_THREADS`).

SereneDB’s own `memory_limit` (~80% of visible RAM) is **not** overridden — tune via SQL yourself if you want a smaller Railway footprint.
