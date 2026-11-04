"""Fill the display-only translation fields from the shared serverless data.

Reversible: rolling back clears both fields (the English columns were never
touched). The English values stay canonical for matching, Telegram and tests.
"""

import json
from pathlib import Path

from django.conf import settings
from django.db import migrations


def load(name):
    return json.loads((Path(settings.BASE_DIR) / "GetFood" / "data" / name).read_text(encoding="utf-8"))


def forwards(apps, schema_editor):
    Ingredient = apps.get_model("GetFood", "Ingredient")
    Recipe = apps.get_model("GetFood", "Recipe")

    ingredients = load("ingredient-translations.json")
    for ingredient in Ingredient.objects.all():
        translations = ingredients.get(ingredient.name)
        if translations:
            ingredient.name_i18n = translations
            ingredient.save(update_fields=["name_i18n"])

    recipes = load("recipe-translations.json")
    for recipe in Recipe.objects.all():
        translations = recipes.get(recipe.name)
        if translations:
            recipe.translations = translations
            recipe.save(update_fields=["translations"])


def backwards(apps, schema_editor):
    Ingredient = apps.get_model("GetFood", "Ingredient")
    Recipe = apps.get_model("GetFood", "Recipe")
    Ingredient.objects.update(name_i18n={})
    Recipe.objects.update(translations={})


class Migration(migrations.Migration):
    dependencies = [
        ("GetFood", "0008_ingredient_name_i18n_recipe_translations"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
