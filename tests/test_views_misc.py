"""API tests for the non-AI views: auth/pantry error paths, shopping list, Telegram bot, platform
probes, legacy server-rendered pages and the rate-limit helpers.

Deliberately NOT covered here: who may edit or delete a given shopping-list row. That is an open
authorization question (see the PR description), so no test pins the current behaviour.
"""
import os
from unittest.mock import MagicMock, patch

import requests
from django.contrib.auth.models import AnonymousUser, User
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from GetFood import rate_limits
from GetFood.models import Ingredient, Recipe, RecipeIngredient, ShoppingListItem, TelegramAccountLink, UserPantry

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "views-misc-tests"}}
PW = "x" * 12
FAST_HASH = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # test-only: PBKDF2 costs ~0.3 s per create_user


@override_settings(CACHES=LOCMEM, PASSWORD_HASHERS=FAST_HASH)
class ApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()


# --------------------------------------------------------------------------- auth
class AuthErrorPathTests(ApiTestCase):
    def test_login_requires_both_fields(self):
        for body in ({}, {"username": "a"}, {"password": "b"}, {"username": "  ", "password": "b"}):
            r = self.client.post(reverse("api_auth_login"), body, format="json")
            self.assertEqual(r.status_code, 400, body)

    def test_signup_validation_and_duplicate_username(self):
        url = reverse("api_auth_signup")
        self.assertEqual(self.client.post(url, {"username": "a"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(url, {"password": "b"}, format="json").status_code, 400)
        User.objects.create_user("taken", password=PW)
        r = self.client.post(url, {"username": "taken", "password": PW}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("already taken", r.data["error"])

    def test_me_for_anonymous_visitors(self):
        self.assertEqual(self.client.get(reverse("api_auth_me")).data, {"authenticated": False, "user": None, "pantry": None})


# --------------------------------------------------------------------------- pantry
class PantryErrorPathTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.tomato = Ingredient.objects.create(name="Tomato")
        self.egg = Ingredient.objects.create(name="Egg")

    def test_anonymous_without_a_demo_account_cannot_write(self):
        for name in ("api_pantry_add", "api_pantry_remove", "api_pantry_clear"):
            r = self.client.post(reverse(name), {"ingredient_id": self.tomato.id}, format="json")
            self.assertEqual(r.status_code, 400, name)
        self.assertFalse(UserPantry.objects.exists())

    def test_add_by_name_by_ids_and_unknown_ids(self):
        user = User.objects.create_user("cook", password=PW)
        self.client.force_authenticate(user)
        r = self.client.post(reverse("api_pantry_add"), {"name": "  Basil "}, format="json")
        self.assertIn("Basil", r.data["message"])
        r = self.client.post(reverse("api_pantry_add"), {"ingredient_ids": [self.tomato.id, 99999, self.egg.id]}, format="json")
        self.assertEqual(r.data["message"], "Added: Tomato, Egg")
        self.assertEqual(self.client.post(reverse("api_pantry_add"), {"ingredient_id": 99999}, format="json").status_code, 404)
        self.assertEqual(self.client.post(reverse("api_pantry_add"), {}, format="json").data["message"], "Added: ")

    def test_remove_errors_and_clear(self):
        user = User.objects.create_user("cook", password=PW)
        UserPantry.objects.create(user=user).ingredients.add(self.tomato, self.egg)
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(reverse("api_pantry_remove"), {}, format="json").status_code, 400)
        self.assertEqual(self.client.post(reverse("api_pantry_remove"), {"ingredient_id": 99999}, format="json").status_code, 404)
        self.assertEqual(self.client.post(reverse("api_pantry_remove"), {"ingredient_id": self.egg.id}, format="json").status_code, 200)
        self.client.post(reverse("api_pantry_clear"))
        self.assertEqual(user.userpantry.ingredients.count(), 0)


# --------------------------------------------------------------------------- shopping list
class ShoppingListTests(ApiTestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("shopper", password=PW)
        self.client.force_authenticate(self.user)

    def test_add_single_and_bulk_skips_blank_names(self):
        add = reverse("api_shopping_list_add")
        single = self.client.post(add, {"name": " Milk ", "quantity": "2 l", "added_from": "Pancakes"}, format="json").data
        self.assertEqual((single["added_count"], single["items"][0]["name"], single["items"][0]["quantity"]), (1, "Milk", "2 l"))
        bulk = self.client.post(add, {"items": [{"name": "Eggs"}, {"name": "  "}, {"name": "Flour", "category": "Pantry"}]}, format="json").data
        self.assertEqual(bulk["added_count"], 2)
        self.assertEqual(self.client.post(add, {}, format="json").data["added_count"], 0)
        self.assertEqual(ShoppingListItem.objects.filter(user=self.user).count(), 3)

    def test_get_lists_the_users_items(self):
        ShoppingListItem.objects.create(user=self.user, name="Milk", added_from="Pancakes")
        data = self.client.get(reverse("api_shopping_list_get")).data
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["items"][0]["added_from"], "Pancakes")

    def test_anonymous_visitors_use_a_session_scoped_list(self):
        anon = APIClient()
        anon.post(reverse("api_shopping_list_add"), {"name": "Salt"}, format="json")
        self.assertEqual(anon.get(reverse("api_shopping_list_get")).data["count"], 1)
        self.assertEqual(self.client.get(reverse("api_shopping_list_get")).data["count"], 0)  # not the logged-in user's list

    def test_sync_replaces_the_list_and_rejects_bad_shapes(self):
        sync = reverse("api_shopping_list_sync")
        ShoppingListItem.objects.create(user=self.user, name="Old")
        r = self.client.post(sync, {"items": [{"name": "New", "checked": True}, {"name": ""}]}, format="json")
        self.assertEqual(r.data, {"status": "synced", "count": 1})
        self.assertEqual(list(ShoppingListItem.objects.filter(user=self.user).values_list("name", "checked")), [("New", True)])
        self.assertEqual(self.client.post(sync, {"items": "nope"}, format="json").status_code, 400)
        anon = APIClient()
        self.assertEqual(anon.post(sync, {"items": [{"name": "Salt"}]}, format="json").data["count"], 1)

    def test_toggle_updates_fields_and_unknown_id_is_404(self):
        item = ShoppingListItem.objects.create(user=self.user, name="Milk")
        r = self.client.patch(reverse("api_shopping_list_toggle", args=[item.id]),
                              {"checked": True, "name": " Oat milk ", "quantity": " 2 ", "category": " Dairy "}, format="json")
        self.assertEqual((r.status_code, r.data["checked"]), (200, True))
        item.refresh_from_db()
        self.assertEqual((item.name, item.quantity, item.category), ("Oat milk", "2", "Dairy"))
        self.assertEqual(self.client.patch(reverse("api_shopping_list_toggle", args=[999999]), {}, format="json").status_code, 404)

    def test_remove_and_clear(self):
        keep = ShoppingListItem.objects.create(user=self.user, name="Keep")
        gone = ShoppingListItem.objects.create(user=self.user, name="Gone")
        done = ShoppingListItem.objects.create(user=self.user, name="Done", checked=True)
        self.assertEqual(self.client.delete(reverse("api_shopping_list_remove", args=[gone.id])).data["status"], "deleted")
        self.assertEqual(self.client.post(reverse("api_shopping_list_clear"), {"only_completed": True}, format="json").data["deleted_count"], 1)
        self.assertFalse(ShoppingListItem.objects.filter(pk=done.pk).exists())
        self.assertTrue(ShoppingListItem.objects.filter(pk=keep.pk).exists())
        r = self.client.delete(reverse("api_shopping_list_clear"), {"only_completed": ""})  # query-string flavour: empty = all
        self.assertEqual(r.data["status"], "cleared")
        self.assertFalse(ShoppingListItem.objects.filter(user=self.user).exists())


# --------------------------------------------------------------------------- telegram
@override_settings(CACHES=LOCMEM, PASSWORD_HASHERS=FAST_HASH, TELEGRAM_BOT_TOKEN="bot-token")
class TelegramTests(ApiTestCase):
    url = property(lambda self: reverse("api_telegram_webhook"))

    def setUp(self):
        super().setUp()
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("TELEGRAM_WEBHOOK_SECRET", None)
        post = patch("GetFood.views.requests.post")
        self.send = post.start()
        self.addCleanup(post.stop)
        self.user = User.objects.create_user("chef", password=PW)
        self.link = TelegramAccountLink.generate_token_for_user(self.user)

    def _say(self, text, chat_id=555, **extra):
        return self.client.post(self.url, {"message": {"chat": {"id": chat_id}, "from": {"username": "tg_chef"}, "text": text}},
                                format="json", **extra)

    def _reply(self):
        return self.send.call_args.kwargs["json"]["text"]

    def _link_chat(self, chat_id="555"):
        TelegramAccountLink.objects.filter(pk=self.link.pk).update(telegram_chat_id=chat_id)

    # -- get link
    def test_link_endpoint_issues_a_stable_token_for_the_logged_in_user(self):
        self.client.force_authenticate(self.user)
        a = self.client.get(reverse("api_telegram_get_link")).data
        b = self.client.post(reverse("api_telegram_get_link")).data
        self.assertEqual(a["auth_token"], b["auth_token"])
        self.assertFalse(a["is_connected"])
        self.assertIn(a["auth_token"], a["connect_url"])

    def test_link_endpoint_for_guests_uses_the_demo_user_or_creates_one(self):
        r = self.client.get(reverse("api_telegram_get_link"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(User.objects.filter(username="chef_demo").exists())
        User.objects.create_user("ChefDemo", password=PW)
        self.client.get(reverse("api_telegram_get_link"))
        self.assertTrue(TelegramAccountLink.objects.filter(user__username="ChefDemo").exists())

    # -- secret
    def test_webhook_secret_is_enforced_when_configured(self):
        with patch.dict(os.environ, {"TELEGRAM_WEBHOOK_SECRET": "s3cret"}):
            self.assertEqual(self._say("/pantry").status_code, 403)
            self.assertEqual(self._say("/pantry", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="wrong").status_code, 403)
            self.assertEqual(self._say("/start", HTTP_X_TELEGRAM_BOT_API_SECRET_TOKEN="s3cret").status_code, 200)

    @override_settings(TELEGRAM_WEBHOOK_SECRET="from-settings")
    def test_webhook_secret_can_come_from_settings(self):
        self.assertEqual(self._say("/start").status_code, 403)

    def test_updates_without_a_message_are_ignored(self):
        r = self.client.post(self.url, {"edited_message": {}}, format="json")
        self.assertEqual(r.data, {"status": "ignored"})
        self.send.assert_not_called()

    # -- /start
    def test_start_with_a_valid_token_connects_the_chat(self):
        r = self._say(f"/start {self.link.auth_token}")
        self.assertEqual(r.data, {"status": "connected", "user": "chef"})
        self.link.refresh_from_db()
        self.assertEqual((self.link.telegram_chat_id, self.link.telegram_username), ("555", "tg_chef"))
        self.assertIn("Account Connected", self._reply())

    def test_start_with_an_unknown_token_or_no_token(self):
        self.assertEqual(self._say("/start nope").data, {"status": "invalid_token"})
        self.assertEqual(self._say("/start").data, {"status": "welcome"})
        self.link.refresh_from_db()
        self.assertIsNone(self.link.telegram_chat_id)

    def test_unlinked_chats_get_a_locked_message(self):
        self.assertEqual(self._say("/pantry").data, {"status": "unlinked"})
        self.assertFalse(UserPantry.objects.exists())

    def test_deactivated_links_are_treated_as_unlinked(self):
        self._link_chat()
        TelegramAccountLink.objects.filter(pk=self.link.pk).update(is_active=False)
        self.assertEqual(self._say("/pantry").data, {"status": "unlinked"})

    # -- commands
    def test_pantry_command_empty_and_stocked(self):
        self._link_chat()
        self.assertEqual(self._say("/pantry").data, {"status": "pantry_viewed"})
        self.assertIn("empty", self._reply())
        self._say("/add garlic")
        self._say("/pantry")
        self.assertIn("Garlic", self._reply())

    def test_add_command(self):
        self._link_chat()
        self.assertEqual(self._say("/add olive oil").data, {"status": "ingredient_added"})
        self.assertTrue(self.user.userpantry.ingredients.filter(name="Olive Oil").exists())
        self._say("/add")
        self.assertIn("specify", self._reply())

    def test_remove_command(self):
        self._link_chat()
        self._say("/add tomato")
        self._say("/remove TOMATO")
        self.assertIn("Removed", self._reply())
        self.assertEqual(self.user.userpantry.ingredients.count(), 0)
        self._say("/remove tomato")
        self.assertIn("Could not find", self._reply())
        self._say("/remove")
        self.assertIn("specify", self._reply())

    def test_cook_command_empty_pantry_and_with_suggestions(self):
        self._link_chat()
        self.assertEqual(self._say("/cook").data, {"status": "empty_pantry"})
        self._say("/add egg")
        suggestions = [{"name": f"Dish {i}", "prep_time": "10 mins", "short_description": "tasty"} for i in range(6)]
        with patch("GetFood.views.generate_recipe_suggestions", return_value=suggestions):
            r = self._say("/cook")
        self.assertEqual(r.data, {"status": "recipes_suggested"})
        self.assertIn("Dish 3", self._reply())
        self.assertNotIn("Dish 4", self._reply())  # at most four ideas per message

    def test_unknown_commands_get_the_help_text(self):
        self._link_chat()
        self.assertEqual(self._say("hello?").data, {"status": "help_sent"})
        self.assertIn("/pantry", self._reply())

    def test_replies_are_skipped_without_a_bot_token_and_send_errors_are_swallowed(self):
        with override_settings(TELEGRAM_BOT_TOKEN=""), patch.dict(os.environ, {}, clear=False):
            os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            self.assertEqual(self._say("/start").status_code, 200)
        self.send.assert_not_called()
        self.send.side_effect = requests.ConnectionError("telegram down")
        self.assertEqual(self._say("/start").status_code, 200)


# --------------------------------------------------------------------------- probes
class PlatformProbeTests(ApiTestCase):
    def test_stats_survive_a_broken_cache(self):
        with patch("django.core.cache.cache.get", side_effect=OSError("redis down")), \
                patch("django.core.cache.cache.set", side_effect=OSError("redis down")):
            r = self.client.get(reverse("api_stats"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(set(r.data), {"total_recipes", "total_ingredients", "total_users"})

    def test_health_reports_a_database_outage_as_503(self):
        with patch("django.db.connection.cursor", side_effect=RuntimeError("db gone")):
            r = self.client.get(reverse("api_health"))
        self.assertEqual(r.status_code, 503)
        self.assertEqual((r.data["status"], r.data["checks"]["database"]), ("error", "down"))

    def test_health_degrades_but_stays_up_on_cache_trouble(self):
        with patch("django.core.cache.cache.get", return_value="unexpected"):
            self.assertEqual(self.client.get(reverse("api_health")).data["checks"]["cache"], "degraded")
        with patch("django.core.cache.cache.set", side_effect=OSError("redis down")):
            r = self.client.get(reverse("api_health"))
        self.assertEqual((r.status_code, r.data["checks"]["cache"]), (200, "degraded"))


# --------------------------------------------------------------------------- legacy pages
@override_settings(CACHES=LOCMEM, PASSWORD_HASHERS=FAST_HASH)
class LegacyPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user("legacy", password=PW)
        self.egg = Ingredient.objects.create(name="Egg")
        self.salt = Ingredient.objects.create(name="Salt")
        self.recipes = []
        for i in range(8):  # more than one page (6 per page)
            recipe = Recipe.objects.create(name=f"Dish {i}", instructions="Step 1\nStep 2")
            RecipeIngredient.objects.create(recipe=recipe, ingredient=self.egg)
            self.recipes.append(recipe)

    def test_index_paginates_and_clamps_bad_page_numbers(self):
        for page, expected in (("1", 1), ("2", 2), ("abc", 1), ("99", 2)):
            r = self.client.get(reverse("index"), {"page": page})
            self.assertEqual((r.status_code, r.context["current_page"]), (200, expected), page)

    def test_recipe_detail_and_404(self):
        r = self.client.get(reverse("recipe_detail", args=[self.recipes[0].id]))
        self.assertEqual(r.context["instructions_list"], ["Step 1", "Step 2"])
        self.assertEqual(self.client.get(reverse("recipe_detail", args=[999999])).status_code, 404)

    def test_login_required_pages_redirect_anonymous_visitors(self):
        for name, args in (("pantry", []), ("ai_suggestions", []), ("ai_recipe_detail", ["Soup"])):
            r = self.client.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 302, name)
            self.assertIn("login", r["Location"])

    def test_pantry_page_add_and_remove(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("pantry")).status_code, 200)
        self.assertEqual(self.client.post(reverse("pantry"), {"ingredient_id": self.egg.id}).status_code, 302)
        self.assertEqual(list(self.user.userpantry.ingredients.all()), [self.egg])
        self.assertEqual(self.client.post(reverse("pantry"), {"remove_id": self.egg.id}).status_code, 302)
        self.assertEqual(self.user.userpantry.ingredients.count(), 0)
        self.assertEqual(self.client.post(reverse("pantry"), {"unrelated": "1"}).status_code, 200)

    def test_ai_suggestions_page_renders_for_logged_in_users(self):
        # ai_recipe_detail is intentionally not rendered here: its template reverses a URL name that
        # does not exist (reported in the PR description), so a 200 assertion would fail.
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("ai_suggestions")).status_code, 200)

    def test_can_cook_for_anonymous_and_for_a_stocked_pantry(self):
        self.assertEqual(self.client.get(reverse("can_cook")).context["possible_recipes"].paginator.count, 0)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("can_cook")).context["possible_recipes"].paginator.count, 0)  # no pantry yet
        UserPantry.objects.create(user=self.user).ingredients.add(self.egg)
        r = self.client.get(reverse("can_cook"), {"page": "zzz"})
        self.assertEqual(r.context["possible_recipes"].paginator.count, 8)
        self.assertEqual(self.client.get(reverse("can_cook"), {"page": "50"}).context["current_page"], 2)

    def test_signup_and_login_forms(self):
        self.assertEqual(self.client.get(reverse("signup")).status_code, 200)
        self.assertEqual(self.client.post(reverse("signup"), {"username": "n", "password1": "a", "password2": "b"}).status_code, 200)
        ok = {"username": "newcomer", "password1": "Zq!9-long-pass", "password2": "Zq!9-long-pass"}
        self.assertEqual(self.client.post(reverse("signup"), ok).status_code, 302)
        self.assertTrue(UserPantry.objects.filter(user__username="newcomer").exists())

        self.client.logout()
        self.assertEqual(self.client.get(reverse("login")).status_code, 200)
        self.assertEqual(self.client.post(reverse("login"), {"username": "legacy", "password": "wrong"}).status_code, 200)
        self.assertEqual(self.client.post(reverse("login"), {"username": "legacy", "password": PW}).status_code, 302)


