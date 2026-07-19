"""Benchmark forward prediction ledger: benchmark_ledger + benchmark_manifests

Revision ID: 014
Revises: 013
Create Date: 2026-07-19 00:00:00.000000

Phase 2 (benchmark program): the public, tamper-evident forward prediction ledger.
Each published forecast (a confident event_consequence_maps row) becomes a
benchmark_ledger entry with a write-once content_hash; a daily benchmark_manifests
row stores the root hash over that day's entries (also committed to git under
docs/benchmark/). Resolution fields on benchmark_ledger are backfilled by
outcome_worker when real later evidence grades the prediction.

CREATE TABLE / INDEX IF NOT EXISTS keeps this safe to re-run and self-healing
against alembic-version drift (same posture as 008-013).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_ledger (
            id UUID PRIMARY KEY,
            consequence_map_id UUID NOT NULL UNIQUE REFERENCES event_consequence_maps(id),
            question_text TEXT NOT NULL,
            prediction_score INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            content_hash TEXT NOT NULL UNIQUE,
            manifest_date DATE NOT NULL,
            published_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            outcome TEXT,
            observed_probability DOUBLE PRECISION,
            brier_score DOUBLE PRECISION,
            resolved_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_ledger_manifest_date "
        "ON benchmark_ledger (manifest_date)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_ledger_resolved_at "
        "ON benchmark_ledger (resolved_at)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_manifests (
            id UUID PRIMARY KEY,
            manifest_date DATE NOT NULL UNIQUE,
            root_hash TEXT NOT NULL,
            entry_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS benchmark_manifests")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_ledger_resolved_at")
    op.execute("DROP INDEX IF EXISTS ix_benchmark_ledger_manifest_date")
    op.execute("DROP TABLE IF EXISTS benchmark_ledger")
