"""Guards for the nightly load/soak setup: .github/workflows/load.yml, load/k6/*.js and scripts/check_ai_queue.py.

The soak itself only runs on a GitHub runner (it needs Docker); these read the files and cross-check them against the
app (routes, queue names), so a rename or an edit that would silently turn the nightly into a no-op fails here.
"""
import re
from pathlib import Path

import yaml
from django.test import SimpleTestCase
from django.urls import resolve

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github" / "workflows" / "load.yml"
MAIN_JS = (ROOT / "load" / "k6" / "main.js").read_text(encoding="utf-8")
THROTTLE_JS = (ROOT / "load" / "k6" / "throttle.js").read_text(encoding="utf-8")


def workflow():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def job_steps():
    return workflow()["jobs"]["soak"]["steps"]


def step(fragment):
    """The single step whose name contains `fragment`."""
    matches = [s for s in job_steps() if fragment in s.get("name", "")]
    assert len(matches) == 1, (fragment, [s.get("name") for s in job_steps()])
    return matches[0]


def index(fragment):
    return job_steps().index(step(fragment))


class LoadWorkflowTests(SimpleTestCase):
    def test_it_runs_nightly_and_on_demand_but_is_never_a_pr_or_push_gate(self):
        triggers = workflow().get("on") or workflow().get(True)  # PyYAML reads the bare key `on` as True
        self.assertEqual(set(triggers), {"schedule", "workflow_dispatch"})
        self.assertTrue(triggers["schedule"][0]["cron"])

    def test_least_privilege_bounded_runtime_and_no_overlapping_runs(self):
        wf = workflow()
        self.assertEqual(wf["permissions"], {"contents": "read"})
        self.assertFalse(wf["concurrency"]["cancel-in-progress"])
        self.assertLessEqual(wf["jobs"]["soak"]["timeout-minutes"], 60)

    def test_dispatch_inputs_reach_the_shell_only_through_env_and_are_validated(self):
        for s in job_steps():
            self.assertNotIn("${{ inputs.", s.get("run", ""), f"{s.get('name')}: interpolating an input into a script is an injection vector")
        env = workflow()["jobs"]["soak"]["env"]
        self.assertIn("inputs.steady", env["STEADY"])
        self.assertIn("inputs.tasks", env["TASKS"])
        validate = step("Validate inputs")["run"]
        self.assertIn("$STEADY", validate)
        self.assertIn("$TASKS", validate)

    def test_k6_is_pinned_to_a_release_and_verified_against_its_checksum(self):
        env = workflow()["jobs"]["soak"]["env"]
        self.assertRegex(env["K6_VERSION"], r"^v\d+\.\d+\.\d+$")
        self.assertRegex(env["K6_SHA256"], r"^[0-9a-f]{64}$")
        install = step("Install k6")["run"]
        self.assertIn("sha256sum -c", install)
        self.assertIn("${K6_VERSION}", install)
        self.assertLess(install.index("sha256sum -c"), install.index("tar -xzf"), "verify before unpacking")

    def test_the_stack_runs_production_settings_with_no_rate_limits_and_no_llm_key(self):
        configure = step("Configure the stack")["run"]
        self.assertIn('echo "DEBUG=false"', configure)
        self.assertIn('echo "GEMINI_API_KEY="', configure)  # empty: the provider fails instantly into the fallback
        self.assertIn('echo "THROTTLING_ENABLED=false"', configure)
        self.assertIn("openssl rand", configure)  # random secret key and database password, never a placeholder
        self.assertNotIn("cp .env.example .env", configure, ".env.example carries a non-empty placeholder GEMINI_API_KEY")
        # every key it sets must first be stripped from the copy, or the file would hold two values for it
        stripped = re.search(r"grep -vE '\^\(([^)]*)\)=' \.env\.example", configure)
        self.assertIsNotNone(stripped)
        for key in ("DEBUG", "SECRET_KEY", "POSTGRES_PASSWORD", "GEMINI_API_KEY", "THROTTLING_ENABLED"):
            self.assertIn(key, stripped.group(1).split("|"))

    def test_the_phases_run_in_order(self):
        order = [index(n) for n in ("Configure the stack", "Start the stack", "Soak with k6", "Rate limits still hold")]
        self.assertEqual(order, sorted(order))

    def test_the_ai_queue_burst_lands_while_k6_is_running(self):
        run = step("Soak with k6")["run"]
        k6_started = run.index("k6 run")
        burst = run.index("check_ai_queue.py")
        joined = run.index('wait "$K6_PID"')
        self.assertLess(k6_started, burst)
        self.assertLess(burst, joined)
        self.assertRegex(run[k6_started:burst], r"\$!\s", "k6 must be a background job when the burst starts")
        self.assertIn("main.js", run)
        self.assertIn("--summary-export", run)
        self.assertRegex(run, r"K6_RC.*\n.*QUEUE_RC|QUEUE_RC.*\n.*K6_RC|K6_RC.*QUEUE_RC", "both exit codes must decide the step")

    def test_throttling_is_turned_back_on_and_nginx_is_recreated_after_web(self):
        run = step("Rate limits still hold")["run"]
        self.assertIn("THROTTLING_ENABLED=true", run)
        self.assertLess(run.index("--force-recreate --no-deps --wait --wait-timeout 180 web"), run.index("frontend"))
        self.assertIn("throttle.js", run)

    def test_results_are_uploaded_even_when_the_run_fails_and_the_stack_is_always_torn_down(self):
        upload = next(s for s in job_steps() if "upload-artifact" in s.get("uses", ""))
        self.assertEqual(upload["if"], "always()")
        self.assertEqual(step("Tear down")["if"], "always()")
        self.assertEqual(step("Diagnostics")["if"], "failure()")

    def test_every_file_it_runs_exists(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        for rel in re.findall(r"\b((?:load/k6|scripts)/[\w./-]+\.(?:js|py))", text):
            self.assertTrue((ROOT / rel).exists(), rel)


class K6ScriptTests(SimpleTestCase):
    def test_check_comes_from_k6_not_a_made_up_module(self):
        self.assertIn('import { check } from "k6";', MAIN_JS)
        self.assertIn('import { check } from "k6";', THROTTLE_JS)

    def test_every_endpoint_tag_a_request_uses_has_a_latency_threshold(self):
        tags = set(re.findall(r'(?:get|post)\([^)]*?,\s*"(\w+)"\)', MAIN_JS)) | set(re.findall(r'tags: \{ endpoint: "(\w+)" \}', MAIN_JS))
        self.assertGreaterEqual(tags, {"catalog", "stats", "can_cook", "shopping", "ai_suggestions", "spa"})
        for tag in tags:
            declared = re.search(rf'"http_req_duration\{{endpoint:{tag}\}}"\]?\s*[:=]\s*\["p\(95\)<\d+"\]', MAIN_JS)  # literal or conditional assignment
            self.assertTrue(declared, f"no p95 threshold for endpoint:{tag}")

    def test_the_run_fails_on_errors_dropped_load_and_cross_session_leaks(self):
        for needle in ('http_req_failed: ["rate<', "checks: [", 'dropped_iterations: ["count<', 'isolation_violations: ["count==0"]'):
            self.assertIn(needle, MAIN_JS)

    def test_every_api_path_it_calls_is_a_real_route(self):
        paths = set(re.findall(r'"(/api/[\w/-]+/)"', MAIN_JS)) | set(re.findall(r"\$\{BASE\}(/api/[\w/-]+/)", MAIN_JS))
        self.assertGreaterEqual(len(paths), 7)
        for path in paths:
            resolve(path)  # raises Resolver404 if the route was renamed or removed

    def test_the_shopping_scenario_checks_ownership_and_cleans_up_after_itself(self):
        self.assertIn("isolationViolations.add", MAIN_JS)
        self.assertIn("/api/shopping-list/clear/", MAIN_JS)

    def test_the_throttle_script_demands_every_check_pass(self):
        self.assertIn('checks: ["rate==1"]', THROTTLE_JS)
        self.assertIn("Retry-After", THROTTLE_JS)
        self.assertIn("rate_limited", THROTTLE_JS)

    def test_the_throttle_script_attacks_the_ai_scope_it_names(self):
        from GetFood.rate_limits import DEFAULT_RATES

        self.assertIn("/api/ai/suggestions/", THROTTLE_JS)
        per_minute = int(DEFAULT_RATES["ai"].split("/")[0])
        attempts = int(re.search(r"i < (\d+)", THROTTLE_JS).group(1))
        self.assertGreater(attempts, per_minute, "too few attempts to ever exceed the ai scope's default rate")
