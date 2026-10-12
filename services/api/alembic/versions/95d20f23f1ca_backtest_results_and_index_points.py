"""backtest_results and index_points (Phase 6)

Two new tables, nothing existing is changed. A backtest result stores its inputs, the data
versions it ran on, the headline metrics as NUMERIC and the variant, benchmarks and daily series
as JSONB. index_points holds daily index closes from a versioned file (KSE-100 once PSX grants
permission); a new version is added beside the old one.

Revision ID: 95d20f23f1ca
Revises: 259b1d19deaa
Create Date: 2026-10-12 23:36:00.030093

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '95d20f23f1ca'
down_revision: Union[str, Sequence[str], None] = '259b1d19deaa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('index_points',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('index_code', sa.String(), nullable=False),
    sa.Column('dataset_version', sa.String(), nullable=False),
    sa.Column('trade_date', sa.Date(), nullable=False),
    sa.Column('close', sa.Numeric(precision=14, scale=4), nullable=False),
    sa.Column('source', sa.String(), nullable=False),
    sa.Column('loaded_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('index_code', 'dataset_version', 'trade_date', name='uq_index_points_version_date')
    )
    op.create_index(op.f('ix_index_points_index_code'), 'index_points', ['index_code'], unique=False)
    op.create_table('backtest_results',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('portfolio_id', sa.UUID(), nullable=True),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('years', sa.Integer(), nullable=False),
    sa.Column('period_start', sa.Date(), nullable=False),
    sa.Column('period_end', sa.Date(), nullable=False),
    sa.Column('trading_days', sa.Integer(), nullable=False),
    sa.Column('carried_forward_days', sa.Integer(), nullable=False),
    sa.Column('capital', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('filer_status', sa.String(), nullable=False),
    sa.Column('commission_rate', sa.Numeric(precision=6, scale=5), nullable=False),
    sa.Column('rates_version', sa.String(), nullable=False),
    sa.Column('risk_free_version', sa.String(), nullable=False),
    sa.Column('price_adjustment', sa.String(), nullable=False),
    sa.Column('dividends_source', sa.String(), nullable=False),
    sa.Column('prices_as_of', sa.Date(), nullable=False),
    sa.Column('method_version', sa.String(), nullable=False),
    sa.Column('inputs', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('buy_charges', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('dividends_gross', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('wht', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('sell_charges', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('cgt', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('idle_cash', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('end_value_before_sale', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('end_value_net', sa.Numeric(precision=16, scale=2), nullable=False),
    sa.Column('total_return', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('total_return_before_sale', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('annualised_return', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('sharpe_ratio', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('max_drawdown', sa.Numeric(precision=12, scale=6), nullable=False),
    sa.Column('drawdown_peak_date', sa.Date(), nullable=True),
    sa.Column('drawdown_trough_date', sa.Date(), nullable=True),
    sa.Column('win_rate', sa.Numeric(precision=12, scale=6), nullable=True),
    sa.Column('months_won', sa.Integer(), nullable=False),
    sa.Column('months_total', sa.Integer(), nullable=False),
    sa.Column('holdings', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('start_date_rules', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('benchmark', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('kse100', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('risk_free', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('series', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("(kind = 'portfolio') = (portfolio_id IS NOT NULL)", name='ck_backtest_results_portfolio_kind'),
    sa.CheckConstraint("filer_status IN ('filer', 'non_filer')", name='ck_backtest_results_filer_status'),
    sa.CheckConstraint("kind IN ('portfolio', 'custom')", name='ck_backtest_results_kind'),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_backtest_results_portfolio_id'), 'backtest_results', ['portfolio_id'], unique=False)
    op.create_index(op.f('ix_backtest_results_user_id'), 'backtest_results', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_backtest_results_user_id'), table_name='backtest_results')
    op.drop_index(op.f('ix_backtest_results_portfolio_id'), table_name='backtest_results')
    op.drop_table('backtest_results')
    op.drop_index(op.f('ix_index_points_index_code'), table_name='index_points')
    op.drop_table('index_points')
