from celery import Celery
from celery.schedules import crontab

from core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["worker.tasks"],
)

celery_app.conf.timezone = "Asia/Karachi"
celery_app.conf.enable_utc = True

# Celery Beat Schedule (times are Pakistan Standard Time)
celery_app.conf.beat_schedule = {
    "refresh-intraday-prices": {
        "task": "worker.tasks.refresh_stock_prices",
        # Every 15 min during PSX market hours (Mon-Fri, 09:30-15:30 PKT)
        "schedule": crontab(minute="*/15", hour="9-15", day_of_week="mon-fri"),
        "kwargs": {"period": "5d"},
    },
    "fetch-eod-market-data": {
        "task": "worker.tasks.refresh_stock_prices",
        # End-of-day refresh of the full training window
        "schedule": crontab(hour=18, minute=0, day_of_week="mon-fri"),
        "kwargs": {"period": "5y"},
    },
    "fetch-hourly-news": {
        "task": "worker.tasks.fetch_news_for_tickers",
        "schedule": crontab(minute=0),
    },
    "analyze-hourly-news": {
        "task": "worker.tasks.analyze_news_sentiment",
        # Run at 5 minutes past the hour, right after fetching news
        "schedule": crontab(minute=5),
    },
    "run-daily-predictions": {
        "task": "worker.tasks.run_predictions",
        # After the EOD price refresh
        "schedule": crontab(hour=18, minute=30, day_of_week="mon-fri"),
    },
    "retrain-models-weekly": {
        "task": "worker.tasks.train_models",
        # Weekly retrain (PRD.md FR15), Saturday night
        "schedule": crontab(hour=22, minute=0, day_of_week="sat"),
    },
}
