"""
Property test for graph_scoring (pure, stdlib only). Run from repo root:
    python -m backend.consequence_engine.graph_scoring_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to cp1252

from backend.consequence_engine import graph_scoring as G

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


# build_idf — rarer tokens get higher IDF than ubiquitous ones.
corpus = [["united states"]] * 5 + [["lithium"]]  # 'united states' in 5/6 docs, 'lithium' in 1/6
idf = G.build_idf(corpus)
ok("rare token has higher IDF than common", idf["lithium"] > idf["united states"])

# weighted_overlap — identical lists score 1.0.
score, shared = G.weighted_overlap(["a", "b"], ["a", "b"], G.build_idf([["a", "b"]]))
ok("identical lists ⇒ overlap 1.0", abs(score - 1.0) < 1e-9 and shared == ["a", "b"])

# weighted_overlap — no overlap ⇒ 0.
ok("disjoint lists ⇒ overlap 0", G.weighted_overlap(["a"], ["b"], {"a": 1, "b": 1})[0] == 0.0)

# THE KEY PROPERTY: sharing a rare token beats sharing a ubiquitous one.
hand_idf = {"common": 0.1, "rare": 3.0, "x": 1.0, "y": 1.0}
common_pair = G.weighted_overlap(["common", "x"], ["common", "y"], hand_idf)[0]
rare_pair = G.weighted_overlap(["rare", "x"], ["rare", "y"], hand_idf)[0]
ok("shared RARE token > shared COMMON token", rare_pair > common_pair)

# blended_weight — sectors dominate.
ok("blend weights sum to 1", abs(sum(G.DIM_WEIGHTS.values()) - 1.0) < 1e-9)
ok("blended_weight math", abs(G.blended_weight(1.0, 0.0, 0.0) - 0.5) < 1e-9)
ok("sector outweighs keyword", G.blended_weight(1.0, 0, 0) > G.blended_weight(0, 0, 1.0))

# cosine — identical vectors ⇒ 1, orthogonal ⇒ 0, missing ⇒ None.
ok("cosine identical ⇒ 1.0", abs(G.cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9)
ok("cosine orthogonal ⇒ 0.0", abs(G.cosine([1.0, 0.0], [0.0, 1.0])) < 1e-9)
ok("cosine missing embedding ⇒ None", G.cosine(None, [1.0]) is None and G.cosine([1.0], []) is None)
ok("cosine zero vector ⇒ 0.0", G.cosine([0.0, 0.0], [1.0, 1.0]) == 0.0)

# semantic_adjust — the gate that kills coincidental tag links.
ok("no embedding ⇒ tag weight unchanged (degrade safe)", G.semantic_adjust(0.8, None) == 0.8)
ok("below floor ⇒ dropped (None)", G.semantic_adjust(0.8, G.SEMANTIC_FLOOR - 0.01) is None)
ok("at floor ⇒ half tag weight", abs(G.semantic_adjust(0.8, G.SEMANTIC_FLOOR) - 0.4) < 1e-9)
ok("cos=1 ⇒ full tag weight", abs(G.semantic_adjust(0.8, 1.0) - 0.8) < 1e-9)
ok("closer events outrank tag-only near-misses",
   G.semantic_adjust(0.5, 0.9) > G.semantic_adjust(0.5, 0.4))

# causal_direction — earlier event is the cause.
ok("a earlier ⇒ a_to_b", G.causal_direction(1, 2) == "a_to_b")
ok("b earlier ⇒ b_to_a", G.causal_direction(2, 1) == "b_to_a")
ok("equal/none ⇒ undirected", G.causal_direction(1, 1) is None and G.causal_direction(None, 2) is None)

# case-insensitive overlap.
ci, _ = G.weighted_overlap(["Shipping"], ["shipping"], {"shipping": 2.0})
ok("overlap is case-insensitive", ci == 1.0)

print(f"\ngraph_scoring: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
