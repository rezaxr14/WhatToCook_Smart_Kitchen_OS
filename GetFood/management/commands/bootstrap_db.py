"""Concurrency-safe database bootstrap: migrate + seed under a Postgres advisory lock.

Several ``web`` replicas (Kubernetes rollout, HPA scale-out, compose scale) may
boot at the same moment. Django's ``migrate`` is not safe to run concurrently,
so every replica takes the same advisory lock first; the first one migrates,
the others wait, then find nothing left to do. SQLite (bare-metal) needs no lock.
"""
import contextlib

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

LOCK_ID = 7_265_001  # arbitrary, app-wide constant


@contextlib.contextmanager
def advisory_lock(conn, lock_id=LOCK_ID):
    if conn.vendor != "postgresql":
        yield
        return
    with conn.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_id])
    try:
        yield
    finally:
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_id])


class Command(BaseCommand):
    help = "Apply migrations and seed reference data, safe to run from many replicas at once."

    def add_arguments(self, parser):
        parser.add_argument("--no-seed", action="store_true", help="Only migrate.")

    def handle(self, *args, **options):
        with advisory_lock(connection):
            self.stdout.write("Applying database migrations...")
            call_command("migrate", interactive=False, verbosity=1)
            if not options["no_seed"]:
                self.stdout.write("Seeding ingredients & recipes (idempotent)...")
                try:
                    call_command("seed_recipes")
                except Exception as exc:  # non-fatal: same contract as the old entrypoint
                    self.stderr.write(f"Seed skipped: {exc}")
