#!/usr/bin/env python3
"""Generate CytoSorbents enterprise Grafana dashboards (SereneDB TIMESTAMP_NS-safe)."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
DS = {"type": "grafana-postgresql-datasource", "uid": "serenedb"}
FOLDER = "bg4s2ze4a7o5cc"

ERROR_PRED = """(
    log_attributes->>'log.kind' = 'error'
    OR log_attributes->>'exception.type' IS NOT NULL
    OR coalesce(severity_text,'') ~* '^(error|fatal|critical|warn|warning)$'
    OR body ~* '(Exception|Traceback|error_proto|FATAL|\\\\[php:(error|crit|alert)\\\\])'
  )"""

FRESH_5M = "epoch_ns({col}) > (extract(epoch from now()) - 300) * 1000000000"
HOSTS_UP_WHERE = f'"timestamp" > make_timestamp_ns((extract(epoch from now()) - 300)::bigint * 1000000000)'


def panel_stat(pid, title, sql, x, y, w=4, h=4, unit=None, desc="", thresholds=None, color_mode="value"):
    fc = {
        "defaults": {
            "thresholds": thresholds
            or {
                "mode": "absolute",
                "steps": [{"color": "blue", "value": None}],
            }
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
            "textMode": "value_and_name" if " / " in title or "UP" in title else "auto",
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


def panel_ts(pid, title, sql, x, y, w=12, h=8, unit="percentunit", desc="", bars=False):
    custom = {
        "drawStyle": "bars" if bars else "line",
        "lineWidth": 2,
        "fillOpacity": 40 if bars else 15,
        "showPoints": "never",
    }
    if bars:
        custom["stacking"] = {"mode": "normal"}
    return {
        "type": "timeseries",
        "id": pid,
        "title": title,
        "description": desc,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": DS,
        "fieldConfig": {
            "defaults": {
                "unit": unit,
                "min": 0,
                "custom": custom,
            },
            "overrides": [],
        },
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
            "tooltip": {"mode": "multi"},
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


STATUS_OVERRIDE = {
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
                    },
                }
            ],
        },
    ],
}

UPTIME_OVERRIDE = {
    "matcher": {"id": "byName", "options": "uptime"},
    "properties": [{"id": "unit", "value": "dtdurations"}],
}
CPU_OVERRIDE = {
    "matcher": {"id": "byName", "options": "cpu"},
    "properties": [{"id": "unit", "value": "percentunit"}],
}
MEM_OVERRIDE = {
    "matcher": {"id": "byName", "options": "memory"},
    "properties": [{"id": "unit", "value": "percentunit"}],
}
HOST_UPTIME_OVERRIDE = {
    "matcher": {"id": "byName", "options": "host_uptime"},
    "properties": [{"id": "unit", "value": "dtdurations"}],
}
HOST_CPU_OVERRIDE = {
    "matcher": {"id": "byName", "options": "host_cpu"},
    "properties": [{"id": "unit", "value": "percentunit"}],
}
HOST_MEM_OVERRIDE = {
    "matcher": {"id": "byName", "options": "host_mem"},
    "properties": [{"id": "unit", "value": "percentunit"}],
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
        {"color": "red", "value": 20},
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
            "resource_attributes->>'host.name' AS __value FROM ("
            " SELECT resource_attributes FROM otel_metrics_gauge"
            " UNION ALL SELECT resource_attributes FROM otel_logs"
            ") s WHERE resource_attributes->>'host.name' IS NOT NULL ORDER BY 1"
        ),
        "includeAll": include_all,
        "allValue": None,
        "label": "Host",
        "multi": multi,
        "name": name,
        "query": (
            "SELECT DISTINCT resource_attributes->>'host.name' AS __text, "
            "resource_attributes->>'host.name' AS __value FROM ("
            " SELECT resource_attributes FROM otel_metrics_gauge"
            " UNION ALL SELECT resource_attributes FROM otel_logs"
            ") s WHERE resource_attributes->>'host.name' IS NOT NULL ORDER BY 1"
        ),
        "refresh": 2,
        "regex": "",
        "type": "query",
        "sort": 1,
    }


APP_HEALTH_SQL = f"""
WITH apps(app, host, metric_uptime, metric_cpu, metric_mem, container_name, service_name, process_exe) AS (
  VALUES
    ('print-via-email', 'print-via-email-pi', 'process.uptime', 'process.cpu.utilization', 'process.memory.utilization', NULL, 'print-via-email', NULL),
    ('moodle', 'CSE-01', 'process.uptime', 'process.cpu.utilization', 'process.memory.utilization', NULL, 'moodle', 'apache2'),
    ('openproject', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'openproject-web-1', 'openproject', NULL),
    ('forgejo', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'forgejo', 'forgejo', NULL)
),
uptime AS (
  SELECT a.app,
         (SELECT g.value FROM otel_metrics_gauge g
          WHERE g.metric_name = a.metric_uptime
            AND g.resource_attributes->>'host.name' = a.host
            AND (a.container_name IS NULL OR g.resource_attributes->>'container.name' = a.container_name)
            AND (a.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = a.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS uptime_s,
         (SELECT max(g."timestamp") FROM otel_metrics_gauge g
          WHERE g.metric_name = a.metric_uptime
            AND g.resource_attributes->>'host.name' = a.host
            AND (a.container_name IS NULL OR g.resource_attributes->>'container.name' = a.container_name)
            AND (a.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = a.process_exe)
            AND $__timeFilter(g."timestamp")) AS last_seen
  FROM apps a
),
cpu AS (
  SELECT a.app,
         (SELECT g.value FROM otel_metrics_gauge g
          WHERE g.metric_name = a.metric_cpu
            AND g.resource_attributes->>'host.name' = a.host
            AND (a.container_name IS NULL OR g.resource_attributes->>'container.name' = a.container_name)
            AND (a.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = a.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS cpu_util
  FROM apps a
),
mem AS (
  SELECT a.app,
         (SELECT CASE WHEN a.metric_mem = 'container.memory.percent' THEN g.value / 100.0 ELSE g.value END
          FROM otel_metrics_gauge g
          WHERE g.metric_name = a.metric_mem
            AND g.resource_attributes->>'host.name' = a.host
            AND (a.container_name IS NULL OR g.resource_attributes->>'container.name' = a.container_name)
            AND (a.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = a.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS mem_util
  FROM apps a
),
errs AS (
  SELECT a.app, count(*) AS error_count
  FROM apps a
  LEFT JOIN otel_logs l
    ON coalesce(l.resource_attributes->>'service.name', l.service_name) = a.service_name
   AND l.resource_attributes->>'host.name' = a.host
   AND $__timeFilter(l."timestamp")
   AND {ERROR_PRED}
  GROUP BY a.app
)
SELECT a.app,
       a.host,
       CASE WHEN u.last_seen IS NOT NULL AND {FRESH_5M.format(col='u.last_seen')} THEN 'UP' ELSE 'DOWN' END AS status,
       u.uptime_s AS uptime,
       c.cpu_util AS cpu,
       m.mem_util AS memory,
       coalesce(e.error_count, 0) AS errors,
       u.last_seen
FROM apps a
LEFT JOIN uptime u ON u.app = a.app
LEFT JOIN cpu c ON c.app = a.app
LEFT JOIN mem m ON m.app = a.app
LEFT JOIN errs e ON e.app = a.app
WHERE a.host IN (${{host:sqlstring}})
ORDER BY status ASC, a.host, a.app
""".strip()


HOST_INFRA_SQL = f"""
WITH hosts AS (
  SELECT DISTINCT resource_attributes->>'host.name' AS host
  FROM otel_metrics_gauge
  WHERE $__timeFilter("timestamp")
    AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
),
last_seen AS (
  SELECT resource_attributes->>'host.name' AS host, max("timestamp") AS last_seen
  FROM otel_metrics_gauge
  WHERE $__timeFilter("timestamp")
  GROUP BY 1
),
uptime AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host, value AS host_uptime
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.uptime' AND $__timeFilter("timestamp")
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
),
cpu AS (
  SELECT resource_attributes->>'host.name' AS host, avg(value) AS host_cpu
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.cpu.utilization' AND $__timeFilter("timestamp")
  GROUP BY 1
),
mem AS (
  SELECT DISTINCT ON (resource_attributes->>'host.name')
         resource_attributes->>'host.name' AS host, value AS host_mem
  FROM otel_metrics_gauge
  WHERE metric_name = 'system.memory.utilization' AND $__timeFilter("timestamp")
  ORDER BY resource_attributes->>'host.name', "timestamp" DESC
)
SELECT h.host,
       CASE WHEN ls.last_seen IS NOT NULL AND {FRESH_5M.format(col='ls.last_seen')} THEN 'UP' ELSE 'DOWN' END AS status,
       u.host_uptime,
       c.host_cpu,
       m.host_mem,
       ls.last_seen
FROM hosts h
LEFT JOIN last_seen ls ON ls.host = h.host
LEFT JOIN uptime u ON u.host = h.host
LEFT JOIN cpu c ON c.host = h.host
LEFT JOIN mem m ON m.host = h.host
ORDER BY status ASC, h.host
""".strip()


def build_command_center():
    panels = [
        panel_stat(
            1,
            "Hosts UP",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name') AS "Hosts UP"
FROM otel_metrics_gauge
WHERE {HOSTS_UP_WHERE}
  AND resource_attributes->>'host.name' IS NOT NULL
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})""",
            0,
            0,
            w=3,
            desc="Hosts with any metric sample in the last 5 minutes (TIMESTAMP_NS-safe).",
            thresholds={
                "mode": "absolute",
                "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}],
            },
            color_mode="background",
        ),
        panel_stat(
            2,
            "Apps UP",
            f"""SELECT count(*) AS "Apps UP" FROM (
  SELECT a.app FROM (
    VALUES
      ('print-via-email', 'print-via-email-pi', 'process.uptime', NULL, NULL),
      ('moodle', 'CSE-01', 'process.uptime', NULL, 'apache2'),
      ('openproject', 'CSE-01', 'container.uptime', 'openproject-web-1', NULL),
      ('forgejo', 'CSE-01', 'container.uptime', 'forgejo', NULL)
  ) AS a(app, host, metric_uptime, container_name, process_exe)
  WHERE a.host IN (${{host:sqlstring}})
    AND EXISTS (
      SELECT 1 FROM otel_metrics_gauge g
      WHERE g.metric_name = a.metric_uptime
        AND g.resource_attributes->>'host.name' = a.host
        AND (a.container_name IS NULL OR g.resource_attributes->>'container.name' = a.container_name)
        AND (a.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = a.process_exe)
        AND g."timestamp" > make_timestamp_ns((extract(epoch from now()) - 300)::bigint * 1000000000)
    )
) s""",
            3,
            0,
            w=3,
            desc="Catalog apps with a fresh uptime sample in the last 5 minutes.",
            thresholds={
                "mode": "absolute",
                "steps": [{"color": "red", "value": None}, {"color": "green", "value": 1}],
            },
            color_mode="background",
        ),
        panel_stat(
            3,
            "Errors",
            f"""SELECT count(*) AS "Errors"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND {ERROR_PRED}""",
            6,
            0,
            w=3,
            desc="Error/exception logs only — INFO excluded.",
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_stat(
            4,
            "Host CPU",
            """SELECT avg(value) AS "Host CPU"
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})""",
            9,
            0,
            w=5,
            unit="percentunit",
            desc="Average system.cpu.utilization across selected hosts.",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            5,
            "Host memory",
            """SELECT avg(value) AS "Host memory"
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})""",
            14,
            0,
            w=5,
            unit="percentunit",
            desc="Average system.memory.utilization across selected hosts.",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            6,
            "Fleet size",
            """SELECT count(DISTINCT resource_attributes->>'host.name') AS "Hosts"
FROM otel_metrics_gauge
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})""",
            19,
            0,
            w=5,
            desc="Distinct hosts in the selected time range.",
        ),
        panel_table(
            10,
            "Application health",
            APP_HEALTH_SQL,
            0,
            4,
            h=9,
            desc="One row per production app. Uptime = process/container seconds since start (duration). Status = metric in last 5 minutes.",
            overrides=[STATUS_OVERRIDE, UPTIME_OVERRIDE, CPU_OVERRIDE, MEM_OVERRIDE],
        ),
        panel_table(
            11,
            "Host infrastructure",
            HOST_INFRA_SQL,
            0,
            13,
            h=7,
            desc="Machine-level health. host_uptime = OS uptime (duration), not a chart.",
            overrides=[STATUS_OVERRIDE, HOST_UPTIME_OVERRIDE, HOST_CPU_OVERRIDE, HOST_MEM_OVERRIDE],
        ),
        panel_ts(
            20,
            "Host CPU utilization",
            """SELECT "timestamp" AS time,
       resource_attributes->>'host.name' AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
GROUP BY 1, 2
ORDER BY 1""",
            0,
            20,
            desc="system.cpu.utilization per host (machine load).",
        ),
        panel_ts(
            21,
            "Host memory utilization",
            """SELECT "timestamp" AS time,
       resource_attributes->>'host.name' AS metric,
       value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${host:sqlstring})
ORDER BY 1""",
            12,
            20,
            desc="system.memory.utilization per host.",
        ),
        panel_ts(
            22,
            "Error rate by app",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2
ORDER BY 1""",
            0,
            28,
            unit="short",
            bars=True,
            desc="Errors/exceptions only — no INFO noise.",
        ),
        panel_table(
            23,
            "Recent errors",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS app,
       coalesce(severity_text, log_attributes->>'severity', '') AS severity,
       left(body, 2000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 40""",
            12,
            28,
            w=12,
            h=8,
            desc="Latest failures across the fleet.",
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 480},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                }
            ],
        ),
    ]

    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": True,
                "keepTime": True,
                "tags": [],
                "targetBlank": False,
                "title": "Host & Infrastructure",
                "type": "link",
                "url": "/d/cyto-server-detail/cyto-sorbents-observability-host-infrastructure?var-host=${host}",
            },
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": True,
                "keepTime": True,
                "tags": [],
                "targetBlank": False,
                "title": "Errors & Incidents",
                "type": "link",
                "url": "/d/cyto-errors/cyto-sorbents-observability-errors-incidents?var-host=${host}",
            },
        ],
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["cytosorbents", "production", "observability", "fleet"],
        "templating": {"list": [host_var(multi=True, include_all=True)]},
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "CytoSorbents Observability — Command Center",
        "uid": "cyto-fleet-overview",
        "version": 1,
    }


