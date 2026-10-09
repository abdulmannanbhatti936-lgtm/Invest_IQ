"""lowercase user emails + case-insensitive unique index

Emails are matched case-insensitively (schemas.user.normalize_email). Existing rows are
trimmed and lowercased, and a unique index on lower(email) makes the database reject
two addresses that differ only by letter case.

Refuses to run if two existing accounts would collide after lowercasing: which one to
keep is a human decision, never made silently by a migration.

Revision ID: 9428fccc1482
Revises: f7a2c4e81b90
Create Date: 2026-10-09 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9428fccc1482"
down_revision: Union[str, Sequence[str], None] = "f7a2c4e81b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    clashes = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT lower(btrim(email)) AS email, count(*) AS n FROM users "
                "GROUP BY lower(btrim(email)) HAVING count(*) > 1 ORDER BY 1"
            )
        )
        .fetchall()
    )
    if clashes:
        listing = ", ".join(f"{row.email} ({row.n} accounts)" for row in clashes)
        raise RuntimeError(
            f"{len(clashes)} email(s) exist in more than one letter case: {listing}. "
            "Merge or delete the duplicates by hand, then run the upgrade again."
        )

    op.execute("UPDATE users SET email = lower(btrim(email)) WHERE email <> lower(btrim(email))")
    op.create_index("ix_users_email_lower", "users", [sa.text("lower(email)")], unique=True)


def downgrade() -> None:
    # The original letter case was not kept, so emails stay lowercase after a downgrade.
    op.drop_index("ix_users_email_lower", table_name="users")
