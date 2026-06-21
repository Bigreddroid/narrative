#!/usr/bin/env bash
# Post-deploy smoke test for the Narrative stack.
#
#   API_BASE=https://<railway-api-host>            \
#   WEB_BASE=https://<your-app>.vercel.app         \
#   bash scripts/smoke_test.sh
#
# Or positionally:  bash scripts/smoke_test.sh <API_BASE> [WEB_BASE]
#
# MODE defaults to "prod" (asserts APP_ENV=production behaviour: /docs is 404).
# For a LOCAL dry-run against the dev API, pass MODE=dev so the /docs check
# expects 200 instead:  MODE=dev API_BASE=http://127.0.0.1:8000 bash scripts/smoke_test.sh
#
# Exits non-zero if any check fails. Reachable-but-unauthorised (401) and
# rate-limited (429) count as PASS for the data endpoints: they still prove the
# API is routing and the DB is up — only 5xx / connection failure (000) fail.
set -u

API_BASE="${API_BASE:-${1:-}}"
WEB_BASE="${WEB_BASE:-${2:-}}"
MODE="${MODE:-prod}"

if [ -z "$API_BASE" ]; then
  echo "usage: API_BASE=<url> [WEB_BASE=<url>] [MODE=prod|dev] bash scripts/smoke_test.sh"
  exit 2
fi
API_BASE="${API_BASE%/}"
WEB_BASE="${WEB_BASE%/}"

fail=0
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$1" 2>/dev/null; }
body() { curl -s --max-time 15 "$1" 2>/dev/null; }

pass_line() { printf '  PASS  %s (%s)\n' "$1" "$2"; }
fail_line() { printf '  FAIL  %s (%s)\n' "$1" "$2"; fail=1; }

echo "== API: $API_BASE  (mode=$MODE) =="

# 1) Health — 200 and reports the running env.
h="$(body "$API_BASE/health")"
hc="$(code "$API_BASE/health")"
if [ "$hc" = "200" ] && printf '%s' "$h" | grep -q '"status"[[:space:]]*:[[:space:]]*"ok"'; then
  pass_line "/health 200 + status ok" "$h"
else
  fail_line "/health" "code=$hc body=$h"
fi
if [ "$MODE" = "prod" ] && ! printf '%s' "$h" | grep -q '"env"[[:space:]]*:[[:space:]]*"production"'; then
  fail_line "/health reports production env" "$h"
fi

# 2) /docs — disabled in production (404); enabled in dev (200).
dc="$(code "$API_BASE/docs")"
if [ "$MODE" = "prod" ]; then
  [ "$dc" = "404" ] && pass_line "/docs disabled in prod" "404" || fail_line "/docs should be 404 in prod" "$dc"
else
  [ "$dc" = "200" ] && pass_line "/docs enabled in dev" "200" || fail_line "/docs should be 200 in dev" "$dc"
fi

# 3) Data endpoint — routing + DB up (not 5xx, not connection failure).
ec="$(code "$API_BASE/api/v1/events/")"
if [ -n "$ec" ] && [ "$ec" != "000" ] && [ "$ec" -lt 500 ]; then
  pass_line "/api/v1/events/ reachable" "$ec"
else
  fail_line "/api/v1/events/ unreachable or 5xx" "${ec:-no-response}"
fi

# 4) Frontend + Vercel rewrite (optional).
if [ -n "$WEB_BASE" ]; then
  echo "== WEB: $WEB_BASE =="
  wc="$(code "$WEB_BASE/")"
  [ "$wc" = "200" ] && pass_line "frontend serves" "200" || fail_line "frontend root" "$wc"
  rc="$(code "$WEB_BASE/api/v1/events/")"
  if [ -n "$rc" ] && [ "$rc" != "000" ] && [ "$rc" -lt 500 ]; then
    pass_line "Vercel /api rewrite reaches Railway" "$rc"
  else
    fail_line "Vercel /api rewrite" "${rc:-no-response}"
  fi
fi

echo
[ "$fail" = "0" ] && echo "SMOKE TEST PASSED" || echo "SMOKE TEST FAILED"
exit $fail
