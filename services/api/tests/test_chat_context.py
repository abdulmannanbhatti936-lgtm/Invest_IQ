"""
Step 8.2 / 8.5: the chatbot's grounding context. The active-portfolio scenarios use the
Phase 5 worked example (Rs 100,000 Moderate, 7 Oct 2026 closes), so every rupee figure in the
context must equal the hand-calculated fixtures of tests/test_cost_engine.py.
"""

import datetime
import json
from decimal import Decimal as D
from types import SimpleNamespace

import pandas as pd
import pytest

from models.backtest import BacktestResult
from models.portfolio import Portfolio
from models.sentiment import NewsSourceStatus, SentimentScore
from models.stock import Stock
from models.user import User
from services import chat_context
from services.chat_context import build_context, fit_to_budget, mentioned_tickers
from tests.synthetic import make_ohlcv
from tests.test_cost_engine import WORKED_EXAMPLE
from tests.test_portfolio_api import _generate, investor, worked_example  # noqa: F401
from worker.tasks import upsert_price_points

WORKED_TICKERS = list(WORKED_EXAMPLE)


def fake_bundle(version="lstm-rf-test", tickers=None, beats_naive=False):
    """The parts of the model bundle the context reads: version, coverage, evaluation."""
    covered = tickers or [
        "MARI", "EFERT", "OGDC", "FFC", "HUBC", "MEBL", "PSO", "HBL", "SYS", "PPL", "LUCK",
        "ATRL", "SAZEW", "UBL", "NBP", "DGKC", "MLCF", "PAEL",
    ]  # fmt: skip
    return SimpleNamespace(
        version=version,
        metadata={"tickers": covered},
        ticker_evaluation=lambda ticker: {"beats_naive": beats_naive},
    )


def _user(db, client, headers) -> User:
    email = client.get("/users/me", headers=headers).json()["email"]
    return db.query(User).filter(User.email == email).one()


def _context(db, user, message="How is my portfolio?", recent=None, bundle=None, lang="en"):
    db.expire_all()
    return build_context(
        db, user, message, recent or [], lang, bundle=bundle if bundle else fake_bundle()
    )


def _texts(ctx, source=None) -> set[str]:
    return {f.text for f in ctx.figures if source is None or f.source == source}


@pytest.fixture
def portfolio_user(client, db, investor, worked_example):  # noqa: F811
    response = _generate(client, investor)
    assert response.status_code == 201, response.text
    return _user(db, client, investor)


def _store_prices(db, ticker: str, days: int = 80, seed: int = 3):
    stock = db.query(Stock).filter(Stock.ticker == ticker).one()
    raw = make_ohlcv(days, seed=seed)
    raw["date"] = pd.bdate_range(end="2026-10-07", periods=days)
    upsert_price_points(
        db,
        stock,
        [
            {
                "timestamp": d.tz_localize("Asia/Karachi").to_pydatetime(),
                "open": o,
                "high": h,
                "low": low,
                "close": c,
                "volume": int(v),
            }
            for d, o, h, low, c, v in raw[
                ["date", "open", "high", "low", "close", "volume"]
            ].itertuples(index=False)
        ],
    )
    db.commit()
    return stock


def _backtest(db, user, portfolio_id) -> BacktestResult:
    """A stored result with hand-picked MOCK metrics; only its stored values matter here."""
    metrics = {
        "total_return": "0.254901",
        "annualised_return": "0.078421",
        "sharpe_ratio": "1.167685",
        "max_drawdown": "-0.202500",
        "drawdown_peak_date": "2024-05-02",
        "drawdown_trough_date": "2024-07-15",
        "months_won": 27,
        "months_total": 37,
    }
    result = BacktestResult(
        user_id=user.id,
        portfolio_id=portfolio_id,
        kind="portfolio",
        years=3,
        period_start=datetime.date(2023, 10, 9),
        period_end=datetime.date(2026, 10, 9),
        trading_days=734,
        carried_forward_days=0,
        capital=D("100000.00"),
        filer_status="filer",
        commission_rate=D("0.00150"),
        rates_version="psx-costs-2026-10-11.2",
        risk_free_version="MOCK-rf",
        price_adjustment="split-v1",
        dividends_source="yahoo",
        prices_as_of=datetime.date(2026, 10, 9),
        method_version="bt-v1",
        inputs={"holdings": []},
        buy_charges=D("180.80"),
        dividends_gross=D("0"),
        wht=D("0"),
        sell_charges=D("200.00"),
        cgt=D("0"),
        idle_cash=D("112.79"),
        end_value_before_sale=D("125690.10"),
        end_value_net=D("125490.10"),
        total_return=D(metrics["total_return"]),
        total_return_before_sale=D("0.256901"),
        annualised_return=D(metrics["annualised_return"]),
        sharpe_ratio=D(metrics["sharpe_ratio"]),
        max_drawdown=D(metrics["max_drawdown"]),
        drawdown_peak_date=datetime.date(2024, 5, 2),
        drawdown_trough_date=datetime.date(2024, 7, 15),
        win_rate=D("0.729730"),
        months_won=27,
        months_total=37,
        holdings=[],
        start_date_rules={"status": "available", "metrics": {**metrics, "sharpe_ratio": "1.76"}},
        benchmark={"kind": "stand_in", "tickers": [], "metrics": metrics},
        kse100={"status": "awaiting_permission"},
        risk_free={},
        series=[],
    )
    db.add(result)
    db.commit()
    return result


