"""
Enforced budget gate for paid LLM calls.

Unlike cost_alert.py (which only emails when a soft threshold is crossed), this
module is consulted *before* a paid call and returns False to block it once the
enforced hard caps are reached. Callers then degrade to the free/heuristic path.

Free/local providers are always allowed (cost is $0).
"""

import logging

from backend.config import get_settings
from backend.services import llm

logger = logging.getLogger(__name__)
settings = get_settings()


async def claude_allowed(db) -> bool:
    """True if a paid Anthropic call may proceed right now.

    Returns True immediately for any non-paid active provider (the call is free).
    For the paid provider, blocks when today's or this-month's recorded spend has
    reached the enforced hard cap.
    """
    if not llm.is_paid():
        return True  # local/free provider — nothing to cap

    from backend.admin.metrics import get_today_metrics, get_monthly_cost

    daily = (await get_today_metrics(db))["claude_cost_usd"]
    if daily >= settings.claude_hard_cap_daily_usd:
        logger.warning(
            "Paid LLM blocked: daily spend $%.2f ≥ hard cap $%.2f",
            daily, settings.claude_hard_cap_daily_usd,
        )
        return False

    monthly = await get_monthly_cost(db)
    if monthly >= settings.claude_hard_cap_monthly_usd:
        logger.warning(
            "Paid LLM blocked: 30-day spend $%.2f ≥ hard cap $%.2f",
            monthly, settings.claude_hard_cap_monthly_usd,
        )
        return False

    return True


async def llm_allowed(db) -> bool:
    """True if *some* LLM path can run now: a free provider that is up, or a paid
    provider that is both available and within budget."""
    if not llm.available():
        return False
    return await claude_allowed(db)
