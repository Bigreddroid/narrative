"""
MARKET INGEST — pulls free commodity/FX prices into market_snapshots (no paid keys).
Feeds the CPE market-stress term and the /api/v1/market overlay.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

from backend.database import AsyncSessionLocal
from backend.feeds import market
from backend.models.market_snapshot import MarketSnapshot

logger = logging.getLogger(__name__)


async def run_market_ingest_worker() -> dict:
    start = time.perf_counter()
    rows = await market.fetch_market()
    if rows:
        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as db:
            for r in rows:
                db.add(MarketSnapshot(
                    id=uuid.uuid4(), symbol=r["symbol"], label=r.get("label"),
                    sector=r.get("sector"), price=r["price"], change_pct=r.get("change_pct"),
                    captured_at=now,
                ))
            await db.commit()
    logger.info("Market ingest: %d rows (%.1fs)", len(rows), time.perf_counter() - start)
    return {"rows": len(rows)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_market_ingest_worker())
