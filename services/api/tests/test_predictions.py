import datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from core.config import settings
from core.deps import get_current_user
from main import app
from ml.inference import load_bundle
from models.prediction import Prediction
from models.stock import PricePoint, Stock
from services.prediction_service import (
    BELOW_THRESHOLD,
    MODELS_DISAGREE,
    NO_EDGE_OVER_BASELINE,
    generate_prediction,
    low_confidence_reasons,
)
from tests.fixtures.build_model_fixture import FIXTURE_DIR, FIXTURE_VERSION
from tests.synthetic import make_ohlcv
from worker.tasks import run_predictions, upsert_price_points


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def mock_model(monkeypatch, fake_redis):
    """The frozen MOCK fixture model is the current model; it covers MOCKA/MOCKB/MOCKC."""
    monkeypatch.setattr(settings, "MODEL_DIR", str(FIXTURE_DIR))
    return load_bundle(FIXTURE_DIR)


@pytest.fixture
def edge(monkeypatch, mock_model):
    """Set whether the model beat the naive forecast for MOCKA on the test period."""

    def _set(beats: bool):
        monkeypatch.setitem(
            mock_model.metadata["evaluation"]["per_ticker"]["MOCKA"], "beats_naive", beats
        )

    return _set


def mock_stock(db, ticker="MOCKA") -> Stock:
    stock = Stock(ticker=ticker, name=f"{ticker} (MOCK test stock)", sector="Test")
    db.add(stock)
    db.commit()
    return stock


def store_history(db, stock, days=400, seed=7) -> list[dict]:
    raw = make_ohlcv(days, seed=seed)
    history = [
        {
            "timestamp": d.tz_localize("Asia/Karachi").to_pydatetime(),
            "open": o,
            "high": h,
            "low": low,
            "close": c,
            "volume": int(v),
        }
        for d, o, h, low, c, v in raw[
            ["date", "open", "high", "low", "close", "volume"]
        ].itertuples(index=False)
    ]
    upsert_price_points(db, stock, history)
    return history


def add_prediction(
    db,
    stock,
    *,
    confidence,
    signal="BUY",
    last_close=100.0,
    forecast=101.5,
    version=FIXTURE_VERSION,
):
    db.add(
        Prediction(
            stock_id=stock.id,
            model_version=version,
            forecast_price=Decimal(str(forecast)),
            last_close=Decimal(str(last_close)),
            confidence_score=Decimal(str(confidence)),
            signal=signal,
            signal_probability=Decimal("0.55"),
            as_of_date=datetime.date(2026, 10, 7),
        )
    )
    db.commit()


# ---- Low-confidence rules (PRD.md FR16)


def stub(beats_naive: bool | None):
    evaluation = None if beats_naive is None else {"beats_naive": beats_naive}
    return SimpleNamespace(ticker_evaluation=lambda ticker: evaluation)


def row(confidence, signal="BUY", forecast=101.5):
    return SimpleNamespace(
        confidence_score=Decimal(str(confidence)),
        signal=signal,
        forecast_price=Decimal(str(forecast)),
        last_close=Decimal("100"),
    )


@pytest.mark.parametrize(
    "prediction, beats, expected",
    [
        (row(0.65), True, []),
        (row(0.60), True, []),  # the threshold itself is not low
        (row(0.59), True, [BELOW_THRESHOLD]),
        (row(0.7, signal="BUY", forecast=98.0), True, [MODELS_DISAGREE]),
        (row(0.7), False, [NO_EDGE_OVER_BASELINE]),
        (row(0.7), None, [NO_EDGE_OVER_BASELINE]),  # not evaluated: never shown as confident
        (row(0.5, signal="SELL"), False, [BELOW_THRESHOLD, MODELS_DISAGREE, NO_EDGE_OVER_BASELINE]),
    ],
)
def test_low_confidence_rules(prediction, beats, expected):
    assert low_confidence_reasons(prediction, stub(beats), "MOCKA") == expected


# ---- Endpoint


