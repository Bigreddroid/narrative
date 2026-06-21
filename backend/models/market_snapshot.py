import uuid
from datetime import datetime

from sqlalchemy import Float, Text, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class MarketSnapshot(Base):
    """Free market layer — commodity / FX / index prices over time, mapped to sectors.

    Feeds the CPE market-stress term and the temporal layer. Written by
    market_ingest_worker from free sources (stooq, Frankfurter/ECB).
    """
    __tablename__ = "market_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(Text, nullable=False)        # e.g. "brent", "wheat", "usdeur"
    label: Mapped[str | None] = mapped_column(Text)
    sector: Mapped[str | None] = mapped_column(Text)                 # mapped CPE sector
    price: Mapped[float] = mapped_column(Float, nullable=False)
    change_pct: Mapped[float | None] = mapped_column(Float)          # day change %
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_market_snapshots_lookup", "symbol", "captured_at"),
    )
