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
4. ~~**Frontend bundle.**~~ **Done** (pending CI on the PR): entry chunk 1,060 kB (313 kB gz) → 208 kB (66 kB gz); critical path (entry + modulepreloads)
   is 190 kB gz. Root cause was one `import * as THREE` in `journey/state.ts` (eagerly imported by the landing page) putting ~360 kB of three into
   every route; fixed by inlining `smoothstep` (verified identical to three's on 200k cases). Also: 7 pages `React.lazy`, `manualChunks`
   (react / motion / i18n / query / three), a one-time reload on `vite:preloadError` (stale tab after a deploy). No chunk warning: the lazy 3D
   vendor chunk (~920 kB, only loaded by the landing scene) has a documented 1,000 kB budget; `npm run check:bundle` (CI + `make web`) holds every
   other chunk to 300 kB and the initial graph to 220 kB gz, and fails if three appears up front. Not done: prefetching route chunks on hover,
   an error boundary for a chunk that stays unreachable (offline) - today that shows a blank page, as the lazy 3D scene already did.
5. ~~**Tailwind 3 → 4.**~~ **Done** (pending CI on the PR): `npm audit --audit-level=high` including dev dependencies now exits 0 (9 findings → 2 moderate;
   all 5 highs hung off the `tailwindcss@3` chain). Migrated with the official upgrade tool, then audited, because it is not trustworthy on its own:
   it rewrote the `outline` *variant name* in `StyledButton.tsx` (a string, not a class; reverted - `tsc` caught it) and renamed 5 classes that were dead in v3.
   Parity work: compared the generated class sets (no utility silently dropped), re-added v3's button cursor and gray-400 placeholder in `@layer base`
   (`e2e-csp/styles.spec.ts`), pinned 39 gradients to sRGB (`/srgb`; v4 defaults to oklab), checked no element combines a Tailwind transform with a JS
   transform (v4 composes them), and verified the lockfile has the musl native binaries the `node:20-alpine` image needs.
   **Deliberately NOT activated** - these classes were silently dead in v3 (many are v4 vocabulary) and would change rendering the moment v4 honours them;
   removed to keep parity, decide per item whether to re-add: `shadow-2xs` (18 places), `scrollbar-none` (3: IngredientPicker, RecipeChatBox, RecipeFilter),
   `scrollbar-thin` (AIProviderSwitcher), `rounded-tl-xs`/`rounded-tr-xs` (RecipeChatBox bubble corners), `group-hover:scale-108` (IngredientPicker, PantryShelf),
   `bottom-22 lg:bottom-26` and `lg:w-68` (LandingPage floating cards), `border-stone-100/12` (LandingPage pill).
   Screenshots: `visual.yml` renders `main` and the PR with the same Playwright script and posts a per-page diff table + diff images (informational;
   set `VISUAL_FAIL_ABOVE_PCT` to gate). Known, expected change: `space-x-*`/`divide-*` now use logical margins, so RTL (fa/ar) rows gain their gap.

## Later
6. ~~**Grafana**~~ **Done** (pending CI on the PR): `grafana` in the compose `monitoring` profile (pinned `grafana/grafana:13.2.4`, localhost-only, real healthcheck,
   no anonymous access) with a provisioned Prometheus datasource and the "WhatToCook / Overview" dashboard (22 panels, 25 queries: scrape health,
   request rate by status class, latency p50/p95/p99 and p95 per view, exceptions, Celery outcomes/runtime/workers, RabbitMQ backlog/unacked/consumers
   per queue); `k8s/optional/grafana.yaml`, a Flower ServiceMonitor and a per-queue RabbitMQ endpoint on the existing one. `compose-smoke.sh` runs
   `scripts/check_grafana.py`: health, datasource health, dashboard provisioned with every panel, every query executed through Grafana, all four scrape
   targets up, API counters flowing and a Celery worker online. Found on the way: **nothing enabled Celery events**, so Flower's task metrics (and any
   Celery panel) would have been empty; fixed with `CELERY_WORKER_SEND_TASK_EVENTS` (env `CELERY_SEND_EVENTS`). Per-queue visibility needs RabbitMQ's
   `/metrics/per-object` endpoint (the default one only aggregates), hence a second Prometheus job. Verified against a real Prometheus 3.5.0, not
   against Grafana or RabbitMQ themselves (neither could run in the sandbox): RabbitMQ series names are documentation-verified, Grafana's behaviour is
   what the smoke test proves. Not done: alert rules (Prometheus/Alertmanager), a Postgres/Redis exporter, a Flower scrape secret (not needed: its
   /metrics is unauthenticated).
