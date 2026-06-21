import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class EventRevision(Base):
    __tablename__ = "event_revisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narrative_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_events.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    consequence_chain: Mapped[dict | None] = mapped_column(JSONB)
    prediction_score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[str | None] = mapped_column(Text)
    change_summary: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    narrative_event: Mapped["NarrativeEvent"] = relationship("NarrativeEvent", back_populates="revisions")
