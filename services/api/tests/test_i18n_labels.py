"""
The questionnaire is defined once, on the server (GET /users/risk-questionnaire); the apps
show each id/option through packages/i18n. Fail if anything the API can return has no label
in English or Urdu, so a backend change can't silently show raw keys on the onboarding screen.
"""

import json
from functools import reduce
from pathlib import Path

import pytest

from models.risk_profile import RiskCategory
from services.cost_engine import load_rates
from services.risk_scoring import SAFETY_CAPS
from services.rolling import RollStatus

LOCALES_DIR = Path(__file__).resolve().parents[3] / "packages" / "i18n" / "src" / "locales"


def _load(lang: str) -> dict:
    return json.loads((LOCALES_DIR / f"{lang}.json").read_text(encoding="utf-8"))


def _label(messages: dict, key: str):
    """Value at a dotted i18n key, or None if any part is missing."""
    return reduce(
        lambda node, part: node.get(part) if isinstance(node, dict) else None,
        key.split("."),
        messages,
    )


def _required_keys(client) -> list[str]:
    response = client.get("/users/risk-questionnaire")
    assert response.status_code == 200
    keys = []
    for question in response.json():
        prefix = f"onboarding.questions.{question['id']}"
        keys.append(f"{prefix}.title")
        keys += [f"{prefix}.options.{option}" for option in question["options"]]
    # The result screen shows these, also by id from the API (risk profile response)
    keys += [f"onboarding.result.caps.{cap}" for cap in SAFETY_CAPS]
    for category in RiskCategory:
        keys += [f"risk.{category.value}", f"risk.description.{category.value}"]
    # The portfolio screen labels these ids from the API (Phase 5)
    rates = load_rates()
    charges = ["commission", "sales_tax", *(fee.key for fee in rates.fees)]
    keys += [f"portfolio.holding.charges.{key}" for key in charges]
    keys += [f"portfolio.notModelled.{key}" for key in rates.not_modelled]
    keys += [f"portfolio.roll.status.{status.value}" for status in RollStatus]
    keys += [f"portfolio.idle.{reason}" for reason in ("stock_cap", "sector_cap")]
    return keys


@pytest.mark.parametrize("lang", ["en", "ur"])
def test_every_questionnaire_id_has_a_label(client, lang):
    messages = _load(lang)
    missing = [
        key
        for key in _required_keys(client)
        if not (isinstance(_label(messages, key), str) and _label(messages, key).strip())
    ]
    assert missing == [], f"{lang}.json has no label for: {missing}"


def test_the_check_catches_a_missing_label(client):
    """Guard against a test that can never fail: drop one label and expect it to be reported."""
    messages = _load("en")
    del messages["onboarding"]["questions"]["loss_tolerance"]["options"]["hold"]
    keys = _required_keys(client)
    missing = [k for k in keys if _label(messages, k) is None]
    assert missing == ["onboarding.questions.loss_tolerance.options.hold"]
