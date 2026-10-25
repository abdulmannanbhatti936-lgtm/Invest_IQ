import os
import time
import uuid

import pytest

# Must be set before the app/settings are imported. Real env vars and .env win
# for the DB/Redis URLs; secrets get test defaults so CI needs no .env file.
os.environ.setdefault("JWT_SECRET", "test-access-secret")
os.environ.setdefault("JWT_REFRESH_SECRET", "test-refresh-secret")
# Tests are a development context (weak test secrets, /docs on); .env or CI usually set it too
os.environ.setdefault("ENVIRONMENT", "development")
os.environ["AUTH_RATE_LIMIT"] = "10000"
# No LLM keys or backup from a developer's .env: local runs see what CI sees (no provider at all)
for _name in ("GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY", "CLAUDE_API_KEY"):
    os.environ[_name] = ""
os.environ["LLM_BACKUP_PROVIDER"] = ""

# Tests never touch the dev/demo database: importing testdb switches settings to the separate
# "<db>_test" database (or TEST_DATABASE_URL) before core.database creates its engine.
# The split marker stops the import sorter from moving it below core.database.
from tests.testdb import clear_e2e_market, create_and_migrate  # noqa: E402

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
    # A Playwright run that crashed before its teardown would leave its MOCK market behind
    clear_e2e_market()


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


@pytest.fixture(autouse=True)
def _no_news_or_finbert_network(monkeypatch):
    """Tests never reach a news site or download FinBERT: use fakes instead."""

    def blocked(*args, **kwargs):
        raise RuntimeError("News/FinBERT network calls are disabled in tests; use a fake")

    monkeypatch.setattr("integrations.news.http.requests.Session.get", blocked)
    monkeypatch.setattr("ml.sentiment.build_pipeline", blocked)


LLM_HOSTS = (
    "generativelanguage.googleapis.com",
    "api.groq.com",
    "api.mistral.ai",
    "api.anthropic.com",
)


@pytest.fixture(autouse=True)
def _no_llm_network(monkeypatch):
    """
    CI never calls a real LLM. Every adapter sends through integrations.llm.base, so every
    provider call fails loudly there, whatever the host (Gemini, Groq, Mistral and Claude are
    named in the message so a failure is easy to read); tests script the responses instead.
    """

    def blocked(url, *args, **kwargs):
        raise RuntimeError(
            f"LLM network calls are disabled in tests ({', '.join(LLM_HOSTS)}); fake the "
            f"provider instead of calling {url}"
        )

    monkeypatch.setattr("integrations.llm.base.httpx.post", blocked)


@pytest.fixture(autouse=True)
def _no_push_network(monkeypatch):
    """Tests never reach Firebase: the FCM channel's HTTP call fails loudly unless faked."""

    def blocked(url, *args, **kwargs):
        raise RuntimeError(f"Push network calls are disabled in tests; fake the channel ({url})")

    monkeypatch.setattr("integrations.push.fcm.httpx.post", blocked)


class QueuedTasks:
    """Celery calls recorded instead of sent: tests never need a broker or a worker."""

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []

    def recorder(self, name):
        def record(*args, **kwargs):
            self.calls.append((name, args, kwargs))

        return record

    def named(self, name) -> list[tuple[tuple, dict]]:
        return [(args, kwargs) for n, args, kwargs in self.calls if n == name]


@pytest.fixture(autouse=True)
def queued_tasks(monkeypatch):
    from worker import tasks

    queued = QueuedTasks()
    monkeypatch.setattr(
        tasks.monitor_portfolios, "apply_async", queued.recorder("monitor_portfolios")
    )
    monkeypatch.setattr(tasks.send_notification, "delay", queued.recorder("send_notification"))
    return queued


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
        self.ttls: dict[str, int] = {}
        self.expires_at: dict[str, float] = {}  # keys set with px (millisecond expiry)
        self.get_calls = 0

    def _drop_expired(self, key):
        if key in self.expires_at and time.monotonic() >= self.expires_at[key]:
            self.store.pop(key, None)
            del self.expires_at[key]

    def get(self, key):
        self.get_calls += 1
        self._drop_expired(key)
        return self.store.get(key)

    def set(self, key, value, ex=None, nx=False, px=None):
        self._drop_expired(key)
        if nx and key in self.store:
            return None
        self.store[key] = value
        if px:
            self.expires_at[key] = time.monotonic() + px / 1000
        return True

    def incr(self, key):
        self.store[key] = str(int(self.store.get(key, 0)) + 1)
        return int(self.store[key])

    def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    def ttl(self, key):
        return self.ttls.get(key, -1)

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
    monkeypatch.setattr("services.chat_service.get_redis_client", lambda: fake)
    monkeypatch.setattr("integrations.llm.base.get_redis_client", lambda: fake)
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
