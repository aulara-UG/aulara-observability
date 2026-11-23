#!/usr/bin/env python3
"""Enterprise Grafana dashboards for CytoSorbents Observability Stack (SereneDB)."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
DS = {"type": "grafana-postgresql-datasource", "uid": "serenedb"}
FOLDER = "bg56fkcmm0miod"

ERROR_PRED = """(
    log_attributes->>'log.kind' = 'error'
    OR log_attributes->>'exception.type' IS NOT NULL
    OR coalesce(severity_text,'') ~* '^(error|fatal|critical|warn|warning)$'
    OR body ~* '(Exception|Traceback|error_proto|FATAL|\\\\[php:(error|crit|alert)\\\\])'
    OR body ~* '(?i)\\\\b(ERROR|FAILED|FATAL|CRIT)\\\\b'
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
FRESH_WHERE = '"timestamp" > make_timestamp_ns((extract(epoch from now()) - 300)::bigint * 1000000000)'


def panel_stat(pid, title, sql, x, y, w=4, h=4, unit=None, desc="", thresholds=None, color_mode="value"):
    fc = {
        "defaults": {
            "thresholds": thresholds
            or {"mode": "absolute", "steps": [{"color": "blue", "value": None}]},
        },
        "overrides": [],
    }
    if unit:
        fc["defaults"]["unit"] = unit
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


THRESH_OK_BAD = {
    "mode": "absolute",
    "steps": [
        {"color": "green", "value": None},
        {"color": "red", "value": 1},
    ],
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
                        "UNKNOWN": {"color": "super-light-yellow", "index": 3, "text": "UNKNOWN"},
                        "RECENT_BOOT": {"color": "purple", "index": 4, "text": "RECENT BOOT"},
                        "STABLE": {"color": "green", "index": 5, "text": "STABLE"},
                    },
                }
            ],
        },
    ],
}


def host_var(multi=True, include_all=True, name="host"):
    return {
        "current": {
            "selected": True,
            "text": "All" if include_all else "CSE-01",
            "value": "$__all" if include_all else "CSE-01",
        },
        "datasource": DS,
        "definition": (
            "SELECT DISTINCT resource_attributes->>'host.name' AS __text, "
            "resource_attributes->>'host.name' AS __value FROM otel_metrics_gauge "
            "WHERE resource_attributes->>'host.name' IS NOT NULL ORDER BY 1"
        ),
        "includeAll": include_all,
        "label": "Host",
        "multi": multi,
        "name": name,
        "query": (
            "SELECT DISTINCT resource_attributes->>'host.name' AS __text, "
            "resource_attributes->>'host.name' AS __value FROM otel_metrics_gauge "
            "WHERE resource_attributes->>'host.name' IS NOT NULL ORDER BY 1"
        ),
        "refresh": 2,
        "type": "query",
        "sort": 1,
    }


def service_var(name="service", multi=True, include_all=True, where="TRUE"):
    return {
        "current": {"selected": True, "text": "All", "value": "$__all"},
        "datasource": DS,
        "definition": (
            "SELECT DISTINCT coalesce(resource_attributes->>'service.name', service_name) AS __text, "
            "coalesce(resource_attributes->>'service.name', service_name) AS __value "
            f"FROM otel_logs WHERE coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL AND ({where}) ORDER BY 1"
        ),
        "includeAll": include_all,
        "label": "Service",
        "multi": multi,
        "name": name,
        "query": (
            "SELECT DISTINCT coalesce(resource_attributes->>'service.name', service_name) AS __text, "
            "coalesce(resource_attributes->>'service.name', service_name) AS __value "
            f"FROM otel_logs WHERE coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL AND ({where}) ORDER BY 1"
        ),
        "refresh": 2,
        "type": "query",
        "sort": 1,
    }


LINKS_COMMON = [
    {
        "title": "Fleet Infrastructure",
        "type": "link",
        "icon": "dashboard",
        "url": "/d/cyto-fleet-infra/fleet-infrastructure",
        "keepTime": True,
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
    {
        "title": "Host Drill-down",
        "type": "link",
        "icon": "dashboard",
        "url": "/d/cyto-server-detail/host-infrastructure-detail",
        "keepTime": True,
        "includeVars": True,
    },
]


def dash(title, uid, tags, panels, templating, links=None, refresh="30s", time_from="now-24h"):
    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": links or LINKS_COMMON,
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
        "version": 1,
    }