def build_infra():
    services_sql = f"""
WITH catalog(app, host, metric_uptime, metric_cpu, metric_mem, container_name, service_name, process_exe) AS (
  VALUES
    ('print-via-email', 'print-via-email-pi', 'process.uptime', 'process.cpu.utilization', 'process.memory.utilization', NULL, 'print-via-email', NULL),
    ('moodle (apache)', 'CSE-01', 'process.uptime', 'process.cpu.utilization', 'process.memory.utilization', NULL, 'moodle', 'apache2'),
    ('openproject-web', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'openproject-web-1', 'openproject', NULL),
    ('openproject-worker', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'openproject-worker-1', 'openproject', NULL),
    ('forgejo', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'forgejo', 'forgejo', NULL),
    ('forgejo-private', 'CSE-01', 'container.uptime', 'container.cpu.utilization', 'container.memory.percent', 'forgejo-private', 'forgejo', NULL)
),
rows AS (
  SELECT c.app,
         c.service_name,
         (SELECT g.value FROM otel_metrics_gauge g
          WHERE g.metric_name = c.metric_uptime
            AND g.resource_attributes->>'host.name' = '$host'
            AND (c.container_name IS NULL OR g.resource_attributes->>'container.name' = c.container_name)
            AND (c.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = c.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS uptime_s,
         (SELECT max(g."timestamp") FROM otel_metrics_gauge g
          WHERE g.metric_name = c.metric_uptime
            AND g.resource_attributes->>'host.name' = '$host'
            AND (c.container_name IS NULL OR g.resource_attributes->>'container.name' = c.container_name)
            AND (c.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = c.process_exe)
            AND $__timeFilter(g."timestamp")) AS last_seen,
         (SELECT g.value FROM otel_metrics_gauge g
          WHERE g.metric_name = c.metric_cpu
            AND g.resource_attributes->>'host.name' = '$host'
            AND (c.container_name IS NULL OR g.resource_attributes->>'container.name' = c.container_name)
            AND (c.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = c.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS cpu_util,
         (SELECT CASE WHEN c.metric_mem = 'container.memory.percent' THEN g.value / 100.0 ELSE g.value END
          FROM otel_metrics_gauge g
          WHERE g.metric_name = c.metric_mem
            AND g.resource_attributes->>'host.name' = '$host'
            AND (c.container_name IS NULL OR g.resource_attributes->>'container.name' = c.container_name)
            AND (c.process_exe IS NULL OR g.resource_attributes->>'process.executable.name' = c.process_exe)
            AND $__timeFilter(g."timestamp")
          ORDER BY g."timestamp" DESC LIMIT 1) AS mem_util,
         (SELECT count(*) FROM otel_logs l
          WHERE l.resource_attributes->>'host.name' = '$host'
            AND coalesce(l.resource_attributes->>'service.name', l.service_name) = c.service_name
            AND $__timeFilter(l."timestamp")
            AND {ERROR_PRED}) AS errors
  FROM catalog c
  WHERE c.host = '$host'
)
SELECT app,
       CASE WHEN last_seen IS NOT NULL AND {FRESH_5M.format(col='last_seen')} THEN 'UP' ELSE 'DOWN' END AS status,
       uptime_s AS uptime,
       cpu_util AS cpu,
       mem_util AS memory,
       errors,
       last_seen
FROM rows
WHERE last_seen IS NOT NULL OR errors > 0
ORDER BY status ASC, app
""".strip()

    panels = [
        panel_stat(
            1,
            "Status",
            f"""SELECT CASE WHEN max("timestamp") IS NOT NULL AND {FRESH_5M.format(col='max("timestamp")')} THEN 'UP' ELSE 'DOWN' END AS "Status"
FROM otel_metrics_gauge
WHERE resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")""",
            0,
            0,
            w=3,
            desc="UP if any metric arrived in the last 5 minutes.",
            thresholds={
                "mode": "absolute",
                "steps": [{"color": "green", "value": None}],
            },
            color_mode="background",
        ),
        panel_stat(
            2,
            "OS uptime",
            """SELECT value AS "OS uptime"
FROM otel_metrics_gauge
WHERE metric_name = 'system.uptime'
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC
LIMIT 1""",
            3,
            0,
            w=4,
            unit="dtdurations",
            desc="How long this machine has been running (system.uptime).",
        ),
        panel_stat(
            3,
            "Host CPU",
            f"""SELECT avg(value) AS "Host CPU"
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
  AND {HOSTS_UP_WHERE}""",
            7,
            0,
            w=4,
            unit="percentunit",
            desc="Recent host CPU (last ~5 minutes within dashboard range).",
            thresholds=THRESH_CPU,
        ),
        panel_stat(
            4,
            "Host memory",
            """SELECT value AS "Host memory"
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
ORDER BY "timestamp" DESC
LIMIT 1""",
            11,
            0,
            w=4,
            unit="percentunit",
            thresholds=THRESH_MEM,
        ),
        panel_stat(
            5,
            "Errors",
            f"""SELECT count(*) AS "Errors"
FROM otel_logs
WHERE resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
  AND {ERROR_PRED}""",
            15,
            0,
            w=4,
            thresholds=THRESH_ERR,
            color_mode="background",
        ),
        panel_stat(
            6,
            "Host",
            "SELECT '$host' AS \"Host\"",
            19,
            0,
            w=5,
            desc="Selected host variable.",
        ),
        panel_table(
            10,
            "Services on this host",
            services_sql,
            0,
            4,
            h=8,
            desc="Per-app uptime as duration. No uptime line charts.",
            overrides=[STATUS_OVERRIDE, UPTIME_OVERRIDE, CPU_OVERRIDE, MEM_OVERRIDE],
        ),
        panel_ts(
            20,
            "Host CPU",
            """SELECT "timestamp" AS time, 'host.cpu' AS metric, avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name = 'system.cpu.utilization'
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
GROUP BY 1
ORDER BY 1""",
            0,
            12,
        ),
        panel_ts(
            21,
            "Host memory",
            """SELECT "timestamp" AS time, 'host.memory' AS metric, value
FROM otel_metrics_gauge
WHERE metric_name = 'system.memory.utilization'
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
ORDER BY 1""",
            12,
            12,
        ),
        panel_ts(
            22,
            "Per-service CPU",
            """SELECT "timestamp" AS time,
       coalesce(resource_attributes->>'container.name',
                resource_attributes->>'process.executable.name',
                resource_attributes->>'service.name',
                'process') AS metric,
       avg(value) AS value
FROM otel_metrics_gauge
WHERE metric_name IN ('process.cpu.utilization', 'container.cpu.utilization')
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
GROUP BY 1, 2
ORDER BY 1""",
            0,
            20,
            desc="Process and container CPU for this host.",
        ),
        panel_ts(
            23,
            "Load average",
            """SELECT "timestamp" AS time,
       metric_name AS metric,
       value
FROM otel_metrics_gauge
WHERE metric_name IN (
  'system.cpu.load_average.1m',
  'system.cpu.load_average.5m',
  'system.cpu.load_average.15m'
)
  AND resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
ORDER BY 1""",
            12,
            20,
            unit="short",
            desc="Host load averages (when scraped).",
        ),
        panel_ts(
            24,
            "Error rate",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       count(*) AS value
FROM otel_logs
WHERE resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
  AND {ERROR_PRED}
GROUP BY 1, 2
ORDER BY 1""",
            0,
            28,
            w=8,
            unit="short",
            bars=True,
        ),
        panel_table(
            25,
            "Errors on this host",
            f"""SELECT "timestamp",
       coalesce(resource_attributes->>'service.name', service_name) AS app,
       coalesce(severity_text, log_attributes->>'severity', log_attributes->>'log.source', '') AS severity,
       left(body, 4000) AS body
FROM otel_logs
WHERE resource_attributes->>'host.name' = '$host'
  AND $__timeFilter("timestamp")
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 80""",
            8,
            28,
            w=16,
            h=10,
            overrides=[
                {
                    "matcher": {"id": "byName", "options": "body"},
                    "properties": [
                        {"id": "custom.width", "value": 640},
                        {"id": "custom.cellOptions", "value": {"type": "auto", "wrapText": True}},
                    ],
                }
            ],
        ),
    ]

    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": False,
                "keepTime": True,
                "title": "Command Center",
                "type": "link",
                "url": "/d/cyto-fleet-overview/cyto-sorbents-observability-command-center",
            },
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": True,
                "keepTime": True,
                "title": "Errors & Incidents",
                "type": "link",
                "url": "/d/cyto-errors/cyto-sorbents-observability-errors-incidents?var-host=$host",
            },
        ],
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["cytosorbents", "production", "observability", "infrastructure"],
        "templating": {"list": [host_var(multi=False, include_all=False)]},
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "CytoSorbents Observability — Host & Infrastructure",
        "uid": "cyto-server-detail",
        "version": 1,
    }


def build_errors():
    app_var = {
        "current": {"selected": True, "text": "All", "value": "$__all"},
        "datasource": DS,
        "definition": (
            "SELECT DISTINCT coalesce(resource_attributes->>'service.name', service_name) AS __text, "
            "coalesce(resource_attributes->>'service.name', service_name) AS __value "
            "FROM otel_logs WHERE coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL "
            "AND coalesce(resource_attributes->>'service.name', service_name) NOT IN "
            "('cse-01-host','cse-01-system','cse-01-smoke') ORDER BY 1"
        ),
        "includeAll": True,
        "label": "App",
        "multi": True,
        "name": "app",
        "query": (
            "SELECT DISTINCT coalesce(resource_attributes->>'service.name', service_name) AS __text, "
            "coalesce(resource_attributes->>'service.name', service_name) AS __value "
            "FROM otel_logs WHERE coalesce(resource_attributes->>'service.name', service_name) IS NOT NULL "
            "AND coalesce(resource_attributes->>'service.name', service_name) NOT IN "
            "('cse-01-host','cse-01-system','cse-01-smoke') ORDER BY 1"
        ),
        "refresh": 2,
        "type": "query",
        "sort": 1,
    }

    panels = [
        panel_stat(
            1,
            "Error volume",
            f"""SELECT count(*) AS "Errors"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}""",
            0,
            0,
            w=6,
            thresholds=THRESH_ERR,
            color_mode="background",
            desc="Filtered error/exception events in range.",
        ),
        panel_stat(
            2,
            "Apps with errors",
            f"""SELECT count(DISTINCT coalesce(resource_attributes->>'service.name', service_name)) AS "Apps"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}""",
            6,
            0,
            w=6,
            desc="Distinct apps that produced at least one error.",
        ),
        panel_stat(
            3,
            "Hosts with errors",
            f"""SELECT count(DISTINCT resource_attributes->>'host.name') AS "Hosts"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}""",
            12,
            0,
            w=6,
        ),
        panel_stat(
            4,
            "Latest error age",
            f"""SELECT CASE WHEN max("timestamp") IS NULL THEN NULL
       ELSE (extract(epoch from now()) * 1000000000 - epoch_ns(max("timestamp"))) / 1000000000.0
       END AS "Seconds since last error"
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}""",
            18,
            0,
            w=6,
            unit="s",
            desc="Seconds since the most recent error in range (lower is hotter).",
        ),
        panel_ts(
            10,
            "Errors per interval by app",
            f"""SELECT $__timeGroupAlias("timestamp", $__interval),
       coalesce(resource_attributes->>'service.name', service_name) AS metric,
       count(*) AS value
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}
GROUP BY 1, 2
ORDER BY 1""",
            0,
            4,
            w=24,
            h=9,
            unit="short",
            bars=True,
            desc="Error burn rate — INFO excluded.",
        ),
        panel_table(
            20,
            "Incident log",
            f"""SELECT "timestamp",
       resource_attributes->>'host.name' AS host,
       coalesce(resource_attributes->>'service.name', service_name) AS app,
       coalesce(severity_text, log_attributes->>'severity', '') AS severity,
       coalesce(log_attributes->>'log.file.name', log_attributes->>'log.source', '') AS source,
       left(body, 4000) AS body
