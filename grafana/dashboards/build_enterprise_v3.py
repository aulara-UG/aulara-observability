#!/usr/bin/env python3
"""Boss-ready CytoSorbents Grafana dashboards (SereneDB TIMESTAMP_NS).

Metric contract (verified live):
  CPU busy  = 1 - avg(idle) on system.cpu.utilization
  Mem used  = state='used' on system.memory.utilization
  Host UP   = max(timestamp) within 5m via make_timestamp_ns / epoch_ns only
  Errors    = log.kind=error OR exception OR severity ERROR/FATAL/CRITICAL — never body spam
  Uptime    = STAT only (never timeseries)
  Process   = resource_attributes process.executable.name + sum(user+system)
"""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
DS = {"type": "grafana-postgresql-datasource", "uid": "serenedb"}

# --- SQL contract helpers ---------------------------------------------------

ERROR_PRED = """(
    log_attributes->>'log.kind' = 'error'
    OR log_attributes->>'exception.type' IS NOT NULL
    OR upper(coalesce(severity_text, '')) IN ('ERROR', 'FATAL', 'CRITICAL')
    OR severity_number >= 17
  )
  AND NOT (
    log_attributes->>'backup.status' = 'success'
    OR log_attributes->>'event.name' = 'backup.success'
    OR log_attributes->>'event.name' = 'otel-backup-event'
  )"""

BACKUP_SUCCESS = """(
    log_attributes->>'backup.status' = 'success'
    OR log_attributes->>'event.name' = 'backup.success'
    OR (log_attributes->>'log.kind' = 'backup' AND body ~* '(Done|completed|success)')
  )"""

BACKUP_FAIL = """(
    log_attributes->>'backup.status' IN ('failed','failure','error')
    OR log_attributes->>'event.name' = 'backup.failed'
    OR (log_attributes->>'log.kind' = 'backup' AND body ~* '(ERROR|FAILED|fail\\()')
  )"""

BACKUP_ANY = """(
    log_attributes->>'log.kind' = 'backup'
    OR log_attributes->>'event.name' LIKE 'backup.%'
    OR coalesce(resource_attributes->>'service.name', service_name) ILIKE '%backup%'
  )"""

FRESH_5M = "epoch_ns({col}) > (extract(epoch from now()) - 300) * 1000000000"
FRESH_WHERE = (
    '"timestamp" > make_timestamp_ns('
    "(extract(epoch from now()) - 300)::bigint * 1000000000)"
)

# Corrected metric fragments
CPU_BUSY_TS = """
SELECT $__timeGroupAlias("timestamp", $__interval),
       {metric_expr} AS metric,
       1 - avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND attributes->>'state' = 'idle'
  AND $__timeFilter("timestamp")
  AND {host_filter}
GROUP BY 1, 2
ORDER BY 1
""".strip()

MEM_USED_TS = """
SELECT $__timeGroupAlias("timestamp", $__interval),
       {metric_expr} AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND attributes->>'state' = 'used'
  AND $__timeFilter("timestamp")
  AND {host_filter}
GROUP BY 1, 2
ORDER BY 1
""".strip()


def cpu_busy_latest(host_filter: str) -> str:
    return f"""
SELECT 1 - avg(value)
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND attributes->>'state' = 'idle'
  AND {host_filter}
  AND {FRESH_WHERE}
""".strip()


def mem_used_latest(host_filter: str) -> str:
    return f"""
SELECT value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND attributes->>'state' = 'used'
  AND {host_filter}
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC
LIMIT 1
""".strip()


def cpu_busy_percentile(p: float, host_filter: str, fresh: bool = False) -> str:
    fresh_clause = f"AND {FRESH_WHERE}" if fresh else ""
    return f"""
WITH samples AS (
  SELECT resource_attributes->>'host.name' AS host,
         attributes->>'cpu' AS cpu,
         date_trunc('minute', ("timestamp")::timestamp) AS bucket,
         1 - avg(value) AS busy
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.cpu.utilization'
    AND attributes->>'state' = 'idle'
    AND $__timeFilter("timestamp")
    AND {host_filter}
    {fresh_clause}
  GROUP BY 1, 2, 3
)
SELECT percentile_cont({p}) WITHIN GROUP (ORDER BY busy) FROM samples
""".strip()


def mem_used_percentile(p: float, host_filter: str, fresh: bool = False) -> str:
    fresh_clause = f"AND {FRESH_WHERE}" if fresh else ""
    return f"""
SELECT percentile_cont({p}) WITHIN GROUP (ORDER BY value)
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND attributes->>'state' = 'used'
  AND $__timeFilter("timestamp")
  AND {host_filter}
  {fresh_clause}
""".strip()


# --- panel builders ---------------------------------------------------------

THRESH_OK_BAD = {
    "mode": "absolute",
    "steps": [{"color": "green", "value": None}, {"color": "red", "value": 1}],
}
THRESH_DISK = {
    "mode": "absolute",
    "steps": [
        {"color": "red", "value": None},
        {"color": "yellow", "value": 0.15},
        {"color": "green", "value": 0.25},
    ],
}
THRESH_CPU = {
    "mode": "absolute",
    "steps": [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 0.7},
        {"color": "red", "value": 0.9},
    ],
}
THRESH_MEM = {
    "mode": "absolute",
    "steps": [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 0.8},
        {"color": "red", "value": 0.92},
    ],
}
THRESH_ERR = {
    "mode": "absolute",
    "steps": [
        {"color": "green", "value": None},
        {"color": "yellow", "value": 1},
        {"color": "orange", "value": 10},
        {"color": "red", "value": 50},
    ],
}

STATUS_MAP = {
    "matcher": {"id": "byName", "options": "status"},
    "properties": [
        {
            "id": "custom.cellOptions",
            "value": {"type": "color-background", "mode": "basic"},
        },
        {
            "id": "mappings",
            "value": [
                {
                    "type": "value",
                    "options": {
                        "UP": {"color": "green", "index": 0, "text": "UP"},
                        "DOWN": {"color": "red", "index": 1, "text": "DOWN"},
                        "OK": {"color": "green", "index": 0, "text": "OK"},
                        "FAIL": {"color": "red", "index": 1, "text": "FAIL"},
                        "STALE": {"color": "orange", "index": 2, "text": "STALE"},
                        "QUIET": {"color": "yellow", "index": 3, "text": "QUIET"},
                        "UNKNOWN": {"color": "super-light-yellow", "index": 4, "text": "UNKNOWN"},
                        "RECENT_BOOT": {"color": "purple", "index": 5, "text": "RECENT BOOT"},
                        "STABLE": {"color": "green", "index": 6, "text": "STABLE"},
                    },
                }
            ],
        },
    ],
}


