# Calibration — what is proven, what is accruing

This document is the honest, public-safe statement of how The Narrative measures whether its
consequence predictions are trustworthy. It is written so that every claim below is one you can
make to a judge, investor, or journalist **and defend on the spot**. The reproducible commands
are included so anyone can re-run the proof.

The distinction that matters — and the one most systems blur — is:

| | Claim | Status |
|---|---|---|
| **The scoring pipeline is correct** | Our Brier / ECE / isotonic-recalibration code does the right thing on known-answer data | ✅ **Proven, reproducible today** |
| **The engine is calibrated on real events** | Our live predictions match observed reality | ⏳ **Accruing** — requires real graded outcomes over time |

We claim the first. We do **not** yet claim the second, and our tooling actively refuses to let us.

---

## 1. Proven today — the calibration pipeline is correct

`backend/consequence_engine/calibration.py` implements proper scoring rules (Brier, log-loss),
Expected Calibration Error (ECE), a reliability curve, and Pool-Adjacent-Violators isotonic
recalibration — all pure stdlib, unit-tested.

`scripts/validate_calibration.py` validates it with a **positive and negative control**, the
standard way to prove a calibration estimator:

```
python scripts/validate_calibration.py
```

| Control | What it is | Result |
|---|---|---|
| **Positive** | Well-calibrated forecasts (`outcome ~ Bernoulli(p)`), n=2000 | ECE **0.0193 → 0.0000** after isotonic; Brier 0.1642 → 0.1612 (no harm) |
| **Negative** | Systematically **overconfident** forecasts, n=2000 | Miscalibration **flagged** (ECE 0.1324); isotonic **recovers** it — Brier **0.1931 → 0.1677**, ECE **→ 0.0000** |

Five correctness checks pass; a seeded test (`scripts/validate_calibration_test.py`) locks the
numbers into CI so the proof is reproducible on every commit. The full backend suite (**23
modules**) is green.

**Interpretation:** the pipeline correctly (a) recognizes calibrated forecasts, (b) detects
miscalibration, and (c) provably fixes it. That is a real, defensible result about the *method*.

---

## 2. Accruing — the engine's own calibration

Whether *our* predictions are calibrated can only be measured against **real outcomes**:

- `outcome_worker` (wired into `backend/scheduler.py`) grades each prediction once its horizon has
  elapsed and post-prediction evidence exists, writing rows to `prediction_outcomes`.
- `scripts/backtest_cpe.py` then scores those rows (**Path A**) — Brier vs a base-rate baseline and
  a coin baseline, with a reliability curve.

This is **honest by construction**: `backtest_cpe.py` **refuses to validate below n=20**
("*any number above is anecdote, not accuracy*"), flags label sets with no observed failures
("*a stopped clock scores well here*"), and only reports "beats baseline" when the model's Brier
is genuinely lower than always-predicting-the-base-rate. We consider that self-skepticism a
feature to show, not hide.

Real outcomes accrue over calendar time. Until n≥20 of genuinely graded outcomes exists, we report
the pipeline proof (§1) and the accrual status — never a premature production Brier.

For faster bootstrapping from a **real labeled dataset**, `scripts/backfill_prediction_outcomes.py`
ingests `(narrative_event_id, original_prediction_score, actual_outcome|observed_probability)` rows
into `prediction_outcomes`, so an external gold-standard set (e.g. Metaculus, Good Judgment) can seed
Path A directly.

---

## 3. The claims we make (verbatim, safe to quote)

> "Our calibration **pipeline** is validated against positive and negative controls — it detects
> miscalibration and provably corrects it — and the proof is reproducible in one command."

> "Our backtest is **self-skeptical by design**: it refuses to report accuracy below 20 graded
> outcomes and always benchmarks against a base-rate baseline."

> "Live outcome grading is **accruing**; we do not claim a production accuracy number until enough
> real outcomes have resolved."

Claims we deliberately do **not** make: any single production Brier presented as "engine accuracy"
before n≥20 real graded outcomes; any calibration number derived from soft/status-only labels
presented as ground truth.

---

## 4. Reproduce it

```
# Pipeline proof (offline, <1s, deterministic)
python scripts/validate_calibration.py --report calibration_report.txt

# Full test suite (23 modules)
bash scripts/run_backend_tests.sh

# Engine calibration once outcomes exist (needs a populated DB + running scheduler w/ LLM)
python scripts/backtest_cpe.py
```
