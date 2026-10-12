import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, require_risk_profile
from models.risk_profile import RiskProfile
from models.user import User
from schemas.backtest import BacktestResponse, RunBacktestRequest, UniverseResponse
from services import backtest, backtest_service, cost_engine, portfolio_service
from services.backtest_service import RunInputs, UnknownStocks
from services.risk_free import RiskFreeUnavailable

router = APIRouter(prefix="/backtest", tags=["backtest"])

ERRORS = {
    404: {"description": "detail.code: 'portfolio_not_found' or 'backtest_not_found'"},
    409: {"description": "detail.code: 'risk_profile_required'"},
    422: {
        "description": (
            "detail.code: 'insufficient_history' (required_start, stocks with first_date), "
            "'weight_too_small' (tickers), 'weights_not_100' (total_pct), 'duplicate_stocks', "
            "'unknown_stock' (tickers) or 'split_not_supported' (ticker)"
        )
    },
    503: {"description": "detail.code: 'risk_free_unavailable'"},
}


def _error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def _custom_inputs(body: RunBacktestRequest) -> RunInputs:
    mix = body.custom
    tickers = [h.ticker.strip().upper() for h in mix.holdings]
    duplicates = sorted({t for t in tickers if tickers.count(t) > 1})
    if duplicates:
        raise _error(422, "duplicate_stocks", "A stock appears more than once.", tickers=duplicates)
    total = sum((h.weight_pct for h in mix.holdings), Decimal(0))
    if total != 100:
        raise _error(
            422, "weights_not_100", f"Weights total {total}%, not 100%.", total_pct=str(total)
        )
    return RunInputs(
        kind="custom",
        portfolio=None,
        weights={t: h.weight_pct / 100 for t, h in zip(tickers, mix.holdings, strict=True)},
        capital=mix.capital,
        filer_status=mix.filer_status,
        commission_rate=cost_engine.load_rates().commission_rate,
        years=body.years,
    )


@router.get("/universe", response_model=UniverseResponse, responses=ERRORS)
def universe(
    _: RiskProfile = Depends(require_risk_profile),
    db: Session = Depends(get_db),
):
    """Stocks a custom mix may use, each with how many whole years of history it has."""
    return backtest_service.universe(db)


@router.post("/run", response_model=BacktestResponse, status_code=201, responses=ERRORS)
def run(
    body: RunBacktestRequest,
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Buy and hold a stored portfolio (its target weights) or the user's own mix over the last
    `years` of PSX prices, with every charge, dividends and CGT, and compare it with the
    benchmarks (FR29-FR32). Past results; no order is placed.
    """
    if body.portfolio_id is not None:
        portfolio = portfolio_service.owned_portfolio(db, user, body.portfolio_id)
        if portfolio is None:
            raise _error(404, "portfolio_not_found", "Portfolio not found.")
        inputs = backtest_service.portfolio_inputs(portfolio, body.years)
    else:
        inputs = _custom_inputs(body)

    try:
        result = backtest_service.run(db, user, inputs)
    except UnknownStocks as exc:
        raise _error(422, "unknown_stock", "Unknown stock.", tickers=exc.tickers) from exc
    except backtest.UnsupportedSplit as exc:
        raise _error(
            422,
            "split_not_supported",
            f"{exc.ticker} had a split that leaves part of a share.",
            ticker=exc.ticker,
        ) from exc
    except backtest.InsufficientHistory as exc:
        raise _error(
            422,
            "insufficient_history",
            f"Not every stock has prices back to {exc.required_start}.",
            required_start=exc.required_start.isoformat(),
            stocks=[
                {"ticker": t, "first_date": None if d is None else d.isoformat()}
                for t, d in sorted(exc.first_dates.items())
            ],
        ) from exc
    except backtest.WeightTooSmall as exc:
        raise _error(
            422,
            "weight_too_small",
            "A weight is too small to buy one share at the start date's price.",
            tickers=exc.tickers,
        ) from exc
    except RiskFreeUnavailable as exc:
        raise _error(503, "risk_free_unavailable", "No T-bill rate for this period.") from exc
    return backtest_service.result_payload(result)


@router.get("/{result_id}", response_model=BacktestResponse, responses=ERRORS)
def get_result(
    result_id: uuid.UUID,
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = backtest_service.owned_result(db, user, result_id)
    if result is None:
        raise _error(404, "backtest_not_found", "Backtest not found.")
    return backtest_service.result_payload(result)
