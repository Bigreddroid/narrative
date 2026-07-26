"""Tests for the external resolution worker's PURE helpers.
Run from repo root:  python -m backend.workers.external_resolution_worker_test

Pure: exercises external_ref parsing + outcome labelling + the source resolution
mapping. NO DB, NO network (the async run loop is exercised on the live stack).
"""
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.workers import external_resolution_worker as w
from backend.consequence_engine import calibration

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# external_ref -> contract id (only the manifold scheme we actually poll).
ok("contract id parsed", w._manifold_contract_id("manifold:abc123") == "abc123")
ok("non-manifold scheme -> None", w._manifold_contract_id("metaculus:99") is None)
ok("empty ref -> None", w._manifold_contract_id("") is None)
ok("bare scheme -> None", w._manifold_contract_id("manifold:") is None)

# outcome label mirrors outcome_worker's vocabulary.
ok("label materialized", w._outcome_label(1.0) == "materialized")
ok("label failed", w._outcome_label(0.0) == "failed")

# The resolution mapping the worker relies on (delegated to external_benchmark):
# only a clean YES/NO grades; everything else leaves the entry open.
ok("YES grades to 1", w.eb.resolution_from_manifold_market(
    {"isResolved": True, "resolution": "YES"}) == 1.0)
ok("MKT leaves open", w.eb.resolution_from_manifold_market(
    {"isResolved": True, "resolution": "MKT"}) is None)

# Brier composes as the worker would compute it (score/100 vs realised outcome).
brier = calibration.brier_score(0.70, 1.0)
ok("brier is a real number in [0,1]", 0.0 <= brier <= 1.0 and abs(brier - 0.09) < 1e-9)

print(f"\nexternal_resolution_worker: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
