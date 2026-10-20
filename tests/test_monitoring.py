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


def _compose_allowed_hosts():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    raw = compose["x-backend-common"]["environment"]["ALLOWED_HOSTS"]
    match = re.fullmatch(r"\$\{ALLOWED_HOSTS:-([^}]*)\}", raw)
    assert match, f"expected a ${{ALLOWED_HOSTS:-default}} interpolation, got {raw!r}"
    return [h.strip() for h in match.group(1).split(",")]


class PrometheusCanReachTheApiTests(TestCase):
    """The first real CI run of the Grafana check failed: Prometheus scrapes web:8000, so it sends `Host: web:8000`, and Django
    answers 400 to a host that is not in ALLOWED_HOSTS (the DEBUG default is localhost-only). The API target was permanently down."""

    def scrape_host(self):
        prom = yaml.safe_load((ROOT / "monitoring" / "prometheus.yml").read_text())
        job = next(j for j in prom["scrape_configs"] if j["job_name"] == "whattocook-api")
        return job["static_configs"][0]["targets"][0]  # e.g. "web:8000"

    def test_the_compose_default_allows_the_host_prometheus_sends(self):
        self.assertIn(self.scrape_host().split(":")[0], _compose_allowed_hosts())

    def test_the_compose_default_keeps_what_the_healthchecks_and_browsers_use(self):
        self.assertTrue({"localhost", "127.0.0.1"} <= set(_compose_allowed_hosts()))  # Dockerfile HEALTHCHECK uses 127.0.0.1

    def test_metrics_answers_200_to_that_host_under_the_compose_default(self):
        with self.settings(ALLOWED_HOSTS=_compose_allowed_hosts()):
            response = self.client.get("/metrics", HTTP_HOST=self.scrape_host())
        self.assertEqual(response.status_code, 200)

    def test_control_without_web_the_same_scrape_is_a_400(self):
        with self.settings(ALLOWED_HOSTS=["localhost", "127.0.0.1", "0.0.0.0"]), self.assertLogs("django.security.DisallowedHost", "ERROR"):
            response = self.client.get("/metrics", HTTP_HOST=self.scrape_host())
        self.assertEqual(response.status_code, 400)

    def test_env_example_no_longer_claims_a_wildcard_default_and_says_to_keep_web(self):
        text = (ROOT / ".env.example").read_text()
        self.assertNotIn('Default "*"', text)
        self.assertIn('Keep "web"', text)


