import torch
import torch.nn as nn
import pandas as pd
import numpy as np
import logging
from sklearn.preprocessing import MinMaxScaler
from typing import Tuple

logger = logging.getLogger(__name__)

class LSTMModel(nn.Module):
    def __init__(self, input_size, hidden_layer_size=64, num_layers=2, output_size=1, dropout=0.2):
        super(LSTMModel, self).__init__()
        self.hidden_layer_size = hidden_layer_size
        
        self.lstm = nn.LSTM(
            input_size, 
            hidden_layer_size, 
            num_layers, 
            batch_first=True, 
            dropout=dropout if num_layers > 1 else 0
        )
        self.dropout = nn.Dropout(dropout)
        self.linear = nn.Linear(hidden_layer_size, output_size)
        
    def forward(self, input_seq):
        lstm_out, _ = self.lstm(input_seq)
        # Take the output from the last time step
        last_time_step_out = lstm_out[:, -1, :]
        out = self.dropout(last_time_step_out)
        predictions = self.linear(out)
        return predictions

class LSTMPipeline:
    def __init__(self, seq_length=60):
        self.seq_length = seq_length
        self.model = None
        self.feature_scaler = MinMaxScaler()
        self.target_scaler = MinMaxScaler()
        self.feature_columns = [
            'close', 'RSI', 'MACD', 'MACD_Signal', 'MACD_Hist', 
            'SMA_20', 'SMA_50', 'BB_Lower', 'BB_Mid', 'BB_Upper', 
            'sentiment_score'
        ]
        
    def create_sequences(self, data, target, seq_length):
        xs, ys = [], []
        for i in range(len(data) - seq_length):
            x = data[i:(i + seq_length)]
            y = target[i + seq_length]
            xs.append(x)
            ys.append(y)
        return np.array(xs), np.array(ys)
        
    def train(self, df: pd.DataFrame, epochs=50, lr=0.001) -> Tuple[bool, float]:
        """
        Trains the LSTM model on historical feature data.
        Returns the RMSE on a test split for logging.
        """
        if df.empty or len(df) <= self.seq_length:
            logger.warning("Not enough data to train LSTM prediction model.")
            return False, 0.0
            
        for col in self.feature_columns:
            if col not in df.columns:
                logger.warning(f"Missing feature {col} in dataframe.")
                return False, 0.0
                
        # We predict the next close price instead of signal
        if 'next_close' not in df.columns:
            df['next_close'] = df['close'].shift(-1)
            
        df = df.dropna()
        if df.empty:
            return False, 0.0
            
        feature_data = df[self.feature_columns].values
        target_data = df[['next_close']].values
        
        scaled_features = self.feature_scaler.fit_transform(feature_data)
        scaled_targets = self.target_scaler.fit_transform(target_data)
        
        X, y = self.create_sequences(scaled_features, scaled_targets, self.seq_length)
        
        if len(X) < 10:
            logger.warning("Not enough sequences to train LSTM.")
            return False, 0.0
            
        # Chronological train/test split (80/20)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        X_train = torch.tensor(X_train, dtype=torch.float32)
        y_train = torch.tensor(y_train, dtype=torch.float32)
        X_test = torch.tensor(X_test, dtype=torch.float32)
        y_test = torch.tensor(y_test, dtype=torch.float32)
        
        self.model = LSTMModel(input_size=len(self.feature_columns))
        criterion = nn.MSELoss()
        optimizer = torch.optim.Adam(self.model.parameters(), lr=lr)
        
        self.model.train()
        for epoch in range(epochs):
            optimizer.zero_grad()
            y_pred = self.model(X_train)
            loss = criterion(y_pred, y_train)
            loss.backward()
            optimizer.step()
            
        # Evaluate RMSE
        self.model.eval()
        with torch.no_grad():
            test_preds = self.model(X_test)
            # Scale back to original values for interpretable RMSE
            test_preds_actual = self.target_scaler.inverse_transform(test_preds.numpy())
            y_test_actual = self.target_scaler.inverse_transform(y_test.numpy())
            rmse = float(np.sqrt(np.mean((test_preds_actual - y_test_actual)**2)))
            
        logger.info(f"LSTM Model trained successfully. Test RMSE: {rmse:.4f}")
        return True, rmse
        
    def predict_latest(self, df: pd.DataFrame) -> Tuple[float, float, str]:
        """
        Predicts the next closing price for the most recent window in the dataframe.
        Returns: predicted_price, confidence_score (0.0 - 1.0), direction (BUY, SELL, HOLD)
        """
        if self.model is None or df.empty or len(df) < self.seq_length:
            return 0.0, 0.0, "HOLD"
            
        latest_window = df[self.feature_columns].iloc[-self.seq_length:].values
        scaled_window = self.feature_scaler.transform(latest_window)
        
        X_latest = torch.tensor(np.array([scaled_window]), dtype=torch.float32)
        
        self.model.eval()
        with torch.no_grad():
            prediction_scaled = self.model(X_latest)
            predicted_price = self.target_scaler.inverse_transform(prediction_scaled.numpy())[0][0]
            
        current_price = latest_window[-1][0] # 'close' is the first feature
        
        predicted_return = (predicted_price - current_price) / current_price
        
        if predicted_return > 0.01:
            direction = "BUY"
        elif predicted_return < -0.01:
            direction = "SELL"
        else:
            direction = "HOLD"
            
        # Confidence heuristic based on magnitude of the predicted return
        confidence = min(abs(predicted_return) * 10, 0.95)
        if direction == "HOLD":
            confidence = 0.5
            
        return float(predicted_price), float(confidence), direction

lstm_predictor = LSTMPipeline()
