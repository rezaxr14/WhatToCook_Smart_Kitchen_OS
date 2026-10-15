from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .models import Ingredient, Recipe, RecipeIngredient, TelegramAccountLink, UserPantry


class AuthAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.username = "culinary_tester"
        self.password = "pass12345"
        self.email = "tester@whattocook.local"

    def test_user_signup_and_auto_pantry(self):
        response = self.client.post(
            reverse("api_auth_signup"),
            data={"username": self.username, "password": self.password, "email": self.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("user", response.data)
        self.assertIn("pantry", response.data)
        
        # Verify user and pantry in DB
        user = User.objects.get(username=self.username)
        self.assertTrue(UserPantry.objects.filter(user=user).exists())

    def test_user_login_valid_and_invalid(self):
        user = User.objects.create_user(username=self.username, password=self.password)
        UserPantry.objects.create(user=user)

        # Valid login
        res_valid = self.client.post(
            reverse("api_auth_login"),
            data={"username": self.username, "password": self.password},
            format="json",
        )
        self.assertEqual(res_valid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_valid.data["user"]["username"], self.username)

        # Invalid login
        res_invalid = self.client.post(
            reverse("api_auth_login"),
            data={"username": self.username, "password": "wrongpassword"},
            format="json",
        )
        self.assertEqual(res_invalid.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guest_demo_login(self):
        response = self.client.post(reverse("api_auth_demo"), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["username"], "ChefDemo")
        self.assertIn("pantry", response.data)

    def test_auth_me_and_logout(self):
        user = User.objects.create_user(username=self.username, password=self.password)
        UserPantry.objects.create(user=user)
        self.client.force_authenticate(user=user)

        # Me endpoint
        res_me = self.client.get(reverse("api_auth_me"))
        self.assertEqual(res_me.status_code, status.HTTP_200_OK)
        self.assertTrue(res_me.data["authenticated"])
        self.assertEqual(res_me.data["user"]["username"], self.username)

        # Logout endpoint
        res_logout = self.client.post(reverse("api_auth_logout"))
        self.assertEqual(res_logout.status_code, status.HTTP_200_OK)


class PantryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="pantry_tester", password="password123")
        self.pantry = UserPantry.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        self.egg = Ingredient.objects.create(name="Eggs", category="Dairy & Eggs")
        self.milk = Ingredient.objects.create(name="Milk", category="Dairy & Eggs")
        self.flour = Ingredient.objects.create(name="Flour", category="Grains & Pasta")

    def test_get_pantry(self):
        self.pantry.ingredients.add(self.egg)
        response = self.client.get(reverse("api_pantry_get"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["ingredients"]), 1)
        self.assertEqual(response.data["ingredients"][0]["name"], "Eggs")

    def test_add_ingredient_by_id(self):
        response = self.client.post(
            reverse("api_pantry_add"),
            data={"ingredient_id": self.milk.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(self.pantry.ingredients.filter(id=self.milk.id).exists())

    def test_add_ingredient_by_name(self):
        response = self.client.post(
            reverse("api_pantry_add"),
            data={"name": "Avocado"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Ingredient.objects.filter(name="Avocado").exists())
        self.assertTrue(self.pantry.ingredients.filter(name="Avocado").exists())

    def test_add_multiple_ingredients(self):
        response = self.client.post(
            reverse("api_pantry_add"),
            data={"ingredient_ids": [self.egg.id, self.flour.id]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.pantry.ingredients.count(), 2)

    def test_remove_ingredient(self):
        self.pantry.ingredients.add(self.egg, self.milk)
        response = self.client.post(
            reverse("api_pantry_remove"),
            data={"ingredient_id": self.egg.id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(self.pantry.ingredients.filter(id=self.egg.id).exists())
        self.assertTrue(self.pantry.ingredients.filter(id=self.milk.id).exists())

    def test_clear_pantry(self):
        self.pantry.ingredients.add(self.egg, self.milk, self.flour)
        response = self.client.post(reverse("api_pantry_clear"), format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.pantry.ingredients.count(), 0)


class CanCookMatchTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="cook_tester", password="password123")
        self.pantry = UserPantry.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

        self.egg = Ingredient.objects.create(name="Eggs")
        self.cheese = Ingredient.objects.create(name="Cheese")
        self.butter = Ingredient.objects.create(name="Butter")
        self.bread = Ingredient.objects.create(name="Bread")

        # 100% Match Recipe: Cheesy Omelette (Eggs, Cheese)
        self.omelette = Recipe.objects.create(name="Cheesy Omelette", cooking_time=10)
        RecipeIngredient.objects.create(recipe=self.omelette, ingredient=self.egg, quantity="2")
        RecipeIngredient.objects.create(recipe=self.omelette, ingredient=self.cheese, quantity="50g")

        # Partial Match Recipe: Grilled Cheese (Bread, Cheese, Butter)
        self.grilled_cheese = Recipe.objects.create(name="Grilled Cheese", cooking_time=8)
        RecipeIngredient.objects.create(recipe=self.grilled_cheese, ingredient=self.bread, quantity="2 slices")
        RecipeIngredient.objects.create(recipe=self.grilled_cheese, ingredient=self.cheese, quantity="50g")
        RecipeIngredient.objects.create(recipe=self.grilled_cheese, ingredient=self.butter, quantity="10g")

    def test_recipe_matching_logic(self):
        # User has Eggs, Cheese, Butter (can make Omelette fully; missing Bread for Grilled Cheese)
        self.pantry.ingredients.add(self.egg, self.cheese, self.butter)

        response = self.client.get(reverse("api_can_cook"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        full_matches = response.data.get("full_matches", [])
        partial_matches = response.data.get("partial_matches", [])

        # Cheesy Omelette must be in full matches
        self.assertTrue(any(r["name"] == "Cheesy Omelette" for r in full_matches))

        # Grilled Cheese must be in partial matches (missing 1 item: Bread)
        gc_match = next((r for r in partial_matches if r["name"] == "Grilled Cheese"), None)
        self.assertIsNotNone(gc_match)
        self.assertEqual(gc_match["missing_count"], 1)
        self.assertEqual(gc_match["missing_ingredients"][0], "Bread")


class AIVisionScannerTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="vision_tester", password="password123")
        self.pantry = UserPantry.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_scan_image_base64_payload(self):
        # Create a tiny 1x1 dummy image base64
        dummy_base64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        response = self.client.post(
            reverse("api_pantry_scan_image"),
            data={"image_base64": dummy_base64, "auto_add": False},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("detected_ingredients", response.data)
        self.assertGreater(len(response.data["detected_ingredients"]), 0)

    def test_scan_image_auto_add_flag(self):
        dummy_base64 = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
        response = self.client.post(
            reverse("api_pantry_scan_image"),
            data={"image_base64": dummy_base64, "auto_add": True},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["auto_added"])
        self.assertGreater(self.pantry.ingredients.count(), 0)


class AISuggestionsAndStreamingTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_ai_suggestions_api(self):
        response = self.client.post(
            reverse("api_ai_suggestions"),
            data={"ingredients": ["Eggs", "Cheese", "Garlic"], "provider": "gemini"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("recipes", response.data)
        self.assertGreater(len(response.data["recipes"]), 0)

    def test_ai_recipe_detail_api(self):
        response = self.client.get(
            reverse("api_ai_recipe_detail", kwargs={"recipe_name": "Garlic Butter Skillet"})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("ingredients", response.data)
        self.assertIn("instructions", response.data)

    def test_ai_streaming_response_sse(self):
        response = self.client.get(
            f"{reverse('api_ai_stream_recipe')}?recipe=Tuscan%20Chicken&provider=gemini"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")


class TelegramBotAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="tg_chef", password="password123")
        self.pantry = UserPantry.objects.create(user=self.user)
        self.client.force_authenticate(user=self.user)

    def test_telegram_link_generation(self):
        response = self.client.get(reverse("api_telegram_get_link"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("auth_token", response.data)
        self.assertIn("connect_url", response.data)

    def test_telegram_webhook_start_command(self):
        link = TelegramAccountLink.generate_token_for_user(self.user)
        payload = {
            "message": {
                "chat": {"id": "12345678"},
                "from": {"username": "chef_john"},
                "text": f"/start {link.auth_token}",
            }
        }
        response = self.client.post(
            reverse("api_telegram_webhook"),
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "connected")

        # Verify linked in DB
        link.refresh_from_db()
        self.assertEqual(link.telegram_chat_id, "12345678")
        self.assertEqual(link.telegram_username, "chef_john")

    def test_telegram_webhook_pantry_add_command(self):
        TelegramAccountLink.objects.create(
            user=self.user,
            telegram_chat_id="999999",
            telegram_username="tg_tester",
            auth_token="sampletoken123",
        )
        payload = {
            "message": {
                "chat": {"id": "999999"},
                "text": "/add Olive Oil",
            }
        }
        response = self.client.post(
            reverse("api_telegram_webhook"),
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ingredient_added")
        self.assertTrue(self.pantry.ingredients.filter(name="Olive Oil").exists())


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "platform-endpoint-tests",
        }
    }
)
class PlatformEndpointTests(TestCase):
    """
    Uses a hermetic in-memory cache so runs stay independent of any live
    REDIS_URL configured in the environment (e.g. Docker's redis://redis:6379).
    """

    def setUp(self):
        from django.core.cache import cache

        cache.clear()  # stats are cached; isolate per test
        self.client = APIClient()
        Ingredient.objects.create(name="Tomato", calories_per_100g=18)
        recipe = Recipe.objects.create(name="Test Soup", description="Warm soup")
        recipe.ingredients.add(Ingredient.objects.first())

    def test_api_stats_public_counters(self):
        response = self.client.get(reverse("api_stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_recipes"], 1)
        self.assertEqual(response.data["total_ingredients"], 1)

    def test_api_stats_includes_active_users(self):
        User.objects.create_user(username="active_chef", password="pass12345")
        User.objects.create_user(username="ghost_chef", password="pass12345", is_active=False)
        response = self.client.get(reverse("api_stats"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total_users"], 1)

    def test_api_health_reports_database_ok(self):
        response = self.client.get(reverse("api_health"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertEqual(response.data["checks"]["database"], "ok")

    def test_legacy_html_routes_namespaced(self):
        res_index = self.client.get(reverse("index"))
        self.assertEqual(res_index.status_code, status.HTTP_200_OK)
        self.assertTemplateUsed(res_index, "GetFood/index.html")
