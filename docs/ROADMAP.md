# Roadmap

Everything above the line is done and green in CI: RabbitMQ broker, Redis integration, Celery
retries/queues/beat/Flower, structured logs + Prometheus + optional Sentry, hardened images,
Kubernetes (base/dev/prod, NetworkPolicy, backups, KEDA/Flower/ServiceMonitor add-ons), CI
(lint, SQLite+Postgres, coverage gate, backup/restore drill, kubeconform, compose+kind smoke, e2e,
CodeQL, audits, GHCR release).

Items below are ordered by value/risk. Each has an acceptance test; add a CI check wherever it makes sense.

## Next
1. ~~**Raise coverage where it is thinnest.**~~ **Done** (pending CI on the PR): `ai_service.py` 34% → 99%, `views.py` 60% → 99%,
   total 60% → 93%; gate ratcheted 58 → 90 in `.coveragerc`. Remaining soft spots: `WhatToCook/settings.py` (69%), `GetFood/utils.py` (69%),
   `GetFood/tasks.py` (81%). `tests/test_ai_service.py`, `tests/test_views_ai.py`, `tests/test_views_misc.py` hold the new tests.
2. ~~**OpenAPI docs.**~~ **Done** (pending CI on the PR): `drf-spectacular` + local Swagger UI assets (`drf-spectacular-sidecar`, no CDN) at
   `/api/schema/` and `/api/docs/`; all 30 function views annotated (shapes live in `GetFood/api_schemas.py`); `/legacy/` aliases excluded.
   `ci.yml` runs `spectacular --validate --fail-on-warn`; `tests/test_openapi.py` asserts the AI endpoints are listed and every `api/` route is documented.
   Note for item 3: the Swagger UI page uses inline scripts, so the CSP needs an exception (or a nonce) for `/api/docs/`.
3. ~~**Security headers.**~~ **Done** (pending CI on the PR): `frontend/nginx.conf` + `frontend/nginx/*.conf` send nosniff, Referrer-Policy,
   X-Frame-Options, Permissions-Policy and a CSP on every location (strict for the SPA, baseline for Django pages, sandboxed `/media/`).
   Found and fixed while auditing: the inline `onload` font trick (fonts would have stayed `media=print`) and the scanner's sample-photo
   `fetch()` to Unsplash (needs `connect-src`). `smoke.yml` runs `scripts/check-security-headers.sh`; `e2e.yml` also runs `npm run test:e2e:csp`
   (production build under the real CSP, since the main e2e uses the Vite dev server which has no CSP). Not done on purpose: HSTS (TLS
   terminator's job), `style-src` without `'unsafe-inline'` (React/framer-motion/drei write inline styles), strict CSP on Django pages.
4. **Frontend bundle.** The main chunk is ~1.06 MB (Vite warns >500 kB): route-level `React.lazy` + `manualChunks` for `three`/react. *Done when* the build has no chunk warning (or a documented budget) and e2e is green.
5. **Tailwind 3 → 4.** Clears the dev-only `npm audit` highs. *Done when* `npm audit --audit-level=high` (including dev) is clean, e2e is green, and screenshots of the main pages are compared.

## Later
6. **Grafana** in the compose `monitoring` profile (provisioned Prometheus datasource + a dashboard: request rate/p95/5xx from `django_http_*`, RabbitMQ queue depth, Flower task metrics) and a k8s optional manifest. *Done when* `compose-smoke.sh` checks Grafana health + datasource.
7. **Domain events on RabbitMQ** (e.g. `pantry.updated`, `recipe.generated`) with an idempotent consumer. Choose **Kafka only if** you need replay or many independent consumers; for fan-out/work-queue semantics RabbitMQ already fits. Needs a product decision first.
8. **Supply chain:** SBOM (`docker buildx --sbom`), keyless image signing (cosign) in `release.yml`, pin every action by SHA, image vulnerability scan with a SHA-pinned scanner.
9. **Load/soak:** nightly k6 against the compose stack with thresholds (p95 latency, error rate) and a check that the `ai` queue drains.
10. **GitOps:** Argo CD/Flux pointing at `k8s/overlays/prod`, image tag bumps from `release.yml`; multi-arch (arm64) images.