class ScrapeDiagnosticsTests(TestCase):
    """When the scrape check gives up it must say which target is down and why (it used to print only the list of jobs)."""

    def setUp(self):
        spec = importlib.util.spec_from_file_location("check_grafana", ROOT / "scripts" / "check_grafana.py")
        self.cg = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cg)

    @staticmethod
    def targets(*rows):
        return {"status": "success", "data": {"activeTargets": [
            {"labels": {"job": job}, "scrapeUrl": url, "health": health, "lastError": error} for job, url, health, error in rows]}}

    def test_each_job_gets_its_health_url_and_last_error(self):
        result = self.targets(("rabbitmq", "http://rabbitmq:15692/metrics", "up", ""),
                              ("celery-flower", "http://flower:5555/metrics", "down", "connection refused"))
        text = self.cg.describe_targets(200, result, ["rabbitmq", "celery-flower"])
        self.assertIn("rabbitmq: up  http://rabbitmq:15692/metrics", text)
        self.assertIn("celery-flower: down  http://flower:5555/metrics  lastError: connection refused", text)

    def test_a_400_from_the_api_points_at_allowed_hosts(self):
        result = self.targets(("whattocook-api", "http://web:8000/metrics", "down", "server returned HTTP status 400 Bad Request"))
        self.assertIn("ALLOWED_HOSTS", self.cg.describe_targets(200, result, ["whattocook-api"]))

    def test_the_allowed_hosts_hint_is_only_for_the_api_job(self):
        result = self.targets(("celery-flower", "http://flower:5555/metrics", "down", "server returned HTTP status 400 Bad Request"))
        self.assertNotIn("ALLOWED_HOSTS", self.cg.describe_targets(200, result, ["celery-flower"]))

    def test_a_401_points_at_the_metrics_token(self):
        result = self.targets(("whattocook-api", "http://web:8000/metrics", "down", "server returned HTTP status 401 Unauthorized"))
        self.assertIn("METRICS_TOKEN", self.cg.describe_targets(200, result, ["whattocook-api"]))

    def test_a_job_with_no_active_target_is_named(self):
        text = self.cg.describe_targets(200, self.targets(), ["rabbitmq"])
        self.assertIn("rabbitmq: no active target", text)

    def test_an_unreadable_targets_endpoint_is_reported_not_raised(self):
        text = self.cg.describe_targets(502, "bad gateway", ["rabbitmq"])
        self.assertIn("could not read Prometheus targets", text)
        self.assertIn("502", text)

    def test_poll_appends_the_explanation_when_it_gives_up(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            self.cg.poll("target down", lambda: None, 0, explain=lambda: "      rabbitmq: down  http://x  lastError: boom")
        self.assertIn("target down (gave up after 0s)", out.getvalue())
        self.assertIn("lastError: boom", out.getvalue())

    def test_poll_without_an_explanation_still_fails_cleanly(self):
        import contextlib
        import io

        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            self.cg.poll("target down", lambda: None, 0)
        self.assertEqual(out.getvalue().count("\n"), 1)

    def test_the_scrape_check_wires_the_explanation_in(self):
        source = (ROOT / "scripts" / "check_grafana.py").read_text()
        self.assertTrue("targets_up, args.wait, explain_targets" in source, "the scrape poll must be given explain_targets")
        self.assertTrue("/api/v1/targets?state=active" in source, "the explanation must read Prometheus's active targets")
        self.assertTrue("first_readable(" in source and "args.prometheus" in source, "Prometheus is tried directly before the Grafana proxy")
        self.assertTrue("{args.prometheus.rstrip('/')}/api/v1/targets?state=active" in source, "the direct source must ask for the ACTIVE targets")

    def test_the_first_readable_source_wins_and_a_failing_one_falls_through(self):
        good = (200, {"status": "success", "data": {"activeTargets": []}})
        calls = []
        self.assertEqual(self.cg.first_readable(lambda: calls.append("direct") or (0, "connection refused"), lambda: calls.append("proxy") or good), good)
        self.assertEqual(calls, ["direct", "proxy"])
        calls.clear()
        self.assertEqual(self.cg.first_readable(lambda: calls.append("direct") or good, lambda: calls.append("proxy") or (403, "forbidden")), good)
        self.assertEqual(calls, ["direct"], "no second request when the first source answered")

    def test_an_error_status_from_prometheus_is_not_readable_so_the_next_source_is_tried(self):
        good = (200, {"status": "success", "data": {"activeTargets": []}})
        self.assertEqual(self.cg.first_readable(lambda: (200, {"status": "error", "error": "boom"}), lambda: good), good)

    def test_prometheus_url_is_a_real_command_line_option(self):
        import subprocess
        import sys

        out = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_grafana.py"), "--help"], capture_output=True, text=True, timeout=30)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertRegex(out.stdout, r"--prometheus PROMETHEUS\b")  # the exact option (argparse also accepts abbreviations)

    def test_the_grafana_proxy_is_kept_as_the_fallback_source(self):
        source = (ROOT / "scripts" / "check_grafana.py").read_text()
        self.assertTrue("/api/datasources/proxy/uid/{DATASOURCE_UID}/api/v1/targets?state=active" in source, "the proxy fallback is gone")

    def test_when_no_source_is_readable_the_last_failure_is_what_gets_reported(self):
        self.assertEqual(self.cg.first_readable(lambda: (0, "refused"), lambda: (403, "forbidden")), (403, "forbidden"))
        self.assertEqual(self.cg.first_readable(lambda: (200, {"status": "error"})), (200, {"status": "error"}))
