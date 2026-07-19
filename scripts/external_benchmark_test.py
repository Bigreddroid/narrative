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

print(f"\nexternal_benchmark: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
