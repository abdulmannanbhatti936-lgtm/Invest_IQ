import os
import uuid

import pytest

# Must be set before the app/settings are imported. Real env vars and .env win
# for the DB/Redis URLs; secrets get test defaults so CI needs no .env file.
os.environ.setdefault("JWT_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
# Tests are a development context (weak test secrets, /docs on); .env or CI usually set it too
os.environ.setdefault("ENVIRONMENT", "development")
os.environ["AUTH_RATE_LIMIT"] = "10000"

# Tests never touch the dev/demo database: importing testdb switches settings to the separate
# "<db>_test" database (or TEST_DATABASE_URL) before core.database creates its engine.
# The split marker stops the import sorter from moving it below core.database.
from tests.testdb import create_and_migrate  # noqa: E402

# isort: split
from fastapi.testclient import TestClient  # noqa: E402

from core.config import settings  # noqa: E402
from core.database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from tests.synthetic import make_ohlcv  # noqa: E402

if not engine.url.database.endswith("_test"):
    raise RuntimeError(f"Test engine points at '{engine.url.database}', not a *_test database")


@pytest.fixture(scope="session", autouse=True)
def _test_database():
    create_and_migrate()


@pytest.fixture(autouse=True)
def _rollback_after_each_test(_test_database):
    """
    Every session the app opens (SessionLocal) joins one outer transaction per test, and the
    app's own commits become savepoints. Rolling the outer transaction back afterwards leaves
    the test DB exactly as migrated (including the seeded PSX catalog).
    """
    connection = engine.connect()
    outer = connection.begin()
    SessionLocal.configure(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield
    finally:
        SessionLocal.configure(bind=engine, join_transaction_mode="conservative_savepoint")
        outer.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def _no_market_data_network(monkeypatch):
    """Tests never reach Yahoo Finance: any call that is not mocked fails loudly."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Market data network calls are disabled in tests; mock the client")

    monkeypatch.setattr("integrations.market_data.yf.Ticker", blocked)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


class FakeRedis:
    """In-memory stand-in for the few Redis calls the app makes."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.get_calls = 0

    def get(self, key):
        self.get_calls += 1
        return self.store.get(key)

    def set(self, key, value, ex=None):
        self.store[key] = value

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])

    def expire(self, key, seconds):
        return True

    def scan_iter(self, pattern):
        prefix = pattern.rstrip("*")
        return [k for k in list(self.store) if k.startswith(prefix)]

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr("services.stock_service.get_redis_client", lambda: fake)
    monkeypatch.setattr("core.rate_limit.get_redis_client", lambda: fake)
    return fake


def register_and_login(client) -> dict:
    email = f"test_{uuid.uuid4()}@example.com"
    client.post(
        "/auth/register", json={"email": email, "full_name": "Test User", "password": "password123"}
    )
    token = client.post("/auth/login", data={"username": email, "password": "password123"}).json()[
        "access_token"
    ]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers(client):
    return register_and_login(client)


__all__ = ["settings", "make_ohlcv", "register_and_login"]
