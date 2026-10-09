"""align schema with Architecture.md section 7

- users: add role (user/admin) and onboarding_progress (FR6)
- predictions: UUID id, NUMERIC forecast_price/confidence_score, generated_at
- news_sentiments: sentiment_score nullable (NULL = not yet scored)
- price_points: unique (stock_id, timestamp) so refreshes can upsert
- stocks: seed the PSX company catalog for search/browse (FR9)

Revision ID: f7a2c4e81b90
Revises: e532cc911ac7
Create Date: 2026-10-08 23:30:00.000000

"""
import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7a2c4e81b90"
down_revision: Union[str, Sequence[str], None] = "e532cc911ac7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of the catalog at the time of this migration, so the migration
# never changes behaviour if integrations/psx_catalog.py is edited later.
PSX_SEED = [
    ("SYS", "Systems Limited", "Technology & Communication"),
    ("TRG", "TRG Pakistan Limited", "Technology & Communication"),
    ("NETSOL", "NetSol Technologies Limited", "Technology & Communication"),
    ("AIRLINK", "Air Link Communication Limited", "Technology & Communication"),
    ("PTC", "Pakistan Telecommunication Company Limited", "Technology & Communication"),
    ("HUBC", "The Hub Power Company Limited", "Power Generation & Distribution"),
    ("KEL", "K-Electric Limited", "Power Generation & Distribution"),
    ("KAPCO", "Kot Addu Power Company Limited", "Power Generation & Distribution"),
    ("OGDC", "Oil & Gas Development Company Limited", "Oil & Gas Exploration"),
    ("PPL", "Pakistan Petroleum Limited", "Oil & Gas Exploration"),
    ("MARI", "Mari Energies Limited", "Oil & Gas Exploration"),
    ("POL", "Pakistan Oilfields Limited", "Oil & Gas Exploration"),
    ("PSO", "Pakistan State Oil Company Limited", "Oil & Gas Marketing"),
    ("SNGP", "Sui Northern Gas Pipelines Limited", "Oil & Gas Marketing"),
    ("SSGC", "Sui Southern Gas Company Limited", "Oil & Gas Marketing"),
    ("ATRL", "Attock Refinery Limited", "Refinery"),
    ("NRL", "National Refinery Limited", "Refinery"),
    ("MCB", "MCB Bank Limited", "Commercial Banks"),
    ("UBL", "United Bank Limited", "Commercial Banks"),
    ("HBL", "Habib Bank Limited", "Commercial Banks"),
    ("MEBL", "Meezan Bank Limited", "Commercial Banks"),
    ("BAHL", "Bank AL Habib Limited", "Commercial Banks"),
    ("BAFL", "Bank Alfalah Limited", "Commercial Banks"),
    ("NBP", "National Bank of Pakistan", "Commercial Banks"),
    ("ABL", "Allied Bank Limited", "Commercial Banks"),
    ("FABL", "Faysal Bank Limited", "Commercial Banks"),
    ("AKBL", "Askari Bank Limited", "Commercial Banks"),
    ("EFERT", "Engro Fertilizers Limited", "Fertilizer"),
    ("FFC", "Fauji Fertilizer Company Limited", "Fertilizer"),
    ("LUCK", "Lucky Cement Limited", "Cement"),
    ("DGKC", "D.G. Khan Cement Company Limited", "Cement"),
    ("MLCF", "Maple Leaf Cement Factory Limited", "Cement"),
    ("FCCL", "Fauji Cement Company Limited", "Cement"),
    ("CHCC", "Cherat Cement Company Limited", "Cement"),
    ("KOHC", "Kohat Cement Company Limited", "Cement"),
    ("PIOC", "Pioneer Cement Limited", "Cement"),
    ("NML", "Nishat Mills Limited", "Textile Composite"),
    ("ILP", "Interloop Limited", "Textile Composite"),
    ("SEARL", "The Searle Company Limited", "Pharmaceuticals"),
    ("MTL", "Millat Tractors Limited", "Automobile Assembler"),
    ("INDU", "Indus Motor Company Limited", "Automobile Assembler"),
    ("HCAR", "Honda Atlas Cars (Pakistan) Limited", "Automobile Assembler"),
    ("SAZEW", "Sazgar Engineering Works Limited", "Automobile Assembler"),
    ("PAEL", "Pak Elektron Limited", "Cable & Electrical Goods"),
    ("EPCL", "Engro Polymer & Chemicals Limited", "Chemical"),
    ("LOTCHEM", "Lotte Chemical Pakistan Limited", "Chemical"),
    ("NESTLE", "Nestle Pakistan Limited", "Food & Personal Care Products"),
    ("UNITY", "Unity Foods Limited", "Food & Personal Care Products"),
    ("INIL", "International Industries Limited", "Engineering"),
    ("ISL", "International Steels Limited", "Engineering"),
]

