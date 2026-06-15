"""Calibration math for the prediction track record (pure, no DB)."""
from backend.workers.outcome_worker import _brier


def test_brier_materialized():
    # perfectly confident + materialized -> low error
    assert _brier(80, "materialized") == round((0.8 - 1.0) ** 2, 4)


def test_brier_failed_high_conf_is_penalized():
    # confident but wrong -> high error
    assert _brier(80, "failed") == round((0.8 - 0.0) ** 2, 4)
    assert _brier(80, "failed") > _brier(80, "materialized")


def test_brier_partial():
    assert _brier(60, "partial") == round((0.6 - 0.5) ** 2, 4)


def test_brier_too_early_not_scored():
    assert _brier(80, "too_early") is None


def test_brier_handles_missing_or_out_of_range():
    assert _brier(None, "materialized") is None
    assert _brier(150, "materialized") == 0.0   # clamps to 1.0
    assert _brier(-20, "failed") == 0.0          # clamps to 0.0
