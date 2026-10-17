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
| Frontend | `make web` (typecheck, build, bundle budget) | `ci.yml` frontend (incl. `check:bundle`), `e2e.yml` (Playwright, incl. the CSP suite on the production build) |
| Anything that changes how pages look (CSS framework, theme, layout) | `npm run test:visual` (needs the API + two builds, so use CI) | `visual.yml` (screenshots of `main` vs the PR, diff table + images; informational) |
| nginx headers / CSP (`frontend/nginx*`) | `bash scripts/check-security-headers.sh <url>` against any nginx | `smoke.yml` → `compose-smoke.sh` (curls every header), `e2e.yml` (`test:e2e:csp`) |
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
- **Shopping lists are owner-scoped.** Rows belong to a user or to one anonymous *session* (`_shopping_scope`/`_shopping_qs` in `views.py`); never look rows up by id alone and never add a shared fallback bucket. API errors never echo exception text (log it instead).
- **Security headers live in nginx only.** `frontend/nginx.conf` includes `nginx/security-headers.conf` plus exactly one CSP snippet **in every location** (nginx drops inherited `add_header` as soon as a location declares its own), and proxied locations include `hide-upstream-security-headers.conf` so Django's copies aren't sent twice. The SPA's strict CSP (`nginx/csp-spa.conf`, one `add_header` line) is read by `vite preview`; `npm run test:e2e:csp` fails on any violation. A new external origin (font, image, `fetch`) must be added to that file; never add inline scripts or `on*=` handlers. Django-rendered pages (`/admin/`, `/legacy/`, `/api/docs/`) get only the baseline CSP because they rely on inline scripts.
- **Local media is returned as relative paths.** Serializers emit `/media/...`, never `request.build_absolute_uri(...)`: Host/port/scheme differ behind Vite's proxy and nginx, and the SPA CSP is `img-src 'self'`. (`tests/test_media_urls.py`)
- **Keep `three` out of the entry graph.** Only `components/three/journey/JourneyScene` (lazy) may import `three`/`@react-three/*`; eagerly imported modules such as `journey/state.ts` must not (one `import * as THREE` once added ~360 kB to every route). Non-landing pages are `React.lazy` in `App.tsx`. `frontend/scripts/check-bundle.mjs` enforces the budgets; raise them deliberately, in the PR that needs it.
- **Tailwind 4: the theme lives in `src/index.css` (`@theme`); there is no `tailwind.config.js`.** Write v4 vocabulary (`shadow-xs` is v3's `shadow-sm`, `rounded-sm`, `shrink`/`grow`, `bg-linear-to-*`, `outline-hidden`, `inset-s/e-*`). Keep gradients on `/srgb` (`bg-linear-to-r/srgb`) or they interpolate in oklab and drift from the design. `@layer base` re-adds two v3 preflight behaviours (button `cursor: pointer`, gray-400 placeholders; tested in `e2e-csp/styles.spec.ts`). Beware class names that were silently dead in v3 and are *valid* in v4 (`scrollbar-none`, `bottom-22`, `shadow-2xs`, …): they change the layout the moment they work. See roadmap item 5 for the ones deliberately left out.
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
