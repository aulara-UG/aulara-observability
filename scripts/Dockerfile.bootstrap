FROM postgres:16-alpine
COPY bootstrap-roles.sh /bootstrap-roles.sh
RUN chmod +x /bootstrap-roles.sh
ENTRYPOINT ["/bootstrap-roles.sh"]
