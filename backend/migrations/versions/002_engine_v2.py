"""Engine v2 — directed/explainable connections + richer prediction outcomes

Revision ID: 002
Revises: 001
Create Date: 2026-06-18 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Priority 2 — directed/temporal + explainable connection weights.
    op.add_column("event_connections", sa.Column("direction", sa.Text(), nullable=True))
    op.add_column("event_connections", sa.Column("weight_breakdown", postgresql.JSONB(), nullable=True))

    # Priority 7 — real prediction calibration metrics (infra now, pays off on data).
    op.add_column("prediction_outcomes", sa.Column("brier_score", sa.Float(), nullable=True))
    op.add_column("prediction_outcomes", sa.Column("log_loss", sa.Float(), nullable=True))
    op.add_column("prediction_outcomes", sa.Column("observed_probability", sa.Float(), nullable=True))
    op.add_column("prediction_outcomes", sa.Column("outcome_label", sa.Float(), nullable=True))
    op.add_column("prediction_outcomes", sa.Column("evidence", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("prediction_outcomes", "evidence")
    op.drop_column("prediction_outcomes", "outcome_label")
    op.drop_column("prediction_outcomes", "observed_probability")
    op.drop_column("prediction_outcomes", "log_loss")
    op.drop_column("prediction_outcomes", "brier_score")
    op.drop_column("event_connections", "weight_breakdown")
    op.drop_column("event_connections", "direction")
