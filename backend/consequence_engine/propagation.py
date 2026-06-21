"""
THE NARRATIVE — CONSEQUENCE PROPAGATION ENGINE (CPE) v2 — server-side core.

Authoritative, server-side port of web/src/lib/propagation.js. Keeping the engine
(and its tuned parameters) on the server is an IP requirement: the constants below
are the trade-secret surface and must never ship to the browser. The client should
consume only computed scores + drivers via /api/v1/exposure.

Deterministic. Explainable. Runs WITHOUT the LLM. See docs/IP-AND-ALGORITHMS.md.

base(e)       = importance(e) · confidence(e) · recency(e)
effective(e)  = base(e) + LAMBDA · Σ_{c→e} w · effective(c)         (Katz diffusion)
shock(entity) = Σ_e Σ_impacts sign · severity · effective(e)
ExposureIndex = 100 · (1 − e^(−max(net_shock, 0) / K))              (bounded 0–100)
"""

from __future__ import annotations

import math
import re
import time
from datetime import datetime

from backend.consequence_engine.corroboration import CORROB_W

# Tuned "secret sauce" — versioned with the model. SERVER-SIDE ONLY.
ENGINE_VERSION = "2.0"
LAMBDA = 0.5            # per-hop causal decay (LAMBDA·ρ(W) < 1 ⇒ Katz series converges)
K = 0.8                # exposure saturation constant
INDIRECT_FACTOR = 0.6  # indirect impacts count less than direct
SEVERITY = {"critical": 1.0, "high": 0.72, "medium": 0.45, "low": 0.22}
EVIDENCE = {"VERIFIED": 1.0, "INFERRED": 0.6, "SPECULATIVE": 0.3}
KAPPA = 2.5            # corroboration saturation (independent sources)
DELTA = 0.5           # max confidence penalty from fully-disputed claims
TAU_HOURS = 168.0     # event-freshness e-folding horizon (≈7 days)
MAX_ITERS = 64        # Katz diffusion iteration cap
EPSILON = 1e-4        # Katz convergence tolerance
K_EVENT = 1.2         # saturation for per-event exposure heat
DISRUPTION_K = 0.8    # max shock from traffic disruption near an event
TAU_TRAFFIC = 30.0    # traffic-count saturation for disruption emissions
MARKET_W = 0.5        # how much per-sector market stress amplifies its exposure

ENTITY_ALIASES = {
    "shipping and logistics": "shipping",
    "logistics": "shipping",
    "maritime shipping": "shipping",
    "oil and gas": "energy",
    "fuel": "energy",
    "consumer prices": "consumer goods",
    "semiconductor supply": "semiconductors",
    "tech industry": "technology",
    "ai": "technology",
}

_PARAMS_PUBLIC = {
    "version": ENGINE_VERSION,
    # NOTE: only the version is public. The constants are intentionally omitted.
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _as_list(v):
    if isinstance(v, list):
        return v
    return [v] if v else []


def _sev_weight(s) -> float:
    return SEVERITY.get(str(s or "medium").lower(), SEVERITY["medium"])


def _importance_of(e: dict) -> float:
    raw = e.get("importance_score")
    if raw is None:
        raw = e.get("global_importance_score")
    if raw is None:
        raw = e.get("importance", 0)
    return _clamp01((raw or 0) / 100.0)


def canonicalize(name) -> str:
    s = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(name or "").lower().replace("&", " and "))).strip()
    return ENTITY_ALIASES.get(s, s)


def _to_ms(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw.timestamp() * 1000.0
    try:
        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s).timestamp() * 1000.0
    except ValueError:
        return None


def _recency_of(e: dict, now_ms: float) -> float:
    ts = _to_ms(e.get("last_updated_at") or e.get("first_detected_at") or e.get("created_at"))
    if ts is None:
        return 1.0
    age_hours = max(0.0, (now_ms - ts) / 3_600_000.0)
    return math.exp(-age_hours / TAU_HOURS)


def _confidence_of(e: dict) -> float:
    m = e.get("consequence_map") or {}
    chain = m.get("consequence_chain") or []
    chain = chain if isinstance(chain, list) else []

    if chain:
        s = 0.0
        for n in chain:
            t = str((n or {}).get("type", "")).upper()
            s += EVIDENCE["VERIFIED"] if "VERIFIED" in t else EVIDENCE["INFERRED"] if "INFERRED" in t else EVIDENCE["SPECULATIVE"]
        grade = s / len(chain)
    else:
        c = m.get("confidence")
        grade = 0.85 if c == "high" else 0.4 if c == "low" else 0.6

    n_sources = len(m.get("sources_analyzed") or []) or e.get("sources_count") or len(e.get("articles") or []) or (len(chain) or 1)
    corroboration = 1 - math.exp(-n_sources / KAPPA)

    disputed = len(m.get("disputed_points") or [])
    dispute_penalty = DELTA * (disputed / (len(chain) + disputed)) if disputed else 0.0

    return _clamp01(grade * corroboration * (1 - dispute_penalty))


