import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, Float, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Person(Base):
    """An employee the customer owes a duty of care to.

    Counted in people rather than events on purpose: duty-of-care liability attaches
    to people, so "how many of ours are exposed" is the question the board actually asks.
    """
    __tablename__ = "people"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)
    home_site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_people_org", "org_id", "is_active"),
        Index("ix_people_home_site", "home_site_id"),
    )


class Trip(Base):
    """One traveller itinerary — a person temporarily somewhere other than their home site.

    ``to_site_id`` is the real join to a location; ``to_city`` is display text.

    🔴 The deck currently matches travellers to sites with string equality on the city
    NAME (``trip.to === office.city`` in ExecDeck). That works only because both sides
    come from the same fixture. Once trips carry a real ``to_site_id``, the deck must
    join on the id — otherwise the site-detail traveller panel goes quietly empty while
    every other number on the page still looks right.

    ``to_site_id`` is nullable because people travel to cities where the customer has no
    site, and those trips still need to be tracked; ``to_lat``/``to_lng`` carry the
    position in that case.
    """
    __tablename__ = "trips"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id"), nullable=False
    )

    from_site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    to_site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sites.id"))
    to_city: Mapped[str | None] = mapped_column(Text)
    to_country: Mapped[str | None] = mapped_column(Text)
    to_lat: Mapped[float | None] = mapped_column(Float)
    to_lng: Mapped[float | None] = mapped_column(Float)

    depart_date: Mapped[date | None] = mapped_column(Date)
    return_date: Mapped[date | None] = mapped_column(Date)

    # Null means never checked in. travelPosture() treats a stale or absent check-in as
    # "unaccounted for", which is the state a GSOC actually acts on.
    last_check_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_trips_org_dates", "org_id", "depart_date", "return_date"),
        Index("ix_trips_person", "person_id"),
        Index("ix_trips_to_site", "to_site_id"),
    )
