"""
Prediction calibration — proper scoring + reliability + isotonic recalibration.

Replaces the old circular heuristic (which assumed resolved=85/escalating=65 and
never measured reality) with real metrics:

  • outcome_label(...)   ground truth ∈ {1.0 materialized, 0.5 partial, 0.0 failed}
  • brier_score / log_loss   proper scoring rules, per prediction
  • reliability_curve / ece   how well predicted probabilities match observed rates
  • fit_isotonic / apply_isotonic   monotonic recalibration map (PAVA), identity
        until enough data accrues — feeds back into future prediction scores

Pure stdlib (no sklearn) so it stays dependency-light and unit-testable. The
prediction_outcomes table IS the proprietary calibration dataset; the calibrator
is re-fit from it on demand.
"""

import bisect
import math

EPS = 1e-12
MIN_CALIBRATION_POINTS = 20  # below this, recalibration is the identity map


def brier_score(p: float, o: float) -> float:
    """Squared error of a probabilistic prediction. 0 = perfect, 1 = worst."""
    return (p - o) ** 2


def log_loss(p: float, o: float) -> float:
    """Logarithmic (cross-entropy) loss, clipped to stay finite."""
    p = min(1 - EPS, max(EPS, p))
    return -(o * math.log(p) + (1 - o) * math.log(1 - p))


def outcome_label(status: str | None, impacts_materialized: bool | None = None) -> float | None:
    """Objective outcome ∈ {1.0, 0.5, 0.0}; None while still pending.

    Status is the primary signal; an explicit impacts-materialized flag (e.g. from
    later articles or an admin review) overrides it when present.
    """
    if impacts_materialized is True:
        return 1.0
    if impacts_materialized is False:
        return 0.0
    s = (status or "").lower()
    if s == "resolved":
        return 1.0
    if s == "escalating":
        return 0.5
    if s == "stable":
        return 0.0
    return None


def reliability_curve(pairs: list[tuple[float, float]], n_bins: int = 10) -> list[dict]:
    """Bin predictions and compare mean predicted prob vs observed frequency."""
    bins = []
    for i in range(n_bins):
        lo, hi = i / n_bins, (i + 1) / n_bins
        members = [(p, o) for p, o in pairs if (lo <= p < hi or (i == n_bins - 1 and p == hi))]
        if members:
            k = len(members)
            bins.append({
                "lo": lo, "hi": hi, "count": k,
                "mean_pred": sum(p for p, _ in members) / k,
                "obs_freq": sum(o for _, o in members) / k,
            })
    return bins


def ece(pairs: list[tuple[float, float]], n_bins: int = 10) -> float:
    """Expected Calibration Error: weighted gap between confidence and accuracy."""
    if not pairs:
        return 0.0
    n = len(pairs)
    return sum((b["count"] / n) * abs(b["mean_pred"] - b["obs_freq"]) for b in reliability_curve(pairs, n_bins))


def brier_skill_score(pairs: list[tuple[float, float]], reference_prob: float | None = None) -> float | None:
    """Brier Skill Score — the forecast-verification standard for skill over a baseline.

        BSS = 1 - Brier_model / Brier_reference

    The reference is the climatological forecast: always predict `reference_prob`,
    which defaults to the base rate (mean observed outcome) — the standard
    climatology reference. BSS > 0 means genuine skill over that baseline;
    0 = no better than climatology; 1 = perfect; < 0 = worse than the baseline.

    This turns the raw "model Brier beats base-rate Brier" comparison into one
    normalized, quotable number. Returns None when there are no pairs, or when the
    reference is itself perfect (Brier_reference = 0) — skill is undefined against a
    zero-error baseline (e.g. a degenerate set with a single outcome value).
    """
    if not pairs:
        return None
    if reference_prob is None:
        reference_prob = sum(o for _, o in pairs) / len(pairs)
    brier_model = sum(brier_score(p, o) for p, o in pairs) / len(pairs)
    brier_ref = sum(brier_score(reference_prob, o) for _, o in pairs) / len(pairs)
    if brier_ref <= EPS:
        return None
    return 1.0 - brier_model / brier_ref


