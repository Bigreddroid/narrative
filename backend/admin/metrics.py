"""
Admin metrics — aggregates pipeline_metrics for dashboard queries.
"""

from datetime import datetime, timezone, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_today_metrics(db: AsyncSession) -> dict:
    result = await db.execute(
        text("""
            SELECT
                COALESCE(SUM(articles_scraped), 0) AS articles_scraped,
                COALESCE(SUM(articles_embedded), 0) AS articles_embedded,
                COALESCE(SUM(events_mapped), 0) AS events_mapped,
                COALESCE(SUM(claude_calls), 0) AS claude_calls,
                COALESCE(SUM(claude_cost_usd), 0) AS claude_cost_usd,
                COALESCE(SUM(alerts_sent), 0) AS alerts_sent,
                COALESCE(SUM(errors), 0) AS errors
            FROM pipeline_metrics
            WHERE run_at > NOW() - INTERVAL '24 hours'
        """)
    )
    row = result.fetchone()
    return {
        "articles_scraped": int(row.articles_scraped),
        "articles_embedded": int(row.articles_embedded),
        "events_mapped": int(row.events_mapped),
        "claude_calls": int(row.claude_calls),
        "claude_cost_usd": float(row.claude_cost_usd),
        "alerts_sent": int(row.alerts_sent),
        "errors": int(row.errors),
    }


async def get_monthly_cost(db: AsyncSession) -> float:
    result = await db.execute(
        text("""
            SELECT COALESCE(SUM(claude_cost_usd), 0) AS total
            FROM pipeline_metrics
            WHERE run_at > NOW() - INTERVAL '30 days'
        """)
    )
    return float(result.scalar() or 0)
