"""
Steps 6.4-6.5: the backtest endpoints. Prices are MOCK stocks inserted into the test database
only (deterministic synthetic walks, tests/synthetic.py); the arithmetic itself is checked
against the hand-worked fixture in tests/test_backtest_engine.py, so these tests check that
the API runs it on the stored data, stores it, and refuses what it should.
"""

import datetime
import hashlib
import json
import shutil
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from core.config import settings
from models.backtest import BacktestResult
from models.portfolio import Portfolio, PortfolioHolding
from models.risk_profile import RiskCategory, RiskProfile
from models.stock import PricePoint, Stock, StockDividend
from models.user import User
from services import cost_engine, index_data
from tests.conftest import register_and_login
from tests.synthetic import make_ohlcv

PKT = ZoneInfo("Asia/Karachi")
FIXTURES = Path(__file__).parent / "fixtures"
TRACKED = ["MOCK_A", "MOCK_B", "MOCK_C", "MOCK_D", "MOCK_E"]
DAYS = 1150  # 3 Jan 2022 to mid-2026: three years plus a year of closes before the start


def _stock(db, ticker, sector, days=DAYS, seed=1, factor=D(1), start_price=100.0):
    stock = Stock(ticker=ticker, name=f"{ticker} (mock)", sector=sector)
    db.add(stock)
    db.flush()
    frame = make_ohlcv(days=days, seed=seed, start_price=start_price)
    if days < DAYS:
        frame["date"] = make_ohlcv(days=DAYS)["date"].iloc[-days:].to_numpy()
    db.add_all(
        PricePoint(
            stock_id=stock.id,
            timestamp=datetime.datetime.combine(row.date.date(), datetime.time(), PKT),
            close=D(str(round(row.close, 2))) * factor,
            split_factor=factor,
            volume=1000,
        )
        for row in frame.itertuples()
    )
    return stock


@pytest.fixture
def market(db, monkeypatch, fake_redis):
    stocks = {
        t: _stock(db, t, f"MOCK sector {i % 3}", seed=10 + i, start_price=50 + 20 * i)
        for i, t in enumerate(TRACKED)
    }
    stocks["MOCK_NEW"] = _stock(db, "MOCK_NEW", "MOCK sector 0", days=300, seed=3)
    stocks["MOCK_REV"] = _stock(db, "MOCK_REV", "MOCK sector 1", seed=4, factor=D("0.5"))
    db.add(StockDividend(stock_id=stocks["MOCK_A"].id, ex_date=datetime.date(2025, 6, 2),
                         amount=D("3"), source="yahoo"))  # fmt: skip
    db.commit()
    monkeypatch.setattr(settings, "TRACKED_TICKERS", ",".join(TRACKED))
    return stocks


def _investor(client, db, category=RiskCategory.aggressive):
    headers = register_and_login(client)
    email = client.get("/users/me", headers=headers).json()["email"]
    user = db.query(User).filter(User.email == email).one()
    db.add(RiskProfile(user_id=user.id, category=category, answers={}))
    db.commit()
    return headers, user


def _portfolio(db, user, weights: dict[str, str], stocks) -> Portfolio:
    """A stored Phase 5 portfolio; only the fields a backtest reads matter."""
    zero = D(0)
    portfolio = Portfolio(
        user_id=user.id, status="active", risk_category="aggressive", capital=D("100000"),
        filer_status="filer", shariah_only=False, excluded_tickers=[],
        commission_rate=cost_engine.load_rates().commission_rate, rates_version="test",
        model_version="test", prices_as_of=datetime.date(2026, 5, 1), input_snapshot={},
        gross_total=zero, charges_total=zero, cost_total=zero, idle_cash=zero,
    )  # fmt: skip
    for position, (ticker, weight) in enumerate(weights.items()):
        portfolio.holdings.append(
            PortfolioHolding(
                stock_id=stocks[ticker].id, position=position, shares=1, reference_price=zero,
                target_weight=D(weight), allocation_pct=D(weight), gross_value=zero,
                commission=zero, sales_tax=zero, cdc_fee=zero, psx_trading_fee=zero,
                psx_regulatory_fee=zero, secp_levy=zero, nccpl_trade_fee=zero,
                nccpl_secp_fee=zero, buy_charges=zero, total_cost=zero, projection={},
            )  # fmt: skip
        )
    db.add(portfolio)
    db.commit()
    return portfolio


WEIGHTS = {"MOCK_A": "40.0000", "MOCK_B": "35.0000", "MOCK_C": "25.0000"}


