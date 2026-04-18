#!/usr/bin/env bash
# Post-deploy smoke test for TrueFans DISPATCH.
#
# Usage:
#   bash scripts/smoke.sh [URL]
#
# URL defaults to $SMOKE_URL or the live Railway URL. Reads the admin
# password from $SMOKE_ADMIN_PASSWORD so it stays out of the shell
# history. Exits non-zero the moment any check fails — safe to wire
# into a CI gate or a pre-launch checklist.

set -euo pipefail

URL="${1:-${SMOKE_URL:-https://web-production-2684b.up.railway.app}}"
URL="${URL%/}"

PW="${SMOKE_ADMIN_PASSWORD:-}"

green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }

fail=0
ok()   { green "  [PASS] $*"; }
bad()  { red   "  [FAIL] $*"; fail=1; }

echo
echo "Smoke against: ${URL}"
echo

# 1. Health
echo "[1/5] /health"
if curl -sf -o /dev/null -m 10 "${URL}/health"; then
    ok "200 OK"
else
    bad "not responding"
fi

# 2. Login page renders
echo "[2/5] GET /login"
code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 "${URL}/login")
if [[ "$code" == "200" ]]; then
    ok "200 OK"
else
    bad "unexpected ${code}"
fi

# 3. Wrong password rejected
echo "[3/5] POST /login with bad password"
code=$(curl -s -o /dev/null -w "%{http_code}" -m 10 \
    -X POST "${URL}/login" -d "password=definitely-not-the-password")
if [[ "$code" == "401" || "$code" == "429" ]]; then
    ok "rejected (${code})"
else
    bad "unexpected ${code} — auth may be disabled"
fi

# 4. Correct password — redirect to /dashboard + session cookie
echo "[4/5] POST /login with correct password"
if [[ -z "${PW}" ]]; then
    yellow "  [SKIP] set SMOKE_ADMIN_PASSWORD to enable this check"
else
    headers=$(curl -s -i -m 10 -X POST "${URL}/login" -d "password=${PW}")
    if grep -qiE "^HTTP/.+ 302" <<< "$headers" && \
       grep -qiE "^location: /dashboard" <<< "$headers" && \
       grep -qiE "^set-cookie: _session=" <<< "$headers"; then
        ok "302 → /dashboard + session cookie set"
    else
        bad "login failed"
        echo "$headers" | head -20 | sed 's/^/    /'
    fi
fi

# 5. Feature flags admin page loads (authenticated)
echo "[5/5] GET /admin/feature-flags (authenticated)"
if [[ -z "${PW}" ]]; then
    yellow "  [SKIP] needs SMOKE_ADMIN_PASSWORD"
else
    cookies=$(mktemp)
    trap 'rm -f "$cookies"' EXIT
    curl -s -o /dev/null -c "$cookies" -m 10 -X POST "${URL}/login" -d "password=${PW}"
    body=$(curl -s -b "$cookies" -m 10 "${URL}/admin/feature-flags")
    if grep -q "Feature Flags" <<< "$body"; then
        ok "feature flags UI reachable"
    else
        bad "feature flags UI did not render"
    fi
fi

echo
if [[ $fail -eq 0 ]]; then
    green "Smoke PASSED"
    exit 0
else
    red "Smoke FAILED"
    exit 1
fi