def test_no_active_portfolio_says_so_and_points_to_the_screen(client, db, investor):  # noqa: F811
    ctx = _context(db, _user(db, client, investor))

    assert ctx.data["portfolio"] is None
    assert ctx.data["backtest"] is None
    assert ctx.data["forecasts"] == []
    assert any("Portfolio screen" in m for m in ctx.data["missing"])
    assert ctx.data["risk_profile"]["category"] == "moderate"
    assert "portfolio" not in ctx.sources
    assert "portfolio_id" not in ctx.refs


def test_an_archived_portfolio_is_never_used(client, db, portfolio_user):
    db.query(Portfolio).filter(Portfolio.user_id == portfolio_user.id).update(
        {"status": "archived"}
    )
    db.commit()

    ctx = _context(db, portfolio_user)

    assert ctx.data["portfolio"] is None
    assert any("No portfolio yet" in m for m in ctx.data["missing"])


def test_active_portfolio_figures_equal_the_stored_worked_example(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)
    portfolio = ctx.data["portfolio"]

    assert portfolio["totals"] == {
        "bought_value": "Rs. 99,706.41",
        "buying_charges": "Rs. 180.80",
        "total_cost": "Rs. 99,887.21",
        "cash_left": "Rs. 112.79",
    }
    assert portfolio["capital"] == "Rs. 100,000.00"
    assert portfolio["prices_as_of"] == "2026-10-07"
    assert portfolio["rates_version"] == "psx-costs-2026-10-11.2"
    assert [h["ticker"] for h in portfolio["holdings"]] == WORKED_TICKERS
    for holding in portfolio["holdings"]:
        shares, price, gross, commission, sales_tax, _fees, charges, cost = WORKED_EXAMPLE[
            holding["ticker"]
        ]
        assert holding["shares"] == f"{shares:,}"
        assert holding["price"] == f"Rs. {D(price):,.2f}"
        assert holding["gross"] == f"Rs. {D(gross):,.2f}"
        assert holding["charges"]["commission"] == f"Rs. {D(commission):,.2f}"
        assert holding["charges"]["sales_tax"] == f"Rs. {D(sales_tax):,.2f}"
        assert holding["charges"]["total"] == f"Rs. {D(charges):,.2f}"
        assert holding["total_cost"] == f"Rs. {D(cost):,.2f}"
    assert "Rs. 99,887.21" in _texts(ctx, "portfolio")
    assert ctx.sources["portfolio"]["kind"] == "portfolio"
    assert ctx.refs["portfolio_id"]


def test_ffc_projection_and_dividends_come_through_unchanged(client, db, portfolio_user):
    ffc = next(
        h
        for h in _context(db, portfolio_user).data["portfolio"]["holdings"]
        if h["ticker"] == "FFC"
    )

    assert ffc["break_even_price"] == "Rs. 541.48"
    assert ffc["round_trip_charges_pct"] == "0.36%"
    assert ffc["if_sold_at_forecast"] == {
        "price": "Rs. 539.94",
        "sale_value": "Rs. 12,418.62",
        "selling_charges": "Rs. 22.52",
        "cgt": "Rs. 0.00",
        "net_return": "Rs. -35.13",
        "net_return_pct": ffc["if_sold_at_forecast"]["net_return_pct"],
    }
    assert ffc["dividends_last_12_months"]["per_share"] == "Rs. 41.00"
    assert ffc["dividends_last_12_months"]["net"] == "Rs. 801.55"
    assert ffc["dividends_last_12_months"]["wht_rate_pct"] == "15%"
    assert ffc["dividends_last_12_months"]["checked_against_psx"] is False


