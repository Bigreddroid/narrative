"""Market overlay — latest free commodity / FX prices, mapped to CPE sectors."""

from fastapi import APIRouter
from sqlalchemy import select

from backend.api.dependencies import DbDep, UserDep
from backend.models.market_snapshot import MarketSnapshot

router = APIRouter(prefix="/market", tags=["market"])


async def latest_market_rows(db) -> list[MarketSnapshot]:
    """Most recent snapshot per symbol."""
    rows = (await db.execute(
        select(MarketSnapshot).order_by(MarketSnapshot.symbol, MarketSnapshot.captured_at.desc())
    )).scalars().all()
    latest: dict = {}
    for r in rows:
        latest.setdefault(r.symbol, r)
    return list(latest.values())


@router.get("")
async def get_market(db: DbDep, user: UserDep) -> dict:
    rows = await latest_market_rows(db)
    return {
        "market": [
            {"symbol": r.symbol, "label": r.label, "sector": r.sector,
             "price": r.price, "change_pct": r.change_pct,
             "at": r.captured_at.isoformat() if r.captured_at else None}
            for r in rows
        ]
    }
