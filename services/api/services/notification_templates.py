"""
The text of a notification, from the app's own English and Urdu strings (packages/i18n), so
the web list, the stored reasoning and the push all say the same thing. No text is written
by a model. Every figure is a stored value, only formatted here; the push carries no figure
(Design.md §19), the in-app card and the stored reasoning do.
"""

import datetime
import json
import re
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from core.config import settings

PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


@lru_cache(maxsize=2)
def _messages(language: str) -> dict:
    path = Path(settings.I18N_LOCALES_DIR) / f"{language}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def translate(language: str, key: str, **values) -> str:
    """i18next-style lookup and {{name}} interpolation; a missing key or value fails loudly."""
    node = _messages(language)
    for part in key.split("."):
        node = node[part]
    if not isinstance(node, str):
        raise KeyError(f"{language}:{key} is not a string")
    return PLACEHOLDER.sub(lambda m: str(values[m.group(1)]), node)


def money(value: str | Decimal) -> str:
    """Like the web's formatMoney: 'Rs. 12,345.67'."""
    return f"Rs. {Decimal(value):,.2f}"


def pct(value: str | Decimal) -> str:
    return f"{Decimal(value)}%"


def day(value: str | datetime.date) -> str:
    """Like the web's formatDate in English: '9 Oct 2026'."""
    date = datetime.date.fromisoformat(value) if isinstance(value, str) else value
    return f"{date.day} {MONTHS[date.month - 1]} {date.year}"


def _signal(language: str, signal: str) -> str:
    return translate(language, f"prediction.signal.{signal}")


def reasoning(rule: str, params: dict) -> str:
    """The English reasoning stored with the notification (Architecture.md §7 `reasoning`)."""
    lang = "en"
    if rule == "sell_forecast":
        sale = params["sale"]
        parts = [
            translate(
                lang,
                "notifications.message.sell_forecast.summary",
                ticker=params["ticker"],
                date=day(params["as_of"]),
                **{"from": _signal(lang, params["from_signal"])},
            ),
            (
                translate(
                    lang,
                    "notifications.message.sell_forecast.news",
                    label=translate(lang, f"sentiment.label.{params['sentiment_label']}"),
                )
                if params["sentiment_label"] and params["counted_headlines"]
                else translate(lang, "portfolio.holding.whyNoNews")
            ),
            translate(
                lang,
                "notifications.message.sell_forecast.saleLine",
                shares=params["shares"],
                price=money(params["price"]),
                net=money(sale["net_proceeds"]),
                charges=money(sale["charges_total"]),
                cgt=money(sale["cgt"]),
            ),
        ]
        return " ".join(parts)
    if rule == "roll_suggested":
        return " ".join(
            [
                translate(
                    lang,
                    "notifications.message.roll_suggested.summary",
                    ticker=params["ticker"],
                    gap=pct(params["relative_return_pct"]),
                    days=params["trading_days"],
                    threshold=pct(params["threshold_pct"]),
                ),
                translate(
                    lang,
                    "portfolio.roll.status.suggested",
                    to=params["replacement"]["ticker"],
                    benefit=money(params["expected_benefit"]),
                    cost=money(params["switch_cost"]),
                ),
            ]
        )
    if rule == "idle_cash":
        return translate(
            lang, "notifications.message.idle_cash.summary", amount=money(params["amount"])
        )
    raise ValueError(f"Unknown rule {rule}")


def push_text(rule: str, strength: str | None, params: dict, language: str) -> tuple[str, str]:
    """Title and one-line body of the OS-level push, in the user's chosen language."""
    if rule == "sell_forecast":
        base = "notifications.message.sell_forecast"
        title = translate(language, f"{base}.title", ticker=params["ticker"])
        return title, translate(language, f"{base}.push.{strength}")
    if rule == "roll_suggested":
        base = "notifications.message.roll_suggested"
        title = translate(
            language, f"{base}.title", ticker=params["ticker"], to=params["replacement"]["ticker"]
        )
        return title, translate(language, f"{base}.push.{strength}")
    if rule == "idle_cash":
        base = "notifications.message.idle_cash"
        return translate(language, f"{base}.pushTitle"), translate(language, f"{base}.push")
    raise ValueError(f"Unknown rule {rule}")
