#!/usr/bin/env python3
"""Prove that the Celery `ai` queue drains under a burst (compose stack). Standard library only.

    python3 scripts/check_ai_queue.py [--tasks 200] [--deadline 90] [--mgmt http://localhost:15672]
    credentials: $RABBITMQ_DEFAULT_USER / $RABBITMQ_DEFAULT_PASS (defaults whattocook / secret, as in docker-compose.yml)

Why this exists: `POST /api/ai/suggestions/` answers inline and only enqueues when the inline call raises (the provider
layer swallows provider errors and returns the fallback), so HTTP load alone never puts a message on `ai`. This check
publishes the burst itself, with the same task the endpoint would enqueue, and asserts, in order, that:
  1. no GEMINI_API_KEY is configured in the web container or the worker (otherwise the burst would spend real quota);
  2. RabbitMQ's management API is reachable and the `ai` queue has at least one consumer;
  3. N tasks are published to the queue named `ai` (message_stats.publish grew by >= N);
  4. the queue drains within --deadline seconds: ready == 0 and unacknowledged == 0 on consecutive polls, and
     message_stats.ack grew by >= N (the worker acks after finishing: CELERY_TASK_ACKS_LATE);
  5. every one of the N task ids is SUCCESS in the Redis result backend and carries the degraded fallback answer.
Management statistics are sampled by RabbitMQ (not instantaneous), hence consecutive polls rather than one reading.
Run it WHILE the k6 soak is hitting the API, so it proves broker -> worker -> Redis under load.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

QUEUE = "ai"
STABLE_POLLS = 2


def ok(msg):
    print(f"  \033[32m✔\033[0m {msg}")


def fail(msg):
    print(f"  \033[31m✘\033[0m {msg}")
    sys.exit(1)


# ---------------------------------------------------------------- pure helpers (unit-tested without a stack) ----
def parse_queue(payload):
    """RabbitMQ management /api/queues/<vhost>/<name> JSON -> the few numbers we judge on.

    `message_stats` is absent until the queue has seen traffic, and `consumers` is only present on a live queue."""
    stats = payload.get("message_stats") or {}
    return {
        "ready": int(payload.get("messages_ready", 0) or 0),
        "unacked": int(payload.get("messages_unacknowledged", 0) or 0),
        "publish": int(stats.get("publish", 0) or 0),
        "ack": int(stats.get("ack", 0) or 0),
        "consumers": payload.get("consumers"),
    }


def parse_marker(stdout, marker):
    """The value printed as `<marker> <json>` somewhere in noisy shell output."""
    for line in reversed(stdout.splitlines()):
        if line.startswith(marker + " "):
            return json.loads(line[len(marker) + 1:])
    raise ValueError(f"no {marker} line in output: {stdout[-400:]!r}")


def enqueue_code(tasks, run_id):
    """Python for `manage.py shell -c`: publish `tasks` AI tasks (provider pinned to gemini: with an empty key it fails
    instantly and the task returns the deterministic fallback, never calling out)."""
    return (
        "import json\n"
        "from GetFood.tasks import generate_ai_suggestions_task as task\n"
        "ids = []\n"
        f"for i in range({int(tasks)}):\n"
        f"    names = ['loadcheck-{run_id}-%d-%s' % (i, w) for w in ('a', 'b', 'c')]\n"
        f"    ids.append(task.delay(names, 'loadcheck-{run_id}-%d' % i, provider='gemini', language='en').id)\n"
        "print('WTC_IDS ' + json.dumps(ids))\n"
    )


def key_probe_code():
    return "import json\nfrom GetFood import ai_service\nprint('WTC_KEY ' + json.dumps(bool(ai_service.GEMINI_API_KEY)))\n"


def verify_code(ids):
    return (
        "import json\n"
        "from celery.result import AsyncResult\n"
        f"ids = json.loads({json.dumps(json.dumps(ids))})\n"
        "states, bad = {}, 0\n"
        "for task_id in ids:\n"
        "    r = AsyncResult(task_id)\n"
        "    states[r.state] = states.get(r.state, 0) + 1\n"
        "    if r.state == 'SUCCESS':\n"
        "        res = r.result\n"
        "        if not (isinstance(res, dict) and res.get('status') == 'ok' and res.get('degraded') is True and res.get('recipes')):\n"
        "            bad += 1\n"
        "print('WTC_RESULT ' + json.dumps({'states': states, 'bad': bad, 'total': len(ids)}))\n"
    )


def results_ok(result, tasks):
    return result["total"] == tasks and result["states"] == {"SUCCESS": tasks} and result["bad"] == 0


def wait_for_drain(fetch, tasks, baseline, deadline, interval=2.0, clock=time.monotonic, sleep=time.sleep):
    """Poll `fetch()` (-> parse_queue dict, or None when the queue is not visible) until the burst is fully drained.

    Returns {"ok": bool, "reason": str, "peak": int, "polls": int, "last": dict|None}."""
    end = clock() + deadline
    peak, polls, quiet, last = 0, 0, 0, None
    while True:
        snap = fetch()
        polls += 1
        if snap is not None:
            last = snap
            peak = max(peak, snap["ready"] + snap["unacked"])
            published = snap["publish"] - baseline["publish"] >= tasks
            acked = snap["ack"] - baseline["ack"] >= tasks
            empty = snap["ready"] == 0 and snap["unacked"] == 0
            quiet = quiet + 1 if (published and acked and empty) else 0
            if quiet >= STABLE_POLLS:
                return {"ok": True, "reason": "drained", "peak": peak, "polls": polls, "last": snap}
        if clock() >= end:
            return {"ok": False, "reason": _why_stuck(last, baseline, tasks), "peak": peak, "polls": polls, "last": last}
        sleep(interval)


def _why_stuck(last, baseline, tasks):
    if last is None:
        return f"queue '{QUEUE}' never became visible in the management API"
    if last["publish"] - baseline["publish"] < tasks:
        return (f"only {last['publish'] - baseline['publish']} of {tasks} messages were published to '{QUEUE}' "
                f"(are the tasks routed elsewhere? check CELERY_TASK_ROUTES)")
    if last["consumers"] == 0:
        return f"no consumer on '{QUEUE}': start a worker with CELERY_QUEUES including {QUEUE}"
    if last["ready"] or last["unacked"]:
        return f"still {last['ready']} ready + {last['unacked']} unacknowledged on '{QUEUE}': the worker is not keeping up"
    return f"queue is empty but only {last['ack'] - baseline['ack']} of {tasks} acks were recorded"


# ---------------------------------------------------------------------------------------------- I/O wrappers ----
class Stack:
    """Runs Python inside compose services and reads the RabbitMQ management API."""

    def __init__(self, compose, mgmt, credentials, vhost="/"):
        self.compose = compose.split()
        self.mgmt = mgmt.rstrip("/")
        self.auth = "Basic " + base64.b64encode(credentials.encode()).decode()
        self.vhost = vhost

    def run_python(self, service, code, timeout=120):
        cmd = self.compose + ["exec", "-T", service, "python", "manage.py", "shell", "-c", code]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if out.returncode != 0:
            raise RuntimeError(f"`{' '.join(cmd[:5])} ...` exited {out.returncode}: {out.stderr[-600:]}")
        return out.stdout

    def queue(self):
        """-> parse_queue dict, None if the queue does not exist (yet) or the API is unreachable."""
        url = f"{self.mgmt}/api/queues/{urllib.parse.quote(self.vhost, safe='')}/{QUEUE}"
        req = urllib.request.Request(url, headers={"Authorization": self.auth, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return parse_queue(json.loads(resp.read().decode()))
        except (urllib.error.URLError, OSError, ValueError):
            return None


def run(stack, tasks, deadline, web, worker, interval=2.0, clock=time.monotonic, sleep=time.sleep, say=ok, die=fail):
    """The whole check against a `stack`; `say`/`die` are the reporting hooks (die must not return)."""
    for service in (web, worker):
        key = parse_marker(stack.run_python(service, key_probe_code()), "WTC_KEY")
        if key:
            die(f"GEMINI_API_KEY is set in '{service}': refusing to publish a burst that would call the real provider")
    say("no Gemini key configured in the web container or the worker (the burst cannot spend real quota)")

    baseline = stack.queue()
    if baseline is None:
        die("RabbitMQ management API unreachable or queue 'ai' does not exist (is a worker consuming it?)")
    if baseline["consumers"] == 0:
        die(f"queue '{QUEUE}' has no consumer: start a worker with CELERY_QUEUES including {QUEUE}")
    say(f"management API reachable; '{QUEUE}' has {baseline['consumers']} consumer(s), {baseline['ready'] + baseline['unacked']} backlog")

    run_id = uuid.uuid4().hex[:8]
    ids = parse_marker(stack.run_python(web, enqueue_code(tasks, run_id)), "WTC_IDS")
    if len(ids) != tasks:
        die(f"published {len(ids)} tasks, expected {tasks}")
    say(f"published {tasks} tasks to the broker (run {run_id})")

    outcome = wait_for_drain(stack.queue, tasks, baseline, deadline, interval, clock, sleep)
    if not outcome["ok"]:
        die(f"'{QUEUE}' did not drain in {deadline}s: {outcome['reason']} (peak backlog {outcome['peak']}, last {outcome['last']})")
    say(f"'{QUEUE}' drained: peak backlog {outcome['peak']}, {outcome['polls']} polls, "
        f"publish +{outcome['last']['publish'] - baseline['publish']}, ack +{outcome['last']['ack'] - baseline['ack']}")

    result = None
    for _ in range(5):
        result = parse_marker(stack.run_python(web, verify_code(ids)), "WTC_RESULT")
        if results_ok(result, tasks):
            break
        sleep(interval)
    if not results_ok(result, tasks):
        die(f"results in Redis are not all SUCCESS + degraded fallback: {result}")
    say(f"all {tasks} task results are SUCCESS with the fallback answer in the Redis result backend")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--tasks", type=int, default=200)
    parser.add_argument("--deadline", type=float, default=90, help="seconds allowed for the burst to drain")
    parser.add_argument("--mgmt", default="http://localhost:15672")
    parser.add_argument("--compose", default="docker compose")
    parser.add_argument("--web", default="web")
    parser.add_argument("--worker", default="celery")
    args = parser.parse_args(argv)
    credentials = f"{os.environ.get('RABBITMQ_DEFAULT_USER', 'whattocook')}:{os.environ.get('RABBITMQ_DEFAULT_PASS', 'secret')}"
    print(f"ai-queue drain check: {args.tasks} tasks, deadline {args.deadline:.0f}s")
    run(Stack(args.compose, args.mgmt, credentials), args.tasks, args.deadline, args.web, args.worker)
    print("\033[32mai queue OK\033[0m")


if __name__ == "__main__":
    main()
