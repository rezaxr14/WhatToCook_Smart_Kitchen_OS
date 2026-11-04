"""Tests for the adaptive AI challenge, daily caps, and gateway adapter (M2)."""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from GetFood import gateway_client
from GetFood.ai_guard import (
    ChallengeRequired,
    QuotaExceeded,
    begin_ai_call,
    challenge_state,
    reset_challenge,
    verify_turnstile,
)


def _request(user=None):
    request = RequestFactory().post("/")
    request.session = SessionStore()
    request.user = user or AnonymousUser()
    return request


class ChallengeAndCapTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(TURNSTILE_SECRET_KEY="", AI_ANON_DAILY_AI=2)
    def test_daily_cap_is_consumed_and_then_blocks(self):
        request = _request()
        begin_ai_call(request, "ai")
        begin_ai_call(request, "ai")
        with self.assertRaises(QuotaExceeded) as caught:
            begin_ai_call(request, "ai")
        self.assertEqual(caught.exception.error_code, "quota_exceeded")
        self.assertEqual(caught.exception.extra["limit"], 2)

    @override_settings(TURNSTILE_SECRET_KEY="", AI_ANON_DAILY_AI=0)
    def test_a_zero_cap_blocks_every_call(self):
        with self.assertRaises(QuotaExceeded):
            begin_ai_call(_request(), "ai")

    @override_settings(
        TURNSTILE_SECRET_KEY="secret",
        AI_CHALLENGE_EVERY_N=3,
        AI_ANON_DAILY_AI=100,
    )
    def test_step_up_after_n_calls_and_reset_after_verification(self):
        request = _request()
        for _ in range(3):
            begin_ai_call(request, "ai")
        with self.assertRaises(ChallengeRequired) as caught:
            begin_ai_call(request, "ai")
        self.assertEqual(caught.exception.error_code, "challenge_required")
        self.assertEqual(caught.exception.extra["kinds"], ["turnstile"])

        reset_challenge(request)
        self.assertEqual(challenge_state(request), 0)
        begin_ai_call(request, "ai")

    @override_settings(TURNSTILE_SECRET_KEY="secret", AI_ANON_DAILY_AI=0, AI_CHALLENGE_EVERY_N=1)
    def test_the_daily_cap_is_checked_before_the_challenge_slot(self):
        with self.assertRaises(QuotaExceeded):
            begin_ai_call(_request(), "ai")

    @override_settings(TURNSTILE_SECRET_KEY="", AI_USER_DAILY_AI=3, AI_ANON_DAILY_AI=1)
    def test_registered_accounts_get_their_own_larger_cap(self):
        user = User.objects.create_user(username="cook", password="pw")
        request = _request(user)
        for _ in range(3):
            begin_ai_call(request, "ai")
        with self.assertRaises(QuotaExceeded):
            begin_ai_call(request, "ai")

    @override_settings(TURNSTILE_SECRET_KEY="", AI_ANON_DAILY_SCAN=1)
    def test_scan_and_text_caps_are_separate(self):
        request = _request()
        begin_ai_call(request, "scan")
        with self.assertRaises(QuotaExceeded):
            begin_ai_call(request, "scan")
        begin_ai_call(request, "ai")  # still available

    @override_settings(TURNSTILE_SECRET_KEY="secret", AI_CHALLENGE_EVERY_N=2)
    def test_the_shared_demo_account_is_keyed_by_session(self):
        demo = User.objects.create_user(username="ChefDemo", password="pw")
        first = _request(demo)
        second = _request(demo)
        begin_ai_call(first, "ai")
        begin_ai_call(first, "ai")
        with self.assertRaises(ChallengeRequired):
            begin_ai_call(first, "ai")
        begin_ai_call(second, "ai")  # another visitor has their own counter