userrole = postgresql.ENUM("user", "admin", name="userrole", create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    # users
    userrole.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "users",
        sa.Column("role", userrole, nullable=False, server_default="user"),
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_progress",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # predictions: old rows were produced by the leaky prototype model; drop them
    op.drop_index("ix_predictions_id", table_name="predictions")
    op.drop_table("predictions")
    op.create_table(
        "predictions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("forecast_price", sa.Numeric(14, 4), nullable=False),
        sa.Column("last_close", sa.Numeric(14, 4), nullable=False),
        sa.Column("signal", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Numeric(5, 4), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_stock_id", "predictions", ["stock_id"])
    op.create_index("ix_predictions_generated_at", "predictions", ["generated_at"])

    # news_sentiments: 0.0 used to double as "unscored"; NULL now means unscored
    op.alter_column(
        "news_sentiments", "sentiment_score", existing_type=sa.Float(), nullable=True
    )
    op.execute("UPDATE news_sentiments SET sentiment_score = NULL WHERE sentiment_score = 0")

    # price_points: remove duplicates, then enforce uniqueness
    op.execute(
        """
        DELETE FROM price_points a USING price_points b
        WHERE a.id < b.id AND a.stock_id = b.stock_id AND a.timestamp = b.timestamp
        """
    )
    op.create_unique_constraint(
        "uq_price_points_stock_ts", "price_points", ["stock_id", "timestamp"]
    )

    # stocks: seed catalog (existing rows get their name/sector corrected)
    stocks = sa.table(
        "stocks",
        sa.column("id", sa.UUID()),
        sa.column("ticker", sa.String()),
        sa.column("name", sa.String()),
        sa.column("sector", sa.String()),
    )
    insert = postgresql.insert(stocks).values(
        [
            {"id": uuid.uuid4(), "ticker": t, "name": n, "sector": s}
            for t, n, s in PSX_SEED
        ]
    )
    op.execute(
        insert.on_conflict_do_update(
            index_elements=["ticker"],
            set_={"name": insert.excluded.name, "sector": insert.excluded.sector},
        )
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("uq_price_points_stock_ts", "price_points", type_="unique")

    op.execute("UPDATE news_sentiments SET sentiment_score = 0 WHERE sentiment_score IS NULL")
    op.alter_column(
        "news_sentiments", "sentiment_score", existing_type=sa.Float(), nullable=False
    )

    op.drop_index("ix_predictions_generated_at", table_name="predictions")
    op.drop_index("ix_predictions_stock_id", table_name="predictions")
    op.drop_table("predictions")
    op.create_table(
        "predictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("predicted_price", sa.Float(), nullable=False),
        sa.Column("signal", sa.String(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_predictions_id", "predictions", ["id"], unique=False)

    op.drop_column("users", "onboarding_progress")
    op.drop_column("users", "role")
    userrole.drop(op.get_bind(), checkfirst=True)
