"""
Backfill `prediction_outcomes` from a labeled historical-outcome dataset.
$0 / local. Ingests YOUR labeled outcomes so backtest_cpe.py's Path A (real graded
outcomes) has rows to score — as opposed to Path B, which only *derives* soft labels
from current_status and needs no dataset.

INPUT (CSV with a header row, or a JSON array of objects). Columns per row:
  REQUIRED
    narrative_event_id          UUID — must exist in narrative_events.id (FK)
    original_prediction_score   number 0-100 (the CPE prediction at the time)
    <one outcome column>        either:
        observed_probability    float 0-1 (what actually happened, as a probability), OR
        actual_outcome          text: materialized (=1.0) | partial (=0.5) | failed (=0.0)
  OPTIONAL
    predicted_timeline          text
    outcome_notes               text
    evaluated_at                ISO-8601 timestamp (default: now)

Each accepted row is stored with observed_probability + per-row brier_score/log_loss
computed via backend.consequence_engine.calibration, so the rows look exactly like ones
the live outcome_worker would have graded.

Usage:
    python -m scripts.backfill_prediction_outcomes --input outcomes.csv --dry-run
    python -m scripts.backfill_prediction_outcomes --input outcomes.csv
    python -m scripts.backfill_prediction_outcomes --input outcomes.json --replace

--dry-run  : validate + report, insert nothing.
--replace  : delete existing prediction_outcomes rows for the referenced event ids first
             (makes re-running idempotent instead of piling up duplicates).
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.consequence_engine import calibration  # noqa: E402

_OUTCOME_TO_PROB = {"materialized": 1.0, "partial": 0.5, "failed": 0.0}


class RowError(ValueError):
    """A single input row failed validation (message names the offending field)."""


def normalize_row(raw: dict) -> dict:
    """Pure: validate + normalize one input record into an insertable row.

    Returns a dict with keys: narrative_event_id, original_prediction_score (int),
    observed_probability (float 0-1), actual_outcome (str|None), predicted_timeline,
    outcome_notes, evaluated_at (datetime). Raises RowError on bad input.
    """
    eid = (raw.get("narrative_event_id") or "").strip()
    if not eid:
        raise RowError("narrative_event_id is required")

    score_raw = raw.get("original_prediction_score")
    if score_raw in (None, ""):
        raise RowError(f"{eid}: original_prediction_score is required")
    try:
        score = int(round(float(score_raw)))
    except (TypeError, ValueError):
        raise RowError(f"{eid}: original_prediction_score not a number: {score_raw!r}")
    if not 0 <= score <= 100:
        raise RowError(f"{eid}: original_prediction_score out of 0-100: {score}")

    # Outcome: observed_probability wins; else map actual_outcome text.
    obs_raw = raw.get("observed_probability")
    outcome = (raw.get("actual_outcome") or "").strip().lower() or None
    if obs_raw not in (None, ""):
        try:
            obs = float(obs_raw)
        except (TypeError, ValueError):
            raise RowError(f"{eid}: observed_probability not a number: {obs_raw!r}")
        if not 0.0 <= obs <= 1.0:
            raise RowError(f"{eid}: observed_probability out of 0-1: {obs}")
    elif outcome is not None:
        if outcome not in _OUTCOME_TO_PROB:
            raise RowError(
                f"{eid}: actual_outcome must be one of {sorted(_OUTCOME_TO_PROB)}, got {outcome!r}"
            )
        obs = _OUTCOME_TO_PROB[outcome]
    else:
        raise RowError(f"{eid}: need observed_probability or actual_outcome")

    ev_raw = (raw.get("evaluated_at") or "").strip()
    if ev_raw:
        try:
            evaluated_at = datetime.fromisoformat(ev_raw.replace("Z", "+00:00"))
        except ValueError:
            raise RowError(f"{eid}: evaluated_at not ISO-8601: {ev_raw!r}")
    else:
        evaluated_at = datetime.now(timezone.utc)

    return {
        "narrative_event_id": eid,
        "original_prediction_score": score,
        "observed_probability": obs,
        "actual_outcome": outcome,
        "predicted_timeline": (raw.get("predicted_timeline") or "").strip() or None,
        "outcome_notes": (raw.get("outcome_notes") or "").strip() or None,
        "evaluated_at": evaluated_at,
    }


def _read_records(path: str) -> list[dict]:
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON input must be an array of row objects")
        return [dict(r) for r in data]
    with open(path, newline="", encoding="utf-8") as f:
        return [dict(r) for r in csv.DictReader(f)]


def normalize_all(records: list[dict]) -> tuple[list[dict], list[str]]:
    """Pure: normalize every record; return (accepted_rows, error_messages)."""
    rows, errors = [], []
    for i, raw in enumerate(records, start=1):
        try:
            rows.append(normalize_row(raw))
        except RowError as e:
            errors.append(f"row {i}: {e}")
    return rows, errors


def _asyncpg_dsn() -> str:
    # Mirror backtest_cpe: accept either scheme, hand asyncpg a plain DSN.
    url = os.environ.get("DATABASE_URL", "postgresql://narrative:narrative@localhost:5432/narrative")
    return url.replace("postgresql+asyncpg://", "postgresql://").replace("+asyncpg", "")


async def _run(rows: list[dict], replace: bool) -> tuple[int, int]:
    import asyncpg  # lazy — keeps the pure path importable without the driver

    conn = await asyncpg.connect(_asyncpg_dsn())
    inserted = skipped = 0
    try:
        eids = list({r["narrative_event_id"] for r in rows})
        existing = {
            str(r["id"]) for r in await conn.fetch(
                "select id from narrative_events where id = any($1::uuid[])", eids
            )
        }
        if replace:
            await conn.execute(
                "delete from prediction_outcomes where narrative_event_id = any($1::uuid[])", eids
            )
        for r in rows:
            if r["narrative_event_id"] not in existing:
                skipped += 1
                print(f"  skip (no such event): {r['narrative_event_id']}")
                continue
            p = r["original_prediction_score"] / 100.0
            o = r["observed_probability"]
            await conn.execute(
                """
                insert into prediction_outcomes
                    (narrative_event_id, original_prediction_score, actual_outcome,
                     predicted_timeline, outcome_notes, evaluated_at,
                     observed_probability, outcome_label, brier_score, log_loss)
                values ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                r["narrative_event_id"], r["original_prediction_score"], r["actual_outcome"],
                r["predicted_timeline"], r["outcome_notes"], r["evaluated_at"],
                o, o, calibration.brier_score(p, o), calibration.log_loss(p, o),
            )
            inserted += 1
    finally:
        await conn.close()
    return inserted, skipped


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill prediction_outcomes from labeled data.")
    ap.add_argument("--input", required=True, help="CSV or JSON dataset path")
    ap.add_argument("--dry-run", action="store_true", help="validate + report, insert nothing")
    ap.add_argument("--replace", action="store_true", help="delete existing rows for these events first")
    args = ap.parse_args()

    records = _read_records(args.input)
    rows, errors = normalize_all(records)
    print(f"read {len(records)} records -> {len(rows)} valid, {len(errors)} invalid")
    for e in errors:
        print(f"  ! {e}")

    if not rows:
        print("nothing to insert.")
        sys.exit(1 if errors else 0)

    if args.dry_run:
        # Preview the Brier the accepted rows would contribute (Path A shape).
        pairs = [(r["original_prediction_score"] / 100.0, r["observed_probability"]) for r in rows]
        brier = sum(calibration.brier_score(p, o) for p, o in pairs) / len(pairs)
        print(f"[dry-run] {len(rows)} rows would insert; mean Brier {brier:.4f}. No DB write.")
        return

    inserted, skipped = asyncio.run(_run(rows, args.replace))
    print(f"done: inserted {inserted}, skipped {skipped} (missing event FK).")
    print("Now score them:  python scripts/backtest_cpe.py   (Path A)")


if __name__ == "__main__":
    main()
