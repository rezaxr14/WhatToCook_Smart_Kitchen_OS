# Roadmap

Everything above the line is done and green in CI: RabbitMQ broker, Redis integration, Celery
retries/queues/beat/Flower, structured logs + Prometheus + optional Sentry, hardened images,
Kubernetes (base/dev/prod, NetworkPolicy, backups, KEDA/Flower/ServiceMonitor add-ons), CI
(lint, SQLite+Postgres, coverage gate, backup/restore drill, kubeconform, compose+kind smoke, e2e,
CodeQL, audits, GHCR release).

Items below are ordered by value/risk. Each has an acceptance test; add a CI check wherever it makes sense.

## Next
1. **Raise coverage where it is thinnest.** `GetFood/ai_service.py` is at ~34%: mock the Gemini/LM Studio providers and cover the error/quota/fallback branches, plus the error paths in `GetFood/views.py` (~60%). *Done when* the gate (`.coveragerc`) is ratcheted to ≥ 70%.
2. **OpenAPI docs.** `drf-spectacular`: `/api/schema/` + Swagger UI at `/api/docs/`. *Done when* CI runs `manage.py spectacular --validate --fail-on-warn` and a test asserts the schema lists the AI endpoints.
3. **Security headers.** CSP, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy` in `frontend/nginx.conf` (check the 3D scene, fonts and Gemini-less flows still work). *Done when* `smoke.yml` curls the headers and `e2e.yml` stays green.
4. **Frontend bundle.** The main chunk is ~1.06 MB (Vite warns >500 kB): route-level `React.lazy` + `manualChunks` for `three`/react. *Done when* the build has no chunk warning (or a documented budget) and e2e is green.
5. **Tailwind 3 → 4.** Clears the dev-only `npm audit` highs. *Done when* `npm audit --audit-level=high` (including dev) is clean, e2e is green, and screenshots of the main pages are compared.

## Later
6. **Grafana** in the compose `monitoring` profile (provisioned Prometheus datasource + a dashboard: request rate/p95/5xx from `django_http_*`, RabbitMQ queue depth, Flower task metrics) and a k8s optional manifest. *Done when* `compose-smoke.sh` checks Grafana health + datasource.
7. **Domain events on RabbitMQ** (e.g. `pantry.updated`, `recipe.generated`) with an idempotent consumer. Choose **Kafka only if** you need replay or many independent consumers; for fan-out/work-queue semantics RabbitMQ already fits. Needs a product decision first.
8. **Supply chain:** SBOM (`docker buildx --sbom`), keyless image signing (cosign) in `release.yml`, pin every action by SHA, image vulnerability scan with a SHA-pinned scanner.
9. **Load/soak:** nightly k6 against the compose stack with thresholds (p95 latency, error rate) and a check that the `ai` queue drains.
10. **GitOps:** Argo CD/Flux pointing at `k8s/overlays/prod`, image tag bumps from `release.yml`; multi-arch (arm64) images.
