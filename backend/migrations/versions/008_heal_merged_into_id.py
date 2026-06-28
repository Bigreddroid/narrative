"""Heal merged_into_id on narrative_events (idempotent)

Revision ID: 008
Revises: 007
Create Date: 2026-06-28 18:00:00.000000

Production's alembic_version was stamped at 007 but the merged_into_id column was
never actually created, so `alembic upgrade head` was a no-op and every query that
filters `merged_into_id IS NULL` (events / feed / search) hit a 500. This migration
re-asserts the column, FK, and partial index using IF NOT EXISTS / guarded DDL, so
it is safe whether or not 007 truly applied. Idempotent and self-healing.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Column — plain ADD COLUMN IF NOT EXISTS (Postgres native, idempotent).
    op.execute(
        "ALTER TABLE narrative_events "
        "ADD COLUMN IF NOT EXISTS merged_into_id UUID"
    )
    # FK — guarded so re-runs don't error if it already exists.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'fk_narrative_events_merged_into'
            ) THEN
                ALTER TABLE narrative_events
                    ADD CONSTRAINT fk_narrative_events_merged_into
                    FOREIGN KEY (merged_into_id)
                    REFERENCES narrative_events (id)
                    ON DELETE SET NULL;
            END IF;
        END $$;
        """
    )
    # Partial index used by feed/map queries.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_narrative_events_not_merged "
        "ON narrative_events (id) WHERE merged_into_id IS NULL"
    )


def downgrade() -> None:
    # 007 owns the real teardown; nothing to undo here.
    pass
