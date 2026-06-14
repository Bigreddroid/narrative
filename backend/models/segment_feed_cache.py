import uuid
from datetime import datetime

from sqlalchemy import Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class SegmentFeedCache(Base):
    __tablename__ = "segment_feed_cache"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    segment_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    event_ids: Mapped[list[uuid.UUID] | None] = mapped_column(ARRAY(UUID(as_uuid=True)))
    built_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
