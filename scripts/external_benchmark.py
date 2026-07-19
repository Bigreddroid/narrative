"""
EXTERNAL BENCHMARK — score OUR engine on outside, independently-resolved questions.

This runs the engine's reasoning core (consensus_mapper.forecast_binary) over an
external dataset of RESOLVED yes/no questions and scores its forecasts against the
known outcomes with our own metrics (backend/consequence_engine/calibration.py).

THE LEAKAGE GUARD (read this before quoting any number):
    Our local LLM has a training cutoff. Any question that RESOLVED BEFORE that
    cutoff may already be "known" to the model — so a good score there is
    hindsight, not skill, and must NEVER be compared to superforecasters. We
    partition every run into:
      - pre_cutoff  (leakage: "exposed")        -> a DIAGNOSTIC only. Proves the
                                                   engine ingests an arbitrary
                                                   external question and emits a
                                                   scored forecast end-to-end.
      - post_cutoff (leakage: "post_cutoff_clean") -> the only bucket that could
                                                   support a skill claim. For
                                                   Autocast (all pre-2023) this is
                                                   usually EMPTY, which is the
                                                   honest answer: retrospective
                                                   Autocast cannot yield a clean
                                                   engine-skill number.
    The clean, forward-looking engine benchmark lives in the prediction ledger,
    not here.

Usage:
    python scripts/external_benchmark.py --dataset autocast --limit 50
    python scripts/external_benchmark.py --offline            # stub forecaster, no LLM/network
    python scripts/external_benchmark.py --json --report out.txt
    python scripts/external_benchmark.py --model-cutoff 2023-11-01
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.consequence_engine import calibration  # noqa: E402
from scripts import benchmark_score as bs  # noqa: E402
from scripts import validate_calibration_autocast as ac  # noqa: E402

# Default model cutoff — the local default forecaster is llama3.2 (~late 2023).
# Override per-run with --model-cutoff.
DEFAULT_CUTOFF = "2023-11-01"

# A tiny offline fixture (labeled) so the harness + partition logic run with no
# network and no LLM. Two "pre" (resolved 2022) and one "post" (resolved 2024).
_SELFTEST_RECORDS = [
    {"id": "s1", "question_text": "Did event A happen?", "background": "",
     "publish_date": "2022-01-01", "resolution_date": "2022-06-01",
     "outcome": 1.0, "crowd_prob": 0.8, "source": "selftest"},
    {"id": "s2", "question_text": "Did event B happen?", "background": "",
     "publish_date": "2022-01-01", "resolution_date": "2022-07-01",
     "outcome": 0.0, "crowd_prob": 0.2, "source": "selftest"},
    {"id": "s3", "question_text": "Did event C happen?", "background": "",
     "publish_date": "2024-01-01", "resolution_date": "2024-06-01",
     "outcome": 1.0, "crowd_prob": 0.7, "source": "selftest"},
]


def _parse_date(value) -> datetime | None:
    """Best-effort parse of an Autocast-ish date (ISO string or epoch)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    s = str(value).strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.fromisoformat(s) if fmt is None else datetime.strptime(s, fmt)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Fall back to a leading YYYY-MM-DD.
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def partition_by_leakage(records: list[dict], cutoff: datetime | None
                         ) -> tuple[list[dict], list[dict]]:
    """Split records into (pre_cutoff exposed, post_cutoff clean) by resolution date.

    A record with no parseable resolution date is treated as pre_cutoff (exposed) —
    the conservative choice, since we can't prove it resolved after the cutoff.
    """
    pre, post = [], []
    for r in records:
        rd = _parse_date(r.get("resolution_date"))
        if cutoff and rd and rd > cutoff:
            post.append(r)
        else:
            pre.append(r)
    return pre, post


def score_records(records: list[dict], forecaster, limit: int | None = None) -> dict:
    """Run `forecaster` over records, score forecasts vs outcomes. Reuses ac.report."""
    pairs: list[tuple[float, float]] = []
    skipped = 0
    for r in records:
        if limit and len(pairs) >= limit:
            break
        try:
            p = forecaster(r)
        except Exception:
            p = None
        if p is None:
            skipped += 1
            continue
        pairs.append((float(p), float(r["outcome"])))
    rep = ac.report(pairs)
    rep["skipped"] = skipped
    if rep.get("n"):
        rep["bss"] = calibration.brier_skill_score(pairs)
        rep["murphy"] = calibration.murphy_decomposition(pairs)
    return rep


def engine_forecaster(record: dict) -> float | None:
    """The real engine forecaster: one LLM call per question -> probability in [0,1]."""
    from backend.consequence_engine import consensus_mapper
    out = consensus_mapper.forecast_binary(record["question_text"], record.get("background", ""))
    return out["probability"] / 100.0


