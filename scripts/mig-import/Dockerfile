FROM alpine:3.20
RUN apk add --no-cache postgresql-client curl
COPY run.sh /run.sh
RUN chmod +x /run.sh
CMD ["/run.sh"]
