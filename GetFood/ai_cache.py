"""Redis-backed hot cache for AI results.

All helpers go through Django's cache framework, so in Docker/Kubernetes they
hit Redis (``REDIS_URL``) and on bare-metal/tests they transparently use the
local-memory backend. A cache outage must never break a request: every helper
swallows backend errors and behaves like a cache miss.

Layers
------
* ``suggestions`` - ingredient-hash -> list of AI recipe ideas (24h). Sits in
  front of the durable ``AISuggestionCache`` table.
* ``detail``      - recipe/provider/model/language -> full chef recipe (24h).
  Avoids paying for the same LLM call every time a card is opened.
* ``task``        - Celery task id -> ingredient hash (15min), so the status
  endpoint can return the result of *that* task instead of "latest entry".
"""
import hashlib
import logging

from django.core.cache import cache

logger = logging.getLogger(__name__)

PREFIX = "wtc:ai"
SUGGESTIONS_TTL = 24 * 60 * 60
DETAIL_TTL = 24 * 60 * 60
TASK_TTL = 15 * 60


def _get(key):
    try:
        return cache.get(key)
    except Exception as exc:  # Redis down / misconfigured -> behave like a miss
        logger.warning("AI cache read failed (%s): %s", key, exc)
        return None


def _set(key, value, ttl):
    try:
        cache.set(key, value, ttl)
    except Exception as exc:
        logger.warning("AI cache write failed (%s): %s", key, exc)


# -- suggestions -------------------------------------------------------------

def is_degraded(recipes) -> bool:
    """True when the suggestions are the built-in culinary fallback (AI offline).

    Such answers must not be pinned in Redis or the DB for 24h: a short
    provider outage would otherwise outlive itself.
    """
    return isinstance(recipes, list) and any(
        isinstance(r, dict) and str(r.get("provider", "")).startswith("fallback") for r in recipes
    )


def get_suggestions(ingredients_hash: str):
    """Return a non-empty list of cached recipe ideas, else None."""
    value = _get(f"{PREFIX}:sug:{ingredients_hash}")
    return value if isinstance(value, list) and value else None


def set_suggestions(ingredients_hash: str, recipes) -> None:
    if isinstance(recipes, list) and recipes and not is_degraded(recipes):
        _set(f"{PREFIX}:sug:{ingredients_hash}", recipes, SUGGESTIONS_TTL)


# -- recipe detail -----------------------------------------------------------

def detail_key(recipe_name, provider, model, lang_code) -> str:
    raw = f"{(recipe_name or '').strip().lower()}|{provider or ''}|{model or ''}|{lang_code or ''}"
    return f"{PREFIX}:detail:{hashlib.sha256(raw.encode()).hexdigest()}"


def get_detail(key: str):
    value = _get(key)
    return value if isinstance(value, dict) else None


def set_detail(key: str, data: dict) -> None:
    if isinstance(data, dict) and data:
        _set(key, data, DETAIL_TTL)


# -- celery task bookkeeping ---------------------------------------------------

def remember_task(task_id: str, ingredients_hash: str) -> None:
    _set(f"{PREFIX}:task:{task_id}", ingredients_hash, TASK_TTL)


def task_hash(task_id: str):
    return _get(f"{PREFIX}:task:{task_id}")
