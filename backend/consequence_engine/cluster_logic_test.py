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

# time decay can demote an otherwise-strong match
ok("huge time gap demotes to new", C.decide_cluster([cand(0.9, 9, 1000)], 0.8, 0.84, 2, 24)[0] is None)

# picks the best candidate among several
multi = [cand(0.81, 5), {"id": "y", "sim": 0.95, "member_count": 5, "age_gap_hours": 0}]
ok("picks highest effective sim", C.decide_cluster(multi, 0.8, 0.84, 2, 168)[0] == "y")
ok("empty candidates => new", C.decide_cluster([], 0.8, 0.84, 2, 168)[0] is None)

# centroid running mean
ok("centroid running mean", C.update_centroid([0.0, 0.0], [2.0, 4.0], 1) == [1.0, 2.0])
ok("centroid: empty old => vec", C.update_centroid([], [1.0, 2.0], 3) == [1.0, 2.0])
ok("centroid: n=0 => vec", C.update_centroid([5.0], [1.0], 0) == [1.0])

print(f"\ncluster_logic: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
