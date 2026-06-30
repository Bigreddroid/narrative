import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class OsintTriageDecision(Base):
    """One row per OSINT post the triage agent judged — kept OR dropped.

    The flywheel: drops normally vanish (triage returns None), so we never learn
    *why* the agent rejected something or whether thresholds are too tight. Logging
    every decision with its reason makes the funnel observable and tunable, and
    becomes labelled data for future eval/training.
    """

    __tablename__ = "osint_triage_decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)          # osint_gdelt | osint_rss | ...
    kept: Mapped[bool] = mapped_column(Boolean, nullable=False)        # survived triage → upserted
    reason: Mapped[str] = mapped_column(Text, nullable=False)          # see osint_agent reasons
    method: Mapped[str] = mapped_column(Text, nullable=False)          # llm | heuristic
    category: Mapped[str | None] = mapped_column(Text)                 # set when kept (or LLM proposed)
    confidence: Mapped[float | None] = mapped_column(Float)
    importance: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)                    # short, for inspection
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