def _base_of(e: dict, now_ms: float) -> float:
    base = _importance_of(e) * _confidence_of(e) * _recency_of(e, now_ms)
    # Cross-feed corroboration uplift (default 0 ⇒ no-op): independent feeds
    # converging on the same place+time make an event's shock more credible.
    idx = e.get("corroboration_index")
    if idx:
        base *= 1 + CORROB_W * _clamp01(idx)
    return base


_MITIGATE_RE = re.compile(r"mitigat|reduc|de-?escalat|resolv")


def _is_mitigating(i: dict) -> bool:
    return bool(_MITIGATE_RE.search(str((i or {}).get("direction") or (i or {}).get("effect") or "").lower()))


def _sector_emissions(e: dict, traffic_by_event: dict | None = None):
    m = e.get("consequence_map") or {}
    out = []
    for i in _as_list(m.get("direct_impact")):
        if i and i.get("sector"):
            out.append((i["sector"].strip(), _sev_weight(i.get("severity")), -1 if _is_mitigating(i) else 1))
    for i in _as_list(m.get("indirect_impact")):
        if i and i.get("sector"):
            out.append((i["sector"].strip(), _sev_weight(i.get("severity")) * INDIRECT_FACTOR, -1 if _is_mitigating(i) else 1))
    tr = (traffic_by_event or {}).get(str(e["id"]))
    if tr:
        esc = 1.0 if e.get("current_status") == "escalating" else 0.5
        disrupt = lambda n: DISRUPTION_K * (1 - math.exp(-(n or 0) / TAU_TRAFFIC)) * esc  # noqa: E731
        if tr.get("vessels"):
            out.append(("shipping", disrupt(tr["vessels"]), 1))
        if tr.get("aircraft"):
            out.append(("aviation", disrupt(tr["aircraft"]), 1))
    return out


def _region_emissions(e: dict):
    geos = e.get("geography") or e.get("geographic_relevance") or []
    m = e.get("consequence_map") or {}
    impacts = _as_list(m.get("direct_impact")) + _as_list(m.get("indirect_impact"))
    max_sev = max((_sev_weight(i.get("severity")) for i in impacts), default=0.5)
    all_mit = len(impacts) > 0 and all(_is_mitigating(i) for i in impacts)
    return [(str(g).strip(), max_sev, -1 if all_mit else 1) for g in geos]


def _diffuse(events: list[dict], edges: list[dict], now_ms: float):
    by_id = {str(e["id"]): e for e in events}
    ids = [str(e["id"]) for e in events]

    in_adj: dict[str, list[tuple[str, float]]] = {i: [] for i in ids}
    for ed in edges or []:
        a = str(ed.get("source_event_id", ed.get("source")))
        b = str(ed.get("target_event_id", ed.get("target")))
        w = ed.get("weight", ed.get("connection_weight", 0.5)) or 0.5
        if a not in by_id or b not in by_id:
            continue
        in_adj[b].append((a, w))
        if ed.get("directed") is not True:
            in_adj[a].append((b, w))

    base = {i: _base_of(by_id[i], now_ms) for i in ids}
    eff = dict(base)
    attr: dict[str, dict[str, float]] = {i: {i: base[i]} for i in ids}

    for _ in range(MAX_ITERS):
        next_eff: dict[str, float] = {}
        next_attr: dict[str, dict[str, float]] = {}
        max_delta = 0.0
        for i in ids:
            v = base[i]
            m: dict[str, float] = {i: base[i]}
            for frm, w in in_adj[i]:
                v += LAMBDA * w * eff[frm]
                for src, amt in attr[frm].items():
                    m[src] = m.get(src, 0.0) + LAMBDA * w * amt
            next_eff[i] = v
            next_attr[i] = m
            max_delta = max(max_delta, abs(v - eff[i]))
        eff, attr = next_eff, next_attr
        if max_delta < EPSILON:
            break

    return by_id, attr


