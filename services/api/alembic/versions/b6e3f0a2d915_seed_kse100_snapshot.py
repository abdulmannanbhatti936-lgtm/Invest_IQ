"""seed the KSE-100 snapshot (2026-10-10); stocks.shares_outstanding

- stocks.shares_outstanding: refreshed from the data provider; market cap is the latest
  stored close x shares (Yahoo's own market cap and P/E for PSX symbols are unreliable).
- The stock universe becomes the 95 KSE-100 constituents with 3+ years of Yahoo history
  (integrations/data/kse100_snapshot_2026-10-10.csv). Names and sectors follow PSX.
- Stocks outside the snapshot are deleted with their price points, predictions and news
  (ON DELETE CASCADE): the 4 earlier catalog tickers that are not KSE-100 constituents and
  the non-PSX rows AAPL and LOWCONF. Approved 2026-10-10 (Memory.md §4).

Downgrade restores the previous 50-company catalog (revision f7a2c4e81b90). Rows deleted on
upgrade are not restored; their price history can be fetched again by the refresh job.

Revision ID: b6e3f0a2d915
Revises: 5b8e2d41c7a3
Create Date: 2026-10-10 12:00:00.000000

"""

import csv
import importlib.util
import uuid
from pathlib import Path
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6e3f0a2d915"
down_revision: Union[str, Sequence[str], None] = "5b8e2d41c7a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# A versioned file, never edited after release, so this migration's behaviour is fixed
SNAPSHOT = (
    Path(__file__).resolve().parents[2] / "integrations" / "data" / "kse100_snapshot_2026-10-10.csv"
)

stocks = sa.table(
    "stocks",
    sa.column("id", sa.UUID()),
    sa.column("ticker", sa.String()),
    sa.column("name", sa.String()),
    sa.column("sector", sa.String()),
)


def _snapshot() -> list[tuple[str, str, str]]:
    with SNAPSHOT.open(newline="", encoding="utf-8") as f:
        return [
            (r["ticker"], r["name"], r["sector"])
            for r in csv.DictReader(f)
            if r["included"] == "true"
        ]


def _previous_catalog() -> list[tuple[str, str, str]]:
    path = Path(__file__).with_name("f7a2c4e81b90_align_schema_with_architecture.py")
    spec = importlib.util.spec_from_file_location("previous_catalog", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.PSX_SEED


def _replace_catalog(companies: list[tuple[str, str, str]]) -> None:
    op.execute(stocks.delete().where(stocks.c.ticker.notin_([t for t, _, _ in companies])))
    insert = postgresql.insert(stocks).values(
        [{"id": uuid.uuid4(), "ticker": t, "name": n, "sector": s} for t, n, s in companies]
    )
    op.execute(
        insert.on_conflict_do_update(
            index_elements=["ticker"],
            set_={"name": insert.excluded.name, "sector": insert.excluded.sector},
        )
    )


def upgrade() -> None:
    op.add_column("stocks", sa.Column("shares_outstanding", sa.BigInteger(), nullable=True))
    _replace_catalog(_snapshot())


def downgrade() -> None:
    _replace_catalog(_previous_catalog())
    op.drop_column("stocks", "shares_outstanding")
