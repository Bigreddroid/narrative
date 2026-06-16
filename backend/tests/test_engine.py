"""Unit tests for the consequence engine's pure scoring/connection logic (no DB)."""
from types import SimpleNamespace

from backend.consequence_engine import importance_scorer as imp
from backend.consequence_engine.graph_connector import _overlap_score, compute_connection_weight


# ── importance scorer ──────────────────────────────────────────────────────────

def test_score_article_matches_signals():
    # population + economic + conflict + tier-1 source should all add up
    score = imp.score_article("War missile attack kills millions", "economic sanctions on oil", "reuters")
    assert score >= 50


def test_score_article_low_for_noise():
    assert imp.score_article("Local bakery wins award", "nice pastries", "unknown blog") < 20


def test_get_mapping_depth_thresholds():
    assert imp.get_mapping_depth(75, 70, 40) == "deep"
    assert imp.get_mapping_depth(55, 70, 40) == "light"
    assert imp.get_mapping_depth(20, 70, 40) == "none"


# ── graph connector ────────────────────────────────────────────────────────────

def test_overlap_score_jaccard():
    score, shared = _overlap_score(["Israel", "Iran", "Lebanon"], ["Iran", "Lebanon", "Syria"])
    assert shared == ["iran", "lebanon"]      # sorted, lowercased
    assert round(score, 3) == 0.5             # 2 shared / 4 union


def test_overlap_score_empty():
    assert _overlap_score([], ["a"]) == (0.0, [])
    assert _overlap_score(None, ["a"]) == (0.0, [])


def _ev(geo=None, sectors=None, kw=None, cat=None):
    return SimpleNamespace(geographic_relevance=geo, affected_sectors=sectors, follow_keywords=kw, category=cat)


def test_connection_forms_on_shared_geography():
    a = _ev(geo=["Israel", "Iran", "Lebanon"], sectors=["Energy"], kw=[], cat="conflict")
    b = _ev(geo=["Israel", "Iran", "Syria"], sectors=["Defense"], kw=[], cat="conflict")
    conn = compute_connection_weight(a, b)
    assert conn is not None
    assert conn["connection_weight"] > 0.12
    assert "iran" in conn["shared_geography"]


def test_connection_none_for_unrelated():
    a = _ev(geo=["Brazil"], sectors=["Agriculture"], kw=[], cat="climate")
    b = _ev(geo=["Japan"], sectors=["Finance"], kw=[], cat="economy")
    assert compute_connection_weight(a, b) is None