# --------------------------------------------------------------------------- rate-limit helpers
class RateLimitHelperTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()
        self.addCleanup(cache.clear)

    def _request(self, ip="1.2.3.4", user=None, **meta):
        request = self.factory.get("/", REMOTE_ADDR=ip, **meta)
        request.user = user or AnonymousUser()
        return request

    def test_load_rates_merges_env_overrides_and_ignores_garbage(self):
        with patch.dict(os.environ, {"THROTTLE_RATES": "ai=20/min; signup=10/hour;broken;=1/min;empty="}):
            rates = rate_limits.load_rates()
        self.assertEqual((rates["ai"], rates["signup"]), ("20/min", "10/hour"))
        self.assertEqual(rates["catalog"], rate_limits.DEFAULT_RATES["catalog"])
        with patch.dict(os.environ, {"THROTTLE_RATES": ""}):
            self.assertEqual(rate_limits.load_rates(), rate_limits.DEFAULT_RATES)

    def test_fixed_window_counter_trips_after_the_limit(self):
        results = [rate_limits.limit_exceeded(self._request(), "t", limit=2) for _ in range(4)]
        self.assertEqual(results, [False, False, True, True])

    def test_buckets_are_per_ip_per_user_and_honour_forwarded_for(self):
        for _ in range(3):
            rate_limits.limit_exceeded(self._request(), "t", limit=2)
        self.assertFalse(rate_limits.limit_exceeded(self._request(ip="9.9.9.9"), "t", limit=2))
        self.assertFalse(rate_limits.limit_exceeded(self._request(user=MagicMock(is_authenticated=True, pk=7)), "t", limit=2))
        fwd = self._request(ip="10.0.0.1", HTTP_X_FORWARDED_FOR="5.5.5.5, 10.0.0.1")
        rate_limits.limit_exceeded(fwd, "t", limit=2)
        self.assertEqual(fwd.wtc_client_key, "i5.5.5.5")

    def test_rate_limited_json_is_none_until_the_limit_then_a_429_with_retry_after(self):
        self.assertIsNone(rate_limits.rate_limited_json(self._request(), "j", limit=1, window_seconds=30))
        response = rate_limits.rate_limited_json(self._request(), "j", limit=1, window_seconds=30)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "30")
