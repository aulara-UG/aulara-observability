FROM serenedb/serenedb:26.11.9.1

# Railway volumes are root-owned; the stock image user cannot create LOCK files.
USER root
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENTRYPOINT ["/docker-entrypoint.sh"]