def panel_stat(
    pid,
    title,
    sql,
    x,
    y,
    w=4,
    h=4,
    unit=None,
    desc="",
    thresholds=None,
    color_mode="value",
    mappings=None,
    no_value=None,
):
    fc = {
        "defaults": {
            "thresholds": thresholds
            or {"mode": "absolute", "steps": [{"color": "blue", "value": None}]},
        },
        "overrides": [],
    }
    if unit:
        fc["defaults"]["unit"] = unit
    if mappings:
        fc["defaults"]["mappings"] = mappings
    if no_value is not None:
        fc["defaults"]["noValue"] = no_value
    return {
        "type": "stat",
        "id": pid,
        "title": title,
        "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": fc,
        "options": {
            "reduceOptions": {"calcs": ["lastNotNull"]},
            "colorMode": color_mode,
            "graphMode": "none",
            "justifyMode": "center",
            "textMode": "auto",
        },
        "targets": [
            {
                "refId": "A",
                "datasource": DS,
                "format": "table",
                "rawQuery": True,
                "rawSql": sql,
            }
        ],
    }


def panel_table(pid, title, sql, x, y, w=24, h=8, desc="", overrides=None):
    return {
        "type": "table",
        "id": pid,
        "title": title,
        "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {"custom": {"align": "auto", "filterable": True}},
            "overrides": overrides or [],
        },
        "options": {"showHeader": True, "footer": {"show": False}, "cellHeight": "sm"},
        "targets": [
            {
                "refId": "A",
                "datasource": DS,
                "format": "table",
                "rawQuery": True,
                "rawSql": sql,
            }
        ],
    }


def panel_ts(pid, title, sql, x, y, w=12, h=8, unit="short", desc="", bars=False, soft_max=None):
    custom = {
        "drawStyle": "bars" if bars else "line",
        "lineWidth": 2,
        "fillOpacity": 45 if bars else 18,
        "showPoints": "never",
        "spanNulls": True,
    }
    if bars:
        custom["stacking"] = {"mode": "normal"}
    defaults = {"unit": unit, "custom": custom}
    if soft_max is not None:
        defaults["max"] = soft_max
    return {
        "type": "timeseries",
        "id": pid,
        "title": title,
        "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": {"defaults": defaults, "overrides": []},
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            {
                "refId": "A",
                "datasource": DS,
                "format": "time_series",
                "rawQuery": True,
                "rawSql": sql,
            }
        ],
    }


def panel_row(pid, title, y):
    return {
        "type": "row",
        "id": pid,
        "title": title,
        "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
        "collapsed": False,
        "panels": [],
    }


def panel_text(pid, title, content, x, y, w=24, h=3):
    return {
        "type": "text",
        "id": pid,
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {"mode": "markdown", "content": content},
    }


DEFAULT_HOST = "CSE-01"
DEFAULT_SERVICE = "nextcloud-nextcloud"


def host_var(multi=True, include_all=True, name="host"):
    # Custom (not query) so the dropdown always has values — query vars caused empty $host → No data.
    hosts = "CSE-01,nextcloud-aio,dropbox-backup-service,litdb-dev,LitDB-AI-Agent"
    if include_all:
        current = {"selected": True, "text": "All", "value": "$__all"}
    else:
        current = {"selected": True, "text": DEFAULT_HOST, "value": DEFAULT_HOST}
    return {
        "current": current,
        "includeAll": include_all,
        "allValue": "CSE-01,nextcloud-aio,dropbox-backup-service,litdb-dev,LitDB-AI-Agent" if include_all else None,
        "label": "Host",
        "multi": multi,
        "name": name,
        "query": hosts,
        "type": "custom",
        "options": [
            {"selected": h == DEFAULT_HOST and not include_all, "text": h, "value": h}
            for h in hosts.split(",")
        ],
        "sort": 1,
    }


def service_var(name="service", multi=True, include_all=True, where="TRUE"):
    # Prefer a stable custom list for the single-select Service Detail default.
    # Multi/all dashboards still use a query so new services appear.
    if not multi and not include_all:
        services = [
            "nextcloud-nextcloud",
            "cse-risk-matrix-backend",
            "forgejo",
            "moodle",
            "nextcloud-db",
            "nextcloud-redis",
            "nextcloud-backup",
            "openproject",
        ]
        return {
            "current": {"selected": True, "text": DEFAULT_SERVICE, "value": DEFAULT_SERVICE},
            "includeAll": False,
            "label": "Service",
            "multi": False,
            "name": name,
            "query": ",".join(services),
            "type": "custom",
            "options": [
                {"selected": s == DEFAULT_SERVICE, "text": s, "value": s} for s in services
            ],
            "sort": 1,
        }
    q = (
        "SELECT DISTINCT coalesce(resource_attributes->>'service.name', service_name) AS __text, "
        "coalesce(resource_attributes->>'service.name', service_name) AS __value "
        "FROM otel_logs "
        "WHERE coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL "
        f'AND "timestamp" > make_timestamp_ns((extract(epoch from now()) - 86400)::bigint * 1000000000) '
        f"AND ({where}) ORDER BY 1"
    )
    current = {"selected": True, "text": "All", "value": "$__all"} if include_all else {
        "selected": True, "text": DEFAULT_SERVICE, "value": DEFAULT_SERVICE
    }
    return {
        "current": current,
        "datasource": DS,
        "definition": q,
        "includeAll": include_all,
        "label": "Service",
        "multi": multi,
        "name": name,
        "query": q,
        "refresh": 1,
        "type": "query",
        "sort": 1,
    }


# Never includeVars on Host/Service Detail links from pages that lack those vars —
# Grafana would open them with empty $host/$service and every panel shows No data.
LINKS_COMMON = [
    {
        "title": "Command Center",
        "type": "link",
        "icon": "home",
        "url": "/d/cyto-command-center/command-center",
        "keepTime": True,
    },
    {
        "title": "Fleet Infrastructure",
        "type": "link",
        "icon": "dashboard",
        "url": "/d/cyto-fleet-infra/fleet-infrastructure",
        "keepTime": True,
    },
    {
        "title": "Host Detail",
        "type": "link",
        "icon": "dashboard",
        "url": f"/d/cyto-server-detail/host-infrastructure-detail?var-host={DEFAULT_HOST}",
        "keepTime": True,
        "includeVars": False,
    },
    {
        "title": "Service Detail",
        "type": "link",
        "icon": "dashboard",
        "url": f"/d/cyto-service-detail/service-detail?var-service={DEFAULT_SERVICE}",
        "keepTime": True,
        "includeVars": False,
    },
    {
        "title": "Backup Operations",
        "type": "link",
        "icon": "dashboard",
        "url": "/d/cyto-backups/backup-operations",
        "keepTime": True,
    },
    {
        "title": "Errors & Incidents",
        "type": "link",
        "icon": "dashboard",
        "url": "/d/cyto-errors/errors-incidents",
        "keepTime": True,
    },
]


