"""Startup checks for JWT secrets and the development-only API docs (audit findings 4 and 11)."""

import importlib
import logging
import secrets

import pytest
from pydantic import ValidationError

from core.config import Settings, warn_if_weak_jwt_secrets

STRONG = {"JWT_SECRET": secrets.token_urlsafe(48), "JWT_REFRESH_SECRET": secrets.token_urlsafe(48)}


def _settings(**overrides) -> Settings:
    return Settings(_env_file=None, **{**STRONG, **overrides})


@pytest.mark.parametrize("environment", ["production", "staging"])
@pytest.mark.parametrize(
    "weak",
    [
        {"JWT_SECRET": "placeholder_jwt_secret"},
        {"JWT_REFRESH_SECRET": "placeholder_jwt_refresh_secret"},
        {"JWT_SECRET": "x" * 31},  # one character short
        {"JWT_REFRESH_SECRET": "CHANGEME-" + "y" * 40},
    ],
)
def test_refuses_to_start_outside_development_with_weak_secrets(environment, weak):
    with pytest.raises(ValidationError, match="Refusing to start"):
        _settings(ENVIRONMENT=environment, **weak)


def test_error_never_contains_the_secret_value():
    with pytest.raises(ValidationError) as error:
        _settings(ENVIRONMENT="production", JWT_SECRET="short-but-secret-value")
    assert "short-but-secret-value" not in str(error.value)
    # Nor any other setting: pydantic would otherwise echo the whole input
    assert STRONG["JWT_REFRESH_SECRET"] not in str(error.value)
    assert "input_value" not in str(error.value)


def test_starts_outside_development_with_strong_secrets():
    assert _settings(ENVIRONMENT="production", JWT_SECRET="z" * 32).jwt_secret_problems() == []


def test_development_allows_weak_secrets_but_warns_loudly(caplog):
    weak = _settings(ENVIRONMENT="development", JWT_SECRET="placeholder_jwt_secret")
    with caplog.at_level(logging.WARNING, logger="core.config"):
        warn_if_weak_jwt_secrets(weak)
    warnings = [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert "INSECURE JWT SECRET: JWT_SECRET is a placeholder" in warnings[0]
    assert "placeholder_jwt_secret" not in warnings[0]


def test_no_warning_with_strong_secrets(caplog):
    with caplog.at_level(logging.WARNING, logger="core.config"):
        warn_if_weak_jwt_secrets(_settings(ENVIRONMENT="development"))
    assert caplog.records == []


def test_unset_environment_means_production(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    strict = _settings()  # _env_file=None: nothing sets ENVIRONMENT
    assert strict.ENVIRONMENT == "production"
    assert not strict.is_development
    # ...so a deployment that forgets ENVIRONMENT can't start with a placeholder secret
    with pytest.raises(ValidationError, match="Refusing to start with ENVIRONMENT=production"):
        _settings(JWT_SECRET="placeholder_jwt_secret")


def test_api_docs_only_in_development(monkeypatch):
    from fastapi.testclient import TestClient

    import main
    from core.config import settings

    paths = ("/docs", "/redoc", "/openapi.json")
    assert [TestClient(main.app).get(p).status_code for p in paths] == [200, 200, 200]

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    try:
        production_app = importlib.reload(main).app
        assert [TestClient(production_app).get(p).status_code for p in paths] == [404, 404, 404]
        assert TestClient(production_app).get("/health").status_code == 200
    finally:
        monkeypatch.undo()
        importlib.reload(main)
