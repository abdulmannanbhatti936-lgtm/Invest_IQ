"""stock_dividends: provider dividend events and the div-v1 adjustment decision

The training/inference series is dividend-adjusted backwards (services/dividend_adjustment.py);
served prices are not. Each row keeps the provider's amount and, once assessed, the closes
around the ex-date, the factor applied (or none) and a review flag.

Additive only: no existing data is changed.

Revision ID: a4c9e1f7b302
Revises: d2a7c5e8f041
Create Date: 2026-10-10 20:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c9e1f7b302"
down_revision: Union[str, Sequence[str], None] = "d2a7c5e8f041"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_dividends",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("ex_date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="yahoo"),
        sa.Column("previous_close", sa.Numeric(), nullable=True),
        sa.Column("ex_close", sa.Numeric(), nullable=True),
        sa.Column("adjustment_factor", sa.Numeric(), nullable=True),
        sa.Column("review_flag", sa.String(), nullable=True),
        sa.Column("method_version", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "ex_date", name="uq_stock_dividends_stock_date"),
    )
    op.create_index("ix_stock_dividends_stock_id", "stock_dividends", ["stock_id"])


def downgrade() -> None:
    op.drop_index("ix_stock_dividends_stock_id", table_name="stock_dividends")
    op.drop_table("stock_dividends")
