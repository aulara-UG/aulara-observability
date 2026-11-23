FROM otel/opentelemetry-collector-contrib:0.149.0 AS otelcol

FROM alpine:3.20
RUN apk add --no-cache apache2-utils ca-certificates \
 && adduser -D -H -u 10001 otel
COPY --from=otelcol /otelcol-contrib /otelcol-contrib
COPY config.yaml /etc/otelcol-contrib/config.yaml
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /otelcol-contrib

# Railway healthchecks use $PORT; OTLP stays on 4318 (service domain port).
ENV PORT=13133 \
    OTEL_INGEST_USER=otel_ingest \
    OTEL_HTPASSWD_FILE=/tmp/otel.htpasswd

USER 10001
EXPOSE 4317 4318 13133
ENTRYPOINT ["/entrypoint.sh"]
