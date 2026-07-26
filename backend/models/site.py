import uuid
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, Text, DateTime, ForeignKey, func, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Site(Base):
    """One physical location a customer is responsible for — the join key of the product.

    Every per-site number a security platform produces hangs off this row, so a defect
    here propagates into figures that reach a board. That is not hypothetical: the
    incumbent register observed in production carries the same identifier on two rows
    with different countries, and another row with no country at all.

    Field names mirror ``web/src/data/customers/wipro.exec.sample.js`` exactly
    (``id, name, city, country, lat, lng, type, criticality, headcount``) so the
    executive deck's pure libs — ``officeContext``, ``execPosture``, ``registryAudit``,
    ``domainScore`` — keep working when the fixture is swapped for this table.
    That fixture's own header states the rule: MOCK THE DATA, NEVER THE SHAPE.
    """
    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )

    # The customer's OWN identifier (e.g. "AFR08"), carried through from their register.
    # Deliberately NOT unique: a real register can repeat one, and we must be able to
    # store and REPORT that defect rather than reject the import. The audit surfaces it;
    # a 409 would just hide it and leave the customer believing their data is clean.
    external_id: Mapped[str | None] = mapped_column(Text)

    name: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(Text)
    lat: Mapped[float | None] = mapped_column(Float)
    lng: Mapped[float | None] = mapped_column(Float)

    # campus | office | delivery | datacentre | vendor
    type: Mapped[str] = mapped_column(Text, nullable=False, default="office")
    # tier-1 | tier-2 | tier-3
    criticality: Mapped[str] = mapped_column(Text, nullable=False, default="tier-3")

    # Nullable on purpose. A site with no headcount cannot be counted in exposure, and
    # the audit flags it as such — which is more useful than defaulting it to 0 and
    # silently under-reporting the people at risk.
    headcount: Mapped[int | None] = mapped_column(Integer)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # There is no repo-wide updated_at convention, but a register is edited and
    # re-imported, and "last updated" is a thing the buyer reads off the screen.
    # Follows the AppConfig precedent (the only other mutable row in the schema).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_sites_org", "org_id", "is_active"),
        Index("ix_sites_org_external", "org_id", "external_id"),
        Index("ix_sites_country", "org_id", "country"),
    )
