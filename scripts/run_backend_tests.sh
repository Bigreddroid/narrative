#!/usr/bin/env bash
# Run every backend test module (they are standalone scripts that exit non-zero
# on failure, not pytest-collectable). Used by CI and for local verification.
# Run from the repo root: bash scripts/run_backend_tests.sh
set -u
cd "$(dirname "$0")/.."

MODULES=(
  backend.config_test
  backend.api.auth_test
  backend.api.security_headers_test
  backend.services.analyst_test
  backend.consequence_engine.propagation_test
  backend.consequence_engine.calibration_test
  backend.consequence_engine.cluster_logic_test
  backend.consequence_engine.corroboration_test
  backend.consequence_engine.evolution_logic_test
  backend.consequence_engine.graph_scoring_test
  backend.consequence_engine.importance_scorer_test
  backend.consequence_engine.temporal_test
  backend.feeds.feeds_test
)

fail=0
for t in "${MODULES[@]}"; do
  if python -m "$t" >/dev/null 2>&1; then
    echo "ok   $t"
  else
    echo "FAIL $t"
    # Re-run on failure so CI logs show which assertion broke.
    python -m "$t" || true
    fail=1
  fi
done

exit $fail
