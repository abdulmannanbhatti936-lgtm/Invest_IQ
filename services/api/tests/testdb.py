"""
The separate test database, shared by pytest (conftest.py) and the Playwright E2E run.

    python -m tests.testdb prepare        # create + migrate <db>_test
    python -m tests.testdb serve --port 8001 --cors-origin http://localhost:5174 [--mock-market]
    python -m tests.testdb cleanup-e2e    # delete E2E accounts, print what is left
    python -m tests.testdb clear-e2e-market   # remove the MOCK market (tests/e2e_market.py)
    python -m tests.testdb e2e-agent --email e2e_...@example.com   # MOCK sell change + agent run

Importing this module points `settings.DATABASE_URL` at the test database, so it must be
imported before core.database creates its engine. Anything not named *_test is refused, so
neither pytest nor the E2E run can ever touch the dev/demo database.
"""

import argparse
import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from core.config import API_ROOT, settings

# Every E2E account uses this prefix (apps/web/e2e/helpers.ts), so cleanup can find them all
E2E_EMAIL_LIKE = r"e2e\_%@example.com"


def _test_db_url():
    configured = make_url(settings.DATABASE_URL)
    if os.environ.get("TEST_DATABASE_URL"):
        url = make_url(os.environ["TEST_DATABASE_URL"])
    elif configured.database.endswith("_test"):
        url = configured
    else:
        url = configured.set(database=f"{configured.database}_test")
    if not url.database.endswith("_test"):
        raise RuntimeError(f"Refusing to use '{url.database}' for tests: not a *_test database")
    return url


TEST_DB_URL = _test_db_url()
settings.DATABASE_URL = TEST_DB_URL.render_as_string(hide_password=False)
os.environ["DATABASE_URL"] = settings.DATABASE_URL


def create_and_migrate() -> None:
    admin = create_engine(TEST_DB_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": TEST_DB_URL.database}
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_URL.database}"'))
    admin.dispose()

    from alembic.config import Config

    from alembic import command

    # No ini file: alembic's fileConfig() would reset logging and break caplog-based tests
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    command.upgrade(config, "head")


def cleanup_e2e() -> tuple[int, int]:
    """Delete every E2E account and its rows. Returns (deleted, users left in the test DB)."""
    engine = create_engine(TEST_DB_URL)
    with engine.begin() as conn:
        ids = "SELECT id FROM users WHERE email LIKE :pattern"
        params = {"pattern": E2E_EMAIL_LIKE}
        conn.execute(text(f"DELETE FROM risk_profiles WHERE user_id IN ({ids})"), params)
        # refresh_tokens rows go with the user (ON DELETE CASCADE)
        deleted = conn.execute(text("DELETE FROM users WHERE email LIKE :pattern"), params)
        left = conn.execute(text("SELECT count(*) FROM users")).scalar()
    engine.dispose()
    return deleted.rowcount, left


def clear_e2e_market() -> int:
    from core.database import SessionLocal
    from tests.e2e_market import clear_market

    db = SessionLocal()
    try:
        return clear_market(db)
    finally:
        db.close()


