"""Unit tests for ``GetFood.ai_service``: provider selection, quota/fallback branches,
JSON salvage, streaming and the sous-chef chat.

No test here talks to the network: ``requests.post``/``requests.get`` are replaced for every
test (a bare ``ConnectionError`` unless the test supplies a response) and the Gemini SDK is a
mock injected as ``google.genai.Client``.
"""
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings

from GetFood import ai_service
from GetFood.ai_service import (
    AI_RESPONSE_LANGUAGES,
    GEMINI_FALLBACK_MODELS,
    _apply_language,
    _call_gemini,
    _call_gemini_vision,
    _call_gemini_with_meta,
    _call_lmstudio,
    _clean_json_str,
    _is_rate_limit_error,
    _language_instruction,
    ask_recipe_chat,
    generate_recipe_detail,
    generate_recipe_detail_meta,
    generate_recipe_suggestions,
    generate_recipe_suggestions_meta,
    normalize_language,
    scan_fridge_image,
    stream_recipe_generation,
)

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "ai-service-tests"}}
IMG = b"\xff\xd8\xff" + b"0" * 64  # not a real JPEG; every provider call is mocked


def _rest_ok(text):
    """A 200 response in the shape of generativelanguage.googleapis.com."""
    resp = MagicMock(status_code=200, text="ok")
    resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return resp


def _rest_status(code, body=""):
    return MagicMock(status_code=code, text=body)


class NoNetworkMixin:
    """Every test starts with HTTP stubbed to fail, a fake API key and (by default) the SDK unavailable."""

    block_sdk = True  # GeminiSdkTests turns this off and injects a mock ``google.genai.Client`` instead

    def setUp(self):
        super().setUp()
        self.post = self._patch("GetFood.ai_service.requests.post", side_effect=requests.ConnectionError("offline"))
        self._patch("GetFood.ai_service.GEMINI_API_KEY", "test-key")
        self._patch("GetFood.ai_service.GEMINI_MODEL", "gemini-3.5-flash-lite")
        if self.block_sdk:
            # sys.modules["google"] = None makes ``from google import genai`` raise ImportError -> REST path.
            # Only this one key is saved/restored (patch.dict would snapshot the whole module table).
            missing = object()
            saved = sys.modules.get("google", missing)
            sys.modules["google"] = None
            self.addCleanup(lambda: sys.modules.__setitem__("google", saved) if saved is not missing else sys.modules.pop("google", None))

    def _patch(self, target, *args, **kwargs):
        p = patch(target, *args, **kwargs)
        mock = p.start()
        self.addCleanup(p.stop)
        return mock


# --------------------------------------------------------------------------- pure helpers
class HelperTests(SimpleTestCase):
    def test_rate_limit_detection(self):
        for msg in ("429 Too Many Requests", "Quota exceeded", "RESOURCE_EXHAUSTED", "ResourceExhausted",
                    "rate limit hit", "RateLimit", "You exceeded your current quota", "too many requests"):
            self.assertTrue(_is_rate_limit_error(msg), msg)
        self.assertFalse(_is_rate_limit_error("500 internal error"))
        self.assertFalse(_is_rate_limit_error(""))

    def test_normalize_language(self):
        self.assertEqual(normalize_language("fa-IR"), "fa")
        self.assertEqual(normalize_language(" EN-us "), "en")
        self.assertIsNone(normalize_language("xx"))
        self.assertIsNone(normalize_language(""))
        self.assertIsNone(normalize_language(None))

    def test_language_instruction_only_for_non_english(self):
        self.assertEqual(_language_instruction(None), "")
        self.assertEqual(_language_instruction("en"), "")
        self.assertEqual(_language_instruction("zz"), "")
        for code, name in AI_RESPONSE_LANGUAGES.items():
            if code != "en":
                self.assertIn(name, _language_instruction(code))

    def test_apply_language_merges_and_skips_blanks(self):
        merged = _apply_language("Be a chef.", "es")
        self.assertTrue(merged.startswith("Be a chef."))
        self.assertIn("Spanish", merged)
        self.assertEqual(_apply_language("Be a chef.", "en"), "Be a chef.")
        self.assertEqual(_apply_language("", "en"), "")

    def test_clean_json_str_strips_markdown_fences(self):
        self.assertEqual(_clean_json_str('```json\n[{"a": 1}]\n```'), '[{"a": 1}]')
        self.assertEqual(_clean_json_str("```\n{}\n```"), "{}")
        self.assertEqual(_clean_json_str('  {"a": 1}  '), '{"a": 1}')

    def test_fallback_data_is_well_formed(self):
        suggestions = ai_service._fallback_recipe_suggestions(["egg", "milk"])
        self.assertGreaterEqual(len(suggestions), 4)
        self.assertTrue(all({"name", "short_description", "prep_time"} <= set(s) for s in suggestions))
        scan = ai_service._fallback_fridge_scan()
        self.assertTrue(all({"name", "category", "confidence"} <= set(i) for i in scan))


