import pandas as pd
import pandas_ta as ta
import numpy as np

class FeatureEngineer:
    @staticmethod
    def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes technical indicators for a given dataframe of OHLCV data.
        Assumes columns: open, high, low, close, volume.
        """
        if df.empty or len(df) < 50:
            return df
            
        # Ensure correct types
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Drop NaN closes
        df = df.dropna(subset=['close'])
        
        # Calculate RSI (14 periods)
        df.ta.rsi(length=14, append=True)
        df.rename(columns={'RSI_14': 'RSI'}, inplace=True)
        
        # Calculate MACD
        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.rename(columns={
            'MACD_12_26_9': 'MACD',
            'MACDs_12_26_9': 'MACD_Signal',
            'MACDh_12_26_9': 'MACD_Hist'
        }, inplace=True, errors='ignore')
            
        # Calculate Simple Moving Averages
        df.ta.sma(length=20, append=True)
        df.rename(columns={'SMA_20': 'SMA_20'}, inplace=True)
        
        df.ta.sma(length=50, append=True)
        df.rename(columns={'SMA_50': 'SMA_50'}, inplace=True)
        
        # Calculate Bollinger Bands
        df.ta.bbands(length=20, std=2, append=True)
        # pandas-ta bbands output format depends on versions, safely rename by looking at prefix
        for col in df.columns:
            if col.startswith('BBL_20'):
                df.rename(columns={col: 'BB_Lower'}, inplace=True)
            elif col.startswith('BBM_20'):
                df.rename(columns={col: 'BB_Mid'}, inplace=True)
            elif col.startswith('BBU_20'):
                df.rename(columns={col: 'BB_Upper'}, inplace=True)

        return df

    @staticmethod
    def prepare_training_data(price_points, sentiments=None) -> pd.DataFrame:
        """
        Convert ORM price points to a dataframe with features and sentiment.
        """
        data = [{
            "timestamp": p.timestamp,
            "open": float(p.open) if p.open else None,
            "high": float(p.high) if p.high else None,
            "low": float(p.low) if p.low else None,
            "close": float(p.close),
            "volume": float(p.volume) if p.volume else 0
        } for p in price_points]
        
        df = pd.DataFrame(data)
        if df.empty:
            return df
            
        df = df.sort_values(by="timestamp").reset_index(drop=True)
        
        # Normalize timestamps to date to merge sentiment
        df['date'] = df['timestamp'].dt.date
        
        # Compute TAs
        df = FeatureEngineer.compute_technical_indicators(df)
        
        # Calculate Target: Next day's return
        df['next_close'] = df['close'].shift(-1)
        df['target_return'] = (df['next_close'] - df['close']) / df['close']
        
        # Target Signal: 1 (BUY) if return > 1%, -1 (SELL) if return < -1%, else 0 (HOLD)
        df['target_signal'] = 0
        df.loc[df['target_return'] > 0.01, 'target_signal'] = 1
        df.loc[df['target_return'] < -0.01, 'target_signal'] = -1
        
        # Add sentiment
        if sentiments and len(sentiments) > 0:
            # Group sentiments by date
            sent_data = [{"date": s.timestamp.date(), "score": s.sentiment_score} for s in sentiments]
            sent_df = pd.DataFrame(sent_data)
            sent_df = sent_df.groupby('date')['score'].mean().reset_index()
            
            # Merge with price df
            df = pd.merge(df, sent_df, on='date', how='left')
            # Fill missing sentiments with 0.0 (Neutral)
            df['score'] = df['score'].fillna(0.0)
            df.rename(columns={'score': 'sentiment_score'}, inplace=True)
        else:
            df['sentiment_score'] = 0.0
            
        # Drop rows that have NaN from rolling windows or shifting
        df = df.dropna().reset_index(drop=True)
        return df
