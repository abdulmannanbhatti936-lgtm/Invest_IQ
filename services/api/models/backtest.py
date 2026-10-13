import datetime
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base
from models.portfolio import MONEY

RATIO = Numeric(12, 6)  # fractions, e.g. 0.235491 for +23.5491%


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class BacktestResult(Base):
    """
    One backtest (PRD.md FR29-FR32): a stored portfolio or the user's own mix, bought and held
    over past PSX prices. The headline (the portfolio as given) has its own columns; the
    "rules applied at the start date" variant, the benchmarks and the daily series are JSONB.
    Every input and data version is stored so a result can be explained later as it was run.
    """

    __tablename__ = "backtest_results"
    __table_args__ = (
        CheckConstraint("kind IN ('portfolio', 'custom')", name="ck_backtest_results_kind"),
        CheckConstraint(
            "filer_status IN ('filer', 'non_filer')", name="ck_backtest_results_filer_status"
        ),
        CheckConstraint(
            "(kind = 'portfolio') = (portfolio_id IS NOT NULL)",
            name="ck_backtest_results_portfolio_kind",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # A custom mix has no portfolio, so ownership is stored directly
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    portfolio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    kind = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Period
    years = Column(Integer, nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)
    trading_days = Column(Integer, nullable=False)
    carried_forward_days = Column(Integer, nullable=False)

    # Inputs and the data they were run on
    capital = Column(MONEY, nullable=False)
    filer_status = Column(String, nullable=False)
    commission_rate = Column(Numeric(6, 5), nullable=False)
    rates_version = Column(String, nullable=False)
    risk_free_version = Column(String, nullable=False)
    price_adjustment = Column(String, nullable=False)
    dividends_source = Column(String, nullable=False)
    prices_as_of = Column(Date, nullable=False)
    method_version = Column(String, nullable=False)
    inputs = Column(JSONB, nullable=False)

    # Headline: money
    buy_charges = Column(MONEY, nullable=False)
    dividends_gross = Column(MONEY, nullable=False)
    wht = Column(MONEY, nullable=False)
    sell_charges = Column(MONEY, nullable=False)
    cgt = Column(MONEY, nullable=False)
    idle_cash = Column(MONEY, nullable=False)
    end_value_before_sale = Column(MONEY, nullable=False)
    end_value_net = Column(MONEY, nullable=False)

    # Headline: ratios (Sharpe is NULL when the returns never vary)
    total_return = Column(RATIO, nullable=False)
    total_return_before_sale = Column(RATIO, nullable=False)
    annualised_return = Column(RATIO, nullable=False)
    sharpe_ratio = Column(RATIO, nullable=True)
    max_drawdown = Column(RATIO, nullable=False)
    drawdown_peak_date = Column(Date, nullable=True)
    drawdown_trough_date = Column(Date, nullable=True)
    win_rate = Column(RATIO, nullable=True)
    months_won = Column(Integer, nullable=False)
    months_total = Column(Integer, nullable=False)

    holdings = Column(JSONB, nullable=False)
    start_date_rules = Column(JSONB, nullable=False)
    benchmark = Column(JSONB, nullable=False)
    kse100 = Column(JSONB, nullable=False)
    risk_free = Column(JSONB, nullable=False)
    series = Column(JSONB, nullable=False)


class IndexPoint(Base):
    """
    A daily index close from a versioned, licensed file (services/index_data.py). Loading a
    new version adds rows beside the old ones; readers use the newest loaded version.
    """

    __tablename__ = "index_points"
    __table_args__ = (
        UniqueConstraint(
            "index_code", "dataset_version", "trade_date", name="uq_index_points_version_date"
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    index_code = Column(String, nullable=False, index=True)  # 'KSE100' / 'KSE100PR'
    dataset_version = Column(String, nullable=False)
    trade_date = Column(Date, nullable=False)
    close = Column(Numeric(14, 4), nullable=False)
    source = Column(String, nullable=False)
    loaded_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