# --------------------------------------------------------------------------- Gemini text
class GeminiSdkTests(NoNetworkMixin, SimpleTestCase):
    """The google-genai SDK path (mocked Client)."""

    block_sdk = False

    def setUp(self):
        super().setUp()
        self.client = MagicMock()
        self.client_cls = self._patch("google.genai.Client", return_value=self.client)

    def test_first_candidate_wins_and_text_is_stripped(self):
        self.client.models.generate_content.return_value = SimpleNamespace(text="  hello  ")
        text, model, limited = _call_gemini_with_meta("hi", system_instruction="sys", model="my-model")
        self.assertEqual((text, model, limited), ("hello", "my-model", []))
        self.assertEqual(self.client.models.generate_content.call_args.kwargs["model"], "my-model")
        self.post.assert_not_called()

    def test_candidate_order_is_explicit_then_default_then_fallbacks_without_duplicates(self):
        self.client.models.generate_content.side_effect = RuntimeError("boom")
        with patch("GetFood.ai_service.requests.post", return_value=_rest_status(500)):
            with self.assertRaises(ValueError):
                _call_gemini_with_meta("hi", model="custom-x")
        tried = [c.kwargs["model"] for c in self.client.models.generate_content.call_args_list]
        self.assertEqual(tried[0], "custom-x")
        self.assertEqual(tried[1], "gemini-3.5-flash-lite")  # GEMINI_MODEL is next, not repeated later
        self.assertEqual(len(tried), len(set(tried)))
        self.assertEqual(set(tried), {"custom-x", *GEMINI_FALLBACK_MODELS})

    def test_quota_error_moves_to_next_model_and_is_reported(self):
        self.client.models.generate_content.side_effect = [
            RuntimeError("429 RESOURCE_EXHAUSTED quota"),
            RuntimeError("503 unavailable"),  # non-quota failure: skipped but not reported as limited
            SimpleNamespace(text="recovered"),
        ]
        text, model, limited = _call_gemini_with_meta("hi")
        self.assertEqual(text, "recovered")
        self.assertEqual(limited, ["gemini-3.5-flash-lite"])
        self.assertEqual(model, GEMINI_FALLBACK_MODELS[2])

    def test_empty_sdk_text_counts_as_a_miss(self):
        self.client.models.generate_content.side_effect = [SimpleNamespace(text=""), SimpleNamespace(text="second")]
        text, model, _ = _call_gemini_with_meta("hi")
        self.assertEqual(text, "second")
        self.assertEqual(model, GEMINI_FALLBACK_MODELS[1])

    def test_blank_mime_type_and_system_instruction_are_omitted(self):
        self.client.models.generate_content.return_value = SimpleNamespace(text="plain")
        _call_gemini_with_meta("hi", response_mime_type="")
        config = self.client.models.generate_content.call_args.kwargs["config"]
        self.assertIsNone(config.response_mime_type)
        self.assertIsNone(config.system_instruction)

    def test_vision_sdk_success(self):
        self.client.models.generate_content.return_value = SimpleNamespace(text=" [] ")
        self.assertEqual(_call_gemini_vision("what is this", IMG, mime_type="image/png"), "[]")

    def test_vision_sdk_failures_fall_through_to_rest(self):
        self.client.models.generate_content.side_effect = RuntimeError("sdk down")
        with patch("GetFood.ai_service.requests.post", return_value=_rest_ok("from rest")) as post:
            self.assertEqual(_call_gemini_vision("p", IMG), "from rest")
        self.assertEqual(post.call_count, 1)


