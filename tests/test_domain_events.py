"""Domain events (roadmap item 7): signals publish pantry.updated / recipe.generated, an idempotent consumer records them.

No broker is involved: the publish is mocked (``apply_async``) and the consumer is called directly or eagerly.
"""
import logging
import subprocess
import sys
import uuid
import warnings
from pathlib import Path
from datetime import timedelta
from unittest import mock

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.signals import m2m_changed, post_save
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from GetFood import events
from GetFood.models import AISuggestionCache, DomainEvent, Ingredient, UserPantry
from GetFood.tasks import cleanup_old_domain_events, process_domain_event

ROOT = Path(__file__).resolve().parent.parent
SEND = "GetFood.tasks.process_domain_event.apply_async"


def make_event(**overrides):
    event = {"id": str(uuid.uuid4()), "type": "pantry.updated", "occurred_at": timezone.now().isoformat(), "payload": {"user_id": 1}}
    event.update(overrides)
    return event


@override_settings(DOMAIN_EVENTS_ENABLED=True)
class PantrySignalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cook", password="x" * 12)
        self.pantry = UserPantry.objects.create(user=self.user)
        self.egg = Ingredient.objects.create(name="egg")
        self.salt = Ingredient.objects.create(name="salt")

    def published(self, action):
        """Run `action`, commit, and return the events handed to the broker (in order)."""
        with mock.patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            action()
        return [call.kwargs["args"][0] for call in send.call_args_list]

    def test_adding_publishes_one_event_with_the_added_ids(self):
        (event,) = self.published(lambda: self.pantry.ingredients.add(self.salt, self.egg))
        self.assertEqual(event["type"], "pantry.updated")
        self.assertEqual(event["payload"], {"user_id": self.user.id, "action": "added", "ingredient_ids": sorted([self.egg.id, self.salt.id])})

    def test_removing_publishes_a_removed_event(self):
        self.pantry.ingredients.add(self.egg)
        (event,) = self.published(lambda: self.pantry.ingredients.remove(self.egg))
        self.assertEqual(event["payload"], {"user_id": self.user.id, "action": "removed", "ingredient_ids": [self.egg.id]})

    def test_clearing_publishes_a_cleared_event_with_what_was_there(self):
        self.pantry.ingredients.add(self.egg, self.salt)
        (event,) = self.published(lambda: self.pantry.ingredients.clear())
        self.assertEqual(event["payload"], {"user_id": self.user.id, "action": "cleared", "ingredient_ids": sorted([self.egg.id, self.salt.id])})

    def test_removing_several_reports_only_those_that_were_there(self):
        self.pantry.ingredients.add(self.egg)
        (event,) = self.published(lambda: self.pantry.ingredients.remove(self.egg, self.salt))
        self.assertEqual(event["payload"]["ingredient_ids"], [self.egg.id])

    def test_a_change_that_changes_nothing_publishes_nothing(self):
        self.pantry.ingredients.add(self.egg)
        self.assertEqual(self.published(lambda: self.pantry.ingredients.add(self.egg)), [])  # already there
        self.assertEqual(self.published(lambda: self.pantry.ingredients.remove(self.salt)), [])  # never was
        self.pantry.ingredients.clear()
        self.assertEqual(self.published(lambda: self.pantry.ingredients.clear()), [])  # already empty

    def test_editing_from_the_ingredient_side_publishes_nothing(self):
        self.assertEqual(self.published(lambda: self.egg.userpantry_set.add(self.pantry)), [])

    def test_nothing_is_sent_before_the_transaction_commits(self):
        with mock.patch(SEND) as send:
            with self.captureOnCommitCallbacks(execute=False) as callbacks:
                self.pantry.ingredients.add(self.egg)
            send.assert_not_called()
            self.assertEqual(len(callbacks), 1)
            callbacks[0]()
            send.assert_called_once()

    def test_each_event_has_its_own_id_and_a_timestamp(self):
        first, second = self.published(lambda: (self.pantry.ingredients.add(self.egg), self.pantry.ingredients.add(self.salt)))
        self.assertNotEqual(first["id"], second["id"])
        uuid.UUID(first["id"])
        self.assertIsNotNone(events.parse_datetime(first["occurred_at"]))

    def test_the_real_endpoint_publishes_through_the_signal(self):
        client = APIClient()
        client.force_authenticate(self.user)
        with mock.patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(client.post(reverse("api_pantry_add"), {"ingredient_id": self.egg.id}, format="json").status_code, 200)
        (call,) = send.call_args_list
        self.assertEqual(call.kwargs["args"][0]["payload"]["ingredient_ids"], [self.egg.id])

    def test_disabled_publishes_nothing(self):
        with override_settings(DOMAIN_EVENTS_ENABLED=False):
            self.assertEqual(self.published(lambda: self.pantry.ingredients.add(self.egg)), [])


