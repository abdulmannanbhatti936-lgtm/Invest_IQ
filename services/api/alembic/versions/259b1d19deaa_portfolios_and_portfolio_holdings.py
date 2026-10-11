"""portfolios and portfolio_holdings (Phase 5)

Two new tables, nothing existing is changed. A portfolio stores its inputs, the rates and
model versions and the per-stock calculation; money is NUMERIC(16, 2), weights NUMERIC(7, 4).
A partial unique index keeps at most one active portfolio per user.

Revision ID: 259b1d19deaa
Revises: f3c8a2d6b417
Create Date: 2026-10-11 23:05:24.493371

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '259b1d19deaa'
down_revision: Union[str, Sequence[str], None] = 'f3c8a2d6b417'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('portfolios',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('risk_category', sa.String(), nullable=False),
    sa.Column('capital', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('filer_status', sa.String(), nullable=False),
    sa.Column('shariah_only', sa.Boolean(), nullable=False),
    sa.Column('excluded_tickers', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('commission_rate', sa.Numeric(precision=6, scale=5), nullable=False),
    sa.Column('rates_version', sa.String(), nullable=False),
    sa.Column('model_version', sa.String(), nullable=False),
    sa.Column('prices_as_of', sa.Date(), nullable=False),
    sa.Column('shariah_list_version', sa.String(), nullable=True),
    sa.Column('input_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('gross_total', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('charges_total', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('cost_total', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('idle_cash', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.CheckConstraint("filer_status IN ('filer', 'non_filer')", name='ck_portfolios_filer_status'),
    sa.CheckConstraint("risk_category IN ('conservative', 'moderate', 'aggressive')", name='ck_portfolios_risk_category'),
    sa.CheckConstraint("status IN ('active', 'archived')", name='ck_portfolios_status'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolios_user_id'), 'portfolios', ['user_id'], unique=False)
    op.create_index('uq_portfolios_one_active_per_user', 'portfolios', ['user_id'], unique=True, postgresql_where=sa.text("status = 'active'"))
    op.create_table('portfolio_holdings',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('portfolio_id', sa.UUID(), nullable=False),
    sa.Column('stock_id', sa.UUID(), nullable=False),
    sa.Column('prediction_id', sa.UUID(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.Column('reference_price', sa.Numeric(precision=14, scale=2), nullable=False),
    sa.Column('target_weight', sa.Numeric(precision=7, scale=4), nullable=False),
    sa.Column('allocation_pct', sa.Numeric(precision=7, scale=4), nullable=False),
    sa.Column('gross_value', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('commission', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('sales_tax', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('cdc_fee', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('psx_trading_fee', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('psx_regulatory_fee', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('secp_levy', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('nccpl_trade_fee', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('nccpl_secp_fee', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('buy_charges', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('total_cost', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('projection', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['prediction_id'], ['predictions.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['stock_id'], ['stocks.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_portfolio_holdings_portfolio_id'), 'portfolio_holdings', ['portfolio_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_portfolio_holdings_portfolio_id'), table_name='portfolio_holdings')
    op.drop_table('portfolio_holdings')
    op.drop_index('uq_portfolios_one_active_per_user', table_name='portfolios', postgresql_where=sa.text("status = 'active'"))
    op.drop_index(op.f('ix_portfolios_user_id'), table_name='portfolios')
    op.drop_table('portfolios')
