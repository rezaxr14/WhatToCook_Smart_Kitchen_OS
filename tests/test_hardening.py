"""Privacy, error-handling and secure-defaults regression tests."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from GetFood import ai_cache
from GetFood.models import AISuggestionCache, Ingredient, UserPantry
from GetFood.tasks import cleanup_expired_ai_cache, generate_ai_suggestions_task

ROOT = Path(__file__).resolve().parent.parent
LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "hardening-tests"}}
DEGRADED = [{"name": "Plain Omelette", "provider": "fallback (AI offline)"}]
GOOD = [{"name": "Shakshuka", "provider": "gemini"}]


class GuestIsolationTests(TestCase):
    """Anonymous visitors act as the demo account, never as the first real user."""

    def setUp(self):
        self.client = APIClient()
        self.real = User.objects.create_user("first_real_user", password="x" * 12)  # lowest id on purpose
        self.demo = User.objects.create_user("ChefDemo", password="x" * 12)
        self.tomato = Ingredient.objects.create(name="Tomato")
        self.secret_item = Ingredient.objects.create(name="Truffle")
        UserPantry.objects.create(user=self.real).ingredients.add(self.secret_item)
        UserPantry.objects.create(user=self.demo).ingredients.add(self.tomato)

    def test_anonymous_pantry_is_the_demo_pantry(self):
        names = [i["name"] for i in self.client.get(reverse("api_pantry_get")).data["ingredients"]]
        self.assertEqual(names, ["Tomato"])

    def test_anonymous_writes_never_touch_a_real_users_pantry(self):
        self.client.post(reverse("api_pantry_add"), {"ingredient_id": self.tomato.id}, format="json")
        self.assertEqual(list(self.real.userpantry.ingredients.all()), [self.secret_item])

    def test_without_a_demo_account_anonymous_gets_an_empty_pantry(self):
        self.demo.delete()
        data = self.client.get(reverse("api_pantry_get")).data
        self.assertEqual(data["ingredients"], [])


@override_settings(CACHES=LOCMEM)
class AiFailureHandlingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_failed_task_reports_error_not_empty_success(self):
        failed = MagicMock(ready=MagicMock(return_value=True), failed=MagicMock(return_value=True), result=RuntimeError("boom"))
        with patch("celery.result.AsyncResult", return_value=failed):
            data = APIClient().get(reverse("api_ai_task_status", kwargs={"task_id": "t"})).data
        self.assertEqual(data["status"], "error")
        self.assertNotIn("boom", str(data))  # no exception text for anonymous pollers

    def test_degraded_suggestions_are_not_cached_by_the_task(self):
        with patch("GetFood.tasks.generate_recipe_suggestions", return_value=DEGRADED):
            generate_ai_suggestions_task.run(["egg"], "h-degraded")
        self.assertFalse(AISuggestionCache.objects.filter(ingredients_hash="h-degraded").exists())
        self.assertIsNone(ai_cache.get_suggestions("h-degraded"))

    def test_good_suggestions_are_cached_in_db_and_redis(self):
        with patch("GetFood.tasks.generate_recipe_suggestions", return_value=GOOD):
            generate_ai_suggestions_task.run(["egg"], "h-good")
        self.assertEqual(AISuggestionCache.objects.get(ingredients_hash="h-good").ai_response, GOOD)
        self.assertEqual(ai_cache.get_suggestions("h-good"), GOOD)

    def test_task_failure_never_overwrites_a_good_cached_answer(self):
        AISuggestionCache.objects.create(ingredients_hash="h-keep", ai_response=GOOD)
        with patch("GetFood.tasks.generate_recipe_suggestions", side_effect=RuntimeError("quota")):
            with self.assertRaises(RuntimeError):
                generate_ai_suggestions_task.run(["egg"], "h-keep")
        self.assertEqual(AISuggestionCache.objects.get(ingredients_hash="h-keep").ai_response, GOOD)

    def test_task_is_configured_to_retry_with_backoff(self):
        self.assertEqual(generate_ai_suggestions_task.max_retries, 3)
        self.assertTrue(generate_ai_suggestions_task.retry_backoff)

    def test_degraded_api_answer_is_not_cached(self):
        body = {"ingredients": ["Egg"], "provider": "fallback"}
        with patch("GetFood.views.generate_recipe_suggestions_meta", return_value=(DEGRADED, "fallback", [])) as gen:
            client = APIClient()
            client.post(reverse("api_ai_suggestions"), body, format="json")
            client.post(reverse("api_ai_suggestions"), body, format="json")
        self.assertEqual(gen.call_count, 2)
        self.assertEqual(AISuggestionCache.objects.count(), 0)


class CleanupTaskTests(TestCase):
    def test_only_rows_past_retention_are_deleted(self):
        old = AISuggestionCache.objects.create(ingredients_hash="old", ai_response=GOOD)
        fresh = AISuggestionCache.objects.create(ingredients_hash="fresh", ai_response=GOOD)
        AISuggestionCache.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=30))
        result = cleanup_expired_ai_cache()
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(list(AISuggestionCache.objects.values_list("pk", flat=True)), [fresh.pk])


class SecureDefaultsTests(TestCase):
    """The settings module must refuse to boot DEBUG=false on placeholder secrets."""

    def _boot(self, **env):
        base = {k: v for k, v in os.environ.items() if k not in ("SECRET_KEY", "DEBUG", "POSTGRES_PASSWORD", "ALLOWED_HOSTS")}
        base.update({"DJANGO_SETTINGS_MODULE": "WhatToCook.settings", "USE_POSTGRES": "false", **env})
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup(); print('BOOT-OK')"],
            cwd=ROOT, env=base, capture_output=True, text=True, timeout=60,
        )

    def test_prod_without_secret_key_is_refused(self):
        r = self._boot(DEBUG="false", ALLOWED_HOSTS="example.com")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("SECRET_KEY", r.stderr)

    def test_prod_with_placeholder_secret_key_is_refused(self):
        r = self._boot(DEBUG="false", ALLOWED_HOSTS="example.com", SECRET_KEY="change-me-to-a-long-random-string-0000")
        self.assertNotEqual(r.returncode, 0)

    def test_prod_with_real_secret_key_boots(self):
        r = self._boot(DEBUG="false", ALLOWED_HOSTS="example.com", SECRET_KEY="k" * 20 + "Zx9!" * 8)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("BOOT-OK", r.stdout)

    def test_debug_mode_keeps_the_dev_defaults(self):
        r = self._boot(DEBUG="true")
        self.assertEqual(r.returncode, 0, r.stderr)
