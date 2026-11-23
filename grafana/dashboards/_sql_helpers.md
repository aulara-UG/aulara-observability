# SereneDB TIMESTAMP_NS SQL contract (v3)

## CPU busy (never avg all states)
```sql
1 - avg(value)  -- WHERE metric_name='system.cpu.utilization' AND attributes->>'state'='idle'
```

## Memory used
```sql
value  -- WHERE metric_name='system.memory.utilization' AND attributes->>'state'='used'
```

## Freshness / UP (never bare now()-interval vs TIMESTAMP_NS)
```sql
epoch_ns(max("timestamp")) > (extract(epoch from now()) - 300) * 1000000000
-- or
"timestamp" > make_timestamp_ns((extract(epoch from now()) - 300)::bigint * 1000000000)
```

## True errors (never body keyword spam)
```sql
(
  log_attributes->>'log.kind' = 'error'
  OR log_attributes->>'exception.type' IS NOT NULL
  OR upper(coalesce(severity_text,'')) IN ('ERROR','FATAL','CRITICAL')
  OR severity_number >= 17
)
AND NOT backup.success markers
```

## Process CPU
```sql
resource_attributes->>'process.executable.name'
sum(value) FILTER (WHERE attributes->>'state' IN ('user','system'))
```

## Uptime
STAT panel only — never timeseries.
