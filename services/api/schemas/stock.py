import datetime

from pydantic import BaseModel, ConfigDict


class StockSummary(BaseModel):
    ticker: str
    name: str
    sector: str | None = None

    model_config = ConfigDict(from_attributes=True)


class StockSearchResponse(BaseModel):
    results: list[StockSummary]


class StockQuote(BaseModel):
    ticker: str
    name: str
    sector: str | None = None
    currency: str = "PKR"
    price: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    volume: int
    timestamp: datetime.datetime
    # Key statistics (PRD.md FR8)
    fifty_two_week_high: float | None = None
    fifty_two_week_low: float | None = None
    market_cap: float | None = None
    pe_ratio: float | None = None


class PricePointResponse(BaseModel):
    timestamp: datetime.datetime
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float
    volume: int
