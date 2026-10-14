try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay = lambda *a, **kw: None
            return func
        return decorator

from django.utils import timezone
from .models import AISuggestionCache
from . import ai_cache
from .ai_service import generate_recipe_suggestions


@shared_task(bind=True)
def generate_ai_suggestions_task(self, ingredients_list, ingredients_hash, provider=None, language=None):
    """
    Celery async task: generate AI-based recipe ideas from ingredients
    using Gemini, LM Studio, or intelligent culinary fallback.
    """
    try:
        recipes = generate_recipe_suggestions(ingredients_list, provider=provider, language=language)

        # Store in cache
        AISuggestionCache.objects.update_or_create(
            ingredients_hash=ingredients_hash,
            defaults={
                "ai_response": recipes,
                "created_at": timezone.now()
            }
        )

        ai_cache.set_suggestions(ingredients_hash, recipes)

        return {"status": "ok", "count": len(recipes)}

    except Exception as exc:
        AISuggestionCache.objects.update_or_create(
            ingredients_hash=ingredients_hash,
            defaults={
                "ai_response": {"error": str(exc)},
                "created_at": timezone.now()
            }
        )
        return {"status": "error", "error": str(exc)}
