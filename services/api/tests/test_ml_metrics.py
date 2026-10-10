import math

import numpy as np
import pytest

from ml.confidence import DirectionCalibrator, certainty
from ml.metrics import (
    brier,
    classification_summary,
    diebold_mariano,
    direction_hits,
    price_error_summary,
    proportion_above_p_value,
    reliability_table,
    wilson_interval,
)


def test_wilson_interval_reference_value():
    # 50 hits in 100: the textbook Wilson 95% interval is 0.4038-0.5962
    low, high = wilson_interval(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-4) and high == pytest.approx(0.5962, abs=1e-4)
    assert all(math.isnan(x) for x in wilson_interval(0, 0))


def test_proportion_test():
    assert proportion_above_p_value(50, 100, 0.5) == pytest.approx(0.5)
    assert proportion_above_p_value(65, 100, 0.5) < 0.01


def test_direction_hits_skip_days_without_a_move():
    predicted = np.array([0.01, -0.02, 0.0, 0.03])
    actual = np.array([0.02, 0.01, 0.05, 0.0])
    # Row 3 (no forecast move) and row 4 (no actual move) are not counted
    assert direction_hits(predicted, actual) == (1, 2)


def test_price_errors_are_relative():
    out = price_error_summary(np.array([110.0, 9.0]), np.array([100.0, 10.0]))
    assert out["rmse_pct"] == pytest.approx(10.0)
    assert out["mape_pct"] == pytest.approx(10.0)
    assert out["mae_rs"] == pytest.approx(5.5)


def test_diebold_mariano_sign():
    rng = np.random.default_rng(0)
    baseline = rng.uniform(1, 2, 200)
    better = diebold_mariano(baseline * 0.5, baseline)
    assert better["statistic"] < 0 and better["p_value"] < 0.01
    same = diebold_mariano(baseline, baseline)
    assert math.isnan(same["p_value"])


def test_classification_summary_and_brier():
    y = np.array([-1, 0, 1, 1])
    perfect = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 1]], dtype=float)
    out = classification_summary(y, y, [-1, 0, 1], perfect)
    assert out["accuracy"] == 1.0 and out["balanced_accuracy"] == 1.0 and out["brier"] == 0.0
    assert out["confusion_matrix"] == [[1, 0, 0], [0, 1, 0], [0, 0, 2]]


def test_reliability_table_bands():
    confidence = np.array([0.45, 0.52, 0.58, 0.7])
    hit = np.array([0.0, 1.0, 0.0, 1.0])
    table = reliability_table(confidence, hit, (0.5, 0.6))
    assert [row["rows"] for row in table] == [1, 2, 1]
    assert table[1]["observed_hit_rate"] == 0.5
    assert table[0]["band"] == [None, 0.5] and table[-1]["band"] == [0.6, None]
    assert brier(np.array([1.0, 0.0]), np.array([1.0, 1.0])) == 0.5


def test_calibrator_is_monotone_and_bounded():
    rng = np.random.default_rng(1)
    z = rng.uniform(0, 3, 2000)
    hit = rng.uniform(size=2000) < 0.45 + 0.1 * z  # more certain -> right more often
    calibrator = DirectionCalibrator().fit(z, hit)
    out = calibrator.predict(np.array([0.0, 1.0, 2.0, 50.0]))
    assert np.all(np.diff(out) >= 0) and out.min() >= 0 and out.max() <= 1
    assert out[-1] == calibrator.predict(np.array([3.0]))[0]  # clipped beyond the fit range
    assert certainty(np.array([0.01]), np.array([0.0]))[0] > 1e5  # zero spread is guarded


def test_diebold_mariano_newey_west_widens_for_overlapping_errors():
    # Five-day forecasts made each day share four days of outcome: errors come in runs
    rng = np.random.default_rng(1)
    shocks = rng.normal(0.05, 1.0, 400)
    d = np.convolve(shocks, np.ones(5), mode="valid")
    plain = diebold_mariano(d, np.zeros_like(d))
    overlapping = diebold_mariano(d, np.zeros_like(d), lag=4)
    assert overlapping["lag"] == 4
    assert abs(overlapping["statistic"]) < abs(plain["statistic"])
    assert diebold_mariano(d, np.zeros_like(d), lag=0)["statistic"] == plain["statistic"]
