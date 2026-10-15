from django.urls import reverse
from django.test import TestCase
from django.contrib.auth.models import User
from GetFood.models import Ingredient, UserPantry, AISuggestionCache


class AISuggestionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="tester", password="1234")
        self.client.login(username="tester", password="1234")
        ingredient = Ingredient.objects.create(name="tomato")
        pantry = UserPantry.objects.create(user=self.user)
        pantry.ingredients.add(ingredient)

    def test_ai_suggestions_returns_json(self):
        url = reverse("ai_suggestions_api")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("recipes", data)
        self.assertIsInstance(data["recipes"], list)

    def test_cache_storage(self):
        Ingredient.objects.create(name="onion")
        AISuggestionCache.objects.create(
            ingredients_hash="fakehash",
            ai_response=[{"name": "Tomato Soup"}]
        )
        self.assertEqual(AISuggestionCache.objects.count(), 1)
