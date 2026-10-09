"""predictions: signal_probability and as_of_date

confidence_score now holds the LSTM's calibrated direction probability; the Random Forest's
class probability moves to signal_probability. as_of_date is the trading date of the close
the forecast was made from. Existing rows keep NULL in both new columns.

Additive only: no existing data is changed.

Revision ID: c81f3d5a9e64
Revises: a4c9e1f7b302
Create Date: 2026-10-10 22:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c81f3d5a9e64"
down_revision: Union[str, Sequence[str], None] = "a4c9e1f7b302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("signal_probability", sa.Numeric(5, 4), nullable=True))
    op.add_column("predictions", sa.Column("as_of_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "as_of_date")
    op.drop_column("predictions", "signal_probability")
