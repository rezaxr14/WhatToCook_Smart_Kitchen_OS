"""Display-only translations and the local/Supabase image tiers."""

from django.test import RequestFactory, TestCase
from rest_framework.test import APIClient

from GetFood.models import Ingredient, Recipe
from GetFood.serializers import IngredientSerializer, RecipeSerializer


def request_with_language(language: str):
    return RequestFactory().get("/", HTTP_ACCEPT_LANGUAGE=language)


class DisplayFieldTests(TestCase):
    def setUp(self):
        self.ingredient = Ingredient.objects.create(
            name="Garlic",
            name_i18n={"fa": "سیر", "ar": "ثوم", "tr": "Sarımsak", "es": "Ajo"},
        )
        self.recipe = Recipe.objects.create(
            name="Shakshuka",
            description="Eggs poached in tomato sauce.",
            instructions="1. Simmer the sauce.\n2. Add the eggs.",
            translations={
                "fa": {
                    "name": "شکشوکا",
                    "description": "تخم‌مرغ در سس گوجه.",
                    "instructions": "۱. سس را بپزید.\n۲. تخم‌مرغ‌ها را اضافه کنید.",
                }
            },
        )

    def test_canonical_fields_stay_english_and_display_fields_follow_accept_language(self):
        client = APIClient()
        response = client.get("/api/ingredients/", HTTP_ACCEPT_LANGUAGE="fa")
        self.assertEqual(response.status_code, 200)
        rows = response.data["results"] if isinstance(response.data, dict) else response.data
        row = next(item for item in rows if item["name"] == "Garlic")
        self.assertEqual(row["name"], "Garlic")
        self.assertEqual(row["display_name"], "سیر")

    def test_recipe_display_fields_are_localized_without_touching_the_canonical_text(self):
        data = RecipeSerializer(
            self.recipe, context={"request": request_with_language("fa")}
        ).data
        self.assertEqual(data["name"], "Shakshuka")
        self.assertEqual(data["description"], "Eggs poached in tomato sauce.")
        self.assertEqual(data["instructions"], "1. Simmer the sauce.\n2. Add the eggs.")
        self.assertEqual(data["display_name"], "شکشوکا")
        self.assertEqual(data["display_description"], "تخم‌مرغ در سس گوجه.")
        self.assertIn("تخم‌مرغ", data["display_instructions"])

    def test_unsupported_or_missing_language_falls_back_to_english(self):
        data = IngredientSerializer(
            self.ingredient, context={"request": request_with_language("de-DE")}
        ).data
        self.assertEqual(data["display_name"], "Garlic")

    def test_image_is_local_and_fallback_is_the_supabase_object(self):
        data = RecipeSerializer(self.recipe).data
        self.assertTrue(data["image"].startswith("/media/"))
        self.assertNotIn("://", data["image"])
        self.assertTrue(data["image_fallback"].startswith("https://"))
        self.assertIn("/storage/v1/object/public/recipe-images/", data["image_fallback"])

    def test_user_uploads_without_a_shared_copy_have_no_fallback(self):
        uploaded = Recipe.objects.create(name="My Dinner", image="recipes/user-photo.jpg")
        data = RecipeSerializer(uploaded).data
        self.assertEqual(data["image"], "/media/recipes/user-photo.jpg")
        self.assertIsNone(data["image_fallback"])
