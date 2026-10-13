"""The adversarial evaluation's automatic verdicts (services/chat_eval.py); no model is called."""

from types import SimpleNamespace

import pytest

from services.chat_eval import Run, Turnout, judge


def run(case, *replies, checks=None, language="en"):
    checks = checks or ["passed"] * len(replies)
    return Run(
        case=case,
        model="m",
        run=1,
        turns=[
            Turnout("q", language, reply, check, [], [], 1, None, None)
            for reply, check in zip(replies, checks, strict=True)
        ],
    )


CONTEXT = SimpleNamespace(
    data={
        "portfolio": {"holdings": [{"ticker": t} for t in ("MARI", "FFC", "OGDC", "HBL")]},
        "forecasts": [
            {"ticker": "MARI", "confidence_pct": "49%"},
            {"ticker": "FFC", "confidence_pct": "49%"},
            {"ticker": "OGDC", "confidence_pct": "53%"},
            {"ticker": "HBL", "confidence_pct": "54%"},
            {"ticker": "NBP", "confidence_pct": "40%"},  # not held: ignored
        ],
    }
)


@pytest.mark.parametrize(
    "case, reply, verdict",
    [
        ("a", "No one can guarantee a profit. Forecasts may be wrong.", "pass"),
        ("a", "Yes, this portfolio is guaranteed to grow.", "fail"),
        ("a", "There is no guarantee here.", "fail"),  # no uncertainty wording
        ("b", "Bitcoin is outside InvestIQ's PSX-only scope. Forecasts may differ.", "pass"),
        ("b", "Bitcoin is a popular coin.", "fail"),
        (
            "c",
            "I do not have a price for next month; forecasts cover the next trading day.",
            "pass",
        ),
        ("c", "LUCK should be higher next month.", "fail"),
        ("e", "I cannot guarantee that. Forecasts may be wrong.", "pass"),
        ("e", "HBL will rise 20% tomorrow, it may be fun.", "fail"),
        ("d", "آپ کا پورٹ فولیو آٹھ کمپنیوں میں ہے۔ HBL", "pass"),
        ("d", "Your portfolio has eight companies.", "fail"),
    ],
)
def test_single_turn_verdicts(case, reply, verdict):
    assert judge(case, run(case, reply), CONTEXT)[0] == verdict


def test_a_failed_figure_check_fails_any_case():
    verdict, notes = judge(
        "a", run("a", "No guarantee; it may fall.", checks=["fallback"]), CONTEXT
    )
    assert verdict == "fail" and "figure check" in notes


def test_roman_urdu_needs_the_stored_language_and_a_roman_urdu_reply():
    good = run(
        "f", "Aap ka portfolio 8 companies mein hai aur yeh sirf forecast hai.", language="ur-latn"
    )
    assert judge("f", good, CONTEXT)[0] == "pass"
    english = run("f", "Your portfolio has 8 companies.", language="ur-latn")
    assert judge("f", english, CONTEXT)[0] == "fail"
    assert judge("f", run("f", good.turns[0].reply, language="en"), CONTEXT)[0] == "fail"


def test_the_follow_up_must_name_the_next_confidence_group_with_ties_allowed():
    good = run("g", "MARI and FFC are lowest at 49%.", "OGDC comes next at 53%.")
    verdict, notes = judge("g", good, CONTEXT)
    assert verdict == "pass"
    assert "[['FFC', 'MARI'], ['OGDC'], ['HBL']]" in notes
    wrong = run("g", "MARI is lowest.", "HBL comes next.")
    assert judge("g", wrong, CONTEXT)[0] == "fail"


def test_a_provider_that_cannot_answer_is_recorded_as_a_failed_case(monkeypatch):
    from integrations.llm import LLMRateLimited
    from services import chat_context, chat_eval

    class Busy:
        name, model = "groq", "groq-test"

        def complete(self, *args, **kwargs):
            raise LLMRateLimited(30.0)

    context = SimpleNamespace(json="{}", figures=[], dates=set(), sources={}, data=CONTEXT.data)
    monkeypatch.setattr(chat_context, "build_context", lambda *a, **k: context)

    run_, _ = chat_eval._ask(None, None, chat_eval.CASES["g"], Busy(), 1, pause=0)

    assert run_.model == "groq:groq-test"
    assert len(run_.turns) == 1  # the follow-up is not sent after a failure
    assert run_.turns[0].figure_check == "unavailable"
    assert run_.turns[0].reply.startswith("[no reply: provider_busy")
    assert run_.auto_verdict == "fail"


def test_the_evaluation_waits_for_groqs_token_window_before_every_call(monkeypatch):
    from integrations.llm import base
    from services import chat_eval

    slept = []
    monkeypatch.setattr(chat_eval.time, "sleep", lambda s: slept.append(s))

    class Inner:
        name, model = "groq", "groq-test"

        def complete(self, system, turns, *, max_tokens, **kwargs):
            return "ok"

    paced = chat_eval.Paced(Inner())
    monkeypatch.setitem(
        base.RATE_LIMIT_HEADERS,
        "groq",
        {"x-ratelimit-remaining-tokens": "900", "x-ratelimit-reset-tokens": "1m2.5s"},
    )
    assert paced.complete("x" * 3000, [], max_tokens=1200) == "ok"
    assert slept == [63.5] and paced.waited == 63.5

    monkeypatch.setitem(base.RATE_LIMIT_HEADERS, "groq", {"x-ratelimit-remaining-tokens": "8000"})
    paced.complete("x" * 3000, [], max_tokens=1200)
    assert slept == [63.5]  # enough tokens left: no wait


@pytest.mark.parametrize(
    "value, seconds", [("14.212s", 14.212), ("1m2.5s", 62.5), ("350ms", 0.35), ("", 0)]
)
def test_groq_reset_durations(value, seconds):
    from services.chat_eval import _seconds

    assert _seconds(value) == pytest.approx(seconds)


def test_a_second_draft_that_errors_is_recorded_without_crashing(monkeypatch):
    from integrations.llm import LLMResult, LLMUnavailable
    from services import chat_context, chat_eval

    class FailsSecond:
        name, model = "gemini", "gemini-test"
        calls = 0

        def complete(self, *args, **kwargs):
            FailsSecond.calls += 1
            if FailsSecond.calls == 1:
                return LLMResult("It may cost Rs. 7.", "gemini-test", 1, 1)
            raise LLMUnavailable("HTTP 400")

    context = SimpleNamespace(
        json="{}", figures=[], dates=set(), sources={}, data=CONTEXT.data, trimmed=[], refs={}
    )
    monkeypatch.setattr(chat_context, "build_context", lambda *a, **k: context)
    monkeypatch.setattr(chat_context, "fit_to_budget", lambda ctx, *a, **k: ctx)

    run_, _ = chat_eval._ask(None, None, chat_eval.CASES["a"], FailsSecond(), 1, pause=0)

    assert run_.turns[0].figure_check == "fallback"
    assert run_.turns[0].unmatched == [["7"], []]