def build_backups():
    panels = [
        panel_row(100, "Backup health", 0),
        panel_stat(
            1,
            "Successful backups",
            f"""SELECT count(*) AS "Success"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_SUCCESS}""",
            0,
            1,
            w=4,
            thresholds={"mode": "absolute", "steps": [{"color": "green", "value": None}]},
            color_mode="background",
            desc="Structured backup.success events + Done markers from backup logs.",
        ),
        panel_stat(
            2,
            "Failed backups",
            f"""SELECT count(*) AS "Failed"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_FAIL}""",
            4,
            1,
            w=4,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
            desc="backup.failed / ERROR lines in backup pipelines.",
        ),
        panel_stat(
            3,
            "Services with success",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name)) AS "Services OK"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_SUCCESS}""",
            8,
            1,
            w=4,
            color_mode="background",
        ),
        panel_stat(
            4,
            "Services with failure",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name)) AS "Services FAIL"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_FAIL}""",
            12,
            1,
            w=4,
            thresholds=THRESH_OK_BAD,
            color_mode="background",
        ),
        panel_stat(
            5,
            "Hours since last success",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
  ELSE (extract(epoch from now())*1e9 - epoch_ns(max("timestamp"))) / 3.6e12
END AS "Hours"
FROM otel_logs
WHERE {BACKUP_SUCCESS}""",
            16,
            1,
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
            desc="Across whole fleet (not filtered by service var).",
        ),
        panel_stat(
            6,
            "Backup log volume",
            f"""SELECT count(*) AS "Events"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_ANY}""",
            20,
            1,
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
         coalesce((log_attributes->>'backup.duration_seconds')::double precision, NULL) AS duration_s,
         left(body, 500) AS body
  FROM otel_logs
  WHERE $__timeFilter("timestamp")
    AND {BACKUP_ANY}
    AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
),
agg AS (
  SELECT service,
         max(host) AS host,
         count(*) FILTER (WHERE kind = 'OK') AS successes,
         count(*) FILTER (WHERE kind = 'FAIL') AS failures,
         max("timestamp") FILTER (WHERE kind = 'OK') AS last_success,
         max("timestamp") FILTER (WHERE kind = 'FAIL') AS last_failure,
         avg(duration_s) FILTER (WHERE kind = 'OK') AS avg_duration_s
  FROM base
  GROUP BY service
)
SELECT service,
       host,
       CASE
         WHEN failures > 0 AND (last_failure IS NULL OR last_success IS NULL OR last_failure >= last_success) THEN 'FAIL'
         WHEN successes > 0 THEN 'OK'
         ELSE 'UNKNOWN'
       END AS status,
       successes,
       failures,
       last_success,
       last_failure,
       avg_duration_s
FROM agg
ORDER BY status ASC, failures DESC, service
""".strip(),
            0,
            5,
            h=9,
            desc="Per backup pipeline (moodle-backup, forgejo-backup, nextcloud-backup, …).",
            overrides=[STATUS_MAP],
        ),
        panel_ts(
            20,
            "Backup outcomes over time",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       CASE
         WHEN {BACKUP_FAIL} THEN 'failed'
         WHEN {BACKUP_SUCCESS} THEN 'success'
         ELSE 'other'
       END AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_ANY}
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
GROUP BY 1, 2
ORDER BY 1""",
            0,
            14,
            w=12,
            h=9,
            bars=True,
            desc="Stacked success vs failed backup markers.",
        ),
        panel_ts(
            21,
            "Backup duration (seconds)",
            f"""SELECT "timestamp" AS time,
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       (log_attributes->>'backup.duration_seconds')::double precision AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_SUCCESS}
  AND log_attributes->>'backup.duration_seconds' IS NOT NULL
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
ORDER BY 1""",
            12,
            14,
            w=12,
            h=9,
            unit="s",
            desc="From otel-backup-event duration attribute.",
        ),
        panel_table(
            30,
            "Backup incident / detail log",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       CASE
         WHEN {BACKUP_FAIL} THEN 'FAIL'
         WHEN {BACKUP_SUCCESS} THEN 'OK'
         ELSE 'INFO'
       END AS status,
       coalesce(log_attributes->>'event.name', log_attributes->>'log.kind', '') AS event,
       coalesce(log_attributes->>'log.file.name', '') AS logfile,
       coalesce(trace_id, '') AS trace_id,
       left(body, 4000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {BACKUP_ANY}
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND (
    {BACKUP_SUCCESS} OR {BACKUP_FAIL}
    OR body ~* '(Done|ERROR|FAILED|Start |borg |rclone )'
  )
ORDER BY "timestamp" DESC
LIMIT 200""",
            0,
            23,
            h=12,
            desc="Success + failure lines with optional trace_id for correlation.",
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


