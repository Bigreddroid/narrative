"""Tests for the forward-mode external forecast publisher — the PURE entry builder.
Run from repo root:  python -m scripts.publish_external_forecasts_test

Pure: injects a stub forecaster, so NO LLM and NO network are touched. The DB
insert / manifest recompute path is exercised live on the local stack, not here.
"""
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts import publish_external_forecasts as pef
from backend.models.benchmark_ledger import compute_content_hash

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


created = datetime(2026, 7, 21, 12, 0, tzinfo=timezone.utc)

records = [
    {"question_text": "Will X happen?", "background": "ctx",
     "external_ref": "manifold:a1", "external_url": "https://manifold.markets/a1",
     "resolution_criteria": "resolves YES if X", "crowd_prob": 0.6, "source": "manifold"},
    {"question_text": "Will Y happen?", "background": "",
     "external_ref": "manifold:a2", "crowd_prob": None, "source": "manifold"},
    {"question_text": "", "external_ref": "manifold:a3", "source": "manifold"},  # no text -> drop
]

# Stub forecaster: a fixed integer probability; None for a specific question to
# prove unscoreable records are skipped (never fabricated).
def stub(qtext, background):
    if qtext == "Will Y happen?":
        return None
    return 73

entries = pef.build_external_entries(records, stub, created.date(), created_at=created)

ok("skips empty-text and unscoreable", len(entries) == 1)
e = entries[0]
ok("carries source", e["source"] == "manifold")
ok("carries external_ref", e["external_ref"] == "manifold:a1")
ok("carries external_url", e["external_url"] == "https://manifold.markets/a1")
ok("carries crowd_prob", e["crowd_prob"] == 0.6)
ok("prediction_score is the stub int", e["prediction_score"] == 73)
ok("manifest_date set", e["manifest_date"] == created.date())

# content_hash commits to (question, score, created_at) EXACTLY like the internal
# ledger, so a third party verifies external + internal entries identically.
ok("content_hash matches canonical helper",
   e["content_hash"] == compute_content_hash("Will X happen?", 73, created))

# Scores are clamped into [0,100] (a bad forecaster can't poison the ledger).
hi = pef.build_external_entries(
    [{"question_text": "q", "external_ref": "manifold:hi", "source": "manifold"}],
    lambda q, b: 250, created.date(), created_at=created)
ok("score clamped to 100", hi[0]["prediction_score"] == 100)

# crowd_prob absent -> None (not fabricated to 0.5 or anything else).
noc = [x for x in entries if x["external_ref"] == "manifold:a1"][0]
ok("crowd_prob preserved exactly", noc["crowd_prob"] == 0.6)

print(f"\npublish_external_forecasts: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