class TurnstileVerificationTests(TestCase):
    @override_settings(TURNSTILE_SECRET_KEY="")
    def test_not_configured(self):
        self.assertEqual(verify_turnstile("token"), (False, "not_configured"))

    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_missing_token(self):
        self.assertEqual(verify_turnstile(None), (False, "missing_token"))

    @override_settings(TURNSTILE_SECRET_KEY="secret", TURNSTILE_ACTION="ai_gate")
    def test_success_checks_action_and_hostname(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "success": True,
            "action": "ai_gate",
            "hostname": "whattocook.example",
        }
        with patch("GetFood.ai_guard.requests.post", return_value=response) as post:
            with override_settings(TURNSTILE_ALLOWED_HOSTNAMES=["whattocook.example"]):
                self.assertEqual(verify_turnstile("token", "1.2.3.4"), (True, None))
        self.assertEqual(post.call_args.args[0], "https://challenges.cloudflare.com/turnstile/v0/siteverify")

    @override_settings(
        TURNSTILE_SECRET_KEY="secret",
        TURNSTILE_ACTION="ai_gate",
        TURNSTILE_ALLOWED_HOSTNAMES=["whattocook.example"],
    )
    def test_wrong_hostname_is_rejected(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "success": True,
            "action": "ai_gate",
            "hostname": "evil.example",
        }
        with patch("GetFood.ai_guard.requests.post", return_value=response):
            self.assertEqual(verify_turnstile("token"), (False, "hostname_mismatch"))

    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_transport_failure_fails_closed(self):
        with patch("GetFood.ai_guard.requests.post", side_effect=RuntimeError("down")):
            self.assertEqual(verify_turnstile("token"), (False, "verification_unavailable"))


class ChallengeApiTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(TURNSTILE_SECRET_KEY="", TURNSTILE_SITE_KEY="")
    def test_get_reports_the_gate_as_disabled(self):
        response = self.client.get(reverse("api_auth_challenge"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["enabled"])
        self.assertEqual(response.json()["every_n"], 3)

    @override_settings(TURNSTILE_SECRET_KEY="secret", TURNSTILE_SITE_KEY="site-key")
    def test_get_exposes_the_site_key(self):
        data = self.client.get(reverse("api_auth_challenge")).json()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["site_key"], "site-key")

    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_post_without_a_token_is_a_403(self):
        response = self.client.post(reverse("api_auth_challenge"), {}, format="json")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "challenge_required")

    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_post_with_a_valid_token_resets_the_counter(self):
        with patch("GetFood.ai_guard.verify_turnstile", return_value=(True, None)):
            response = self.client.post(
                reverse("api_auth_challenge"), {"token": "t"}, format="json"
            )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["verified"])


class LoginChallengeTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="cook", password="pw")

    @override_settings(TURNSTILE_SECRET_KEY="secret")
    def test_login_without_a_token_is_blocked(self):
        with patch("GetFood.ai_guard.verify_turnstile", return_value=(False, "missing_token")):
            response = self.client.post(
                reverse("api_auth_login"),
                {"username": "cook", "password": "pw"},
                format="json",
            )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "challenge_required")

    @override_settings(TURNSTILE_SECRET_KEY="secret", AI_CHALLENGE_EVERY_N=3)
    def test_login_with_a_valid_token_clears_the_counter(self):
        with patch("GetFood.ai_guard.verify_turnstile", return_value=(True, None)):
            response = self.client.post(
                reverse("api_auth_login"),
                {"username": "cook", "password": "pw", "turnstile_token": "t"},
                format="json",
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(challenge_state(self._request_as("cook")), 0)

    def test_demo_login_is_also_gated_when_configured(self):
        with override_settings(TURNSTILE_SECRET_KEY="secret"):
            with patch("GetFood.ai_guard.verify_turnstile", return_value=(False, "missing_token")):
                response = self.client.post(reverse("api_auth_demo"), {}, format="json")
        self.assertEqual(response.status_code, 403)

    def _request_as(self, username):
        request = _request(User.objects.get(username=username))
        request.session = self.client.session
        return request


class GatewaySelectionTests(TestCase):
    def test_model_mapping(self):
        self.assertEqual(gateway_client._split_model("openrouter/free"), ("openrouter", "openrouter/free"))
        self.assertEqual(gateway_client._split_model("openrouter:meta/x"), ("openrouter", "meta/x"))
        self.assertEqual(gateway_client._split_model("gemini:gemini-2.5-flash"), ("gemini", "gemini-2.5-flash"))
        self.assertEqual(gateway_client._split_model("gemini-2.5-flash"), ("gemini", "gemini-2.5-flash"))
        self.assertEqual(gateway_client._split_model(""), (None, None))

    @override_settings(SUPABASE_GATEWAY_URL="https://gw.example/functions/v1/", MAIN_SERVICE_KEY="k" * 40)
    def test_suggestions_request_uses_the_service_principal(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {
            "recipes": [{"name": "Soup"}],
            "model_used": "gemini-x",
            "rate_limited_models": [],
        }
        with patch("GetFood.gateway_client.requests.post", return_value=response) as post:
            recipes, model, limited = gateway_client.generate_suggestions(
                ["tomato"],
                model="gemini:gemini-2.5-flash",
                language="fa",
                principal_class="registered",
                end_user_ref="u7",
            )
        self.assertEqual(recipes, [{"name": "Soup"}])
        self.assertEqual((model, limited), ("gemini-x", []))
        url = post.call_args.args[0]
        self.assertEqual(url, "https://gw.example/functions/v1/generate-recipe")
        self.assertEqual(post.call_args.kwargs["headers"]["X-Service-Key"], "k" * 40)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["principal_class"], "registered")
        self.assertEqual(body["end_user_ref"], "u7")
        self.assertEqual(body["locale"], "fa")
        self.assertEqual(body["provider"], "gemini")
        self.assertEqual(body["model"], "gemini-2.5-flash")

    @override_settings(SUPABASE_GATEWAY_URL="https://gw.example", MAIN_SERVICE_KEY="k" * 40)
    def test_blocking_gateway_errors_map_to_api_exceptions(self):
        response = MagicMock(status_code=403)
        response.json.return_value = {
            "code": "challenge_required",
            "message": "Verify",
            "kinds": ["turnstile"],
        }
        with patch("GetFood.gateway_client.requests.post", return_value=response):
            with self.assertRaises(gateway_client.GatewayError) as caught:
                gateway_client.generate_detail("Soup")
        mapped = gateway_client.to_api_exception(caught.exception)
        self.assertIsInstance(mapped, ChallengeRequired)
        self.assertEqual(mapped.extra["kinds"], ["turnstile"])

        pool = gateway_client.GatewayError(
            "ai_pool_exhausted", "No demo pool", resets_at="2026-01-01T00:00:00Z", pool="anonymous"
        )
        self.assertIsInstance(gateway_client.to_api_exception(pool), QuotaExceeded)

        provider = gateway_client.GatewayError("provider_error", "boom")
        self.assertIsNone(gateway_client.to_api_exception(provider))

    @override_settings(SUPABASE_GATEWAY_URL="https://gw.example", MAIN_SERVICE_KEY="k" * 40)
    def test_stream_reemits_ndjson_deltas_as_sse(self):
        response = MagicMock(status_code=200)
        response.iter_lines.return_value = [
            b'{"type":"delta","text":"Hello "}',
            b'{"type":"delta","text":"world"}',
            b'{"type":"final","data":{}}',
        ]
        with patch("GetFood.gateway_client.requests.post", return_value=response):
            frames = list(gateway_client.stream_recipe("Soup"))
        self.assertIn('"chunk": "Hello "', frames[0])
        self.assertIn('"chunk": "world"', frames[1])
        self.assertIn('"done": true', frames[2])
        response.close.assert_called_once()

    @override_settings(SUPABASE_GATEWAY_URL="", MAIN_SERVICE_KEY="")
    def test_not_configured_without_url_or_long_key(self):
        self.assertFalse(gateway_client.gateway_configured())
        with override_settings(SUPABASE_GATEWAY_URL="https://gw.example", MAIN_SERVICE_KEY="short"):
            self.assertFalse(gateway_client.gateway_configured())
