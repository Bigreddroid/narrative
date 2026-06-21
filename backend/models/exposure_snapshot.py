import uuid
from datetime import datetime

from sqlalchemy import Integer, Text, DateTime, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class ExposureSnapshot(Base):
    """Time series of the Exposure Index — one row per entity per capture cycle.

    The accumulating history powers momentum/trend, analogs, and pattern base rates
    (the temporal moat). Written by the exposure-snapshot scheduler step.
    """
    __tablename__ = "exposure_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(Text, nullable=False)          # "sector" | "region" | "pressure"
    entity_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_exposure_snapshots_lookup", "kind", "entity_key", "captured_at"),
    )
