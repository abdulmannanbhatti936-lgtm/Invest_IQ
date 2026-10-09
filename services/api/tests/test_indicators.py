"""
Indicator correctness and no-lookahead checks (Workflow.md Step 3.2, Memory.md §4).

Reference values: TA-Lib 0.8.1 (`talib.RSI/MACD/BBANDS/SMA` with default parameters) run on
the first 90 served OGDC closes (2021-10-08 to 2022-02-11, rounded to paisa), generated once
in a separate environment; TA-Lib is not a project dependency. TA-Lib itself was checked
against the published Wilder/StockCharts RSI example below, and matches it exactly.
"""

import numpy as np
import pandas as pd
import pytest

from ml.dataset import dividend_adjusted
from ml.features import (
    FEATURE_COLUMNS,
    INDICATOR_COLUMNS,
    add_technical_indicators,
    bollinger,
    build_feature_frame,
    macd,
    rsi,
    sma,
)
from services.dividend_adjustment import cumulative_factors
from tests.conftest import make_ohlcv

OGDC_CLOSES = pd.Series(
    [
        81.5, 81.74, 81.84, 81.03, 81.75, 84.2, 86.12, 84.1, 85.95, 84.43,
        84.43, 83.73, 84.15, 84.59, 85.24, 88.0, 87.86, 86.43, 86.53, 87.62,
        84.89, 83.12, 84.82, 83.51, 81.37, 81.43, 84.76, 83.98, 83.86, 84.3,
        83.95, 82.01, 82.18, 81.6, 80.38, 82.4, 84.93, 83.83, 79.59, 79.76,
        81.05, 84.49, 85.3, 86.69, 86.21, 84.06, 83.28, 85.51, 83.88, 84.8,
        85.34, 84.55, 86.68, 86.7, 86.3, 85.52, 85.8, 85.86, 84.94, 86.2,
        86.86, 87.92, 87.97, 87.02, 87.53, 87.95, 87.29, 88.47, 88.27, 88.7,
        88.4, 88.81, 88.09, 88.34, 87.81, 87.99, 87.53, 86.92, 86.95, 86.26,
        87.04, 88.13, 89.6, 88.34, 89.51, 91.53, 91.23, 91.67, 90.89, 89.97,
    ]
)  # fmt: skip

# name -> (first bar TA-Lib defines, {bar: TA-Lib value})
TALIB_REFERENCE = {
    "RSI_14": (14, {49: 53.025405, 60: 57.230422, 75: 55.419331, 89: 56.580041}),
    "MACD": (33, {49: 0.324295, 60: 0.66059, 75: 0.802313, 89: 1.061755}),
    "MACD_signal": (33, {49: 0.144858, 60: 0.580181, 75: 0.905791, 89: 0.865282}),
    "MACD_hist": (33, {49: 0.179438, 60: 0.080409, 75: -0.103478, 89: 0.196473}),
    "BB_upper": (19, {49: 87.376365, 60: 87.46431, 75: 89.608397, 89: 91.903857}),
    "BB_mid": (19, {49: 83.295, 60: 85.4485, 75: 87.511, 89: 88.7505}),
    "BB_lower": (19, {49: 79.213635, 60: 83.43269, 75: 85.413603, 89: 85.597143}),
    "SMA_20": (19, {49: 83.295, 60: 85.4485, 75: 87.511, 89: 88.7505}),
    "SMA_50": (49, {49: 83.8636, 60: 84.4168, 75: 85.3622, 89: 87.123}),
}


@pytest.fixture(scope="module")
def ours() -> pd.DataFrame:
    frame = pd.DataFrame({"close": OGDC_CLOSES, "high": OGDC_CLOSES, "low": OGDC_CLOSES})
    frame["volume"] = 1.0
    return add_technical_indicators(frame)


@pytest.mark.parametrize("name", list(TALIB_REFERENCE))
def test_indicator_matches_talib_reference(ours, name):
    first, values = TALIB_REFERENCE[name]
    for bar, expected in values.items():
        assert ours[name].iloc[bar] == pytest.approx(expected, abs=1e-5), (name, bar)
    if name == "MACD":
        # TA-Lib hides the MACD line until its signal exists (bar 33); the line itself is
        # defined from the slow EMA's first bar
        assert ours[name].first_valid_index() == 25
    else:
        assert ours[name].first_valid_index() == first


