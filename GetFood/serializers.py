from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Ingredient, Recipe, RecipeIngredient, UserPantry
from .utils import find_best_image, find_ingredient_image


class IngredientSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = ["id", "name", "calories_per_100g", "category", "image_url"]

    def get_image_url(self, obj) -> str:
        return find_ingredient_image(obj.name)


class RecipeIngredientSerializer(serializers.ModelSerializer):
    ingredient = IngredientSerializer(read_only=True)
    ingredient_id = serializers.PrimaryKeyRelatedField(
        queryset=Ingredient.objects.all(), source="ingredient", write_only=True
    )

    class Meta:
        model = RecipeIngredient
        fields = ["id", "ingredient", "ingredient_id", "quantity", "unit"]


class RecipeSerializer(serializers.ModelSerializer):
    ingredients = IngredientSerializer(many=True, read_only=True)
    recipe_ingredients = RecipeIngredientSerializer(source="recipeingredient_set", many=True, read_only=True)
    image = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "name",
            "description",
            "cooking_time",
            "instructions",
            "image",
            "image_url",
            "ingredients",
            "recipe_ingredients",
        ]

    def _get_resolved_image(self, obj):
        if obj.image and hasattr(obj.image, "url") and obj.image.name:
            # A same-origin path ("/media/..."), never an absolute URL: that would be built from the request's
            # Host, which proxies rewrite (Vite changeOrigin) or strip the port from (nginx $host), and the
            # SPA's CSP (img-src 'self') would then block the image.
            return obj.image.url
        return find_best_image(obj.name)

    def get_image(self, obj) -> str:
        return self._get_resolved_image(obj)

    def get_image_url(self, obj) -> str:
        return self._get_resolved_image(obj)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class UserPantrySerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    ingredients = IngredientSerializer(many=True, read_only=True)
    total_ingredients = serializers.IntegerField(source="ingredients.count", read_only=True)

    class Meta:
        model = UserPantry
        fields = ["id", "user", "ingredients", "total_ingredients"]
