"""Multi-INT: int_discipline column on narrative_events (idempotent + backfill)

Revision ID: 012
Revises: 011
Create Date: 2026-07-15 00:00:00.000000

Phase 2a (multi-INT fusion): every event carries an intelligence-discipline tag
(HUMINT/SIGINT/IMINT/GEOINT/MASINT/FININT/CYBINT), derived deterministically from
(source, category). New rows are tagged at ingest by backend.taxonomy.discipline_for;
this migration adds the column + index and backfills existing rows.

The backfill CASE is GENERATED FROM backend/taxonomy.py at migration time (not
hand-written SQL), so it mirrors discipline_for exactly — source precedence,
case-insensitive — and can never drift from the app's tagging logic.

ADD COLUMN / CREATE INDEX IF NOT EXISTS keeps this safe to re-run and self-healing
against alembic-version drift (same posture as 008-011). NULL is read as "untagged"
by the app, so an un-migrated row behaves as before.
"""
from typing import Sequence, Union

from alembic import op

from backend import taxonomy

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _in_clause(keys: Sequence[str]) -> str:
    return ", ".join("'" + k.replace("'", "''") + "'" for k in sorted(set(keys)))


def _when_clauses(col: str, mapping: dict[str, str]) -> list[str]:
    """One WHEN per discipline: lower(col) IN (its keys) THEN 'DISCIPLINE'."""
    by_disc: dict[str, list[str]] = {}
    for key, disc in mapping.items():
        by_disc.setdefault(disc, []).append(key.lower())
    return [
        f"    WHEN lower({col}) IN ({_in_clause(keys)}) THEN '{disc}'"
        for disc, keys in by_disc.items()
    ]


def upgrade() -> None:
    op.execute("ALTER TABLE narrative_events ADD COLUMN IF NOT EXISTS int_discipline TEXT")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_narrative_events_int_discipline "
        "ON narrative_events (int_discipline)"
    )
    # Source precedence first (evaluated top-down), then category, then default —
    # identical to taxonomy.discipline_for.
    whens = (
        _when_clauses("source", taxonomy.SOURCE_DISCIPLINE)
        + _when_clauses("category", taxonomy.CATEGORY_DISCIPLINE)
    )
    op.execute(
        "UPDATE narrative_events SET int_discipline = CASE\n"
        + "\n".join(whens)
        + f"\n    ELSE '{taxonomy.DEFAULT_DISCIPLINE}'\n  END\n"
        "WHERE int_discipline IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_narrative_events_int_discipline")
    op.execute("ALTER TABLE narrative_events DROP COLUMN IF EXISTS int_discipline")
