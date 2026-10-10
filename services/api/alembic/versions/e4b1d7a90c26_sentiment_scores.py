"""sentiment_scores replaces news_sentiments; news_source_status

news_sentiments (integer id, headline, score, timestamp) never matched Architecture.md §7
and never held real data. It is replaced by sentiment_scores (UUID id, source, url,
headline, published_at, score, label, scorer), unique per stock and url, plus
news_source_status for the last attempt and success of each news source (FR22).

The upgrade refuses to run if news_sentiments has any rows, and the downgrade refuses if
sentiment_scores has any rows, so neither direction can drop data (decided 2026-10-11).

Revision ID: e4b1d7a90c26
Revises: c81f3d5a9e64
Create Date: 2026-10-11 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e4b1d7a90c26"
down_revision: Union[str, Sequence[str], None] = "c81f3d5a9e64"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _refuse_if_rows(table: str) -> None:
    rows = op.get_bind().execute(sa.text(f"SELECT count(*) FROM {table}")).scalar()
    if rows:
        raise RuntimeError(
            f"Refusing to drop {table}: it holds {rows} rows. Export or delete them "
            "deliberately first; this migration never drops data."
        )


def upgrade() -> None:
    _refuse_if_rows("news_sentiments")
    op.drop_index("ix_news_sentiments_timestamp", table_name="news_sentiments")
    op.drop_index("ix_news_sentiments_stock_id", table_name="news_sentiments")
    op.drop_table("news_sentiments")

    op.create_table(
        "sentiment_scores",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("score", sa.Numeric(5, 4), nullable=True),
        sa.Column("label", sa.String(), nullable=True),
        sa.Column("scorer", sa.String(), nullable=True),
        sa.Column("scorer_version", sa.String(), nullable=True),
        sa.Column("finbert_confidence", sa.Numeric(5, 4), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "url", name="uq_sentiment_scores_stock_url"),
        sa.CheckConstraint(
            "label IN ('positive', 'negative', 'neutral')", name="ck_sentiment_scores_label"
        ),
        sa.CheckConstraint("scorer IN ('finbert', 'vader')", name="ck_sentiment_scores_scorer"),
    )
    op.create_index("ix_sentiment_scores_stock_id", "sentiment_scores", ["stock_id"])
    op.create_index("ix_sentiment_scores_published_at", "sentiment_scores", ["published_at"])

    op.create_table(
        "news_source_status",
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("last_new_headlines", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("source"),
    )


def downgrade() -> None:
    _refuse_if_rows("sentiment_scores")
    op.drop_table("news_source_status")
    op.drop_index("ix_sentiment_scores_published_at", table_name="sentiment_scores")
    op.drop_index("ix_sentiment_scores_stock_id", table_name="sentiment_scores")
    op.drop_table("sentiment_scores")

    op.create_table(
        "news_sentiments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.UUID(), nullable=False),
        sa.Column("headline", sa.String(), nullable=False),
        sa.Column("sentiment_score", sa.Float(), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_news_sentiments_stock_id", "news_sentiments", ["stock_id"])
    op.create_index("ix_news_sentiments_timestamp", "news_sentiments", ["timestamp"])
