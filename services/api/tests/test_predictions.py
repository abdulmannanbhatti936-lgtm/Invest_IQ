import pytest
from fastapi.testclient import TestClient
from main import app
from core.database import SessionLocal
from models.stock import Stock
from models.prediction import Prediction
from core.security import create_access_token
from core.deps import get_current_user
import datetime

client = TestClient(app)

def override_get_current_user():
    return {"id": 1, "email": "test@example.com"}

@pytest.fixture(autouse=True)
def override_dependency():
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.clear()

@pytest.fixture(scope="module")
def setup_db():
    db = SessionLocal()
    
    # Check if SYS stock exists
    stock = db.query(Stock).filter(Stock.ticker == "SYS").first()
    if not stock:
        stock = Stock(ticker="SYS", name="Systems Limited", sector="Technology")
        db.add(stock)
        db.commit()
        db.refresh(stock)
        
    # Check if prediction exists
    pred = db.query(Prediction).filter(Prediction.stock_id == stock.id).first()
    if not pred:
        pred = Prediction(
            stock_id=stock.id,
            predicted_price=550.0,
            signal="BUY",
            confidence_score=0.85,
            model_version="v1.0"
        )
        db.add(pred)
        db.commit()

    # Also add a low confidence prediction for another stock to test FR16
    stock_low = db.query(Stock).filter(Stock.ticker == "LOWCONF").first()
    if not stock_low:
        stock_low = Stock(ticker="LOWCONF", name="Low Conf Stock", sector="Unknown")
        db.add(stock_low)
        db.commit()
        db.refresh(stock_low)
        
    pred_low = db.query(Prediction).filter(Prediction.stock_id == stock_low.id).first()
    if not pred_low:
        pred_low = Prediction(
            stock_id=stock_low.id,
            predicted_price=10.0,
            signal="HOLD",
            confidence_score=0.3,
            model_version="v1.0"
        )
        db.add(pred_low)
        db.commit()
        
    yield
    db.close()


def test_get_stock_prediction(setup_db):
    headers = {"Authorization": "Bearer fake-token"}
    response = client.get("/stocks/SYS/prediction", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_price"] == 550.0
    assert data["signal"] == "BUY"
    assert data["confidence_score"] == 0.85
    assert data["model_version"] == "v1.0"


def test_get_stock_prediction_low_confidence(setup_db):
    headers = {"Authorization": "Bearer fake-token"}
    response = client.get("/stocks/LOWCONF/prediction", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["predicted_price"] == 10.0
    assert data["signal"] == "HOLD"
    assert data["confidence_score"] == 0.3
    # Check that confidence_score is below threshold (e.g., 0.5)
    assert data["confidence_score"] < 0.5


def test_get_prediction_not_found(setup_db):
    headers = {"Authorization": "Bearer fake-token"}
    response = client.get("/stocks/UNKNOWN/prediction", headers=headers)
    assert response.status_code == 404