@override_settings(DOMAIN_EVENTS_ENABLED=True)
class RecipeSignalTests(TestCase):
    def published(self, action):
        with mock.patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            action()
        return [call.kwargs["args"][0] for call in send.call_args_list]

    def test_caching_suggestions_publishes_recipe_generated_with_the_count(self):
        (event,) = self.published(lambda: AISuggestionCache.objects.create(ingredients_hash="h1", ai_response=[{"name": "a"}, {"name": "b"}]))
        self.assertEqual(event["type"], "recipe.generated")
        self.assertEqual(event["payload"], {"ingredients_hash": "h1", "count": 2})

    def test_regenerating_the_same_hash_publishes_again(self):
        AISuggestionCache.objects.create(ingredients_hash="h1", ai_response=[{"name": "a"}])
        (event,) = self.published(lambda: AISuggestionCache.objects.update_or_create(ingredients_hash="h1", defaults={"ai_response": [1, 2, 3]}))
        self.assertEqual(event["payload"], {"ingredients_hash": "h1", "count": 3})

    def test_a_non_list_response_counts_zero(self):
        (event,) = self.published(lambda: AISuggestionCache.objects.create(ingredients_hash="h2", ai_response={"error": "x"}))
        self.assertEqual(event["payload"]["count"], 0)

    def test_loading_fixtures_publishes_nothing(self):
        with mock.patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            events.suggestions_cached(AISuggestionCache, AISuggestionCache(ingredients_hash="h", ai_response=[]), raw=True)
        send.assert_not_called()


@override_settings(DOMAIN_EVENTS_ENABLED=True)
class PublishFailureTests(TestCase):
    def test_a_broker_outage_is_logged_and_never_raised(self):
        with self.assertLogs("GetFood.events", logging.WARNING) as logs:  # the send runs when the commit callbacks do
            with mock.patch(SEND, side_effect=ConnectionError("rabbitmq is down")), self.captureOnCommitCallbacks(execute=True):
                self.assertIsNotNone(events.publish("pantry.updated", {"user_id": 1}))
        self.assertIn("could not publish pantry.updated", logs.output[0])

    def test_the_publish_does_not_retry_so_a_down_broker_cannot_stall_the_request(self):
        with mock.patch(SEND) as send, self.captureOnCommitCallbacks(execute=True):
            events.publish("pantry.updated", {"user_id": 1})
        self.assertIs(send.call_args.kwargs["retry"], False)


class ConsumerTests(TestCase):
    def test_a_valid_event_is_recorded(self):
        event = make_event(payload={"user_id": 7, "action": "added"})
        self.assertEqual(events.consume(event), "recorded")
        row = DomainEvent.objects.get()
        self.assertEqual((str(row.event_id), row.event_type, row.payload), (event["id"], "pantry.updated", {"user_id": 7, "action": "added"}))

    def test_a_redelivered_event_is_recorded_once(self):
        event = make_event()
        self.assertEqual(events.consume(event), "recorded")
        self.assertEqual(events.consume(event), "duplicate")
        self.assertEqual(events.consume(dict(event)), "duplicate")
        self.assertEqual(DomainEvent.objects.count(), 1)

    def test_two_events_with_the_same_content_but_different_ids_are_two_events(self):
        self.assertEqual(events.consume(make_event()), "recorded")
        self.assertEqual(events.consume(make_event()), "recorded")
        self.assertEqual(DomainEvent.objects.count(), 2)

    def test_malformed_events_are_rejected_without_raising_or_recording(self):
        good = make_event()
        bad = [
            None, "text", 42, {}, {k: v for k, v in good.items() if k != "id"}, {**good, "id": "not-a-uuid"}, {**good, "type": "pantry.exploded"},
            {**good, "occurred_at": "yesterday"}, {**good, "occurred_at": None}, {**good, "payload": [1, 2]}, {**good, "payload": None},
        ]
        for event in bad:
            with self.subTest(event=event), self.assertLogs("GetFood.events", logging.WARNING):
                self.assertEqual(events.consume(event), "rejected")
        self.assertEqual(DomainEvent.objects.count(), 0)

    def test_a_timestamp_without_a_zone_is_stored_as_utc_without_a_naive_datetime_warning(self):
        with warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)  # Django warns, then guesses, when it is handed a naive datetime
            self.assertEqual(events.consume(make_event(occurred_at="2026-10-21T12:00:00")), "recorded")
        self.assertEqual(DomainEvent.objects.get().occurred_at.utcoffset(), timedelta(0))

    def test_the_task_is_the_same_idempotent_consumer(self):
        event = make_event(type="recipe.generated", payload={"ingredients_hash": "h", "count": 1})
        self.assertEqual(process_domain_event.apply(args=[event]).get(), "recorded")
        self.assertEqual(process_domain_event.apply(args=[event]).get(), "duplicate")
        self.assertEqual(DomainEvent.objects.count(), 1)

    def test_end_to_end_a_published_event_is_consumed_once_even_if_delivered_twice(self):
        user = User.objects.create_user("e2e", password="x" * 12)
        pantry = UserPantry.objects.create(user=user)
        egg = Ingredient.objects.create(name="egg")
        sent = []
        with override_settings(DOMAIN_EVENTS_ENABLED=True), mock.patch(SEND, side_effect=lambda **kw: sent.append(kw["args"][0])):
            with self.captureOnCommitCallbacks(execute=True):
                pantry.ingredients.add(egg)
        (event,) = sent
        for _ in range(2):  # at-least-once delivery
            process_domain_event.apply(args=[event])
        (row,) = DomainEvent.objects.all()
        self.assertEqual(row.payload, {"user_id": user.id, "action": "added", "ingredient_ids": [egg.id]})


