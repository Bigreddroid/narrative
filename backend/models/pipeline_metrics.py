import uuid
from datetime import datetime

from sqlalchemy import Float, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class PipelineMetric(Base):
    __tablename__ = "pipeline_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    worker_name: Mapped[str] = mapped_column(Text, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    articles_scraped: Mapped[int] = mapped_column(Integer, default=0)
    articles_embedded: Mapped[int] = mapped_column(Integer, default=0)
    clusters_created: Mapped[int] = mapped_column(Integer, default=0)
    events_mapped: Mapped[int] = mapped_column(Integer, default=0)
    connections_computed: Mapped[int] = mapped_column(Integer, default=0)
    alerts_sent: Mapped[int] = mapped_column(Integer, default=0)
    claude_calls: Mapped[int] = mapped_column(Integer, default=0)
    claude_tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    claude_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
