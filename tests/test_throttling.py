"""Rate limiting behaviour tests (429 shape, Retry-After, per-endpoint caps)."""

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

TEST_RATES = {"demo": "2/min", "ai": "1/min", "catalog": "5/min"}


def _rates():
    from django.conf import settings

    cfg = dict(settings.REST_FRAMEWORK)
    cfg["DEFAULT_THROTTLE_RATES"] = TEST_RATES
    return cfg


@override_settings(REST_FRAMEWORK=_rates())
class ThrottlingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _first_429(self, url: str, method: str = "post", max_attempts: int = 8):
        """POST until the endpoint answers 429; returns (attempt_index, response)."""
        for i in range(max_attempts):
            r = getattr(self.client, method)(url)
            if r.status_code == 429:
                return i, r
        self.fail(f"Endpoint {url} never throttled within {max_attempts} attempts")

    def test_demo_endpoint_429_with_retry_after(self):
        # Request #0 is anonymous (IP bucket); #1 establishes the session
        # (user bucket) -> the per-user 2/min cap trips on request #4.
        idx, r = self._first_429("/api/auth/demo/")
        self.assertEqual(idx, 3)
        body = r.json()
        self.assertEqual(body["error"], "rate_limited")
        self.assertIn("retry_after", body)
        self.assertTrue(int(r["Retry-After"]) >= 1)

    def test_health_probe_is_never_throttled(self):
        # /api/health has no throttle scope — probes must always pass.
        for _ in range(30):
            self.assertEqual(self.client.get("/api/health/").status_code, 200)

    def test_buckets_are_independent_per_scope(self):
        # Burning the "demo" bucket must not affect another scope.
        self._first_429("/api/auth/demo/")
        for _ in range(4):
            r = self.client.get("/api/ingredients/")
            self.assertEqual(r.status_code, 200)

    def test_error_body_is_consistent_json(self):
        idx, r = self._first_429("/api/auth/demo/")
        self.assertGreaterEqual(idx, 3)
        body = r.json()
        self.assertEqual(body["error"], "rate_limited")
        self.assertIsInstance(body["retry_after"], int)
        self.assertIsInstance(body["detail"], str)


class ThrottlingKillSwitchTests(TestCase):
    """THROTTLING_ENABLED=false (load tests, local debugging) must mean "never throttle", not "every scoped view 500s"."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _codes(self, n=8):
        return [self.client.get("/api/recipes/").status_code for _ in range(n)]  # catalog scope

    @override_settings(REST_FRAMEWORK=_rates(), THROTTLING_ENABLED=True)
    def test_control_the_same_rates_do_throttle_when_enabled(self):
        self.assertIn(429, self._codes())

    @override_settings(REST_FRAMEWORK=_rates(), THROTTLING_ENABLED=False)
    def test_disabled_scoped_endpoints_answer_200_and_never_429(self):
        self.assertEqual(set(self._codes()), {200})

    @override_settings(REST_FRAMEWORK=_rates(), THROTTLING_ENABLED=False)
    def test_disabled_also_covers_post_scopes(self):
        from django.contrib.auth.models import User

        from GetFood.views import DEMO_USERNAME

        User.objects.create_user(DEMO_USERNAME)  # the guest the anonymous pantry endpoints act as
        codes = {self.client.post("/api/pantry/add/", {"name": "salt"}, format="json").status_code for _ in range(8)}
        self.assertEqual(codes, {200})

    @override_settings(REST_FRAMEWORK=_rates(), THROTTLING_ENABLED=True)
    def test_a_scope_without_a_rate_is_a_loud_configuration_error_not_an_import_error(self):
        from django.core.exceptions import ImproperlyConfigured

        from GetFood.throttles import _throttle_class

        with self.assertRaisesMessage(ImproperlyConfigured, "No default throttle rate set for 'nonexistent'"):
            _throttle_class("nonexistent")()

    def test_the_environment_variable_reaches_the_setting_and_keeps_the_rate_table(self):
        """Settings are evaluated at import, so check them in a fresh process (without 'test' in argv)."""
        import json
        import os
        import subprocess
        import sys

        code = (
            "import json,django;django.setup();from django.conf import settings as s;"
            "print(json.dumps([s.THROTTLING_ENABLED, bool(s.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'])]))"
        )
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for value, expected in (("false", False), ("true", True), (None, True)):
            env = {**os.environ, "DJANGO_SETTINGS_MODULE": "WhatToCook.settings", "USE_POSTGRES": "false", "DEBUG": "true"}
            env.pop("THROTTLING_ENABLED", None)
            if value is not None:
                env["THROTTLING_ENABLED"] = value
            out = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout.strip().splitlines()[-1]), [expected, True], f"THROTTLING_ENABLED={value}")