def test_rsi_matches_published_wilder_example():
    # StockCharts "RSI" ChartSchool worked example (Wilder's method), RSI(14) from row 14
    closes = pd.Series(
        [
            44.3389, 44.0902, 44.1497, 43.6124, 44.3278, 44.8264, 45.0955, 45.4245, 45.8433,
            46.0826, 45.8931, 46.0328, 45.6140, 46.2820, 46.2820, 46.0028, 46.0328, 46.4116,
            46.2222, 45.6439, 46.2122, 46.2521, 45.7137, 46.4515, 45.7835, 45.3548, 44.0288,
            44.1783, 44.2181, 44.5672, 43.4205, 42.6628, 43.1314,
        ]
    )  # fmt: skip
    published = [
        70.53, 66.32, 66.55, 69.41, 66.36, 57.97, 62.93, 63.26, 56.06, 62.38,
        54.71, 50.42, 39.99, 41.46, 41.87, 45.46, 37.30, 33.08, 37.77,
    ]  # fmt: skip
    assert rsi(closes).iloc[14:].round(2).tolist() == published
    assert rsi(closes).iloc[:14].isna().all()


def test_rsi_extremes_and_flat_window():
    up = pd.Series(np.arange(1, 40, dtype=float))
    assert rsi(up).iloc[-1] == pytest.approx(100.0)
    assert rsi(up[::-1].reset_index(drop=True)).iloc[-1] == pytest.approx(0.0)
    # Deliberate difference from TA-Lib (which reports 0): no movement reads as neutral
    assert rsi(pd.Series([50.0] * 30)).iloc[-1] == 50.0


def test_macd_bollinger_sma_on_a_constant_series():
    flat = pd.Series([50.0] * 60)
    line, signal, hist = macd(flat)
    assert line.dropna().abs().max() == pytest.approx(0.0)
    assert hist.dropna().abs().max() == pytest.approx(0.0)
    upper, mid, lower = bollinger(flat)
    assert upper.iloc[-1] == mid.iloc[-1] == lower.iloc[-1] == 50.0
    assert sma(flat, 20).iloc[-1] == 50.0


# ---- No lookahead: a feature row may only use data up to its own date


COLUMNS = FEATURE_COLUMNS + INDICATOR_COLUMNS


def test_no_feature_row_uses_data_after_its_own_date():
    """
    Rebuilding features from history cut at day t must (a) still produce a row for day t,
    which a forward-looking window would leave undefined, and (b) give every row up to t
    exactly the values it has when the full history is used.
    """
    full_raw = make_ohlcv(260)
    full = build_feature_frame(full_raw).set_index("date")
    for cut in range(60, 260, 7):
        partial = build_feature_frame(full_raw.iloc[: cut + 1]).set_index("date")
        assert partial.index[-1] == full_raw["date"].iloc[cut], f"no feature row for bar {cut}"
        np.testing.assert_allclose(
            partial[COLUMNS].to_numpy(dtype=float),
            full.loc[partial.index, COLUMNS].to_numpy(dtype=float),
            rtol=1e-9,
            err_msg=f"rows up to bar {cut} change when later data is added",
        )


def test_backward_dividend_adjustment_does_not_leak_into_features():
    """
    The backward adjustment rescales every bar before an ex-date, so on day t the series
    already 'knows' about later dividends. Features must be identical to the ones built
    with only the dividends known on day t: scale-free inputs make that true.
    """
    raw = make_ohlcv(260)
    dates = [d.date() for d in raw["date"]]
    ex_dates = [(dates[90], 0.95), (dates[150], 0.9), (dates[220], 0.97)]

    def features(known):
        frame = raw.assign(dividend_factor=cumulative_factors(dates, known))
        return build_feature_frame(dividend_adjusted(frame)).set_index("date")

    full = features(ex_dates)
    for cut in (100, 160, 230):
        day = pd.Timestamp(dates[cut])
        known_then = [(d, f) for d, f in ex_dates if d <= dates[cut]]
        np.testing.assert_allclose(
            features(known_then).loc[day, FEATURE_COLUMNS].to_numpy(dtype=float),
            full.loc[day, FEATURE_COLUMNS].to_numpy(dtype=float),
            rtol=1e-9,
        )
