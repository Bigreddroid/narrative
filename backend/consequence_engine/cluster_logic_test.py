"""
Property test for cluster_logic (pure, stdlib only). Run from repo root:
    python -m backend.consequence_engine.cluster_logic_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import cluster_logic as C

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# effective_similarity
ok("no age gap => unchanged", C.effective_similarity(0.9, None, 168) == 0.9)
ok("time gap discounts similarity", C.effective_similarity(0.9, 168, 168) < 0.9)
ok("bigger gap => lower", C.effective_similarity(0.9, 300, 168) < C.effective_similarity(0.9, 24, 168))

cand = lambda sim, members, gap=0: {"id": "x", "sim": sim, "member_count": members, "age_gap_hours": gap}

# strong match always attaches
ok("strong match attaches (any member count)", C.decide_cluster([cand(0.9, 0)], 0.8, 0.84, 2, 168)[0] == "x")

# mid match: established cluster attaches, fresh cluster spawns
ok("mid match + established => attach", C.decide_cluster([cand(0.82, 3)], 0.8, 0.84, 2, 168)[0] == "x")
ok("mid match + not established => new", C.decide_cluster([cand(0.82, 1)], 0.8, 0.84, 2, 168)[0] is None)

# below attach threshold => new
ok("weak match => new", C.decide_cluster([cand(0.7, 9)], 0.8, 0.84, 2, 168)[0] is None)

# time penalty orders candidates but is BOUNDED — it can never veto a strong match.
# This replaces an older assertion ("huge time gap demotes to new") that encoded the
# multiplicative-decay behaviour. That behaviour was the defect, not the contract.
ok("time penalty is bounded by max_time_penalty",
   C.effective_similarity(0.9, 10_000, 24, 0.05) >= 0.9 - 0.05 - 1e-12)
ok("time penalty never flips a strong match to new",
   C.decide_cluster([cand(0.95, 9, 10_000)], 0.8, 0.84, 2, 24)[0] == "x")
ok("time still discourages: older candidate loses to an equal, fresher one",
   C.decide_cluster([{"id": "old", "sim": 0.9, "member_count": 5, "age_gap_hours": 400},
                     {"id": "new", "sim": 0.9, "member_count": 5, "age_gap_hours": 0}],
                    0.8, 0.84, 2, 168)[0] == "new")

# REGRESSION — the self-locking fragmentation ceiling.
# Old logic was sim * exp(-gap/decay) against a fixed bar, so with cosine capped at 1.0
# nothing could attach past t = -decay*ln(bar): 29.3h for the 0.84 strong bar and 37.5h
# for the 0.80 attach bar at decay=168h. A fresh event has 1 member and min_established
# is 2, so an event that missed its ~29h window could never become established and thus
# never attach anything again. Live result: mean 1.10 articles/event, 94% single-article.
# An IDENTICAL article (sim 1.0) three days later must still attach.
ok("identical article 72h later still attaches (was impossible)",
   C.decide_cluster([cand(1.0, 1, 72)], 0.8, 0.84, 2, 168)[0] == "x")
ok("identical article 10 days later still attaches",
   C.decide_cluster([cand(1.0, 1, 240)], 0.8, 0.84, 2, 168)[0] == "x")
ok("old logic would have vetoed it (documents the bug)",
   0.99 * __import__("math").exp(-72 / 168) < 0.84)

# picks the best candidate among several
multi = [cand(0.81, 5), {"id": "y", "sim": 0.95, "member_count": 5, "age_gap_hours": 0}]
ok("picks highest effective sim", C.decide_cluster(multi, 0.8, 0.84, 2, 168)[0] == "y")
ok("empty candidates => new", C.decide_cluster([], 0.8, 0.84, 2, 168)[0] is None)

# centroid running mean
ok("centroid running mean", C.update_centroid([0.0, 0.0], [2.0, 4.0], 1) == [1.0, 2.0])
ok("centroid: empty old => vec", C.update_centroid([], [1.0, 2.0], 3) == [1.0, 2.0])
ok("centroid: n=0 => vec", C.update_centroid([5.0], [1.0], 0) == [1.0])
ok("centroid: None old => vec", C.update_centroid(None, [1.0, 2.0], 3) == [1.0, 2.0])

# REGRESSION — pgvector hands back a numpy ndarray, never a list. The old guard was
# `if not old:`, which raises ValueError on any multi-element array. That crashed
# cluster_worker on every run from 2026-07-13 and left all 28k articles unattached to
# their events, so no event had a source and corroboration was always empty. Every case
# above passed throughout, because every case above passes a plain list. Exercise the
# type production actually supplies.
try:
    import numpy as _np
except ImportError:  # numpy absent in a bare env — skip rather than fail the suite
    ok("centroid: ndarray old (numpy unavailable, skipped)", True)
else:
    ok("centroid: ndarray old does not raise",
       C.update_centroid(_np.array([0.0, 0.0]), [2.0, 4.0], 1) == [1.0, 2.0])
    ok("centroid: ndarray vec too",
       C.update_centroid(_np.array([0.0, 0.0]), _np.array([2.0, 4.0]), 1) == [1.0, 2.0])
    ok("centroid: empty ndarray => vec",
       C.update_centroid(_np.array([]), [1.0, 2.0], 3) == [1.0, 2.0])
    # A realistic 1024-dim embedding — the exact shape that was blowing up in production.
    _big = _np.zeros(1024)
    ok("centroid: 1024-dim ndarray (production shape)",
       len(C.update_centroid(_big, [1.0] * 1024, 1)) == 1024)

print(f"\ncluster_logic: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
