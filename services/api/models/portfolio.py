import datetime
import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from core.database import Base

MONEY = Numeric(16, 2)
WEIGHT = Numeric(7, 4)  # percent, e.g. 14.8025


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class Portfolio(Base):
    """
    One generated recommendation (PRD.md FR23-FR28). It is guidance only: nothing is bought.
    The inputs, rates version, model version and per-stock calculation are stored with it so
    any portfolio can be explained later exactly as it was generated.
    """

    __tablename__ = "portfolios"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'archived')", name="ck_portfolios_status"),
        CheckConstraint(
            "filer_status IN ('filer', 'non_filer')", name="ck_portfolios_filer_status"
        ),
        CheckConstraint(
            "risk_category IN ('conservative', 'moderate', 'aggressive')",
            name="ck_portfolios_risk_category",
        ),
        # At most one active portfolio per user; generating a new one archives the old one
        Index(
            "uq_portfolios_one_active_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String, nullable=False, default="active")
    generated_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    # Inputs
    risk_category = Column(String, nullable=False)
    capital = Column(MONEY, nullable=False)
    filer_status = Column(String, nullable=False)
    shariah_only = Column(Boolean, nullable=False, default=False)
    excluded_tickers = Column(JSONB, nullable=False, default=list)
    commission_rate = Column(Numeric(6, 5), nullable=False)

    # What it was built from
    rates_version = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    prices_as_of = Column(Date, nullable=False)
    shariah_list_version = Column(String, nullable=True)
    input_snapshot = Column(JSONB, nullable=False)

    # Totals (sums of the holdings' rounded lines)
    gross_total = Column(MONEY, nullable=False)
    charges_total = Column(MONEY, nullable=False)
    cost_total = Column(MONEY, nullable=False)
    idle_cash = Column(MONEY, nullable=False)

    holdings = relationship(
        "PortfolioHolding",
        back_populates="portfolio",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PortfolioHolding.position",
    )


class PortfolioHolding(Base):
    """One stock in a portfolio with its buy-side figures; projections are estimates."""

    __tablename__ = "portfolio_holdings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    portfolio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("portfolios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stock_id = Column(
        UUID(as_uuid=True), ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    # The exact forecast used, so "why this stock" shows what the generator saw
    prediction_id = Column(
        UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="SET NULL"), nullable=True
    )
    position = Column(Integer, nullable=False)

    shares = Column(Integer, nullable=False)
    reference_price = Column(Numeric(14, 2), nullable=False)
    target_weight = Column(WEIGHT, nullable=False)
    allocation_pct = Column(WEIGHT, nullable=False)

    gross_value = Column(MONEY, nullable=False)
    commission = Column(MONEY, nullable=False)
    sales_tax = Column(MONEY, nullable=False)
    cdc_fee = Column(MONEY, nullable=False)
    psx_trading_fee = Column(MONEY, nullable=False)
    psx_regulatory_fee = Column(MONEY, nullable=False)
    secp_levy = Column(MONEY, nullable=False)
    nccpl_trade_fee = Column(MONEY, nullable=False)
    nccpl_secp_fee = Column(MONEY, nullable=False)
    buy_charges = Column(MONEY, nullable=False)
    total_cost = Column(MONEY, nullable=False)

    # Break-even, forecast exit and dividend figures with their basis (estimates)
    projection = Column(JSONB, nullable=False)

    portfolio = relationship("Portfolio", back_populates="holdings")
    stock = relationship("Stock")