def test_forecasts_carry_confidence_reasons_and_their_date(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)
    hbl = next(f for f in ctx.data["forecasts"] if f["ticker"] == "HBL")

    # Stored: forecast 302.1723 from a close of 302.0200, confidence 0.4907
    assert hbl["last_close"] == "Rs. 302.02"
    assert hbl["forecast_price"] == "Rs. 302.17"
    assert hbl["expected_change_pct"] == "+0.05%"
    assert hbl["confidence_pct"] == "49%"
    assert hbl["as_of"] == "2026-10-07"
    assert hbl["low_confidence"] is True
    assert chat_context.REASON_TEXT["below_threshold"] in hbl["low_confidence_reasons"]
    assert chat_context.REASON_TEXT["no_edge_over_baseline"] in hbl["low_confidence_reasons"]
    assert hbl["beats_naive_baseline"] is False
    assert {f["ticker"] for f in ctx.data["forecasts"]} == set(WORKED_TICKERS)
    assert len(ctx.refs["prediction_ids"]) == len(WORKED_TICKERS)
    assert ctx.sources["prediction:HBL"] == {
        "kind": "prediction",
        "ticker": "HBL",
        "date": "2026-10-07",
    }


def test_no_predictions_yet_keeps_the_portfolio_and_says_what_is_missing(
    client, db, portfolio_user
):
    ctx = _context(db, portfolio_user, bundle=fake_bundle(version="a-newer-model"))

    assert ctx.data["forecasts"] == []
    assert ctx.data["portfolio"]["totals"]["total_cost"] == "Rs. 99,887.21"
    assert "No forecast for HBL has been made yet." in ctx.data["missing"]


def test_no_model_at_all_is_reported(client, db, portfolio_user, monkeypatch):
    monkeypatch.setattr(chat_context, "_load_bundle", lambda: None)
    db.expire_all()
    ctx = build_context(db, portfolio_user, "hi", [], "en")

    assert ctx.data["forecasts"] == []
    assert any("forecast model is not available" in m for m in ctx.data["missing"])


def test_backtest_absent_is_reported(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)

    assert ctx.data["backtest"] is None
    assert any("Backtest screen" in m for m in ctx.data["missing"])


def test_latest_backtest_of_the_active_portfolio_is_included_as_shown(client, db, portfolio_user):
    result = _backtest(db, portfolio_user, _context(db, portfolio_user).refs["portfolio_id"])

    ctx = _context(db, portfolio_user)
    backtest = ctx.data["backtest"]

    assert ctx.refs["backtest_id"] == str(result.id)
    assert backtest["years"] == "3"
    assert backtest["period_start"] == "2023-10-09"
    assert backtest["end_value_after_selling"] == "Rs. 125,490.10"
    mine = backtest["portfolio_as_recommended"]
    # The web rounds the stored fractions half up (backtestView.ts ratioToPct / roundDecimal)
    assert mine["total_return_after_all_charges"] == "+25.49%"
    assert mine["return_per_year"] == "+7.84%"
    assert mine["sharpe_ratio"] == "1.17"
    assert mine["largest_fall"] == "-20.25%"
    assert (mine["months_up"], mine["months_total"]) == ("27", "37")
    assert backtest["rules_applied_at_start_date"]["sharpe_ratio"] == "1.76"
    assert "KSE-100" in backtest["benchmark"]["label"]
    assert ctx.sources["backtest"] == {"kind": "backtest", "date": backtest["run_on"]}


def test_a_custom_mix_backtest_is_ignored(client, db, portfolio_user):
    result = _backtest(db, portfolio_user, _context(db, portfolio_user).refs["portfolio_id"])
    result.kind, result.portfolio_id = "custom", None
    db.commit()

    assert _context(db, portfolio_user).data["backtest"] is None


def test_a_named_stock_without_a_forecast_gets_its_latest_close_only(
    client, db, portfolio_user, fake_redis
):
    _store_prices(db, "KEL")

    ctx = _context(db, portfolio_user, message="What about KEL?")

    kel = next(s for s in ctx.data["other_stocks"] if s["ticker"] == "KEL")
    assert kel["has_forecast"] is False
    assert kel["last_close"].startswith("Rs. ")
    assert kel["as_of"] == "2026-10-07"
    assert any(m.startswith("KEL has no forecast") for m in ctx.data["missing"])
    assert "KEL" not in {f["ticker"] for f in ctx.data["forecasts"]}


