"""
Steps 5.6-5.7: the portfolio endpoints. The universe is the worked example's real inputs
(7 Oct 2026 close) on the seeded KSE-100 stocks; everything after it runs for real, so the
API's rupee figures must equal tests/test_cost_engine.py's hand-calculated fixtures exactly.
"""

import datetime
from decimal import Decimal as D

import pytest

from models.portfolio import Portfolio
from models.prediction import Prediction
from models.risk_profile import RiskCategory, RiskProfile
from models.stock import Stock, StockDividend
from models.user import User
from services import portfolio_service
from services.portfolio_service import StockContext, Universe
from tests.conftest import register_and_login
from tests.test_allocation import INPUTS, _candidates
from tests.test_cost_engine import FEE_ORDER, WORKED_EXAMPLE

AS_OF = datetime.date(2026, 10, 7)
# ticker -> (forecast price, close it was made from), as stored in the dev DB
FORECASTS = {
    cells[0]: (D(cells[4]), D(cells[5]))
    for cells in (line.split() for line in INPUTS.strip().splitlines())
}


@pytest.fixture
def worked_example(db, monkeypatch, fake_redis):
    contexts = {}
    for candidate in _candidates():
        stock = db.query(Stock).filter(Stock.ticker == candidate.ticker).one()
        forecast, close = FORECASTS[candidate.ticker]
        prediction = Prediction(
            stock_id=stock.id,
            model_version="lstm-rf-test",
            forecast_price=forecast,
            last_close=close,
            confidence_score=D("0.4907"),
            signal=candidate.signal,
            signal_probability=candidate.signal_probability,
            as_of_date=AS_OF,
        )
        db.add(prediction)
        db.flush()
        contexts[candidate.ticker] = StockContext(
            stock=stock,
            prediction=prediction,
            candidate=candidate,
            as_of=AS_OF,
            low_confidence_reasons=["below_threshold", "no_edge_over_baseline"],
            sentiment_label=None,
            counted_headlines=0,
        )
    ffc = contexts["FFC"].stock
    for ex_date, amount in [
        ("2025-11-03", "9.5"),
        ("2026-03-06", "8.5"),
        ("2026-05-11", "8.5"),
        ("2026-08-10", "14.5"),
        ("2025-10-01", "99"),  # outside the 12 months before 7 Oct 2026
    ]:
        db.add(
            StockDividend(
                stock_id=ffc.id,
                ex_date=datetime.date.fromisoformat(ex_date),
                amount=D(amount),
                source="yahoo",
            )
        )
    db.commit()
    # The request runs in its own session: hand it loaded, detached objects so it never
    # reloads them through this one
    for ctx in contexts.values():
        db.refresh(ctx.stock)
        db.refresh(ctx.prediction)
    db.expunge_all()

    def universe(_db, shariah_only, excluded):
        eligible = {t: c for t, c in contexts.items() if t not in excluded}
        if shariah_only:
            eligible = {
                t: c for t, c in eligible.items() if portfolio_service.is_shariah_compliant(t)
            }
        return Universe("lstm-rf-test", eligible, {t: "excluded" for t in excluded})

    monkeypatch.setattr(portfolio_service, "load_universe", universe)
    return contexts


def _with_profile(db, headers, client, category=RiskCategory.moderate):
    email = client.get("/users/me", headers=headers).json()["email"]
    user = db.query(User).filter(User.email == email).one()
    db.add(RiskProfile(user_id=user.id, category=category, answers={}))
    db.commit()
    return user


@pytest.fixture
def investor(client, db):
    headers = register_and_login(client)
    _with_profile(db, headers, client)
    return headers


def _generate(client, headers, **overrides):
    body = {"capital": "100000", "filer_status": "filer", **overrides}
    return client.post("/portfolio/generate", json=body, headers=headers)


def test_portfolio_figures_equal_the_cost_engine_fixtures(client, investor, worked_example):
    response = _generate(client, investor)
    assert response.status_code == 201, response.text
    body = response.json()

    assert [h["ticker"] for h in body["holdings"]] == list(WORKED_EXAMPLE)
    for holding in body["holdings"]:
        shares, price, gross, commission, sales_tax, fees, charges, cost = WORKED_EXAMPLE[
            holding["ticker"]
        ]
        assert holding["shares"] == shares
        assert D(holding["price"]) == D(price)
        assert D(holding["gross"]) == D(gross)
        assert D(holding["charges"]["commission"]) == D(commission)
        assert D(holding["charges"]["sales_tax"]) == D(sales_tax)
        assert [D(holding["charges"][key]) for key in FEE_ORDER] == [D(f) for f in fees]
        assert D(holding["charges"]["total"]) == D(charges)
        assert D(holding["total_cost"]) == D(cost)

    assert body["totals"] == {
        "gross": "99706.41",
        "charges": "180.80",
        "cost": "99887.21",
        "idle_cash": "112.79",
    }
    assert body["idle"]["flagged"] is False
    assert body["rates"]["version"] == "psx-costs-2026-10-11.2"
    assert body["prices_as_of"] == "2026-10-07"


