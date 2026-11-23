FROM serenedb/serenedb:26.11.9.1

# Railway volumes are root-owned; the stock image user cannot create LOCK files.
USER root
COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY bootstrap-roles.sh /bootstrap-roles.sh
RUN chmod +x /docker-entrypoint.sh /bootstrap-roles.sh \
 && (command -v apt-get >/dev/null \
      && apt-get update \
      && apt-get install -y --no-install-recommends postgresql-client \
      && rm -rf /var/lib/apt/lists/* \
      || command -v apk >/dev/null \
      && apk add --no-cache postgresql-client \
      || echo "WARN: could not install postgresql-client; role bootstrap may be skipped")

# Thread defaults keep Railway cost predictable; tune via env if needed.
ENV SERENEDB_DATA_DIR=/var/lib/serenedb \
    SERENEDB_CPU_THREADS=2 \
    SERENEDB_IO_THREADS=2 \
    OTEL_INGEST_USER=otel_ingest \
    GRAFANA_DB_USER=grafana_ro

ENTRYPOINT ["/docker-entrypoint.sh"]