UP_DOWN_MAP = [
    {
        "type": "value",
        "options": {
            "UP": {"color": "green", "index": 0, "text": "UP"},
            "DOWN": {"color": "red", "index": 1, "text": "DOWN"},
            "QUIET": {"color": "yellow", "index": 2, "text": "QUIET"},
        },
    }
]


def dash(title, uid, tags, panels, templating, links=None, refresh="30s", time_from="now-24h"):
    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": links if links is not None else LINKS_COMMON,
        "panels": panels,
        "refresh": refresh,
        "schemaVersion": 39,
        "tags": ["cytosorbents", "enterprise", "observability"] + tags,
        "templating": {"list": templating},
        "time": {"from": time_from, "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 3,
    }


# --- dashboards -------------------------------------------------------------


def build_command_center():
    panels = [
        panel_text(
            1,
            "",
            f"""# CytoSorbents Observability — Command Center
**Boss walkthrough:** Fleet health → pick a host → Service Detail → Backups → Incidents.
Dashboards: [Fleet](/d/cyto-fleet-infra) · [Host Detail](/d/cyto-server-detail/host-infrastructure-detail?var-host={DEFAULT_HOST}) · [Service Detail](/d/cyto-service-detail/service-detail?var-service={DEFAULT_SERVICE}) · [Backups](/d/cyto-backups) · [Incidents](/d/cyto-errors)""",
            0,
            0,
            h=3,
        ),
        panel_stat(
            2,
            "Hosts UP",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name')
FROM otel_metrics_gauge
WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}""",
            0,
            3,
            w=3,
            color_mode="background",
            thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            desc="Hosts with system.uptime sample in the last 5 minutes.",
        ),
        panel_stat(
            3,
            "Hosts silent (>5m)",
            f"""
WITH all_hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host FROM otel_metrics_gauge
  WHERE resource_attributes->>'host.name' IS NOT NULL AND $__timeFilter("timestamp")
),
alive AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}
)
SELECT count(*) FROM all_hosts a WHERE NOT EXISTS (SELECT 1 FROM alive b WHERE b.host = a.host)
""".strip(),
            3,
            3,
            w=3,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            4,
            "Fleet CPU p95",
            cpu_busy_percentile(0.95, "TRUE", fresh=True),
            6,
            3,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
            desc="p95 of CPU busy = 1 - idle (not raw state average).",
        ),
        panel_stat(
            5,
            "Fleet mem p95",
            mem_used_percentile(0.95, "TRUE", fresh=True),
            9,
            3,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
            desc="p95 of memory state=used only.",
        ),
        panel_stat(
            6,
            "True error events",
            f"""SELECT count(*) FROM otel_logs
WHERE $__timeFilter("timestamp") AND {ERROR_PRED}""",
            12,
            3,
            w=3,
            thresholds=THRESH_ERR,
            color_mode="background",
            desc="log.kind=error / exception / severity ERROR+ only — not INFO body matches.",
        ),
        panel_stat(
            7,
            "Hours since last backup OK",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
  ELSE (extract(epoch from now())*1e9 - epoch_ns(max("timestamp"))) / 3.6e12
END FROM otel_logs WHERE {BACKUP_SUCCESS}""",
            15,
            3,
            w=3,
            unit="h",
            thresholds={
                "mode": "absolute",
                "steps": [
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 12},
                    {"color": "red", "value": 30},
                ],
            },
            color_mode="background",
        ),
        panel_stat(
            8,
            "Backup failures (range)",
            f"""SELECT count(*) FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_FAIL}""",
            18,
            3,
            w=3,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            9,
            "Services seen",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name))
FROM otel_logs WHERE $__timeFilter("timestamp")
  AND coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL""",
            21,
            3,
            w=3,
        ),
        panel_table(
            20,
            "Host status board",
            f"""
WITH hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host
  FROM otel_metrics_gauge
  WHERE resource_attributes->>'host.name' IS NOT NULL AND $__timeFilter("timestamp")
),
alive AS (
  SELECT resource_attributes->>'host.name' AS host, max("timestamp") AS last_seen
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}
  GROUP BY 1
),
cpu AS (
  SELECT resource_attributes->>'host.name' AS host, 1 - avg(value) AS cpu_busy
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.cpu.utilization' AND attributes->>'state' = 'idle' AND {FRESH_WHERE}
  GROUP BY 1
),
mem AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host, value AS mem_used
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.memory.utilization' AND attributes->>'state' = 'used' AND {FRESH_WHERE}
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
uptime AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host, value AS uptime_s
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
errs AS (
  SELECT resource_attributes->>'host.name' AS host, count(*) AS errors
  FROM otel_logs WHERE $__timeFilter("timestamp") AND {ERROR_PRED}
  GROUP BY 1
)
SELECT h.host,
       CASE WHEN a.host IS NOT NULL THEN 'UP' ELSE 'DOWN' END AS status,
       u.uptime_s,
       c.cpu_busy,
       m.mem_used,
       coalesce(e.errors, 0) AS errors
FROM hosts h
LEFT JOIN alive a ON a.host = h.host
LEFT JOIN cpu c ON c.host = h.host
LEFT JOIN mem m ON m.host = h.host
LEFT JOIN uptime u ON u.host = h.host
LEFT JOIN errs e ON e.host = h.host
ORDER BY status ASC, errors DESC, h.host
""".strip(),
            0,
            7,
            h=9,
            desc="Live board. Open Host Detail with the host variable set.",
            overrides=[
                STATUS_MAP,
                {"matcher": {"id": "byName", "options": "uptime_s"}, "properties": [{"id": "unit", "value": "dtdurations"}]},
                {"matcher": {"id": "byName", "options": "cpu_busy"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "mem_used"}, "properties": [{"id": "unit", "value": "percentunit"}]},
            ],
        ),
        panel_ts(
            30,
            "Fleet CPU busy (1 - idle)",
            CPU_BUSY_TS.format(
                metric_expr="resource_attributes->>'host.name'",
                host_filter="TRUE",
            ),
            0,
            16,
            w=12,
            unit="percentunit",
            soft_max=1,
            desc="Corrected: busy = 1 − idle. Never averages all CPU states.",
        ),
        panel_ts(
            31,
            "Fleet memory used",
            MEM_USED_TS.format(
                metric_expr="resource_attributes->>'host.name'",
                host_filter="TRUE",
            ),
            12,
            16,
            w=12,
            unit="percentunit",
            soft_max=1,
            desc="Corrected: state=used only.",
        ),
        panel_table(
            40,
            "Backup last success by host",
            f"""
SELECT resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       max("timestamp") FILTER (WHERE {BACKUP_SUCCESS}) AS last_success,
       max("timestamp") FILTER (WHERE {BACKUP_FAIL}) AS last_failure,
       count(*) FILTER (WHERE {BACKUP_SUCCESS}) AS successes,
       count(*) FILTER (WHERE {BACKUP_FAIL}) AS failures
FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_ANY}
GROUP BY 1, 2
ORDER BY last_success DESC NULLS LAST
LIMIT 40
""".strip(),
            0,
            24,
            h=8,
            desc="Jump to Backup Operations for full pipeline detail.",
            overrides=[STATUS_MAP],
        ),
    ]
    return dash(
        "Command Center",
        "cyto-command-center",
        ["home", "command-center"],
        panels,
        [],
        time_from="now-12h",
    )


def build_fleet_infra():
    host_matrix = f"""
WITH hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host
  FROM otel_metrics_gauge
  WHERE resource_attributes->>'host.name' IS NOT NULL AND $__timeFilter("timestamp")
),
cpu AS (
  SELECT host,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY busy) AS cpu_p50,
         percentile_cont(0.95) WITHIN GROUP (ORDER BY busy) AS cpu_p95,
         percentile_cont(0.99) WITHIN GROUP (ORDER BY busy) AS cpu_p99,
         avg(busy) AS cpu_avg
  FROM (
    SELECT resource_attributes->>'host.name' AS host,
           attributes->>'cpu' AS cpu,
           date_trunc('minute', ("timestamp")::timestamp) AS bucket,
           1 - avg(value) AS busy
    FROM otel_metrics_gauge
    WHERE metric_name = 'system.cpu.utilization'
      AND attributes->>'state' = 'idle'
      AND $__timeFilter("timestamp")
    GROUP BY 1, 2, 3
  ) s
  GROUP BY host
),
mem AS (
  SELECT resource_attributes->>'host.name' AS host,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS mem_p50,
         percentile_cont(0.95) WITHIN GROUP (ORDER BY value) AS mem_p95,
         percentile_cont(0.99) WITHIN GROUP (ORDER BY value) AS mem_p99
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.memory.utilization'
    AND attributes->>'state' = 'used'
    AND $__timeFilter("timestamp")
  GROUP BY 1
),
mem_now AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host, value AS mem_now
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.memory.utilization'
    AND attributes->>'state' = 'used'
    AND {FRESH_WHERE}
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
uptime AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host,
         value AS uptime_s,
         "timestamp" AS last_metric
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND $__timeFilter("timestamp")
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
disk AS (
  SELECT resource_attributes->>'host.name' AS host,
         max(value) FILTER (WHERE attributes->>'state' = 'free' AND attributes->>'mountpoint' = '/') AS free_bytes,
         max(value) FILTER (WHERE attributes->>'state' = 'used' AND attributes->>'mountpoint' = '/') AS used_bytes
  FROM otel_metrics_sum
  WHERE metric_name = 'system.filesystem.usage' AND {FRESH_WHERE}
  GROUP BY 1
),
errs AS (
  SELECT resource_attributes->>'host.name' AS host, count(*) AS errors
  FROM otel_logs WHERE $__timeFilter("timestamp") AND {ERROR_PRED}
  GROUP BY 1
)
SELECT h.host,
       CASE WHEN u.last_metric IS NOT NULL AND {FRESH_5M.format(col='u.last_metric')} THEN 'UP' ELSE 'DOWN' END AS status,
       u.uptime_s AS host_uptime,
       CASE WHEN u.uptime_s < 7200 THEN 'RECENT_BOOT' ELSE 'STABLE' END AS boot,
       c.cpu_p50, c.cpu_p95, c.cpu_p99, c.cpu_avg,
       m.mem_p50, m.mem_p95, m.mem_p99, mn.mem_now AS host_mem,
       CASE WHEN coalesce(d.free_bytes,0)+coalesce(d.used_bytes,0) > 0
            THEN d.free_bytes::double precision / (d.free_bytes + d.used_bytes)
            ELSE NULL END AS disk_free_ratio,
       d.free_bytes AS disk_free_bytes,
       coalesce(e.errors, 0) AS errors
