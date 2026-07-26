import uuid
from datetime import datetime

from sqlalchemy import Boolean, Integer, Text, DateTime, ForeignKey, func, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class AlertSubscription(Base):
    """Who wants to hear about what, how often, and through which channel.

    Replaces the inert JSONB preferences on ``User.notification_preferences``. That
    field is written by the Settings page and read by NOTHING — the toggle labelled
    "Periodic summary of high-impact consequences" has never sent an email. A promise
    on screen that no code keeps is worse than an absent feature, because the customer
    stops checking.

    Org-scoped rather than user-scoped: a GSOC subscribes a distribution list to a
    country, and individuals come and go from it.
    """
    __tablename__ = "alert_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    # Exactly one of user_id / list_id is set: a subscription belongs either to one
    # person or to a named group. Enforced in the route, since a CHECK constraint on
    # "exactly one of" is awkward to evolve.
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    list_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("distribution_lists.id")
    )

    channel: Mapped[str] = mapped_column(Text, nullable=False, default="email")   # email | push
    scope: Mapped[str] = mapped_column(Text, nullable=False, default="org")       # org|site|country
    scope_ref: Mapped[str | None] = mapped_column(Text)   # site id or country name; null for org

    # Bands come from web/src/lib/severity.js: minimal|low|moderate|high|extreme.
    min_severity: Mapped[str] = mapped_column(Text, nullable=False, default="high")
    cadence: Mapped[str] = mapped_column(Text, nullable=False, default="daily")   # daily|weekly

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_alert_subs_org", "org_id", "is_active"),
        Index("ix_alert_subs_cadence", "cadence", "is_active"),
    )


class DistributionList(Base):
    """A named group of recipients — the "distro list" a security team actually uses."""
    __tablename__ = "distribution_lists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("org_id", "name", name="uq_distribution_lists_org_name"),
    )


class DistributionMember(Base):
    """One recipient on a list.

    ``email`` is stored on the row rather than joined from ``users``: the people a
    GSOC alerts are frequently not platform users at all (a site's local security
    lead, a regional HR contact), and requiring an account before they can be warned
    about an incident would be the wrong constraint entirely.
    """
    __tablename__ = "distribution_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    list_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("distribution_lists.id"), nullable=False
    )
    email: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str | None] = mapped_column(Text)
    # Set when the recipient unsubscribes. Never deleted: we must be able to prove we
    # stopped, and a deleted row cannot prove anything.
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("list_id", "email", name="uq_distribution_members_list_email"),
        Index("ix_distribution_members_list", "list_id", "is_active"),
    )


class Delivery(Base):
    """One attempt to deliver one digest to one recipient — the audit trail of sending.

    ``dedup_key`` is the whole design, and it is UNIQUE in the database. The existing
    push path (``alert_worker.py:116-124``) has no dedup key and looks back 35 minutes
    on a 10-minute interval, so the same (user, event) re-sends for about 35 minutes.
    That is survivable for a phone notification and unacceptable for email: the
    observed incumbent inbox held 9,189 messages, and the fastest way to become the
    thing security teams filter to a folder is to send the same digest four times.

    The key is sha256(subscription | window | content root), so a worker that runs
    three times in a window produces exactly one row per recipient. Following the
    ledger's discipline (``scripts/publish_ledger.py``), not the alert worker's.

    A failure is RECORDED, with its error, rather than swallowed the way
    ``cost_alert.py:46-47`` swallows one. "We sent it" and "we tried and SMTP refused"
    must be distinguishable afterwards, or the log is decoration.
    """
    __tablename__ = "deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False
    )
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alert_subscriptions.id")
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False, default="email")
    recipient: Mapped[str] = mapped_column(Text, nullable=False)

    dedup_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content_hash: Mapped[str | None] = mapped_column(Text)
    subject: Mapped[str | None] = mapped_column(Text)
    item_count: Mapped[int] = mapped_column(Integer, default=0)

    # queued | sent | failed | suppressed
    #   suppressed = we deliberately did not send (sending disabled, or unsubscribed).
    #   It is a distinct state from failed on purpose: one is our choice, the other is
    #   a fault, and conflating them makes the log useless for answering "why didn't
    #   they get it?".
    status: Mapped[str] = mapped_column(Text, nullable=False, default="queued")
    error: Mapped[str | None] = mapped_column(Text)

    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_deliveries_org_queued", "org_id", "queued_at"),
        Index("ix_deliveries_status", "status"),
    )