class CleanupTests(TestCase):
    def test_only_rows_past_retention_are_deleted(self):
        old = DomainEvent.objects.create(event_id=uuid.uuid4(), event_type="pantry.updated", payload={}, occurred_at=timezone.now())
        fresh = DomainEvent.objects.create(event_id=uuid.uuid4(), event_type="pantry.updated", payload={}, occurred_at=timezone.now())
        DomainEvent.objects.filter(pk=old.pk).update(recorded_at=timezone.now() - timedelta(days=31))
        result = cleanup_old_domain_events()
        self.assertEqual(result, {"deleted": 1, "older_than_days": 30})
        self.assertEqual(list(DomainEvent.objects.values_list("pk", flat=True)), [fresh.pk])

    def test_the_window_is_a_setting_and_an_argument(self):
        row = DomainEvent.objects.create(event_id=uuid.uuid4(), event_type="pantry.updated", payload={}, occurred_at=timezone.now())
        DomainEvent.objects.filter(pk=row.pk).update(recorded_at=timezone.now() - timedelta(days=5))
        self.assertEqual(cleanup_old_domain_events(max_age_days=10)["deleted"], 0)
        with override_settings(DOMAIN_EVENT_RETENTION_DAYS=3):
            self.assertEqual(cleanup_old_domain_events()["deleted"], 1)


class WiringTests(TestCase):
    def test_the_receivers_are_connected_by_the_app_config(self):
        self.assertTrue(m2m_changed.has_listeners(UserPantry.ingredients.through))
        self.assertTrue(post_save.has_listeners(AISuggestionCache))

    def test_a_fresh_process_has_the_receivers_connected_by_ready_alone(self):
        # in this process the test module and tasks import GetFood.events themselves, which would hide a missing ready()
        code = (
            "import django; django.setup()\n"
            "from django.db.models.signals import m2m_changed, post_save\n"
            "from GetFood.models import AISuggestionCache, UserPantry\n"
            "print(m2m_changed.has_listeners(UserPantry.ingredients.through), post_save.has_listeners(AISuggestionCache))\n"
        )
        env = {"PATH": "", "DJANGO_SETTINGS_MODULE": "WhatToCook.settings", "USE_POSTGRES": "false", "DEBUG": "true", "SECRET_KEY": "x" * 50}
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(result.stdout.strip(), "True True", result.stderr[-800:])

    def test_the_consumer_goes_to_a_queue_every_worker_consumes_and_cleanup_to_maintenance(self):
        routes = settings.CELERY_TASK_ROUTES
        self.assertEqual(routes["GetFood.tasks.process_domain_event"], {"queue": "celery"})
        self.assertEqual(routes["GetFood.tasks.cleanup_old_domain_events"], {"queue": "maintenance"})
        self.assertEqual(process_domain_event.name, "GetFood.tasks.process_domain_event")
        self.assertEqual(cleanup_old_domain_events.name, "GetFood.tasks.cleanup_old_domain_events")

    def test_the_cleanup_is_scheduled(self):
        entry = settings.CELERY_BEAT_SCHEDULE["cleanup-old-domain-events"]
        self.assertEqual(entry["task"], "GetFood.tasks.cleanup_old_domain_events")

    def test_events_are_off_under_the_test_runner_so_no_other_test_needs_a_broker(self):
        self.assertFalse(settings.DOMAIN_EVENTS_ENABLED)
