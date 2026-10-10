"""
The sentiment_scores migration (e4b1d7a90c26) must refuse to drop a table that holds rows,
in both directions (decided 2026-10-11). Runs on its own scratch *_test database.
"""

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text

from alembic import command
from core.config import API_ROOT, settings
from tests.testdb import TEST_DB_URL

BEFORE = "c81f3d5a9e64"
REVISION = "e4b1d7a90c26"


@pytest.fixture
def scratch_db(monkeypatch):
    name = TEST_DB_URL.database.removesuffix("_test") + "_migration_test"
    admin = create_engine(TEST_DB_URL.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = TEST_DB_URL.set(database=name)
    # alembic/env.py reads settings.DATABASE_URL on every command
    monkeypatch.setattr(settings, "DATABASE_URL", url.render_as_string(hide_password=False))
    config = Config()
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    engine = create_engine(url)
    try:
        yield config, engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()


def _count(engine, table: str) -> int:
    with engine.connect() as conn:
        return conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()


def test_upgrade_refuses_when_news_sentiments_has_rows(scratch_db):
    config, engine = scratch_db
    command.upgrade(config, BEFORE)
    with engine.begin() as conn:
        stock_id = conn.execute(text("SELECT id FROM stocks LIMIT 1")).scalar()
        conn.execute(
            text("INSERT INTO news_sentiments (stock_id, headline) VALUES (:s, 'MOCK_ headline')"),
            {"s": stock_id},
        )

    with pytest.raises(RuntimeError, match="Refusing to drop news_sentiments"):
        command.upgrade(config, REVISION)
    assert _count(engine, "news_sentiments") == 1

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM news_sentiments"))
    command.upgrade(config, REVISION)
    assert _count(engine, "sentiment_scores") == 0


def test_downgrade_refuses_when_sentiment_scores_has_rows(scratch_db):
    config, engine = scratch_db
    command.upgrade(config, REVISION)
    with engine.begin() as conn:
        stock_id = conn.execute(text("SELECT id FROM stocks LIMIT 1")).scalar()
        conn.execute(
            text(
                "INSERT INTO sentiment_scores (id, stock_id, source, url, headline, published_at,"
                " fetched_at) VALUES (gen_random_uuid(), :s, 'profit', 'https://example.com/MOCK',"
                " 'MOCK_ headline', now(), now())"
            ),
            {"s": stock_id},
        )

    with pytest.raises(RuntimeError, match="Refusing to drop sentiment_scores"):
        command.downgrade(config, BEFORE)
    assert _count(engine, "sentiment_scores") == 1

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM sentiment_scores"))
    command.downgrade(config, BEFORE)
    assert _count(engine, "news_sentiments") == 0
