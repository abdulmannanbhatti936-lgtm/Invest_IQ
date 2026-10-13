"""chat_messages (Phase 8)

One new table, nothing existing is changed. Each row is one chat message; an assistant row also
records the context version and hash it was grounded on, the ids of the rows that context was
built from, the provider and model, token counts, latency and the figure-check result.

Revision ID: fdddb7608c7c
Revises: 95d20f23f1ca
Create Date: 2026-10-13 16:05:00.316794

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'fdddb7608c7c'
down_revision: Union[str, Sequence[str], None] = '95d20f23f1ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('chat_messages',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('role', sa.String(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('context_version', sa.String(), nullable=True),
    sa.Column('context_hash', sa.String(length=64), nullable=True),
    sa.Column('context_refs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('prompt_version', sa.String(), nullable=True),
    sa.Column('provider', sa.String(), nullable=True),
    sa.Column('model', sa.String(), nullable=True),
    sa.Column('input_tokens', sa.Integer(), nullable=True),
    sa.Column('output_tokens', sa.Integer(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('figure_check', sa.String(), nullable=True),
    sa.Column('figure_check_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sources', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.CheckConstraint("figure_check IS NULL OR figure_check IN ('passed', 'regenerated', 'fallback')", name='ck_chat_messages_figure_check'),
    sa.CheckConstraint("language IN ('en', 'ur', 'ur-latn')", name='ck_chat_messages_language'),
    sa.CheckConstraint("role IN ('user', 'assistant')", name='ck_chat_messages_role'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_user_created', 'chat_messages', ['user_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_messages_user_created', table_name='chat_messages')
    op.drop_table('chat_messages')
