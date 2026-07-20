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
  backend.api.rate_limit_test
  backend.api.benchmark_route_test
  backend.api.imint_route_test
  backend.services.analyst_test
  backend.services.llm_test
  backend.services.imint_test
  backend.services.imint_event_test
  backend.services.geolocate_test
  backend.services.source_reliability_test
  backend.services.operator_test
  backend.services.reasoner_test
  backend.consequence_engine.propagation_test
  backend.consequence_engine.calibration_test
  backend.consequence_engine.cluster_logic_test
  backend.consequence_engine.corroboration_test
  backend.consequence_engine.title_dedup_test
  backend.consequence_engine.evolution_logic_test
  backend.consequence_engine.graph_scoring_test
  backend.consequence_engine.importance_scorer_test
  backend.models.benchmark_ledger_test
  backend.workers.benchmark_worker_test
  backend.feeds.feeds_test
  backend.feeds.mastodon_osint_test
  backend.feeds.weather_global_test
  backend.feeds.holidays_test
  scripts.backfill_prediction_outcomes_test
  scripts.validate_calibration_test
  scripts.benchmark_score_test
  scripts.external_benchmark_test
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
