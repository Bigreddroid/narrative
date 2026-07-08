"""OSINT triage-decision flywheel table (idempotent)

Revision ID: 009
Revises: 008
Create Date: 2026-06-30 19:00:00.000000

Records every OSINT post the triage agent judged — kept OR dropped — with the
reason, so the rejection funnel (normally invisible: triage returns None and the
post vanishes) becomes observable and tunable, and accumulates as labelled data.

Created with IF NOT EXISTS / guarded DDL so it is safe to re-run and self-heals
against alembic-version drift, the same posture as 008.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS osint_triage_decisions (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            external_id TEXT NOT NULL,
            source      TEXT NOT NULL,
            kept        BOOLEAN NOT NULL,
            reason      TEXT NOT NULL,
            method      TEXT NOT NULL,
            category    TEXT,
            confidence  DOUBLE PRECISION,
            importance  INTEGER,
            title       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    # Read paths: recent decisions by source, and keep/drop-reason rollups.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_osint_triage_source_created "
        "ON osint_triage_decisions (source, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_osint_triage_kept_reason "
        "ON osint_triage_decisions (kept, reason)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS osint_triage_decisions")