def stub_forecaster(record: dict) -> float | None:
    """Deterministic, LLM-free forecaster for --offline and tests.

    Echoes the crowd probability when present (else 0.5) — this exercises the whole
    pipeline/partition without any model call. Labeled selftest; NOT a skill claim.
    """
    cp = record.get("crowd_prob")
    return float(cp) if cp is not None else 0.5


def load_records(dataset: str, autocast_file: str | None, offline: bool) -> tuple[list[dict], str]:
    """Return (records, source_label). Only 'autocast' is wired today (keyless)."""
    if offline:
        return list(_SELFTEST_RECORDS), "selftest"
    if dataset != "autocast":
        raise SystemExit(f"unknown dataset '{dataset}' (only 'autocast' is wired)")
    # Reuse benchmark_score's keyless, cached, never-committed Autocast fetch.
    path = autocast_file or os.environ.get("AUTOCAST_QUESTIONS")
    if not path:
        path = bs._download_autocast()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    questions = data if isinstance(data, list) else data.get("questions", data.get("data", []))
    return ac.extract_records(questions), "real"


_EXPOSED_CAVEAT = ("leakage-exposed: resolved before the model cutoff, so a good "
                   "score here is hindsight, NOT skill. Diagnostic only.")
_CLEAN_CAVEAT = ("resolved after the model cutoff; the only bucket that could "
                 "support an engine-skill claim.")


def run(records: list[dict], forecaster, cutoff: datetime | None,
        limit: int | None, source: str) -> dict:
    pre, post = partition_by_leakage(records, cutoff)
    pre_rep = score_records(pre, forecaster, limit)
    post_rep = score_records(post, forecaster, limit)
    pre_rep.update(leakage="exposed", caveat=_EXPOSED_CAVEAT)
    post_rep.update(leakage="post_cutoff_clean", caveat=_CLEAN_CAVEAT)
    return {
        "dataset": source,
        "model_cutoff": cutoff.date().isoformat() if cutoff else None,
        "total_records": len(records),
        "pre_cutoff": pre_rep,
        "post_cutoff": post_rep,
        "engine_skill_note": (
            "Engine skill is NOT claimed here. Retrospective external scoring is a "
            "leakage diagnostic; the clean engine benchmark is the forward prediction "
            "ledger, still gated on n>=" + str(calibration.MIN_CALIBRATION_POINTS) + "."
        ),
    }


def render(result: dict) -> str:
    L = ["=" * 72,
         "EXTERNAL BENCHMARK - engine on outside resolved questions",
         f"dataset: {result['dataset']}   model cutoff: {result['model_cutoff']}   "
         f"records: {result['total_records']}",
         "=" * 72]
    for key, title in (("pre_cutoff", "PRE-CUTOFF (leakage: exposed) - DIAGNOSTIC ONLY"),
                       ("post_cutoff", "POST-CUTOFF (leakage: clean) - skill-eligible")):
        b = result[key]
        L += ["", title]
        if not b.get("n"):
            L.append(f"    scored: 0  (skipped {b.get('skipped', 0)}) - nothing to report")
            continue
        L += [f"    scored ...................... {b['n']}  (skipped {b.get('skipped', 0)})",
              f"    engine Brier ................ {b['model_brier']:.4f}",
              f"    vs base-rate Brier .......... {b['base_brier']:.4f}",
              f"    Brier Skill Score ........... {b['bss']:.4f}" if b.get("bss") is not None
              else "    Brier Skill Score ........... n/a",
              f"    note: {b['caveat']}"]
    L += ["", "-" * 72, result["engine_skill_note"]]
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Score the engine on external resolved questions.")
    ap.add_argument("--dataset", default="autocast", help="external dataset (only 'autocast' wired)")
    ap.add_argument("--autocast-file", help="path to autocast_questions.json (else auto-download)")
    ap.add_argument("--offline", action="store_true", help="stub forecaster + fixture; no LLM/network")
    ap.add_argument("--limit", type=int, help="cap questions scored per bucket (LLM calls cost time)")
    ap.add_argument("--model-cutoff", default=DEFAULT_CUTOFF, help="YYYY-MM-DD training cutoff")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--report", help="also write output to this path")
    args = ap.parse_args()

    cutoff = _parse_date(args.model_cutoff)
    records, source = load_records(args.dataset, args.autocast_file, args.offline)
    forecaster = stub_forecaster if args.offline else engine_forecaster
    result = run(records, forecaster, cutoff, args.limit, source)

    out = json.dumps(result, indent=2, default=str) if args.json else render(result)
    print(out)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"[report written: {args.report}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
