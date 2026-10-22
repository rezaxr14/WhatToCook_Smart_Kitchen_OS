"""Prove the domain-event round trip on a running stack: signal -> RabbitMQ -> worker -> DomainEvent row.

    docker compose exec web python manage.py check_domain_events [--deadline 30]

Creates a throwaway user, pantry and ingredient, adds, re-adds and removes the ingredient, and waits for the worker to
record exactly two events (added, removed): the re-add changes nothing, so it must not publish. Cleans up after itself.
A timeout means no worker consumes the `celery` queue, the broker is unreachable, or DOMAIN_EVENTS_ENABLED is off.
"""
import time
import uuid

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from GetFood.models import DomainEvent, Ingredient, UserPantry

SETTLE_SECONDS = 3  # after the expected events arrived: long enough for a wrongly published extra one to show up
EXPECTED = [("pantry.updated", "added"), ("pantry.updated", "removed")]


def judge(rows, ingredient_id):
    """rows: [(event_type, payload)] recorded for the throwaway user. Returns a list of problems (empty = pass)."""
    problems = []
    kinds = sorted((event_type, payload.get("action")) for event_type, payload in rows)
    if kinds != EXPECTED:
        problems.append(f"expected exactly one added and one removed pantry.updated event, got {kinds}")
    for _, payload in rows:
        if payload.get("ingredient_ids") != [ingredient_id]:
            problems.append(f"the {payload.get('action')} event carries ingredient_ids {payload.get('ingredient_ids')}, expected {[ingredient_id]}")
    return problems


class Command(BaseCommand):
    help = "Prove signal -> RabbitMQ -> worker -> DomainEvent on a running stack (creates and removes a throwaway user)."

    def add_arguments(self, parser):
        parser.add_argument("--deadline", type=int, default=30, help="seconds to wait for the worker to record the events")

    @staticmethod
    def recorded(user_id):
        return [(row.event_type, row.payload) for row in DomainEvent.objects.filter(payload__user_id=user_id)]

    def wait_for(self, user_id, deadline):
        end = time.monotonic() + deadline
        while time.monotonic() < end and len(self.recorded(user_id)) < len(EXPECTED):
            time.sleep(1)
        time.sleep(SETTLE_SECONDS)
        return self.recorded(user_id)

    def handle(self, *args, deadline, **options):
        if not settings.DOMAIN_EVENTS_ENABLED:
            raise CommandError("DOMAIN_EVENTS_ENABLED is off: nothing would be published")
        run = uuid.uuid4().hex[:8]
        user = User.objects.create_user(f"events-check-{run}", password=uuid.uuid4().hex)
        pantry = UserPantry.objects.create(user=user)
        ingredient = Ingredient.objects.create(name=f"events-check-{run}")
        try:
            pantry.ingredients.add(ingredient)
            pantry.ingredients.add(ingredient)  # already there: must not publish
            pantry.ingredients.remove(ingredient)
            rows = self.wait_for(user.id, deadline)
            problems = judge(rows, ingredient.id)
        finally:
            DomainEvent.objects.filter(payload__user_id=user.id).delete()
            user.delete()  # cascades to the pantry
            ingredient.delete()
        if problems:
            raise CommandError("; ".join(problems) + f" (waited up to {deadline}s: is a worker consuming the `celery` queue?)")
        self.stdout.write(self.style.SUCCESS("domain events OK: added and removed were published, consumed and recorded once each"))
