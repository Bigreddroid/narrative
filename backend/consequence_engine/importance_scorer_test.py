"""
Property test for importance_scorer (pure, stdlib only). Run from repo root:
    python -m backend.consequence_engine.importance_scorer_test
"""

import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import importance_scorer as S

passed = failed = 0


def ok(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok  {name}")
    else:
        failed += 1
        print(f"  XX  {name}")


BASE = "The government announced major economic sanctions affecting trade."
sa = lambda text, src="reuters", age=None: S.score_article("", text, src, age)

# bounded
ok("empty text => 0", sa("") == 0.0)
ok("scores within [0,100]", all(0 <= sa(t) <= 100 for t in [BASE, BASE * 3, ""]))

# magnitude multiplier
ok("dollar magnitude raises score", sa(BASE + " A $40 billion package.") > sa(BASE))
ok("percentage raises score", sa(BASE + " Output fell 45%.") > sa(BASE))
ok("bigger magnitude => higher", sa(BASE + " $900 billion") > sa(BASE + " $5 million"))
ok("magnitude multiplier capped", S.magnitude_multiplier("$999 trillion 100% 9 billion") <= S.MAGNITUDE_CAP)

# source credibility prior
ok("tier-1 source > unknown source", sa(BASE, "reuters") > sa(BASE, "some random blog"))
ok("credibility tier-1 = 1.0", S.credibility_of("Bloomberg") == 1.0)
ok("credibility unknown = default", S.credibility_of("xyz news") == S.DEFAULT_CREDIBILITY)

# recency decay
ok("fresh > stale", sa(BASE, "reuters", 1) > sa(BASE, "reuters", 24 * 10))
ok("no age => no decay", S.recency_factor(None) == 1.0)
ok("half-life math", abs(S.recency_factor(S.RECENCY_HALFLIFE_HOURS) - 0.5) < 1e-9)

# graded diminishing-returns thematic signal
single = S.score_article_explain("", "oil prices rose", "reuters")
multi = S.score_article_explain("", "oil gas energy fuel lithium copper", "reuters")
ok("more commodity hits => higher signal", multi["signals"]["commodity"] > single["signals"]["commodity"])
ok("diminishing returns (signal < weight cap)", multi["signals"]["commodity"] < 10.0)

# decomposition integrity
exp = S.score_article_explain("", BASE + " $40 billion, 30%", "reuters", 5)
ok("signals sum to thematic", abs(sum(exp["signals"].values()) - exp["thematic"]) < 0.05)
ok("explain has all components", all(k in exp for k in ("score", "thematic", "signals", "magnitude_mult", "credibility", "recency")))

# ── Cluster scoring (Priority 4) ───────────────────────────────────────────────
art = lambda score, src, age=None: {"article_score": score, "source_name": src, "age_hours": age}

ok("empty cluster => 0", S.score_cluster([]) == 0.0)
ok("cluster bounded [0,100]", 0 <= S.score_cluster([art(90, "reuters"), art(80, "bbc news")]) <= 100)

# robust blend: one strong article isn't washed out by weak ones (beats the plain mean of 30)
strong_lead = S.score_cluster([art(90, "reuters"), art(10, "a"), art(10, "b"), art(10, "c")])
ok("strong lead beats plain mean", strong_lead > 30)

# source diversity entropy
diverse = S.score_cluster([art(50, "a"), art(50, "b"), art(50, "c")])
mono = S.score_cluster([art(50, "a"), art(50, "a"), art(50, "a")])
ok("diverse sources > single source", diverse > mono)
ok("entropy: single source = 0", S.source_entropy(["a", "a", "a"]) == 0.0)
ok("entropy: uniform = 1", abs(S.source_entropy(["a", "b"]) - 1.0) < 1e-9)

# tier-1 corroboration
ok("tier-1 source raises cluster", S.score_cluster([art(50, "reuters"), art(50, "x")]) > S.score_cluster([art(50, "y"), art(50, "x")]))

# velocity: accelerating coverage adds bonus
fast = S.score_cluster([art(50, "a", 1), art(50, "b", 2), art(50, "c", 3), art(50, "d", 11)])
slow = S.score_cluster([art(50, "a", 11), art(50, "b", 11.5)])
ok("accelerating coverage scores higher", fast > slow)

# ── Budget-aware routing (Priority 4) ──────────────────────────────────────────
scored = [("a", 95), ("b", 80), ("c", 72), ("d", 50), ("e", 20)]
plan = S.plan_routing(scored, deep_threshold=70, light_threshold=40, deep_budget=2)
ok("top-2 deep within budget", plan["a"] == "deep" and plan["b"] == "deep")
ok("deep-eligible over budget => light", plan["c"] == "light")
ok("mid score => light", plan["d"] == "light")
ok("low score => none", plan["e"] == "none")
ok("unlimited budget deepens all eligible", S.plan_routing(scored, 70, 40, 99)["c"] == "deep")

print(f"\nimportance_scorer: {passed} passed, {failed} failed")
raise SystemExit(1 if failed else 0)
