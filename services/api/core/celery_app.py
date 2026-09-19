from celery import Celery
from core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

from celery.schedules import crontab

celery_app.conf.task_routes = {
    "worker.tasks.*": {"queue": "main-queue"}
}

# Celery Beat Schedule
celery_app.conf.beat_schedule = {
    "fetch-eod-market-data": {
        "task": "worker.tasks.fetch_market_data_for_tickers",
        # Run daily at 18:00 (6 PM) to get End of Day data
        "schedule": crontab(hour=18, minute=0),
    },
    "fetch-hourly-news": {
        "task": "worker.tasks.fetch_news_for_tickers",
        # Run every hour to get fresh headlines
        "schedule": crontab(minute=0),
    },
    "analyze-hourly-news": {
        "task": "worker.tasks.analyze_news_sentiment",
        # Run at 5 minutes past the hour, right after fetching news
        "schedule": crontab(minute=5),
    },
}
