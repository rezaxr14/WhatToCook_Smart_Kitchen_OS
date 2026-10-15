#!/bin/sh
set -e

ROLE="${1:-web}"

echo "🍳 WhatToCook backend initializing (role: ${ROLE})..."

# ---------------------------------------------------------------
# Wait until the database accepts connections.
# Works for Postgres (Docker) and SQLite (bare-metal) alike.
# ---------------------------------------------------------------
echo "⏳ Waiting for the database to be ready..."
i=0
until out=$(python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'WhatToCook.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
" 2>&1); do
    # A configuration error (e.g. refusing insecure defaults with DEBUG=false) will
    # never fix itself: fail fast and show it instead of retrying for two minutes.
    case "$out" in
        *ImproperlyConfigured*|*ModuleNotFoundError*|*SyntaxError*)
            echo "❌ Startup failed:"
            echo "$out" | tail -n 8
            exit 1
            ;;
    esac
    i=$((i + 1))
    if [ "$i" -ge 60 ]; then
        echo "❌ Database not reachable after 60 attempts. Last error:"
        echo "$out" | tail -n 8
        exit 1
    fi
    sleep 2
done
echo "✅ Database is up."

# ---------------------------------------------------------------
# Migrations + idempotent seed + static files (web role only;
# celery/bot just wait for the web container's migrations via DB).
# ---------------------------------------------------------------
if [ "$ROLE" = "web" ]; then
    # Takes a Postgres advisory lock, so any number of replicas can boot at once.
    echo "📦 Migrating + seeding ingredients & recipes (idempotent, lock-protected)..."
    python manage.py bootstrap_db

    echo "🎨 Collecting static files..."
    python manage.py collectstatic --noinput
fi

# ---------------------------------------------------------------
# Hand off to the requested process.
# ---------------------------------------------------------------
case "$ROLE" in
    web)
        # Multi-worker Prometheus metrics: a clean shared directory per container start.
        export PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus_multiproc}"
        rm -rf "$PROMETHEUS_MULTIPROC_DIR" && mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
        echo "🚀 Starting gunicorn on 0.0.0.0:8000..."
        exec gunicorn WhatToCook.wsgi:application \
            --config gunicorn.conf.py \
            --bind 0.0.0.0:8000 \
            --workers "${GUNICORN_WORKERS:-3}" \
            --threads "${GUNICORN_THREADS:-2}" \
            --timeout 120 \
            --access-logfile - \
            --error-logfile -
        ;;
    celery)
        echo "🚀 Starting Celery worker..."
        # Give the web role a head start on first-boot migrations.
        sleep 5
        # Consume every queue by default; dedicate workers with e.g. CELERY_QUEUES=ai
        exec python -m celery -A WhatToCook worker --loglevel=info \
            --concurrency="${CELERY_CONCURRENCY:-2}" \
            --queues="${CELERY_QUEUES:-ai,maintenance,celery}"
        ;;
    beat)
        echo "⏰ Starting Celery beat (periodic tasks)..."
        sleep 5
        exec python -m celery -A WhatToCook beat --loglevel=info \
            --schedule="${CELERY_BEAT_SCHEDULE_FILE:-/tmp/celerybeat-schedule}"
        ;;
    bot)
        if [ -z "$TELEGRAM_BOT_TOKEN" ]; then
            echo "⚠️ TELEGRAM_BOT_TOKEN is empty. Telegram bot disabled; idling so 'docker compose up' stays healthy."
            sleep infinity
        fi
        echo "🚀 Starting Telegram bot (long polling)..."
        sleep 5
        exec python manage.py run_telegram_bot
        ;;
    *)
        echo "❌ Unknown role '${ROLE}'. Use: web | celery | beat | bot"
        exit 1
        ;;
esac
