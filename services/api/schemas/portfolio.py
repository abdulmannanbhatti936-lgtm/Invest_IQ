"""
Portfolio API shapes (PRD.md FR23-FR28). Money and percentages are decimal strings so no
client ever rounds a rupee figure; clients only format them for display.
"""

import datetime
import uuid
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from schemas.types import UTCDateTime
from services.cost_engine import FilerStatus

Money = str
Percent = str


class GeneratePortfolioRequest(BaseModel):
    capital: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    filer_status: FilerStatus
    shariah_only: bool = False
    excluded_tickers: list[str] = Field(default_factory=list, max_length=100)
    # The user's own broker commission in percent, e.g. 0.20; default is the PSX floor
    commission_pct: Decimal | None = Field(default=None, max_digits=6, decimal_places=3)

    @field_validator("excluded_tickers")
    @classmethod
    def _normalise(cls, tickers: list[str]) -> list[str]:
        return sorted({t.strip().upper() for t in tickers if t.strip()})


class ExcludeStockRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=20)


class Charges(BaseModel):
    commission: Money
    sales_tax: Money
    cdc_fee: Money
    psx_trading_fee: Money
    psx_regulatory_fee: Money
    secp_levy: Money
    nccpl_trade_fee: Money
    nccpl_secp_fee: Money
    total: Money


class ForecastExit(BaseModel):
    price: Money
    gross: Money
    charges: Charges
    proceeds: Money
    gain: Money
    cgt: Money
    net_proceeds: Money
    net_return: Money
    net_return_pct: Percent


class DividendPayment(BaseModel):
    ex_date: datetime.date
    amount: Money


class Dividends(BaseModel):
    per_share: Money
    payments: list[DividendPayment]
    period_start: datetime.date
    period_end: datetime.date
    gross: Money
    wht: Money
    net: Money
    source: Literal["yahoo"]


class WhyThisStock(BaseModel):
    rank: int
    volatility_pct: Percent
    forecast_price: Money
    last_close: Money
    expected_change_pct: Percent
    confidence_score: str
    low_confidence_reasons: list[str]
    signal: str
    signal_probability: str | None
    sentiment_label: str | None
    sentiment_score: str | None
    counted_headlines: int
    tilt_effect_pp: str  # how far the forecast and news moved this weight


class Holding(BaseModel):
    ticker: str
    name: str
    sector: str | None
    shares: int
    price: Money
    target_weight_pct: Percent
    allocation_pct: Percent
    gross: Money
    charges: Charges
    total_cost: Money
    break_even_price: Money
    break_even_change_pct: Percent
    round_trip_pct: Percent
    forecast_exit: ForecastExit
    dividends: Dividends | None
    why: WhyThisStock


class RatesInfo(BaseModel):
    version: str
    checked_on: str
    unverified: list[str]
    not_modelled: list[str]
    cgt_non_filer_label: str
    commission_floor_pct: Percent
    commission_max_pct: Percent


class Totals(BaseModel):
    gross: Money
    charges: Money
    cost: Money
    idle_cash: Money


class IdleCash(BaseModel):
    amount: Money
    flagged: bool  # FR24: cash that could buy more shares but a limit stopped it
    blocked_by: dict[str, Literal["stock_cap", "sector_cap"]]


class PortfolioResponse(BaseModel):
    id: uuid.UUID
    status: Literal["active", "archived"]
    generated_at: UTCDateTime
    risk_category: Literal["conservative", "moderate", "aggressive"]
    capital: Money
    filer_status: FilerStatus
    shariah_only: bool
    shariah_list_version: str | None
    excluded_tickers: list[str]
    commission_pct: Percent
    model_version: str
    prices_as_of: datetime.date
    rates: RatesInfo
    totals: Totals
    idle: IdleCash
    holdings: list[Holding]


class RollReplacement(BaseModel):
    ticker: str
    price: Money
    expected_change_pct: Percent


class RollSale(BaseModel):
    gross: Money
    charges_total: Money
    cgt: Money
    net_proceeds: Money


class RollPurchase(BaseModel):
    shares: int
    gross: Money
    charges_total: Money


class RollHolding(BaseModel):
    ticker: str
    status: Literal[
        "too_early", "not_triggered", "no_replacement", "costs_exceed_benefit", "suggested"
    ]
    trading_days: int
    holding_return_pct: Percent
    benchmark_return_pct: Percent
    relative_return_pct: Percent
    threshold_pct: Percent
    weak_forecast: bool
    replacement: RollReplacement | None
    sale: RollSale | None
    purchase: RollPurchase | None
    switch_cost: Money | None
    expected_benefit: Money | None


class Benchmark(BaseModel):
    kind: Literal["equal_weight_forecast_stocks"]
    stock_count: int
    since: datetime.date
    return_pct: Percent | None


class RollCheckResponse(BaseModel):
    portfolio_id: uuid.UUID
    checked_at: UTCDateTime
    required_trading_days: int
    benchmark: Benchmark
    holdings: list[RollHolding]
