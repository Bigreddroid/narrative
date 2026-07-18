"""Pure tests for the backfill transform (no DB). Run:
    python -m scripts.backfill_prediction_outcomes_test
"""
from scripts.backfill_prediction_outcomes import normalize_row, normalize_all, RowError

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name}")


def raises(name, record):
    try:
        normalize_row(record)
        ok(name, False)
    except RowError:
        ok(name, True)


EID = "11111111-1111-1111-1111-111111111111"

# actual_outcome text -> probability
r = normalize_row({"narrative_event_id": EID, "original_prediction_score": "80", "actual_outcome": "Materialized"})
ok("materialized -> 1.0", r["observed_probability"] == 1.0)
ok("score coerced to int", r["original_prediction_score"] == 80)
ok("outcome lowercased", r["actual_outcome"] == "materialized")

ok("partial -> 0.5", normalize_row({"narrative_event_id": EID, "original_prediction_score": 50, "actual_outcome": "partial"})["observed_probability"] == 0.5)
ok("failed -> 0.0", normalize_row({"narrative_event_id": EID, "original_prediction_score": 50, "actual_outcome": "failed"})["observed_probability"] == 0.0)

# observed_probability wins over actual_outcome
r2 = normalize_row({"narrative_event_id": EID, "original_prediction_score": 70, "observed_probability": "0.9", "actual_outcome": "failed"})
ok("observed_probability preferred", r2["observed_probability"] == 0.9)

# validation failures
raises("missing event id", {"original_prediction_score": 50, "actual_outcome": "failed"})
raises("missing score", {"narrative_event_id": EID, "actual_outcome": "failed"})
raises("score out of range", {"narrative_event_id": EID, "original_prediction_score": 150, "actual_outcome": "failed"})
raises("no outcome at all", {"narrative_event_id": EID, "original_prediction_score": 50})
raises("bad outcome label", {"narrative_event_id": EID, "original_prediction_score": 50, "actual_outcome": "kinda"})
raises("obs prob out of range", {"narrative_event_id": EID, "original_prediction_score": 50, "observed_probability": "1.5"})

# batch: mixed good/bad
rows, errors = normalize_all([
    {"narrative_event_id": EID, "original_prediction_score": 60, "actual_outcome": "partial"},
    {"original_prediction_score": 60, "actual_outcome": "partial"},  # bad: no eid
])
ok("batch keeps the good row", len(rows) == 1)
ok("batch reports the bad row", len(errors) == 1)

print(f"\nbackfill_prediction_outcomes: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
