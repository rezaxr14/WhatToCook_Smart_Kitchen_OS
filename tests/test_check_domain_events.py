"""manage.py check_domain_events: the verdict logic, the safety refusals, and the command against a stand-in worker.

The real round trip needs the compose stack (`docker compose exec web python manage.py check_domain_events`); here the broker is
replaced by a patched ``apply_async`` that consumes inline, which is what a healthy worker would do, and the background publisher
is made synchronous so no second thread writes to the in-memory test database while the command polls it.
"""
import io
import uuid
from unittest import mock

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db.models.signals import m2m_changed
from django.utils import timezone
from django.test import SimpleTestCase, TransactionTestCase, override_settings

from GetFood import events
from GetFood.management.commands.check_domain_events import judge
from GetFood.models import DomainEvent, Ingredient, UserPantry

SEND = "GetFood.tasks.process_domain_event.apply_async"
SLEEP = "GetFood.management.commands.check_domain_events.time.sleep"


class SyncExecutor:
    """Stands in for events._executor: run the publish on the calling thread."""

    def submit(self, fn, *args):
        fn(*args)


def row(action="added", ids=(7,), event_type="pantry.updated"):
    return event_type, {"user_id": 1, "action": action, "ingredient_ids": list(ids)}


class JudgeTests(SimpleTestCase):
    def test_one_added_and_one_removed_with_the_right_ids_passes(self):
        self.assertEqual(judge([row("removed"), row("added")], 7), [])

    def test_a_missing_event_fails(self):
        self.assertTrue(judge([row("added")], 7))
        self.assertTrue(judge([], 7))

    def test_a_stray_extra_event_fails(self):
        self.assertTrue(judge([row("added"), row("added"), row("removed")], 7))

    def test_the_wrong_ingredient_ids_fail(self):
        self.assertTrue(judge([row("added", ids=(8,)), row("removed")], 7))

    def test_the_wrong_event_type_fails(self):
        self.assertTrue(judge([row("added"), row("removed", event_type="recipe.generated")], 7))


class CommandTests(TransactionTestCase):
    def run_command(self, send, **options):
        out = io.StringIO()
        with override_settings(DOMAIN_EVENTS_ENABLED=True), mock.patch(SEND, side_effect=send), mock.patch(SLEEP):
            with mock.patch.object(events, "_executor", SyncExecutor()):
                call_command("check_domain_events", stdout=out, **options)
        return out.getvalue()

    @staticmethod
    def healthy_worker(**kwargs):
        events.consume(kwargs["args"][0])

    def assert_cleaned_up(self):
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(UserPantry.objects.count(), 0)
        self.assertEqual(Ingredient.objects.count(), 0)
        self.assertEqual(DomainEvent.objects.count(), 0)

    def test_a_healthy_worker_passes_and_everything_is_cleaned_up(self):
        self.assertIn("domain events OK", self.run_command(self.healthy_worker))
        self.assert_cleaned_up()

    def test_no_worker_fails_with_a_hint_and_still_cleans_up(self):
        with self.assertRaisesMessage(CommandError, "is a worker consuming the `celery` queue?"):
            self.run_command(lambda **kwargs: None, deadline=0)
        self.assert_cleaned_up()

    def test_a_worker_that_records_a_stray_extra_event_fails(self):
        def noisy_worker(**kwargs):
            event = kwargs["args"][0]
            events.consume(event)
            events.consume({**event, "id": "00000000-0000-4000-8000-000000000001"})  # a second event nobody should have published

        with self.assertRaisesMessage(CommandError, "expected exactly one added and one removed"):
            self.run_command(noisy_worker)
        self.assert_cleaned_up()

    def test_it_refuses_when_events_are_disabled(self):
        with self.assertRaisesMessage(CommandError, "DOMAIN_EVENTS_ENABLED is off"), mock.patch(SLEEP):
            call_command("check_domain_events", deadline=0)  # (a mutant that did not refuse would otherwise wait out the default deadline)
        self.assert_cleaned_up()

    def test_it_ignores_and_never_deletes_other_peoples_events(self):
        other = DomainEvent.objects.create(event_id=uuid.uuid4(), event_type="pantry.updated", payload={"user_id": 999999, "action": "added", "ingredient_ids": [1]},
                                           occurred_at=timezone.now())
        self.assertIn("domain events OK", self.run_command(self.healthy_worker))
        self.assertEqual(list(DomainEvent.objects.values_list("pk", flat=True)), [other.pk])

    def test_a_signal_that_publishes_for_a_no_op_add_is_caught_by_the_re_add_step(self):
        def regression(sender, instance, action, reverse, pk_set, **kwargs):  # what a broken receiver would do: announce an add that added nothing
            if action == "post_add" and not reverse and not pk_set:
                events.publish(events.PANTRY_UPDATED, {"user_id": instance.user_id, "action": "added", "ingredient_ids": [1]})

        m2m_changed.connect(regression, sender=UserPantry.ingredients.through)
        self.addCleanup(m2m_changed.disconnect, regression, sender=UserPantry.ingredients.through)
        with self.assertRaisesMessage(CommandError, "expected exactly one added and one removed"):
            self.run_command(self.healthy_worker)
        self.assert_cleaned_up()
