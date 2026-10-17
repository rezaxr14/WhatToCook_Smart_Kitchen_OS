"""Locally stored media is always returned as a same-origin *path*, never an absolute URL.

An absolute URL is built from the request's Host. Behind a proxy that rewrites Host (Vite's
``changeOrigin``) or drops the port (nginx ``$host`` with a published port) it points at the wrong
origin, and the SPA's CSP (``img-src 'self'``) then blocks the image. A path is correct everywhere.
"""
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from GetFood.models import Ingredient, Recipe, RecipeIngredient
from GetFood.serializers import RecipeSerializer


class MediaUrlTests(TestCase):
    def setUp(self):
        self.recipe = Recipe.objects.create(name="Shakshuka", instructions="Cook.", image="recipes/shakshuka.jpg")
        RecipeIngredient.objects.create(recipe=self.recipe, ingredient=Ingredient.objects.create(name="Egg"))

    def test_serializer_returns_a_path_even_with_a_request_in_context(self):
        request = RequestFactory().get("/api/recipes/", HTTP_HOST="127.0.0.1:8000")
        data = RecipeSerializer(self.recipe, context={"request": request}).data
        self.assertEqual(data["image"], "/media/recipes/shakshuka.jpg")
        self.assertEqual(data["image_url"], "/media/recipes/shakshuka.jpg")

    def test_api_ignores_the_host_header_when_building_image_urls(self):
        for host in ("127.0.0.1:8000", "localhost", "localhost:4173"):
            response = APIClient().get(reverse("recipe-list"), HTTP_HOST=host)
            self.assertEqual(response.status_code, 200)
            rows = response.data["results"] if isinstance(response.data, dict) else response.data
            mine = next(r for r in rows if r["name"] == "Shakshuka")
            self.assertEqual(mine["image_url"], "/media/recipes/shakshuka.jpg", host)
            self.assertNotIn("://", mine["image"], host)

    def test_recipes_without_an_uploaded_image_still_get_a_fallback(self):
        bare = Recipe.objects.create(name="Plain omelette", instructions="Whisk.")
        data = RecipeSerializer(bare, context={"request": RequestFactory().get("/")}).data
        self.assertTrue(data["image_url"])
