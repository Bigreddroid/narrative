"""
Cached benchmark scoreboard run (Phase 3 of the benchmark program).

The public /benchmark/score endpoint used to compute its numbers at REQUEST time:
synthetic controls (cheap, pure) plus a real Autocast crowd Brier read from a
temp-dir cache that is wiped on `docker compose up --force-recreate` and must be
hand-warmed. This table lets a scheduled worker (backend/workers/benchmark_worker)
compute the expensive numbers ONCE per cadence and persist them in Postgres, so:

  - the number survives container recreate (it is not in /tmp), and
  - the endpoint serves a cached row with zero request-time compute or network.

The full scoreboard payload (scripts.benchmark_score.as_dict) is stored verbatim
in `payload` so the API can never drift from the CLI/CI shape; the flat columns
alongside it are for observability and cheap querying.

Honesty guardrail: `engine_bss` is NULL unless `engine_gate_met` is true (n>=20
resolved forward forecasts). The worker never writes a skill number below the
gate - the same refusal the /engine-skill endpoint and backtest_cpe.py hold.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # "ok" when the real Autocast number was computed; "error" when the run fell
    # back to the labeled selftest fixture (honest degradation, never fabricated).
    status: Mapped[str] = mapped_column(Text, nullable=False, default="ok")

    # Proof A - synthetic controls (deterministic).
    synthetic_passed: Mapped[int | None] = mapped_column(Integer)
    synthetic_total: Mapped[int | None] = mapped_column(Integer)

    # Proof B - external crowd bar (Autocast). source = "real" | "selftest".
    autocast_source: Mapped[str | None] = mapped_column(Text)
    autocast_n: Mapped[int | None] = mapped_column(Integer)
    autocast_brier: Mapped[float | None] = mapped_column(Float)
    autocast_bss: Mapped[float | None] = mapped_column(Float)

    # Forward ledger auto-publish results for this run.
    ledger_published: Mapped[int | None] = mapped_column(Integer)
    ledger_root_hash: Mapped[str | None] = mapped_column(Text)
    ledger_entry_count: Mapped[int | None] = mapped_column(Integer)

    # Engine skill over RESOLVED ledger forecasts - GATED at n>=20.
    engine_n: Mapped[int | None] = mapped_column(Integer)
    engine_bss: Mapped[float | None] = mapped_column(Float)   # NULL unless engine_gate_met
    engine_gate_met: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # The full /score payload (as_dict shape) - served verbatim so it cannot drift.
    payload: Mapped[dict | None] = mapped_column(JSONB)

    duration_seconds: Mapped[float | None] = mapped_column(Float)
