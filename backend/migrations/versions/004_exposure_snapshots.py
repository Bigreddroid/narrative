"""Exposure snapshots — persisted Exposure-Index time series (temporal layer)

Revision ID: 004
Revises: 003
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "exposure_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("entity_key", sa.Text, nullable=False, server_default=""),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_exposure_snapshots_lookup", "exposure_snapshots", ["kind", "entity_key", "captured_at"])


def downgrade() -> None:
    op.drop_index("ix_exposure_snapshots_lookup", table_name="exposure_snapshots")
    op.drop_table("exposure_snapshots")
