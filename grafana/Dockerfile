FROM grafana/grafana:13.2.6

USER root
COPY provisioning /etc/grafana/provisioning
# Keep dashboards outside the Railway volume mount (/var/lib/grafana).
COPY dashboards /etc/grafana/dashboards
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh \
 && chown -R grafana:root /etc/grafana/provisioning /etc/grafana/dashboards /custom-entrypoint.sh

# Low-footprint + zero-config defaults (no Railway prompts for these).
ENV GF_SECURITY_ADMIN_USER=admin \
    GF_AUTH_ANONYMOUS_ENABLED=false \
    GF_USERS_ALLOW_SIGN_UP=false \
    GF_INSTALL_PLUGINS= \
    GF_SERVER_HTTP_PORT=3000 \
    PORT=3000 \
    SERENEDB_PORT=7890 \
    GRAFANA_DB_USER=grafana_ro \
    GF_ANALYTICS_REPORTING_ENABLED=false \
    GF_ANALYTICS_CHECK_FOR_UPDATES=false \
    GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false \
    GF_NEWS_NEWS_FEED_ENABLED=false \
    GF_HELP_ENABLED=false \
    GF_PROFILE_ENABLED=false \
    GF_UNIFIED_ALERTING_ENABLED=false \
    GF_ALERTING_ENABLED=false \
    GF_EXPLORE_ENABLED=true \
    GF_LOG_LEVEL=warn \
    GF_SERVER_ENABLE_GZIP=true \
    GF_DATABASE_WAL=true \
    GF_DATAPROXY_LOGGING=false \
    GF_LIVE_MAX_CONNECTIONS=0 \
    GOMEMLIMIT=384MiB \
    GOGC=40

ENTRYPOINT ["/custom-entrypoint.sh"]
