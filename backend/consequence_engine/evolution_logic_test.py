"""
Property test for evolution_logic (pure, stdlib only). Run from repo root:
    python -m backend.consequence_engine.evolution_logic_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import evolution_logic as E

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


VW, VT, ST, BASE = 0.5, 2.0, 168.0, 0.15

# pressure
ok("no signal => 0 pressure", E.evolution_pressure(0, 0, VW, VT) == 0.0)
ok("drift contributes directly", E.evolution_pressure(0.2, 0, VW, VT) == 0.2)
ok("new high-importance adds pressure", E.evolution_pressure(0, 1, VW, VT) > 0)
ok("more articles => more pressure (diminishing)",
   E.evolution_pressure(0, 3, VW, VT) > E.evolution_pressure(0, 1, VW, VT))

# threshold sensitivity by category
ok("conflict more sensitive than policy",
   E.effective_threshold(BASE, None, "conflict", ST) < E.effective_threshold(BASE, None, "policy", ST))
ok("unknown category = default", E.effective_threshold(BASE, None, "weird", ST) == BASE * E.DEFAULT_SENSITIVITY)

# staleness lowers the bar
ok("stale event has lower threshold",
   E.effective_threshold(BASE, 24 * 14, "health", ST) < E.effective_threshold(BASE, 0, "health", ST))
ok("no timestamp => no staleness discount", E.effective_threshold(BASE, None, "health", ST) == BASE)

# end-to-end decisions
fresh_conflict = E.effective_threshold(BASE, 0, "conflict", ST)
ok("fresh conflict + 1 high article => re-map",
   E.should_remap(E.evolution_pressure(0, 1, VW, VT), fresh_conflict))
fresh_policy = E.effective_threshold(BASE, 0, "policy", ST)
ok("fresh policy + tiny drift => no re-map",
   not E.should_remap(E.evolution_pressure(0.05, 0, VW, VT), fresh_policy))
ok("same event re-maps once stale",
   E.should_remap(E.evolution_pressure(0.05, 0, VW, VT), E.effective_threshold(BASE, 24 * 30, "policy", ST)))

print(f"\nevolution_logic: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
