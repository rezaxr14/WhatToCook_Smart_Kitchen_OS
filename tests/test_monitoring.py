"""The Grafana dashboard, Prometheus scrape config, compose service and k8s manifest must stay consistent.

Nothing here needs Grafana or Prometheus. The end-to-end proof (queries actually execute through Grafana, targets are
up, a worker is online) is scripts/check_grafana.py, run by the compose smoke test in CI.
"""
import importlib.util
import json
import re
from pathlib import Path

import yaml
from django.test import TestCase
from prometheus_client import REGISTRY

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "monitoring" / "grafana" / "dashboards" / "whattocook-overview.json"
PROVISIONING = ROOT / "monitoring" / "grafana" / "provisioning"

# Names the dashboard may use for series we do not export ourselves. Verified, not recalled:
#  - Flower 2.0.1: flower/events.py (+ views/monitor.py: /metrics is not authenticated)
#  - RabbitMQ: rabbitmq_prometheus docs (queue series exist unlabelled on /metrics and per queue on /metrics/per-object)
FLOWER_METRICS = {
    "flower_events_total",
    "flower_worker_online",
    "flower_worker_number_of_currently_executing_tasks",
    "flower_task_runtime_seconds_bucket",
    "flower_task_runtime_seconds_count",
    "flower_task_runtime_seconds_sum",
    "flower_task_prefetch_time_seconds",
    "flower_worker_prefetched_tasks",
}
RABBITMQ_METRICS = {
    "rabbitmq_queue_messages_ready",
    "rabbitmq_queue_messages_unacked",
    "rabbitmq_queue_consumers",
    "rabbitmq_connections",
    "rabbitmq_channels",
}


def load_dashboard():
    return json.loads(DASHBOARD.read_text(encoding="utf-8"))


def expressions(dashboard):
    return [t["expr"] for p in dashboard["panels"] for t in p.get("targets", [])]


def metric_names(expr, prefix):
    return set(re.findall(rf"\b({prefix}_[a-z0-9_]+)", expr))


class DashboardStructureTests(TestCase):
    def setUp(self):
        self.dash = load_dashboard()
        self.panels = [p for p in self.dash["panels"] if p["type"] != "row"]

    def test_identity_is_stable_and_not_editable_in_the_ui(self):
        self.assertEqual(self.dash["uid"], "whattocook-overview")
        self.assertIs(self.dash["editable"], False)  # provisioned from files: edit the JSON, not the UI

    def test_panel_ids_are_unique_and_the_grid_stays_inside_24_columns(self):
        ids = [p["id"] for p in self.dash["panels"]]
        self.assertEqual(len(ids), len(set(ids)))
        for p in self.dash["panels"]:
            grid = p["gridPos"]
            self.assertLessEqual(grid["x"] + grid["w"], 24, p["title"])

    def test_every_panel_has_a_title_and_queries_the_provisioned_datasource(self):
        for p in self.panels:
            self.assertTrue(p["title"], p)
            self.assertEqual(p["datasource"]["uid"], "prometheus", p["title"])
            self.assertTrue(p["targets"], p["title"])
            for t in p["targets"]:
                self.assertEqual(t["datasource"]["uid"], "prometheus", p["title"])
                self.assertTrue(t["expr"].strip(), p["title"])

    def test_target_ref_ids_are_unique_within_a_panel(self):
        for p in self.panels:
            refs = [t["refId"] for t in p["targets"]]
            self.assertEqual(len(refs), len(set(refs)), p["title"])

    def test_queries_are_job_agnostic_where_it_matters(self):
        # compose jobs are whattocook-api / celery-flower, Prometheus Operator names them web / flower: only the
        # `up` tiles may select by job, everything else matches on metric name so one dashboard serves both.
        for p in self.panels:
            for t in p["targets"]:
                if t["expr"].startswith(("min(up", "(min(up")):
                    continue
                self.assertNotIn("job=", t["expr"], f"{p['title']}: {t['expr']}")

    def test_healthy_systems_do_not_render_as_no_data(self):
        # An empty numerator made the 5xx tile read "No data" on a healthy API; `or vector(0)` keeps it at 0.
        by_title = {p["title"]: p for p in self.panels}
        self.assertIn("or vector(0)", by_title["5xx ratio"]["targets"][0]["expr"])
        for t in by_title["Responses per second by status class"]["targets"]:
            self.assertIn("or vector(0)", t["expr"])


class MetricNameTests(TestCase):
    """A typo, or a library upgrade that renames a series, would leave a panel silently empty."""

    def setUp(self):
        self.exprs = expressions(load_dashboard())

    def _registered_django_series(self):
        self.client.get("/api/health/")  # loads the django-prometheus middleware, which registers its collectors
        allowed = set()
        for family in REGISTRY.collect():
            if not family.name.startswith("django_http"):
                continue
            allowed.add(family.name)
            if family.type == "counter":
                allowed.add(family.name + "_total")
            if family.type == "histogram":
                allowed.update(family.name + suffix for suffix in ("_bucket", "_count", "_sum"))
        return allowed

    def test_every_django_series_the_dashboard_uses_is_exported_by_django_prometheus(self):
        allowed = self._registered_django_series()
        self.assertTrue(allowed, "django-prometheus registered no django_http_* collectors")
        used = set().union(*(metric_names(e, "django_http") for e in self.exprs))
        self.assertTrue(used)
        self.assertEqual(sorted(used - allowed), [], "dashboard references series django-prometheus does not export")

    def test_flower_series_are_ones_flower_defines(self):
        used = set().union(*(metric_names(e, "flower") for e in self.exprs))
        self.assertTrue(used)
        self.assertEqual(sorted(used - FLOWER_METRICS), [])

    def test_rabbitmq_series_are_ones_the_plugin_exposes(self):
        used = set().union(*(metric_names(e, "rabbitmq") for e in self.exprs))
        self.assertTrue(used)
        self.assertEqual(sorted(used - RABBITMQ_METRICS), [])

    def test_per_queue_panels_select_the_labelled_series_and_totals_the_unlabelled_ones(self):
        by_queue = [e for e in self.exprs if "by (queue)" in e]
        self.assertTrue(by_queue)
        for e in by_queue:
            self.assertIn('queue!=""', e)  # per-object series only
        totals = [e for e in self.exprs if 'queue=""' in e]
        self.assertTrue(totals)  # aggregated /metrics series have no queue label


