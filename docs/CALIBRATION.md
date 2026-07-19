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

## 3. The benchmark — metrics the forecast-verification field already recognizes

Being an "industry-best-standard" benchmark means adopting the metrics the forecast-verification
field already accepts — proper scoring rules and their standard decompositions — not inventing our
own. `backend/consequence_engine/calibration.py` implements them (pure stdlib, unit-tested); they
surface in `scripts/backtest_cpe.py` and are reproduced in CI on the validation controls.

### 3a. The two benchmarks and their bars

| Benchmark | Metric | Bar to pass | Status |
|---|---|---|---|
| **Pipeline** (fixed pass/fail) | calibrated-control ECE | < 0.05 | ✅ (0.019 → 0.000) |
| | isotonic no-harm on calibrated data | ΔBrier ≤ +0.005 | ✅ |
| | overconfident-control detection | ECE > 0.05 flagged | ✅ (0.132) |
| | isotonic recovery on overconfident data | strictly lowers Brier **and** ECE | ✅ (Brier 0.193 → 0.168, ECE → 0.000) |
| | seeded reproducibility | numbers locked to < 1e-12 | ✅ |
| **Engine** (relative, gated) | graded outcomes | n ≥ 20 | ⏳ accruing |
| | **Brier Skill Score** vs base rate | BSS > 0 | ⏳ (runs once n ≥ 20) |

### 3b. The recognized metrics we report

- **Proper scoring rules** — **Brier score** and **log-loss**, per prediction. Proper = a
  forecaster minimizes expected score only by reporting its true probability, so the score cannot
  be gamed.
- **Brier Skill Score (BSS)** = `1 − Brier_model / Brier_reference`, reference = the climatological
  base rate. **BSS > 0 means genuine skill over the baseline** — the meteorology / forecast-
  verification standard. It turns the raw "beats base rate" comparison into one normalized, quotable
  number: BSS = 1 perfect, 0 = no better than climatology, < 0 = worse.
- **Murphy (1973) decomposition**: `Brier = Reliability − Resolution + Uncertainty`.
  Reliability (calibration gap, lower better), Resolution (ability to separate cases, higher better),
  Uncertainty (irreducible base-rate variance). Our implementation groups by distinct forecast value,
  so the identity reconstructs the Brier score exactly for binary outcomes (asserted to < 1e-12).
- **ECE / reliability curve** — Expected Calibration Error and the reliability diagram (the standard
  calibration plot).

### 3c. Field reference points (so "good" is honest, not near-zero)

- **Brier:** 0 = perfect, **0.25 = a coin flip**, 1 = worst possible.
- **ECE:** < 0.05 well-calibrated, < 0.10 acceptable.
- **Elite human forecasters** (Tetlock / Good Judgment superforecasters) score roughly **0.15–0.20
  Brier** on hard geopolitical questions. So the honest bar for the engine is **"positive BSS with a
  small ECE"** — beating the base rate on real outcomes — **not** a near-zero Brier, which on genuinely
  uncertain events would signal a leak or an easy question set, not skill.

### 3d. Methodology citations

- Brier, G.W. (1950). *Verification of forecasts expressed in terms of probability.* Monthly Weather Review.
- Murphy, A.H. (1973). *A new vector partition of the probability score.* Journal of Applied Meteorology (reliability–resolution–uncertainty).
- Gneiting, T. & Raftery, A.E. (2007). *Strictly proper scoring rules, prediction, and estimation.* JASA.
- Barnston, A.G. (1992) / WMO forecast-verification practice — **Brier Skill Score** vs climatology.
- Ayer, M. et al. (1955); Zadrozny & Elkan (2002) — **isotonic regression / PAVA** for probability calibration.
- Zou, A. et al. (2022). *Forecasting Future World Events with Neural Networks* (the **Autocast** dataset). NeurIPS.

> **No overclaiming:** BSS and the Murphy decomposition on the *engine* are still gated on n ≥ 20 real
> graded outcomes. Until then they run on the validation controls — proving the *metrics themselves* are
> implemented correctly — exactly as `backtest_cpe.py` refuses a verdict below n = 20.

### 3e. Validation benchmark score — one command, two independent proofs

`python scripts/benchmark_score.py` rolls the whole thing into a single headline verdict:

| Proof | What it validates | Result |
|---|---|---|
| **A — synthetic controls** | the scoring + isotonic-recovery math, deterministically | **5 / 5 controls PASS** (locked < 1e-12): overconfident Brier 0.193 → 0.168, ECE 0.132 → 0.000; no harm on calibrated data |
| **B — Autocast real data** | the *same* math on **real** forecasts (Zou et al., 2022; Metaculus / GJOpen / CSET crowds) | n = 2003 resolved binary questions, crowd Brier **0.0948**, **BSS 0.547** vs base-rate Brier 0.209 — BEATS the baseline |

