"""Redis (Django cache) integration: AI hot cache, task bookkeeping, health.

Uses a hermetic in-memory cache so the suite never needs a live Redis or
RabbitMQ; the code paths are identical because everything goes through
Django's cache framework.
"""
import json
from unittest.mock import MagicMock, patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from GetFood import ai_cache, ai_service
from GetFood.models import AISuggestionCache

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "redis-integration-tests"}}
RECIPES = [{"name": "Tomato Soup", "description": "Warm", "time_minutes": 20}]


@override_settings(CACHES=LOCMEM)
class SuggestionHotCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse("api_ai_suggestions")
        self.body = {"ingredients": ["Tomato", "Basil"], "provider": "fallback"}

    @patch("GetFood.views.generate_recipe_suggestions_meta", return_value=(RECIPES, "fallback", []))
    def test_second_call_is_served_from_redis_layer(self, gen):
        first = self.client.post(self.url, self.body, format="json")
        self.assertEqual(first.data["cached"], False)

        # Drop the durable copy: only the Redis layer can answer now.
        AISuggestionCache.objects.all().delete()
        second = self.client.post(self.url, self.body, format="json")

        self.assertEqual(second.data["cached"], True)
        self.assertEqual(second.data["recipes"], RECIPES)
        self.assertEqual(gen.call_count, 1)

    @patch("GetFood.views.generate_recipe_suggestions_meta", return_value=(RECIPES, "fallback", []))
    def test_db_hit_rewarms_redis(self, gen):
        self.client.post(self.url, self.body, format="json")
        cache.clear()  # simulate a Redis flush; the DB row survives

        again = self.client.post(self.url, self.body, format="json")
        self.assertEqual(again.data["cached"], True)
        self.assertEqual(gen.call_count, 1)

        row = AISuggestionCache.objects.get()
        self.assertEqual(ai_cache.get_suggestions(row.ingredients_hash), RECIPES)

    @patch("GetFood.views.generate_recipe_suggestions_meta", return_value=(RECIPES, "fallback", []))
    def test_force_refresh_bypasses_both_layers(self, gen):
        self.client.post(self.url, self.body, format="json")
        again = self.client.post(self.url, {**self.body, "force_refresh": True}, format="json")
        self.assertEqual(again.data["cached"], False)
        self.assertEqual(gen.call_count, 2)


@override_settings(CACHES=LOCMEM)
class TaskStatusTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def _status(self, task_id):
        done = MagicMock(ready=MagicMock(return_value=True))
        with patch("celery.result.AsyncResult", return_value=done):
            return self.client.get(reverse("api_ai_task_status", kwargs={"task_id": task_id}))

    def test_status_returns_the_tasks_own_result_not_the_newest_row(self):
        mine = [{"name": "Mine"}]
        AISuggestionCache.objects.create(ingredients_hash="hash-mine", ai_response=mine, created_at=timezone.now())
        AISuggestionCache.objects.create(ingredients_hash="hash-other", ai_response=[{"name": "Newer, someone else's"}])
        ai_cache.remember_task("task-1", "hash-mine")

        response = self._status("task-1")
        self.assertEqual(response.data, {"status": "done", "recipes": mine})

    def test_status_prefers_redis_result(self):
        ai_cache.remember_task("task-2", "hash-hot")
        ai_cache.set_suggestions("hash-hot", RECIPES)
        self.assertEqual(self._status("task-2").data["recipes"], RECIPES)

    def test_unknown_task_keeps_legacy_fallback(self):
        AISuggestionCache.objects.create(ingredients_hash="whatever", ai_response=RECIPES)
        self.assertEqual(self._status("never-seen").data["recipes"], RECIPES)


@override_settings(CACHES=LOCMEM)
class RecipeDetailCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.detail = {"name": "Soup", "ingredients": [{"name": "Tomato", "amount": "2", "unit": "pcs"}], "instructions": []}

    def test_real_ai_answers_are_cached(self):
        with patch.object(ai_service, "_call_gemini_with_meta", return_value=(json.dumps(self.detail), "gemini-x", [])) as call:
            first, _, _ = ai_service.generate_recipe_detail_meta("Soup", provider="gemini")
            second, model_used, _ = ai_service.generate_recipe_detail_meta("  SOUP ", provider="gemini")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(first["name"], second["name"])
        self.assertEqual(model_used, "gemini-x")

    def test_fallback_answers_are_never_cached(self):
        with patch.object(ai_service, "_call_gemini_with_meta", side_effect=RuntimeError("quota")) as call:
            ai_service.generate_recipe_detail_meta("Soup", provider="gemini")
            ai_service.generate_recipe_detail_meta("Soup", provider="gemini")
        self.assertEqual(call.call_count, 2)

    def test_key_separates_language_and_provider(self):
        a = ai_cache.detail_key("Soup", "gemini", None, "tr")
        self.assertNotEqual(a, ai_cache.detail_key("Soup", "gemini", None, "es"))
        self.assertNotEqual(a, ai_cache.detail_key("Soup", "lmstudio", None, "tr"))


class CacheOutageTests(TestCase):
    def test_backend_errors_behave_like_a_miss(self):
        with patch.object(ai_cache.cache, "get", side_effect=ConnectionError("redis down")), \
                patch.object(ai_cache.cache, "set", side_effect=ConnectionError("redis down")):
            self.assertIsNone(ai_cache.get_suggestions("x"))
            ai_cache.set_suggestions("x", RECIPES)  # must not raise
            self.assertIsNone(ai_cache.task_hash("t"))


@override_settings(CACHES=LOCMEM)
class HealthBrokerTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_broker_check_is_skipped_by_default_in_tests(self):
        data = self.client.get(reverse("api_health")).data
        self.assertEqual(data["checks"]["broker"], "skipped")

    @override_settings(HEALTH_CHECK_BROKER=True)
    def test_unreachable_broker_degrades_but_stays_healthy(self):
        with patch("WhatToCook.celery.app.connection_for_read", side_effect=OSError("no rabbit")):
            response = self.client.get(reverse("api_health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["checks"]["broker"], "degraded")
        self.assertEqual(response.data["status"], "ok")

    @override_settings(HEALTH_CHECK_BROKER=True)
    def test_reachable_broker_reports_ok(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        with patch("WhatToCook.celery.app.connection_for_read", return_value=conn):
            data = self.client.get(reverse("api_health")).data
        self.assertEqual(data["checks"]["broker"], "ok")
