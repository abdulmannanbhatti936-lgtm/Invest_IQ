"""predictions: sentiment_status

'used' when the forecast read the news inputs, 'unavailable' when the news sources were
stale and the price-only fallback model made it (PRD.md FR22), NULL for a price-only model.

Additive only: existing rows keep NULL.

Revision ID: f3c8a2d6b417
Revises: e4b1d7a90c26
Create Date: 2026-10-11 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3c8a2d6b417"
down_revision: Union[str, Sequence[str], None] = "e4b1d7a90c26"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("predictions", sa.Column("sentiment_status", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("predictions", "sentiment_status")
