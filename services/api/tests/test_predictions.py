import uuid
from decimal import Decimal

import pytest

from core.config import settings
from core.deps import get_current_user
from main import app
from models.prediction import Prediction
from models.stock import Stock
from tests.conftest import make_ohlcv
from worker.tasks import run_predictions, upsert_price_points


@pytest.fixture(autouse=True)
def authenticated():
    app.dependency_overrides[get_current_user] = lambda: object()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def make_stock(db):
    created = []

    def _make(ticker_prefix="T"):
        stock = Stock(
            ticker=f"{ticker_prefix}{uuid.uuid4().hex[:8].upper()}", name="Test Co", sector="Test"
        )
        db.add(stock)
        db.commit()
        db.refresh(stock)
        created.append(stock)
        return stock

    yield _make
    for stock in created:
        db.delete(stock)
    db.commit()


def add_prediction(
    db, stock, *, confidence, signal="BUY", last_close=100.0, forecast=101.5, version="test-v1"
):
    db.add(
        Prediction(
            stock_id=stock.id,
            model_version=version,
            forecast_price=Decimal(str(forecast)),
            last_close=Decimal(str(last_close)),
            signal=signal,
            confidence_score=Decimal(str(confidence)),
        )
    )
    db.commit()


def test_high_confidence_prediction(client, db, make_stock):
    stock = make_stock()
    add_prediction(db, stock, confidence=0.85)
    response = client.get(f"/stocks/{stock.ticker}/prediction")
    assert response.status_code == 200
    data = response.json()
    assert data["signal"] == "BUY"
    assert data["forecast_price"] == 101.5
    assert data["expected_change_pct"] == pytest.approx(1.5)
    assert data["confidence_score"] == 0.85
    assert data["models_agree"] is True
    assert data["low_confidence"] is False
    assert data["low_confidence_threshold"] == settings.LOW_CONFIDENCE_THRESHOLD == 0.6


def test_low_confidence_flag_below_threshold(client, db, make_stock):  # PRD.md FR16
    stock = make_stock()
    add_prediction(db, stock, confidence=0.55)
    data = client.get(f"/stocks/{stock.ticker}/prediction").json()
    assert data["low_confidence"] is True


def test_low_confidence_flag_when_models_disagree(client, db, make_stock):
    stock = make_stock()
    add_prediction(db, stock, confidence=0.9, signal="BUY", forecast=98.0)
    data = client.get(f"/stocks/{stock.ticker}/prediction").json()
    assert data["models_agree"] is False
    assert data["low_confidence"] is True


def test_latest_prediction_wins(client, db, make_stock):
    stock = make_stock()
    add_prediction(db, stock, confidence=0.7, signal="SELL", forecast=97.0)
    add_prediction(db, stock, confidence=0.8, signal="BUY", forecast=103.0)
    assert client.get(f"/stocks/{stock.ticker}/prediction").json()["signal"] == "BUY"


def test_unknown_stock(client):
    response = client.get("/stocks/NOSUCHSTOCK/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "stock_not_found"


def test_insufficient_data_message(client, make_stock):  # PRD.md FR10
    stock = make_stock()
    response = client.get(f"/stocks/{stock.ticker}/prediction")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "insufficient_data"


def test_end_to_end_job_to_endpoint(client, db, make_stock, trained_model_dir, monkeypatch):
    """run_predictions loads the saved model, stores a row, the endpoint serves it."""
    stock = make_stock("E2E")
    raw = make_ohlcv(400)
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
    assert upsert_price_points(db, stock, history) == 400
    assert upsert_price_points(db, stock, history[-5:]) == 5  # idempotent upsert

    # Point the stock at the synthetic model
    import shutil

    shutil.copytree(trained_model_dir.path / "SYNTH", trained_model_dir.path / stock.ticker)
    monkeypatch.setattr(settings, "MODEL_DIR", str(trained_model_dir.path))

    not_ready = client.get(f"/stocks/{stock.ticker}/prediction")
    assert not_ready.json()["detail"]["code"] == "not_ready"

    result = run_predictions([stock.ticker])
    assert result["predictions_made"] == 1, result

    data = client.get(f"/stocks/{stock.ticker}/prediction").json()
    assert data["model_version"] == "test-v1"
    assert data["last_close"] == pytest.approx(raw["close"].iloc[-1], rel=1e-4)
    assert data["evaluation"]["lstm_rmse_pct"] > 0
    assert len(data["evaluation"]["top_features"]) == 3