class GeminiRestTests(NoNetworkMixin, SimpleTestCase):
    """SDK unavailable (ImportError) -> REST fallback with the same model list."""

    def test_missing_api_key_is_a_clear_error(self):
        with patch("GetFood.ai_service.GEMINI_API_KEY", ""), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            with self.assertRaisesMessage(ValueError, "GEMINI_API_KEY"):
                _call_gemini_with_meta("hi")
            with self.assertRaisesMessage(ValueError, "GEMINI_API_KEY"):
                _call_gemini_vision("hi", IMG)
        self.post.assert_not_called()

    def test_api_key_can_come_from_the_environment(self):
        with patch("GetFood.ai_service.GEMINI_API_KEY", ""), patch.dict(os.environ, {"GEMINI_API_KEY": "env-key"}):
            self.post.side_effect = None
            self.post.return_value = _rest_ok("ok")
            _call_gemini_with_meta("hi")
        self.assertIn("key=env-key", self.post.call_args.args[0])

    def test_success_builds_the_expected_request(self):
        self.post.side_effect = None
        self.post.return_value = _rest_ok("  tasty  ")
        text, model, limited = _call_gemini_with_meta("cook", system_instruction="be brief", model="m1")
        self.assertEqual((text, model, limited), ("tasty", "m1", []))
        url = self.post.call_args.args[0]
        payload = self.post.call_args.kwargs["json"]
        self.assertIn("/models/m1:generateContent", url)
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "cook")
        self.assertEqual(payload["systemInstruction"]["parts"][0]["text"], "be brief")
        self.assertEqual(payload["generationConfig"]["responseMimeType"], "application/json")

    def test_rest_without_system_instruction_or_mime_omits_both(self):
        self.post.side_effect = None
        self.post.return_value = _rest_ok("x")
        _call_gemini_with_meta("cook", response_mime_type="")
        payload = self.post.call_args.kwargs["json"]
        self.assertNotIn("systemInstruction", payload)
        self.assertNotIn("responseMimeType", payload["generationConfig"])

    def test_429_and_quota_text_are_tracked_then_next_model_is_tried(self):
        self.post.side_effect = [
            _rest_status(429),
            _rest_status(400, "You exceeded your current quota"),
            _rest_status(500, "server exploded"),
            _rest_ok("finally"),
        ]
        text, model, limited = _call_gemini_with_meta("hi")
        self.assertEqual(text, "finally")
        self.assertEqual(limited, ["gemini-3.5-flash-lite", GEMINI_FALLBACK_MODELS[1]])
        self.assertEqual(model, GEMINI_FALLBACK_MODELS[3])

    def test_200_without_candidates_or_text_is_skipped(self):
        empty = MagicMock(status_code=200, text="{}")
        empty.json.return_value = {"candidates": []}
        blank = _rest_ok("   ")
        self.post.side_effect = [empty, blank, _rest_ok("real")]
        text, _, _ = _call_gemini_with_meta("hi")
        self.assertEqual(text, "real")

    def test_exceptions_are_swallowed_per_model_and_quota_ones_recorded(self):
        self.post.side_effect = [requests.Timeout("429 slow"), requests.ConnectionError("down"), _rest_ok("ok")]
        text, _, limited = _call_gemini_with_meta("hi")
        self.assertEqual(text, "ok")
        self.assertEqual(limited, ["gemini-3.5-flash-lite"])

    def test_all_models_failing_raises_with_the_last_error(self):
        self.post.side_effect = requests.ConnectionError("network unreachable")
        with self.assertRaises(ValueError) as ctx:
            _call_gemini_with_meta("hi")
        self.assertIn("All Gemini models failed", str(ctx.exception))
        self.assertIn("network unreachable", str(ctx.exception))
        self.assertEqual(self.post.call_count, len(set(["gemini-3.5-flash-lite", *GEMINI_FALLBACK_MODELS])))

    def test_wrapper_returns_only_the_text(self):
        self.post.side_effect = None
        self.post.return_value = _rest_ok("just text")
        self.assertEqual(_call_gemini("hi"), "just text")

    def test_vision_rest_success_encodes_the_image(self):
        self.post.side_effect = None
        self.post.return_value = _rest_ok("[]")
        self.assertEqual(_call_gemini_vision("look", IMG, mime_type="image/webp", system_instruction="sys"), "[]")
        payload = self.post.call_args.kwargs["json"]
        inline = payload["contents"][0]["parts"][1]["inline_data"]
        self.assertEqual(inline["mime_type"], "image/webp")
        self.assertTrue(inline["data"])
        self.assertIn("systemInstruction", payload)

    def test_vision_requires_image_bytes(self):
        with self.assertRaisesMessage(ValueError, "No image data"):
            _call_gemini_vision("look", b"")

    def test_vision_non_200_and_exceptions_are_skipped_then_raise(self):
        self.post.side_effect = [_rest_status(500), requests.ConnectionError("x")] + [_rest_status(503)] * 20
        with self.assertRaisesMessage(ValueError, "All Gemini vision models failed"):
            _call_gemini_vision("look", IMG)

    def test_vision_200_without_text_is_skipped(self):
        empty = MagicMock(status_code=200, text="{}")
        empty.json.return_value = {"candidates": []}
        self.post.side_effect = [empty, _rest_ok("found")]
        self.assertEqual(_call_gemini_vision("look", IMG), "found")


