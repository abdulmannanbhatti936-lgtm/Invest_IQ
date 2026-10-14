"""
Phase 8 reply generation rules (decided 2026-10-13): failover from the primary to the backup,
the per-provider context budget, cut-off replies, markdown stripping, the reply token limits by
language and the Urdu glossary. Providers are scripted; no model is called.
"""

import json
from decimal import Decimal as D

import pytest

from core.config import settings
from integrations import llm
from integrations.llm import LLMRateLimited, LLMResult, LLMUnavailable
from integrations.llm.gemini import GeminiProvider
from integrations.llm.groq import GroqProvider
from integrations.llm.mock import _CONTEXT
from services import chat_context, chat_prompt, chat_service
from services.chat_context import ChatContext, Figure
from tests import test_chat_context, test_portfolio_api
from tests.test_chat_context import _context

# Shared fixtures: the Phase 5 worked example (Rs 100,000 Moderate) and its portfolio owner
investor = test_portfolio_api.investor
worked_example = test_portfolio_api.worked_example
portfolio_user = test_chat_context.portfolio_user

GOOD = "Your portfolio cost Rs. 99,887.21."


class Scripted:
    """A provider that answers (or raises) from a script and records every call."""

    def __init__(self, name, *replies, model=None):
        self.name, self.model = name, model or f"{name}-test"
        self.replies = list(replies)
        self.calls = []

    def complete(self, system, turns, *, max_tokens, temperature, deadline, retry=True):
        self.calls.append({"system": system, "max_tokens": max_tokens, "retry": retry})
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        text, truncated = reply if isinstance(reply, tuple) else (reply, False)
        return LLMResult(text, self.model, 100, 20, truncated=truncated)


def small_context() -> ChatContext:
    return ChatContext(
        data={"portfolio": None, "sentiment": [], "missing": []},
        figures=[Figure(D("99887.21"), "money", "Rs. 99,887.21", "portfolio")],
        dates=set(),
        sources={"portfolio": {"kind": "portfolio", "date": "2026-10-13"}},
        refs={},
    )


def generate(providers, language="en", context=None):
    return chat_service.generate_reply(
        context or small_context(), [], "How is my portfolio?", language, providers=providers
    )


# Failover


@pytest.mark.parametrize(
    "error",
    [
        LLMRateLimited(10.0),
        LLMUnavailable("HTTP 503", failover=True),
        LLMUnavailable("ReadTimeout", failover=True),
    ],
)
def test_a_429_5xx_or_timeout_moves_the_message_to_the_backup(error):
    primary, backup = Scripted("gemini", error), Scripted("groq", GOOD)

    reply = generate([primary, backup])

    assert reply.text == GOOD and reply.figure_check == "passed"
    assert (reply.provider, reply.model) == ("groq", "groq-test")
    assert reply.detail["failover"] == {"from": "gemini:gemini-test", "reason": error.reason}
    assert reply.detail["attempts"][0]["provider"] == "groq:groq-test"
    # With a backup waiting, the primary gets one attempt so the backup has time left
    assert primary.calls[0]["retry"] is False
    assert backup.calls[0]["retry"] is True


def test_a_refused_request_does_not_fail_over():
    primary, backup = Scripted("gemini", LLMUnavailable("HTTP 400")), Scripted("groq", GOOD)
    with pytest.raises(LLMUnavailable):
        generate([primary, backup])
    assert backup.calls == []


def test_when_both_fail_the_error_reaches_the_caller():
    primary = Scripted("gemini", LLMRateLimited(5.0))
    backup = Scripted("groq", LLMRateLimited(30.0))
    with pytest.raises(LLMRateLimited) as caught:
        generate([primary, backup])
    assert caught.value.retry_after == 30.0


def test_without_a_backup_the_primary_keeps_its_own_retry():
    primary = Scripted("gemini", GOOD)
    assert generate([primary]).provider == "gemini"
    assert primary.calls[0]["retry"] is True


def test_a_regeneration_stays_on_the_provider_that_answered():
    primary = Scripted("gemini", LLMRateLimited(1.0))
    backup = Scripted("groq", "It cost about Rs. 99,900.", GOOD)

    reply = generate([primary, backup])

    assert reply.figure_check == "regenerated" and reply.provider == "groq"
    assert len(primary.calls) == 1 and len(backup.calls) == 2


