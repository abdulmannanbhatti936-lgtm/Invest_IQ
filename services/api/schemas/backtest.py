"""
Backtest API shapes (PRD.md FR29-FR32). Money is a decimal string in rupees; returns, drawdown
and win rate are decimal-string fractions (0.235491 = +23.5491%). Clients only format them.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from schemas.types import UTCDateTime
from services.backtest_service import MIN_YEARS
from services.cost_engine import FilerStatus

Money = str
Ratio = str
MAX_YEARS = 10


class CustomHolding(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)
    weight_pct: Decimal = Field(gt=0, le=100, max_digits=5, decimal_places=2)


class CustomMix(BaseModel):
    """The user's own mix (FR29 "or custom"); run once and stored as a result, not a portfolio."""

    capital: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    filer_status: FilerStatus
    holdings: list[CustomHolding] = Field(min_length=1, max_length=100)


class RunBacktestRequest(BaseModel):
    years: int = Field(default=MIN_YEARS, ge=MIN_YEARS, le=MAX_YEARS)
    portfolio_id: uuid.UUID | None = None
    custom: CustomMix | None = None

    @model_validator(mode="after")
    def _one_source(self):
        if (self.portfolio_id is None) == (self.custom is None):
            raise ValueError("Give either portfolio_id or custom, not both")
        return self


class Metrics(BaseModel):
    total_return: Ratio
    total_return_before_sale: Ratio
    annualised_return: Ratio
    sharpe_ratio: Ratio | None
    max_drawdown: Ratio
    drawdown_peak_date: datetime.date | None
    drawdown_trough_date: datetime.date | None
    win_rate: Ratio | None
    months_won: int
    months_total: int


class Costs(BaseModel):
    buy_charges: Money
    dividends_gross: Money
    wht: Money
    sell_charges: Money
    cgt: Money
    idle_cash: Money
    end_value_before_sale: Money
    end_value_net: Money


class HoldingResult(BaseModel):
    ticker: str
    name: str
    weight_pct: str | None
    buy_date: datetime.date
    shares_bought: int
    buy_price: Money
    buy_cost: Money
    dividends_net: Money
    dividend_payments: int
    sell_date: datetime.date
    shares_sold: int
    sell_price: Money
    sell_charges: Money
    cgt: Money
    sale_net: Money
    carried_forward_days: int


class StrategyResult(BaseModel):
    metrics: Metrics
    costs: Costs
    holdings: list[HoldingResult]


class StartDateRules(BaseModel):
    # not_applicable: a custom mix has no risk rules; not_possible: see reason
    status: Literal["available", "not_applicable", "not_possible"]
    reason: Literal["too_few_stocks_with_history", "capital_too_low"] | None = None
    risk_category: str | None = None
    metrics: Metrics | None = None
    costs: Costs | None = None
    holdings: list[HoldingResult] | None = None


class StandInBenchmark(BaseModel):
    kind: Literal["forecast_stocks_equal_weight"]
    tickers: list[str]
    metrics: Metrics


class Kse100(BaseModel):
    status: Literal["available", "awaiting_permission", "not_covering_period"]
    dataset_version: str | None = None
    metrics: Metrics | None = None


class RiskFree(BaseModel):
    source: str
    source_url: str
    version: str
    basis: str
    yield_at_start: Ratio
    auctions_in_period: int
    lowest_yield: Ratio | None
    highest_yield: Ratio | None


class Period(BaseModel):
    years: int
    start: datetime.date
    end: datetime.date
    trading_days: int


class InputHolding(BaseModel):
    ticker: str
    name: str
    weight_pct: str


class Inputs(BaseModel):
    capital: Money
    filer_status: FilerStatus
    commission_pct: str
    holdings: list[InputHolding]


class Assumptions(BaseModel):
    rates_version: str
    price_adjustment: str
    dividends_source: Literal["yahoo"]
    dividends_checked: bool
    prices_as_of: datetime.date
    method_version: str
    carried_forward_days: int


class SeriesPoint(BaseModel):
    date: datetime.date
    portfolio: Money
    start_date_rules: Money | None
    benchmark: Money  # the stand-in, in rupees from the same capital
    kse100: Money | None


class BacktestResponse(BaseModel):
    id: uuid.UUID
    kind: Literal["portfolio", "custom"]
    portfolio_id: uuid.UUID | None
    created_at: UTCDateTime
    period: Period
    inputs: Inputs
    portfolio: StrategyResult
    start_date_rules: StartDateRules
    benchmark: StandInBenchmark
    kse100: Kse100
    risk_free: RiskFree
    assumptions: Assumptions
    series: list[SeriesPoint]


class UniverseStock(BaseModel):
    ticker: str
    name: str
    sector: str
    first_date: datetime.date
    max_years: int


class LeftOutStock(BaseModel):
    ticker: str
    reason: Literal["split_not_supported"]


class UniverseResponse(BaseModel):
    latest_date: datetime.date | None  # None until prices have been loaded
    min_years: int
    max_years: int | None
    stocks: list[UniverseStock]
    left_out: list[LeftOutStock]