# --------------------------------------------------------------------------- LM Studio
class LmStudioTests(NoNetworkMixin, SimpleTestCase):
    def _response(self, payload, error=None):
        resp = MagicMock()
        resp.json.return_value = payload
        resp.raise_for_status.side_effect = error
        return resp

    def test_success_sends_system_and_user_messages(self):
        self.post.side_effect = None
        self.post.return_value = self._response({"choices": [{"message": {"content": "  local answer "}}]})
        self.assertEqual(_call_lmstudio("hi", system_instruction="sys"), "local answer")
        messages = self.post.call_args.kwargs["json"]["messages"]
        self.assertEqual([m["role"] for m in messages], ["system", "user"])

    def test_no_system_message_when_blank(self):
        self.post.side_effect = None
        self.post.return_value = self._response({"choices": [{"message": {"content": "x"}}]})
        _call_lmstudio("hi")
        self.assertEqual([m["role"] for m in self.post.call_args.kwargs["json"]["messages"]], ["user"])

    def test_empty_choices_yield_empty_string(self):
        self.post.side_effect = None
        self.post.return_value = self._response({"choices": []})
        self.assertEqual(_call_lmstudio("hi"), "")

    def test_http_errors_propagate_to_the_caller(self):
        self.post.side_effect = None
        self.post.return_value = self._response({}, error=requests.HTTPError("502"))
        with self.assertRaises(requests.HTTPError):
            _call_lmstudio("hi")


# --------------------------------------------------------------------------- suggestions
SUGGESTION = {"name": "Shakshuka", "short_description": "eggs in sauce", "cuisine": "Levantine", "difficulty": "Easy"}


