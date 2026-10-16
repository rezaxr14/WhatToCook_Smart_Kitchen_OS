# Convenience targets (Linux/macOS/WSL/Git Bash). Windows PowerShell has no `make`:
# run the commands shown here directly.
.DEFAULT_GOAL := help
PY ?= python

help: ## list targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n",$$1,$$2}'

install: ## install Python deps
	$(PY) -m pip install -r requirements.txt

test: ## backend tests on SQLite (same as CI's sqlite leg)
	USE_POSTGRES=false $(PY) manage.py test GetFood tests

cov: ## backend tests + coverage gate
	USE_POSTGRES=false coverage run manage.py test GetFood tests && coverage report

lint: ## ruff (syntax errors + pyflakes)
	ruff check .

web: ## frontend typecheck + production build
	cd frontend && npm ci && npm run build

e2e: ## Playwright (needs the API on :8000: make run)
	cd frontend && npm run test:e2e

run: ## Django dev server on :8000
	USE_POSTGRES=false $(PY) manage.py runserver 127.0.0.1:8000

up: ## docker compose stack
	docker compose up -d --build --wait

down: ## stop the stack (keeps volumes)
	docker compose down

logs: ## follow web + celery logs
	docker compose logs -f web celery

smoke: ## end-to-end check of the compose stack (CI runs this too)
	bash scripts/compose-smoke.sh

k8s-render: ## render the Kubernetes overlays
	kubectl kustomize k8s/overlays/dev >/dev/null && kubectl kustomize k8s/overlays/prod >/dev/null && echo ok

k8s-smoke: ## deploy the dev overlay to kind and verify (CI runs this too)
	bash scripts/kind-smoke.sh

drill: ## backup/restore drill (needs Postgres env, see the script header)
	bash scripts/backup-restore-drill.sh

.PHONY: help install test cov lint web e2e run up down logs smoke k8s-render k8s-smoke drill
