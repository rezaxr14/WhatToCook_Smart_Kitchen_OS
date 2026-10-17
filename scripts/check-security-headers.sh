#!/usr/bin/env bash
# Asserts the security headers nginx (frontend/nginx.conf + frontend/nginx/*.conf) puts on every kind of
# response. Needs only curl, so it runs against the compose stack (compose-smoke.sh does) or any URL:
#   ./scripts/check-security-headers.sh                      # http://localhost:4173 (compose frontend)
#   ./scripts/check-security-headers.sh https://example.org
set -euo pipefail

BASE="${1:-${FRONT_URL:-http://localhost:4173}}"
BASE="${BASE%/}"
ok()   { printf '  \033[32m✔\033[0m %s\n' "$*"; }
fail() { printf '  \033[31m✘\033[0m %s\n' "$*"; exit 1; }

# NB: capture first, grep after - `curl | grep -q` can die of SIGPIPE under `set -o pipefail`.
hdrs() { curl -sS -D - -o /dev/null "$BASE$1" | tr -d '\r'; }
count() { local n; n=$(grep -ci "^$1:" <<<"$2" || true); echo "${n:-0}"; }
has() { grep -qiE "^$1" <<<"$2"; }

echo "▶ security headers on $BASE"

for path in / /recipes /api/health/ /api/nonexistent/ /media/missing.png /legacy/ /static/admin/css/base.css; do
  h=$(hdrs "$path")
  has "HTTP/[0-9.]* [0-9]" "$h" || fail "$path: no response"
  has "x-content-type-options: nosniff" "$h"                            || fail "$path: X-Content-Type-Options missing"
  has "referrer-policy: strict-origin-when-cross-origin" "$h"           || fail "$path: Referrer-Policy missing"
  has "x-frame-options: DENY" "$h"                                      || fail "$path: X-Frame-Options missing"
  has "permissions-policy: .*microphone=\(\)" "$h"                        || fail "$path: Permissions-Policy missing"
  has "content-security-policy: " "$h"                                  || fail "$path: Content-Security-Policy missing"
  # Django sets some of these itself; nginx must hide its copies, not send everything twice.
  for name in x-content-type-options referrer-policy x-frame-options permissions-policy content-security-policy; do
    [ "$(count "$name" "$h")" = "1" ] || fail "$path: $name sent $(count "$name" "$h") times (want exactly 1)"
  done
  ok "$path: all five headers, once each"
done

spa=$(hdrs /)
has "content-security-policy: .*script-src 'self'(;|$)" "$spa"  || fail "SPA CSP does not restrict script-src to 'self'"
grep -qiE "^content-security-policy: .*script-src [^;]*'unsafe-(inline|eval)'" <<<"$spa" \
  && fail "SPA CSP allows unsafe script execution"
has "content-security-policy: .*frame-ancestors 'none'" "$spa"  || fail "SPA CSP lacks frame-ancestors 'none'"
ok "SPA CSP: script-src 'self' only, frame-ancestors 'none'"

# Django-rendered pages (admin, legacy, Swagger UI) need inline scripts: only the baseline CSP applies.
docs=$(hdrs /api/docs/)
has "HTTP/[0-9.]* 200" "$docs"                                   || fail "/api/docs/ is not served (HTTP 200 expected)"
grep -qiE "^content-security-policy: .*script-src" <<<"$docs"    && fail "/api/docs/ must not get the strict script-src (Swagger UI uses inline scripts)"
has "content-security-policy: .*frame-ancestors 'none'" "$docs"  || fail "/api/docs/ lacks the baseline CSP"
ok "/api/docs/ served with the baseline CSP (no script-src restriction)"

media=$(hdrs /media/missing.png)
has "content-security-policy: default-src 'none'; sandbox" "$media" || fail "/media/ is not locked down (default-src 'none'; sandbox)"
ok "/media/ locked down (default-src 'none'; sandbox)"

echo "All security header checks passed."
