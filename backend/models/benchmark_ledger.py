"""
Public auditable forward prediction ledger (Phase 2 of the benchmark program).

The clean, leak-proof engine benchmark: a forecast made NOW, published + hashed
BEFORE its outcome is known, graded LATER. Because the content hash is written at
publication and rolled into a daily manifest root (also committed to git as
docs/benchmark/manifest-YYYY-MM-DD.txt), a third party can prove we did not
back-date or edit a prediction after seeing how it resolved.

Two tables:
  - LedgerEntry     one published forecast, keyed to its event_consequence_maps
                    row. created_at + content_hash are WRITE-ONCE; resolution
                    fields (outcome, brier_score, resolved_at) are backfilled by
                    outcome_worker when real later evidence grades it.
  - BenchmarkManifest  one row per publication day: the merkle-ish root over that
                    day's entry hashes, the audit anchor.

Honesty guardrail: engine skill (Brier Skill Score over resolved entries) is
STILL gated at calibration.MIN_CALIBRATION_POINTS (n>=20). This module only
publishes + hashes; it never emits a skill number below the gate.

The hash helpers below are PURE (no DB, no I/O) so they are unit-testable and so
the API, the publisher, and any external verifier all compute the identical hash
from the same canonical string.
"""
import hashlib
import uuid
from datetime import datetime

from sqlalchemy import Date, Float, ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


def canonical_created_at(created_at: datetime) -> str:
    """The canonical string form of a forecast's created_at used in the hash.

    Microsecond-precision ISO-8601. Kept identical between publish time and any
    later verification so the hash is reproducible; never reformat this casually.
    """
    return created_at.isoformat()


def compute_content_hash(question_text: str, prediction_score: int, created_at: datetime) -> str:
    """sha256 over 'question_text|prediction_score|created_at' - the per-entry commitment.

    This is the value published before resolution; recomputing it later from the
    same three fields must reproduce it exactly, which is the whole audit claim.
    """
    payload = f"{question_text}|{prediction_score}|{canonical_created_at(created_at)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_root_hash(entry_hashes: list[str]) -> str:
    """Deterministic root over a day's entry hashes (order-independent).

    Hashes are sorted before concatenation so the root depends only on the SET of
    entries, not the order they were inserted - two verifiers with the same rows
    always get the same root. Empty set -> sha256 of the empty string.
    """
    joined = "".join(sorted(entry_hashes))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


class LedgerEntry(Base):
    __tablename__ = "benchmark_ledger"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # One ledger entry per consequence map (unique) - re-publishing is idempotent.
    consequence_map_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("event_consequence_maps.id"), nullable=False, unique=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    prediction_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # Copied write-once from the consequence map - the immutable "forecast made at".
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    # The publication day this entry was rolled into (matches BenchmarkManifest.manifest_date).
    manifest_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Resolution fields - NULL until outcome_worker grades this via real later evidence.
    outcome: Mapped[str | None] = mapped_column(Text)                    # materialized/partial/failed
    observed_probability: Mapped[float | None] = mapped_column(Float)    # realised outcome in [0,1]
    brier_score: Mapped[float | None] = mapped_column(Float)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BenchmarkManifest(Base):
    __tablename__ = "benchmark_manifests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    manifest_date: Mapped[datetime] = mapped_column(Date, nullable=False, unique=True)
    root_hash: Mapped[str] = mapped_column(Text, nullable=False)
    entry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
