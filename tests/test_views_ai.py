"""API tests for the AI-facing views: scan upload hardening, provider/model discovery, suggestions
(cache layers + Celery/offline fallbacks), recipe detail/chat, SSE and task polling.

The AI layer itself is mocked at ``GetFood.views.*``; nothing here reaches the network.
"""
import base64
from datetime import timedelta
import os
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from GetFood import ai_cache
from GetFood.models import AISuggestionCache, Ingredient, UserPantry
from GetFood.views import _check_lmstudio_health

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "views-ai-tests"}}
GOOD = [{"name": "Shakshuka", "provider": "gemini"}]
DEGRADED = [{"name": "Plain Omelette", "provider": "fallback (AI offline)"}]
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 64


@override_settings(CACHES=LOCMEM)
class ApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()


# --------------------------------------------------------------------------- scan upload
class ScanImageTests(ApiTestCase):
    url = property(lambda self: reverse("api_pantry_scan_image"))

    def setUp(self):
        super().setUp()
        p = patch(
            "GetFood.views.scan_fridge_image",
            return_value=[{"name": "Egg", "category": "Dairy & Eggs"}, {"category": "no name"}],
        )
        self.scan = p.start()
        self.addCleanup(p.stop)

    def _upload(self, content=PNG_BYTES, content_type="image/png", **extra):
        f = SimpleUploadedFile("fridge.png", content, content_type=content_type)
        return self.client.post(self.url, {"image": f, **extra}, format="multipart")

    def test_no_image_is_a_400(self):
        r = self.client.post(self.url, {}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("image", r.data["error"])
        self.scan.assert_not_called()

    def test_oversized_upload_is_a_413_and_never_reaches_the_model(self):
        with patch.dict(os.environ, {"SCAN_MAX_BYTES": "100"}):
            r = self._upload(content=b"x" * 200)
        self.assertEqual(r.status_code, 413)
        self.scan.assert_not_called()

    def test_non_image_content_type_is_rejected(self):
        r = self._upload(content=b"x" * 64, content_type="text/plain")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Unsupported", r.data["error"])
        self.scan.assert_not_called()

    def test_empty_or_truncated_upload_is_rejected(self):
        r = self._upload(content=b"tiny")
        self.assertEqual(r.status_code, 400)
        self.assertIn("empty", r.data["error"])
        self.scan.assert_not_called()

    def test_valid_upload_passes_bytes_mime_and_language_to_the_scanner(self):
        r = self._upload(language="fa", provider="gemini")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["detected_count"], 2)
        self.assertFalse(r.data["auto_added"])
        self.assertEqual(self.scan.call_args.args[0], PNG_BYTES)
        self.assertEqual(self.scan.call_args.kwargs["mime_type"], "image/png")
        self.assertEqual(self.scan.call_args.kwargs["language"], "fa")

    def test_oversized_base64_is_a_413(self):
        with patch.dict(os.environ, {"SCAN_MAX_BYTES": "10"}):
            r = self.client.post(self.url, {"image_base64": "A" * 30}, format="json")
        self.assertEqual(r.status_code, 413)
        self.scan.assert_not_called()

    def test_base64_mime_is_taken_from_the_data_url_header(self):
        raw = base64.b64encode(PNG_BYTES).decode()
        for prefix, mime in (("data:image/png;base64,", "image/png"), ("data:image/webp;base64,", "image/webp"),
                             ("data:image/jpeg;base64,", "image/jpeg"), ("", "image/jpeg")):
            self.client.post(self.url, {"image_base64": prefix + raw}, format="json")
            self.assertEqual(self.scan.call_args.kwargs["mime_type"], mime, prefix)
            self.assertEqual(self.scan.call_args.args[0], PNG_BYTES)

    def test_auto_add_for_guests_goes_to_the_demo_pantry_only(self):
        real = User.objects.create_user("real", password="x" * 12)  # lowest id, must stay untouched
        demo = User.objects.create_user("ChefDemo", password="x" * 12)
        r = self.client.post(self.url, {"image_base64": base64.b64encode(PNG_BYTES).decode(), "auto_add": True}, format="json")
        self.assertEqual(r.data["added_ingredients"], ["Egg"])
        self.assertEqual([i.name for i in demo.userpantry.ingredients.all()], ["Egg"])
        self.assertFalse(UserPantry.objects.filter(user=real).exists())
        self.assertEqual(Ingredient.objects.get(name="Egg").category, "Dairy & Eggs")

    def test_auto_add_without_a_demo_account_adds_nothing(self):
        r = self.client.post(self.url, {"image_base64": base64.b64encode(PNG_BYTES).decode(), "auto_add": True}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["added_ingredients"], [])
        self.assertIsNone(r.data["pantry"])

    def test_auto_add_for_a_logged_in_user_returns_the_pantry(self):
        user = User.objects.create_user("cook", password="x" * 12)
        self.client.force_authenticate(user)
        r = self.client.post(self.url, {"image_base64": base64.b64encode(PNG_BYTES).decode(), "auto_add": True}, format="json")
        self.assertEqual(r.data["added_ingredients"], ["Egg"])
        self.assertEqual(r.data["pantry"]["ingredients"][0]["name"], "Egg")