class SuggestionTests(NoNetworkMixin, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.gemini = self._patch("GetFood.ai_service._call_gemini_with_meta")
        self.lm = self._patch("GetFood.ai_service._call_lmstudio")

    def test_gemini_json_array_is_decorated_with_image_and_provider(self):
        self.gemini.return_value = (json.dumps([SUGGESTION]), "gemini-x", ["gemini-y"])
        recipes, model, limited = generate_recipe_suggestions_meta(["egg"], provider="gemini", language="tr")
        self.assertEqual((model, limited), ("gemini-x", ["gemini-y"]))
        self.assertEqual(recipes[0]["provider"], "gemini")
        self.assertEqual(recipes[0]["model_used"], "gemini-x")
        self.assertTrue(recipes[0]["image"])
        self.assertIn("Turkish", self.gemini.call_args.args[1])  # language directive reached the system prompt

    def test_markdown_fenced_and_wrapped_shapes_are_unwrapped(self):
        for wrapper in ({"dishes": [SUGGESTION]}, {"recipes": [SUGGESTION]}):
            self.gemini.return_value = ("```json\n" + json.dumps(wrapper) + "\n```", "m", [])
            recipes, _, _ = generate_recipe_suggestions_meta(["egg"], provider="gemini")
            self.assertEqual([r["name"] for r in recipes], ["Shakshuka"])

    def test_malformed_json_is_salvaged_object_by_object(self):
        broken = '[{"name": "A", "x": 1}, {"name": "B"}, {"nope": 1}, {"name": ] garbage'
        self.gemini.return_value = (broken, "m", [])
        recipes, _, _ = generate_recipe_suggestions_meta(["egg"], provider="gemini")
        self.assertEqual([r["name"] for r in recipes], ["A", "B"])

    def test_unusable_output_falls_back_to_presets_marked_offline(self):
        for content in ("", "no json at all", "{}", '"just a string"'):
            self.gemini.return_value = (content, "m", [])
            recipes, _, _ = generate_recipe_suggestions_meta(["egg", "milk"], provider="gemini")
            self.assertGreaterEqual(len(recipes), 4, content)
            self.assertTrue(all(r["provider"] == "fallback (AI offline)" for r in recipes), content)

    def test_provider_exception_falls_back_and_marks_offline(self):
        self.gemini.side_effect = ValueError("All Gemini models failed")
        recipes, model, limited = generate_recipe_suggestions_meta(["egg"], provider="gemini")
        self.assertTrue(all(r["provider"] == "fallback (AI offline)" for r in recipes))
        self.assertEqual(limited, [])
        self.assertEqual(model, "gemini-3.5-flash-lite")

    def test_lmstudio_provider_uses_the_local_model(self):
        self.lm.return_value = json.dumps([SUGGESTION])
        recipes, model, _ = generate_recipe_suggestions_meta(["egg"], provider="lmstudio")
        self.assertEqual(model, ai_service.MODEL_NAME)
        self.assertEqual(recipes[0]["provider"], "lmstudio")
        self.gemini.assert_not_called()

    def test_unknown_provider_tries_gemini_then_lmstudio(self):
        self.gemini.side_effect = ValueError("no key")
        self.lm.return_value = json.dumps([SUGGESTION])
        recipes, model, _ = generate_recipe_suggestions_meta(["egg"], provider="auto")
        self.assertEqual(recipes[0]["name"], "Shakshuka")
        self.assertEqual(model, ai_service.MODEL_NAME)

    def test_unknown_provider_with_both_down_uses_the_fallback(self):
        self.gemini.side_effect = ValueError("no key")
        self.lm.side_effect = requests.ConnectionError("lm studio offline")
        recipes, _, _ = generate_recipe_suggestions_meta(["egg"], provider="auto")
        self.assertTrue(all(r["provider"] == "fallback (AI offline)" for r in recipes))

    def test_default_provider_comes_from_settings(self):
        self.gemini.return_value = (json.dumps([SUGGESTION]), "m", [])
        with patch("GetFood.ai_service.DEFAULT_AI_PROVIDER", "gemini"):
            recipes = generate_recipe_suggestions(["egg"])  # compat wrapper returns just the list
        self.assertEqual(recipes[0]["provider"], "gemini")


# --------------------------------------------------------------------------- recipe detail
DETAIL = {"name": "Soup", "ingredients": [{"name": "water", "amount": "1", "unit": "l"}], "instructions": []}


@override_settings(CACHES=LOCMEM)
class RecipeDetailTests(NoNetworkMixin, TestCase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.gemini = self._patch("GetFood.ai_service._call_gemini_with_meta")
        self.lm = self._patch("GetFood.ai_service._call_lmstudio")

    def test_real_answer_is_returned_and_cached_for_the_next_call(self):
        self.gemini.return_value = (json.dumps(DETAIL), "gemini-x", ["gemini-y"])
        data, model, limited = generate_recipe_detail_meta("Soup", provider="gemini")
        self.assertEqual((model, limited), ("gemini-x", ["gemini-y"]))
        self.assertEqual(data["provider"], "gemini")
        self.assertTrue(data["image"])

        again, model2, limited2 = generate_recipe_detail_meta("Soup", provider="gemini")
        self.assertEqual(self.gemini.call_count, 1)  # served from the cache
        self.assertEqual((again["name"], model2, limited2), ("Soup", "gemini-x", ["gemini-y"]))

    def test_cache_is_scoped_by_language(self):
        self.gemini.return_value = (json.dumps(DETAIL), "m", [])
        generate_recipe_detail_meta("Soup", provider="gemini", language="fa")
        generate_recipe_detail_meta("Soup", provider="gemini", language="es")
        self.assertEqual(self.gemini.call_count, 2)
        self.assertIn("Persian", self.gemini.call_args_list[0].args[1])

    def test_degraded_answer_is_never_cached(self):
        self.gemini.side_effect = ValueError("quota")
        first, _, _ = generate_recipe_detail_meta("Soup", provider="gemini")
        second, _, _ = generate_recipe_detail_meta("Soup", provider="gemini")
        self.assertEqual(self.gemini.call_count, 2)  # the second call re-tried the provider
        self.assertEqual(first["cuisine"], "Gourmet")
        self.assertTrue(first["ingredients"] and first["instructions"] and first["nutrition"])
        self.assertEqual(second["name"], "Soup")

    def test_unusable_json_or_missing_ingredients_triggers_the_fallback_recipe(self):
        for content in ("not json", json.dumps({"name": "Soup"}), json.dumps([1, 2]), "null"):
            cache.clear()
            self.gemini.return_value = (content, "m", [])
            data, _, _ = generate_recipe_detail_meta("Soup", provider="gemini")
            self.assertEqual(data["cuisine"], "Gourmet", content)

    def test_escaped_json_is_recovered_through_the_unicode_escape_path(self):
        escaped = '{"name": "Soup", "ingredients": [{"name": "a"}], "bad": "\\\\u00e9" , }'
        self.gemini.return_value = (escaped, "m", [])
        data, _, _ = generate_recipe_detail_meta("Soup", provider="gemini")
        self.assertIn("ingredients", data)  # either recovered or the fallback; never an exception

    def test_lmstudio_and_auto_provider_paths(self):
        self.lm.return_value = json.dumps(DETAIL)
        data, model, _ = generate_recipe_detail_meta("Soup", provider="lmstudio")
        self.assertEqual(model, ai_service.MODEL_NAME)
        self.assertEqual(data["provider"], "lmstudio")

        cache.clear()
        self.gemini.side_effect = ValueError("no key")
        data, model, _ = generate_recipe_detail_meta("Soup", provider="auto")
        self.assertEqual(model, ai_service.MODEL_NAME)

    def test_both_providers_down_in_auto_mode_degrades_instead_of_raising(self):
        self.gemini.side_effect = ValueError("no key")
        self.lm.side_effect = requests.ConnectionError("offline")
        data, _, _ = generate_recipe_detail_meta("Soup", provider="auto")
        self.assertEqual(data["cuisine"], "Gourmet")

    def test_wrapper_returns_only_the_dict(self):
        self.gemini.return_value = (json.dumps(DETAIL), "m", [])
        with patch("GetFood.ai_service.DEFAULT_AI_PROVIDER", "gemini"):
            self.assertEqual(generate_recipe_detail("Soup")["name"], "Soup")


# --------------------------------------------------------------------------- fridge scan
class ScanTests(NoNetworkMixin, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.vision = self._patch("GetFood.ai_service._call_gemini_vision")

    def test_array_is_sanitised_and_titled(self):
        self.vision.return_value = json.dumps([
            {"name": " bell pepper ", "category": "Produce", "confidence": "0.7", "estimated_quantity": "2"},
            {"name": "milk"},  # defaults for the missing fields
            {"category": "Other"},  # no name -> dropped
            "not a dict",  # dropped
        ])
        items = scan_fridge_image(IMG, provider="gemini")
        self.assertEqual([i["name"] for i in items], ["Bell Pepper", "Milk"])
        self.assertEqual(items[0]["confidence"], 0.7)
        self.assertEqual(items[1]["category"], "Produce")
        self.assertEqual(items[1]["confidence"], 0.9)
        self.assertNotIn("display_name", items[0])

    def test_wrapped_object_shapes(self):
        for key in ("detected_ingredients", "ingredients"):
            self.vision.return_value = "```json\n" + json.dumps({key: [{"name": "egg"}]}) + "\n```"
            self.assertEqual([i["name"] for i in scan_fridge_image(IMG)], ["Egg"], key)

    def test_malformed_json_is_salvaged(self):
        self.vision.return_value = '[{"name": "egg"}, {"name": "ham"} ,, oops'
        self.assertEqual([i["name"] for i in scan_fridge_image(IMG)], ["Egg", "Ham"])

    def test_localised_display_name_is_requested_and_kept(self):
        self.vision.return_value = json.dumps([{"name": "Egg", "display_name": " تخم مرغ "}])
        items = scan_fridge_image(IMG, language="fa")
        self.assertEqual(items[0]["display_name"], "تخم مرغ")
        self.assertEqual(items[0]["name"], "Egg")  # canonical English name is untouched
        self.assertIn("display_name", self.vision.call_args.args[0])
        self.assertIn("Persian", self.vision.call_args.kwargs["system_instruction"])

    def test_vision_failure_or_empty_result_returns_the_demo_fallback(self):
        self.vision.side_effect = ValueError("All Gemini vision models failed")
        fallback = scan_fridge_image(IMG)
        self.assertGreaterEqual(len(fallback), 5)
        self.vision.side_effect = None
        for content in ("", "[]", "garbage"):
            self.vision.return_value = content
            self.assertEqual([i["name"] for i in scan_fridge_image(IMG)], [i["name"] for i in fallback], content)

    def test_non_gemini_provider_still_uses_vision_and_default_provider(self):
        self.vision.return_value = json.dumps([{"name": "egg"}])
        self.assertEqual(scan_fridge_image(IMG, provider="lmstudio")[0]["name"], "Egg")
        with patch("GetFood.ai_service.DEFAULT_AI_PROVIDER", "gemini"):
            self.assertEqual(scan_fridge_image(IMG)[0]["name"], "Egg")


# --------------------------------------------------------------------------- SSE streaming
def _sse_response(lines, status=200):
    resp = MagicMock(status_code=status)
    resp.iter_lines.return_value = lines
    return resp


def _payload(text):
    return json.dumps({"candidates": [{"content": {"parts": [{"text": text}]}}]})


def _chunks(stream):
    """Parse the SSE ``data: {...}`` frames a stream yields."""
    out = []
    for frame in stream:
        assert frame.startswith("data: ") and frame.endswith("\n\n"), frame
        out.append(json.loads(frame[len("data: "):]))
    return out


class StreamTests(NoNetworkMixin, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.sleep = self._patch("time.sleep")  # the offline streamer paces itself at 30 ms/word

    def _stream_with(self, resp):
        self.post.side_effect = None
        self.post.return_value.__enter__.return_value = resp

    def test_live_gemini_stream_relays_text_chunks_then_done(self):
        self._stream_with(_sse_response([
            f"data: {_payload('Hello ')}".encode(),
            b"",  # keep-alive blank line
            b": comment",  # not a data frame
            b"data: {not json",  # malformed frames are skipped
            f"data: {_payload('world')}".encode(),
            f"data: {_payload('')}".encode(),  # empty text is not forwarded
        ]))
        frames = _chunks(stream_recipe_generation("Soup", provider="gemini", language="ar"))
        self.assertEqual([f["chunk"] for f in frames], ["Hello ", "world", ""])
        self.assertEqual([f["done"] for f in frames], [False, False, True])
        self.assertIn("streamGenerateContent", self.post.call_args.args[0])
        self.assertIn("Arabic", self.post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"])
        self.sleep.assert_not_called()

    def test_non_200_from_google_switches_to_the_offline_streamer(self):
        self._stream_with(_sse_response([], status=503))
        frames = _chunks(stream_recipe_generation("Soup", provider="gemini"))
        text = "".join(f["chunk"] for f in frames)
        self.assertIn("Gourmet Soup", text)
        self.assertTrue(frames[-1]["done"])
        self.assertTrue(self.sleep.called)

    def test_connection_error_switches_to_the_offline_streamer(self):
        frames = _chunks(stream_recipe_generation("Soup", provider="gemini"))  # post raises ConnectionError
        self.assertIn("Gourmet Soup", "".join(f["chunk"] for f in frames))
        self.assertTrue(frames[-1]["done"])

    def test_no_api_key_or_other_provider_never_calls_google(self):
        with patch("GetFood.ai_service.GEMINI_API_KEY", ""), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("GEMINI_API_KEY", None)
            frames = _chunks(stream_recipe_generation("Soup", provider="gemini"))
        self.assertTrue(frames[-1]["done"])
        _chunks(stream_recipe_generation("Soup", provider="lmstudio"))
        self.post.assert_not_called()

    def test_default_provider_is_used_when_none_given(self):
        with patch("GetFood.ai_service.DEFAULT_AI_PROVIDER", "lmstudio"):
            _chunks(stream_recipe_generation("Soup"))
        self.post.assert_not_called()


# --------------------------------------------------------------------------- sous-chef chat
class ChatTests(NoNetworkMixin, SimpleTestCase):
    def setUp(self):
        super().setUp()
        self.gemini = self._patch("GetFood.ai_service._call_gemini_with_meta")
        self.lm = self._patch("GetFood.ai_service._call_lmstudio")

    def test_gemini_reply_includes_recipe_context_and_recent_history(self):
        self.gemini.return_value = ("  Use butter.  ", "gemini-x", ["gemini-y"])
        history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)]
        result = ask_recipe_chat(
            "Soup",
            ingredients=[{"name": "leek"}],
            instructions="Boil it.",
            user_question="Can I swap the oil?",
            history=history,
            provider="gemini",
            language="es",
        )
        self.assertEqual(result, {
            "reply": "Use butter.", "model_used": "gemini-x", "rate_limited_models": ["gemini-y"], "recipe_name": "Soup",
        })
        prompt = self.gemini.call_args.args[0]
        self.assertNotIn("m3", prompt)  # only the last six turns are sent
        self.assertIn("Cook: m4", prompt)
        self.assertIn("Chef: m5", prompt)
        self.assertTrue(prompt.endswith("Cook: Can I swap the oil?\nChef:"))
        system = self.gemini.call_args.kwargs["system_instruction"]
        self.assertIn("leek", system)
        self.assertIn("Boil it.", system)
        self.assertIn("Spanish", system)
        self.assertEqual(self.gemini.call_args.kwargs["response_mime_type"], "")  # plain text, not JSON

    def test_lmstudio_provider(self):
        self.lm.return_value = "local reply"
        result = ask_recipe_chat("Soup", user_question="hi", provider="lmstudio")
        self.assertEqual((result["reply"], result["model_used"]), ("local reply", ai_service.MODEL_NAME))
        self.gemini.assert_not_called()

    def test_unknown_provider_falls_back_from_gemini_to_lmstudio(self):
        self.gemini.side_effect = ValueError("no key")
        self.lm.return_value = "local reply"
        result = ask_recipe_chat("Soup", user_question="hi", provider="auto")
        self.assertEqual(result["reply"], "local reply")

    def test_provider_failure_returns_friendly_tips_not_an_exception(self):
        self.gemini.side_effect = ValueError("quota")
        result = ask_recipe_chat("Soup", user_question="hi", provider="gemini")
        self.assertIn("sous-chef for **Soup**", result["reply"])
        self.assertEqual(result["rate_limited_models"], [])
        self.assertEqual(result["recipe_name"], "Soup")

    def test_both_providers_down_in_auto_mode_returns_friendly_tips(self):
        self.gemini.side_effect = ValueError("no key")
        self.lm.side_effect = requests.ConnectionError("offline")
        self.assertIn("Substitutions", ask_recipe_chat("Soup", user_question="hi", provider="auto")["reply"])

    def test_missing_context_and_falsy_provider_use_defaults(self):
        self.gemini.return_value = ("ok", "m", [])
        with patch("GetFood.ai_service.DEFAULT_AI_PROVIDER", "gemini"):
            result = ask_recipe_chat("Soup", user_question="hi", provider=None, history="not a list")
        self.assertEqual(result["reply"], "ok")
