FROM postgres:16-alpine
RUN apk add --no-cache curl openssl python3 bash
COPY smoke-test.sh /smoke-test.sh
RUN chmod +x /smoke-test.sh
ENTRYPOINT ["/smoke-test.sh"]