FROM hosts h
LEFT JOIN cpu c ON c.host = h.host
LEFT JOIN mem m ON m.host = h.host
LEFT JOIN mem_now mn ON mn.host = h.host
LEFT JOIN uptime u ON u.host = h.host
LEFT JOIN disk d ON d.host = h.host
LEFT JOIN errs e ON e.host = h.host
ORDER BY status ASC, errors DESC, h.host
""".strip()

    panels = [
        panel_row(100, "Fleet pulse", 0),
        panel_stat(
            1,
            "Hosts UP",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name')
FROM otel_metrics_gauge WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}""",
            0,
            1,
            w=3,
            color_mode="background",
            thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}]},
        ),
        panel_stat(
            2,
            "Hosts silent (>5m)",
            f"""
WITH all_hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host FROM otel_metrics_gauge
  WHERE resource_attributes->>'host.name' IS NOT NULL AND $__timeFilter("timestamp")
),
alive AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND {FRESH_WHERE}
)
SELECT count(*) FROM all_hosts a WHERE NOT EXISTS (SELECT 1 FROM alive b WHERE b.host = a.host)
""".strip(),
            3,
            1,
            w=3,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            3,
            "Fleet CPU p50",
            cpu_busy_percentile(0.5, "TRUE"),
            6,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            4,
            "Fleet CPU p95",
            cpu_busy_percentile(0.95, "TRUE"),
            9,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
            desc="Busy = 1 − idle.",
        ),
        panel_stat(
            5,
            "Fleet CPU p99",
            cpu_busy_percentile(0.99, "TRUE"),
            12,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            6,
            "Fleet mem p95",
            mem_used_percentile(0.95, "TRUE"),
            15,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            7,
            "Worst disk free",
            f"""
WITH d AS (
  SELECT resource_attributes->>'host.name' AS host,
         max(value) FILTER (WHERE attributes->>'state'='free' AND attributes->>'mountpoint'='/') AS free_b,
         max(value) FILTER (WHERE attributes->>'state'='used' AND attributes->>'mountpoint'='/') AS used_b
  FROM otel_metrics_sum
  WHERE metric_name='system.filesystem.usage' AND {FRESH_WHERE}
  GROUP BY 1
)
SELECT min(free_b::double precision / NULLIF(free_b+used_b,0)) FROM d
""".strip(),
            18,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_DISK,
            color_mode="background",
        ),
        panel_stat(
            8,
            "True errors",
            f"""SELECT count(*) FROM otel_logs WHERE $__timeFilter("timestamp") AND {ERROR_PRED}""",
            21,
            1,
            w=3,
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_table(
            10,
            "Host infrastructure matrix",
            host_matrix,
            0,
            5,
            h=10,
            desc="UP/DOWN via nanosecond freshness. CPU/mem percentiles on corrected series.",
            overrides=[
                STATUS_MAP,
                {
                    "matcher": {"id": "byName", "options": "boot"},
                    "properties": [
                        {
                            "id": "custom.cellOptions",
                            "value": {"type": "color-background", "mode": "basic"},
                        },
                        {
                            "id": "mappings",
                            "value": [
                                {
                                    "type": "value",
                                    "options": {
                                        "RECENT_BOOT": {
                                            "color": "purple",
                                            "index": 0,
                                            "text": "RECENT BOOT",
                                        },
                                        "STABLE": {"color": "green", "index": 1, "text": "STABLE"},
                                    },
                                }
                            ],
                        },
                    ],
                },
                {"matcher": {"id": "byName", "options": "host_uptime"}, "properties": [{"id": "unit", "value": "dtdurations"}]},
                {"matcher": {"id": "byName", "options": "cpu_p50"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "cpu_p95"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "cpu_p99"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "cpu_avg"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "mem_p50"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "mem_p95"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "mem_p99"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "host_mem"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "disk_free_ratio"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "disk_free_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
            ],
        ),
        panel_ts(
            20,
            "CPU busy by host (1 − idle)",
            CPU_BUSY_TS.format(
                metric_expr="resource_attributes->>'host.name'",
                host_filter="resource_attributes->>'host.name' IN (${host:sqlstring})",
            ),
            0,
            15,
            w=12,
            unit="percentunit",
            soft_max=1,
        ),
        panel_ts(
            21,
            "Memory used by host",
            MEM_USED_TS.format(
                metric_expr="resource_attributes->>'host.name'",
                host_filter="resource_attributes->>'host.name' IN (${host:sqlstring})",
            ),
            12,
            15,
            w=12,
            unit="percentunit",
            soft_max=1,
        ),
        panel_ts(
            22,
            "Root disk free ratio",
            f"""
WITH snap AS (
  SELECT $__timeGroup("timestamp", $__interval) AS time,
         resource_attributes->>'host.name' AS host,
         max(value) FILTER (WHERE attributes->>'state'='free' AND attributes->>'mountpoint'='/') AS free_b,
         max(value) FILTER (WHERE attributes->>'state'='used' AND attributes->>'mountpoint'='/') AS used_b
  FROM otel_metrics_sum
  WHERE metric_name='system.filesystem.usage'
    AND $__timeFilter("timestamp")
    AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  GROUP BY 1, 2
)
SELECT time, host AS metric,
       free_b::double precision / NULLIF(free_b+used_b,0) AS value
FROM snap WHERE free_b IS NOT NULL ORDER BY 1
""".strip(),
            0,
            23,
            w=12,
            unit="percentunit",
        ),
        panel_ts(
            23,
            "Load average (1m)",
            """SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.load_average.1m'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
GROUP BY 1, 2 ORDER BY 1""",
            12,
            23,
            w=12,
        ),
        panel_ts(
            24,
            "True error burn by host",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2 ORDER BY 1""",
            0,
            31,
            w=24,
            bars=True,
        ),
    ]
    return dash(
        "Fleet Infrastructure",
        "cyto-fleet-infra",
        ["infrastructure", "hosts", "sre"],
        panels,
        [host_var(multi=True, include_all=True)],
        time_from="now-12h",
    )


def build_host_detail():
    # Guard empty $host (e.g. stale bookmark / bad includeVars) so panels never blank out.
    host_f = "resource_attributes->>'host.name' = ${host:sqlstring}"
    panels = [
        panel_stat(
            1,
            "Server status",
            f"""SELECT CASE WHEN max("timestamp") IS NOT NULL
  AND {FRESH_5M.format(col='max("timestamp")')} THEN 'UP' ELSE 'DOWN' END
FROM otel_metrics_gauge
WHERE {host_f} AND metric_name = 'system.uptime'""",
            0,
            0,
            w=3,
            color_mode="background",
            mappings=UP_DOWN_MAP,
            desc="UP if system.uptime seen in last 5 minutes (nanosecond compare).",
        ),
        panel_stat(
            2,
            "OS uptime",
            f"""SELECT value FROM otel_metrics_gauge
WHERE metric_name='system.uptime' AND {host_f}
ORDER BY "timestamp" DESC LIMIT 1""",
            3,
            0,
            w=3,
            unit="dtdurations",
            desc="STAT only — not a graph.",
        ),
        panel_stat(
            3,
            "Process uptime (agent)",
            f"""SELECT max(value) FROM otel_metrics_gauge
WHERE metric_name='process.uptime' AND {host_f} AND {FRESH_WHERE}""",
            6,
            0,
            w=3,
            unit="dtdurations",
            desc="STAT only.",
        ),
        panel_stat(
            4,
            "Boot state",
            f"""SELECT CASE WHEN value < 7200 THEN 'RECENT_BOOT' ELSE 'STABLE' END
FROM otel_metrics_gauge
WHERE metric_name='system.uptime' AND {host_f}
ORDER BY "timestamp" DESC LIMIT 1""",
            9,
            0,
            w=3,
            color_mode="background",
        ),
        panel_stat(
            5,
            "CPU now",
            cpu_busy_latest(host_f),
            12,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
            desc="1 − avg(idle) over last 5m.",
        ),
        panel_stat(
            6,
            "CPU p95",
            cpu_busy_percentile(0.95, host_f),
            15,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            7,
            "Mem used",
            mem_used_latest(host_f),
            18,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            8,
            "True errors",
            f"""SELECT count(*) FROM otel_logs
WHERE {host_f} AND $__timeFilter("timestamp") AND {ERROR_PRED}""",
            21,
            0,
            w=3,
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_stat(
            9,
            "CPU p50",
            cpu_busy_percentile(0.5, host_f),
            0,
            4,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            10,
            "CPU p99",
            cpu_busy_percentile(0.99, host_f),
            3,
            4,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            11,
            "Mem p95",
            mem_used_percentile(0.95, host_f),
            6,
            4,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            12,
            "Mem p99",
            mem_used_percentile(0.99, host_f),
            9,
            4,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            13,
            "Disk free /",
            f"""
WITH d AS (
  SELECT max(value) FILTER (WHERE attributes->>'state'='free' AND attributes->>'mountpoint'='/') AS free_b,
         max(value) FILTER (WHERE attributes->>'state'='used' AND attributes->>'mountpoint'='/') AS used_b
  FROM otel_metrics_sum
  WHERE metric_name='system.filesystem.usage' AND {host_f} AND {FRESH_WHERE}
)
SELECT free_b::double precision / NULLIF(free_b+used_b,0) FROM d
""".strip(),
            12,
            4,
            w=3,
            unit="percentunit",
            thresholds=THRESH_DISK,
            color_mode="background",
        ),
        panel_stat(
            14,
            "Load 1m",
            f"""SELECT value FROM otel_metrics_gauge
WHERE metric_name='system.cpu.load_average.1m' AND {host_f}
ORDER BY "timestamp" DESC LIMIT 1""",
            15,
            4,
            w=3,
        ),
        panel_text(
            15,
            "",
            "[Backups](/d/cyto-backups) · [Service Detail](/d/cyto-service-detail) · [Incidents](/d/cyto-errors) · [Fleet](/d/cyto-fleet-infra) · [Command Center](/d/cyto-command-center)",
            18,
            4,
            w=6,
            h=4,
        ),
        panel_ts(
            20,
            "CPU busy (1 − idle)",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       'cpu_busy' AS metric,
       1 - avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND attributes->>'state' = 'idle'
  AND {host_f}
  AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1""",
            0,
            8,
            w=12,
            unit="percentunit",
            soft_max=1,
        ),
        panel_ts(
            21,
            "Memory used",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       'mem_used' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND attributes->>'state' = 'used'
  AND {host_f}
  AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1""",
            12,
            8,
            w=12,
            unit="percentunit",
            soft_max=1,
        ),
        panel_ts(
            22,
            "Load averages",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       metric_name AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name IN ('system.cpu.load_average.1m','system.cpu.load_average.5m','system.cpu.load_average.15m')
  AND {host_f} AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1""",
            0,
            16,
            w=12,
        ),
        panel_ts(
            23,
            "Network IO (bytes)",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       attributes->>'direction' AS metric,
       sum(value) AS value
FROM otel_metrics_sum
WHERE metric_name = 'system.network.io'
  AND {host_f} AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1""",
            12,
            16,
            w=12,
            unit="bytes",
        ),
        panel_table(
            30,
            "Top processes by CPU",
            f"""
WITH latest AS (
  SELECT resource_attributes->>'process.executable.name' AS process,
         resource_attributes->>'process.pid' AS pid,
         resource_attributes->>'process.owner' AS owner,
         attributes->>'state' AS state,
         value,
         "timestamp",
         row_number() OVER (
           PARTITION BY resource_attributes->>'process.pid', attributes->>'state'
           ORDER BY "timestamp" DESC
         ) AS rn
  FROM otel_metrics_gauge
  WHERE metric_name = 'process.cpu.utilization'
    AND {host_f}
    AND {FRESH_WHERE}
)
SELECT process,
       pid,
       owner,
       sum(value) FILTER (WHERE state IN ('user','system')) AS cpu_util,
       max("timestamp") AS last_seen
FROM latest
WHERE rn = 1 AND process IS NOT NULL
GROUP BY process, pid, owner
ORDER BY cpu_util DESC NULLS LAST
LIMIT 25
""".strip(),
            0,
            24,
            h=10,
            w=12,
            desc="Per-process CPU = user + system. Empty if host does not scrape process metrics.",
            overrides=[
                {"matcher": {"id": "byName", "options": "cpu_util"}, "properties": [{"id": "unit", "value": "percentunit"}]},
            ],
        ),
        panel_table(
            31,
            "Filesystems",
            f"""
SELECT attributes->>'mountpoint' AS mount,
       attributes->>'device' AS device,
       attributes->>'type' AS fstype,
       max(value) FILTER (WHERE attributes->>'state'='free') AS free_bytes,
       max(value) FILTER (WHERE attributes->>'state'='used') AS used_bytes,
       max(value) FILTER (WHERE attributes->>'state'='free')::double precision
         / NULLIF(max(value) FILTER (WHERE attributes->>'state'='free')
                + max(value) FILTER (WHERE attributes->>'state'='used'),0) AS free_ratio
FROM otel_metrics_sum
WHERE metric_name='system.filesystem.usage' AND {host_f} AND {FRESH_WHERE}
GROUP BY 1,2,3
ORDER BY free_ratio ASC NULLS LAST
""".strip(),
            12,
            24,
            h=10,
            w=12,
            overrides=[
                {"matcher": {"id": "byName", "options": "free_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
                {"matcher": {"id": "byName", "options": "used_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
                {"matcher": {"id": "byName", "options": "free_ratio"}, "properties": [{"id": "unit", "value": "percentunit"}]},
            ],
        ),
        panel_ts(
            40,
            "Top process CPU over time",
            f"""
SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'process.executable.name' AS metric,
       sum(value) FILTER (WHERE attributes->>'state' IN ('user','system')) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'process.cpu.utilization'
  AND {host_f}
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'process.executable.name' IS NOT NULL
GROUP BY 1, 2
ORDER BY 1
""".strip(),
            0,
            34,
            w=24,
            unit="percentunit",
            desc="Stacked by executable name (user+system).",
        ),
        panel_table(
            50,
            "True errors on this host",
            f"""SELECT "timestamp",
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       coalesce(severity_text, '') AS severity,
       coalesce(log_attributes->>'log.kind', '') AS log_kind,
       left(body, 4000) AS body
FROM otel_logs
WHERE {host_f}
  AND $__timeFilter("timestamp")
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 100""",
            0,
            42,
            h=11,
            desc="Strict filter only — INFO/auth chatter without log.kind=error is excluded.",
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 700},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                }
            ],
        ),
    ]
    return dash(
        "Host Infrastructure Detail",
        "cyto-server-detail",
        ["host", "infrastructure"],
        panels,
        [host_var(multi=False, include_all=False)],
        time_from="now-6h",
    )


def build_service_detail():
    svc_name = "${service:sqlstring}"
    svc = f"coalesce(resource_attributes->>'service.name', service_name) = {svc_name}"
    panels = [
        panel_stat(
            1,
            "Service status",
            f"""SELECT CASE
  WHEN max("timestamp") IS NULL THEN 'DOWN'
  WHEN epoch_ns(max("timestamp")) > (extract(epoch from now()) - 300) * 1000000000 THEN 'UP'
  WHEN epoch_ns(max("timestamp")) > (extract(epoch from now()) - 3600) * 1000000000 THEN 'QUIET'
  ELSE 'DOWN'
END
FROM otel_logs WHERE {svc}""",
            0,
            0,
            w=3,
            color_mode="background",
            mappings=UP_DOWN_MAP,
            desc="UP = log in last 5m. QUIET = log in last 1h (normal for sparse services like DBs). DOWN = older/none.",
        ),
        panel_stat(
            2,
            "Log volume",
            f"""SELECT count(*) FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp")""",
            3,
            0,
            w=3,
            no_value="0",
        ),
        panel_stat(
            3,
            "Minutes since last log",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
  ELSE (extract(epoch from now())*1e9 - epoch_ns(max("timestamp"))) / 6e10
END
FROM otel_logs WHERE {svc}""",
            6,
            0,
            w=3,
            unit="m",
            no_value="n/a",
            desc="How long since the last log line for this service (any time).",
        ),
        panel_stat(
            4,
            "True errors",
            f"""SELECT count(*) FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp") AND {ERROR_PRED}""",
            9,
            0,
            w=3,
            thresholds=THRESH_ERR,
            color_mode="background",
            no_value="0",
        ),
        panel_stat(
            5,
            "Error rate",
            f"""
SELECT CASE WHEN count(*) = 0 THEN 0
  ELSE count(*) FILTER (WHERE {ERROR_PRED})::double precision / count(*)
END
FROM otel_logs WHERE {svc} AND $__timeFilter("timestamp")
""".strip(),
            12,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
            no_value="0",
        ),
        panel_stat(
            6,
            "Hosts",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name')
FROM otel_logs WHERE {svc} AND $__timeFilter("timestamp")""",
            15,
            0,
            w=3,
            no_value="0",
        ),
        panel_stat(
            7,
            "Process CPU",
            f"""
SELECT CASE WHEN count(*) = 0 THEN NULL
  ELSE sum(value) FILTER (WHERE attributes->>'state' IN ('user','system'))
END
FROM otel_metrics_gauge
WHERE metric_name = 'process.cpu.utilization'
  AND resource_attributes->>'service.name' = {svc_name}
  AND {FRESH_WHERE}
""".strip(),
            18,
            0,
            w=3,
            unit="percentunit",
            no_value="not scraped",
            desc="Only for services that emit process.* with this service.name (container DB logs usually do not).",
        ),
        panel_stat(
            8,
            "Process mem",
            f"""
SELECT CASE WHEN count(*) = 0 THEN NULL ELSE max(value) END
FROM otel_metrics_gauge
WHERE metric_name = 'process.memory.utilization'
  AND resource_attributes->>'service.name' = {svc_name}
  AND {FRESH_WHERE}
""".strip(),
            21,
            0,
            w=3,
            unit="percentunit",
            no_value="not scraped",
            desc="not scraped = no process metrics for this service.name. Use Host Detail for node/process CPU.",
        ),
        panel_table(
            10,
            "Hosts running this service",
            f"""
SELECT resource_attributes->>'host.name' AS host,
       count(*) AS log_lines,
       count(*) FILTER (WHERE {ERROR_PRED}) AS errors,
       max("timestamp") AS last_seen,
       CASE
         WHEN epoch_ns(max("timestamp")) > (extract(epoch from now()) - 300) * 1000000000 THEN 'UP'
         WHEN epoch_ns(max("timestamp")) > (extract(epoch from now()) - 3600) * 1000000000 THEN 'QUIET'
         ELSE 'STALE'
       END AS status
FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp")
GROUP BY 1
ORDER BY errors DESC, last_seen DESC
""".strip(),
            0,
            4,
            h=7,
            overrides=[STATUS_MAP],
        ),
        panel_ts(
            20,
            "Log volume over time",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       'logs' AS metric,
       count(*) AS value
FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1""",
            0,
            11,
            w=12,
            bars=True,
        ),
        panel_ts(
            21,
            "True error rate over time",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       'errors' AS metric,
       count(*) AS value
FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp") AND {ERROR_PRED}
GROUP BY 1, 2 ORDER BY 1""",
            12,
            11,
            w=12,
            bars=True,
        ),
        panel_ts(
            22,
            "Process CPU (if scraped)",
            f"""
SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'process.executable.name', 'process') AS metric,
       sum(value) FILTER (WHERE attributes->>'state' IN ('user','system')) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'process.cpu.utilization'
  AND resource_attributes->>'service.name' = {svc_name}
  AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1
""".strip(),
            0,
            19,
            w=12,
            unit="percentunit",
        ),
        panel_ts(
            23,
            "Process memory (if scraped)",
            f"""
SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'process.executable.name', 'process') AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'process.memory.utilization'
  AND resource_attributes->>'service.name' = {svc_name}
  AND $__timeFilter("timestamp")
GROUP BY 1, 2 ORDER BY 1
""".strip(),
            12,
            19,
            w=12,
            unit="percentunit",
        ),
        panel_table(
            30,
            "Recent logs",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(severity_text, '') AS severity,
       coalesce(log_attributes->>'log.kind', '') AS log_kind,
       left(body, 4000) AS body
FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC
LIMIT 150""",
            0,
            27,
            h=10,
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 720},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                }
            ],
        ),
        panel_table(
            31,
            "True error stream",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(severity_text, '') AS severity,
       coalesce(trace_id, '') AS trace_id,
       left(body, 5000) AS body
FROM otel_logs
WHERE {svc} AND $__timeFilter("timestamp") AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 100""",
            0,
            37,
            h=10,
        ),
    ]
    return dash(
        "Service Detail",
        "cyto-service-detail",
        ["service", "application"],
        panels,
        [
            service_var(
                multi=False,
                include_all=False,
                where="TRUE",
            )
        ],
        time_from="now-6h",
    )


def build_backups():
    panels = [
        panel_text(
            99,
            "",
            "[Command Center](/d/cyto-command-center) · [Fleet](/d/cyto-fleet-infra) · [Host Detail](/d/cyto-server-detail) · [Incidents](/d/cyto-errors)",
            0,
            0,
            h=2,
        ),
        panel_row(100, "Backup health", 2),
        panel_stat(
            1,
            "Successful backups",
            f"""SELECT count(*) AS "Success" FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_SUCCESS}""",
            0,
            3,
            w=4,
            thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            color_mode="background",
        ),
        panel_stat(
            2,
            "Failed backups",
            f"""SELECT count(*) AS "Failed" FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_FAIL}""",
            4,
            3,
            w=4,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            3,
            "Services with success",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name))
FROM otel_logs WHERE $__timeFilter("timestamp") AND {BACKUP_SUCCESS}""",
            8,
            3,
            w=4,
            color_mode="background",
        ),
        panel_stat(
            4,
            "Services with failure",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name))
