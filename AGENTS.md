# Working on WhatToCook (for humans and coding agents)

Django 5.2 + DRF API, React/Vite frontend, Celery on **RabbitMQ**, **Redis** (results + cache),
Postgres, Docker Compose, Kubernetes (kustomize), GitHub Actions. See `README.md` for the tour and
`docs/ROADMAP.md` for what to build next.

## Verify with CI, not by guessing
Anything that needs Docker/kind/browsers is **proven by GitHub Actions** (all green as of the last
merge). Push a branch/PR and read the jobs; don't spend hours fighting a local Docker VM.

| You changed | Run locally (fast) | CI proves it |
|---|---|---|
| Python / API | `make test` · `make lint` · `make cov` | `ci.yml` lint, backend (SQLite **and** Postgres), coverage gate |
| Frontend | `make web` | `ci.yml` frontend, `e2e.yml` (Playwright) |
| Compose / entrypoint / Dockerfile | `docker compose config -q` | `smoke.yml` → `scripts/compose-smoke.sh`, `ci.yml` docker build |
| `k8s/**` | `make k8s-render` | `ci.yml` kubeconform (incl. CRDs), `smoke.yml` → kind |
| Backups / DB | `make drill` (needs Postgres env) | `ci.yml` backup/restore drill |
| Dependencies | `pip-audit -r requirements.txt` · `cd frontend && npm audit --omit=dev` | `security.yml` (+ CodeQL) |

## Invariants (each one cost us a bug; don't undo them)
- **`db.sqlite3` is tracked on purpose**: it is the initial dataset (images etc.). Don't untrack or regenerate it. `.dockerignore` keeps it out of images.
- **Broker vs results.** Celery broker = RabbitMQ pinned to **4.2** (4.3+ rejects the transient non-exclusive queues Celery 5.5's kombu declares; Dependabot ignores it on purpose). Results + Django cache = Redis. Never default `CELERY_RESULT_BACKEND` to the broker URL.
- **Queues.** `ai`, `maintenance`, `celery`. Route every new task in `CELERY_TASK_ROUTES`, schedule periodic ones in `CELERY_BEAT_SCHEDULE`, keep workers consuming `CELERY_QUEUES`.
- **AI fallbacks are never cached** (`ai_cache.is_degraded`). The Celery task *returns its recipes*, so the status endpoint works even when nothing is cached. Failed tasks → `status: "error"` (no exception text to clients).
- **Anonymous visitors act as `ChefDemo`** (`DEMO_USERNAME`, `_guest_user()`), never `User.objects.first()`.
- **Secrets.** With `DEBUG=false` the app refuses placeholder/short `SECRET_KEY` and well-known Postgres passwords (`settings.py`). `.env` is optional locally; every setting has a working default.
- **Containers run as uid 10001.** Never use `healthcheck: disable: true` in compose: newer Compose releases fail `up --wait` ("has no healthcheck configured"). Give each role a real check; the PID-1 checks (beat, bot) depend on the entrypoint `exec`-ing the process (idle bot stays the entrypoint shell and traps SIGTERM).
- **Boot safety.** `bootstrap_db` migrates + seeds under a Postgres advisory lock so replicas can start together. Don't reintroduce a bare `migrate` in entrypoints.
- **Kubernetes.** `k8s/base` + `overlays/{dev,prod}`. Probes send `Host: web`; `media` PVC is RWO (>1 web replica needs RWX); beat and the Telegram bot are single-replica `Recreate`. Secrets are never committed (`k8s/secret.yaml` is git-ignored).
- **Supply chain.** No third-party scanner actions for now (`trivy-action` tags were hijacked in March 2026). If you add one, pin a full commit SHA.
- **Windows checkouts.** `.gitattributes` forces LF for scripts/YAML/Dockerfile; `make` is unavailable in PowerShell, call the underlying commands.
- **Prove, don't claim.** If you didn't run it (or CI didn't), say "not verified".

## Conventions
- Conventional Commits (`feat(scope):`, `fix(scope):`, `ci:`, `docs:`); small, themed commits.
- New behaviour gets a test (`tests/` or `GetFood/tests.py`); keep the coverage gate green and ratchet `.coveragerc` `fail_under` up as it improves.
- Deliver as commits on a branch/PR; if a patch is needed: `git format-patch <base> --stdout > x.patch`, applied with `git am`.
- Optional local gate: `pip install pre-commit && pre-commit install` (ruff + YAML + secret checks).