def test_confident_prediction(client, db, mock_model, edge):
    edge(True)
    stock = mock_stock(db)
    add_prediction(db, stock, confidence=0.72)
    response = client.get("/stocks/MOCKA/prediction")
    assert response.status_code == 200
    data = response.json()
    assert data["model_version"] == FIXTURE_VERSION
    assert data["as_of_date"] == "2026-10-07"
    assert data["forecast_price"] == 101.5
    assert data["expected_change_pct"] == pytest.approx(1.5)
    assert data["confidence_score"] == 0.72 and data["signal_probability"] == 0.55
    assert data["low_confidence"] is False and data["low_confidence_reasons"] == []
    assert data["low_confidence_threshold"] == settings.LOW_CONFIDENCE_THRESHOLD == 0.6
    assert data["models_agree"] is True
    ev = data["evaluation"]
    assert ev["beats_naive"] is True and len(ev["top_features"]) == 3
    expected_error = mock_model.ticker_evaluation("MOCKA")["lstm_rmse_pct"]
    assert ev["typical_error_pct"] == pytest.approx(expected_error)
    assert ev["baseline_direction"] in {"up", "down"}


def test_flagged_prediction_lists_every_reason(client, db, mock_model, edge):
    edge(False)
    stock = mock_stock(db)
    add_prediction(db, stock, confidence=0.55, signal="BUY", forecast=98.0)
    data = client.get("/stocks/MOCKA/prediction").json()
    assert data["low_confidence"] is True
    assert data["low_confidence_reasons"] == [
        BELOW_THRESHOLD,
        MODELS_DISAGREE,
        NO_EDGE_OVER_BASELINE,
    ]
    assert data["models_agree"] is False


def test_latest_prediction_of_the_current_model_wins(client, db, mock_model):
    stock = mock_stock(db)
    add_prediction(db, stock, confidence=0.7, signal="SELL", forecast=97.0)
    add_prediction(db, stock, confidence=0.8, signal="BUY", forecast=103.0)
    assert client.get("/stocks/MOCKA/prediction").json()["signal"] == "BUY"


def test_older_model_rows_are_never_served(client, db, mock_model):
    stock = mock_stock(db)
    store_history(db, stock)
    add_prediction(db, stock, confidence=0.9, version="lstm-rf-20261008T191201Z")
    response = client.get("/stocks/MOCKA/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_ready"


def test_stock_outside_the_model_has_no_forecast(client, db, mock_model):
    # HBL is a real catalog stock, but the current model was not trained on it
    response = client.get("/stocks/HBL/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_covered"


def test_without_a_model_coverage_follows_the_tracked_list(
    client, db, monkeypatch, tmp_path, fake_redis
):
    monkeypatch.setattr(settings, "MODEL_DIR", str(tmp_path))
    assert client.get("/stocks/MCB/prediction").json()["detail"]["code"] == "not_covered"
    assert client.get("/stocks/HBL/prediction").json()["detail"]["code"] == "insufficient_data"


def test_unknown_stock(client, mock_model):
    response = client.get("/stocks/NOSUCHSTOCK/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "stock_not_found"


def test_insufficient_data_message(client, db, mock_model):  # PRD.md FR10
    mock_stock(db)
    response = client.get("/stocks/MOCKA/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "insufficient_data"


# ---- Prediction job


def test_job_uses_served_split_adjusted_closes_only(db, mock_model):
    """Regression: generate_prediction used raw closes, flagged bars included."""
    stock = mock_stock(db)
    history = store_history(db, stock)
    db.query(PricePoint).filter(PricePoint.stock_id == stock.id).update({"split_factor": 2})
    db.add(
        PricePoint(
            stock_id=stock.id,
            timestamp=history[-1]["timestamp"] + datetime.timedelta(days=3),
            close=99999,
            volume=1,
            quality_flag="mixed_split_level",
        )
    )
    db.commit()

    prediction = generate_prediction(db, stock, mock_model)
    assert float(prediction.last_close) == pytest.approx(history[-1]["close"] / 2, rel=1e-4)
    assert prediction.as_of_date == history[-1]["timestamp"].date()
    assert prediction.signal_probability is not None


def test_end_to_end_job_to_endpoint(client, db, mock_model):
    stock = mock_stock(db)
    history = store_history(db, stock)
    assert client.get("/stocks/MOCKA/prediction").json()["detail"]["code"] == "not_ready"

    result = run_predictions(["MOCKA", "MOCKB", "HBL"])
    assert result["predictions_made"] == 1, result
    assert set(result["skipped"]) == {"MOCKB", "HBL"}  # no stock row / not covered

    data = client.get("/stocks/MOCKA/prediction").json()
    assert data["model_version"] == FIXTURE_VERSION
    assert data["last_close"] == pytest.approx(history[-1]["close"], rel=1e-4)
    assert data["as_of_date"] == history[-1]["timestamp"].date().isoformat()
    assert 0 <= data["confidence_score"] <= 1


def test_job_without_a_model_reports_it(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "MODEL_DIR", str(tmp_path))
    assert run_predictions()["status"] == "no_model"
