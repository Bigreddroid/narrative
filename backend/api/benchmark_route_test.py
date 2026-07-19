"""Asserts the public benchmark scoreboard endpoint and its honesty guardrails.
Run from repo root:  python -m backend.api.benchmark_route_test

Uses TestClient (like security_headers_test). The endpoint's DB read is
best-effort, so this passes with OR without Postgres — the accrual meter just
reports 'unknown' (n=None) when the DB is unreachable, never a fabricated count
and never a 500.
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from backend.consequence_engine import calibration
from backend.main import app

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


def _is_ascii(obj) -> bool:
    """No non-ASCII anywhere in the payload (locks the cp1252 mojibake fix)."""
    if isinstance(obj, str):
        return obj.isascii()
    if isinstance(obj, dict):
        return all(_is_ascii(k) and _is_ascii(v) for k, v in obj.items())
    if isinstance(obj, list):
        return all(_is_ascii(x) for x in obj)
    return True


with TestClient(app) as client:
    r = client.get("/api/v1/benchmark/score")
    ok("endpoint 200 (no 500 without DB)", r.status_code == 200)
    d = r.json()

    # Proven layer — synthetic controls all pass and match the CLI.
    syn = d["synthetic"]
    ok("synthetic controls 5/5", syn["passed"] == syn["total"] == 5)

    # The n>=20 gate is surfaced and correct.
    gated = d["engine_gated"]
    ok("engine metric gated on n>=20", gated["requires_n"] == calibration.MIN_CALIBRATION_POINTS == 20)
    ok("engine status accruing", gated["status"] == "accruing")

    acc = d["engine_accrual"]
    ok("accrual meter required=20", acc["required"] == 20)
    # Below the gate: never 'ready', never a leaked engine skill number.
    below_gate = not acc["gate_met"]
    ok("gate withheld while accruing", (acc["status"] == "accruing") == below_gate)
    ok("no top-level engine brier/bss leaked", not any(
        k in d for k in ("engine_brier", "engine_bss", "brier", "bss")))

    # Crowd bar is explicitly labeled as NOT the engine.
    crowd = next(b for b in d["reference_bars"] if b["kind"] == "crowd")
    ok("crowd bar labeled not-our-engine", "not our engine" in crowd["note"].lower())

    # Self-documenting: citations + honesty layers present.
    ok("citations present", len(d["citations"]) >= 5)
    ok("three honesty layers", len(d["layers"]) == 3)

    # Encoding guardrail.
    ok("payload is pure ASCII", _is_ascii(d))

print(f"\nbenchmark_route: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
