#!/usr/bin/env bash
# End-to-end smoke test of the docker-compose stack (needs Docker; run locally).
#   ./scripts/compose-smoke.sh            # start, verify, leave running
#   KEEP=0 ./scripts/compose-smoke.sh    # tear everything down afterwards
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$*"; exit 1; }

echo "▶ building and starting the stack (waiting for healthchecks)..."
docker compose up -d --build --wait --wait-timeout 300

echo "▶ API"
body=$(curl -fsS http://localhost:8000/api/health/) || fail "health endpoint unreachable"
echo "    $body"
echo "$body" | grep -q '"database": *"ok"' && ok "database ok"  || fail "database not ok"
echo "$body" | grep -q '"broker": *"ok"'   && ok "RabbitMQ reachable from the API" || fail "broker not ok"
curl -fsS -o /dev/null -D - http://localhost:8000/api/health/ | grep -qi '^x-request-id:' && ok "X-Request-ID header present" || fail "no request id"
curl -fsS http://localhost:8000/metrics | grep -q django_http && ok "/metrics serves Prometheus data" || fail "/metrics broken"

echo "▶ RabbitMQ -> worker -> Redis round trip"
docker compose exec -T web python manage.py shell -c "
from GetFood.tasks import cleanup_expired_ai_cache as t
print('RESULT', t.delay().get(timeout=60))" | grep -q RESULT && ok "task published to RabbitMQ, consumed by the worker, result read back from Redis" || fail "task round trip failed"
docker compose exec -T rabbitmq rabbitmq-diagnostics -q list_queues name messages consumers | sed 's/^/    /'
docker compose exec -T rabbitmq rabbitmq-plugins list -e -m | grep -q rabbitmq_prometheus && ok "rabbitmq_prometheus plugin enabled" || fail "rabbitmq_prometheus not enabled (see monitoring/prometheus.yml)"

echo "▶ non-root + beat"
[ "$(docker compose exec -T web id -u)" = "10001" ] && ok "web runs as uid 10001" || fail "web is not uid 10001"
docker compose logs celery_beat 2>&1 | grep -q "beat: Starting" && ok "celery beat started" || fail "celery beat did not start"
docker compose exec -T web sh -c 'touch /app/media/.write-test && rm /app/media/.write-test' && ok "media volume writable by the non-root user" \
  || fail "media volume not writable (volume created by an older root-owned image? run: docker compose run --rm --user root --entrypoint chown web -R 10001:10001 /app/media)"

echo "▶ optional monitoring profile"
docker compose --profile monitoring up -d --wait --wait-timeout 120
curl -fsS http://localhost:9090/-/ready >/dev/null && ok "Prometheus ready (http://localhost:9090)" || fail "Prometheus not ready"
curl -fsS -u "${FLOWER_BASIC_AUTH:-admin:change-me}" http://localhost:5555/healthcheck >/dev/null && ok "Flower up (http://localhost:5555)" || fail "Flower not up"

echo; echo "All checks passed."
[ "${KEEP:-1}" = "0" ] && docker compose --profile monitoring down -v
