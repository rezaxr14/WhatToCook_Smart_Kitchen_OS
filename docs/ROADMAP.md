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
   **First CI run of the smoke check (2026-10-20) failed: `Prometheus is not scraping all of [...]` (90 s), without saying which target.** Cause found by
   reproducing it with the real Prometheus 3.5.0 against the real app: the API job was permanently down. Prometheus scrapes `web:8000`, so it sends
   `Host: web:8000`; Django answers 400 to a host not in `ALLOWED_HOSTS`, and the DEBUG default is `localhost,127.0.0.1,0.0.0.0` (compose never set it).
   So the compose monitoring profile had never scraped the API; nothing asserted it until this check. Fixed: compose sets
   `ALLOWED_HOSTS=${ALLOWED_HOSTS:-localhost,127.0.0.1,0.0.0.0,web}` (a user-set value in `.env` wins, so `.env.example` now says to keep `web`; it also
   claimed a `"*"` default that has not existed). `check_grafana.py` now explains a failed scrape check: every expected job's health, URL and
   `lastError` read from Prometheus (directly on `--prometheus`, default localhost:9090, then through Grafana's proxy), with a hint for 400 (ALLOWED_HOSTS)
   and 401 (METRICS_TOKEN). Verified: with the real binary a rejected Host gives `down` + `HTTP status 400 Bad Request` and an allowed one gives
   `up == 1`; tests pin the compose default against `monitoring/prometheus.yml` and send the scrape's Host to `/metrics`; 17 mutations caught.
   **Not verified:** the other three jobs (`rabbitmq`, `rabbitmq-per-object`, `celery-flower`) in compose: they were never the reported failure, but the
   log did not say, so if one of them is also down the check now names it. `docker compose` itself (the interpolation) was not run.
   **Open question, not changed:** `k8s/optional/servicemonitor.yaml` scrapes the API by pod address, so under the prod overlay's strict `ALLOWED_HOSTS`
   (`whattocook.example.com,web`) the same 400 is likely there too; probes avoid it with `httpHeaders: Host: web`, a ServiceMonitor has no equivalent (resolved 2026-10-21: each pod allows its own IP through `POD_IP`, see `_with_pod_ip` in `settings.py`).
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
   Not done (base images are pinned since 2026-10-21, see item 10): SARIF upload to code scanning, attaching the SBOM to GitHub releases, multi-arch (item 10).
   **First CI scan (2026-10-20) reported four fixable HIGH findings; fixed:** frontend (alpine 3.24.2): libexpat CVE-2026-77214 and libx11 CVE-2026-88806 ->
   `apk upgrade --no-cache` as the first instruction of a named `serve` stage, which the scan builds (and only the scan builds) rebuild without cache
   (`no-cache-filters`), so a cached layer cannot hide a later fix and the published image is still exactly what was scanned. Backend: jaraco.context 5.3.0
   and wheel 0.45.1 *vendored inside the setuptools 79.0.1 that python:3.11-slim ships* -> `setuptools~=84.0.0` in `requirements.txt` (80.10.2 clears those
   but carries CVE-2026-59890, fixed in 83.0.0; 82+ no longer ships `pkg_resources`, which nothing of ours imports: a test guards that). Verified: a clean
   venv from `requirements.txt` has the fixed vendored copies, the suite passes (318) and the Celery CLI loads (Python 3.12 here, 3.11 in the image).
   **Not verified:** the Trivy re-scan itself (DB unreachable) and that Alpine's repo already carries libexpat 2.9.0-r0 / libx11 1.8.14-r0 (index unreachable;
   Trivy's own table names them as the fixed versions). `.trivyignore` stays empty.
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
10. ~~**GitOps + multi-arch**~~ **Done as code; nothing here has run yet: it needs a tag push and a cluster.** Argo CD was chosen (the roadmap said Argo CD/Flux; no Flux manifests).
   **Multi-arch:** `release.yml` builds `linux/amd64` + `linux/arm64` in one index (QEMU for arm64 only, `docker/setup-qemu-action` v4.4.0 pinned by SHA), scans **both** architectures
   before publishing, and afterwards checks the published index really contains both (the check's jq filter is tested against single-arch, attestation-only and windows-only
   indexes). The SPA is built once on the native builder (`FROM --platform=$BUILDPLATFORM`): its output is architecture-independent and emulating Node would be slow. All 61
   backend requirements resolve to **prebuilt aarch64 wheels** for Python 3.11 (checked with `pip download --platform manylinux2014_aarch64`; no sdist, so no compiler under QEMU).
   Each scan build has its own GHA cache scope (two exports to one scope overwrite each other); the publish build reads both and does not bypass the cache, so what ships is
   what was scanned. Job timeout 30 -> 60 min. **GitOps:** `k8s/gitops/argocd/` has an `AppProject` (exactly the kinds the prod overlay renders, no Secret, no wildcard) and an
   `Application` (path `k8s/overlays/prod`, `main`, automated prune + self-heal, **no `resources-finalizer`**: deleting the Application must not delete the database); both validated
   strictly against the real Argo CD v3.5.6 CRD schemas (and the validator was shown to reject a misspelled field and a wrong type). The two PVCs in git (`media`,
   `postgres-backups`) carry `Prune=false`. The new `gitops-bump` job (tags only, `contents`/`pull-requests` write + `packages` read, no `id-token`) resolves each published
   digest, **cosign-verifies it against the release workflow's identity**, runs `scripts/set_image_digests.py` and opens a **pull request** (never a push to `main`); merging it is the
   deployment. The script writes `newTag` + `digest`; checked with real kustomize 5.8.3 that this renders `image:1.2.3@sha256:...` for all six image references (five backend, one frontend), idempotently, and that a
   re-bump replaces rather than stacks. `tests/test_gitops.py`: 41 tests, 49 mutations caught.
   **Not verified (all need a tag or a cluster):** the QEMU build and the arm64 Trivy scan of a loaded foreign-architecture image; that `docker buildx imagetools inspect` prints a
   `Digest:` line the way the bump job parses it (a wrong parse cannot slip through: `cosign verify` fails on a digest that was not signed); `gh pr create` (needs the setting
   *Allow GitHub Actions to create and approve pull requests*); Argo CD itself (never applied to a cluster; Argo's bundled kustomize was not checked, only 5.8.3). Rehearse with a
   pre-release tag such as `v0.0.1-rc.1`. **Known gaps, deliberately not hidden:** (1) `setup-qemu-action` runs `docker.io/tonistiigi/binfmt:latest --privileged` and that image is **not
   pinned by digest** (no registry was reachable to resolve one; the workflow says so at the call site and a test insists it does until it is pinned). Pin it with `image:
   docker.io/tonistiigi/binfmt@sha256:<digest>`. Native arm64 runners would avoid it but need a per-platform push-and-merge design. (2) Pull-request scans (`ci.yml`, `security.yml`) stay amd64-only.
   (3) Base images (`python:3.11-slim`, `nginx:alpine`, `node:20-alpine`) are still not pinned by digest, for the same reason. (4) `ci.yml` downloads kubeconform from `releases/latest`: unpinned.
   **Update 2026-10-21:** the `v0.0.1-rc.2` tag run of `release.yml` succeeded (every `publish` step, then `gitops-bump` pushed `gitops/release-0.0.1-rc.2`); CI passed on the bump PR. PR #31 was opened **by hand**, not by the job, so `gh pr create` in `gitops-bump` is still unproven (`GITOPS_TOKEN` is set; check the setting *Allow GitHub Actions to create and approve pull requests*). Gaps (1) and (3) are closed for `tonistiigi/binfmt`, `python:3.11-slim` and `nginx:alpine` (digests of the multi-arch indexes); `node:20-alpine` is pinned in the Node bump. Still tag-only, not digest-pinned: the service images in `docker-compose.yml` and `k8s/` (postgres, redis, rabbitmq, flower, prometheus, grafana), and `postgres:15-alpine` in `ci.yml`.
   (5) `k8s/overlays/prod` still carries the placeholder host `whattocook.example.com`: replace it **before** applying the Application. (6) Open question from item 6 still stands: the optional
   ServiceMonitor hit the same `ALLOWED_HOSTS` 400 under the prod overlay: fixed 2026-10-21 (neither the operator CRD nor Prometheus can set `Host`, so the pod's own IP is allowed). Not run against a cluster: only the tests and CI manifest checks prove it.
11. ~~**React Router 6 → 7**~~ **Done** (pending the e2e / `e2e-csp` run on the PR, which is this item's own done-criterion): `react-router@^7.18.4`, `react-router-dom` and
   `@remix-run/router` removed (v7 folds the dom package into `react-router`; the 13 imports changed mechanically). `npm audit` is 0 vulnerabilities, dev dependencies
   included (it listed two moderate advisories; vulnerable range is <= 7.17.0). **Version choice:** `latest` is 8.5.0, which needs React >= 19.2.7 and Node >= 22.22; this
   app is on React 18 and builds on `node:20-alpine`, so 7.18.4 (npm's `version-7` tag, five weeks old, Node >= 20, React >= 18). **Decision for you to revisit:**
   `<Router useTransitions={false}>`. v7 wraps router updates in `React.startTransition` by default; with every route lazy-loaded that would keep the old page on screen
   (no `RouteFallback` spinner) while a chunk loads, so the migration keeps today's behaviour; remove the prop to opt in. Cost: `vendor-react` 165.0 -> 182.9 kB raw, initial
   graph 196.5 kB gzip against the 220 kB budget (v7 adds `cookie` and `set-cookie-parser`, both assigned to `vendor-react`). `tests/test_frontend_deps.py` pins the version window
   (>= 7.18, < 8), no leftovers of the old packages, the chunk rule, `useTransitions={false}`, and Node pins against the router's `engines`; 12 mutations caught.
   **Verified here:** `tsc -b` + `vite build` (exit 0), `check:bundle`, `npm audit`, `playwright test --list` for all three configs (23 + 18 + 18 tests). **Not verified:** any
   browser behaviour: Playwright was not run (by design), so navigation, the lazy-route fallback and the CSP chunk checks are proven only by CI. Separate observation: Node 20 reached
   end-of-life in April 2026 (Dockerfile and four workflows); a Node bump is not part of this item.
12. ~~**Node 20 → 24**~~ **Done** (pending CI on the PR). Node 20 reached end-of-life on 2026-04-30; `frontend/Dockerfile` and the four `setup-node` pins (ci, e2e, security, visual) now run Node 24 (LTS until 2028-04-30, `nodejs/Release` `schedule.json`), `@types/node` moved to 24.19.1 (19 days old; the lockfile also takes `undici-types` 7.24.6). Node 26 becomes LTS on 2026-10-28: a later bump, not this one. Every `engines` range in the lockfile allows 24 (vite `^18 || ^20 || >=22`, react-router `>=20`, playwright `>=20`). **Verified here, on Node 24.22.0:** `npm ci`, `vite build`, `check:bundle`, `npm audit` (0 vulnerabilities), `playwright test --list` (23 tests); `NodeVersionTests` keep one major everywhere, off end-of-life, with matching types; 9 mutations caught. **Not verified:** `node:24-alpine` resolving on Docker Hub and the musl native binaries inside the image (Docker is not run here: CI's image build and smoke prove it), and any browser behaviour. `node:24-alpine` is the one base image still not pinned by digest (`UNPINNED_ON_PURPOSE` in `tests/test_images.py`): pin it with `docker buildx imagetools inspect node:24-alpine | awk '/^Digest:/ {print $2; exit}'` and remove it from that list.
