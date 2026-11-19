#!/bin/sh
set -eu

HTPASSWD_FILE="${OTEL_HTPASSWD_FILE:-/tmp/otel.htpasswd}"
TENANTS_LIST="${OTEL_TENANTS_FILE:-/tmp/otel.tenants}"

# OTEL_TENANTS format (newline and/or comma separated):
#   customer-a:secret-a
#   customer-b:secret-b
if [ -z "${OTEL_TENANTS:-}" ]; then
  echo "OTEL_TENANTS is required (tenantId:password pairs)" >&2
  exit 1
fi

: > "$HTPASSWD_FILE"
: > "$TENANTS_LIST"
chmod 600 "$HTPASSWD_FILE" "$TENANTS_LIST"

tmp_entries="$(mktemp)"
printf '%s\n' "$OTEL_TENANTS" | tr ',' '\n' > "$tmp_entries"

first=1
while IFS= read -r line || [ -n "$line" ]; do
  line=$(printf '%s' "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac
  tenant=${line%%:*}
  password=${line#*:}
  if [ -z "$tenant" ] || [ -z "$password" ] || [ "$tenant" = "$line" ]; then
    echo "Invalid OTEL_TENANTS entry (expected tenant:password): $line" >&2
    rm -f "$tmp_entries"
    exit 1
  fi
  if [ "$first" -eq 1 ]; then
    htpasswd -cbB "$HTPASSWD_FILE" "$tenant" "$password" >/dev/null
    first=0
  else
    htpasswd -bB "$HTPASSWD_FILE" "$tenant" "$password" >/dev/null
  fi
  printf '%s\n' "$tenant" >> "$TENANTS_LIST"
done < "$tmp_entries"
rm -f "$tmp_entries"

count=$(wc -l < "$TENANTS_LIST" | tr -d ' ')
if [ "$count" -lt 1 ]; then
  echo "No tenants loaded from OTEL_TENANTS" >&2
  exit 1
fi

echo "Loaded ${count} OTLP tenant credential(s)"
export OTEL_HTPASSWD_FILE="$HTPASSWD_FILE"

exec /otelcol-contrib --config=/etc/otelcol-contrib/config.yaml
