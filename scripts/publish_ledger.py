"""
PUBLISH the forward prediction ledger (Phase 2 of the benchmark program).

Reads confident, ungraded forecasts (event_consequence_maps with
prediction_score >= 60 - the same bar outcome_worker grades at) and publishes each
as a tamper-evident benchmark_ledger entry: a write-once content_hash committing to
(question, score, created_at) BEFORE the outcome is known. It then (re)computes the
day's benchmark_manifests root over all entries published that day and writes the
git-committable anchor docs/benchmark/manifest-YYYY-MM-DD.txt.

Why this is the CLEAN engine benchmark: the forecast is hashed + committed now and
graded later by outcome_worker against evidence that did not exist yet - so a good
resolved Brier cannot be hindsight. Engine skill (BSS over resolved entries) is
still gated at n>=20; this script only publishes + hashes, it never scores skill.

Idempotent: entries are keyed by consequence_map_id (UNIQUE), so re-running never
duplicates. Re-running the same day recomputes an identical manifest root (the root
is order-independent over the day's hash SET).

Usage:
    python -m scripts.publish_ledger                 # publish new forecasts
    python -m scripts.publish_ledger --dry-run       # report only, no DB write
    python -m scripts.publish_ledger --limit 500     # cap per run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.models.benchmark_ledger import (  # noqa: E402
    compute_content_hash,
    compute_root_hash,
)

# Same confidence bar outcome_worker uses - only forecasts we'd actually grade.
MIN_PREDICTION_SCORE = 60

_DOCS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "benchmark"
)


def _asyncpg_dsn() -> str:
    # Mirror backfill_prediction_outcomes: accept either scheme, hand asyncpg a plain DSN.
    url = os.environ.get("DATABASE_URL", "postgresql://narrative:narrative@localhost:5432/narrative")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")


def build_entries(rows: list[dict], manifest_date) -> list[dict]:
    """Pure: turn raw map rows into insertable ledger entries with content hashes.

    Kept pure (no DB) so the hashing is unit-testable in isolation.
    """
    entries = []
    for r in rows:
        qtext = r["question_text"] or ""
        score = int(r["prediction_score"])
        created = r["created_at"]
        entries.append({
            "id": uuid.uuid4(),
            "consequence_map_id": r["consequence_map_id"],
            "question_text": qtext,
            "prediction_score": score,
            "created_at": created,
            "content_hash": compute_content_hash(qtext, score, created),
            "manifest_date": manifest_date,
        })
    return entries


def manifest_file_text(manifest_date, root_hash: str, hashes: list[str]) -> str:
    """The git-committable manifest anchor - the external non-repudiation record."""
    lines = [
        "# Narrative benchmark manifest (forward prediction ledger)",
        f"# date: {manifest_date.isoformat()}",
        f"# root_hash: {root_hash}",
        f"# entry_count: {len(hashes)}",
        "# Each line below is a published forecast's content_hash (sha256), sorted.",
        "# root_hash = sha256 of the sorted hashes concatenated. Recompute to verify.",
    ]
    lines.extend(sorted(hashes))
    return "\n".join(lines) + "\n"


def write_manifest_file(manifest_date, root_hash: str, hashes: list[str]) -> str:
    os.makedirs(_DOCS_DIR, exist_ok=True)
    path = os.path.join(_DOCS_DIR, f"manifest-{manifest_date.isoformat()}.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(manifest_file_text(manifest_date, root_hash, hashes))
    return path


async def _fetch_unpublished(conn, limit: int) -> list[dict]:
    sql = """
        SELECT m.id AS consequence_map_id, m.created_at, m.prediction_score,
               e.canonical_title AS question_text
        FROM event_consequence_maps m
        JOIN narrative_events e ON e.id = m.narrative_event_id
        LEFT JOIN benchmark_ledger l ON l.consequence_map_id = m.id
        WHERE m.prediction_score IS NOT NULL
          AND m.prediction_score >= $1
          AND l.id IS NULL
        ORDER BY m.created_at ASC
        LIMIT $2
    """
    return [dict(r) for r in await conn.fetch(sql, MIN_PREDICTION_SCORE, limit)]


async def _run(limit: int, dry_run: bool) -> dict:
    import asyncpg  # lazy - keeps the pure helpers importable without the driver

    manifest_date = datetime.now(timezone.utc).date()
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        raw = await _fetch_unpublished(conn, limit)
        entries = build_entries(raw, manifest_date)

        if dry_run:
            return {"new_entries": len(entries), "manifest_date": manifest_date,
                    "dry_run": True}

        for e in entries:
            # ON CONFLICT keeps a concurrent/duplicate run from erroring.
            await conn.execute(
                """
                INSERT INTO benchmark_ledger
                    (id, consequence_map_id, question_text, prediction_score,
                     created_at, content_hash, manifest_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (consequence_map_id) DO NOTHING
                """,
                e["id"], e["consequence_map_id"], e["question_text"],
                e["prediction_score"], e["created_at"], e["content_hash"],
                e["manifest_date"],
            )

        # Recompute today's manifest over ALL entries stamped with this date
        # (idempotent: root depends only on the hash set).
        day_rows = await conn.fetch(
            "SELECT content_hash FROM benchmark_ledger WHERE manifest_date = $1",
            manifest_date,
        )
        hashes = [r["content_hash"] for r in day_rows]
        root = compute_root_hash(hashes)
        await conn.execute(
            """
            INSERT INTO benchmark_manifests (id, manifest_date, root_hash, entry_count)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (manifest_date)
            DO UPDATE SET root_hash = EXCLUDED.root_hash,
                          entry_count = EXCLUDED.entry_count
            """,
            uuid.uuid4(), manifest_date, root, len(hashes),
        )
        path = write_manifest_file(manifest_date, root, hashes)
        return {"new_entries": len(entries), "manifest_date": manifest_date,
                "root_hash": root, "entry_count": len(hashes), "manifest_file": path,
                "dry_run": False}
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish the forward prediction ledger.")
    ap.add_argument("--limit", type=int, default=1000, help="max forecasts to publish this run")
    ap.add_argument("--dry-run", action="store_true", help="report only, no DB write")
    args = ap.parse_args()

    res = asyncio.run(_run(args.limit, args.dry_run))
    if res.get("dry_run"):
        print(f"[dry-run] {res['new_entries']} new forecasts would publish "
              f"into manifest {res['manifest_date']}. No DB write.")
        return
    print(f"published {res['new_entries']} new forecast(s).")
    print(f"manifest {res['manifest_date']}: root {res['root_hash'][:16]}... "
          f"over {res['entry_count']} entries")
    print(f"anchor written: {res['manifest_file']}")


if __name__ == "__main__":
    main()
