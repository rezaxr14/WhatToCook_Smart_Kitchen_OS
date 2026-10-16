#!/usr/bin/env bash
# Proves the nightly backup (k8s/overlays/prod/postgres-backup.yaml) can really be restored:
# bootstrap a source DB -> dump with the CronJob's pipeline -> restore into a fresh DB ->
# compare row counts -> check that Django considers the restored schema fully migrated.
# Needs a reachable Postgres plus psql/pg_dump, and the Python deps. Runs in CI (ci.yml).
#   POSTGRES_PASSWORD=... PGHOST=localhost PGPORT=5432 ./scripts/backup-restore-drill.sh
set -euo pipefail
cd "$(dirname "$0")/.."

: "${PGHOST:=localhost}" "${PGPORT:=5432}" "${POSTGRES_USER:=whattocook}" "${POSTGRES_DB:=whattocook}"
: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}"
export PGHOST PGPORT PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD"
export USE_POSTGRES=true DB_HOST="$PGHOST" DB_PORT="$PGPORT" POSTGRES_USER POSTGRES_PASSWORD POSTGRES_DB
RESTORE_DB="${POSTGRES_DB}_restore"
tmp=$(mktemp -d)
cleanup() { rm -rf "$tmp"; psql -d postgres -qAt -c "DROP DATABASE IF EXISTS \"$RESTORE_DB\"" >/dev/null 2>&1 || true; }
trap cleanup EXIT
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$*"; exit 1; }

# recipes/ingredients/applied-migrations - enough to notice a truncated or partial restore
counts() { psql -d "$1" -Atc "select (select count(*) from \"GetFood_recipe\") || '/' || (select count(*) from \"GetFood_ingredient\") || '/' || (select count(*) from django_migrations)"; }

echo "1/4 bootstrap the source database"
python manage.py bootstrap_db >/dev/null
before=$(counts "$POSTGRES_DB"); echo "    recipes/ingredients/migrations = $before"
case "$before" in 0/*|*/0/*) fail "source database is empty - nothing to prove";; esac

echo "2/4 dump (same pipeline as the CronJob)"
out="$tmp/whattocook-drill.sql.gz"
set -o pipefail
pg_dump -h "$PGHOST" -U "$PGUSER" "$POSTGRES_DB" | gzip > "$out.tmp"
mv "$out.tmp" "$out"
ok "dump written ($(du -h "$out" | cut -f1))"

echo "3/4 restore into a brand-new database"
psql -d postgres -qAt -c "DROP DATABASE IF EXISTS \"$RESTORE_DB\"" -c "CREATE DATABASE \"$RESTORE_DB\" OWNER \"$PGUSER\"" >/dev/null
gunzip -c "$out" | psql -d "$RESTORE_DB" -q -v ON_ERROR_STOP=1 >/dev/null
after=$(counts "$RESTORE_DB"); echo "    recipes/ingredients/migrations = $after"
[ "$before" = "$after" ] && ok "row counts match" || fail "restored data differs ($before vs $after)"

echo "4/4 Django accepts the restored schema"
POSTGRES_DB="$RESTORE_DB" python manage.py migrate --check >/dev/null && ok "no unapplied migrations on the restored database" || fail "restored schema is behind"
echo; echo "Backup/restore drill passed."
