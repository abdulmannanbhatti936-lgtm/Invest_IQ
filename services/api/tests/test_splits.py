import pandas as pd
import pytest

from ml.splits import assign_periods, shared_cut_dates, walk_forward_folds


def calendar(n: int) -> pd.Series:
    return pd.Series(pd.bdate_range("2022-01-03", periods=n))


def test_shared_cut_dates_come_from_the_union_of_trading_dates():
    a = calendar(100)
    b = calendar(100).iloc[::2]  # a ticker with gaps does not move the cut dates
    cuts = shared_cut_dates(pd.concat([a, b]))
    assert cuts.val_start == a.iloc[70] and cuts.test_start == a.iloc[85]
    assert cuts.test_end == a.iloc[-1]


def test_periods_are_chronological_and_purged_at_boundaries():
    dates = calendar(100)
    periods = assign_periods(dates, shared_cut_dates(dates))
    train = dates[periods == "train"]
    val = dates[periods == "val"]
    test = dates[periods == "test"]
    assert train.max() < val.min() and val.max() < test.min()
    # The last train row (labelled with the first val close) and last val row are purged
    assert periods.isna().sum() == 2
    assert list(periods.iloc[68:72]) == ["train", None, "val", "val"]
    assert len(test) == 15


def test_a_ticker_starting_late_gets_no_train_rows_before_its_history():
    dates = calendar(100)
    cuts = shared_cut_dates(dates)
    late = dates.iloc[80:].reset_index(drop=True)
    periods = assign_periods(late, cuts)
    assert set(periods.dropna()) == {"val", "test"}


def test_walk_forward_folds_expand_and_never_overlap():
    dates = calendar(300)
    folds = walk_forward_folds(dates, n_folds=3, test_frac=0.30)
    assert len(folds) == 3
    for earlier, later in zip(folds, folds[1:], strict=False):
        assert earlier.test_end < later.test_start  # test blocks are disjoint, in order
        assert earlier.val_start < later.val_start  # training window grows
    assert folds[-1].test_end == dates.iloc[-1]
    for fold in folds:
        periods = assign_periods(dates, fold)
        assert dates[periods == "train"].max() < dates[periods == "val"].min()
        assert dates[periods == "val"].max() < dates[periods == "test"].min()
        assert (periods == "test").sum() == 30


def test_walk_forward_rejects_too_few_dates():
    with pytest.raises(ValueError):
        walk_forward_folds(calendar(4), n_folds=3)


def test_a_five_day_horizon_purges_five_rows_before_each_boundary():
    dates = calendar(100)
    periods = assign_periods(dates, shared_cut_dates(dates), horizon=5)
    assert periods.isna().sum() == 10
    assert list(periods.iloc[64:71]) == ["train", None, None, None, None, None, "val"]
