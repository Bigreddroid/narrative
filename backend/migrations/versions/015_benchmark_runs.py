"""Benchmark scoreboard cache: benchmark_runs

Revision ID: 015
Revises: 014
Create Date: 2026-07-19 00:00:00.000000

Phase 3 (benchmark program): a cache table for the public /benchmark/score board.
A scheduled worker (backend/workers/benchmark_worker) computes the expensive
numbers (real Autocast crowd Brier + ledger auto-publish + gated engine skill)
once per cadence and writes one benchmark_runs row; the endpoint serves the
latest row with zero request-time compute or network. Because the row lives in
Postgres (not the /tmp Autocast cache), the real number survives a container
`--force-recreate`.

The full /score payload is stored in `payload` (JSONB) so the API cannot drift
from the CLI/CI shape; the flat columns are for observability. engine_bss is NULL
unless engine_gate_met (n>=20 resolved forecasts) - the n>=20 honesty gate.

CREATE TABLE / INDEX IF NOT EXISTS keeps this safe to re-run and self-healing
against alembic-version drift (same posture as 008-014).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS benchmark_runs (
            id UUID PRIMARY KEY,
            run_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'ok',
            synthetic_passed INTEGER,
            synthetic_total INTEGER,
            autocast_source TEXT,
            autocast_n INTEGER,
            autocast_brier DOUBLE PRECISION,
            autocast_bss DOUBLE PRECISION,
            ledger_published INTEGER,
            ledger_root_hash TEXT,
            ledger_entry_count INTEGER,
            engine_n INTEGER,
            engine_bss DOUBLE PRECISION,
            engine_gate_met BOOLEAN NOT NULL DEFAULT FALSE,
            payload JSONB,
            duration_seconds DOUBLE PRECISION
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_benchmark_runs_run_at "
        "ON benchmark_runs (run_at)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_benchmark_runs_run_at")
    op.execute("DROP TABLE IF EXISTS benchmark_runs")