def build_fleet_infra():
    host_matrix = f"""
WITH hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host
  FROM otel_metrics_gauge
  WHERE resource_attributes->>'host.name' IS NOT NULL
    AND $__timeFilter("timestamp")
),
cpu AS (
  SELECT resource_attributes->>'host.name' AS host,
         percentile_cont(0.5) WITHIN GROUP (ORDER BY value) AS cpu_p50,
         percentile_cont(0.95) WITHIN GROUP (ORDER BY value) AS cpu_p95,
         avg(value) AS cpu_avg
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.cpu.utilization'
    AND $__timeFilter("timestamp")
  GROUP BY 1
),
mem AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host,
         value AS mem
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.memory.utilization'
    AND $__timeFilter("timestamp")
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
uptime AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host,
         value AS uptime_s,
         "timestamp" AS last_metric
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime'
    AND $__timeFilter("timestamp")
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
disk AS (
  SELECT resource_attributes->>'host.name' AS host,
         max(value) FILTER (WHERE attributes->>'state' = 'free' AND attributes->>'mountpoint' = '/') AS free_bytes,
         max(value) FILTER (WHERE attributes->>'state' = 'used' AND attributes->>'mountpoint' = '/') AS used_bytes
  FROM otel_metrics_sum
  WHERE metric_name = 'system.filesystem.usage'
    AND $__timeFilter("timestamp")
    AND {FRESH_WHERE}
  GROUP BY 1
),
errs AS (
  SELECT resource_attributes->>'host.name' AS host,
         count(*) AS errors
  FROM otel_logs
  WHERE $__timeFilter("timestamp")
    AND {ERROR_PRED}
  GROUP BY 1
),
neterr AS (
  SELECT resource_attributes->>'host.name' AS host,
         sum(value) AS net_errors
  FROM otel_metrics_sum
  WHERE metric_name = 'system.network.errors'
    AND $__timeFilter("timestamp")
  GROUP BY 1
)
SELECT h.host,
       CASE WHEN u.last_metric IS NOT NULL AND {FRESH_5M.format(col='u.last_metric')} THEN 'UP' ELSE 'DOWN' END AS status,
       u.uptime_s AS host_uptime,
       CASE WHEN u.uptime_s < 7200 THEN 'RECENT_BOOT' ELSE 'STABLE' END AS boot,
       c.cpu_p50,
       c.cpu_p95,
       m.mem AS host_mem,
       CASE WHEN coalesce(d.free_bytes,0)+coalesce(d.used_bytes,0) > 0
            THEN d.free_bytes::double precision / (d.free_bytes + d.used_bytes)
            ELSE NULL END AS disk_free_ratio,
       d.free_bytes AS disk_free_bytes,
       coalesce(e.errors, 0) AS errors,
       coalesce(n.net_errors, 0) AS net_errors
FROM hosts h
LEFT JOIN cpu c ON c.host = h.host
LEFT JOIN mem m ON m.host = h.host
LEFT JOIN uptime u ON u.host = h.host
LEFT JOIN disk d ON d.host = h.host
LEFT JOIN errs e ON e.host = h.host
LEFT JOIN neterr n ON n.host = h.host
ORDER BY status ASC, errors DESC, h.host
""".strip()

    panels = [
        panel_row(100, "Fleet pulse", 0),
        panel_stat(
            1,
            "Hosts UP",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name')
FROM otel_metrics_gauge
WHERE metric_name = 'system.uptime'
  AND {FRESH_WHERE}""",
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
            "Fleet CPU p95",
            f"""SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY value)
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND $__timeFilter("timestamp")
  AND {FRESH_WHERE}""",
            6,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            4,
            "Fleet mem p95",
            f"""SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY value)
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND $__timeFilter("timestamp")
  AND {FRESH_WHERE}""",
            9,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            5,
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
            12,
            1,
            w=3,
            unit="percentunit",
            thresholds=THRESH_DISK,
            color_mode="background",
            desc="Lowest root filesystem free ratio across fleet.",
        ),
        panel_stat(
            6,
            "Error events",
            f"""SELECT count(*) FROM otel_logs
WHERE $__timeFilter("timestamp") AND {ERROR_PRED}""",
            15,
            1,
            w=3,
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_stat(
            7,
            "Recent boots (<2h)",
            f"""SELECT count(*) FROM (
  SELECT DISTINCT ON (resource_attributes->>'host.name') value
  FROM otel_metrics_gauge
  WHERE metric_name='system.uptime' AND {FRESH_WHERE}
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
) s WHERE value < 7200""",
            18,
            1,
            w=3,
            desc="Hosts with system.uptime under 2 hours — proxy for recent reboot (reboot-required file is not scraped yet).",
            color_mode="background",
            thresholds={
                "mode": "absolute",
                "steps": [
                    {"color": "green", "value": None},
                    {"color": "purple", "value": 1},
                ],
            },
        ),
        panel_stat(
            8,
            "Containers observed",
            f"""SELECT count(DISTINCT resource_attributes->>'container.name')
