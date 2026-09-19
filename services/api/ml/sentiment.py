import logging
from transformers import pipeline

logger = logging.getLogger(__name__)

class FinBERTSentimentModel:
    """
    Wrapper around HuggingFace's FinBERT model (ProsusAI/finbert)
    specifically trained for financial sentiment analysis.
    """
    def __init__(self):
        logger.info("Initializing FinBERT model. This might take a while if downloading weights...")
        try:
            # We use 'ProsusAI/finbert' as it's the industry standard for financial text.
            # Labels: 'positive', 'negative', 'neutral'
            self.model = pipeline("sentiment-analysis", model="ProsusAI/finbert")
            logger.info("FinBERT model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load FinBERT model: {e}")
            self.model = None

    def analyze_headline(self, text: str) -> float:
        """
        Analyzes a single financial headline.
        Returns a float between -1.0 (highly negative) to +1.0 (highly positive).
        Neutral is mapped to 0.0.
        """
        if not self.model:
            logger.warning("FinBERT model not loaded. Returning default 0.0 score.")
            return 0.0
            
        try:
            result = self.model(text)[0]
            label = result['label']
            score = result['score']
            
            # Map probabilities to our [-1.0, 1.0] scale
            if label == 'positive':
                return round(float(score), 4)
            elif label == 'negative':
                return round(-float(score), 4)
            else:
                return 0.0
        except Exception as e:
            logger.error(f"Error during sentiment analysis of text '{text}': {e}")
            return 0.0

# Singleton instance for the app lifecycle
sentiment_model = FinBERTSentimentModel()
