from fastapi.testclient import TestClient
from main import app
from core.deps import get_current_user
from core.database import SessionLocal
from models.stock import Stock
from models.prediction import Prediction

def override_get_current_user():
    return {"id": 1, "email": "test@example.com"}

app.dependency_overrides[get_current_user] = override_get_current_user

client = TestClient(app)

db = SessionLocal()
stock = db.query(Stock).filter(Stock.ticker == "SYS").first()
if not stock:
    stock = Stock(ticker="SYS", name="Systems Limited", sector="Technology")
    db.add(stock)
    db.commit()
    db.refresh(stock)

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

headers = {"Authorization": "Bearer fake-token"}
response = client.get("/stocks/SYS/prediction", headers=headers)
print("Status code:", response.status_code)
print("Response:", response.json())
