"""Runtime config overrides table (idempotent)

Revision ID: 010
Revises: 009
Create Date: 2026-07-02 00:00:00.000000

Backs the admin Settings panel: a small key/value store so llm_provider /
osint_source / osint_rss_enabled can be flipped at runtime instead of only via
env + redeploy. A missing row means "use the env default", so this table being
empty is behaviourally identical to before it existed.

Created with IF NOT EXISTS / guarded DDL so it is safe to re-run and self-heals
against alembic-version drift, the same posture as 008/009.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS app_config (
            key        TEXT PRIMARY KEY,
            value      JSONB NOT NULL,
            updated_by TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_config")
