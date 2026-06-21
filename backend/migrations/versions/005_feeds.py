"""Free-feed provenance on events + market snapshots

Revision ID: 005
Revises: 004
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("narrative_events", sa.Column("source", sa.Text(), nullable=True))
    op.add_column("narrative_events", sa.Column("external_id", sa.Text(), nullable=True))
    op.create_index(
        "ux_narrative_events_source_external",
        "narrative_events", ["source", "external_id"], unique=True,
        postgresql_where=sa.text("external_id IS NOT NULL"),
    )

    op.create_table(
        "market_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("symbol", sa.Text, nullable=False),
        sa.Column("label", sa.Text),
        sa.Column("sector", sa.Text),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("change_pct", sa.Float),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_market_snapshots_lookup", "market_snapshots", ["symbol", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_market_snapshots_lookup", table_name="market_snapshots")
    op.drop_table("market_snapshots")
    op.drop_index("ux_narrative_events_source_external", table_name="narrative_events")
    op.drop_column("narrative_events", "external_id")
    op.drop_column("narrative_events", "source")
