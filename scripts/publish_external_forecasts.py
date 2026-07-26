"""
PUBLISH forward-mode EXTERNAL forecasts (forward ledger, external source).

The clean, FAST, leak-proof engine benchmark. We pull OPEN binary questions from
an outside source (Manifold — keyless), have the engine forecast each one NOW,
and publish it as a tamper-evident benchmark_ledger entry (source='manifold')
with a write-once content_hash committing to (question, score, created_at) BEFORE
the outcome is known. The SOURCE resolves the question later; external_resolution_worker
backfills the outcome, and /engine-skill scores it — gated at n>=20 per source.

Why this beats the internal ledger for a first honest skill number:
  * Leak-proof BY CONSTRUCTION — an open question has no outcome to memorize.
  * Short-horizon Manifold markets resolve in hours/days, so the external bucket
    can reach the n>=20 gate far sooner than the internal-news timeline.
  * Each market ships a crowd probability at forecast time -> an honest
    "engine vs the market" comparison (never blended into one hero number).

Honesty guardrails (same as publish_ledger / the whole program):
  * The QUALITY FILTER is load-bearing (min traders/volume, short horizon) — see
    external_benchmark.parse_manifold_open_markets. Without it we forecast noise.
  * Idempotent on (source, external_ref): re-running never duplicates or re-dates.
  * LLM is local-only, so this runs on the local Docker stack (same host as the
    accrual gate). --dry-run does NO LLM call; a real run that gets no forecast
    (LLM down) publishes nothing rather than fabricating.
  * Engine skill is STILL withheld below n>=20; this script only publishes + hashes.

Usage:
    python -m scripts.publish_external_forecasts --dry-run --limit 5 --horizon-days 3
    python -m scripts.publish_external_forecasts --limit 20 --min-traders 20
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
from scripts import external_benchmark as eb  # noqa: E402
from scripts.publish_ledger import (  # noqa: E402  (reuse the manifest spine verbatim)
    _asyncpg_dsn,
    manifest_file_text,
    write_manifest_file,
)

SOURCE = "manifold"


def engine_forecaster(question_text: str, background: str) -> int | None:
    """Real forecaster: one local-LLM call -> integer probability 0-100, or None.

    Returns None (skip, never fabricate) if the model can't produce a usable
    forecast — the same posture forecast_binary + the harness already hold.
    """
    from backend.consequence_engine import consensus_mapper
    try:
        out = consensus_mapper.forecast_binary(question_text, background or "")
    except Exception:
        return None
    p = out.get("probability")
    try:
        return int(round(float(p)))
    except (TypeError, ValueError):
        return None


def build_external_entries(records: list[dict], forecaster, manifest_date,
                           *, created_at: datetime | None = None) -> list[dict]:
    """Pure-ish: forecast each open record -> insertable ledger entries.

    `forecaster(question_text, background) -> int|None` is injected so this is
    unit-testable with a stub (no LLM, no network). Records the engine can't score
    are skipped. content_hash commits to (question, score, created_at) exactly as
    the internal ledger does, so a third party verifies both identically.
    """
    created_at = created_at or datetime.now(timezone.utc)
    entries = []
    for r in records:
        qtext = (r.get("question_text") or "").strip()
        if not qtext:
            continue
        score = forecaster(qtext, r.get("background", ""))
        if score is None:
            continue
        score = max(0, min(100, int(score)))
        cp = r.get("crowd_prob")
        entries.append({
            "id": uuid.uuid4(),
            "source": r.get("source", SOURCE),
            "external_ref": r.get("external_ref"),
            "external_url": r.get("external_url"),
            "resolution_criteria": r.get("resolution_criteria"),
            "crowd_prob": float(cp) if cp is not None else None,
            "question_text": qtext,
            "prediction_score": score,
            "created_at": created_at,
            "content_hash": compute_content_hash(qtext, score, created_at),
            "manifest_date": manifest_date,
        })
    return entries


async def _run(limit: int, dry_run: bool, max_fetch: int, filters: dict) -> dict:
    manifest_date = datetime.now(timezone.utc).date()

    # Fetch + quality-filter OPEN questions (keyless, no LLM yet).
    records = eb.manifold_open_adapter(max_fetch=max_fetch, **filters)
    if limit:
        records = records[:limit]

    if dry_run:
        # No LLM, no DB write — just report what WOULD be forecast.
        return {"open_candidates": len(records), "manifest_date": manifest_date,
                "dry_run": True,
                "sample": [r["question_text"][:80] for r in records[:5]]}

    # Real run: forecast (LLM) then publish. Idempotent on (source, external_ref).
    entries = build_external_entries(records, engine_forecaster, manifest_date)

    import asyncpg  # lazy — keeps the pure helpers importable without the driver
    conn = await asyncpg.connect(_asyncpg_dsn())
    try:
        for e in entries:
            await conn.execute(
                """
                INSERT INTO benchmark_ledger
                    (id, source, external_ref, external_url, resolution_criteria,
                     crowd_prob, question_text, prediction_score, created_at,
                     content_hash, manifest_date)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (source, external_ref) WHERE external_ref IS NOT NULL
                DO NOTHING
                """,
                e["id"], e["source"], e["external_ref"], e["external_url"],
                e["resolution_criteria"], e["crowd_prob"], e["question_text"],
                e["prediction_score"], e["created_at"], e["content_hash"],
                e["manifest_date"],
            )

        # Recompute today's manifest over ALL entries stamped today (internal +
        # external share one audit anchor; root is order-independent over the set).
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
        return {"open_candidates": len(records), "forecast": len(entries),
                "manifest_date": manifest_date, "root_hash": root,
                "entry_count": len(hashes), "manifest_file": path, "dry_run": False}
    finally:
        await conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description="Publish forward-mode external forecasts (Manifold).")
    ap.add_argument("--limit", type=int, default=25, help="max open questions to forecast this run")
    ap.add_argument("--max-fetch", type=int, default=200, help="candidate markets to pull before filtering")
    ap.add_argument("--horizon-days", type=int, default=14, help="only markets closing within N days")
    ap.add_argument("--min-traders", type=int, default=15, help="min unique bettors (liquidity floor)")
    ap.add_argument("--min-volume", type=float, default=50.0, help="min market volume (liquidity floor)")
    ap.add_argument("--dry-run", action="store_true", help="report candidates only; no LLM, no DB write")
    args = ap.parse_args()

    filters = {"min_traders": args.min_traders, "min_volume": args.min_volume,
               "max_horizon_days": args.horizon_days}
    res = asyncio.run(_run(args.limit, args.dry_run, args.max_fetch, filters))

    if res.get("dry_run"):
        print(f"[dry-run] {res['open_candidates']} filtered OPEN question(s) would be "
              f"forecast into manifest {res['manifest_date']}. No LLM, no DB write.")
        for q in res.get("sample", []):
            print(f"    - {q}")
        return
    print(f"forecast {res['forecast']} of {res['open_candidates']} open question(s); "
          f"published (idempotent).")
    print(f"manifest {res['manifest_date']}: root {res['root_hash'][:16]}... "
          f"over {res['entry_count']} entries")
    print(f"anchor written: {res['manifest_file']}")


if __name__ == "__main__":
    main()
