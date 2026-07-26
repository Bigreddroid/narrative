"""Delivery: subscriptions, distribution lists, and a deduplicated delivery log

Revision ID: 018
Revises: 017
Create Date: 2026-07-26 00:00:00.000000

Nothing in this product has ever sent an email. The only mail code in the repo is
``backend/services/cost_alert.py`` (57 lines, admin cost alerts, blocking smtplib),
while ``web/src/pages/Settings.jsx`` shows users a toggle called "email digest" that
writes to a JSONB column no backend code reads. This migration is the schema behind
making that toggle true.

Tables:
  - distribution_lists / distribution_members
        Named recipient groups. A member's email lives on the row, NOT joined from
        users: the people a security team alerts are often not platform users at all
        (a site's local security lead, a regional HR contact), and requiring an
        account before someone can be warned about an incident is the wrong
        constraint. ``unsubscribed_at`` is set, never deleted — we must be able to
        prove we stopped, and a deleted row proves nothing.
  - alert_subscriptions
        Scope (org | site | country), minimum severity, cadence, channel. Belongs to
        either one user or one list.
  - deliveries
        One row per attempt, with a UNIQUE ``dedup_key``. This is the point of the
        table. The existing push path has no dedup key and a 35-minute lookback on a
        10-minute interval, so it re-sends the same alert for ~35 minutes; tolerable
        for a phone notification, fatal for email. The key is
        sha256(subscription | window | content root), so running the worker three
        times in one window still produces exactly one row per recipient.
        ``status`` distinguishes SUPPRESSED (we chose not to send) from FAILED (we
        tried and it broke) — conflating them makes the log useless for answering
        "why didn't they get it?".

All DDL is CREATE ... IF NOT EXISTS so the migration is re-runnable and self-heals
against alembic-version drift (same posture as 008-017). No data migration: existing
``users.notification_preferences`` is deliberately NOT backfilled into subscriptions,
because that column represents an intention users expressed to a control that never
worked. Silently turning it into real email to real people would be the worst possible
first use of this table.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_lists (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            name TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_distribution_lists_org_name UNIQUE (org_id, name)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS distribution_members (
            id UUID PRIMARY KEY,
            list_id UUID NOT NULL REFERENCES distribution_lists(id),
            email TEXT NOT NULL,
            name TEXT,
            unsubscribed_at TIMESTAMPTZ,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_distribution_members_list_email UNIQUE (list_id, email)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_distribution_members_list "
        "ON distribution_members (list_id, is_active)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS alert_subscriptions (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            user_id UUID REFERENCES users(id),
            list_id UUID REFERENCES distribution_lists(id),
            channel TEXT NOT NULL DEFAULT 'email',
            scope TEXT NOT NULL DEFAULT 'org',
            scope_ref TEXT,
            min_severity TEXT NOT NULL DEFAULT 'high',
            cadence TEXT NOT NULL DEFAULT 'daily',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alert_subs_org "
        "ON alert_subscriptions (org_id, is_active)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_alert_subs_cadence "
        "ON alert_subscriptions (cadence, is_active)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS deliveries (
            id UUID PRIMARY KEY,
            org_id UUID NOT NULL REFERENCES organizations(id),
            subscription_id UUID REFERENCES alert_subscriptions(id),
            channel TEXT NOT NULL DEFAULT 'email',
            recipient TEXT NOT NULL,
            dedup_key TEXT NOT NULL UNIQUE,
            content_hash TEXT,
            subject TEXT,
            item_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'queued',
            error TEXT,
            queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            sent_at TIMESTAMPTZ,
            opened_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_deliveries_org_queued "
        "ON deliveries (org_id, queued_at)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_deliveries_status ON deliveries (status)")


def downgrade() -> None:
    # Reverse dependency order.
    op.execute("DROP INDEX IF EXISTS ix_deliveries_status")
    op.execute("DROP INDEX IF EXISTS ix_deliveries_org_queued")
    op.execute("DROP TABLE IF EXISTS deliveries")

    op.execute("DROP INDEX IF EXISTS ix_alert_subs_cadence")
    op.execute("DROP INDEX IF EXISTS ix_alert_subs_org")
    op.execute("DROP TABLE IF EXISTS alert_subscriptions")

    op.execute("DROP INDEX IF EXISTS ix_distribution_members_list")
    op.execute("DROP TABLE IF EXISTS distribution_members")

    op.execute("DROP TABLE IF EXISTS distribution_lists")
