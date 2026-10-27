"""
Phase 7: notification text comes from the app's own en/ur strings. Every template renders in
both languages, the stored reasoning carries the stored figures formatted like the web, and the
push carries no rupee figure (Design.md §19).
"""

import pytest

from services import notification_templates as templates

SELL = {
    "ticker": "HBL",
    "as_of": "2026-10-09",
    "from_signal": "HOLD",
    "shares": 40,
    "price": "302.02",
    "sentiment_label": "negative",
    "counted_headlines": 3,
    "sale": {
        "gross": "12080.80",
        "charges_total": "21.44",
        "cgt": "0.00",
        "net_proceeds": "12059.36",
    },
}
ROLL = {
    "ticker": "HBL",
    "trading_days": 21,
    "relative_return_pct": "-13.00",
    "threshold_pct": "8.00",
    "replacement": {"ticker": "OGDC"},
    "expected_benefit": "300.00",
    "switch_cost": "60.00",
}
IDLE = {"amount": "1234.50"}
CASES = [("sell_forecast", SELL), ("roll_suggested", ROLL), ("idle_cash", IDLE)]


def test_sell_reasoning_names_the_change_the_news_and_the_sale_figures():
    text = templates.reasoning("sell_forecast", SELL)
    assert text == (
        "The latest forecast for HBL, from the close of 9 Oct 2026, changed from Hold to Sell. "
        "News mood: Negative. Selling all 40 shares at Rs. 302.02 would bring Rs. 12,059.36 "
        "after selling charges (Rs. 21.44) and capital gains tax (Rs. 0.00)."
    )


def test_sell_reasoning_without_headlines_says_so():
    text = templates.reasoning("sell_forecast", {**SELL, "counted_headlines": 0})
    assert "No recent headlines" in text


def test_roll_reasoning_uses_the_portfolio_screens_wording():
    text = templates.reasoning("roll_suggested", ROLL)
    assert "trailed the benchmark by -13.00% over 21 trading days" in text
    assert text.endswith(
        "Consider switching to OGDC: expected gain Rs. 300.00, cost of switching Rs. 60.00."
    )


def test_idle_reasoning():
    assert templates.reasoning("idle_cash", IDLE).startswith("Rs. 1,234.50 of your portfolio")


@pytest.mark.parametrize("language", ["en", "ur"])
@pytest.mark.parametrize(("rule", "params"), CASES)
@pytest.mark.parametrize("strength", ["strong", "watch"])
def test_push_text_renders_in_both_languages_without_figures(language, rule, params, strength):
    title, body = templates.push_text(rule, strength, params, language)
    assert title and body
    assert "{{" not in title + body
    assert "Rs." not in title + body
    assert "302.02" not in body


def test_the_urdu_push_is_urdu():
    title, body = templates.push_text("sell_forecast", "watch", SELL, "ur")
    assert title == "HBL کی فروخت پر غور کریں"
    assert "کمزور اشارہ" in body


def test_a_missing_value_fails_loudly():
    with pytest.raises(KeyError):
        templates.translate("en", "notifications.message.sell_forecast.title")
