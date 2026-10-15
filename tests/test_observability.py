"""Request ids, JSON logs, /metrics, Celery routing/beat and the migration lock."""
import json
import logging
from io import StringIO
from unittest.mock import MagicMock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from GetFood.management.commands.bootstrap_db import LOCK_ID, advisory_lock
from WhatToCook.celery import app as celery_app
from WhatToCook.logging_utils import JsonFormatter, RequestIDFilter, request_id_var


class RequestIdTests(TestCase):
    def test_a_request_id_is_minted_when_absent(self):
        rid = self.client.get(reverse("api_health"))["X-Request-ID"]
        self.assertRegex(rid, r"^[0-9a-f]{32}$")

    def test_a_sane_incoming_id_is_propagated(self):
        response = self.client.get(reverse("api_health"), headers={"X-Request-ID": "ingress-abc123.42"})
        self.assertEqual(response["X-Request-ID"], "ingress-abc123.42")

    def test_a_hostile_incoming_id_is_replaced(self):
        response = self.client.get(reverse("api_health"), headers={"X-Request-ID": "bad id\r\nSet-Cookie: x=1"})
        self.assertRegex(response["X-Request-ID"], r"^[0-9a-f]{32}$")


class JsonLoggingTests(TestCase):
    def test_json_formatter_emits_one_object_with_request_id(self):
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RequestIDFilter())
        log = logging.getLogger("obs-test")
        log.addHandler(handler)
        log.propagate = False
        token = request_id_var.set("req-12345678")
        try:
            log.warning("pantry %s", "empty")
            try:
                1 / 0
            except ZeroDivisionError:
                log.exception("boom")
        finally:
            request_id_var.reset(token)
            log.removeHandler(handler)
        first, second = (json.loads(line) for line in stream.getvalue().splitlines() if line.startswith("{"))
        self.assertEqual((first["level"], first["msg"], first["request_id"]), ("WARNING", "pantry empty", "req-12345678"))
        self.assertIn("ZeroDivisionError", second["exc"])


class MetricsEndpointTests(TestCase):
    def test_metrics_are_exposed_in_prometheus_format(self):
        self.client.get(reverse("api_health"))
        response = self.client.get(reverse("metrics"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("django_http_requests_total_by_method_total", response.content.decode())

    @override_settings(METRICS_TOKEN="s3cret-token")
    def test_token_is_required_when_configured(self):
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 401)
        ok = self.client.get(reverse("metrics"), headers={"Authorization": "Bearer s3cret-token"})
        self.assertEqual(ok.status_code, 200)

    @override_settings(METRICS_ENABLED=False)
    def test_metrics_can_be_disabled(self):
        self.assertEqual(self.client.get(reverse("metrics")).status_code, 404)


class CeleryConfigTests(TestCase):
    def test_beat_schedule_points_at_registered_tasks(self):
        celery_app.loader.import_default_modules()
        schedule = celery_app.conf.beat_schedule
        self.assertIn("cleanup-expired-ai-cache", schedule)
        for entry in schedule.values():
            self.assertIn(entry["task"], celery_app.tasks)

    def test_tasks_are_routed_to_their_own_queues(self):
        routes = celery_app.conf.task_routes
        self.assertEqual(routes["GetFood.tasks.generate_ai_suggestions_task"]["queue"], "ai")
        self.assertEqual(routes["GetFood.tasks.cleanup_expired_ai_cache"]["queue"], "maintenance")

    def test_broker_and_result_backend_are_split(self):
        self.assertTrue(celery_app.conf.broker_url.startswith("amqp://"))
        self.assertTrue(celery_app.conf.result_backend.startswith("redis://"))


class BootstrapDbTests(TestCase):
    def test_postgres_takes_and_releases_the_lock_around_the_body(self):
        conn = MagicMock(vendor="postgresql")
        with advisory_lock(conn):
            conn.cursor.return_value.__enter__.return_value.execute.assert_called_once_with(
                "SELECT pg_advisory_lock(%s)", [LOCK_ID]
            )
        calls = [c.args for c in conn.cursor.return_value.__enter__.return_value.execute.call_args_list]
        self.assertEqual(calls[-1], ("SELECT pg_advisory_unlock(%s)", [LOCK_ID]))

    def test_lock_is_released_even_if_the_body_fails(self):
        conn = MagicMock(vendor="postgresql")
        with self.assertRaises(RuntimeError):
            with advisory_lock(conn):
                raise RuntimeError("migration failed")
        last = conn.cursor.return_value.__enter__.return_value.execute.call_args_list[-1].args
        self.assertIn("pg_advisory_unlock", last[0])

    def test_sqlite_needs_no_lock(self):
        conn = MagicMock(vendor="sqlite")
        with advisory_lock(conn):
            pass
        conn.cursor.assert_not_called()

    def test_command_runs_on_sqlite(self):
        out = StringIO()
        call_command("bootstrap_db", "--no-seed", stdout=out)
        self.assertIn("Applying database migrations", out.getvalue())