FROM otel_logs WHERE $__timeFilter("timestamp") AND {BACKUP_FAIL}""",
            12,
            3,
            w=4,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            5,
            "Hours since last success",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
  ELSE (extract(epoch from now())*1e9 - epoch_ns(max("timestamp"))) / 3.6e12
END FROM otel_logs WHERE {BACKUP_SUCCESS}""",
            16,
            3,
            w=4,
            unit="h",
            thresholds={
                "mode": "absolute",
                "steps": [
                    {"color": "green", "value": None},
                    {"color": "yellow", "value": 12},
                    {"color": "red", "value": 30},
                ],
            },
            color_mode="background",
        ),
        panel_stat(
            6,
            "Backup log volume",
            f"""SELECT count(*) FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_ANY}""",
            20,
            3,
            w=4,
        ),
        panel_table(
            10,
            "Backup status by service",
            f"""
WITH base AS (
  SELECT coalesce(resource_attributes->>'service.name', service_name) AS service,
         resource_attributes->>'host.name' AS host,
         "timestamp",
         CASE
           WHEN {BACKUP_FAIL} THEN 'FAIL'
           WHEN {BACKUP_SUCCESS} THEN 'OK'
           ELSE 'INFO'
         END AS kind,
         coalesce((log_attributes->>'backup.duration_seconds')::double precision, NULL) AS duration_s
  FROM otel_logs
  WHERE $__timeFilter("timestamp")
    AND {BACKUP_ANY}
    AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
),
agg AS (
  SELECT service, max(host) AS host,
         count(*) FILTER (WHERE kind = 'OK') AS successes,
         count(*) FILTER (WHERE kind = 'FAIL') AS failures,
         max("timestamp") FILTER (WHERE kind = 'OK') AS last_success,
         max("timestamp") FILTER (WHERE kind = 'FAIL') AS last_failure,
         avg(duration_s) FILTER (WHERE kind = 'OK') AS avg_duration_s
  FROM base GROUP BY service
)
SELECT service, host,
       CASE
         WHEN failures > 0 AND (last_failure IS NULL OR last_success IS NULL OR last_failure >= last_success) THEN 'FAIL'
         WHEN successes > 0 THEN 'OK'
         ELSE 'UNKNOWN'
       END AS status,
       successes, failures, last_success, last_failure, avg_duration_s
FROM agg ORDER BY status ASC, failures DESC, service
""".strip(),
            0,
            7,
            h=9,
            overrides=[STATUS_MAP],
        ),
        panel_ts(
            20,
            "Backup outcomes over time",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       CASE WHEN {BACKUP_FAIL} THEN 'failed' WHEN {BACKUP_SUCCESS} THEN 'success' ELSE 'other' END AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_ANY}
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
GROUP BY 1, 2 ORDER BY 1""",
            0,
            16,
            w=12,
            h=9,
            bars=True,
        ),
        panel_ts(
            21,
            "Backup duration (seconds)",
            f"""SELECT "timestamp" AS time,
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       (log_attributes->>'backup.duration_seconds')::double precision AS value
FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_SUCCESS}
  AND log_attributes->>'backup.duration_seconds' IS NOT NULL
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
ORDER BY 1""",
            12,
            16,
            w=12,
            h=9,
            unit="s",
        ),
        panel_table(
            30,
            "Backup incident / detail log",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       CASE WHEN {BACKUP_FAIL} THEN 'FAIL' WHEN {BACKUP_SUCCESS} THEN 'OK' ELSE 'INFO' END AS status,
       coalesce(log_attributes->>'event.name', log_attributes->>'log.kind', '') AS event,
       left(body, 4000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp") AND {BACKUP_ANY}
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND ({BACKUP_SUCCESS} OR {BACKUP_FAIL} OR body ~* '(Done|ERROR|FAILED|Start |borg |rclone )')
ORDER BY "timestamp" DESC LIMIT 200""",
            0,
            25,
            h=12,
            overrides=[
                STATUS_MAP,
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 720},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                },
            ],
        ),
    ]
    return dash(
        "Backup Operations",
        "cyto-backups",
        ["backup", "reliability"],
        panels,
        [
            service_var(
                where=(
                    "coalesce(resource_attributes->>'service.name', service_name) ILIKE '%backup%' "
                    "OR log_attributes->>'log.kind' = 'backup'"
                )
            )
        ],
        time_from="now-7d",
    )


