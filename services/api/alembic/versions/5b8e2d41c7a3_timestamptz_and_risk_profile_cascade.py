"""naive timestamps -> TIMESTAMPTZ; risk_profiles.user_id ON DELETE CASCADE

The four columns below were written with datetime.utcnow(), so every existing value is a
UTC wall-clock time. `AT TIME ZONE 'UTC'` converts them as UTC whatever the session
TimeZone is (and converts back the same way on downgrade).

Revision ID: 5b8e2d41c7a3
Revises: 081c356f48e6
Create Date: 2026-10-09 16:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b8e2d41c7a3"
down_revision: Union[str, Sequence[str], None] = "081c356f48e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = [
    ("users", "created_at", False),
    ("risk_profiles", "updated_at", False),
    ("predictions", "generated_at", False),
    ("news_sentiments", "timestamp", True),
]

FK_NAME = "risk_profiles_user_id_fkey"


def upgrade() -> None:
    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(timezone=True),
            existing_type=sa.DateTime(),
            existing_nullable=nullable,
            postgresql_using=f"\"{column}\" AT TIME ZONE 'UTC'",
        )

    op.drop_constraint(FK_NAME, "risk_profiles", type_="foreignkey")
    op.create_foreign_key(
        FK_NAME, "risk_profiles", "users", ["user_id"], ["id"], ondelete="CASCADE"
    )


def downgrade() -> None:
    op.drop_constraint(FK_NAME, "risk_profiles", type_="foreignkey")
    op.create_foreign_key(FK_NAME, "risk_profiles", "users", ["user_id"], ["id"])

    for table, column, nullable in COLUMNS:
        op.alter_column(
            table,
            column,
            type_=sa.DateTime(),
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=nullable,
            postgresql_using=f"\"{column}\" AT TIME ZONE 'UTC'",
        )
