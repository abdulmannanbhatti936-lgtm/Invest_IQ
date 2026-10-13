"""The chatbot figure check: every number in a reply must be a figure of its context."""

import datetime
import json
from decimal import Decimal as D

import pytest

from services.chat_context import Figure
from services.chat_figure_check import check_reply, extract_numbers, normalize, number_words


class Context:
    """The three things the check reads from a ChatContext."""

    def __init__(self, figures, dates=(), extra=None):
        self.figures = figures
        self.dates = set(dates)
        self.json = json.dumps({"figures": [f.text for f in figures], **(extra or {})})


CTX = Context(
    [
        Figure(D("99887.21"), "money", "Rs. 99,887.21", "portfolio"),
        Figure(D("100000.00"), "money", "Rs. 100,000.00", "portfolio"),
        Figure(D("-20.25"), "pct", "-20.25%", "backtest"),
        Figure(D("12.50"), "pct", "12.50%", "prediction:HBL"),
        Figure(D("302.02"), "money", "Rs. 302.02", "prediction:HBL"),
        Figure(D("49"), "pct", "49%", "prediction:HBL"),
        Figure(D("27"), "number", "27", "backtest"),
        Figure(D("37"), "number", "37", "backtest"),
        Figure(D("1.17"), "number", "1.17", "backtest"),
        Figure(D("60"), "pct", "60%", "prediction:HBL"),
    ],
    dates=[datetime.date(2026, 10, 7), datetime.date(2024, 5, 2)],
)


def check(reply, user="How is my portfolio?"):
    return check_reply(reply, CTX, user)


@pytest.mark.parametrize(
    "reply",
    [
        "Your portfolio cost Rs. 99,887.21 from Rs. 100,000.00.",
        "It cost Rs.99,887.21 of your Rs 100,000.",  # no space, no decimals on a whole amount
        "You put in PKR 1,00,000.",  # lakh-style grouping
        "The largest fall was 20.25%.",  # the sign carried by the word "fall"
        "The largest fall was -20.25%.",
        "The forecast change is 12.5%.",  # trailing zero dropped
        "Confidence is 49%, below the 60% the app asks for.",
        "It went up in 27 of 37 months, with a Sharpe ratio of 1.17.",
        "HBL closed at Rs. 302.02 on 7 October 2026.",
        "HBL closed at Rs. 302.02 on 2026-10-07.",
        "The fall started on May 2, 2024 and forecasts may be wrong.",
        "آپ کے پورٹ فولیو کی کل لاگت ۹۹,۸۸۷٫۲۱ روپے ہے۔",  # Urdu digits and separators
        "اعتماد ⁦49%⁩ ہے۔",  # inside a bidi isolate
        "HBL ka confidence 49 feesad hai.",
        "1. HBL\n2. OGDC\n3. PPL",  # list numbering
        "This compares with the KSE-100, which is not shown.",
        "One of your stocks is HBL.",
        "You asked about 3 years: InvestIQ has no 3-year forecast.",  # numbers the user wrote
    ],
)
def test_replies_that_only_repeat_context_figures_pass(reply):
    user = "What about 3 years?" if "3 years" in reply else "How is my portfolio?"
    result = check(reply, user)
    assert result.passed, (result.unmatched, result.number_words)


@pytest.mark.parametrize(
    "reply, unmatched",
    [
        ("Your portfolio cost about Rs. 99,887.", ["99,887"]),  # rounded
        ("Your portfolio cost about Rs. 99,900.", ["99,900"]),
        ("HBL may reach Rs. 340 next week.", ["340"]),  # invented price
        ("That is a gain of 12.6%.", ["12.6"]),
        ("Your money could grow by 8% a year.", ["8"]),
        ("27% of months were up.", ["27"]),  # a count is not a percentage
        ("Prices were checked on 8 October 2026.", ["8 October 2026"]),
        ("In 2027 the stock may do better.", ["2027"]),
        ("HBL may be at Rs. 302.02 on 2026-11-01.", ["2026-11-01"]),
    ],
)
def test_figures_not_in_the_context_fail_and_are_listed(reply, unmatched):
    result = check(reply)
    assert not result.passed
    assert result.unmatched == unmatched


@pytest.mark.parametrize(
    "phrase",
    [
        "twenty percent",
        "twenty-five percent",
        "بیس فیصد",
        "bees percent",
        "ten thousand rupees",
        "دس ہزار روپے",
        "das hazaar",
        "do hazaar",
        "a thousand rupees",
        "10 thousand",
        "5 lakh",
        "half percent",
    ],
)
def test_numbers_in_words_next_to_a_unit_or_magnitude_fail(phrase):
    result = check(f"Your return was {phrase} this year.")
    assert not result.passed
    assert result.number_words


@pytest.mark.parametrize(
    "text",
    [
        "One of your stocks is HBL.",
        "How do shares work? Two of them are banks.",
        "ایک اچھا سوال ہے۔",
        "Arab investors and one more thing.",
        "Forecasts may be wrong, so treat them as one input.",
    ],
)
def test_ordinary_words_are_not_numbers(text):
    assert number_words(text) == []


def test_a_magnitude_from_a_headline_may_be_quoted():
    # The builder records a headline title's numbers as figures (_Recorder.text)
    ctx = Context(
        [Figure(D("10"), "money", "10", "sentiment:HBL")],
        extra={"headline": "HBL posts Rs 10bn profit"},
    )
    result = check_reply("A headline said: HBL posts Rs 10bn profit.", ctx, "")
    assert result.passed, (result.unmatched, result.number_words)


def test_a_figure_shared_by_several_stocks_is_credited_to_the_one_named():
    ctx = Context(
        [
            Figure(D("49"), "pct", "49%", "prediction:HBL"),
            Figure(D("49"), "pct", "49%", "prediction:OGDC"),
        ]
    )
    assert check_reply("OGDC's confidence is 49%.", ctx, "").matched_sources == ["prediction:OGDC"]
    assert check_reply("Confidence is 49%.", ctx, "").matched_sources == []


def test_matched_figures_tag_their_sources_but_small_counts_do_not():
    result = check("It cost Rs. 99,887.21; HBL's confidence is 49%; 27 of 37 months were up.")
    assert result.matched_sources == ["portfolio", "prediction:HBL"]


def test_extraction_reads_units_and_ignores_digits_inside_tickers():
    numbers = extract_numbers("TPLRF1 at Rs. 9.50, up 3%; 1,200 shares; PKR 5")
    assert [(str(n.value), n.kind) for n in numbers] == [
        ("9.50", "money"),
        ("3", "pct"),
        ("1200", "number"),
        ("5", "money"),
    ]


def test_normalize_maps_urdu_and_arabic_indic_digits():
    assert normalize("۱۲۳٫۴٥") == "123.45"
    assert normalize("−20.25") == "-20.25"
    assert normalize("⁦12%⁩") == "12%"
