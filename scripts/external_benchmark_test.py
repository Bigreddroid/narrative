"""Tests for the external benchmark harness — leakage partition, scoring, parsing.
Run from repo root:  python -m scripts.external_benchmark_test

Pure: uses the stub forecaster + fixtures, so NO LLM and NO network are touched.
"""
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from scripts import external_benchmark as eb
from scripts import validate_calibration_autocast as ac

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


cutoff = eb._parse_date("2023-11-01")

# _parse_date handles ISO strings and returns tz-aware datetimes.
ok("_parse_date ISO", isinstance(eb._parse_date("2024-06-01"), datetime))
ok("_parse_date epoch", isinstance(eb._parse_date(1_700_000_000), datetime))
ok("_parse_date junk -> None", eb._parse_date("not-a-date") is None)

# Leakage partition: 2 pre-cutoff (2022), 1 post-cutoff (2024).
pre, post = eb.partition_by_leakage(eb._SELFTEST_RECORDS, cutoff)
ok("partition pre=2", len(pre) == 2)
ok("partition post=1", len(post) == 1)

# A record with no resolution date is conservatively pre_cutoff (exposed).
pre2, post2 = eb.partition_by_leakage([{"resolution_date": None, "outcome": 1.0}], cutoff)
ok("missing date -> exposed", len(pre2) == 1 and len(post2) == 0)

# Scoring with the stub forecaster (echoes crowd_prob) produces real metrics.
rep = eb.score_records(pre, eb.stub_forecaster)
ok("score n=2", rep["n"] == 2)
ok("score has bss", "bss" in rep)
ok("score has murphy", "murphy" in rep)

# End-to-end run: labels + caveats + honesty note present, gate value surfaced.
result = eb.run(eb._SELFTEST_RECORDS, eb.stub_forecaster, cutoff, None, "selftest")
ok("pre labeled exposed", result["pre_cutoff"]["leakage"] == "exposed")
ok("post labeled clean", result["post_cutoff"]["leakage"] == "post_cutoff_clean")
ok("pre carries caveat", "hindsight" in result["pre_cutoff"]["caveat"].lower())
ok("engine skill NOT claimed", "not claimed" in result["engine_skill_note"].lower())
ok("gate n>=20 surfaced", "20" in result["engine_skill_note"])

# render() is ASCII-only (Windows console / mojibake guard) and runs clean.
text = eb.render(result)
ok("render ASCII-only", text.isascii())
ok("render mentions DIAGNOSTIC", "DIAGNOSTIC" in text)

# extract_records keeps question text and filters like extract_pairs.
questions = [
    {"qtype": "t/f", "answer": "yes", "question": "Q1?", "crowd": [{"forecast": 0.8}],
     "close_time": "2024-01-01"},
    {"qtype": "t/f", "answer": None, "question": "Q2?", "crowd": [{"forecast": 0.5}]},  # unresolved -> drop
    {"qtype": "num", "answer": "42", "question": "Q3?"},                                 # non-binary -> drop
    {"qtype": "t/f", "answer": "no", "question": "", "crowd": [0.1, 0.3]},               # no text -> drop
]
recs = ac.extract_records(questions)
ok("extract_records keeps 1", len(recs) == 1)
ok("extract_records keeps text", recs[0]["question_text"] == "Q1?")
ok("extract_records outcome", recs[0]["outcome"] == 1.0)

# --- Phase 4: pure dataset adapters (no network — parse fixtures only) --------

