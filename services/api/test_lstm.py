import sys
import os

# Ensure the correct path is in sys.path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from core.database import SessionLocal
from models.stock import Stock
from ml.features import FeatureEngineer
from ml.lstm_predictor import lstm_predictor
import logging
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_test():
    db = SessionLocal()
    try:
        # Get AAPL
        stock = db.query(Stock).filter(Stock.ticker == "AAPL").first()
        if not stock:
            print("AAPL not found.")
            return
            
        print(f"Found stock: {stock.ticker} with {len(stock.price_points)} price points")
        
        df = FeatureEngineer.prepare_training_data(stock.price_points, stock.sentiments)
        print(f"Engineered features. DataFrame shape: {df.shape}")
        
        success, rmse = lstm_predictor.train(df)
        if success:
            print(f"LSTM Training succeeded with RMSE: {rmse}")
            
            # Predict
            pred_price, conf, signal = lstm_predictor.predict_latest(df)
            print(f"LATEST PREDICTION: Price {pred_price:.2f}, Signal {signal}, Confidence {conf:.2f}")
        else:
            print("Training failed.")
            
    finally:
        db.close()

if __name__ == "__main__":
    run_test()
