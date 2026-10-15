try:
    from celery import shared_task
except ImportError:
    def shared_task(*args, **kwargs):
        def decorator(func):
            func.delay = lambda *a, **kw: None
            return func
        return decorator

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from . import ai_cache
from .ai_service import generate_recipe_suggestions
from .models import AISuggestionCache

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,       # 1s, 2s, 4s ... capped below
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def generate_ai_suggestions_task(self, ingredients_list, ingredients_hash, provider=None, language=None):
    """
    Celery async task: generate AI-based recipe ideas from ingredients
    using Gemini, LM Studio, or intelligent culinary fallback.

    Unexpected errors are retried with exponential backoff; once retries are
    exhausted the task ends in FAILURE and the status endpoint reports
    ``status: "error"``. A failure never overwrites a previously cached good
    answer, and the AI-offline fallback is never cached.
    """
    recipes = generate_recipe_suggestions(ingredients_list, provider=provider, language=language)

    # The recipes travel in the task's own result (Celery result backend = Redis), so the
    # poller gets them even when we deliberately refuse to cache a degraded answer.
    if ai_cache.is_degraded(recipes):
        return {"status": "ok", "count": len(recipes), "degraded": True, "recipes": recipes}

    AISuggestionCache.objects.update_or_create(
        ingredients_hash=ingredients_hash,
        defaults={"ai_response": recipes, "created_at": timezone.now()},
    )
    ai_cache.set_suggestions(ingredients_hash, recipes)
    return {"status": "ok", "count": len(recipes), "degraded": False, "recipes": recipes}


@shared_task
def cleanup_expired_ai_cache(max_age_days=None):
    """Housekeeping (Celery beat): drop AISuggestionCache rows nobody can hit any more.

    Suggestions are only served for 24h, so anything older than the retention
    window (default 7 days, ``AI_CACHE_RETENTION_DAYS``) is dead weight.
    """
    days = max_age_days if max_age_days is not None else getattr(settings, "AI_CACHE_RETENTION_DAYS", 7)
    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = AISuggestionCache.objects.filter(created_at__lt=cutoff).delete()
    logger.info("AI cache cleanup removed %s rows older than %s days", deleted, days)
    return {"deleted": deleted, "older_than_days": days}
