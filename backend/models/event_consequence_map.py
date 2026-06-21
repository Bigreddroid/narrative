import uuid
from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, Integer, Text, DateTime, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class EventConsequenceMap(Base):
    __tablename__ = "event_consequence_maps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narrative_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_events.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    consensus_summary: Mapped[str | None] = mapped_column(Text)
    disputed_points: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    consequence_chain: Mapped[dict | None] = mapped_column(JSONB)
    direct_impact: Mapped[dict | None] = mapped_column(JSONB)
    indirect_impact: Mapped[dict | None] = mapped_column(JSONB)
    prediction_score: Mapped[int | None] = mapped_column(Integer)
    # Prediction score after isotonic recalibration from realised outcomes (identity pre-launch).
    calibrated_prediction_score: Mapped[int | None] = mapped_column(Integer)
    prediction_reasoning: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[str | None] = mapped_column(Text)
    sources_analyzed: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    is_suppressed: Mapped[bool] = mapped_column(Boolean, default=False)
    suppression_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    narrative_event: Mapped["NarrativeEvent"] = relationship(
        "NarrativeEvent", back_populates="consequence_maps"
    )
