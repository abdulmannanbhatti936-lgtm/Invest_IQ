# sentiment-engine

FinBERT + VADER pipeline and news scrapers (Architecture.md §6.3), built in Phase 4.

Per Architecture.md §6.5 it runs as an internal module of `services/api`, not as a separate
network service. The code lives in:

- `services/api/integrations/news/`: polite fetching, the Profit, Mettis Global and Business
  Recorder clients, and headline-to-ticker matching
- `services/api/services/news_ingestion.py`: collection into `sentiment_scores` (live job and backfill)
- `services/api/ml/sentiment.py`: FinBERT scoring with the VADER fallback
- `services/api/services/sentiment_service.py`: scoring, source freshness and the API payload
