FROM serenedb/serenedb:26.11.9.1

# Railway volumes are root-owned; the stock image user cannot create LOCK files.
USER root
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY soft-tune.sql /soft-tune.sql
COPY bootstrap-roles.sh /bootstrap-roles.sh
RUN chmod +x /docker-entrypoint.sh /bootstrap-roles.sh \
 && (command -v apt-get >/dev/null \
      && apt-get update \
      && apt-get install -y --no-install-recommends postgresql-client \
      && rm -rf /var/lib/apt/lists/* \
      || command -v apk >/dev/null \
      && apk add --no-cache postgresql-client \
      || echo "WARN: could not install postgresql-client; soft-tune/bootstrap may be skipped")

# Soft footprint defaults (override via env if needed)
ENV SERENEDB_DATA_DIR=/var/lib/serenedb \
    SERENEDB_CPU_THREADS=2 \
    SERENEDB_IO_THREADS=2 \
    SERENEDB_MEMORY_LIMIT=768MB \
    OTEL_INGEST_USER=otel_ingest \
    GRAFANA_DB_USER=grafana_ro

ENTRYPOINT ["/docker-entrypoint.sh"]