def e2e_agent(email: str) -> str:
    """
    The notifications E2E test's trigger, on the MOCK market only: a newer MOCK forecast turns the
    account's first holding to SELL, then the real agent runs for that account at the MOCK
    market's evening (its forecasts are dated that day). Only E2E accounts are accepted.
    """
    import datetime
    import re
    from decimal import Decimal

    from core.database import SessionLocal
    from crud.user import get_user_by_email
    from models.portfolio import Portfolio
    from models.prediction import Prediction
    from services import notification_agent
    from services.notification_dispatch import dispatch
    from tests.e2e_market import (
        E2E_MODEL_DIR,
        E2E_MODEL_VERSION,
        E2E_TICKERS,
        FORECAST_TIME,
        LAST_DAY,
        PKT,
    )

    if not re.fullmatch(r"e2e_[\w.-]+@example\.com", email):
        raise SystemExit("e2e-agent only runs for E2E accounts (e2e_...@example.com)")
    settings.MODEL_DIR = str(E2E_MODEL_DIR)
    settings.TRACKED_TICKERS = ",".join(E2E_TICKERS)
    db = SessionLocal()
    try:
        user = get_user_by_email(db, email)
        portfolio = (
            db.query(Portfolio)
            .filter(Portfolio.user_id == user.id, Portfolio.status == "active")
            .one()
        )
        holding = portfolio.holdings[0]
        if (
            not db.query(Prediction)
            .filter(Prediction.stock_id == holding.stock_id, Prediction.signal == "SELL")
            .first()
        ):
            close = Decimal(holding.reference_price)
            db.add(
                Prediction(
                    stock_id=holding.stock_id,
                    model_version=E2E_MODEL_VERSION,
                    forecast_price=close * Decimal("0.99"),
                    last_close=close,
                    confidence_score=Decimal("0.5"),
                    signal="SELL",
                    signal_probability=Decimal("0.55"),
                    as_of_date=LAST_DAY,
                    generated_at=FORECAST_TIME + datetime.timedelta(minutes=15),
                )
            )
            db.commit()
        evening = datetime.datetime.combine(LAST_DAY, datetime.time(19, 0), PKT)
        outcome = notification_agent.run(
            db,
            "cli",
            lambda notification_id: dispatch(db, notification_id),
            scope_user_id=user.id,
            now=evening,
        )
        return f"{outcome.status}: {len(outcome.created)} new, {len(outcome.suppressed)} not stored"
    finally:
        db.close()


def serve(
    port: int, cors_origins: list[str], mock_market: bool = False, mock_llm: bool = False
) -> None:
    import uvicorn

    settings.CORS_ORIGINS = ",".join(cors_origins)
    if mock_llm:
        # The chat E2E test never calls a real model: the MOCK provider answers from the context
        if not settings.is_development:
            raise SystemExit("--mock-llm needs ENVIRONMENT=development")
        settings.LLM_PROVIDER = "mock"
        # No real backup either: a MOCK "busy" must never fail over to a real provider
        settings.LLM_BACKUP_PROVIDER = ""
    if mock_market:
        # The backtest E2E test needs prices, forecasts and a model: the MOCK market and the
        # MOCK model built for it, never the real ones
        from core.database import SessionLocal
        from tests.e2e_market import E2E_MODEL_DIR, E2E_TICKERS, seed_market

        settings.MODEL_DIR = str(E2E_MODEL_DIR)
        settings.TRACKED_TICKERS = ",".join(E2E_TICKERS)
        db = SessionLocal()
        try:
            seed_market(db)
        finally:
            db.close()
    # Several registrations/logins per run from one IP; the limiter itself is covered by pytest
    settings.AUTH_RATE_LIMIT = 1000
    from main import app

    uvicorn.run(app, host="127.0.0.1", port=port)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    serve_parser = sub.add_parser("serve")
    serve_parser.add_argument("--port", type=int, required=True)
    serve_parser.add_argument("--cors-origin", action="append", required=True)
    serve_parser.add_argument("--mock-market", action="store_true")
    serve_parser.add_argument("--mock-llm", action="store_true")
    sub.add_parser("cleanup-e2e")
    sub.add_parser("clear-e2e-market")
    agent_parser = sub.add_parser("e2e-agent")
    agent_parser.add_argument("--email", required=True)
    args = parser.parse_args()

    print(f"Test database: {TEST_DB_URL.database}")
    if args.command == "prepare":
        create_and_migrate()
    elif args.command == "serve":
        create_and_migrate()
        serve(args.port, args.cors_origin, args.mock_market, args.mock_llm)
    elif args.command == "e2e-agent":
        print(f"E2E agent run: {e2e_agent(args.email)}")
    elif args.command == "clear-e2e-market":
        print(f"E2E market cleared: {clear_e2e_market()} MOCK stock(s) removed")
    else:
        deleted, left = cleanup_e2e()
        print(f"E2E cleanup: deleted {deleted} E2E account(s); {left} user(s) left in the test DB")