Proof B is a **real Brier on real forecasts**, so the pipeline is validated beyond synthetic streams.
It is **crowd** calibration (other forecasters'), an independent sanity check on our scoring code —
**not** the engine's own skill, which stays gated on n ≥ 20 (§2). CI and air-gapped runs use
`--offline` (a deterministic self-test fixture, clearly labeled) when the dataset is unreachable; the
Autocast file is fetched keylessly and cached to a temp dir, never committed.

**Headline verdict:** *calibration pipeline VALIDATED — 5/5 synthetic controls + real-data Brier
0.095; engine domain accuracy (BSS on its own predictions) accruing toward n ≥ 20.*

### 3f. The third axis — testing the engine *outside*, and the leakage trap

Proofs A/B validate the *scoring math*. Testing our own **engine** on outside questions has one
integrity trap: our local model has a training cutoff, so any externally-resolved question that
resolved **before** that cutoff may already be "known" to the model — a good score there is hindsight,
not skill, and must never be compared to superforecasters. Two surfaces, hard-labeled:

- **Retrospective external (diagnostic only).** `python scripts/external_benchmark.py --dataset
  autocast` runs `consensus_mapper.forecast_binary` over resolved external questions and partitions
  every run by `--model-cutoff` into `pre_cutoff` (`leakage:"exposed"`) and `post_cutoff`
  (`leakage:"post_cutoff_clean"`). The pre-cutoff bucket is a **diagnostic** that proves the engine
  ingests an arbitrary outside question and emits a scored forecast end-to-end — **not** a skill claim.
  For Autocast (all pre-2023) the clean bucket is essentially empty, which is the honest answer.

- **Forward prediction ledger (the clean engine benchmark).** The only leak-proof engine score: a
  forecast made **now**, published + hashed **before** its outcome is known, graded **later**.
  `scripts/publish_ledger.py` writes each confident forecast (`prediction_score ≥ 60`) to
  `benchmark_ledger` with a write-once `content_hash = sha256(question | score | created_at)`, rolls
  the day's hashes into a `benchmark_manifests` root, and commits that root to git as
  `docs/benchmark/manifest-YYYY-MM-DD.txt`. When `outcome_worker` later grades the prediction against
  evidence that did not exist at forecast time, it backfills the entry's resolved Brier. A third party
  recomputes `sha256(sorted content_hashes)` and matches it against the committed root — proving we did
  not back-date or edit any forecast after seeing how it resolved. **Engine skill (BSS over resolved
  ledger entries) stays gated at n ≥ 20**; `GET /api/v1/benchmark/engine-skill` returns
  `status:"withheld"` with no number below the gate.

Public, precomputed, no-auth endpoints (they serve persisted rows only — never a request-time download
or LLM call): `GET /api/v1/benchmark/ledger?since=`, `GET /api/v1/benchmark/ledger/manifest/{date}`,
`GET /api/v1/benchmark/engine-skill`.

### 3g. Continuous refresh — the board stays live on its own

`backend/workers/benchmark_worker.py` runs every `benchmark_interval_days` (default 7) in the scheduler
and, in one LLM-free pass, recomputes the real Autocast crowd Brier, auto-publishes the forward ledger
(so new confident forecasts get hashed + manifested without a manual `publish_ledger` run), recomputes
the gated engine skill, and writes one `benchmark_runs` cache row. `GET /api/v1/benchmark/score` serves
the **latest cached row** — zero request-time compute or network — and because the row lives in Postgres
(not the `/tmp` Autocast cache) the real crowd number **survives a container `--force-recreate`**. Until
the first worker row exists (fresh DB / CI), the endpoint falls back to the deterministic offline proofs,
so it never fabricates and never 500s. The worker calls no LLM, so it behaves identically on the local
Docker stack and on Railway; `engine_bss` is persisted as NULL until the n ≥ 20 gate is met.

---

## 4. The claims we make (verbatim, safe to quote)

> "Our calibration **pipeline** is validated against positive and negative controls — it detects
> miscalibration and provably corrects it — and the proof is reproducible in one command."

> "Our backtest is **self-skeptical by design**: it refuses to report accuracy below 20 graded
> outcomes and always benchmarks against a base-rate baseline."

> "Live outcome grading is **accruing**; we do not claim a production accuracy number until enough
> real outcomes have resolved."

> "Every forecast is **hashed and published before its outcome is known**, and the daily manifest root
> is committed to git — so our resolved scores are third-party verifiable and cannot be back-dated."

Claims we deliberately do **not** make: any single production Brier presented as "engine accuracy"
before n≥20 real graded outcomes; any calibration number derived from soft/status-only labels
presented as ground truth.

---

## 5. Reproduce it

```
# Headline validation benchmark — 5/5 synthetic controls + real Autocast Brier
python scripts/benchmark_score.py            # fetches Autocast (keyless) for a real Brier
python scripts/benchmark_score.py --offline  # deterministic, no network (selftest fixture)

# Pipeline proof (offline, <1s, deterministic)
python scripts/validate_calibration.py --report calibration_report.txt

# Full test suite
bash scripts/run_backend_tests.sh

# Engine on OUTSIDE resolved questions (leakage-partitioned diagnostic)
python scripts/external_benchmark.py --dataset autocast --limit 50
python scripts/external_benchmark.py --offline          # stub forecaster, no LLM/network

# Publish the forward prediction ledger + daily manifest root (needs a populated DB)
python -m scripts.publish_ledger --dry-run              # report only
python -m scripts.publish_ledger                        # writes docs/benchmark/manifest-<date>.txt

# Continuous refresh: recompute crowd Brier, auto-publish the ledger, cache a
# benchmark_runs row that /benchmark/score serves (LLM-free; needs a populated DB)
python -m backend.workers.benchmark_worker

# Engine calibration once outcomes exist (needs a populated DB + running scheduler w/ LLM)
python scripts/backtest_cpe.py
```
