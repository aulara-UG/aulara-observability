-- Soft engine budgets (survive many tenants without Railway hard OOM caps).
-- SereneDB respects memory_limit internally (spill / bound work) instead of
-- growing toward ~80% of the visible cgroup/host RAM.

SET memory_limit = '768MB';
SET GLOBAL threads = 2;
SET write_buffer_row_group_count = 2;
SET checkpoint_threshold = '8MB';

-- Default for NEW search tables only. Existing otel_* keep WITH(segment_memory_max=256MB)
-- until recreated with a lower value (see soft-tune-tables.sql).
SET segment_memory_max = 67108864;

SELECT current_setting('memory_limit') AS memory_limit,
       current_setting('threads') AS threads,
       current_setting('segment_memory_max') AS segment_memory_max_default;
