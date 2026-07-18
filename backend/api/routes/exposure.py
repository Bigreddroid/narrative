"""
Exposure API — serves the Consequence Propagation Engine output.

The CPE and its tuned parameters live server-side (backend/consequence_engine/
propagation.py) so the trade-secret constants never reach the browser. Clients
receive only computed scores + driver attribution.

  GET  /api/v1/exposure       → full sector/region exposure model
  GET  /api/v1/exposure/me    → personalised exposure for the current user's profile
"""

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter
from sqlalchemy import func, select

from backend.api.dependencies import DbDep, UserDep
from backend.api.routes.market import latest_market_rows
from backend.api.routes.vessels import cached_vessels
from backend.consequence_engine import corroboration, propagation
from backend.services import source_reliability
from backend.feeds import chokepoints, spaceweather
from backend.feeds.market import sector_stress
from backend.models.event_connection import EventConnection
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.exposure_snapshot import ExposureSnapshot
from backend.models.narrative_event import NarrativeEvent

router = APIRouter(prefix="/exposure", tags=["exposure"])

FREE_TIER_EVENT_LIMIT = 10
PAID_TIER_EVENT_LIMIT = 500
HISTORY_POINTS = 12  # real ExposureSnapshot points attached per entity (oldest→newest)


async def _load_graph(db, limit: int, event_ids: list | None = None) -> tuple[list[dict], list[dict]]:
    """Load mapped events (with their latest consequence map) + causal edges.

    When ``event_ids`` is given, load exactly those events (question-scoped
    exposure for the analyst chat) instead of the global top-importance slice —
    so the readout differs per question rather than being the same global list.
    """
    stmt = select(NarrativeEvent).where(NarrativeEvent.is_mapped == True)  # noqa: E712
    if event_ids:
        ids = [UUID(x) if isinstance(x, str) else x for x in event_ids]
        stmt = stmt.where(NarrativeEvent.id.in_(ids)).limit(len(ids))
    else:
        stmt = stmt.order_by(NarrativeEvent.global_importance_score.desc()).limit(limit)
    events_result = await db.execute(stmt)
    events = events_result.scalars().all()
    event_ids = [e.id for e in events]
    if not event_ids:
        return [], []

    # Latest (highest-version) consequence map per event.
    maps_result = await db.execute(
        select(EventConsequenceMap)
        .where(EventConsequenceMap.narrative_event_id.in_(event_ids))
        .where(EventConsequenceMap.is_suppressed == False)  # noqa: E712
        .order_by(EventConsequenceMap.narrative_event_id, EventConsequenceMap.version.desc())
    )
    latest_map: dict = {}
    for m in maps_result.scalars().all():
        latest_map.setdefault(m.narrative_event_id, m)

    engine_events = []
    for e in events:
        m = latest_map.get(e.id)
        engine_events.append({
            "id": str(e.id),
            "canonical_title": e.canonical_title,
            "category": e.category,
            # multi-INT: enables the cross-discipline corroboration uplift (XDISC_W)
            "discipline": e.int_discipline,
            "importance_score": e.global_importance_score,
            "current_status": e.current_status,
            "geographic_relevance": e.geographic_relevance or [],
            "first_detected_at": e.first_detected_at,
            "last_updated_at": e.last_updated_at,
            # for cross-feed corroboration (independent feed convergence in geo+time)
            "source": e.source,
            "lat": e.geo_centroid_lat,
            "lng": e.geo_centroid_lng,
            "ts": e.first_detected_at.timestamp() * 1000 if e.first_detected_at else None,
            "consequence_map": None if m is None else {
                "consequence_chain": m.consequence_chain,
                "direct_impact": m.direct_impact,
                "indirect_impact": m.indirect_impact,
                "disputed_points": m.disputed_points,
                "sources_analyzed": m.sources_analyzed,
                "confidence": m.confidence,
            },
        })

    id_set = set(event_ids)
    edges_result = await db.execute(
        select(EventConnection)
        .where(EventConnection.event_a_id.in_(id_set))
        .where(EventConnection.event_b_id.in_(id_set))
        .order_by(EventConnection.connection_weight.desc())
        .limit(2000)
    )
    edges = []
    for c in edges_result.scalars().all():
        # Orient the edge cause→effect using the stored direction label.
        src, tgt = (c.event_b_id, c.event_a_id) if c.direction == "b_to_a" else (c.event_a_id, c.event_b_id)
        edges.append({
            "source": str(src),
            "target": str(tgt),
            "weight": c.connection_weight,
            "directed": c.direction is not None,
            # carried for the consequence tracer's hop mechanism (ignored by the CPE)
            "shared_sectors": c.shared_sectors or [],
            "shared_geography": c.shared_geography or [],
            "cosine": (c.weight_breakdown or {}).get("cosine"),
        })
    return engine_events, edges


