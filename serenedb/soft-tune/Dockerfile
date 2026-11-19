FROM postgres:16-alpine
COPY soft-tune.sql /soft-tune.sql
# Wait for SereneDB, apply soft memory/thread settings as superuser.
CMD sh -c 'for i in $(seq 1 60); do pg_isready -h serenedb.railway.internal -p 7890 -U postgres && break; sleep 2; done; PGPASSWORD="$POSTGRES_PASSWORD" psql -h serenedb.railway.internal -p 7890 -U postgres -d postgres -v ON_ERROR_STOP=1 -f /soft-tune.sql'
