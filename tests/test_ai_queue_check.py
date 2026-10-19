"""scripts/check_ai_queue.py: the drain logic, the generated in-container code, and the safety guards.

The check itself needs the compose stack (the nightly load workflow runs it); everything that can be decided without
one (how stats are read, when a queue counts as drained, that a configured API key aborts BEFORE anything is published)
is tested here with fake stacks and a fake clock.
"""
import importlib.util
import json
from pathlib import Path

from django.test import SimpleTestCase

_SPEC = importlib.util.spec_from_file_location("check_ai_queue", Path(__file__).resolve().parent.parent / "scripts" / "check_ai_queue.py")
chk = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(chk)


def snap(ready=0, unacked=0, publish=0, ack=0, consumers=1):
    return {"ready": ready, "unacked": unacked, "publish": publish, "ack": ack, "consumers": consumers}


class Clock:
    """Deterministic time: sleeping advances it, so deadlines are exercised without waiting."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def sequence(*snaps):
    """fetch() that replays `snaps`, then repeats the last one."""
    items = list(snaps)
    return lambda: items.pop(0) if len(items) > 1 else items[0]


class ParseQueueTests(SimpleTestCase):
    def test_reads_the_management_api_fields(self):
        payload = {"messages_ready": 3, "messages_unacknowledged": 2, "consumers": 1, "message_stats": {"publish": 10, "ack": 5}}
        self.assertEqual(chk.parse_queue(payload), snap(ready=3, unacked=2, publish=10, ack=5, consumers=1))

    def test_a_queue_that_never_saw_traffic_has_no_message_stats(self):
        self.assertEqual(chk.parse_queue({"messages_ready": 0, "messages_unacknowledged": 0, "consumers": 2}), snap(consumers=2))

    def test_parse_marker_ignores_noise_and_requires_the_marker(self):
        self.assertEqual(chk.parse_marker('warning: x\nWTC_IDS ["a", "b"]\n', "WTC_IDS"), ["a", "b"])
        with self.assertRaises(ValueError):
            chk.parse_marker("nothing here", "WTC_IDS")


class DrainTests(SimpleTestCase):
    def drain(self, fetch, tasks=10, deadline=30):
        clock = Clock()
        return chk.wait_for_drain(fetch, tasks, snap(), deadline, interval=2, clock=clock, sleep=clock.sleep)

    def test_drains_after_a_backlog_and_reports_the_peak(self):
        out = self.drain(sequence(snap(ready=10, publish=10), snap(ready=4, unacked=2, publish=10, ack=4), snap(publish=10, ack=10)))
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["peak"], 10)

    def test_a_single_empty_reading_is_not_enough(self):
        # Stats are sampled: one empty poll between non-empty ones must not count as drained.
        out = self.drain(sequence(snap(publish=10, ack=10), snap(ready=1, publish=10, ack=10)), deadline=10)
        self.assertFalse(out["ok"])

    def test_empty_queue_without_acks_is_not_a_drain(self):
        out = self.drain(sequence(snap(publish=10, ack=3)), deadline=10)
        self.assertFalse(out["ok"])
        self.assertIn("acks", out["reason"])

    def test_messages_that_never_reached_the_ai_queue_are_reported_as_a_routing_problem(self):
        out = self.drain(sequence(snap(publish=2, ack=2)), deadline=10)
        self.assertFalse(out["ok"])
        self.assertIn("CELERY_TASK_ROUTES", out["reason"])

    def test_a_backlog_nobody_consumes_names_the_missing_worker(self):
        out = self.drain(sequence(snap(ready=10, publish=10, consumers=0)), deadline=10)
        self.assertFalse(out["ok"])
        self.assertIn("no consumer", out["reason"])

    def test_a_slow_worker_times_out_with_the_remaining_backlog(self):
        out = self.drain(sequence(snap(ready=7, unacked=1, publish=10, ack=2)), deadline=10)
        self.assertFalse(out["ok"])
        self.assertIn("7 ready", out["reason"])

    def test_an_invisible_queue_times_out_instead_of_crashing(self):
        out = self.drain(lambda: None, deadline=6)
        self.assertFalse(out["ok"])
        self.assertIn("never became visible", out["reason"])

    def test_the_deadline_is_honoured(self):
        clock = Clock()
        chk.wait_for_drain(lambda: snap(ready=1, publish=10), 10, snap(), 30, interval=2, clock=clock, sleep=clock.sleep)
        self.assertGreaterEqual(clock.now, 30)
        self.assertLess(clock.now, 34)


class GeneratedCodeTests(SimpleTestCase):
    def test_every_snippet_is_valid_python(self):
        for code in (chk.enqueue_code(3, "abc12345"), chk.key_probe_code(), chk.verify_code(["x", "y"])):
            compile(code, "<snippet>", "exec")

    def test_the_burst_pins_the_provider_so_a_stray_default_cannot_call_out(self):
        code = chk.enqueue_code(7, "abc12345")
        self.assertIn("range(7)", code)
        self.assertIn("provider='gemini'", code)
        self.assertIn("generate_ai_suggestions_task", code)

    def test_verify_demands_success_and_the_degraded_fallback(self):
        ok = {"total": 5, "states": {"SUCCESS": 5}, "bad": 0}
        self.assertTrue(chk.results_ok(ok, 5))
        self.assertFalse(chk.results_ok({**ok, "states": {"SUCCESS": 4, "PENDING": 1}}, 5))
        self.assertFalse(chk.results_ok({**ok, "bad": 1}, 5))
        self.assertFalse(chk.results_ok({**ok, "total": 4, "states": {"SUCCESS": 4}}, 5))

    def test_the_ids_survive_the_round_trip_into_the_verify_snippet(self):
        ids = ["8f1c-ä", 'quote"d']
        namespace = {}
        code = chk.verify_code(ids).split("states, bad")[0].replace("from celery.result import AsyncResult\n", "")
        exec(code, namespace)
        self.assertEqual(namespace["ids"], ids)


class FakeStack:
    """Stands in for compose + RabbitMQ: records what ran, and behaves like a healthy stack unless told otherwise."""

    def __init__(self, tasks, key_in=None, queues=None, results=None, published=None):
        self.tasks, self.key_in, self.ran = tasks, key_in, []
        self.published = tasks if published is None else published
        self.queues = queues or [snap(), snap(publish=tasks, ack=tasks)]
        self.results = results or {"total": tasks, "states": {"SUCCESS": tasks}, "bad": 0}
        self._q = list(self.queues)

    def run_python(self, service, code, timeout=120):
        self.ran.append((service, code))
        if "WTC_KEY" in code:
            return "WTC_KEY " + json.dumps(service == self.key_in)
        if "WTC_IDS" in code:
            return "WTC_IDS " + json.dumps([f"id{i}" for i in range(self.published)])
        return "WTC_RESULT " + json.dumps(self.results)

    def queue(self):
        return self._q.pop(0) if len(self._q) > 1 else self._q[0]


class Died(Exception):
    pass


def _die(message):
    raise Died(message)


class RunTests(SimpleTestCase):
    def go(self, stack, tasks=5, deadline=10):
        clock = Clock()
        said = []
        chk.run(stack, tasks, deadline, "web", "celery", interval=1, clock=clock, sleep=clock.sleep, say=said.append, die=_die)
        return said

    def test_a_healthy_stack_passes_every_step(self):
        stack = FakeStack(5)
        said = self.go(stack)
        self.assertEqual(len(said), 5)
        self.assertTrue(any("WTC_IDS" in code for _, code in stack.ran))

    def test_a_gemini_key_in_the_worker_aborts_before_anything_is_published(self):
        stack = FakeStack(5, key_in="celery")
        with self.assertRaisesRegex(Died, "GEMINI_API_KEY is set in 'celery'"):
            self.go(stack)
        self.assertFalse(any("WTC_IDS" in code for _, code in stack.ran), "the burst must not be published when a real key is configured")

    def test_a_gemini_key_in_the_web_container_aborts_before_anything_is_published(self):
        stack = FakeStack(5, key_in="web")
        with self.assertRaisesRegex(Died, "GEMINI_API_KEY is set in 'web'"):
            self.go(stack)
        self.assertFalse(any("WTC_IDS" in code for _, code in stack.ran))

    def test_no_consumer_on_the_queue_aborts_before_publishing(self):
        stack = FakeStack(5, queues=[snap(consumers=0)])
        with self.assertRaisesRegex(Died, "no consumer"):
            self.go(stack)
        self.assertFalse(any("WTC_IDS" in code for _, code in stack.ran))

    def test_a_short_publish_is_reported_instead_of_being_waited_out(self):
        stack = FakeStack(5, published=3)
        with self.assertRaisesRegex(Died, "published 3 tasks, expected 5"):
            self.go(stack)

    def test_an_unreachable_management_api_aborts(self):
        stack = FakeStack(5)
        stack.queue = lambda: None
        with self.assertRaisesRegex(Died, "unreachable"):
            self.go(stack)

    def test_a_queue_that_never_drains_fails(self):
        stack = FakeStack(5, queues=[snap(), snap(ready=5, publish=5)])
        with self.assertRaisesRegex(Died, "did not drain"):
            self.go(stack)

    def test_results_that_are_not_all_success_fail_even_if_the_queue_drained(self):
        stack = FakeStack(5, results={"total": 5, "states": {"SUCCESS": 4, "FAILURE": 1}, "bad": 0})
        with self.assertRaisesRegex(Died, "not all SUCCESS"):
            self.go(stack)