FROM otel_metrics_gauge
WHERE metric_name='container.uptime' AND {FRESH_WHERE}""",
            21,
            1,
            w=3,
        ),
        panel_table(
            10,
            "Host infrastructure matrix",
            host_matrix,
            0,
            5,
            h=10,
            desc="UP/DOWN, CPU percentiles, memory, root disk free, errors, network errors, recent reboot heuristic.",
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
                {"matcher": {"id": "byName", "options": "host_mem"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "disk_free_ratio"}, "properties": [{"id": "unit", "value": "percentunit"}]},
                {"matcher": {"id": "byName", "options": "disk_free_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
            ],
        ),
        panel_ts(
            20,
            "CPU utilization by host",
            """SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
GROUP BY 1, 2
ORDER BY 1""",
            0,
            15,
            w=12,
            unit="percentunit",
        ),
        panel_ts(
            21,
            "Memory utilization by host",
            """SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
GROUP BY 1, 2
ORDER BY 1""",
            12,
            15,
            w=12,
            unit="percentunit",
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
FROM snap
WHERE free_b IS NOT NULL
ORDER BY 1
""".strip(),
            0,
            23,
            w=12,
            unit="percentunit",
            desc="Free / (free+used) on mountpoint=/.",
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
GROUP BY 1, 2
ORDER BY 1""",
            12,
            23,
            w=12,
            unit="short",
        ),
        panel_ts(
            24,
            "Network errors (sum)",
            """SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       sum(value) AS value
