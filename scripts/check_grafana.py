#!/usr/bin/env python3
"""End-to-end check of the Grafana stack (compose `monitoring` profile). Standard library only.

    python3 scripts/check_grafana.py [GRAFANA_URL] [USER:PASSWORD]
    defaults: http://localhost:3000  and  $GRAFANA_ADMIN_USER:$GRAFANA_ADMIN_PASSWORD (admin:change-me)

It asserts, in order, that:
  1. Grafana is up and its database is healthy;
  2. the provisioned Prometheus datasource exists, is the default, and passes Grafana's own health check;
  3. the "WhatToCook / Overview" dashboard is provisioned and has every panel from the JSON in the repo;
  4. EVERY panel query executes through Grafana's datasource proxy (status "success"; an empty result is fine);
  5. Prometheus is actually scraping the API, RabbitMQ (both endpoints) and Flower;
  6. data is really flowing: API request counters exist and at least one Celery worker is online in Flower (the
     latter needs worker events, i.e. CELERY_WORKER_SEND_TASK_EVENTS).
Targets and counters take a scrape or two to appear, so 5 and 6 poll for up to --wait seconds.
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DASHBOARD_FILE = os.path.join(os.path.dirname(__file__), "..", "monitoring", "grafana", "dashboards", "whattocook-overview.json")
DASHBOARD_UID = "whattocook-overview"
DATASOURCE_UID = "prometheus"
SCRAPE_JOBS = ["whattocook-api", "rabbitmq", "rabbitmq-per-object", "celery-flower"]


def ok(msg):
    print(f"  \033[32m✔\033[0m {msg}")


def fail(msg):
    print(f"  \033[31m✘\033[0m {msg}")
    sys.exit(1)


class Grafana:
    def __init__(self, base, credentials):
        self.base = base.rstrip("/")
        self.auth = "Basic " + base64.b64encode(credentials.encode()).decode()

    def get(self, path, timeout=15):
        """-> (http_status, parsed_json_or_text)"""
        req = urllib.request.Request(self.base + path, headers={"Authorization": self.auth, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status, body = resp.status, resp.read().decode()
        except urllib.error.HTTPError as err:
            status, body = err.code, err.read().decode()
        except (urllib.error.URLError, OSError) as err:
            return 0, str(err)
        try:
            return status, json.loads(body)
        except ValueError:
            return status, body

    def query(self, expr):
        """Run a PromQL instant query through Grafana's datasource proxy."""
        qs = urllib.parse.urlencode({"query": expr})
        return self.get(f"/api/datasources/proxy/uid/{DATASOURCE_UID}/api/v1/query?{qs}")


def panel_queries(dashboard):
    for panel in dashboard["panels"]:
        for target in panel.get("targets", []):
            yield panel["title"], target["expr"]


def poll(description, fn, wait):
    """Call fn() until it returns a truthy value (returned) or `wait` seconds pass (-> fail)."""
    deadline = time.time() + wait
    last = None
    while True:
        last = fn()
        if last:
            return last
        if time.time() >= deadline:
            fail(f"{description} (gave up after {wait}s)")
        time.sleep(3)


