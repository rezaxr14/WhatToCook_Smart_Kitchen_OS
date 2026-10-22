"""Domain events (roadmap item 7).

Django signals publish small JSON events to RabbitMQ (through Celery, on the existing ``celery`` queue) and an
idempotent consumer records each one once. RabbitMQ delivers at least once, so the consumer must tolerate a replay:
the unique ``event_id`` on :class:`~GetFood.models.DomainEvent` is what makes recording the same event twice a no-op.

Publishing is best effort by design: it happens after the surrounding transaction commits, on a small background thread
(an unreachable broker makes kombu retry the connection for about six seconds, which the request must never wait for), and a
failure is logged, never raised. A pantry edit therefore cannot fail or slow down because RabbitMQ is down. The price is that
an event can be lost (broker down, backlog full, process killed): there is no outbox, so the event log is an audit trail, not
the source of truth.
"""
import atexit
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timezone as dt_timezone

from django.conf import settings
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import AISuggestionCache, DomainEvent, UserPantry

logger = logging.getLogger(__name__)

PANTRY_UPDATED = "pantry.updated"
RECIPE_GENERATED = "recipe.generated"
EVENT_TYPES = frozenset({PANTRY_UPDATED, RECIPE_GENERATED})

PANTRY_ACTIONS = {"post_add": "added", "post_remove": "removed", "post_clear": "cleared"}

# Publishes run on these threads. With the broker down each one blocks ~6s, so the backlog is capped: past MAX_PENDING an event is
# dropped (and logged) instead of piling up memory behind a dead broker.
MAX_PENDING = 200
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="domain-events")
_idle = threading.Condition()
_pending = 0


def build_event(event_type, payload):
    return {"id": str(uuid.uuid4()), "type": event_type, "occurred_at": timezone.now().isoformat(), "payload": payload}


def publish(event_type, payload):
    """Queue an event for the consumer once the current transaction has committed. Returns the event id, or None when disabled."""
    if not getattr(settings, "DOMAIN_EVENTS_ENABLED", True):
        return None
    event = build_event(event_type, payload)
    transaction.on_commit(lambda: _send(event))
    return event["id"]


def _send(event):
    """Hand the event to a background thread: the caller (a request, or a Celery task) never waits for the broker."""
    global _pending
    with _idle:
        if _pending >= MAX_PENDING:
            logger.warning("dropped %s event %s: %s publishes are already waiting on the broker", event["type"], event["id"], _pending)
            return
        _pending += 1
    _executor.submit(_publish, event)


def _publish(event):
    global _pending
    try:
        from .tasks import process_domain_event  # late: tasks imports this module

        process_domain_event.apply_async(args=[event], retry=False)
    except Exception:
        logger.warning("could not publish %s event %s", event["type"], event["id"], exc_info=True)
    finally:
        with _idle:
            _pending -= 1
            _idle.notify_all()


def flush(timeout=5.0):
    """Wait until every queued publish has finished (tests, clean shutdown). True when nothing is left waiting."""
    with _idle:
        return _idle.wait_for(lambda: _pending == 0, timeout)


atexit.register(flush, 2.0)  # a clean shutdown still pushes what is already queued


def consume(event):
    """Record one event exactly once. Returns "recorded", "duplicate" (already seen) or "rejected" (malformed, not retried)."""
    try:
        event_id = uuid.UUID(str(event["id"]))
        event_type = event["type"]
        occurred_at = parse_datetime(event["occurred_at"])
        payload = event["payload"]
    except (KeyError, TypeError, ValueError, AttributeError):
        occurred_at = payload = event_type = event_id = None
    if event_id is None or event_type not in EVENT_TYPES or occurred_at is None or not isinstance(payload, dict):
        logger.warning("rejected a malformed domain event (%s)", sorted(event) if isinstance(event, dict) else type(event).__name__)
        return "rejected"
    if timezone.is_naive(occurred_at):
        occurred_at = timezone.make_aware(occurred_at, dt_timezone.utc)
    _, created = DomainEvent.objects.get_or_create(
        event_id=event_id, defaults={"event_type": event_type, "payload": payload, "occurred_at": occurred_at}
    )
    return "recorded" if created else "duplicate"


@receiver(m2m_changed, sender=UserPantry.ingredients.through)
def pantry_changed(sender, instance, action, reverse, pk_set, **kwargs):
    """Every pantry edit goes through ``pantry.ingredients.add/remove/clear``, so one receiver covers every view.

    Django signals ``remove`` with the ids it was *asked* to remove and always signals ``clear``, so what was really
    present is read in the ``pre_`` step: an event means something changed, and ``ingredient_ids`` is what changed.
    """
    if reverse:  # edited from the Ingredient side; the app never does that
        return
    if action == "pre_remove":
        instance._event_ids = sorted(instance.ingredients.filter(pk__in=pk_set).values_list("pk", flat=True))
        return
    if action == "pre_clear":
        instance._event_ids = sorted(instance.ingredients.values_list("pk", flat=True))
        return
    if action not in PANTRY_ACTIONS:
        return
    ids = sorted(pk_set) if action == "post_add" else instance.__dict__.pop("_event_ids", [])
    if ids:  # adding what is already there, removing what is not, clearing an empty pantry: nothing changed
        publish(PANTRY_UPDATED, {"user_id": instance.user_id, "action": PANTRY_ACTIONS[action], "ingredient_ids": ids})


@receiver(post_save, sender=AISuggestionCache)
def suggestions_cached(sender, instance, raw=False, **kwargs):
    """AI suggestions are only cached when they are real (the AI-offline fallback is never cached), so this is "a recipe set was generated"."""
    if raw:  # loaddata / fixtures
        return
    recipes = instance.ai_response
    publish(RECIPE_GENERATED, {"ingredients_hash": instance.ingredients_hash, "count": len(recipes) if isinstance(recipes, list) else 0})