def _propagate(events, edges, emit, now_ms):
    by_id, attr = _diffuse(events, edges, now_ms)

    contrib: dict[str, dict] = {}
    for e in events:
        eid = str(e["id"])
        eff_attr = attr[eid]
        for target, w, sign in emit(e):
            key = canonicalize(target)
            if not key:
                continue
            slot = contrib.setdefault(key, {"display": target, "parts": {}})
            for src, amt in eff_attr.items():
                slot["parts"][src] = slot["parts"].get(src, 0.0) + sign * w * amt

    def title_of(i):
        ev = by_id.get(i)
        return (ev or {}).get("canonical_title") or (ev or {}).get("title") or i

    out = []
    for key, slot in contrib.items():
        pos = sum(a for a in slot["parts"].values() if a > 0)
        neg = sum(-a for a in slot["parts"].values() if a < 0)
        net = pos - neg
        score = round(100 * (1 - math.exp(-max(net, 0) / K)))

        ordered = sorted(slot["parts"].items(), key=lambda kv: (-kv[1], str(kv[0])))
        drivers = [
            {"id": i, "title": title_of(i), "category": (by_id.get(i) or {}).get("category"), "pct": round(100 * amt / pos) if pos else 0}
            for i, amt in ordered if amt > 0
        ][:3]
        mitigators = [
            {"id": i, "title": title_of(i), "category": (by_id.get(i) or {}).get("category"), "pct": round(100 * -amt / neg) if neg else 0}
            for i, amt in sorted(slot["parts"].items(), key=lambda kv: kv[1]) if amt < 0
        ][:2]

        out.append({"name": slot["display"], "key": key, "score": score, "net": round(net, 4), "raw": round(pos, 4), "drivers": drivers, "mitigators": mitigators})

    # Per-event drive: total exposure each event projects across all entities.
    event_drive: dict[str, float] = {}
    for slot in contrib.values():
        for src, amt in slot["parts"].items():
            event_drive[src] = event_drive.get(src, 0.0) + abs(amt)

    out.sort(key=lambda x: (-x["score"], x["key"]))
    return out, event_drive


def combine_stress(*stresses: dict | None) -> dict:
    """Merge several {sector: 0-1} stress dicts into one (max per sector, clamped).

    Lets independent stress sources — market moves, chokepoint congestion, space
    weather — share the single market_stress channel without double-counting.
    """
    out: dict[str, float] = {}
    for s in stresses:
        for sec, raw in (s or {}).items():
            try:
                v = max(0.0, min(1.0, float(raw)))
            except (TypeError, ValueError):
                continue
            if v > out.get(sec, 0.0):
                out[sec] = v
    return out


def compute_exposure_model(events: list[dict], edges: list[dict] | None = None, now_ms: float | None = None,
                           traffic_by_event: dict | None = None, market_stress: dict | None = None,
                           corroboration: dict | None = None) -> dict:
    """Full exposure model from the live event graph. Public-safe (no params leaked).

    `corroboration` maps event id → {"index": 0-1} (from corroboration.corroborate);
    a corroborated event's base shock is amplified before diffusion.
    """
    if now_ms is None:
        now_ms = time.time() * 1000.0
    edges = edges or []

    if corroboration:
        def _corrob_idx(e):
            rec = corroboration.get(str(e.get("id")))
            return rec.get("index", 0.0) if isinstance(rec, dict) else (rec or 0.0)
        # copy (never mutate the caller's events) so no index leaks across calls
        events = [{**e, "corroboration_index": _corrob_idx(e)} for e in events]
    sectors, s_drive = _propagate(events, edges, lambda e: _sector_emissions(e, traffic_by_event), now_ms)
    regions, r_drive = _propagate(events, edges, _region_emissions, now_ms)

    # Market stress amplifies exposure on stressed sectors (bounded, transparent).
    if market_stress:
        idx = {x["key"]: x for x in sectors}
        for sec, raw in market_stress.items():
            key = canonicalize(sec)
            st = max(0.0, min(1.0, raw))
            if key in idx:
                x = idx[key]
                x["score"] = round(x["score"] + (100 - x["score"]) * st * MARKET_W)
            elif st > 0:
                sectors.append({"name": sec, "key": key, "score": round(100 * st * MARKET_W),
                                "net": 0.0, "raw": 0.0, "drivers": [], "mitigators": [], "market": True})
        sectors.sort(key=lambda x: (-x["score"], x["key"]))

    drive: dict[str, float] = {}
    for d in (s_drive, r_drive):
        for k, v in d.items():
            drive[k] = drive.get(k, 0.0) + v
    event_scores = {k: round(100 * (1 - math.exp(-v / K_EVENT))) for k, v in drive.items()}

    top = sectors[:5]
    pressure = round(sum(x["score"] for x in top) / len(top)) if top else 0
    return {
        "sectors": sectors,
        "regions": regions,
        "event_scores": event_scores,
        "pressure": pressure,
        "meta": {"events": len(events), "links": len(edges), **_PARAMS_PUBLIC},
    }


def profile_exposure(profile: dict, model: dict) -> dict:
    """Personalised exposure for a user profile of sectors/regions, with attribution."""
    wanted = {canonicalize(s) for s in (profile.get("sectors") or []) + (profile.get("regions") or [])}
    matches = [x for x in (model["sectors"] + model["regions"]) if x["key"] in wanted]
    if not matches:
        return {"score": 0, "drivers": []}
    mx = max(m["score"] for m in matches)
    mean = sum(m["score"] for m in matches) / len(matches)
    score = round(0.65 * mx + 0.35 * mean)
    agg: dict[str, dict] = {}
    for m in matches:
        for d in m["drivers"]:
            slot = agg.setdefault(d["id"], {**d, "pct": 0})
            slot["pct"] += d["pct"]
    drivers = sorted(agg.values(), key=lambda d: -d["pct"])[:3]
    return {"score": score, "drivers": drivers}