def build_errors():
    panels = [
        panel_stat(
            1,
            "True incidents",
            f"""SELECT count(*) FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            0,
            0,
            w=4,
            thresholds=THRESH_ERR,
            color_mode="background",
            desc="log.kind=error / exception / severity ERROR+ only.",
        ),
        panel_stat(
            2,
            "Services affected",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name))
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            4,
            0,
            w=4,
        ),
        panel_stat(
            3,
            "Hosts affected",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name')
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            8,
            0,
            w=4,
        ),
        panel_stat(
            4,
            "Minutes since last",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
  ELSE (extract(epoch from now())*1e9 - epoch_ns(max("timestamp"))) / 6e10 END
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            12,
            0,
            w=4,
            unit="m",
        ),
        panel_stat(
            5,
            "With trace_id",
            f"""SELECT count(*) FILTER (WHERE coalesce(trace_id,'') <> '' AND trace_id <> '00000000000000000000000000000000')
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            16,
            0,
            w=4,
        ),
        panel_stat(
            6,
            "Unique signatures",
            f"""SELECT count(DISTINCT left(regexp_replace(body, '\\\\s+', ' ', 'g'), 120))
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}""",
            20,
            0,
            w=4,
        ),
        panel_table(
            10,
            "Incidents by service",
            f"""
SELECT coalesce(resource_attributes->>'service.name', service_name) AS service,
       resource_attributes->>'host.name' AS host,
       count(*) AS incidents,
       max("timestamp") AS last_seen,
       left(max(body), 240) AS sample
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2 ORDER BY incidents DESC LIMIT 80
""".strip(),
            0,
            4,
            h=9,
        ),
        panel_ts(
            20,
            "Incident rate by service",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2 ORDER BY 1""",
            0,
            13,
            w=24,
            h=9,
            bars=True,
        ),
        panel_table(
            30,
            "Incident detail stream",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       coalesce(severity_text, log_attributes->>'severity', '') AS severity,
       coalesce(log_attributes->>'log.kind', '') AS log_kind,
       coalesce(trace_id, '') AS trace_id,
       left(body, 5000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC LIMIT 250""",
            0,
            22,
            h=14,
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 760},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                }
            ],
        ),
    ]
    return dash(
        "Errors & Incidents",
        "cyto-errors",
        ["errors", "incidents", "sre"],
        panels,
        [
            host_var(multi=True, include_all=True),
            service_var(where="TRUE"),
        ],
        time_from="now-12h",
    )


