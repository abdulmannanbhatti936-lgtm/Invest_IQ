import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from ml.features import FeatureEngineer
import logging

logger = logging.getLogger(__name__)

class PricePredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        # We will use these columns to predict
        self.feature_columns = ['RSI', 'MACD', 'MACD_Signal', 'MACD_Hist', 
                                'SMA_20', 'SMA_50', 'BB_Lower', 'BB_Mid', 'BB_Upper', 
                                'sentiment_score']

    def train(self, df: pd.DataFrame):
        """
        Trains the Random Forest model on historical feature data.
        Returns the accuracy on a test split for logging.
        """
        if df.empty or len(df) < 20:
            logger.warning("Not enough data to train prediction model.")
            return False, 0.0
            
        # Ensure we have all required features
        for col in self.feature_columns:
            if col not in df.columns:
                logger.warning(f"Missing feature {col} in dataframe.")
                return False, 0.0

        X = df[self.feature_columns]
        y = df['target_signal']
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        self.model.fit(X_train, y_train)
        accuracy = self.model.score(X_test, y_test)
        
        logger.info(f"Model trained successfully. Test Accuracy: {accuracy:.4f}")
        return True, accuracy

    def predict_latest(self, df: pd.DataFrame):
        """
        Predicts the signal for the most recent day in the dataframe.
        Returns: signal (BUY, SELL, HOLD), confidence_score (0.0 - 1.0)
        """
        if df.empty:
            return "HOLD", 0.0
            
        latest_row = df.iloc[-1:]
        X_latest = latest_row[self.feature_columns]
        
        prediction = self.model.predict(X_latest)[0]
        probabilities = self.model.predict_proba(X_latest)[0]
        confidence = max(probabilities)
        
        if prediction == 1:
            signal = "BUY"
        elif prediction == -1:
            signal = "SELL"
        else:
            signal = "HOLD"
            
        return signal, confidence

predictor = PricePredictor()
