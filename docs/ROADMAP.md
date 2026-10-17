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
6. **Grafana** in the compose `monitoring` profile (provisioned Prometheus datasource + a dashboard: request rate/p95/5xx from `django_http_*`, RabbitMQ queue depth, Flower task metrics) and a k8s optional manifest. *Done when* `compose-smoke.sh` checks Grafana health + datasource.
7. **Domain events on RabbitMQ** (e.g. `pantry.updated`, `recipe.generated`) with an idempotent consumer. Choose **Kafka only if** you need replay or many independent consumers; for fan-out/work-queue semantics RabbitMQ already fits. Needs a product decision first.
8. **Supply chain:** SBOM (`docker buildx --sbom`), keyless image signing (cosign) in `release.yml`, pin every action by SHA, image vulnerability scan with a SHA-pinned scanner.
9. **Load/soak:** nightly k6 against the compose stack with thresholds (p95 latency, error rate) and a check that the `ai` queue drains.
10. **GitOps:** Argo CD/Flux pointing at `k8s/overlays/prod`, image tag bumps from `release.yml`; multi-arch (arm64) images.
11. **React Router 6 → 7.** `npm audit` reports two moderate advisories in production dependencies (`react-router`, `react-router-dom`: open redirect via backslash in `<Link>`/`useNavigate`, CVE-2025-68470 bypass); the fix exists only in v7. *Done when* `npm audit` is fully clean and e2e + `e2e-csp` are green.