FROM otel_logs
WHERE $__timeFilter("timestamp")
  AND resource_attributes->>'host.name' IN (${{host:sqlstring}})
  AND coalesce(resource_attributes->>'service.name', service_name) IN (${{app:sqlstring}})
  AND {ERROR_PRED}
ORDER BY "timestamp" DESC
LIMIT 150""",
            0,
            13,
            h=14,
            desc="Failures only. Body truncated for readability.",
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

    return {
        "annotations": {"list": []},
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": False,
                "keepTime": True,
                "title": "Command Center",
                "type": "link",
                "url": "/d/cyto-fleet-overview/cyto-sorbents-observability-command-center",
            },
            {
                "asDropdown": False,
                "icon": "dashboard",
                "includeVars": True,
                "keepTime": True,
                "title": "Host & Infrastructure",
                "type": "link",
                "url": "/d/cyto-server-detail/cyto-sorbents-observability-host-infrastructure?var-host=${host}",
            },
        ],
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": ["cytosorbents", "production", "observability", "errors"],
        "templating": {"list": [host_var(multi=True, include_all=True), app_var]},
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": "CytoSorbents Observability — Errors & Incidents",
        "uid": "cyto-errors",
        "version": 1,
    }


def main():
    suite = {
        "fleet-overview.json": build_command_center(),
        "server-detail.json": build_infra(),
        "errors-incidents.json": build_errors(),
    }
    for name, dash in suite.items():
        path = OUT / name
        path.write_text(json.dumps(dash, indent=2) + "\n")
        print(f"wrote {path} uid={dash['uid']} panels={len(dash['panels'])}")


if __name__ == "__main__":
    main()
