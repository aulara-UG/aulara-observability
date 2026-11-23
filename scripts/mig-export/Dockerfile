FROM postgres:18-alpine
USER root
RUN apk add --no-cache python3
COPY run.sh /run.sh
COPY serve.py /serve.py
RUN chmod +x /run.sh /serve.py
ENV PORT=8080
ENTRYPOINT ["/run.sh"]
