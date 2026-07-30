import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    rss_url: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    bias_rating: Mapped[str | None] = mapped_column(Text)
    bias_source: Mapped[str | None] = mapped_column(Text)
    scrape_method: Mapped[str] = mapped_column(Text, default="rss")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_scraped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scrape_error_count: Mapped[int] = mapped_column(Integer, default=0)
    # When this feed last actually DELIVERED a new article, as distinct from when we
    # last managed to read it. A feed answering 200-with-nothing keeps last_scraped_at
    # fresh and scrape_error_count at 0 forever; only this column shows the rot.
    last_article_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    articles: Mapped[list["Article"]] = relationship("Article", back_populates="source")
