"""
The separate test database, shared by pytest (conftest.py) and the Playwright E2E run.

    python -m tests.testdb prepare        # create + migrate <db>_test
    python -m tests.testdb serve --port 8001 --cors-origin http://localhost:5174 [--mock-market]
    python -m tests.testdb cleanup-e2e    # delete E2E accounts, print what is left
    python -m tests.testdb clear-e2e-market   # remove the MOCK market (tests/e2e_market.py)

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
    args = parser.parse_args()

    print(f"Test database: {TEST_DB_URL.database}")
    if args.command == "prepare":
        create_and_migrate()
    elif args.command == "serve":
        create_and_migrate()
        serve(args.port, args.cors_origin, args.mock_market, args.mock_llm)
    elif args.command == "clear-e2e-market":
        print(f"E2E market cleared: {clear_e2e_market()} MOCK stock(s) removed")
    else:
        deleted, left = cleanup_e2e()
        print(f"E2E cleanup: deleted {deleted} E2E account(s); {left} user(s) left in the test DB")
