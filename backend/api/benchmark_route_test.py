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

    # Phase 3: the endpoint serves a cached benchmark_runs row when present and
    # falls back to request-time proofs otherwise. Either way `cached_at` is a
    # declared key (None on the fallback path this test exercises without a DB).
    ok("cached_at key present", "cached_at" in d)

    # Encoding guardrail.
    ok("payload is pure ASCII", _is_ascii(d))

    # --- Phase 2: forward prediction ledger endpoints (no 500 without DB) ---
    r = client.get("/api/v1/benchmark/ledger")
    ok("ledger 200 (no 500 without DB)", r.status_code == 200)
    led = r.json()
    ok("ledger returns an entries list", isinstance(led.get("entries"), list))
    ok("ledger count matches entries", led["count"] == len(led["entries"]))

    r = client.get("/api/v1/benchmark/ledger/manifest/2026-07-19")
    ok("manifest 200 (no 500 without DB)", r.status_code == 200)
    man = r.json()
    ok("manifest reports found bool", isinstance(man.get("found"), bool))

    r = client.get("/api/v1/benchmark/ledger/manifest/not-a-date")
    ok("manifest rejects junk date without 500", r.status_code == 200 and r.json()["found"] is False)

    # Engine skill is GATED: below n>=20 it must withhold the number entirely.
    r = client.get("/api/v1/benchmark/engine-skill")
    ok("engine-skill 200 (no 500 without DB)", r.status_code == 200)
    skill = r.json()
    ok("engine-skill required=20", skill["required"] == calibration.MIN_CALIBRATION_POINTS == 20)
    if skill["resolved_n"] < skill["required"]:
        ok("engine-skill withheld below gate", skill["status"] == "withheld")
        ok("no skill number leaked below gate",
           "brier_skill_score" not in skill and "brier" not in skill)
    else:
        ok("engine-skill ready at/above gate", skill["status"] == "ready")

    ok("ledger payloads pure ASCII", _is_ascii(led) and _is_ascii(man) and _is_ascii(skill))

# summarize_engine_skill (pure): source separation + per-bucket gating + crowd delta.
from backend.api.routes.benchmark import summarize_engine_skill

req = calibration.MIN_CALIBRATION_POINTS  # 20

# Below the gate in every bucket -> nothing leaks.
small = summarize_engine_skill([(70, 1.0, "engine", None), (30, 0.0, "manifold", 0.4)], req)
ok("headline withheld below gate", small["status"] == "withheld" and "brier" not in small)
ok("by_source manifold withheld", small["by_source"]["manifold"]["status"] == "withheld"
   and "brier" not in small["by_source"]["manifold"])

# Enough external rows to clear the gate; internal stays below -> headline still withheld
# (external NEVER blends into the headline) but by_source.manifold is ready.
rows = [(80, 1.0, "manifold", 0.55) for _ in range(req)]
rows += [(20, 0.0, "manifold", 0.45) for _ in range(req)]
big = summarize_engine_skill(rows, req)
ok("headline still withheld (internal n=0)", big["status"] == "withheld")
ok("by_source manifold ready above gate", big["by_source"]["manifold"]["status"] == "ready")
ok("manifold bucket has a brier", "brier" in big["by_source"]["manifold"])
ok("engine_vs_crowd present + gated ready", big["engine_vs_crowd"]["manifold"]["status"] == "ready")
ok("engine beat crowd here (positive delta)", big["engine_vs_crowd"]["manifold"]["delta"] > 0)
ok("summarize payload ASCII", _is_ascii(big))

print(f"\nbenchmark_route: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