def test_ffc_projection_equals_the_hand_calculation(client, investor, worked_example):
    ffc = next(h for h in _generate(client, investor).json()["holdings"] if h["ticker"] == "FFC")

    assert ffc["break_even_price"] == "541.48"
    assert ffc["round_trip_pct"] == "0.36"
    exit_ = ffc["forecast_exit"]
    assert (exit_["price"], exit_["gross"], exit_["charges"]["total"]) == (
        "539.94",
        "12418.62",
        "22.52",
    )
    assert (exit_["proceeds"], exit_["gain"], exit_["cgt"], exit_["net_return"]) == (
        "12396.10",
        "-35.13",
        "0",
        "-35.13",
    )
    dividends = ffc["dividends"]
    assert (dividends["per_share"], dividends["gross"], dividends["wht"], dividends["net"]) == (
        "41.00",
        "943.00",
        "141.45",
        "801.55",
    )
    assert len(dividends["payments"]) == 4
    assert D(ffc["why"]["tilt_effect_pp"]) == D("0.30")


def test_non_filer_changes_only_dividend_tax(client, investor, worked_example):
    filer = _generate(client, investor).json()
    non_filer = _generate(client, investor, filer_status="non_filer").json()

    assert non_filer["totals"] == filer["totals"]
    ffc = next(h for h in non_filer["holdings"] if h["ticker"] == "FFC")
    assert (ffc["dividends"]["wht"], ffc["dividends"]["net"]) == ("282.90", "660.10")
    assert ffc["forecast_exit"]["cgt"] == "0"
    assert non_filer["rates"]["cgt_non_filer_label"].startswith("Non-filer: NCCPL deducts 15%")


def test_current_returns_the_active_portfolio(client, investor, worked_example):
    assert client.get("/portfolio/current", headers=investor).status_code == 404
    created = _generate(client, investor).json()
    current = client.get("/portfolio/current", headers=investor).json()
    assert current["id"] == created["id"]
    assert current["holdings"] == created["holdings"]


def test_generating_again_archives_the_old_portfolio(client, db, investor, worked_example):
    first = _generate(client, investor).json()
    second = _generate(client, investor).json()
    statuses = {str(p.id): p.status for p in db.query(Portfolio).all()}
    assert statuses[first["id"]] == "archived"
    assert statuses[second["id"]] == "active"


def test_exclude_stock_regenerates_without_it(client, investor, worked_example):
    first = _generate(client, investor).json()
    response = client.patch(
        f"/portfolio/{first['id']}/exclude-stock", json={"ticker": "hbl"}, headers=investor
    )
    assert response.status_code == 200, response.text
    second = response.json()

    assert second["id"] != first["id"]
    assert second["excluded_tickers"] == ["HBL"]
    assert "HBL" not in [h["ticker"] for h in second["holdings"]]
    # The ninth-ranked stock takes its place
    assert "SYS" in [h["ticker"] for h in second["holdings"]]

    again = client.patch(
        f"/portfolio/{first['id']}/exclude-stock", json={"ticker": "MARI"}, headers=investor
    )
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "portfolio_archived"


def test_exclude_a_stock_that_is_not_held(client, investor, worked_example):
    portfolio = _generate(client, investor).json()
    response = client.patch(
        f"/portfolio/{portfolio['id']}/exclude-stock", json={"ticker": "NBP"}, headers=investor
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "ticker_not_in_portfolio"


def test_shariah_filter_uses_the_psx_review(client, investor, worked_example):
    body = _generate(client, investor, shariah_only=True).json()
    tickers = {h["ticker"] for h in body["holdings"]}
    assert not tickers & {"HBL", "UBL", "NBP"}
    assert body["shariah_list_version"] == "PSX/N-610, effective 2026-05-25"


def test_low_capital_explains_the_minimum(client, investor, worked_example):
    response = _generate(client, investor, capital="500")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["code"] == "capital_below_minimum"
    assert detail["min_holdings"] == 5
    assert D(detail["minimum_capital"]) > D("500")
    assert D(detail["minimum_capital"]) % 500 == 0

    retry = _generate(client, investor, capital=detail["minimum_capital"])
    assert retry.status_code == 201


def test_too_few_stocks_after_filters(client, investor, worked_example):
    # Four stocks left; Moderate needs at least five
    keep = {"MARI", "OGDC", "FFC", "EFERT"}
    excluded = [t for t in worked_example if t not in keep]
    response = _generate(client, investor, excluded_tickers=excluded)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "too_few_eligible_stocks"


def test_commission_override_is_validated(client, investor, worked_example):
    assert _generate(client, investor, commission_pct="0.10").status_code == 422
    assert _generate(client, investor, commission_pct="3").status_code == 422
    body = _generate(client, investor, commission_pct="0.25").json()
    assert body["commission_pct"] == "0.250"
    ffc = next(h for h in body["holdings"] if h["ticker"] == "FFC")
    assert ffc["charges"]["commission"] != "18.61"


def test_roll_check_reports_too_early_on_day_one(client, investor, worked_example):
    portfolio = _generate(client, investor).json()
    response = client.post(f"/portfolio/{portfolio['id']}/roll-check", headers=investor)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["required_trading_days"] == 20
    assert body["benchmark"]["kind"] == "equal_weight_forecast_stocks"
    assert {h["status"] for h in body["holdings"]} == {"too_early"}


def test_portfolio_endpoints_need_a_risk_profile(client, worked_example):
    headers = register_and_login(client)
    response = _generate(client, headers)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "risk_profile_required"
    assert client.get("/portfolio/current", headers=headers).status_code == 409


def test_portfolio_endpoints_need_a_login(client):
    assert client.post("/portfolio/generate", json={}).status_code == 401
    assert client.get("/portfolio/current").status_code == 401


def test_another_users_portfolio_is_not_found(client, db, investor, worked_example):
    portfolio = _generate(client, investor).json()
    other = register_and_login(client)
    _with_profile(db, other, client)
    response = client.post(f"/portfolio/{portfolio['id']}/roll-check", headers=other)
    assert response.status_code == 404