def scalar(result):
    """First sample value of an instant-vector result, else None."""
    data = result.get("data", {}).get("result", []) if isinstance(result, dict) else []
    return float(data[0]["value"][1]) if data else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", default="http://localhost:3000")
    parser.add_argument("credentials", nargs="?", default=f"{os.getenv('GRAFANA_ADMIN_USER', 'admin')}:{os.getenv('GRAFANA_ADMIN_PASSWORD', 'change-me')}")
    parser.add_argument("--wait", type=int, default=90, help="seconds to wait for Grafana / scrape targets / data")
    args = parser.parse_args()
    g = Grafana(args.url, args.credentials)

    print(f"▶ Grafana at {g.base}")

    def healthy():
        status, body = g.get("/api/health", timeout=5)
        return status == 200 and isinstance(body, dict) and body.get("database") == "ok" and body
    health = poll("Grafana is not healthy (/api/health database != ok)", healthy, args.wait)
    ok(f"Grafana {health.get('version', '?')} healthy (database ok)")

    status, _ = g.get("/api/user")  # any authenticated endpoint: tells a bad password apart from a missing resource
    if status == 401:
        fail("authentication failed: check GRAFANA_ADMIN_USER / GRAFANA_ADMIN_PASSWORD (or the credentials argument)")
    if status != 200:
        fail(f"authenticated probe /api/user returned HTTP {status}")

    status, ds = g.get(f"/api/datasources/uid/{DATASOURCE_UID}")
    if status != 200 or not isinstance(ds, dict):
        fail(f"datasource '{DATASOURCE_UID}' not provisioned (HTTP {status}): {ds}")
    if ds.get("type") != "prometheus" or not ds.get("isDefault"):
        fail(f"datasource '{DATASOURCE_UID}' should be the default Prometheus datasource, got type={ds.get('type')} isDefault={ds.get('isDefault')}")
    ok(f"datasource '{ds.get('name')}' provisioned (default, {ds.get('url')})")

    status, health_ds = g.get(f"/api/datasources/uid/{DATASOURCE_UID}/health")
    state = str(health_ds.get("status", "OK")).upper() if isinstance(health_ds, dict) else "?"
    if status != 200 or state != "OK":
        fail(f"datasource health check failed (HTTP {status}): {health_ds}")
    ok("datasource health check passes (Grafana can reach Prometheus)")

    with open(DASHBOARD_FILE, encoding="utf-8") as fh:
        expected = json.load(fh)
    status, body = g.get(f"/api/dashboards/uid/{DASHBOARD_UID}")
    if status != 200 or not isinstance(body, dict):
        fail(f"dashboard '{DASHBOARD_UID}' not provisioned (HTTP {status}): {body}")
    live = body["dashboard"]
    if not body.get("meta", {}).get("provisioned"):
        fail("dashboard exists but was not provisioned from files (someone created it by hand?)")
    want, have = len(expected["panels"]), len(live.get("panels", []))
    if want != have:
        fail(f"dashboard has {have} panels in Grafana but {want} in {os.path.basename(DASHBOARD_FILE)}")
    ok(f"dashboard '{live['title']}' provisioned with all {have} panels")

    queries = list(panel_queries(expected))
    for title, expr in queries:
        status, result = g.query(expr.replace("$__rate_interval", "5m"))
        if status != 200 or not isinstance(result, dict) or result.get("status") != "success":
            fail(f"panel '{title}' query does not execute through Grafana (HTTP {status}): {expr}\n      -> {result}")
    ok(f"all {len(queries)} panel queries execute through Grafana's datasource proxy")

    def targets_up():
        status, result = g.query("up")
        if status != 200 or not isinstance(result, dict):
            return None
        up = {r["metric"].get("job"): r["value"][1] == "1" for r in result["data"]["result"]}
        missing = [j for j in SCRAPE_JOBS if not up.get(j)]
        return {"up": up} if not missing else None
    poll(f"Prometheus is not scraping all of {SCRAPE_JOBS} (check `docker compose --profile monitoring ps` and monitoring/prometheus.yml)", targets_up, args.wait)
    ok("Prometheus scrapes " + ", ".join(SCRAPE_JOBS))

    poll("no django_http_* series: the API is not exporting request metrics",
         lambda: (scalar(g.query("sum(django_http_requests_total_by_method_total)")[1]) or 0) > 0, args.wait)
    ok("API request counters are flowing")

    poll("no Celery worker is online in Flower: workers are not emitting events (CELERY_WORKER_SEND_TASK_EVENTS) or Flower cannot reach the broker",
         lambda: (scalar(g.query("sum(flower_worker_online)")[1]) or 0) >= 1, args.wait)
    ok("at least one Celery worker is online in Flower (worker events are enabled)")

    print("Grafana checks passed.")


if __name__ == "__main__":
    main()
