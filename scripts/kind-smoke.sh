#!/usr/bin/env bash
# Deploy the dev overlay to a local kind cluster and verify the whole stack.
# Needs: docker, kind, kubectl. Run locally.
#   ./scripts/kind-smoke.sh              # create/reuse the cluster, deploy, verify
#   TEARDOWN=1 ./scripts/kind-smoke.sh   # delete the cluster afterwards
set -euo pipefail
cd "$(dirname "$0")/.."
CLUSTER="${CLUSTER:-whattocook}"
NS=whattocook
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
diagnose() {
  echo "----- diagnostics -----"
  kubectl get nodes -o wide || true
  kubectl describe nodes | grep -A8 "Allocated resources" || true
  kubectl -n "$NS" get pods,pvc,svc -o wide || true
  kubectl -n "$NS" get events --sort-by=.lastTimestamp | tail -40 || true
  # Why is a pod not Running? (Pending => FailedScheduling / unbound PVC shows up here)
  for p in $(kubectl -n "$NS" get pods --no-headers | awk '$3!="Running" && $3!="Completed"{print $1}'); do
    echo "== describe $p =="; kubectl -n "$NS" describe pod "$p" | sed -n '/^Events:/,$p;/Conditions:/,/Volumes:/p' | head -40
  done
  for d in web celery celery-beat; do echo "== logs deploy/$d =="; kubectl -n "$NS" logs "deploy/$d" --tail=60 2>&1 || true; done
  for s in postgres rabbitmq; do echo "== logs sts/$s =="; kubectl -n "$NS" logs "statefulset/$s" --tail=40 2>&1 || true; done
}
fail() { printf '  \033[31m✘\033[0m %s\n' "$*"; diagnose; exit 1; }

kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER"
kubectl config use-context "kind-$CLUSTER" >/dev/null

echo "▶ building + loading images"
docker build -t whattocook-backend:latest .
docker build -t whattocook-frontend:latest ./frontend
kind load docker-image --name "$CLUSTER" whattocook-backend:latest whattocook-frontend:latest

echo "▶ applying k8s/overlays/dev"
kubectl apply -k k8s/overlays/dev

echo "▶ waiting for rollouts"
for r in statefulset/postgres statefulset/rabbitmq deployment/redis deployment/web deployment/celery deployment/celery-beat deployment/frontend; do
  kubectl -n "$NS" rollout status "$r" --timeout=420s >/dev/null && ok "$r ready" || fail "$r did not become ready"
done

echo "▶ verifying"
kubectl -n "$NS" port-forward svc/web 18000:8000 >/dev/null 2>&1 & PF=$!
trap 'kill $PF 2>/dev/null || true; [ "${TEARDOWN:-0}" = "1" ] && kind delete cluster --name "$CLUSTER"' EXIT
sleep 4
body=$(curl -fsS http://localhost:18000/api/health/) || fail "health unreachable"
echo "    $body"
echo "$body" | grep -q '"broker": *"ok"' && ok "API -> RabbitMQ ok" || fail "broker not ok"
rt=$(kubectl -n "$NS" exec deploy/web -- python manage.py shell -c "
from GetFood.tasks import cleanup_expired_ai_cache as t
print('RESULT', t.delay().get(timeout=60))") || true
echo "    $rt"
grep -q RESULT <<<"$rt" && ok "RabbitMQ -> worker -> Redis round trip" || fail "task round trip failed"
[ "$(kubectl -n "$NS" exec deploy/web -- id -u)" = "10001" ] && ok "web runs as uid 10001" || fail "web not uid 10001"
kubectl -n "$NS" exec deploy/web -- sh -c 'touch /app/media/.t && rm /app/media/.t' && ok "media PVC writable (fsGroup)" || fail "media PVC not writable"
echo; echo "All checks passed. UI: kubectl -n $NS port-forward svc/frontend 4173:80"
