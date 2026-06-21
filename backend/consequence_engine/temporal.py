"""
TEMPORAL LAYER (server-side) — history, timelines & patterns over exposure signals.

Authoritative, dependency-light mirror of web/src/lib/temporal.js. Turns snapshot
scores into trajectories: EMA/momentum/trend, historical analogs (pattern match
with realised outcomes), and causal lead-lag. The compounding proprietary history
is the moat — see docs/IP-AND-ALGORITHMS.md. Pure stdlib, unit-testable.
"""

from __future__ import annotations

from datetime import datetime
from statistics import median


def ema(series: list[float], alpha: float = 0.4) -> float:
    if not series:
        return 0.0
    e = series[0]
    for x in series[1:]:
        e = alpha * x + (1 - alpha) * e
    return e


def momentum(series: list[float], alpha: float = 0.4) -> float:
    """Latest value minus the EMA of everything before it. >0 ⇒ rising."""
    if len(series) < 2:
        return 0.0
    return series[-1] - ema(series[:-1], alpha)


def trend_label(m: float, eps: float = 2.0) -> str:
    return "rising" if m > eps else "falling" if m < -eps else "stable"


def _to_set(x) -> set:
    return {str(s).lower() for s in (x or [])}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / (len(a) + len(b) - inter)


def find_analogs(target: dict, history: list[dict], k: int = 3) -> list[dict]:
    """Rank past events by similarity (category + sectors + geography), each with outcome."""
    tcat = str(target.get("category") or "").lower()
    tsec = _to_set(target.get("affected_sectors") or target.get("sectors"))
    tgeo = _to_set(target.get("geography") or target.get("geographic_relevance"))
    out = []
    for h in history or []:
        if h.get("id") == target.get("id"):
            continue
        sim = (
            0.4 * (1 if str(h.get("category") or "").lower() == tcat else 0)
            + 0.35 * _jaccard(tsec, _to_set(h.get("sectors") or h.get("affected_sectors")))
            + 0.25 * _jaccard(tgeo, _to_set(h.get("geography") or h.get("geographic_relevance")))
        )
        if sim > 0:
            out.append({"event": h, "similarity": round(sim * 100)})
    out.sort(key=lambda x: -x["similarity"])
    return out[:k]


def _ts(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def lead_lag(events: list[dict], edges: list[dict]) -> int | None:
    """Median days between a cause event and its effect over the directed graph."""
    t = {str(e["id"]): _ts(e.get("first_detected_at") or e.get("last_updated_at")) for e in events}
    lags = []
    for ed in edges or []:
        a = str(ed.get("source_event_id", ed.get("source")))
        b = str(ed.get("target_event_id", ed.get("target")))
        ta, tb = t.get(a), t.get(b)
        if ta is None or tb is None:
            continue
        days = abs(tb - ta) / 86_400.0
        if days > 0:
            lags.append(days)
    return round(median(lags)) if lags else None
