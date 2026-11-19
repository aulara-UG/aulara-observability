FROM grafana/grafana:13.2.6

USER root
COPY provisioning /etc/grafana/provisioning
# Keep dashboards outside the Railway volume mount (/var/lib/grafana).
COPY dashboards /etc/grafana/dashboards
COPY entrypoint.sh /custom-entrypoint.sh
RUN chmod +x /custom-entrypoint.sh \
 && chown -R grafana:root /etc/grafana/provisioning /etc/grafana/dashboards /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