async def _market_stress(db) -> dict:
    """Per-sector market stress from the latest free commodity/FX snapshots."""
    rows = await latest_market_rows(db)
    return sector_stress([{"sector": r.sector, "change_pct": r.change_pct} for r in rows])


async def _attach_reliability(db, model: dict, events: list[dict]) -> None:
    """Attach NATO Admiralty grades to /exposure's corroboration map. The grading is
    shared with the view-scoped /events/corroboration so both surfaces read the same
    (see source_reliability.attach_grades)."""
    await source_reliability.attach_grades(db, model.get("corroboration") or {}, events)


async def _attach_history(db, model: dict) -> None:
    """Attach REAL recent ExposureSnapshot history (oldest→newest) to each sector/
    region so the UI can draw a genuine trend. Entities with <2 stored points get
    none (the UI then shows no trend rather than a fabricated one)."""
    wanted = {"sector": {s["key"] for s in model["sectors"]},
              "region": {r["key"] for r in model["regions"]}}
    hist: dict = {}
    for kind, keys in wanted.items():
        if not keys:
            continue
        rows = (await db.execute(
            select(ExposureSnapshot.entity_key, ExposureSnapshot.score)
            .where(ExposureSnapshot.kind == kind)
            .where(ExposureSnapshot.entity_key.in_(keys))
            .order_by(ExposureSnapshot.captured_at.asc())
        )).all()
        per: dict = defaultdict(list)
        for ek, score in rows:
            per[ek].append(score)
        for ek, scores in per.items():
            hist[(kind, ek)] = scores[-HISTORY_POINTS:]
    for s in model["sectors"]:
        h = hist.get(("sector", s["key"]), [])
        if len(h) >= 2:
            s["history"] = h
    for r in model["regions"]:
        h = hist.get(("region", r["key"]), [])
        if len(h) >= 2:
            r["history"] = h


# CYBINT stress: saturating map from recent cyber-event volume to a bounded 0-1
# level. 3 cyber events ≈ 0.63, matching the corroboration KAPPA feel. Server-side.
_CYBER_KAPPA = 3.0
_CYBER_WINDOW_DAYS = 7


async def _cyber_stress(db) -> dict:
    """Per-sector stress from recent CYBINT activity (CISA KEV / ransomware / cyber
    events). Feeds the same combine_stress channel as market/chokepoint/space so a
    live CVE or ransomware wave lifts Technology/Banking exposure — a concrete
    multi-INT fusion signal. Best-effort: any failure degrades to no-op."""
    try:
        since = datetime.now(timezone.utc) - timedelta(days=_CYBER_WINDOW_DAYS)
        n = (await db.execute(
            select(func.count()).select_from(NarrativeEvent)
            .where(NarrativeEvent.int_discipline == "CYBINT")
            .where(NarrativeEvent.merged_into_id.is_(None))
            .where(func.coalesce(NarrativeEvent.last_updated_at, NarrativeEvent.first_detected_at) >= since)
        )).scalar_one()
        if not n:
            return {}
        lvl = round(1 - math.exp(-n / _CYBER_KAPPA), 4)
        return {"Technology": lvl, "Banking": round(0.6 * lvl, 4),
                "Infrastructure": round(0.4 * lvl, 4)}
    except Exception:  # noqa: BLE001 — cyber stress is best-effort, never break exposure
        return {}


