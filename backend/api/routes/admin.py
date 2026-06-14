"""
Admin command panel routes.
All endpoints require admin tier.
Every action logged to admin_logs.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text

from backend.api.dependencies import AdminDep, DbDep
from backend.models.admin_log import AdminLog
from backend.models.narrative_event import NarrativeEvent
from backend.models.event_consequence_map import EventConsequenceMap
from backend.models.pipeline_metrics import PipelineMetric
from backend.models.source import Source
from backend.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


async def _log_action(admin_id, action, target_type, target_id, notes, db):
    log = AdminLog(
        id=uuid.uuid4(),
        admin_id=admin_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        notes=notes,
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    await db.flush()


# ─── DASHBOARD ────────────────────────────────────────────────────────────────

@router.get("/dashboard")
async def get_dashboard(db: DbDep, admin: AdminDep) -> dict:
    today_metrics = await db.execute(
        text("""
            SELECT
                SUM(articles_scraped) AS articles_scraped,
                SUM(articles_embedded) AS articles_embedded,
                SUM(events_mapped) AS events_mapped,
                SUM(claude_calls) AS claude_calls,
                SUM(claude_cost_usd) AS claude_cost_usd,
                SUM(alerts_sent) AS alerts_sent,
                SUM(errors) AS errors
            FROM pipeline_metrics
            WHERE run_at > NOW() - INTERVAL '24 hours'
        """)
    )
    row = today_metrics.fetchone()

    user_count = await db.scalar(select(func.count()).select_from(User))
    event_count = await db.scalar(
        select(func.count()).select_from(NarrativeEvent).where(NarrativeEvent.is_mapped == True)
    )

    return {
        "today": {
            "articles_scraped": row.articles_scraped or 0,
            "articles_embedded": row.articles_embedded or 0,
            "events_mapped": row.events_mapped or 0,
            "claude_calls": row.claude_calls or 0,
            "claude_cost_usd": round(float(row.claude_cost_usd or 0), 4),
            "alerts_sent": row.alerts_sent or 0,
            "errors": row.errors or 0,
        },
        "totals": {
            "users": user_count or 0,
            "mapped_events": event_count or 0,
        },
    }


# ─── PIPELINE METRICS ────────────────────────────────────────────────────────

@router.get("/pipeline/metrics")
async def get_pipeline_metrics(db: DbDep, admin: AdminDep) -> dict:
    result = await db.execute(
        select(PipelineMetric)
        .order_by(PipelineMetric.run_at.desc())
        .limit(200)
    )
    metrics = result.scalars().all()

    return {
        "metrics": [
            {
                "worker_name": m.worker_name,
                "run_at": m.run_at.isoformat(),
                "articles_scraped": m.articles_scraped,
                "articles_embedded": m.articles_embedded,
                "clusters_created": m.clusters_created,
                "events_mapped": m.events_mapped,
                "connections_computed": m.connections_computed,
                "alerts_sent": m.alerts_sent,
                "claude_calls": m.claude_calls,
                "claude_tokens_used": m.claude_tokens_used,
                "claude_cost_usd": m.claude_cost_usd,
                "errors": m.errors,
                "duration_seconds": m.duration_seconds,
            }
            for m in metrics
        ]
    }


# ─── WORKER CONTROLS ─────────────────────────────────────────────────────────

class WorkerTriggerRequest(BaseModel):
    worker_name: str


@router.post("/workers/trigger")
async def trigger_worker(body: WorkerTriggerRequest, db: DbDep, admin: AdminDep) -> dict:
    worker_map = {
        "scrape_worker": "backend.workers.scrape_worker.run_scrape_worker",
        "embed_worker": "backend.workers.embed_worker.run_embed_worker",
        "cluster_worker": "backend.workers.cluster_worker.run_cluster_worker",
        "importance_worker": "backend.workers.importance_worker.run_importance_worker",
        "mapping_worker": "backend.workers.mapping_worker.run_mapping_worker",
        "graph_worker": "backend.workers.graph_worker.run_graph_worker",
        "evolution_worker": "backend.workers.evolution_worker.run_evolution_worker",
        "feed_worker": "backend.workers.feed_worker.run_feed_worker",
        "alert_worker": "backend.workers.alert_worker.run_alert_worker",
        "outcome_worker": "backend.workers.outcome_worker.run_outcome_worker",
        "archive_worker": "backend.workers.archive_worker.run_archive_worker",
    }

    if body.worker_name not in worker_map:
        raise HTTPException(status_code=400, detail=f"Unknown worker: {body.worker_name}")

    await _log_action(admin.id, "trigger_worker", "worker", None, body.worker_name, db)
    await db.commit()

    # Enqueue via RQ
    import redis
    from rq import Queue
    from backend.config import get_settings

    settings = get_settings()
    r = redis.from_url(settings.redis_url)
    q = Queue(connection=r)

    module_path, func_name = worker_map[body.worker_name].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    func = getattr(module, func_name)

    job = q.enqueue(func, job_timeout=600)
    return {"enqueued": True, "job_id": job.id, "worker": body.worker_name}


# ─── SOURCE MANAGER ──────────────────────────────────────────────────────────

@router.get("/sources")
async def list_sources(db: DbDep, admin: AdminDep) -> dict:
    result = await db.execute(select(Source).order_by(Source.name))
    sources = result.scalars().all()

    return {
        "sources": [
            {
                "id": str(s.id),
                "name": s.name,
                "url": s.url,
                "rss_url": s.rss_url,
                "category": s.category,
                "bias_rating": s.bias_rating,
                "scrape_method": s.scrape_method,
                "is_active": s.is_active,
                "last_scraped_at": s.last_scraped_at.isoformat() if s.last_scraped_at else None,
                "scrape_error_count": s.scrape_error_count,
            }
            for s in sources
        ]
    }


class SourceToggle(BaseModel):
    source_id: uuid.UUID
    is_active: bool


@router.patch("/sources/toggle")
async def toggle_source(body: SourceToggle, db: DbDep, admin: AdminDep) -> dict:
    source = await db.get(Source, body.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_active = body.is_active
    db.add(source)

    await _log_action(
        admin.id, "toggle_source", "source", source.id,
        f"set is_active={body.is_active}", db
    )
    await db.commit()

    return {"updated": True, "is_active": source.is_active}


# ─── EVENT REVIEW ────────────────────────────────────────────────────────────

class EventScoreOverride(BaseModel):
    event_id: uuid.UUID
    importance_score: float | None = None
    suppress_map: bool | None = None
    suppression_reason: str | None = None


@router.post("/events/override")
async def override_event(body: EventScoreOverride, db: DbDep, admin: AdminDep) -> dict:
    event = await db.get(NarrativeEvent, body.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    notes = []
    if body.importance_score is not None:
        event.global_importance_score = body.importance_score
        db.add(event)
        notes.append(f"importance_score={body.importance_score}")

    if body.suppress_map is not None:
        map_result = await db.execute(
            select(EventConsequenceMap)
            .where(EventConsequenceMap.narrative_event_id == body.event_id)
            .order_by(EventConsequenceMap.version.desc())
            .limit(1)
        )
        latest_map = map_result.scalar_one_or_none()
        if latest_map:
            latest_map.is_suppressed = body.suppress_map
            latest_map.suppression_reason = body.suppression_reason
            db.add(latest_map)
            notes.append(f"suppress_map={body.suppress_map}")

    await _log_action(
        admin.id, "override_event", "event", body.event_id, "; ".join(notes), db
    )
    await db.commit()

    return {"updated": True}


# ─── COST DASHBOARD ──────────────────────────────────────────────────────────

@router.get("/costs")
async def get_costs(db: DbDep, admin: AdminDep) -> dict:
    costs = await db.execute(
        text("""
            SELECT
                DATE(run_at) AS day,
                SUM(claude_calls) AS claude_calls,
                SUM(claude_tokens_used) AS claude_tokens,
                SUM(claude_cost_usd) AS cost_usd,
                SUM(events_mapped) AS events_mapped
            FROM pipeline_metrics
            WHERE run_at > NOW() - INTERVAL '30 days'
            GROUP BY DATE(run_at)
            ORDER BY day DESC
        """)
    )
    rows = costs.fetchall()

    today_cost = sum(r.cost_usd or 0 for r in rows[:1])
    week_cost = sum(r.cost_usd or 0 for r in rows[:7])
    month_cost = sum(r.cost_usd or 0 for r in rows)

    return {
        "today_usd": round(today_cost, 4),
        "week_usd": round(week_cost, 4),
        "month_usd": round(month_cost, 4),
        "projected_monthly_usd": round(week_cost / 7 * 30, 2) if week_cost else 0,
        "daily_breakdown": [
            {
                "day": str(r.day),
                "claude_calls": r.claude_calls or 0,
                "claude_tokens": r.claude_tokens or 0,
                "cost_usd": round(float(r.cost_usd or 0), 4),
                "events_mapped": r.events_mapped or 0,
            }
            for r in rows
        ],
    }


# ─── USER STATS ──────────────────────────────────────────────────────────────

@router.get("/users/stats")
async def get_user_stats(db: DbDep, admin: AdminDep) -> dict:
    stats = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE tier = 'free') AS free_count,
                COUNT(*) FILTER (WHERE tier = 'paid') AS paid_count,
                COUNT(*) FILTER (WHERE tier = 'admin') AS admin_count,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') AS new_today,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS new_week,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') AS new_month
            FROM users
        """)
    )
    row = stats.fetchone()

    return {
        "total": row.total or 0,
        "by_tier": {
            "free": row.free_count or 0,
            "paid": row.paid_count or 0,
            "admin": row.admin_count or 0,
        },
        "new_users": {
            "today": row.new_today or 0,
            "week": row.new_week or 0,
            "month": row.new_month or 0,
        },
    }
