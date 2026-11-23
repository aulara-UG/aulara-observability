FROM alpine:3.20
RUN apk add --no-cache python3 postgresql-client curl
COPY run.sh /run.sh
RUN chmod +x /run.sh
ENV PORT=8080
CMD ["/run.sh"]
