"""Advice library: ingested government travel advisories

Revision ID: 019
Revises: 018
Create Date: 2026-07-26 00:00:00.000000

The incumbent ships ~143 advice sheets (Entry-Exit, Pre-Departure, On Arrival, In
Transit) written by a research desk. We do not have one, and this table is the
alternative to pretending we do: every sheet is fetched from a named government,
stored with its own level vocabulary, its publication date and a link back to the
original. We author nothing.

Verified keyless and reachable before building: the US State Department advisory RSS
(213 countries) and the UK FCDO's GOV.UK content API (one JSON document per country,
six named parts).

🔴 There is deliberately NO normalised numeric risk column. State's Level 1-4 and the
FCDO's alert statuses are different instruments from different governments; blending
them into one score would invent a precision neither claims, and a customer acting on
that number would believe two governments agreed when they had never been asked the
same question. Each row keeps its issuer's own words.

History is retained rather than overwritten — ``is_current`` marks the latest sheet
per (authority, country) and superseded rows stay. "What did the FCDO say at the time
we sent our people there?" is a question a duty-of-care team must be able to answer
afterwards, and an UPDATE in place destroys the only evidence of it.

``content_hash`` in the unique key makes re-ingest a no-op: a 6-hourly poll would
otherwise write four identical rows per country per day and bury that history.

All DDL is CREATE ... IF NOT EXISTS so the migration is re-runnable and self-heals
against alembic-version drift (same posture as 008-018).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS advisories (
            id UUID PRIMARY KEY,
            authority TEXT NOT NULL,
            country TEXT NOT NULL,
            country_iso TEXT,
            level_code TEXT,
            level_label TEXT,
            summary TEXT,
            sections JSONB,
            url TEXT,
            published_at TIMESTAMPTZ,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            content_hash TEXT NOT NULL,
            is_current BOOLEAN NOT NULL DEFAULT TRUE,
            CONSTRAINT uq_advisories_authority_country_hash
                UNIQUE (authority, country, content_hash)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_advisories_current "
        "ON advisories (country_iso, is_current)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_advisories_authority "
        "ON advisories (authority, is_current)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_advisories_authority")
    op.execute("DROP INDEX IF EXISTS ix_advisories_current")
    op.execute("DROP TABLE IF EXISTS advisories")
