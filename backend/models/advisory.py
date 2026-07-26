import uuid
from datetime import datetime

from sqlalchemy import Boolean, Text, DateTime, func, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Advisory(Base):
    """One government travel advisory, as that government published it.

    Every field here is THEIRS. We store the issuing authority, their level in their
    own vocabulary, their text, their publication date and a link back to the source.
    We add nothing. The incumbent's 143 advice sheets are written by a research desk
    we do not have, and inventing guidance would be the same fabrication this project
    refuses everywhere else — so this is an ingest, not an authoring surface.

    🔴 ``level_code`` is NOT comparable across authorities. State Department "L2" and
    FCDO "avoid_all_travel_to_parts" are different instruments from different
    governments. There is deliberately no normalised numeric column: a single blended
    score would invent a precision neither authority claims, and a customer acting on
    it would think two governments agreed when they had not been asked the same
    question.

    History is kept, not overwritten. ``is_current`` marks the latest sheet per
    (authority, country); superseded rows stay, because "what did the FCDO say when
    we sent our people?" is a question a duty-of-care team has to be able to answer
    after the fact.
    """
    __tablename__ = "advisories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # gov_us_state_dept | gov_uk_fcdo — prefixed so source_reliability's provenance
    # prior grades them through the normal path (B, "usually reliable"), not a special case.
    authority: Mapped[str] = mapped_column(Text, nullable=False)
    country: Mapped[str] = mapped_column(Text, nullable=False)
    country_iso: Mapped[str | None] = mapped_column(Text)

    level_code: Mapped[str | None] = mapped_column(Text)
    level_label: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    # Named parts as the issuer divides them (entry-requirements, safety-and-security,
    # health, …). Kept as a map rather than flattened so the section headings stay theirs.
    sections: Mapped[dict | None] = mapped_column(JSONB)

    url: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # sha256 of the advisory's content. Re-ingesting an unchanged sheet is a no-op —
    # otherwise a 6-hourly poll would write 4 identical rows a day per country and the
    # history above would become unreadable.
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("authority", "country", "content_hash",
                         name="uq_advisories_authority_country_hash"),
        Index("ix_advisories_current", "country_iso", "is_current"),
        Index("ix_advisories_authority", "authority", "is_current"),
    )
