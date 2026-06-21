import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    narrative_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_events.id"), nullable=False
    )
    original_prediction_score: Mapped[int | None] = mapped_column(Integer)
    predicted_timeline: Mapped[str | None] = mapped_column(Text)
    actual_outcome: Mapped[str | None] = mapped_column(Text)
    outcome_notes: Mapped[str | None] = mapped_column(Text)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    calibration_error: Mapped[float | None] = mapped_column(Float)  # legacy |p-o|
    # Proper scoring + ground truth (Priority 7).
    outcome_label: Mapped[float | None] = mapped_column(Float)            # {1.0, 0.5, 0.0}
    observed_probability: Mapped[float | None] = mapped_column(Float)     # realised outcome ∈ [0,1]
    brier_score: Mapped[float | None] = mapped_column(Float)
    log_loss: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict | None] = mapped_column(JSONB)

    narrative_event: Mapped["NarrativeEvent"] = relationship(
        "NarrativeEvent", back_populates="prediction_outcomes"
    )
