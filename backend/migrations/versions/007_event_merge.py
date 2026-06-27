"""Event dedup — merged_into_id self-reference on narrative_events

Revision ID: 007
Revises: 006
Create Date: 2026-06-27 00:00:00.000000

Near-duplicate events (e.g. many GDELT docs about the same story) are merged into
a canonical event: the duplicates keep their row but point at the canonical via
merged_into_id, and every feed/map query filters them out. Reversible — clearing
the column "un-merges" them.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "narrative_events",
        sa.Column("merged_into_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_narrative_events_merged_into",
        "narrative_events", "narrative_events",
        ["merged_into_id"], ["id"],
        ondelete="SET NULL",
    )
    # Feed/map queries filter `merged_into_id IS NULL`; a partial index keeps that fast.
    op.create_index(
        "ix_narrative_events_not_merged",
        "narrative_events", ["id"],
        postgresql_where=sa.text("merged_into_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_narrative_events_not_merged", table_name="narrative_events")
    op.drop_constraint("fk_narrative_events_merged_into", "narrative_events", type_="foreignkey")
    op.drop_column("narrative_events", "merged_into_id")
