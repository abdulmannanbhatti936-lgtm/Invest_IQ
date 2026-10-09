"""split adjustment: price_points factor/flag/version, stock_splits

- price_points keeps the provider's raw OHLCV untouched; split_factor is the divisor that
  turns it into the split-adjusted series (volume is multiplied), quality_flag marks a bar
  left out of the served series, adjustment_version names the method that set both.
- stock_splits records the provider's split events and, per split, whether InvestIQ
  adjusted the earlier history (services/split_adjustment.py).

Additive only: no existing data is changed.

Revision ID: d2a7c5e8f041
Revises: b6e3f0a2d915
Create Date: 2026-10-10 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d2a7c5e8f041"
down_revision: Union[str, Sequence[str], None] = "b6e3f0a2d915"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "price_points",
        sa.Column("split_factor", sa.Numeric(), nullable=False, server_default="1"),
    )
    op.add_column("price_points", sa.Column("quality_flag", sa.String(), nullable=True))
    op.add_column("price_points", sa.Column("adjustment_version", sa.String(), nullable=True))

    op.create_table(
        "stock_splits",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("split_date", sa.Date(), nullable=False),
        sa.Column("ratio", sa.Numeric(), nullable=False),
        sa.Column("history_adjusted", sa.Boolean(), nullable=True),
        sa.Column("decision_note", sa.String(), nullable=True),
        sa.Column("method_version", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "split_date", name="uq_stock_splits_stock_date"),
    )
    op.create_index("ix_stock_splits_stock_id", "stock_splits", ["stock_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_splits_stock_id", table_name="stock_splits")
    op.drop_table("stock_splits")
    op.drop_column("price_points", "adjustment_version")
    op.drop_column("price_points", "quality_flag")
    op.drop_column("price_points", "split_factor")