FROM otel_metrics_sum
WHERE metric_name = 'system.network.errors'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
GROUP BY 1, 2
ORDER BY 1""",
            0,
            31,
            w=12,
            bars=True,
        ),
        panel_ts(
            25,
            "Error log burn by host",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'host.name' AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2
ORDER BY 1""",
            12,
            31,
            w=12,
            bars=True,
        ),
        panel_table(
            30,
            "Top error signatures (fleet)",
            f"""SELECT left(regexp_replace(body, '\\\\s+', ' ', 'g'), 180) AS signature,
       count(*) AS hits,
       count(DISTINCT resource_attributes->>'host.name') AS hosts,
       max("timestamp") AS last_seen
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND {ERROR_PRED}
GROUP BY 1
ORDER BY hits DESC
LIMIT 40""",
            0,
            39,
            h=10,
            desc="Cluster similar error bodies for fast triage.",
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
    panels = [
        panel_stat(
            1,
            "Status",
            f"""SELECT CASE WHEN max("timestamp") IS NOT NULL AND {FRESH_5M.format(col='max("timestamp")')} THEN 'UP' ELSE 'DOWN' END
FROM otel_metrics_gauge
WHERE resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")""",
            0,
            0,
            w=3,
            color_mode="background",
        ),
        panel_stat(
            2,
            "OS uptime",
            """SELECT value FROM otel_metrics_gauge
WHERE metric_name='system.uptime' AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC LIMIT 1""",
            3,
            0,
            w=4,
            unit="dtdurations",
        ),
        panel_stat(
            3,
            "Boot state",
            """SELECT CASE WHEN value < 7200 THEN 'RECENT_BOOT' ELSE 'STABLE' END
FROM otel_metrics_gauge
WHERE metric_name='system.uptime' AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC LIMIT 1""",
            7,
            0,
            w=4,
            color_mode="background",
            desc="RECENT_BOOT if uptime < 2h. True reboot-required flag is not ingested yet — add a tiny agent check later.",
        ),
        panel_stat(
            4,
            "CPU p95",
            f"""SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY value)
FROM otel_metrics_gauge
WHERE metric_name='system.cpu.utilization'
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")""",
            11,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            5,
            "Mem",
            """SELECT value FROM otel_metrics_gauge
WHERE metric_name='system.memory.utilization'
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC LIMIT 1""",
            14,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            6,
            "Disk free /",
            f"""
WITH d AS (
  SELECT max(value) FILTER (WHERE attributes->>'state'='free' AND attributes->>'mountpoint'='/') AS free_b,
         max(value) FILTER (WHERE attributes->>'state'='used' AND attributes->>'mountpoint'='/') AS used_b
  FROM otel_metrics_sum
  WHERE metric_name='system.filesystem.usage'
    AND resource_attributes->>'host.name'='$host'
    AND {FRESH_WHERE}
)
SELECT free_b::double precision / NULLIF(free_b+used_b,0) FROM d
""".strip(),
            17,
            0,
            w=3,
            unit="percentunit",
            thresholds=THRESH_DISK,
            color_mode="background",
        ),
        panel_stat(
            7,
            "Errors",
            f"""SELECT count(*) FROM otel_logs
WHERE resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp") AND {ERROR_PRED}""",
            20,
            0,
            w=4,
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_table(
            10,
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
WHERE metric_name='system.filesystem.usage'
  AND resource_attributes->>'host.name'='$host'
  AND {FRESH_WHERE}
GROUP BY 1,2,3
ORDER BY free_ratio ASC NULLS LAST
""".strip(),
            0,
            4,
            h=7,
            overrides=[
                {"matcher": {"id": "byName", "options": "free_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
                {"matcher": {"id": "byName", "options": "used_bytes"}, "properties": [{"id": "unit", "value": "bytes"}]},
                {"matcher": {"id": "byName", "options": "free_ratio"}, "properties": [{"id": "unit", "value": "percentunit"}]},
            ],
        ),
        panel_ts(
            20,
            "CPU (avg / context)",
            """SELECT "timestamp" AS time, 'cpu' AS metric, value
FROM otel_metrics_gauge
WHERE metric_name='system.cpu.utilization'
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY 1""",
            0,
            11,
            unit="percentunit",
        ),
        panel_ts(
            21,
            "Memory",
            """SELECT "timestamp" AS time, 'memory' AS metric, value
FROM otel_metrics_gauge
WHERE metric_name='system.memory.utilization'
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY 1""",
            12,
            11,
            unit="percentunit",
        ),
        panel_ts(
            22,
            "Load averages",
            """SELECT "timestamp" AS time, metric_name AS metric, value
FROM otel_metrics_gauge
WHERE metric_name IN ('system.cpu.load_average.1m','system.cpu.load_average.5m','system.cpu.load_average.15m')
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
ORDER BY 1""",
            0,
            19,
            unit="short",
        ),
        panel_ts(
            23,
            "Container CPU",
            """SELECT $__timeGroupAlias("timestamp", $__interval),
       resource_attributes->>'container.name' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name='container.cpu.utilization'
  AND resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
GROUP BY 1,2
ORDER BY 1""",
            12,
            19,
            unit="percentunit",
        ),
        panel_table(
            30,
            "Errors on this host",
            f"""SELECT "timestamp",
       coalesce(resource_attributes->>'service.name', service_name) AS service,
       coalesce(severity_text,'') AS severity,
       left(body, 4000) AS body
FROM otel_logs
WHERE resource_attributes->>'host.name'='$host'
  AND $__timeFilter("timestamp")
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 100""",
            0,
            27,
            h=11,
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


def build_errors():
    panels = [
        panel_stat(
            1,
            "Incidents (errors)",
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
            desc="An incident ≈ an error/exception/warn event in OTEL logs.",
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
            desc="Errors that carry a trace id for deep dive.",
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
       count(*) FILTER (WHERE coalesce(severity_text,'') ~* 'fatal|crit') AS criticalish,
       max("timestamp") AS last_seen,
       left(max(body), 240) AS sample
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2
ORDER BY incidents DESC
LIMIT 80
""".strip(),
            0,
            4,
            h=9,
            desc="Pick a service in the variable to drill into the detail stream below.",
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
GROUP BY 1, 2
ORDER BY 1""",
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
       coalesce(log_attributes->>'log.source', log_attributes->>'log.file.name', '') AS source,
       coalesce(trace_id, '') AS trace_id,
       left(body, 5000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{service:sqlstring}})
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 250""",
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
            service_var(
                where=(
                    "coalesce(resource_attributes->>'service.name', service_name) NOT IN "
                    "('cse-01-host','cse-01-system')"
                )
            ),
        ],
        time_from="now-12h",
    )


def main():
    suite = {
        "backup-operations.json": build_backups(),
        "fleet-infrastructure.json": build_fleet_infra(),
        "server-detail.json": build_host_detail(),
        "errors-incidents.json": build_errors(),
    }
    for name, d in suite.items():
        path = OUT / name
        path.write_text(json.dumps(d, indent=2) + "\n")
        print(f"wrote {path.name} uid={d['uid']} panels={len(d['panels'])}")


if __name__ == "__main__":
    main()