def murphy_decomposition(pairs: list[tuple[float, float]]) -> dict:
    """Murphy (1973) 3-component decomposition of the Brier score:

        Brier = Reliability - Resolution + Uncertainty

    Forecasts are grouped by distinct predicted value (each distinct forecast is
    its own bin), which makes the identity EXACT for binary outcomes o in {0,1}.

      • reliability (REL): mean squared gap between a forecast value and the outcome
        frequency observed at that value — 0 is perfectly reliable (lower better).
      • resolution (RES): how far each group's outcome rate spreads from the base
        rate — the forecaster's ability to separate cases (higher better).
      • uncertainty (UNC): base-rate variance o(1-o), inherent to the events and
        independent of the forecast.

    Returns {"reliability", "resolution", "uncertainty", "brier"} where `brier` is
    the reconstruction REL - RES + UNC. For binary outcomes this equals the mean
    Brier score to floating precision (the within-group outcome variance is exactly
    UNC - RES). With soft (0.5) labels the reconstruction is the binary-form identity
    rather than the raw mean Brier, so the CPE decisive path scores on {0,1} labels.
    """
    if not pairs:
        return {"reliability": 0.0, "resolution": 0.0, "uncertainty": 0.0, "brier": 0.0}
    n = len(pairs)
    obar = sum(o for _, o in pairs) / n
    groups: dict[float, list[float]] = {}
    for p, o in pairs:
        groups.setdefault(p, []).append(o)
    rel = res = 0.0
    for p, outs in groups.items():
        k = len(outs)
        obar_k = sum(outs) / k
        rel += k * (p - obar_k) ** 2
        res += k * (obar_k - obar) ** 2
    rel /= n
    res /= n
    unc = obar * (1.0 - obar)
    return {"reliability": rel, "resolution": res, "uncertainty": unc, "brier": rel - res + unc}


def fit_isotonic(pairs: list[tuple[float, float]]) -> dict:
    """Pool-Adjacent-Violators isotonic fit ⇒ monotonic recalibration map.

    Returns {"xs": [...], "ys": [...]} (identity {} until MIN_CALIBRATION_POINTS).
    """
    if len(pairs) < MIN_CALIBRATION_POINTS:
        return {"xs": [], "ys": []}

    # Tied predictions must map to a single output — aggregate by distinct x first.
    agg: dict[float, list[float]] = {}
    for p, o in pairs:
        s = agg.setdefault(p, [0.0, 0.0])
        s[0] += o
        s[1] += 1
    xs = sorted(agg)

    # PAVA over distinct-x weighted means: [sum_o, weight, n_x].
    blocks: list[list[float]] = []
    for x in xs:
        blocks.append([agg[x][0], agg[x][1], 1])
        while len(blocks) >= 2 and blocks[-2][0] / blocks[-2][1] > blocks[-1][0] / blocks[-1][1]:
            s2, w2, n2 = blocks.pop()
            s1, w1, n1 = blocks.pop()
            blocks.append([s1 + s2, w1 + w2, n1 + n2])

    ys: list[float] = []
    for s, w, n_x in blocks:
        ys.extend([s / w] * int(n_x))
    return {"xs": xs, "ys": ys}


def base_rates(records: list[dict]) -> dict:
    """Historical outcome base rate per pattern (e.g. category).

    records: [{"pattern": str, "outcome": float in [0,1]}]. Lets a prediction inherit
    how often events of its *kind* have actually materialised — a strong temporal prior.
    """
    agg: dict[str, list[float]] = {}
    for r in records:
        p = r.get("pattern") or "_all"
        s = agg.setdefault(p, [0.0, 0])
        s[0] += r.get("outcome", 0.0)
        s[1] += 1
    return {p: round(s / n, 3) for p, (s, n) in agg.items() if n}


def apply_isotonic(model: dict, p: float) -> float:
    """Map a raw probability through the fitted calibrator (identity if unfitted)."""
    xs, ys = model.get("xs", []), model.get("ys", [])
    if not xs:
        return p
    if p <= xs[0]:
        return ys[0]
    if p >= xs[-1]:
        return ys[-1]
    i = bisect.bisect_left(xs, p)
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    if x1 == x0:
        return y1
    return y0 + (y1 - y0) * (p - x0) / (x1 - x0)