def test_a_provider_error_on_the_second_draft_sends_the_fallback():
    primary = Scripted("gemini", "It cost about Rs. 99,900.", LLMUnavailable("HTTP 400"))
    reply = generate([primary])
    assert reply.figure_check == "fallback"
    assert reply.text == chat_prompt.FALLBACK["en"]
    assert reply.detail["attempts"][1] == {"provider": "gemini:gemini-test", "error": True}


def test_the_chat_endpoint_stores_the_provider_that_actually_answered(
    client, db, investor, monkeypatch, fake_redis
):
    from models.chat import ChatMessage

    # This user has no portfolio yet, so the reply has no figures to check
    no_portfolio = "You do not have a portfolio yet. You can make one on the Portfolio screen."
    primary, backup = Scripted("gemini", LLMRateLimited(3.0)), Scripted("groq", no_portfolio)
    monkeypatch.setattr(chat_service, "get_providers", lambda: [primary, backup])
    monkeypatch.setattr(settings, "LLM_MODEL", "gemini-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "k")

    response = client.post(
        "/chat/message", json={"content": "hello", "language": "en"}, headers=investor
    )

    assert response.status_code == 201, response.text
    row = db.query(ChatMessage).filter(ChatMessage.id == response.json()["reply"]["id"]).one()
    assert (row.provider, row.model) == ("groq", "groq-test")
    assert row.figure_check_detail["failover"]["from"] == "gemini:gemini-test"


def test_get_providers_adds_a_usable_backup_only(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "LLM_MODEL", "gemini-test")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "gk")
    monkeypatch.setattr(settings, "LLM_BACKUP_PROVIDER", "")
    assert [type(p) for p in llm.get_providers()] == [GeminiProvider]

    monkeypatch.setattr(settings, "LLM_BACKUP_PROVIDER", "groq")
    monkeypatch.setattr(settings, "LLM_BACKUP_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    assert settings.backup_unavailable_reason() == "GROQ_API_KEY is not set"
    assert [type(p) for p in llm.get_providers()] == [GeminiProvider]

    monkeypatch.setattr(settings, "GROQ_API_KEY", "gq")
    providers = llm.get_providers()
    assert [type(p) for p in providers] == [GeminiProvider, GroqProvider]
    assert providers[1].model == "openai/gpt-oss-120b"


# Per-provider context budget


def test_groq_gets_the_small_budget_with_the_drop_order_applied(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)

    for_gemini, _ = chat_service.prepare(ctx, [], "hi", "gemini")
    for_groq, _ = chat_service.prepare(ctx, [], "hi", "groq")

    assert settings.chat_context_tokens("gemini") == 12_000
    assert settings.chat_context_tokens("groq") == 4_000
    assert for_gemini.trimmed == []
    assert for_groq.trimmed == ["headlines", "charge_lines"]
    holding = for_groq.data["portfolio"]["recommended_stocks"][0]
    assert list(holding["charges"]) == ["total"]
    # Never dropped: the portfolio totals and the forecasts
    assert for_groq.data["portfolio"]["totals"] == for_gemini.data["portfolio"]["totals"]
    assert for_groq.data["forecasts"] == for_gemini.data["forecasts"]
    # The original is untouched, so a failover starts again from everything
    assert (
        ctx.trimmed == []
        and "commission" in ctx.data["portfolio"]["recommended_stocks"][0]["charges"]
    )


def test_a_failover_to_groq_sends_groq_the_trimmed_context(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)
    primary = Scripted("gemini", LLMRateLimited(1.0))
    backup = Scripted("groq", "Your portfolio cost Rs. 99,887.21.")

    reply = generate([primary, backup], context=ctx)

    sent = json.loads(_CONTEXT.search(backup.calls[0]["system"]).group(1))
    assert all(list(h["charges"]) == ["total"] for h in sent["portfolio"]["recommended_stocks"])
    assert reply.context.trimmed == ["headlines", "charge_lines"]


# Cut-off replies


def test_a_cut_off_reply_is_regenerated_shorter_and_never_shown():
    provider = Scripted("groq", ("Your portfolio cost Rs. 99,887.21 and the", True), GOOD)

    reply = generate([provider])

    assert reply.text == GOOD and reply.figure_check == "regenerated"
    assert reply.detail["attempts"][0]["truncated"] is True
    assert "cut off because it was too long" in provider.calls[1]["system"]
    assert "cut off" not in provider.calls[0]["system"]


def test_two_cut_off_replies_send_the_fallback():
    provider = Scripted("groq", ("Rs. 99,887.21 and", True), ("Rs. 99,887.21 was", True))
    reply = generate([provider], language="ur")
    assert reply.figure_check == "fallback"
    assert reply.text == chat_prompt.FALLBACK["ur"]


# Token limits by language


@pytest.mark.parametrize("language, tokens", [("en", 700), ("ur", 1200), ("ur-latn", 1200)])
def test_urdu_replies_get_more_tokens(language, tokens):
    provider = Scripted("gemini", GOOD)
    generate([provider], language=language)
    assert provider.calls[0]["max_tokens"] == tokens


# Markdown


def test_markdown_is_stripped_before_the_check_and_storage():
    provider = Scripted("gemini", "## Summary\n**Your portfolio** cost `Rs. 99,887.21`.")
    reply = generate([provider])
    assert reply.text == "Summary\nYour portfolio cost Rs. 99,887.21."
    assert reply.figure_check == "passed"


@pytest.mark.parametrize(
    "raw, plain",
    [
        ("**Bold** and __under__", "Bold and under"),
        ("# Heading\n### Smaller\ntext", "Heading\nSmaller\ntext"),
        ("* one\n+ two\n- three", "- one\n- two\n- three"),
        ("```\nRs. 1.00\n```", "Rs. 1.00"),
        ("use `HBL` here", "use HBL here"),
        ("MEBL_A and 2*3 stay; a * b", "MEBL_A and 2*3 stay; a * b"),
        ("line\n\n\n\nnext", "line\n\nnext"),
        ("**ہولڈنگز (۸ سٹاک):**", "ہولڈنگز (۸ سٹاک):"),
    ],
)
def test_plain_text(raw, plain):
    assert chat_prompt.plain_text(raw) == plain


# Urdu glossary


def test_the_urdu_glossary_comes_from_the_app_locale_files():
    glossary = chat_context.urdu_glossary()
    assert len(glossary) == len(chat_context.GLOSSARY_KEYS)
    assert glossary["Moderate"] == "متوازن"
    assert glossary["Break-even price"] == "بریک ایون قیمت"
    assert glossary["Sharpe ratio"] == "شارپ ریشو"
    assert all(value.strip() and "{{" not in value for value in glossary.values())


@pytest.mark.parametrize("language, present", [("ur", True), ("en", False), ("ur-latn", False)])
def test_only_urdu_replies_get_the_glossary(client, db, portfolio_user, language, present):
    ctx = _context(db, portfolio_user, lang=language)
    assert bool(ctx.data["urdu_glossary"]) is present


def test_the_prompt_tells_the_model_to_use_the_glossary_and_keep_roman_urdu_terms():
    prompt = chat_prompt.system_prompt("{}", "ur")
    assert "urdu_glossary" in prompt and "never translate one yourself" in prompt
    assert "do not invent Roman Urdu spellings" in prompt


def test_the_glossary_covers_the_new_terms_and_every_forecast_stocks_sector(db):
    from models.stock import Stock

    glossary = chat_context.urdu_glossary()
    assert glossary["Forecast"] == "پیش گوئی"
    assert glossary["Low confidence"] == "کم اعتماد"
    assert glossary["Confidence"] == "اعتماد"
    assert "Not better than assuming tomorrow's close equals today's" in glossary
    sectors = {
        s for (s,) in db.query(Stock.sector).filter(Stock.ticker.in_(settings.tracked_tickers))
    }
    assert sectors and sectors <= set(glossary), sectors - set(glossary)


@pytest.mark.parametrize(
    "rule",
    [
        "Never put a figure in quotation marks.",
        "it comes from a past test that uses information from after its start date",
        "Never call a backtest figure the portfolio's annual return, return or profit.",
        "(OGDC, never a transliteration)",
        "Do not add English words in brackets after Urdu words.",
        "mention at most 3 of its stocks unless the user asks for all of them",
        'always call it by CONTEXT\'s "portfolio_name", exactly as written there',
        "Never say the user holds, owns, has or bought these stocks, unless the user says so.",
        "When the user asks what to invest in or which stock to buy, do not refuse.",
        "with only a small, low-confidence forecast tilt",
        "forecasts cover only the next trading day, so they say nothing about the long term",
        "Point them to the Portfolio and Backtest screens.",
        "Never write CONTEXT's field names (such as share_of_capital_pct or break_even_price)",
        'Call them recommended stocks, never "holdings" or "your stocks".',
        "refers to the same measure as your previous answer",
        "a tie counts as one place, so the second lowest is the next different value",
        "When you refuse such a request, stay polite",
        "then offer what you can do instead (explain their portfolio, a forecast, news sentiment",
    ],
)
def test_prompt_v3_carries_every_rule(rule):
    assert chat_prompt.PROMPT_VERSION == "prompt-v3.2"
    assert rule in chat_prompt.system_prompt("{}", "en")


@pytest.mark.parametrize("language, words", [("en", 120), ("ur", 150), ("ur-latn", 150)])
def test_reply_length_guidance_depends_on_the_language(language, words):
    assert f"in about {words} words" in chat_prompt.system_prompt("{}", language)


def test_the_last_exchange_survives_even_when_the_context_fills_the_budget():
    from integrations.llm.base import Turn

    history = [  # oldest first, as stored
        Turn("user", "older question"),
        Turn("assistant", "older answer"),
        Turn("user", "Which holding has the lowest confidence?"),
        Turn("assistant", "MARI, EFERT, FFC, HUBC and MEBL are tied at 49%."),
    ]
    turns = chat_service._turns(history, "and the second lowest one?", budget_chars=-500)

    assert [t.content for t in turns] == [
        "Which holding has the lowest confidence?",
        "MARI, EFERT, FFC, HUBC and MEBL are tied at 49%.",
        "and the second lowest one?",
    ]


def test_groq_keeps_the_last_exchange_in_a_real_context(client, db, portfolio_user):
    from integrations.llm.base import Turn

    ctx = _context(db, portfolio_user)
    history = [Turn("user", "Which is lowest?"), Turn("assistant", "MARI is lowest at 49%.")]

    _, turns = chat_service.prepare(ctx, history, "and the second?", "groq")

    assert [t.role for t in turns] == ["user", "assistant", "user"]


def test_an_urdu_context_carries_only_the_glossary_entries_it_can_use(client, db, portfolio_user):
    ctx = _context(db, portfolio_user, lang="ur")
    sent = ctx.data["urdu_glossary"]
    full = chat_context.urdu_glossary()

    assert 0 < len(sent) < len(full)
    assert all(full[term] == word for term, word in sent.items())
    # This worked-example portfolio is Moderate, with break-even prices and forecasts
    for term in ("Moderate", "Break-even price", "Total cost", "Forecast", "Low confidence"):
        assert term in sent, term
    # Screen names always; the other risk categories not
    assert {"Portfolio", "Backtest", "Stocks"} <= set(sent)
    assert "Aggressive" not in sent and "Conservative" not in sent
    # Exactly the glossary sectors this portfolio holds
    held = {h["sector"] for h in ctx.data["portfolio"]["recommended_stocks"]}
    all_sectors = {
        chat_context._lookup(chat_context._locale("en"), key)
        for key in chat_context.GLOSSARY_KEYS
        if key.startswith("terms.sector.")
    }
    assert {term for term in sent if term in all_sectors} == held & all_sectors


def test_glossary_for_matches_field_names_not_only_words():
    text = (
        '{"portfolio":{"totals":{"total_cost":"Rs. 1.00"}},'
        '"risk_profile":{"category":"aggressive"}}'
    )
    sent = chat_context.glossary_for(text)
    assert "Total cost" in sent and "Aggressive" in sent
    assert "Sharpe ratio" not in sent and "Moderate" not in sent


@pytest.mark.parametrize(
    "language, name",
    [
        ("en", "your InvestIQ recommended portfolio"),
        ("ur", "آپ کا InvestIQ تجویز کردہ پورٹ فولیو"),
        ("ur-latn", "aap ka InvestIQ recommended portfolio"),
    ],
)
def test_the_context_names_the_portfolio_as_a_recommendation(
    client, db, portfolio_user, language, name
):
    ctx = _context(db, portfolio_user, lang=language)
    assert ctx.data["portfolio_name"] == name
    # Its stocks are "recommended_stocks", never "holdings", and nothing says "bought"
    assert "recommended_stocks" in ctx.data["portfolio"]
    assert '"holdings"' not in ctx.json and "bought" not in ctx.data["portfolio"]["totals"]
