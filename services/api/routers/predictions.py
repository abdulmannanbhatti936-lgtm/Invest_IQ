from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from models.stock import Stock
from models.prediction import Prediction
from ml.features import FeatureEngineer
from ml.predictor import predictor
from routers.users import get_current_user

router = APIRouter(prefix="/stocks", tags=["Predictions"])

@router.get("/{ticker}/prediction")
def get_stock_prediction(ticker: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """
    Retrieves the latest prediction for a specific stock.
    If no prediction exists, or data is fresh, it calculates it on the fly and saves it.
    """
    stock = db.query(Stock).filter(Stock.ticker == ticker).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
        
    # Grab historical price points
    price_points = stock.price_points
    if len(price_points) < 50:
        raise HTTPException(status_code=400, detail="Not enough historical data to generate predictions (min 50 days required).")
        
    sentiments = stock.sentiments
    
    # Engineer Features
    df = FeatureEngineer.prepare_training_data(price_points, sentiments)
    
    # Train the baseline model (in reality, you'd load a pre-trained model, but Random Forest is fast enough to fit on the fly for a prototype)
    success, accuracy = predictor.train(df)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to train prediction model")
        
    # Get latest prediction
    signal, confidence = predictor.predict_latest(df)
    latest_close = df.iloc[-1]['close']
    
    # Predict rough price movement (just a baseline example for the regressor value)
    predicted_price = float(latest_close * 1.05) if signal == "BUY" else float(latest_close * 0.95) if signal == "SELL" else float(latest_close)
    
    # Save prediction to database
    prediction = Prediction(
        stock_id=stock.id,
        predicted_price=predicted_price,
        signal=signal,
        confidence_score=confidence,
        model_version="v1.0-random-forest"
    )
    db.add(prediction)
    db.commit()
    db.refresh(prediction)
    
    return {
        "ticker": ticker,
        "signal": signal,
        "confidence": confidence,
        "predicted_price": predicted_price,
        "model_accuracy": accuracy,
        "timestamp": prediction.timestamp
    }