7. **Domain events on RabbitMQ** (e.g. `pantry.updated`, `recipe.generated`) with an idempotent consumer. Choose **Kafka only if** you need replay or many independent consumers; for fan-out/work-queue semantics RabbitMQ already fits. Needs a product decision first.
8. ~~**Supply chain**~~ **Done** (pending CI and a real release run): all 34 action references pinned to commit SHAs (each resolved from the upstream repo with
   `git ls-remote`, cross-checked against the moving major tag; trivy-action's and cosign-installer's own nested actions are already SHA-pinned upstream);
   `release.yml` now builds locally -> scans (Trivy v0.76.0, fixable HIGH/CRITICAL fails, **before** anything is published) -> publishes with `sbom: true` and
   `provenance: mode=max` -> signs the digest keylessly (cosign v3.1.3, OIDC, no keys) -> verifies against the workflow identity -> confirms the SPDX SBOM is
   attached. The scan is one local composite action shared with `security.yml`'s new `image-scan` job (every PR + weekly); `.trivyignore` requires a reason
   per entry. Also: `security.yml` now audits dev dependencies (item 5's done-when), Dependabot covers the composite action. 15 tests in
   `tests/test_workflows.py`, mutation-tested with 9 regressions. **Not verified (could not run here):** the scan on the real images (the vulnerability DB is
   not reachable from the sandbox, so the first CI run may report real findings: fix by updating the base image/dependency, or add a justified `.trivyignore`
   entry), and the release job itself (cosign v3 against ghcr.io, `imagetools` output shape): run `release.yml` once via `workflow_dispatch` and read the log.
   Not done: base images pinned by digest, SARIF upload to code scanning, attaching the SBOM to GitHub releases, multi-arch (item 10).
9. ~~**Load/soak**~~ **Done** (pending the first CI run, which is also the calibration run): `.github/workflows/load.yml` (nightly + `workflow_dispatch`, never a
   PR gate) boots the compose stack in production settings (DEBUG=false, random secrets), rate limits off and an **empty `GEMINI_API_KEY`** (the provider fails
   instantly into the fallback: nothing can spend LLM quota), soaks it with k6 v2.3.0 (pinned by sha256) and, **while that load runs**, bursts tasks onto the
   `ai` queue and proves it drains. `load/k6/main.js`: open-model arrival-rate scenarios (catalog, can-cook, per-session shopping list, AI suggestions, SPA
   shell); thresholds on error rate, p95 per endpoint (catalog/stats 500 ms, can-cook 1.5 s, shopping 800 ms, AI 2 s), dropped iterations, and any
   cross-session shopping-list leak (the owner-scoping invariant under concurrency). `load/k6/throttle.js`: afterwards rate limiting is switched back on and a
   `429` + `Retry-After` + JSON body must still come back through nginx. `scripts/check_ai_queue.py`: no Gemini key in web or worker (aborts *before*
   publishing), management API up with a consumer on `ai`, N messages published to `ai`, ready=0/unacked=0 on consecutive polls with N acks, all N results
   SUCCESS with the degraded fallback in Redis. 48 tests (`tests/test_load.py`, `test_ai_queue_check.py`, `test_throttling.py`), mutation-tested (9 on the
   checker, 15 on the workflow/scripts, 3 on the throttle fix).
   **Found on the way:** (1) `THROTTLING_ENABLED=false` made **every scoped endpoint return 500** (an emptied rate table, then an `ImportError` in the error path);
   fixed and tested, and README no longer documents a `USE_RATE_LIMITS` variable that never existed. (2) **HTTP load never reaches the `ai` queue**:
   `ai_suggestions_api` answers inline and only enqueues when the inline call raises, and the provider layer swallows provider errors into the fallback, so a
   queue-drain check driven by HTTP would pass trivially. The check therefore publishes the burst itself with the real task. If you want the *endpoint* to
   enqueue under load, that needs a product-code switch (e.g. an `AI_FORCE_ASYNC` flag): not done, decide first.
   **Verified here:** k6 ran the `smoke` profile of both scripts against a production-mode gunicorn (SQLite) and exits 0; the same scripts exit 99 under an
   impossible threshold, with throttling left on, and (throttle.js) with throttling off; the checker's generated code ran against the real task (eager mode);
   RabbitMQ management field names are documentation-verified; `actionlint` + `shellcheck` are clean on `load.yml` (they do flag three pre-existing SC2034 unused-loop-variable warnings in `e2e.yml` and `visual.yml`, untouched here). **Not verified (needs a runner):** the
   workflow itself (compose with DEBUG=false, nginx behind it, the throttle phase's `up --force-recreate`), the real RabbitMQ stats lag, and every number
   above: the thresholds and arrival rates are a first guess for a 2-vCPU runner. Read the first run's `load-results` artifact, then tighten them.
   Not done: pushing k6 metrics to Prometheus/Grafana, trend history across nights, a notification on failure, authenticated-user scenarios.
10. **GitOps:** Argo CD/Flux pointing at `k8s/overlays/prod`, image tag bumps from `release.yml`; multi-arch (arm64) images.
11. **React Router 6 → 7.** `npm audit` reports two moderate advisories in production dependencies (`react-router`, `react-router-dom`: open redirect via backslash in `<Link>`/`useNavigate`, CVE-2025-68470 bypass); the fix exists only in v7. *Done when* `npm audit` is fully clean and e2e + `e2e-csp` are green.
