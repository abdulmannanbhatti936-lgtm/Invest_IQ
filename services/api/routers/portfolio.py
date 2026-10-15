import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.database import get_db
from core.deps import get_current_user, require_risk_profile
from core.portfolio_rules import RISK_RULES
from models.risk_profile import RiskProfile
from models.user import User
from schemas.portfolio import (
    ExcludeStockRequest,
    GeneratePortfolioRequest,
    PortfolioResponse,
    RollCheckResponse,
)
from services import backtest_service, cost_engine, portfolio_service
from services.allocation import TooFewEligibleStocks
from services.portfolio_service import (
    CapitalBelowMinimum,
    PortfolioArchived,
    PortfolioInputs,
    PredictionsUnavailable,
    TickerNotInPortfolio,
)

router = APIRouter(prefix="/portfolio", tags=["portfolio"])

ERRORS = {
    409: {"description": "detail.code: 'risk_profile_required' or 'portfolio_archived'"},
    422: {
        "description": (
            "detail.code: 'capital_below_minimum' (with minimum_capital), "
            "'too_few_eligible_stocks', 'invalid_commission_rate' or 'ticker_not_in_portfolio'"
        )
    },
    503: {"description": "detail.code: 'predictions_unavailable'"},
}


def _error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message, **extra})


def _generate(db: Session, user: User, profile: RiskProfile, inputs: PortfolioInputs):
    try:
        return portfolio_service.generate_portfolio(db, user, profile, inputs)
    except CapitalBelowMinimum as exc:
        rules = RISK_RULES[exc.category]
        raise _error(
            422,
            "capital_below_minimum",
            f"Rs {exc.capital} cannot be spread across {rules.min_holdings} companies.",
            capital=str(exc.capital),
            minimum_capital=None if exc.minimum is None else str(exc.minimum),
            min_holdings=rules.min_holdings,
            max_stock_weight_pct=str(rules.max_stock_weight * 100),
            risk_category=exc.category,
            prices_as_of=exc.prices_as_of.isoformat(),
        ) from exc
    except TooFewEligibleStocks as exc:
        raise _error(
            422,
            "too_few_eligible_stocks",
            f"Only {exc.eligible} stocks are left after your filters; {exc.needed} are needed.",
            eligible=exc.eligible,
            needed=exc.needed,
        ) from exc
    except cost_engine.InvalidCommissionRate as exc:
        rates = portfolio_service.rates_payload(cost_engine.load_rates())
        raise _error(
            422,
            "invalid_commission_rate",
            str(exc),
            commission_floor_pct=rates["commission_floor_pct"],
            commission_max_pct=rates["commission_max_pct"],
        ) from exc
    except PredictionsUnavailable as exc:
        raise _error(503, "predictions_unavailable", "No current forecasts to use.") from exc


@router.post("/generate", response_model=PortfolioResponse, status_code=201, responses=ERRORS)
def generate(
    body: GeneratePortfolioRequest,
    profile: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Build a new recommended portfolio from the user's risk profile and the current forecasts
    and news, and archive the previous one. Guidance only: no order is placed.
    """
    inputs = PortfolioInputs(
        capital=body.capital,
        filer_status=body.filer_status,
        shariah_only=body.shariah_only,
        excluded_tickers=body.excluded_tickers,
        commission_rate=None if body.commission_pct is None else body.commission_pct / 100,
    )
    portfolio = _generate(db, user, profile, inputs)
    return portfolio_service.portfolio_payload(portfolio)


@router.get("/current", response_model=PortfolioResponse, responses=ERRORS)
def current(
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    portfolio = portfolio_service.active_portfolio(db, user)
    if portfolio is None:
        raise _error(404, "no_active_portfolio", "No portfolio has been generated yet.")
    return {
        **portfolio_service.portfolio_payload(portfolio),
        "latest_backtest": backtest_service.latest_summary(db, portfolio),
    }


def _owned(db: Session, user: User, portfolio_id: uuid.UUID):
    portfolio = portfolio_service.owned_portfolio(db, user, portfolio_id)
    if portfolio is None:
        raise _error(404, "portfolio_not_found", "Portfolio not found.")
    return portfolio


@router.post("/{portfolio_id}/roll-check", response_model=RollCheckResponse, responses=ERRORS)
def roll_check(
    portfolio_id: uuid.UUID,
    _: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check each holding against the rolling rule (FR25). Changes nothing."""
    portfolio = _owned(db, user, portfolio_id)
    try:
        return portfolio_service.roll_check(db, portfolio)
    except PortfolioArchived as exc:
        raise _error(409, "portfolio_archived", "This portfolio has been replaced.") from exc
    except PredictionsUnavailable as exc:
        raise _error(503, "predictions_unavailable", "No current forecasts to use.") from exc


@router.patch("/{portfolio_id}/exclude-stock", response_model=PortfolioResponse, responses=ERRORS)
def exclude_stock(
    portfolio_id: uuid.UUID,
    body: ExcludeStockRequest,
    profile: RiskProfile = Depends(require_risk_profile),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Leave one stock out (FR27): returns a new portfolio built from the same inputs with that
    stock excluded; the old one is archived.
    """
    portfolio = _owned(db, user, portfolio_id)
    ticker = body.ticker.strip().upper()
    try:
        inputs = portfolio_service.exclusion_inputs(portfolio, ticker)
    except PortfolioArchived as exc:
        raise _error(409, "portfolio_archived", "This portfolio has been replaced.") from exc
    except TickerNotInPortfolio as exc:
        raise _error(422, "ticker_not_in_portfolio", f"{ticker} is not in this portfolio.") from exc
    return portfolio_service.portfolio_payload(_generate(db, user, profile, inputs))