# Manifold: keep only RESOLVED YES/NO BINARY; drop partial(MKT)/multi-choice/open.
markets = [
    {"id": "1", "outcomeType": "BINARY", "isResolved": True, "resolution": "YES",
     "question": "q1", "createdTime": 1_700_000_000_000,
     "resolutionTime": 1_710_000_000_000, "probability": 0.7},
    {"id": "2", "outcomeType": "BINARY", "isResolved": True, "resolution": "NO", "question": "q2"},
    {"id": "3", "outcomeType": "BINARY", "isResolved": True, "resolution": "MKT", "question": "partial"},
    {"id": "4", "outcomeType": "MULTIPLE_CHOICE", "isResolved": True, "resolution": "YES", "question": "mc"},
    {"id": "5", "outcomeType": "BINARY", "isResolved": False, "question": "open"},
]
mp = eb.parse_manifold_markets(markets)
ok("manifold keeps 2", len(mp) == 2)
ok("manifold outcomes", [m["outcome"] for m in mp] == [1.0, 0.0])
ok("manifold ms->iso", mp[0]["publish_date"].startswith("2023-11-14"))
ok("manifold source", mp[0]["source"] == "manifold")

# Metaculus: handle both nested (`question`) and flat shapes; drop annulled.
results = [
    {"id": 10, "question": {"title": "mq1", "resolution": "yes",
                            "created_time": "2024-01-01", "actual_resolve_time": "2024-06-01"}},
    {"id": 11, "title": "mq2", "resolution": False},
    {"id": 12, "title": "annulled", "resolution": "annulled"},
]
mq = eb.parse_metaculus_questions(results)
ok("metaculus keeps 2", len(mq) == 2)
ok("metaculus outcomes", [q["outcome"] for q in mq] == [1.0, 0.0])

# Metaculus adapter refuses honestly with no token (no fabricated/empty result).
try:
    eb.metaculus_adapter("")
    ok("metaculus no-token refuses", False)
except SystemExit:
    ok("metaculus no-token refuses", True)

# file adapter: CSV/JSON gold set; drop rows missing text or a clean 0/1 outcome.
import json as _json
import tempfile
import os as _os

_fd, _p = tempfile.mkstemp(suffix=".json")
try:
    with _os.fdopen(_fd, "w", encoding="utf-8") as _fh:
        _json.dump([
            {"question_text": "Did A resolve yes?", "outcome": "yes"},
            {"question_text": "Did B resolve no?", "outcome": 0},
            {"question_text": "", "outcome": 1},          # no text -> drop
            {"question_text": "ambiguous", "outcome": "maybe"},  # bad outcome -> drop
        ], _fh)
    fr = eb.file_adapter(_p)
    ok("file keeps 2", len(fr) == 2)
    ok("file outcomes", [r["outcome"] for r in fr] == [1.0, 0.0])
    ok("file source", fr[0]["source"] == "file")
finally:
    _os.unlink(_p)

# --- Phase 4 (supplement): helper units + adapter field/flow-through ----------

# _ms_to_iso: Manifold epoch-ms -> ISO; None -> None.
ok("_ms_to_iso ms->str", isinstance(eb._ms_to_iso(1_700_000_000_000), str))
ok("_ms_to_iso None", eb._ms_to_iso(None) is None)

# _metaculus_outcome / _coerce_outcome: binary mapping; ambiguous -> None.
ok("metaculus_outcome 1", eb._metaculus_outcome(1) == 1.0)
ok("metaculus_outcome no", eb._metaculus_outcome("no") == 0.0)
ok("metaculus_outcome ambiguous None", eb._metaculus_outcome(0.5) is None)
ok("coerce_outcome yes", eb._coerce_outcome("yes") == 1.0)
ok("coerce_outcome junk None", eb._coerce_outcome("maybe") is None)

# Adapter records carry the namespaced id + source the ledger/labels rely on.
ok("manifold id namespaced", mp[0]["id"].startswith("manifold:"))
ok("metaculus id namespaced", mq[0]["id"].startswith("metaculus:"))
ok("file id defaulted", fr[0]["id"].startswith("file:"))

# Adapter output flows through the existing scorer/partition unchanged.
fresult = eb.run(mp + fr, eb.stub_forecaster, cutoff, None, "manifold")
ok("adapter records score end-to-end", fresult["total_records"] == len(mp) + len(fr))

print(f"\nexternal_benchmark: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