class ConfigCoherenceTests(TestCase):
    def setUp(self):
        self.prom = yaml.safe_load((ROOT / "monitoring" / "prometheus.yml").read_text())
        self.compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
        self.k8s = {d["kind"] + "/" + d["metadata"]["name"]: d for d in yaml.safe_load_all((ROOT / "k8s/optional/grafana.yaml").read_text()) if d}

    def test_prometheus_scrapes_the_jobs_the_smoke_check_expects(self):
        spec = importlib.util.spec_from_file_location("check_grafana", ROOT / "scripts" / "check_grafana.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        jobs = {j["job_name"] for j in self.prom["scrape_configs"]}
        self.assertEqual(set(module.SCRAPE_JOBS) - jobs, set())

    def test_rabbitmq_per_object_job_uses_the_per_object_path(self):
        job = next(j for j in self.prom["scrape_configs"] if j["job_name"] == "rabbitmq-per-object")
        self.assertEqual(job["metrics_path"], "/metrics/per-object")

    def test_scrape_interval_matches_the_datasource_time_interval(self):
        # $__rate_interval is derived from the datasource's timeInterval; a mismatch makes rate() windows too short.
        ds = yaml.safe_load((PROVISIONING / "datasources" / "prometheus.yml").read_text())["datasources"][0]
        self.assertEqual(ds["jsonData"]["timeInterval"], self.prom["global"]["scrape_interval"])
        self.assertEqual(ds["uid"], "prometheus")
        self.assertTrue(ds["isDefault"])

    def test_compose_grafana_is_private_authenticated_and_really_healthchecked(self):
        g = self.compose["services"]["grafana"]
        self.assertEqual(g["profiles"], ["monitoring"])
        self.assertTrue(all(p.startswith("127.0.0.1:") for p in g["ports"]), g["ports"])  # never published on 0.0.0.0
        self.assertEqual(g["environment"]["GF_AUTH_ANONYMOUS_ENABLED"], "false")
        self.assertEqual(g["environment"]["GF_USERS_ALLOW_SIGN_UP"], "false")
        self.assertNotIn("disable", g["healthcheck"])  # AGENTS.md invariant: never `healthcheck: disable: true`
        self.assertIn("/api/health", g["healthcheck"]["test"][1])
        self.assertIn("grafana_data", self.compose["volumes"])

    def test_image_is_pinned_to_the_same_version_in_compose_and_kubernetes(self):
        compose_image = self.compose["services"]["grafana"]["image"]
        k8s_image = self.k8s["Deployment/grafana"]["spec"]["template"]["spec"]["containers"][0]["image"]
        self.assertRegex(compose_image, r"^grafana/grafana:\d+\.\d+\.\d+$")  # an exact tag, never latest
        self.assertEqual(compose_image, k8s_image)

    def test_dashboard_mount_path_matches_the_provider_in_compose_and_kubernetes(self):
        provider = yaml.safe_load((PROVISIONING / "dashboards" / "dashboards.yml").read_text())["providers"][0]
        path = provider["options"]["path"]
        mounts = [v.split(":")[1] for v in self.compose["services"]["grafana"]["volumes"]]
        self.assertIn(path, mounts)
        self.assertEqual(self.compose["services"]["grafana"]["environment"]["GF_DASHBOARDS_DEFAULT_HOME_DASHBOARD_PATH"], f"{path}/{DASHBOARD.name}")
        k8s_provider = yaml.safe_load(self.k8s["ConfigMap/grafana-dashboard-provider"]["data"]["dashboards.yaml"])["providers"][0]
        self.assertEqual(k8s_provider["options"]["path"], path)
        k8s_mounts = [m["mountPath"] for m in self.k8s["Deployment/grafana"]["spec"]["template"]["spec"]["containers"][0]["volumeMounts"]]
        self.assertIn(path, k8s_mounts)

    def test_kubernetes_pod_is_locked_down(self):
        pod = self.k8s["Deployment/grafana"]["spec"]["template"]["spec"]
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        self.assertIs(pod["automountServiceAccountToken"], False)
        container = pod["containers"][0]
        self.assertIs(container["securityContext"]["allowPrivilegeEscalation"], False)
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        secret_ref = next(e for e in container["env"] if e["name"] == "GF_SECURITY_ADMIN_PASSWORD")["valueFrom"]["secretKeyRef"]
        self.assertEqual(secret_ref["key"], "GRAFANA_ADMIN_PASSWORD")  # never a literal password in the manifest

    def test_example_secret_documents_the_grafana_password(self):
        secret = yaml.safe_load((ROOT / "k8s" / "secret.example.yaml").read_text())
        self.assertIn("GRAFANA_ADMIN_PASSWORD", secret["stringData"])
