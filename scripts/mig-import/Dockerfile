FROM postgres:18-alpine
USER root
RUN apk add --no-cache curl
COPY run.sh /run.sh
RUN chmod +x /run.sh
ENTRYPOINT ["/run.sh"]