def main():
    suite = {
        "command-center.json": build_command_center(),
        "observability.json": build_command_center(),  # replace junk overview with Command Center (same uid conflict avoided)
        "fleet-infrastructure.json": build_fleet_infra(),
        "server-detail.json": build_host_detail(),
        "service-detail.json": build_service_detail(),
        "backup-operations.json": build_backups(),
        "errors-incidents.json": build_errors(),
    }
    # observability.json must not share uid with command-center — keep as alias landing with distinct uid
    suite["observability.json"] = dict(build_command_center())
    suite["observability.json"]["uid"] = "cyto-observability-home"
    suite["observability.json"]["title"] = "Observability Home"

    # Remove stale fleet-overview if present (would confuse provisioning)
    stale = OUT / "fleet-overview.json"
    if stale.exists():
        stale.unlink()
        print("removed fleet-overview.json")

    for name, d in suite.items():
        path = OUT / name
        path.write_text(json.dumps(d, indent=2) + "\n")
        print(f"wrote {path.name} uid={d['uid']} panels={len(d['panels'])}")

    # Update SQL helpers doc
    (OUT / "_sql_helpers.md").write_text(
        """# SereneDB TIMESTAMP_NS SQL contract (v3)

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
"""
    )
    print("updated _sql_helpers.md")


if __name__ == "__main__":
    main()