def _custom(holdings, years=3, capital="100000", filer="filer"):
    return {
        "years": years,
        "custom": {
            "capital": capital,
            "filer_status": filer,
            "holdings": [{"ticker": t, "weight_pct": w} for t, w in holdings],
        },
    }


def test_stored_portfolio_backtest_adds_up_and_is_stored(client, db, market):
    headers, user = _investor(client, db)
    portfolio = _portfolio(db, user, WEIGHTS, market)
    response = client.post(
        "/backtest/run", json={"portfolio_id": str(portfolio.id)}, headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()

    period = body["period"]
    start, end = (datetime.date.fromisoformat(period[k]) for k in ("start", "end"))
    assert period["years"] == 3 and end.year - start.year == 3
    assert len(body["series"]) == period["trading_days"] + 1
    assert body["series"][0]["portfolio"] == "100000.00"
    assert body["series"][0]["benchmark"] == "100000.00"

    costs, holdings = body["portfolio"]["costs"], body["portfolio"]["holdings"]
    rates = cost_engine.load_rates()
    for h in holdings:
        # Whole shares within weight x capital at the stored start-date close (Phase 5's rule)
        budget = D(WEIGHTS[h["ticker"]]) / 100 * D("100000")
        assert h["shares_bought"] == cost_engine.max_affordable_shares(
            D(h["buy_price"]), budget, rates
        )
    dividends = D(costs["dividends_gross"]) - D(costs["wht"])
    proceeds = sum(D(h["sale_net"]) for h in holdings)
    assert D(costs["end_value_net"]) == D(costs["idle_cash"]) + dividends + proceeds
    assert D(costs["end_value_before_sale"]) == D(body["series"][-1]["portfolio"])
    # The Rs 3 MOCK_A dividend, 15% WHT for a filer
    assert D(costs["wht"]) == (D(costs["dividends_gross"]) * D("0.15")).quantize(D("0.01"))
    total = (D(costs["end_value_net"]) / D("100000") - 1).quantize(D("0.000001"))
    assert D(body["portfolio"]["metrics"]["total_return"]) == total

    assert body["start_date_rules"]["status"] == "available"
    assert body["start_date_rules"]["risk_category"] == "aggressive"
    assert body["benchmark"]["kind"] == "forecast_stocks_equal_weight"
    assert body["benchmark"]["tickers"] == TRACKED
    assert body["kse100"] == {
        "status": "awaiting_permission",
        "dataset_version": None,
        "metrics": None,
    }
    assert body["risk_free"]["version"] == "sbp-mtb-3m-2026-09-30"
    assert body["assumptions"]["dividends_checked"] is False

    stored = db.get(BacktestResult, body["id"])
    assert stored.portfolio_id == portfolio.id and stored.kind == "portfolio"
    assert stored.end_value_net == D(costs["end_value_net"])
    assert client.get(f"/backtest/{body['id']}", headers=headers).json() == body


def test_longer_period_is_allowed_up_to_the_history_available(client, db, market):
    headers, user = _investor(client, db)
    portfolio = _portfolio(db, user, WEIGHTS, market)
    body = {"portfolio_id": str(portfolio.id), "years": 4}
    assert client.post("/backtest/run", json=body, headers=headers).status_code == 201
    body["years"] = 5
    response = client.post("/backtest/run", json=body, headers=headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "insufficient_history"


def test_custom_mix_runs_without_a_start_date_variant(client, db, market):
    headers, _ = _investor(client, db)
    response = client.post(
        "/backtest/run", json=_custom([("MOCK_D", "60"), ("mock_e", "40")]), headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "custom" and body["portfolio_id"] is None
    assert [h["ticker"] for h in body["inputs"]["holdings"]] == ["MOCK_D", "MOCK_E"]
    assert body["start_date_rules"] == {"status": "not_applicable", "reason": None,
        "risk_category": None, "metrics": None, "costs": None, "holdings": None}  # fmt: skip
    assert body["inputs"]["commission_pct"] == "0.150"
    assert db.get(BacktestResult, body["id"]).kind == "custom"
    assert db.query(Portfolio).count() == 0


@pytest.mark.parametrize(
    "holdings, code, extra",
    [
        ([("MOCK_A", "60"), ("MOCK_B", "30")], "weights_not_100", {"total_pct": "90"}),
        ([("MOCK_A", "50"), ("mock_a", "50")], "duplicate_stocks", {"tickers": ["MOCK_A"]}),
        ([("MOCK_A", "50"), ("NOPE", "50")], "unknown_stock", {"tickers": ["NOPE"]}),
        ([("MOCK_A", "50"), ("MOCK_REV", "50")], "split_not_supported", {"ticker": "MOCK_REV"}),
        ([("MOCK_A", "99.99"), ("MOCK_B", "0.01")], "weight_too_small", {"tickers": ["MOCK_B"]}),
    ],
)
def test_custom_mix_is_refused_with_a_reason(client, db, market, holdings, code, extra):
    headers, _ = _investor(client, db)
    response = client.post("/backtest/run", json=_custom(holdings), headers=headers)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert detail["code"] == code
    assert {k: detail[k] for k in extra} == extra


def test_a_stock_with_too_little_history_is_named_with_its_first_date(client, db, market):
    headers, _ = _investor(client, db)
    response = client.post(
        "/backtest/run", json=_custom([("MOCK_A", "50"), ("MOCK_NEW", "50")]), headers=headers
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "insufficient_history"
    (stock,) = detail["stocks"]
    assert stock["ticker"] == "MOCK_NEW"
    assert stock["first_date"] > detail["required_start"]


@pytest.mark.parametrize(
    "body",
    [
        {"years": 2, "custom": {"capital": "1000", "filer_status": "filer",
                                "holdings": [{"ticker": "MOCK_A", "weight_pct": "100"}]}},
        {"years": 3},
    ],
)  # fmt: skip
def test_fewer_than_three_years_or_no_source_is_invalid(client, db, market, body):
    headers, _ = _investor(client, db)
    assert client.post("/backtest/run", json=body, headers=headers).status_code == 422


def test_kse100_appears_once_a_licensed_series_covers_the_period(client, db, market, tmp_path):
    headers, user = _investor(client, db)
    portfolio = _portfolio(db, user, WEIGHTS, market)
    days = sorted({p.timestamp.astimezone(PKT).date() for p in market["MOCK_A"].price_points})
    csv = tmp_path / "MOCK_kse_full.csv"
    csv.write_text(
        "date,close\n" + "".join(f"{d},{1000 + i}\n" for i, d in enumerate(days)), encoding="utf-8"
    )
    shutil.copy(FIXTURES / "MOCK_kse100.json", csv.with_suffix(".json"))
    manifest = csv.with_suffix(".json")
    meta = json.loads(manifest.read_text(encoding="utf-8"))
    meta["sha256"] = hashlib.sha256(csv.read_bytes()).hexdigest()
    manifest.write_text(json.dumps(meta), encoding="utf-8")
    index_data.load(db, csv, allow_mock=True)

    body = client.post(
        "/backtest/run", json={"portfolio_id": str(portfolio.id)}, headers=headers
    ).json()
    assert body["kse100"]["status"] == "available"
    assert body["kse100"]["dataset_version"] == "MOCK-kse100-test"
    assert body["series"][0]["kse100"] == "100000.00"
    assert body["kse100"]["metrics"]["total_return"] is not None


def test_universe_lists_stocks_with_three_years_and_leaves_out_fractional_splits(
    client, db, market
):
    headers, _ = _investor(client, db)
    body = client.get("/backtest/universe", headers=headers).json()
    tickers = [s["ticker"] for s in body["stocks"]]
    assert set(TRACKED) <= set(tickers)
    assert "MOCK_NEW" not in tickers
    assert {"ticker": "MOCK_REV", "reason": "split_not_supported"} in body["left_out"]
    assert body["min_years"] == 3
    assert {s["max_years"] for s in body["stocks"] if s["ticker"] in TRACKED} == {4}


def test_backtests_need_a_risk_profile_and_a_login(client, market):
    headers = register_and_login(client)
    response = client.post("/backtest/run", json=_custom([("MOCK_A", "100")]), headers=headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "risk_profile_required"
    assert client.get("/backtest/universe").status_code == 401


def test_another_users_portfolio_and_result_are_not_found(client, db, market):
    owner_headers, owner = _investor(client, db)
    portfolio = _portfolio(db, owner, WEIGHTS, market)
    result = client.post(
        "/backtest/run", json={"portfolio_id": str(portfolio.id)}, headers=owner_headers
    ).json()

    other_headers, _ = _investor(client, db)
    response = client.post(
        "/backtest/run", json={"portfolio_id": str(portfolio.id)}, headers=other_headers
    )
    assert response.json()["detail"]["code"] == "portfolio_not_found"
    response = client.get(f"/backtest/{result['id']}", headers=other_headers)
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "backtest_not_found"


def test_universe_without_any_prices_is_empty_not_an_error(client, db):
    headers, _ = _investor(client, db)
    response = client.get("/backtest/universe", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "latest_date": None,
        "min_years": 3,
        "max_years": None,
        "stocks": [],
        "left_out": [],
    }
