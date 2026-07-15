import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Float, String, Text, DateTime, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class NarrativeEvent(Base):
    __tablename__ = "narrative_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    canonical_title: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    # Multi-INT intelligence discipline (HUMINT/SIGINT/IMINT/GEOINT/MASINT/FININT/
    # CYBINT), derived deterministically from (source, category) at ingest — see
    # backend/taxonomy.discipline_for. Nullable so pre-migration rows never break.
    int_discipline: Mapped[str | None] = mapped_column(Text, index=True)
    global_importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    current_status: Mapped[str] = mapped_column(Text, default="developing")
    affected_sectors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    affected_professions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    geographic_relevance: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    geo_centroid_lat: Mapped[float | None] = mapped_column(Float)
    geo_centroid_lng: Mapped[float | None] = mapped_column(Float)
    follow_keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    # Free-feed provenance (real-source events): dedupe by (source, external_id).
    source: Mapped[str | None] = mapped_column(Text)
    external_id: Mapped[str | None] = mapped_column(Text)
    # Set when this event is a near-duplicate folded into a canonical event; such
    # rows are kept (provenance) but excluded from every feed/map query.
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    is_mapped: Mapped[bool] = mapped_column(Boolean, default=False)
    is_importance_scored: Mapped[bool] = mapped_column(Boolean, default=False)
    is_graph_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    first_detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="narrative_event")
    consequence_maps: Mapped[list["EventConsequenceMap"]] = relationship(
        "EventConsequenceMap", back_populates="narrative_event"
    )
    revisions: Mapped[list["EventRevision"]] = relationship("EventRevision", back_populates="narrative_event")
    prediction_outcomes: Mapped[list["PredictionOutcome"]] = relationship(
        "PredictionOutcome", back_populates="narrative_event"
    )
    follows: Mapped[list["UserFollow"]] = relationship("UserFollow", back_populates="narrative_event")
    connections_as_a: Mapped[list["EventConnection"]] = relationship(
        "EventConnection",
        foreign_keys="EventConnection.event_a_id",
        back_populates="event_a",
    )
    connections_as_b: Mapped[list["EventConnection"]] = relationship(
        "EventConnection",
        foreign_keys="EventConnection.event_b_id",
        back_populates="event_b",
    )
