from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Ingredient, Recipe, RecipeIngredient, UserPantry
from .images import (
    find_best_image,
    find_ingredient_image,
    image_fallback_url,
    local_media_url,
    subject_image_urls,
)
from .i18n import request_language


def _language(serializer) -> str:
    return request_language(serializer.context.get("request"))


class IngredientSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    image_fallback = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = [
            "id",
            "name",
            "display_name",
            "calories_per_100g",
            "category",
            "image_url",
            "image_fallback",
        ]

    def get_display_name(self, obj) -> str:
        return obj.display_name(_language(self))

    def get_image_url(self, obj) -> str:
        return find_ingredient_image(obj.name)

    def get_image_fallback(self, obj) -> str | None:
        local = find_ingredient_image(obj.name)
        if not local.startswith("/media/"):
            return None
        return image_fallback_url(local.removeprefix("/media/"))


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
    display_name = serializers.SerializerMethodField()
    display_description = serializers.SerializerMethodField()
    display_instructions = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    image_fallback = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = [
            "id",
            "name",
            "display_name",
            "description",
            "display_description",
            "cooking_time",
            "instructions",
            "display_instructions",
            "image",
            "image_url",
            "image_fallback",
            "ingredients",
            "recipe_ingredients",
        ]

    def _uploaded_image(self, obj) -> str | None:
        if obj.image and getattr(obj.image, "name", ""):
            # A same-origin path ("/media/..."), never an absolute URL: that would be built from the request's
            # Host, which proxies rewrite (Vite changeOrigin) or strip the port from (nginx $host), and the
            # SPA's CSP (img-src 'self') would then block the image.
            return local_media_url(obj.image.name)
        return None

    def _get_resolved_image(self, obj) -> str:
        return self._uploaded_image(obj) or find_best_image(obj.name)

    def get_display_name(self, obj) -> str:
        return obj.display_name(_language(self))

    def get_display_description(self, obj) -> str:
        return obj.display_description(_language(self))

    def get_display_instructions(self, obj) -> str:
        return obj.display_instructions(_language(self))

    def get_image(self, obj) -> str:
        return self._get_resolved_image(obj)

    def get_image_url(self, obj) -> str:
        return self._get_resolved_image(obj)

    def get_image_fallback(self, obj) -> str | None:
        uploaded = self._uploaded_image(obj)
        if uploaded:
            return image_fallback_url(uploaded.removeprefix("/media/"))
        _, fallback = subject_image_urls(obj.name)
        return fallback


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
