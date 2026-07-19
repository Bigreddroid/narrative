"""
VALIDATION BENCHMARK SCORE — one headline number for the CPE calibration pipeline.

Consolidates TWO independent, honest proofs that our proper-scoring +
recalibration code (backend/consequence_engine/calibration.py) is correct:

  [A] SYNTHETIC CONTROLS — deterministic positive/negative controls
      (scripts/validate_calibration.py). A correct pipeline reads calibrated
      data as calibrated and PROVABLY recovers overconfident data with isotonic.
      Reported as "k / 5 controls PASS", numbers locked to < 1e-12.

  [B] EXTERNAL REAL DATA — a real Brier score on the Autocast dataset
      (scripts/validate_calibration_autocast.py; Zou et al., 2022) of real
      Metaculus / Good-Judgment-Open / CSET-Foretell crowd forecasts. Proves the
      same math holds on real-world forecasts, not just synthetic streams.

WHAT THIS IS NOT: it is NOT the consequence engine's own forecast skill. Proof B
scores OTHER forecasters' (crowd) calibration; the engine's own Brier Skill Score
is gated on n>=20 real graded outcomes accruing over calendar time
(scripts/backtest_cpe.py Path A). This script never claims otherwise.

Usage:
    python scripts/benchmark_score.py                 # download Autocast, real Brier
    python scripts/benchmark_score.py --offline       # deterministic, selftest fixture
    python scripts/benchmark_score.py --autocast-file autocast_questions.json
    python scripts/benchmark_score.py --json --report out.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.consequence_engine import calibration  # noqa: E402
from scripts.validate_calibration import (  # noqa: E402
    control_checks, summarize, synth_calibrated, synth_overconfident,
)
from scripts import validate_calibration_autocast as ac  # noqa: E402

AUTOCAST_URL = "https://people.eecs.berkeley.edu/~hendrycks/autocast.tar.gz"
# Four pairs with a hand-computed Brier of 0.0575 (errors .01+.04+.09+.09)/4 —
# the offline fallback so the benchmark still runs (labeled) with no network.
_SELFTEST_PAIRS: list[tuple[float, float]] = [(0.9, 1.0), (0.2, 0.0), (0.7, 1.0), (0.3, 0.0)]


# ── Proof A: synthetic controls ────────────────────────────────────────────────
def synthetic_proof(n: int = 2000) -> dict:
    """Run the positive/negative synthetic controls and score the 5 checks.

    Pure/deterministic (seeded). Reuses validate_calibration so the checks here
    are the SAME assertions that script proves — the score can never drift."""
    cal = summarize("positive control - CALIBRATED forecasts", synth_calibrated(n))
    over = summarize("negative control - OVERCONFIDENT forecasts", synth_overconfident(n))
    checks = control_checks(cal, over)
    passed = sum(1 for _, ok in checks if ok)
    return {"cal": cal, "over": over, "checks": checks, "passed": passed, "total": len(checks)}


# ── Proof B: external real dataset (Autocast) ──────────────────────────────────
def _cache_path() -> str:
    return os.path.join(tempfile.gettempdir(), "narrative_autocast", "autocast_questions.json")


def _download_autocast(timeout: int = 90) -> str:
    """Fetch + extract autocast_questions.json to a temp cache (never committed).

    Returns the cached path. Raises on any network/extraction failure so the
    caller can fall back to the labeled selftest fixture."""
    import tarfile
    import urllib.request

    dst = _cache_path()
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return dst
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    tar_fd, tar_path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(tar_fd)
    try:
        with urllib.request.urlopen(AUTOCAST_URL, timeout=timeout) as resp, open(tar_path, "wb") as out:
            out.write(resp.read())
        with tarfile.open(tar_path) as tf:
            # Match the real file by exact basename and skip macOS AppleDouble
            # sidecars (`._autocast_questions.json`, a 276-byte resource fork that
            # is NOT json) and PaxHeader entries.
            member = next(
                m for m in tf.getmembers()
                if m.isfile() and os.path.basename(m.name) == "autocast_questions.json"
            )
            data = tf.extractfile(member).read()
        with open(dst, "wb") as out:
            out.write(data)
    finally:
        if os.path.exists(tar_path):
            os.remove(tar_path)
    return dst


def autocast_proof(autocast_file: str | None = None, offline: bool = False) -> dict:
    """Score OUR calibration math on real Autocast crowd forecasts.

    Falls back to the built-in selftest fixture (clearly flagged) on --offline or
    any acquisition failure — never fabricates a real number."""
    source, reason = "real", ""
    try:
        if offline:
            raise RuntimeError("offline requested")
        path = autocast_file or os.environ.get("AUTOCAST_QUESTIONS") or _download_autocast()
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        questions = data if isinstance(data, list) else data.get("questions", data.get("data", []))
        pairs = ac.extract_pairs(questions)
        if not pairs:
            raise RuntimeError("no resolved binary questions parsed")
    except Exception as exc:  # network down, server moved, bad file, offline flag
        source, reason = "selftest", str(exc)
        pairs = list(_SELFTEST_PAIRS)

    r = ac.report(pairs)
    r["source"] = source
    r["bss"] = calibration.brier_skill_score(pairs)
    if reason:
        r["reason"] = reason
    return r


# ── Render the consolidated headline panel (ASCII-only for Windows consoles) ───
def render(syn: dict, auto: dict) -> str:
    p, t = syn["passed"], syn["total"]
    cal, over = syn["cal"], syn["over"]
    L = ["=" * 72,
         "VALIDATION BENCHMARK - CPE calibration pipeline",
         "Two independent proofs that the scoring math is correct.",
         "=" * 72,
         "",
         "[A] SYNTHETIC CONTROLS (deterministic, seeded, locked < 1e-12)",
         f"    controls passed .............. {p} / {t}  {'PASS' if p == t else 'FAIL'}",
         f"    overconfidence detected ...... ECE {over['ece']:.3f} (flagged)",
         f"    isotonic recovery (Brier) .... {over['brier']:.3f} -> {over['brier_recal']:.3f}",
         f"    isotonic recovery (ECE) ...... {over['ece']:.3f} -> {over['ece_recal']:.3f}",
         f"    no-harm on calibrated (Brier)  {cal['brier']:.3f} -> {cal['brier_recal']:.3f}"]
    for name, ok in syn["checks"]:
        L.append(f"      [{'PASS' if ok else 'FAIL'}] {name}")

    src = auto["source"]
    tag = "REAL Autocast dataset" if src == "real" else "selftest fixture - real dataset unreachable"
    L += ["", f"[B] EXTERNAL REAL-DATA ({tag})"]
    if auto.get("n"):
        bss = auto.get("bss")
        L += [f"    resolved binary questions .... {auto['n']}",
              f"    crowd Brier .................. {auto['model_brier']:.4f}",
              f"    vs base-rate Brier ........... {auto['base_brier']:.4f}",
              f"    vs coin (0.5) Brier .......... {auto['coin_brier']:.4f}",
              f"    Brier Skill Score ............ {bss:.4f}" if bss is not None
              else "    Brier Skill Score ............ n/a",
              f"    --> crowd {'BEATS' if auto['beats_base_rate'] else 'does NOT beat'} "
              "base-rate (sanity check on our scoring math)"]
    if src == "selftest" and auto.get("reason"):
        L.append(f"    note: {auto['reason']}")
    L += ["    scope: validates our Brier/ECE code on REAL forecasts; this is CROWD",
          "           calibration (Metaculus/GJOpen/CSET), NOT the engine's own skill."]

    real_tail = (f" + real-data Brier {auto['model_brier']:.3f}"
                 if src == "real" and auto.get("n") else "")
    L += ["", "-" * 72,
          f"VERDICT: calibration pipeline {'VALIDATED' if p == t else 'FAILED'} - "
          f"{p}/{t} synthetic controls{real_tail}.",
          "Scope: proves the scoring MATH (synthetic + real forecasts). The engine's OWN",
          "domain accuracy (Brier Skill Score on its predictions) stays gated on n>=20 real",
          "graded outcomes - accruing, first possible ~Aug 2026. No overclaiming."]
    return "\n".join(L)


def as_dict(syn: dict, auto: dict) -> dict:
    """Machine-readable form for docs/artifact generation."""
    return {
        "synthetic": {"passed": syn["passed"], "total": syn["total"],
                      "cal_ece": syn["cal"]["ece"], "over_ece": syn["over"]["ece"],
                      "over_ece_recal": syn["over"]["ece_recal"],
                      "over_brier": syn["over"]["brier"], "over_brier_recal": syn["over"]["brier_recal"]},
        "autocast": {k: auto.get(k) for k in
                     ("source", "n", "model_brier", "base_brier", "coin_brier",
                      "log_loss", "ece", "bss", "beats_base_rate")},
        "engine_gated": {"metric": "Brier Skill Score", "requires_n": calibration.MIN_CALIBRATION_POINTS,
                         "status": "accruing"},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CPE validation benchmark score.")
    ap.add_argument("--offline", action="store_true",
                    help="skip the Autocast download; use the built-in selftest fixture")
    ap.add_argument("--autocast-file", help="path to autocast_questions.json (else auto-download)")
    ap.add_argument("--report", help="also write the panel/json to this path")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of the panel")
    args = ap.parse_args()

    syn = synthetic_proof()
    auto = autocast_proof(args.autocast_file, offline=args.offline)
    out = json.dumps(as_dict(syn, auto), indent=2) if args.json else render(syn, auto)
    print(out)
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(out + "\n")
        print(f"[report written: {args.report}]")
    return 0 if syn["passed"] == syn["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