# --------------------------------------------------------------------------- providers & models
class LmStudioHealthTests(TestCase):
    def test_online_picks_the_first_model_and_lists_all(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"data": [{"id": "llama"}, {"id": "qwen"}, {}]}
        with patch("GetFood.views.requests.get", return_value=resp):
            health = _check_lmstudio_health()
        self.assertTrue(health["online"])
        self.assertEqual((health["model"], health["available_models"]), ("llama", ["llama", "qwen"]))

    def test_online_without_models_reports_the_configured_one(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = {"data": []}
        with patch("GetFood.views.requests.get", return_value=resp):
            health = _check_lmstudio_health()
        self.assertTrue(health["online"])
        self.assertEqual(health["available_models"], [])

    def test_non_200_and_exceptions_mean_offline(self):
        with patch("GetFood.views.requests.get", side_effect=[MagicMock(status_code=500), requests.ConnectionError("x"),
                                                               requests.Timeout("y")]):
            health = _check_lmstudio_health()
        self.assertFalse(health["online"])
        self.assertIn("offline", health["error"])

    @override_settings(LMSTUDIO_URL="http://lm.internal:1234/v1/chat/completions")
    def test_configured_url_is_probed_last(self):
        with patch("GetFood.views.requests.get", side_effect=requests.ConnectionError("x")) as get:
            _check_lmstudio_health()
        self.assertEqual(get.call_args_list[-1].args[0], "http://lm.internal:1234/v1/models")


class ProvidersAndModelsTests(ApiTestCase):
    def test_providers_reflect_key_and_local_server_state(self):
        offline = {"online": False, "model": "m", "available_models": [], "error": "down"}
        with patch("GetFood.views._check_lmstudio_health", return_value=offline), \
                override_settings(GEMINI_API_KEY="k"):
            data = self.client.get(reverse("api_ai_providers")).data
        by_id = {p["id"]: p for p in data["providers"]}
        self.assertTrue(data["has_gemini"])
        self.assertTrue(by_id["gemini"]["online"])
        self.assertFalse(by_id["lmstudio"]["online"])
        self.assertEqual(by_id["lmstudio"]["badge"], "Offline (Not Running)")
        self.assertEqual(data["lmstudio_error"], "down")

    def test_providers_without_key_and_with_local_server_online(self):
        online = {"online": True, "model": "llama", "available_models": ["llama"], "url": "u"}
        with patch("GetFood.views._check_lmstudio_health", return_value=online), \
                override_settings(GEMINI_API_KEY=""), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            data = self.client.get(reverse("api_ai_providers")).data
        self.assertFalse(data["has_gemini"])
        self.assertEqual({p["id"]: p["badge"] for p in data["providers"]}["lmstudio"], "Offline Ready")

    def test_models_without_a_key_serve_the_curated_list(self):
        with override_settings(GEMINI_API_KEY=""), patch.dict(os.environ, {}, clear=False), \
                patch("GetFood.views.requests.get") as get:
            os.environ.pop("GEMINI_API_KEY", None)
            data = self.client.get(reverse("api_ai_models")).data
        get.assert_not_called()
        self.assertFalse(data["is_live"])
        self.assertTrue(data["models"])

    def test_live_models_prioritise_flash_and_drop_pro_and_special_purpose(self):
        listing = {"models": [
            {"name": "models/gemini-2.5-flash", "displayName": "Flash 2.5", "description": "d"},
            {"name": "models/gemini-3.5-flash-lite", "displayName": "Lite"},
            {"name": "models/gemini-2.5-pro", "displayName": "Pro"},
            {"name": "models/gemini-2.5-flash-preview-tts"},
            {"name": "models/gemini-embedding-001"},
            {"name": "models/gemini-2.5-flash-image"},
            {"name": "models/gemini-robotics-er"},
            {"name": "models/gemini-2.5-computer-use"},
            {"name": "models/palm-2"},
            {"name": "models/gemini-exp-1234", "displayName": "Experimental"},
        ]}
        resp = MagicMock(status_code=200)
        resp.json.return_value = listing
        with override_settings(GEMINI_API_KEY="k"), patch("GetFood.views.requests.get", return_value=resp):
            data = self.client.get(reverse("api_ai_models")).data
        ids = [m["id"] for m in data["models"]]
        self.assertTrue(data["is_live"])
        self.assertEqual(ids[0], "gemini-3.5-flash-lite")
        self.assertLess(ids.index("gemini-3.5-flash-lite"), ids.index("gemini-2.5-flash"))
        self.assertIn("gemini-exp-1234", ids)
        for banned in ("gemini-2.5-pro", "gemini-2.5-flash-preview-tts", "gemini-embedding-001", "gemini-2.5-flash-image",
                       "gemini-robotics-er", "gemini-2.5-computer-use", "palm-2"):
            self.assertNotIn(banned, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_models_endpoint_degrades_to_the_curated_list_on_google_errors(self):
        for kwargs in ({"return_value": MagicMock(status_code=503)}, {"side_effect": requests.Timeout("slow")}):
            with override_settings(GEMINI_API_KEY="k"), patch("GetFood.views.requests.get", **kwargs):
                data = self.client.get(reverse("api_ai_models")).data
            self.assertFalse(data["is_live"])
            self.assertTrue(data["models"])


# --------------------------------------------------------------------------- suggestions
class SuggestionsApiTests(ApiTestCase):
    url = property(lambda self: reverse("api_ai_suggestions"))

    def _gen(self, **kw):
        kw.setdefault("return_value", (GOOD, "gemini-x", ["gemini-y"]))
        p = patch("GetFood.views.generate_recipe_suggestions_meta", **kw)
        mock = p.start()
        self.addCleanup(p.stop)
        return mock

    def test_guest_get_uses_the_demo_pantry_and_forwards_provider_model_language(self):
        demo = User.objects.create_user("ChefDemo", password="x" * 12)
        UserPantry.objects.create(user=demo).ingredients.add(Ingredient.objects.create(name="Tomato"))
        gen = self._gen()
        data = self.client.get(self.url, {"provider": "gemini", "model": "m1", "language": "fa"}).data
        self.assertEqual(gen.call_args.args[0], ["Tomato"])
        self.assertEqual(gen.call_args.kwargs, {"provider": "gemini", "model": "m1", "language": "fa"})
        self.assertEqual((data["status"], data["cached"], data["model_used"]), ("done", False, "gemini-x"))
        self.assertEqual(data["rate_limited_models"], ["gemini-y"])

    def test_without_pantry_or_demo_user_sensible_defaults_are_used(self):
        gen = self._gen()
        self.client.get(self.url)
        self.assertIn("Tomato", gen.call_args.args[0])

    def test_empty_pantry_also_gets_defaults(self):
        user = User.objects.create_user("cook", password="x" * 12)
        UserPantry.objects.create(user=user)
        self.client.force_authenticate(user)
        gen = self._gen()
        self.client.get(self.url)
        self.assertIn("Pasta", gen.call_args.args[0])

    def test_custom_ingredients_are_trimmed_and_blank_ones_dropped(self):
        gen = self._gen()
        self.client.post(self.url, {"ingredients": [" Egg ", "", "  ", 7]}, format="json")
        self.assertEqual(gen.call_args.args[0], ["Egg", "7"])

    def test_good_answer_is_served_from_redis_then_from_the_db_and_force_refresh_bypasses(self):
        gen = self._gen()
        body = {"ingredients": ["Egg"]}
        first = self.client.post(self.url, body, format="json").data
        second = self.client.post(self.url, body, format="json").data  # Redis hot layer
        self.assertEqual((first["cached"], second["cached"]), (False, True))
        self.assertEqual(gen.call_count, 1)

        cache.clear()  # Redis flushed: the durable table still answers and re-warms Redis
        third = self.client.post(self.url, body, format="json").data
        self.assertTrue(third["cached"])
        self.assertEqual(gen.call_count, 1)
        self.assertEqual(AISuggestionCache.objects.count(), 1)

        self.client.post(self.url, {**body, "force_refresh": True}, format="json")
        self.assertEqual(gen.call_count, 2)

    def test_stale_db_cache_is_ignored(self):
        gen = self._gen()
        self.client.post(self.url, {"ingredients": ["Egg"]}, format="json")
        AISuggestionCache.objects.update(created_at=timezone.now() - timedelta(days=2))
        cache.clear()
        data = self.client.post(self.url, {"ingredients": ["Egg"]}, format="json").data
        self.assertFalse(data["cached"])
        self.assertEqual(gen.call_count, 2)

    def test_degraded_answer_is_returned_but_never_cached(self):
        self._gen(return_value=(DEGRADED, "fallback", []))
        data = self.client.post(self.url, {"ingredients": ["Egg"]}, format="json").data
        self.assertEqual(data["recipes"], DEGRADED)
        self.assertEqual(AISuggestionCache.objects.count(), 0)

    def test_generation_error_queues_a_celery_task_and_remembers_it(self):
        self._gen(side_effect=RuntimeError("provider exploded"))
        with patch("GetFood.views.generate_ai_suggestions_task.delay", return_value=MagicMock(id="task-1")) as delay:
            data = self.client.post(self.url, {"ingredients": ["Egg"], "provider": "gemini", "language": "es"}, format="json").data
        self.assertEqual(data, {"status": "processing", "task_id": "task-1"})
        args = delay.call_args.args
        self.assertEqual((args[0], args[2], args[3]), (["Egg"], "gemini", "es"))
        self.assertEqual(ai_cache.task_hash("task-1"), args[1])

    def test_broker_down_too_returns_the_safe_offline_recipes(self):
        self._gen(side_effect=RuntimeError("provider exploded"))
        with patch("GetFood.views.generate_ai_suggestions_task.delay", side_effect=OSError("rabbit down")), \
                patch("GetFood.views.generate_recipe_suggestions", return_value=DEGRADED) as fallback:
            r = self.client.post(self.url, {"ingredients": ["Egg"]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["recipes"], DEGRADED)
        self.assertEqual(r.data["model_used"], "fallback")
        self.assertEqual(fallback.call_args.kwargs["provider"], "fallback")
        self.assertEqual(AISuggestionCache.objects.count(), 0)


# --------------------------------------------------------------------------- detail, chat, stream
class RecipeDetailAndChatTests(ApiTestCase):
    def test_detail_success_forwards_query_params(self):
        with patch("GetFood.views.generate_recipe_detail_meta", return_value=({"name": "Soup"}, "m", [])) as gen:
            r = self.client.get(reverse("api_ai_recipe_detail", args=["Soup"]), {"provider": "gemini", "language": "tr"})
        self.assertEqual((r.status_code, r.data), (200, {"name": "Soup"}))
        self.assertEqual(gen.call_args.args[0], "Soup")
        self.assertEqual(gen.call_args.kwargs["language"], "tr")

    def test_detail_failure_is_a_500_with_an_error_key(self):
        with patch("GetFood.views.generate_recipe_detail_meta", side_effect=RuntimeError("boom")):
            r = self.client.get(reverse("api_ai_recipe_detail", args=["Soup"]))
        self.assertEqual(r.status_code, 500)
        self.assertIn("error", r.json())

    def test_chat_requires_a_message(self):
        for body in ({}, {"message": "   "}):
            r = self.client.post(reverse("api_recipe_chat"), body, format="json")
            self.assertEqual(r.status_code, 400)
            self.assertEqual(r.data["error"], "Message is required.")

    def test_chat_forwards_the_whole_context(self):
        result = {"reply": "Use butter", "model_used": "m", "rate_limited_models": [], "recipe_name": "Soup"}
        with patch("GetFood.views.ask_recipe_chat", return_value=result) as chat:
            r = self.client.post(reverse("api_recipe_chat"), {
                "recipe_name": "Soup", "ingredients": ["leek"], "instructions": "boil", "message": " swap oil? ",
                "history": [{"role": "user", "content": "hi"}], "provider": "gemini", "model": "m1", "language": "ar",
            }, format="json")
        self.assertEqual(r.data, result)
        kwargs = chat.call_args.kwargs
        self.assertEqual((kwargs["user_question"], kwargs["language"], kwargs["model"]), ("swap oil?", "ar", "m1"))
        self.assertEqual(kwargs["history"], [{"role": "user", "content": "hi"}])

    def test_chat_failure_returns_a_friendly_fallback_not_an_error(self):
        with patch("GetFood.views.ask_recipe_chat", side_effect=RuntimeError("quota")):
            r = self.client.post(reverse("api_recipe_chat"), {"recipe_name": "Soup", "message": "hi"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["model_used"], "fallback")
        self.assertIn("Soup", r.data["reply"])
        self.assertNotIn("quota", str(r.data))


class StreamEndpointTests(ApiTestCase):
    def test_sse_headers_and_body_are_streamed_through(self):
        frames = ['data: {"chunk": "Hi", "done": false}\n\n', 'data: {"chunk": "", "done": true}\n\n']
        with patch("GetFood.views.stream_recipe_generation", return_value=iter(frames)) as stream:
            r = self.client.get(reverse("api_ai_stream_recipe"), {"recipe": "Soup", "provider": "gemini", "language": "es"})
            body = b"".join(r.streaming_content).decode()
        self.assertEqual(r["Content-Type"], "text/event-stream")
        self.assertEqual(r["Cache-Control"], "no-cache")
        self.assertEqual(r["X-Accel-Buffering"], "no")
        self.assertEqual(body, "".join(frames))
        self.assertEqual(stream.call_args.args[0], "Soup")
        self.assertEqual(stream.call_args.kwargs, {"provider": "gemini", "language": "es"})

    def test_missing_recipe_param_has_a_default_dish_name(self):
        with patch("GetFood.views.stream_recipe_generation", return_value=iter([])) as stream:
            self.client.get(reverse("api_ai_stream_recipe"))
        self.assertTrue(stream.call_args.args[0])


# --------------------------------------------------------------------------- task polling
def _async_result(ready=True, failed=False, result=None):
    return MagicMock(ready=MagicMock(return_value=ready), failed=MagicMock(return_value=failed), result=result)


class TaskStatusTests(ApiTestCase):
    def _poll(self, res, task_id="t1"):
        with patch("celery.result.AsyncResult", return_value=res):
            return self.client.get(reverse("api_ai_task_status", kwargs={"task_id": task_id})).data

    def test_pending(self):
        self.assertEqual(self._poll(_async_result(ready=False)), {"status": "pending"})

    def test_task_result_carrying_recipes_wins(self):
        self.assertEqual(self._poll(_async_result(result={"recipes": GOOD})), {"status": "done", "recipes": GOOD})

    def test_result_without_recipes_uses_the_task_to_hash_mapping(self):
        ai_cache.remember_task("t1", "h1")
        ai_cache.set_suggestions("h1", GOOD)
        self.assertEqual(self._poll(_async_result(result="ok"))["recipes"], GOOD)

    def test_known_hash_falls_back_to_that_hashes_db_row_only(self):
        ai_cache.remember_task("t1", "h-mine")
        AISuggestionCache.objects.create(ingredients_hash="h-other", ai_response=[{"name": "Other"}])
        AISuggestionCache.objects.create(ingredients_hash="h-mine", ai_response=GOOD)
        self.assertEqual(self._poll(_async_result(result=None))["recipes"], GOOD)

    def test_unknown_task_uses_the_newest_recent_row(self):
        AISuggestionCache.objects.create(ingredients_hash="recent", ai_response=GOOD)
        self.assertEqual(self._poll(_async_result(result=None), task_id="evicted")["recipes"], GOOD)

    def test_nothing_anywhere_yields_an_empty_done(self):
        stale = AISuggestionCache.objects.create(ingredients_hash="old", ai_response=GOOD)
        AISuggestionCache.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=1))
        self.assertEqual(self._poll(_async_result(result=None)), {"status": "done", "recipes": []})