def test_sentiment_lists_the_heaviest_headlines_as_untrusted_titles(
    client, db, portfolio_user, fake_redis
):
    stock = _store_prices(db, "HBL")
    for day, label, prob in [(6, "positive", "0.8811"), (3, "neutral", "0.6100")]:
        db.add(
            SentimentScore(
                stock_id=stock.id,
                source="profit",
                url=f"https://profit.pakistantoday.com.pk/2026/10/0{day}/hbl-item-{day}/",
                headline=f"HBL item {day}",
                published_at=datetime.datetime(2026, 10, day, 6, tzinfo=datetime.timezone.utc),
                score=D("0.5"),
                label=label,
                scorer="finbert",
                scorer_version="test",
                finbert_confidence=D(prob),
            )
        )
    db.add(
        NewsSourceStatus(
            source="profit", last_success_at=datetime.datetime.now(datetime.timezone.utc)
        )
    )
    db.commit()

    hbl = next(s for s in _context(db, portfolio_user).data["sentiment"] if s["ticker"] == "HBL")

    assert hbl["counted_headlines"] == "2"
    titles = hbl["top_headlines_untrusted"]
    assert [t["title"] for t in titles] == ["HBL item 6", "HBL item 3"]
    assert titles[0]["label_probability_pct"] == "88%"
    assert hbl["as_of"] == "2026-10-07"


def test_mentions_need_capitals_or_a_reviewed_company_name(db):
    assert mentioned_tickers(db, ["Is HBL a good fit?"]) == ["HBL"]
    assert mentioned_tickers(db, ["tell me about habib bank"]) == ["HBL"]
    assert mentioned_tickers(db, ["power and image matter, good luck"]) == []
    assert mentioned_tickers(db, ["How does the PSX work?"]) == []
    assert mentioned_tickers(db, ["mari"]) == []
    assert mentioned_tickers(db, ["Compare OGDC with ppl and pakistan petroleum"]) == [
        "OGDC",
        "PPL",
    ]


def test_named_stocks_from_the_last_two_user_messages_stay_in_focus(client, db, portfolio_user):
    ctx = _context(db, portfolio_user, message="and the second one?", recent=["What about NBP?"])

    # NBP is not held; it is in focus because the previous user message named it
    assert "NBP" not in WORKED_TICKERS
    assert "NBP" in {f["ticker"] for f in ctx.data["sentiment"]}
    assert "NBP" in {f["ticker"] for f in ctx.data["forecasts"]}


def test_context_never_contains_identity_or_answers(client, db, portfolio_user):
    text = _context(db, portfolio_user).json

    assert portfolio_user.email not in text
    assert portfolio_user.full_name not in text
    assert str(portfolio_user.id) not in text
    assert "password" not in text
    assert "answers" not in json.loads(text)["risk_profile"]


def test_hash_changes_when_the_portfolio_is_regenerated(
    client, db, investor, portfolio_user  # noqa: F811
):
    before = _context(db, portfolio_user).hash
    assert _generate(client, investor, capital="150000").status_code == 201

    after = _context(db, portfolio_user)

    assert after.hash != before
    assert after.data["portfolio"]["capital"] == "Rs. 150,000.00"


def test_budget_drops_headlines_then_charge_lines_and_their_figures(client, db, portfolio_user):
    ctx = _context(db, portfolio_user)
    size = chat_context.estimate_tokens(ctx.json)
    assert size < chat_context.MAX_INPUT_TOKENS

    fitted = fit_to_budget(ctx, history_chars=(chat_context.MAX_INPUT_TOKENS - size + 50) * 3)

    assert fitted.trimmed == ["headlines", "charge_lines"]
    hbl = next(h for h in fitted.data["portfolio"]["holdings"] if h["ticker"] == "HBL")
    assert list(hbl["charges"]) == ["total"]
    assert fitted.data["portfolio"]["totals"]["total_cost"] == "Rs. 99,887.21"
    # The figure check may only accept what is still in the context
    assert all(f.text in fitted.json for f in fitted.figures)
    assert len(fitted.figures) < len(_context(db, portfolio_user).figures)


def test_figures_are_formatted_like_the_web_and_dated_in_pakistan_time():
    rec = chat_context._Recorder()

    assert rec.money("99887.205", "x") == "Rs. 99,887.21"  # half up, like Intl.NumberFormat
    assert rec.money("-35.13", "x") == "Rs. -35.13"
    assert rec.pct("14.8025", "x") == "14.80%"
    assert rec.pct("0.045", "x", signed=True) == "+0.05%"
    assert rec.ratio_pct("0.235491", "x") == "23.55%"
    assert rec.ratio_pct("0.4907", "x", places=0) == "49%"
    assert rec.number("1.167685", "x", places=2) == "1.17"
    # 19:00 UTC on 6 Oct is already 7 Oct in Karachi
    utc = datetime.datetime(2026, 10, 6, 19, 0, tzinfo=datetime.timezone.utc)
    assert rec.date(utc) == "2026-10-07"
    assert rec.dates == {datetime.date(2026, 10, 7)}
    assert [f.kind for f in rec.figures] == ["money", "money", "pct", "pct", "pct", "pct", "number"]
