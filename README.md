# 🍳 WhatToCook — AI-Powered Intelligent Recipe Studio & Smart Pantry

> **Zero Food Waste AI Recipe Engine**, visual camera ingredient scanner powered by **Generative AI**, real-time culinary generation streaming, interactive Telegram bot assistant, smart grocery lists with 1-click WhatsApp & Telegram exports, dynamic portion scaling, an offline Progressive Web App (PWA), and a **5-language interface (English, Türkçe, فارسی, العربية, Español)** with full RTL support.

[![CI](https://github.com/rezaxr14/WhatToCook_Smart_Kitchen_OS/actions/workflows/ci.yml/badge.svg)](https://github.com/rezaxr14/WhatToCook_Smart_Kitchen_OS/actions/workflows/ci.yml)
[![Django 5.2](https://img.shields.io/badge/Django-5.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://djangoproject.com/)
[![React 18](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6.0-646CFF?style=for-the-badge&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Docker Alpine](https://img.shields.io/badge/Docker-Alpine_Lean-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)

---

## 🖼️ Screenshots

<p align="center">
  <img src="docs/screenshots/landing-hero.png" alt="WhatToCook landing page — 'You already have dinner.' 3D kitchen hero" width="100%">
  <br>
  <em>Cinematic 3D landing page — "You already have dinner."</em>
</p>

<table>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/recipes-catalog.png" alt="Kitchen dashboard and recipe catalog with search, filters and cook-time slider">
      <br><sub><b>Kitchen Dashboard &amp; Recipe Catalog</b> — search, category filters and a max-cook-time slider</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/pantry-shelf.png" alt="My Pantry Shelf with stocked ingredients, fridge photo scanner and ingredient catalog">
      <br><sub><b>My Pantry Shelf</b> — stocked ingredients, fridge-photo scanner and a 73-item catalog</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/can-cook.png" alt="What You Can Cook Right Now — zero-waste recipe matching with missing ingredients">
      <br><sub><b>What You Can Cook Right Now</b> — 100% matches and "missing 1 or 2 items" recipes</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/ai-chef-studio.png" alt="AI Chef Studio — pick pantry ingredients and generate chef recipes">
      <br><sub><b>AI Chef Studio</b> — pick ingredients and generate recipes with Cloud or Local AI</sub>
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="docs/screenshots/sign-in.png" alt="Sign-in page with one-click guest demo">
      <br><sub><b>Sign In</b> — with an instant 1-click guest demo</sub>
    </td>
    <td width="50%" align="center">
      <img src="docs/screenshots/landing-mobile.png" alt="WhatToCook landing page on a mobile viewport" height="320">
      <br><sub><b>Mobile</b> — fully responsive layout</sub>
    </td>
  </tr>
</table>

### 🎬 The 3D Landing Journey

Scrolling the landing page tells the whole story in eight chapters: open the fridge, let the AI connect the dots, and watch dinner get discovered.

<table>
  <tr>
    <td width="25%" align="center"><img src="docs/screenshots/journey/01-arrival.png" alt="Chapter 1 — Arrival"><br><sub>1 · Arrival</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/02-fridge-door.png" alt="Chapter 2 — Fridge door"><br><sub>2 · Fridge door</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/03-ai-awakens.png" alt="Chapter 3 — AI awakens"><br><sub>3 · AI awakens</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/04-galaxy.png" alt="Chapter 4 — Galaxy of possibilities"><br><sub>4 · Galaxy</sub></td>
  </tr>
  <tr>
    <td width="25%" align="center"><img src="docs/screenshots/journey/05-cooking.png" alt="Chapter 5 — Cooking"><br><sub>5 · Cooking</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/06-dish.png" alt="Chapter 6 — The dish"><br><sub>6 · The dish</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/07-homecoming.png" alt="Chapter 7 — Homecoming"><br><sub>7 · Homecoming</sub></td>
    <td width="25%" align="center"><img src="docs/screenshots/journey/08-finale.png" alt="Chapter 8 — Finale"><br><sub>8 · Finale</sub></td>
  </tr>
</table>

<details>
<summary>📜 Full-length landing page</summary>
<br>
<p align="center">
  <img src="docs/screenshots/landing-full.png" alt="Full-length WhatToCook landing page" width="60%">
</p>
</details>

---

## 🌟 Architecture & Key Features

```
WhatToCook Ecosystem
├── 🌐 React 18 + TypeScript + Tailwind CSS 4 + TanStack Query Frontend (Vite)
│   └── 🧊 React Three Fiber 3D hero · react-i18next (EN/TR/FA/AR/ES + RTL) · PWA
├── 🛡️ nginx reverse proxy → serves the SPA build, proxies /api /admin /static /media /legacy
├── ⚡ Django 5.2 REST Framework API Backend (Python 3.11, gunicorn + WhiteNoise)
├── 🤖 Multimodal AI Vision & Generative Recipe Streaming Engine
├── 💬 Telegram Bot Webhook & Interactive Pantry Handshake
├── 📱 Smart Grocery Exporter (WhatsApp, Telegram, Markdown, Print)
├── 🗄️ PostgreSQL 15 (Docker) / SQLite3 (Auto-fallback local dev)
├── 📨 RabbitMQ 4.2 → Celery broker (queues: ai · maintenance) + celery beat + optional Flower
├── 🚀 Redis 7 → Celery results + Django cache (AI hot cache, stats, rate limits)
└── 🔭 Prometheus metrics · JSON logs · ☸️ Kubernetes (kustomize) · 🤖 GitHub Actions CI
```

### ✨ Core Features
1. **📸 AI Vision Pantry Scanner**: Snap a photo of your fridge or countertop; AI detects recognized food items and automatically stocks your digital pantry shelf.
2. **🧠 Smart Zero-Waste Recipe Matching**: Instantly computes 100% matched recipes you can cook right now with no extra groceries needed, plus partial matches (missing only 1 or 2 items).
3. **⚡ Live SSE Generative Streaming**: Watch recipes, macro breakdowns, and master chef secrets stream in real-time.
4. **🤖 Telegram AI Chef Bot**: Link your Telegram account with 1-click. Send `/cook`, `/pantry`, `/add Garlic`, or `/remove Butter` from your phone on the go.
5. **🛒 Smart Grocery List & 1-Click Social Exporter**: Add missing ingredients from any recipe or partial match with 1 click. Export formatted grocery lists to **WhatsApp**, **Telegram**, Clipboard, or Print slip.
6. **⚖️ Dynamic Portion Scaler (1x, 2x, 4x, 6x, 8x)**: Scalable ingredient measurements (e.g. `2 tbsp`, `250g`, `1/2 cup`) dynamically recalibrate portions in real-time without boundary overflows.
7. **💡 AI Substitution Assistant**: Missing buttermilk, eggs, heavy cream, or parmesan? Instant culinary swaps and ratio tips.
8. **📱 Progressive Web App (PWA)**: Installable on iOS & Android with offline pantry viewing.
9. **🌍 Multilingual UI (EN / TR / FA / AR / ES)**: First-visit language chooser, floating quick-switcher and footer dropdown; Persian & Arabic get full right-to-left layouts and dedicated fonts (Vazirmatn, Noto Sans Arabic).

---

## ⚡ Superfast Quickstart with Docker (Recommended)

Run the complete multi-service stack with a single command:

```bash
# 1. Clone the repository
git clone https://github.com/rezaxr14/WhatToCook_Smart_Kitchen_OS.git
cd WhatToCook_Smart_Kitchen_OS

# 2. Configure environment variables
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY (from https://aistudio.google.com)

# (If your network requires an HTTP proxy for internet egress, add your overrides:
#  docker compose -f docker-compose.yml -f docker-compose.proxy.yml up -d --build)

# (the .env file is optional: every setting has a working default)

# 3. Build and launch all lightweight containers
#    (migrations, idempotent seeding and collectstatic run automatically on boot)
docker compose up -d --build
```

> **Upgrading an existing checkout?** The backend image now runs as an unprivileged user (uid 10001).
> A `media_data` volume created by an older image is root-owned; fix it once (this does **not** touch your database volume):
> `docker compose run --rm --user root --entrypoint chown web -R 10001:10001 /app/media`
> To verify the whole stack end to end (API, RabbitMQ → worker → Redis round trip, beat, metrics): `./scripts/compose-smoke.sh`.

### 🌐 Access Points:
- **Frontend Web App**: [http://localhost:4173](http://localhost:4173)
- **Django REST API**: [http://localhost:8000/api/](http://localhost:8000/api/)
- **Landing Page Health**: [http://localhost:8000/api/health/](http://localhost:8000/api/health/)
- **API docs (Swagger UI)**: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/), machine-readable schema at [`/api/schema/`](http://localhost:8000/api/schema/) (`?format=json` for JSON)
- **Django Admin Panel**: [http://localhost:8000/admin/](http://localhost:8000/admin/) or [http://localhost:4173/admin/](http://localhost:4173/admin/)
- **Legacy Server-Rendered Pages**: [http://localhost:8000/legacy/](http://localhost:8000/legacy/)
- **Flower / Prometheus / Grafana** (optional, `docker compose --profile monitoring up -d`): [http://localhost:5555](http://localhost:5555) · [http://localhost:9090](http://localhost:9090) · [http://localhost:3000](http://localhost:3000) (Grafana login: `GRAFANA_ADMIN_USER` / `GRAFANA_ADMIN_PASSWORD`, default `admin` / `change-me`)
- **RabbitMQ Management UI**: [http://localhost:15672](http://localhost:15672) (bound to localhost; log in with `RABBITMQ_DEFAULT_USER` / `RABBITMQ_DEFAULT_PASS` from your `.env`, default `whattocook` / `secret`)

---

## 💻 Local Development Setup (Without Docker)

### 1. Backend Setup
```bash
# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# IMPORTANT: if your .env has DB_HOST set (Docker config), force SQLite locally:
#   PowerShell:  $env:USE_POSTGRES="false"
#   bash:        USE_POSTGRES=false

# Run migrations & seed recipes
python manage.py migrate
python manage.py seed_recipes

# Start backend server
python manage.py runserver 127.0.0.1:8000
```

> RabbitMQ and Redis are **optional** for bare-metal development: without them
> the cache falls back to in-process memory and the async Celery fallback
> degrades to the built-in culinary fallback recipes (`/api/health/` reports
> `broker: degraded`). To run the full async path locally, start RabbitMQ
> (`guest`/`guest` works from localhost) and Redis, then in a second terminal:
> `celery -A WhatToCook worker -l info`.

### 2. Frontend Setup
```bash
cd frontend

# Install node dependencies
npm install

# Start Vite development server
npm run dev
```

---

## 🧪 Testing Suite

Run the comprehensive Django REST API test suite:

```bash
# Bare-metal (SQLite): make sure Postgres is not forced via .env
USE_POSTGRES=false python manage.py test GetFood tests
```

Target: **100% passing tests** covering:
- Authentication & Auto-Pantry Creation
- Pantry Ingredient Operations & Optimistic Handshakes
- Zero-Waste Match Engine Algorithms (100% & Partial matches)
- Multimodal Vision Scanner & Fallback Resiliency
- Live AI Recipe Generation & Streaming Endpoints
- Platform endpoints (/api/stats/, /api/health/) & legacy route namespacing
- Rate limiting: every scope trips a clean `429` with `Retry-After`
  (`tests/test_throttling.py`)

Frontend production build + end-to-end Playwright suite (23 tests across the 3D
landing journey, full user flows, i18n/RTL and responsive viewports), plus a CSP
suite (production build under nginx's exact Content-Security-Policy, plus lazy-chunk recovery):

```bash
cd frontend
npm run build          # typecheck + vite build
npm run test:e2e       # starts Vite automatically; backend on :8000 required
npm run test:e2e:csp   # builds + serves the bundle with the real CSP; fails on any violation
npm run check:bundle   # after `npm run build`: bundle budget (initial graph, per-chunk limits, no three.js up front)
npm run test:visual    # full-page screenshots of the main pages (CI diffs main vs the PR: .github/workflows/visual.yml)
# refresh the journey screenshots in docs/screenshots (dev servers running):
node scripts/recapture-journey.cjs && node scripts/recapture-landing.cjs
```

## 📨 Message queue & Redis

| Component | Role |
|---|---|
| **RabbitMQ** (`rabbitmq:4.2-management-alpine`) | Celery **broker**. AI recipe generation is first attempted inline; if the provider is slow or fails, `generate_ai_suggestions_task` is published to RabbitMQ and the client polls `/api/ai/task-status/<task_id>/`. |
| **Redis** | Celery **result backend** (db 0) and Django **cache** (db 1). |

**Queues & workers**

- `ai` — recipe generation · `maintenance` — housekeeping · `celery` — everything else. A worker consumes all three by default; dedicate workers with `CELERY_QUEUES=ai`.
- Failed tasks are retried with exponential backoff + jitter (max 3). When retries are exhausted the status endpoint answers `{"status": "error"}` and the UI shows an error toast instead of an empty result.
- **Celery beat** (`celery_beat` service / `celery-beat` Deployment — run exactly one) schedules `cleanup_expired_ai_cache` nightly (retention: `AI_CACHE_RETENTION_DAYS`, default 7).
- Optional **Flower** (`docker compose --profile monitoring up -d` → <http://localhost:5555>) shows workers, tasks and queue depth. On Kubernetes: `k8s/optional/flower.yaml`, and `k8s/optional/keda-celery.yaml` scales the worker by `ai` queue length.

**What lives in Redis** (all through Django's cache, so it degrades to a cache miss — never an error — if Redis is down):

- **AI suggestions hot cache** (24h) in front of the durable `AISuggestionCache` table; DB hits re-warm Redis.
- **Recipe detail cache** (24h) per recipe / provider / model / language — a real LLM answer is paid for once.
- The AI-offline **fallback recipes are never cached**, and a failed task can never overwrite a good cached answer.
- **Task bookkeeping**: Celery task id → ingredient hash, so the status endpoint returns *that* task's result.
- Platform stats, health probe and the per-scope **rate-limit counters**.

**Safe concurrent boot.** `bootstrap_db` (migrate + seed) runs under a Postgres advisory lock, so any number of `web` replicas can start at once.

`/api/health/` reports `database`, `cache` and `broker` (informational: a queue outage never fails the probe).
RabbitMQ is pinned to **4.2** because 4.3+ rejects the transient non-exclusive queues Celery 5.5's kombu declares; bump it together with Celery (Dependabot ignores it on purpose).

## 🔭 Observability

- **Structured logs**: JSON in production (`LOG_FORMAT=json`, default when `DEBUG=false`), plain text in dev. Every request gets an `X-Request-ID` (an incoming one from your ingress is reused) that appears in each log line and in the response header.
- **Metrics**: `GET /metrics` (django-prometheus; multiprocess-safe under gunicorn). Not proxied by nginx/Ingress — scrape it in-cluster or on the compose-published API port; set `METRICS_TOKEN` to additionally require `Authorization: Bearer <token>`. RabbitMQ's built-in Prometheus endpoint is on `:15692`.
- **Prometheus** for local use: `docker compose --profile monitoring up -d` → <http://localhost:9090> (scrapes the API, RabbitMQ and Flower; see `monitoring/prometheus.yml`). On Kubernetes use `k8s/optional/servicemonitor.yaml` (Prometheus Operator).
- **Grafana** (same profile) opens on the provisioned **WhatToCook / Overview** dashboard: scrape health, request rate by status class, latency p50/p95/p99 and p95 per view, exceptions, Celery task outcomes/runtime/workers, and RabbitMQ backlog, unacked and consumers per queue. The datasource and dashboard are provisioned read-only from `monitoring/grafana/`: edit the JSON, not the UI. Celery panels need worker events (`CELERY_SEND_EVENTS`, on by default); per-queue panels come from RabbitMQ's `/metrics/per-object` endpoint (a second Prometheus job). `python3 scripts/check_grafana.py` verifies the whole chain (compose smoke runs it). On Kubernetes: `k8s/optional/grafana.yaml` (its header shows how to load the dashboard ConfigMap).
- **Sentry** (optional): set `SENTRY_DSN` (plus `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`); Django and Celery are instrumented automatically.

## ☸️ Kubernetes

Kustomize layout in [`k8s/`](k8s):

```
k8s/base/                 Postgres + RabbitMQ (StatefulSets), Redis, web, celery, celery-beat,
                          telegram-bot, frontend, Ingress, PodDisruptionBudget
k8s/overlays/dev/         kind/minikube: throwaway generated secrets, DEBUG on
k8s/overlays/prod/        TLS (cert-manager), strict ALLOWED_HOSTS, NetworkPolicies, nightly pg_dump
k8s/optional/             HPA, KEDA queue-based scaling, Flower, Grafana, ServiceMonitors, ExternalSecret example
k8s/secret.example.yaml   template for the whattocook-secrets Secret
```

**Local cluster (kind)** — one command, then verify (needs `docker`, `kind`, `kubectl`):

```bash
./scripts/kind-smoke.sh            # builds + loads images, deploys overlays/dev, checks the stack end to end
kubectl -n whattocook port-forward svc/frontend 4173:80      # http://localhost:4173
```

**Production-shaped cluster**

```bash
# 1. secrets (never committed; k8s/secret.yaml is git-ignored)
kubectl apply -f k8s/base/namespace.yaml
cp k8s/secret.example.yaml k8s/secret.yaml && $EDITOR k8s/secret.yaml && kubectl apply -f k8s/secret.yaml

# 2. edit the hostname in k8s/overlays/prod/kustomization.yaml, pin image tags, create the
#    cert-manager ClusterIssuer (k8s/overlays/prod/cluster-issuer.example.yaml), then:
kubectl apply -k k8s/overlays/prod
```

Notes:

- With `DEBUG=false` the app **refuses to start** on a placeholder/short `SECRET_KEY` or a well-known Postgres password — use real secrets.
- `CELERY_BROKER_URL` in the Secret must embed the same RabbitMQ credentials as `RABBITMQ_DEFAULT_USER/PASS`.
- App pods run as uid 10001 (`runAsNonRoot`, `fsGroup`, all capabilities dropped, seccomp `RuntimeDefault`). An init container seeds the `media` PVC from the image's recipe photos.
- The `media` PVC is `ReadWriteOnce`; running more than one `web` replica (or `optional/hpa.yaml`) needs ReadWriteMany storage.
- The Telegram bot long-polls, and celery beat must be a single scheduler: both are single-replica `Recreate` Deployments.
- NetworkPolicies (prod overlay) only take effect on CNIs that enforce them (Calico, Cilium, …) and assume ingress-nginx lives in the `ingress-nginx` namespace.

## 🤖 Continuous Integration

| Workflow | Trigger | What it checks |
|---|---|---|
| [`ci.yml`](.github/workflows/ci.yml) | push / PR | **Lint** (ruff), **backend tests on SQLite and Postgres** with a **coverage gate** (`.coveragerc`), migrations in sync, a **backup/restore drill** (dump with the CronJob's pipeline → restore into a fresh DB → compare), **frontend** typecheck + build, `docker compose config` (incl. proxy + monitoring profile), Kubernetes overlays rendered and validated with kubeconform (incl. KEDA / Prometheus Operator / cert-manager CRDs), **Docker images** build and the backend image runs as uid 10001 |
| [`security.yml`](.github/workflows/security.yml) | push / PR / weekly | `pip-audit`, `npm audit` (runtime deps, high+), **CodeQL** for Python and TypeScript |
| [`smoke.yml`](.github/workflows/smoke.yml) | push / PR | Boots the **real stacks on GitHub's runners**: the docker compose stack (`scripts/compose-smoke.sh`: API health, RabbitMQ → worker → Redis round trip, beat, `/metrics`, uid 10001, monitoring profile incl. Grafana datasource/dashboard/queries and Celery events) and the Kubernetes dev overlay on **kind** (`scripts/kind-smoke.sh`), with pod diagnostics on failure |
| [`e2e.yml`](.github/workflows/e2e.yml) | push / PR / nightly | Playwright suite (23 tests) against a seeded API |
| [`load.yml`](.github/workflows/load.yml) | nightly / manual | **Load & soak**: the compose stack in production settings, k6 (`load/k6/main.js`) with p95 / error-rate / isolation thresholds, the `ai` queue drained under that load (`scripts/check_ai_queue.py`), then a `429` still returned through nginx (`load/k6/throttle.js`) |
| [`release.yml`](.github/workflows/release.yml) | `v*.*.*` tag | Publishes `ghcr.io/<owner>/whattocook-{backend,frontend}` |

Dependabot keeps pip, npm, GitHub Actions and Docker base images current.

**Developer tooling:** `make help` lists the common tasks (`make test`, `make cov`, `make smoke`, `make drill`, …); `pre-commit install` adds the same lint gate locally; [`AGENTS.md`](AGENTS.md) documents the invariants and what CI proves (read it before changing queues, compose, k8s or secrets); [`docs/ROADMAP.md`](docs/ROADMAP.md) lists what to build next.
Container-image vulnerability scanning is intentionally not wired through a third-party action (the `trivy-action` tags were hijacked in March 2026); if you add one, pin it to a full commit SHA.
Frontend `npm audit` (dev dependencies included) has no highs since the Tailwind 4 migration. Two *moderate* `react-router` advisories remain (open redirect via backslash in `<Link>`/`useNavigate`); the fix only exists in React Router 7 (roadmap item 11).

## 🛡️ Production hardening

All API traffic is rate-limited per endpoint scope with anon/user-aware
buckets and `Retry-After` responses — see `GetFood/rate_limits.py` (rates
tunable via env), `GetFood/throttles.py`, and `WhatToCook/settings.py`
(on by default; `THROTTLING_ENABLED=false` switches it off for load tests and local debugging only,
never in production). Cache uses a local in-memory backend when Redis is absent.

**Security headers** (`frontend/nginx.conf` + `frontend/nginx/*.conf`): every response
carries `X-Content-Type-Options`, `Referrer-Policy`, `X-Frame-Options`, `Permissions-Policy`
and a `Content-Security-Policy`. The React app gets a strict CSP (`script-src 'self'`, no inline
scripts, only Google Fonts and Unsplash as external origins); Django-rendered pages
(`/admin/`, `/legacy/`, `/api/docs/`) get a baseline CSP; `/media/` is sandboxed. Check any
deployment with `bash scripts/check-security-headers.sh https://your-host`. HSTS is left to the TLS
terminator (Django sends it when `SECURE_HSTS` is on behind HTTPS).

**Supply chain**: every GitHub Action is pinned to a full commit SHA (`# vX.Y.Z` comment; Dependabot keeps both in sync). `release.yml` builds each image locally and scans it with a pinned Trivy before publishing (fixable HIGH/CRITICAL fails the release; the same scan runs on every PR and weekly in `security.yml`, defined once in `.github/actions/scan-image`), publishes with an SPDX SBOM and SLSA provenance, signs the digest keylessly with cosign and verifies the signature. Base tags float, so a new fixable finding is fixed by taking the update (`apk upgrade` in the frontend's `serve` stage, a pinned `setuptools` in `requirements.txt`), not by a `.trivyignore` entry. Verify a published image:

```bash
cosign verify ghcr.io/rezaxr14/whattocook-backend:1.0.0 \
  --certificate-identity-regexp '^https://github.com/rezaxr14/WhatToCook_Smart_Kitchen_OS/\.github/workflows/release\.yml@refs/tags/v' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
docker buildx imagetools inspect ghcr.io/rezaxr14/whattocook-backend:1.0.0 --format '{{ json .SBOM }}'
```

**Load & soak** (`.github/workflows/load.yml`, nightly and on demand; never a PR gate). The soak runs with rate limits **off** and an **empty** `GEMINI_API_KEY`,
so it measures the app and cannot spend LLM quota. Thresholds live in `load/k6/main.js`. Locally: install [k6](https://k6.io/docs/get-started/installation/), start the
API with `THROTTLING_ENABLED=false make run`, then `make load-smoke` (25 s). `POST /api/ai/suggestions/` answers inline and only enqueues when the inline call fails,
so HTTP load never fills the `ai` queue; `python3 scripts/check_ai_queue.py` (compose stack up) publishes a burst of the real task, and asserts the queue drains
and every result lands in Redis. **Not verified until the first run on a runner:** the numbers (thresholds and arrival rates are a first guess for 2 vCPUs); read the
`load-results` artifact (`summary.json`, `k6.log`, `ai-queue.log`) and tighten them.

## 🖼️ Curated dish photography

Every recipe, dish suggestion and pantry ingredient resolves to an
accurate, verified photo (no placeholder repeats): the 12 catalog recipes
ship with original self-hosted photos under `media/recipes/`, while
keyword maps in `GetFood/utils.py` and `frontend/src/utils/imageUtils.ts`
are audited against real stock imagery. Run
`python manage.py seed_recipes` after a fresh DB to bind the photos.

---

## 📄 License

Copyright © 2026. All rights reserved. This project is proprietary software — see [LICENSE.md](LICENSE.md) for the full license terms.
