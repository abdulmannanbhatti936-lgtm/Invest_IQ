"""The Phase 4 experiment's analyses and the versioned news dataset, on MOCK data only."""

import datetime
from decimal import Decimal

import pytest

from ml import sentiment_experiment as experiment
from ml.news_dataset import NewsDatasetError, build_news_dataset, load_news_dataset
from ml.training import RF_PARAMS, fit_candidate
from models.sentiment import SentimentScore
from tests.fixtures.build_model_fixture import mock_headlines, mock_prices
from tests.test_predictions import mock_stock

SMALL = {
    "run_walk_forward": True,
    "lstm_epochs": 1,
    "rf_base": {**RF_PARAMS, "n_estimators": 5, "max_depth": 3},
    "rf_grid": {"min_samples_leaf": (5, 20)},
}
DATASET = {"version": "MOCK", "sha256": {}}
NEWS = {"version": "MOCK-news", "sources": ["profit", "mettis"], "scorer_versions": ["MOCK"]}


@pytest.fixture(scope="module")
def pair():
    prices = mock_prices()
    price = fit_candidate(prices, DATASET, version="MOCK-price", **SMALL)
    news = fit_candidate(
        prices, DATASET, version="MOCK-news", headlines=mock_headlines(prices), news=NEWS, **SMALL
    )
    return price, news


def test_news_inputs_change_the_news_models_own_forecasts(pair):
    _, news = pair
    ablation = experiment._ablation(news)
    assert ablation["rows"] > 0
    assert ablation["lstm_mean_abs_change_pct_points"] > 0


def test_both_models_are_compared_on_the_same_news_days(pair):
    price, news = pair
    days = experiment._news_days(price, news)
    assert days["price_only"]["rows"] == days["with_news"]["rows"] > 0


def test_promotion_needs_both_validation_measures():
    def variant(rmse, balanced):
        return {"validation": {"lstm_rmse_pct": rmse, "rf_balanced_accuracy": balanced}}

    assert experiment._decision(variant(2.0, 0.40), variant(1.9, 0.41))["promote_news_model"]
    assert not experiment._decision(variant(2.0, 0.40), variant(1.9, 0.39))["promote_news_model"]
    assert not experiment._decision(variant(2.0, 0.40), variant(2.1, 0.45))["promote_news_model"]


def test_report_is_written_for_both_horizons(pair, tmp_path):
    price, news = pair
    variants = {
        name: experiment._headline_metrics(c)
        for name, c in (
            ("price_1d", price),
            ("news_1d", news),
            ("price_5d", price),
            ("news_5d", news),
        )
    }
    result = {
        "price_dataset": "MOCK",
        "news_dataset": NEWS | {"sha256": "MOCK"},
        "live_model": "MOCK-live",
        "price_1d_reproduces_live_model": False,
        "variants": variants,
        "coverage_share_of_rows_with_news": experiment._coverage(news),
        "decision_1d": experiment._decision(variants["price_1d"], variants["news_1d"]),
        "news_days_1d": experiment._news_days(price, news),
        "news_days_5d": experiment._news_days(price, news),
        "ablation_1d": experiment._ablation(news),
        "ablation_5d": experiment._ablation(news),
        "feature_importance_news_1d": news.metadata["random_forest"]["feature_importance"],
    }
    text = experiment.write_experiment_report(result, tmp_path / "report.md").read_text()
    assert "## Next trading day" in text and "## Five trading days" in text
    assert "Do not promote" in text or "Promote" in text


def _scored(db, stock, url, score):
    db.add(
        SentimentScore(
            stock_id=stock.id,
            source="profit",
            url=url,
            headline="MOCK_ headline",
            published_at=datetime.datetime(2026, 1, 5, 6, tzinfo=datetime.timezone.utc),
            score=None if score is None else Decimal(str(score)),
            label=None if score is None else "positive",
            scorer=None if score is None else "finbert",
            scorer_version=None if score is None else "MOCK",
        )
    )
    db.commit()


def test_news_dataset_round_trip_without_headline_text(db, tmp_path):
    stock = mock_stock(db)
    _scored(db, stock, "https://example.com/MOCK/1", 0.5)
    path = build_news_dataset(db, ["MOCKA"], tmp_path)
    assert "MOCK_ headline" not in (path / "headlines.csv").read_text()
    manifest, frames = load_news_dataset(path)
    assert manifest["rows"] == 1 and manifest["rows_per_ticker"] == {"MOCKA": 1}
    assert frames["MOCKA"]["score"].tolist() == [0.5]

    (path / "headlines.csv").write_text("tampered\n")
    with pytest.raises(NewsDatasetError, match="hash"):
        load_news_dataset(path)


def test_news_dataset_refuses_unscored_headlines(db, tmp_path):
    stock = mock_stock(db)
    _scored(db, stock, "https://example.com/MOCK/2", None)
    with pytest.raises(NewsDatasetError, match="not scored"):
        build_news_dataset(db, ["MOCKA"], tmp_path)