async def _combined_stress(db) -> dict:
    """Merge the CPE's external stress channels into one {sector: 0-1} dict:
    market moves + Chokepoint Congestion Index (from cached AIS) + space weather +
    CYBINT activity. Each source degrades to no-op if its data is unavailable."""
    market = await _market_stress(db)
    try:
        choke = chokepoints.sector_stress(chokepoints.chokepoint_congestion(cached_vessels()))
    except Exception:  # noqa: BLE001 — congestion is best-effort, never break exposure
        choke = {}
    try:
        space = spaceweather.sector_stress(await spaceweather.latest_kp())
    except Exception:  # noqa: BLE001
        space = {}
    cyber = await _cyber_stress(db)
    return propagation.combine_stress(market, choke, space, cyber)


@router.get("")
async def get_exposure(db: DbDep, user: UserDep) -> dict:
    """Full sector + region exposure model from the live event graph."""
    limit = FREE_TIER_EVENT_LIMIT if user.tier == "free" else PAID_TIER_EVENT_LIMIT
    events, edges = await _load_graph(db, limit)
    # Cross-feed corroboration: independent feeds converging in geo+time both
    # amplify the event's shock (passed into the model) and are surfaced for the UI.
    corrob = corroboration.corroborate(events)
    model = propagation.compute_exposure_model(
        events, edges, market_stress=await _combined_stress(db), corroboration=corrob)
    model["corroboration"] = {k: v for k, v in corrob.items() if v["count"] > 0}
    await _attach_reliability(db, model, events)
    await _attach_history(db, model)
    if user.tier == "free":
        # Free tier sees the headline pressure + top sectors only.
        model = {**model, "sectors": model["sectors"][:3], "regions": model["regions"][:3], "limited": True}
    return model


@router.get("/history")
async def get_exposure_history(db: DbDep, user: UserDep, kind: str = "sector", entity: str = "", limit: int = 168) -> dict:
    """Time series of the Exposure Index for an entity (oldest → newest)."""
    q = select(ExposureSnapshot.score, ExposureSnapshot.captured_at).where(ExposureSnapshot.kind == kind)
    if entity:
        q = q.where(ExposureSnapshot.entity_key == entity)
    q = q.order_by(ExposureSnapshot.captured_at.desc()).limit(max(1, min(limit, 2000)))
    rows = (await db.execute(q)).all()
    series = [{"score": s, "at": c.isoformat()} for s, c in reversed(rows)]
    return {"kind": kind, "entity": entity, "series": series}


@router.get("/countries")
async def get_country_risk(db: DbDep, user: UserDep, top: int = 30) -> dict:
    """Per-country risk index: sum(importance × time-decay) over events touching
    each country (a 'country instability' view). Derived from the live event
    graph — no external data. Free tier sees the top 5."""
    from backend.services.analyst import country_risk
    cap = 5 if user.tier == "free" else max(1, min(top, 100))
    countries = await country_risk(db, top=cap)
    return {"countries": countries, "limited": user.tier == "free"}


@router.get("/me")
async def get_my_exposure(db: DbDep, user: UserDep) -> dict:
    """Personalised exposure for the current user's profile (sectors + home region)."""
    events, edges = await _load_graph(db, PAID_TIER_EVENT_LIMIT)
    model = propagation.compute_exposure_model(
        events, edges, market_stress=await _combined_stress(db),
        corroboration=corroboration.corroborate(events))
    # Choosable lens (R2): the profile is exactly what the user picked — named
    # regions/routes/chokepoints take precedence, home city/country fill in. Exposure
    # is computed strictly over this profile (profile_exposure returns empty when
    # nothing matches — no generic/global fallback leaks into a personal view).
    profile = {
        "sectors": user.spending_categories or [],
        "regions": (user.regions or []) + [r for r in (user.country, user.city) if r],
        "purpose": user.purpose or [],
        "watched_assets": user.watched_assets or [],
    }
    personal = propagation.profile_exposure(profile, model)
    return {"profile": profile, "exposure": personal, "pressure": model["pressure"], "meta": model["meta"]}
