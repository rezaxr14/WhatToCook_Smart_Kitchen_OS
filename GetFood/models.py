from datetime import timedelta
import secrets

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Ingredient(models.Model):
    name = models.CharField(max_length=100, unique=True)
    calories_per_100g = models.FloatField(null=True, blank=True)
    category = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    cooking_time = models.IntegerField(help_text="Time in minutes", null=True, blank=True)
    instructions = models.TextField(blank=True)
    image = models.ImageField(upload_to="recipes/", blank=True, null=True)
    ingredients = models.ManyToManyField(Ingredient, through='RecipeIngredient')

    def __str__(self):
        return self.name

    @property
    def resolved_image(self) -> str:
        """Uploaded image if present, otherwise a curated photo for the dish.
        Used by both the DRF serializer and legacy templates so every surface
        shows a real image."""
        from .utils import find_best_image

        if self.image and getattr(self.image, "name", ""):
            try:
                return self.image.url
            except ValueError:
                pass
        return find_best_image(self.name)


class RecipeIngredient(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity = models.CharField(max_length=100, default="to taste")
    unit = models.CharField(max_length=20, default="g")

    def __str__(self):
        return f"{self.quantity}{self.unit} {self.ingredient.name} for {self.recipe.name}"


class UserPantry(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    ingredients = models.ManyToManyField(Ingredient, blank=True)

    def __str__(self):
        return f"{self.user.username}'s Pantry"


class AISuggestionCache(models.Model):
    ingredients_hash = models.CharField(max_length=255, unique=True)
    ai_response = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Cache for {self.ingredients_hash}"


class TelegramAccountLink(models.Model):
    """Links WhatToCook web user account to Telegram chat."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram_link")
    telegram_chat_id = models.CharField(max_length=64, unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=128, null=True, blank=True)
    auth_token = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_token_for_user(cls, user):
        link, created = cls.objects.get_or_create(
            user=user,
            defaults={"auth_token": secrets.token_urlsafe(16)}
        )
        if not link.auth_token:
            link.auth_token = secrets.token_urlsafe(16)
            link.save()
        return link

    def __str__(self):
        return f"{self.user.username} (TG: {self.telegram_chat_id or 'Pending'})"


class ShoppingListItem(models.Model):
    """Stores user grocery shopping items with checked state, category, and recipe origin."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shopping_items", null=True, blank=True)
    session_key = models.CharField(max_length=64, blank=True, default="")
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, default="General", blank=True)
    quantity = models.CharField(max_length=100, default="1 item", blank=True)
    checked = models.BooleanField(default=False)
    added_from = models.CharField(max_length=150, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["checked", "-created_at"]

    def __str__(self):
        return f"{self.name} ({'✓' if self.checked else '○'})"


class DomainEvent(models.Model):
    """One consumed domain event (roadmap item 7). The unique event_id makes the consumer idempotent: a redelivered event is a no-op."""

    event_id = models.UUIDField(unique=True)
    event_type = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["recorded_at"]

    def __str__(self):
        return f"{self.event_type} {self.event_id}"


@receiver(post_save, sender=AISuggestionCache)
def clean_expired_ai_caches(sender, **kwargs):
    """Delete AI suggestions older than 3 days."""
    expiry_time = timezone.now() - timedelta(days=3)
    AISuggestionCache.objects.filter(created_at__lt=expiry_time).delete()

