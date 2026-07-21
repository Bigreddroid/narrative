"""Benchmark ledger: forward-mode EXTERNAL forecasts (Manifold/Metaculus)

Revision ID: 016
Revises: 015
Create Date: 2026-07-21 00:00:00.000000

Extends the forward prediction ledger so it can also carry forecasts the engine
makes on OUTSIDE open questions (e.g. Manifold markets) — forecast now, resolved
LATER by the source itself. These entries are leak-proof by construction (an open
question has no outcome to memorize) and accrue toward the n>=20 gate far faster
than the internal-news timeline, and each carries the market's crowd probability
at forecast time for an honest engine-vs-crowd comparison.

Changes (all self-healing / re-runnable, same posture as 014):
  - consequence_map_id -> NULLABLE. External forecasts have no consequence map.
    Postgres allows many NULLs under a UNIQUE column, so the existing internal
    one-entry-per-map uniqueness is preserved.
  - source          NOT NULL DEFAULT 'engine'  ('engine' | 'manifold' | ...).
  - external_ref, external_url, resolution_criteria, crowd_prob.
  - partial UNIQUE (source, external_ref) WHERE external_ref IS NOT NULL, so
    re-publishing the same external question is idempotent (DO NOTHING) without
    constraining the internal (external_ref IS NULL) rows.

content_hash stays over (question_text | prediction_score | created_at), so any
third party verifies external and internal entries identically against the same
committed manifest.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # consequence_map_id -> nullable (external forecasts have no map). NOT VALID/
    # DROP NOT NULL is idempotent; the UNIQUE constraint already there is kept.
    op.execute(
        "ALTER TABLE benchmark_ledger ALTER COLUMN consequence_map_id DROP NOT NULL"
    )
    # New columns, each ADD COLUMN IF NOT EXISTS so the migration self-heals.
    op.execute(
        "ALTER TABLE benchmark_ledger "
        "ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'engine'"
    )
    op.execute("ALTER TABLE benchmark_ledger ADD COLUMN IF NOT EXISTS external_ref TEXT")
    op.execute("ALTER TABLE benchmark_ledger ADD COLUMN IF NOT EXISTS external_url TEXT")
    op.execute(
        "ALTER TABLE benchmark_ledger ADD COLUMN IF NOT EXISTS resolution_criteria TEXT"
    )
    op.execute(
        "ALTER TABLE benchmark_ledger ADD COLUMN IF NOT EXISTS crowd_prob DOUBLE PRECISION"
    )
    # Idempotent re-publish key for external forecasts only (internal rows have a
    # NULL external_ref and are excluded from this partial index).
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_benchmark_ledger_source_external_ref "
        "ON benchmark_ledger (source, external_ref) WHERE external_ref IS NOT NULL"
    )
    # Skill queries filter/group by source.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_ledger_source "
        "ON benchmark_ledger (source)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_benchmark_ledger_source")
    op.execute("DROP INDEX IF EXISTS ux_benchmark_ledger_source_external_ref")
    op.execute("ALTER TABLE benchmark_ledger DROP COLUMN IF EXISTS crowd_prob")
    op.execute("ALTER TABLE benchmark_ledger DROP COLUMN IF EXISTS resolution_criteria")
    op.execute("ALTER TABLE benchmark_ledger DROP COLUMN IF EXISTS external_url")
    op.execute("ALTER TABLE benchmark_ledger DROP COLUMN IF EXISTS external_ref")
    op.execute("ALTER TABLE benchmark_ledger DROP COLUMN IF EXISTS source")
    # Leave consequence_map_id nullable on downgrade: re-adding NOT NULL would fail
    # if any external (NULL) rows exist. The UNIQUE constraint is untouched.
