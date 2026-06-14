import uuid
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Text, DateTime, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class EventConnection(Base):
    __tablename__ = "event_connections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_events.id"), nullable=False
    )
    event_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("narrative_events.id"), nullable=False
    )
    connection_type: Mapped[str | None] = mapped_column(Text)
    connection_weight: Mapped[float | None] = mapped_column(Float)
    shared_sectors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    shared_geography: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    shared_context: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    event_a: Mapped["NarrativeEvent"] = relationship(
        "NarrativeEvent",
        foreign_keys=[event_a_id],
        back_populates="connections_as_a",
    )
    event_b: Mapped["NarrativeEvent"] = relationship(
        "NarrativeEvent",
        foreign_keys=[event_b_id],
        back_populates="connections_as_b",
    )
