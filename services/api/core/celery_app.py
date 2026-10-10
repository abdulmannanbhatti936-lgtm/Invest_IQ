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
    "refresh-eod-prices": {
        "task": "worker.tasks.refresh_stock_prices",
        # End of the PSX trading day (Mon-Fri). The last month is re-fetched so late
        # provider corrections are picked up; the provider runs ~1 trading day behind PSX.
        "schedule": crontab(hour=18, minute=0, day_of_week="mon-fri"),
        "kwargs": {"period": "1mo"},
    },
    "resync-prices-weekly": {
        "task": "worker.tasks.refresh_stock_prices",
        # Full 5-year window: re-applies split adjustments to stored history and refreshes
        # shares outstanding (used for market cap)
        "schedule": crontab(hour=6, minute=0, day_of_week="sun"),
        "kwargs": {"period": "5y", "update_shares": True},
    },
    "refresh-dividends-daily": {
        "task": "worker.tasks.refresh_dividends",
        # After the EOD price refresh: new ex-dates and re-assessment against current closes
        "schedule": crontab(hour=18, minute=15, day_of_week="mon-fri"),
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
        # Weekly retrain (PRD.md FR15), Saturday night: trains a candidate only; the live
        # model changes when a person promotes it (ml/promote.py)
        "schedule": crontab(hour=22, minute=0, day_of_week="sat"),
    },
}
