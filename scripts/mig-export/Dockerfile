FROM postgres:18-alpine
USER root
RUN apk add --no-cache python3
COPY run.sh /run.sh
RUN chmod +x /run.sh
ENV PORT=8080
# Bypass the stock postgres entrypoint so we only run the dump helper.
ENTRYPOINT ["/run.sh"]
