import uuid
from datetime import datetime

from sqlalchemy import Boolean, Text, DateTime, ForeignKey, func, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class Organization(Base):
    """A customer tenant — the owner of a site register, its people, and its subscriptions.

    Before this existed, ``user_id`` was the only scoping key in the entire backend,
    which made a shared register impossible: a GSOC is a team reading one asset list,
    not a set of individuals each following their own events.

    Flat by design. The incumbent this displaces offers "Wipro and Sub-Organizations",
    but nesting multiplies the cost of every permission check and every roll-up query,
    and no customer requirement for it has been observed. Add it when one appears.
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False, unique=True)   # url-safe key, e.g. "wipro"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OrgMember(Base):
    """Membership of a user in an organization, carrying that user's role.

    The role lives HERE and deliberately not on ``User.tier``. ``tier`` answers
    "what has this account paid for" (free / pro / intelligence / enterprise / admin)
    and is already overloaded as the platform-admin check in ``require_admin``.
    Role answers "what may this person do inside this customer" — a different question
    with a different lifecycle. Conflating them is very hard to unpick later.

    Soft-deleted via ``is_active``, matching ``UserFollow``.
    """
    __tablename__ = "org_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="viewer")  # admin | analyst | viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # One membership row per (org, user). Enforced in the DATABASE, not only in
        # route code: the existing join tables check for duplicates with a SELECT then
        # 409, which races under concurrent writes. A membership row grants access, so
        # it is the wrong place to be relaxed about it.
        UniqueConstraint("org_id", "user_id", name="uq_org_members_org_user"),
        Index("ix_org_members_user", "user_id", "is_active"),
    )
