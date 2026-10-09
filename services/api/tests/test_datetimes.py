"""Every datetime the API returns is timezone-aware UTC, serialised with a trailing "Z"."""

import datetime as dt
import importlib
import inspect
import pkgutil
import typing
from datetime import timedelta, timezone

from pydantic import BaseModel

import schemas
from schemas.stock import PricePointResponse
from schemas.types import UTCDateTime

PKT = timezone(timedelta(hours=5))


def test_naive_values_are_treated_as_utc():
    point = PricePointResponse(timestamp=dt.datetime(2026, 10, 8, 21, 18), close=1.0, volume=1)
    assert point.model_dump_json().startswith('{"timestamp":"2026-10-08T21:18:00Z"')


def test_aware_values_are_converted_to_utc():
    # 02:18 on the 9th in Karachi is 21:18 on the 8th in UTC
    local = dt.datetime(2026, 10, 9, 2, 18, tzinfo=PKT)
    point = PricePointResponse(timestamp=local, close=1.0, volume=1)
    assert '"timestamp":"2026-10-08T21:18:00Z"' in point.model_dump_json()


def test_every_schema_datetime_field_uses_utc_type():
    """Guard for future fields: a plain `datetime` in any response schema fails this test."""
    expected_metadata = typing.get_args(UTCDateTime)[1:]
    offenders = []
    for module_info in pkgutil.iter_modules(schemas.__path__):
        module = importlib.import_module(f"schemas.{module_info.name}")
        for name, model in inspect.getmembers(module, inspect.isclass):
            if not issubclass(model, BaseModel) or model.__module__ != module.__name__:
                continue
            for field_name, field in model.model_fields.items():
                if field.annotation is dt.datetime and field.metadata != list(expected_metadata):
                    offenders.append(f"{module.__name__}.{name}.{field_name}")
    assert offenders == []


def _parse(value: str) -> dt.datetime:
    assert value.endswith("Z"), value
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_api_responses_end_in_z_and_hold_the_utc_instant(client, auth_headers):
    before = dt.datetime.now(timezone.utc) - timedelta(seconds=5)
    created = _parse(client.get("/users/me", headers=auth_headers).json()["created_at"])
    assert before <= created <= dt.datetime.now(timezone.utc) + timedelta(seconds=5)

    answers = {
        "age_band": "30_to_50",
        "income_stability": "somewhat_stable",
        "investment_horizon": "medium",
        "loss_tolerance": "hold",
        "market_experience": "some",
        "investment_goal": "income",
        "emergency_savings": "3_to_6_months",
    }
    saved = client.patch("/users/me/risk-profile", headers=auth_headers, json={"answers": answers})
    updated = _parse(saved.json()["updated_at"])
    assert abs((updated - dt.datetime.now(timezone.utc)).total_seconds()) < 10
    read_back = client.get("/users/me/risk-profile", headers=auth_headers).json()
    assert _parse(read_back["updated_at"]) == updated
