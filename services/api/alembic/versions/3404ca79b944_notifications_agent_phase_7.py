"""notifications agent (Phase 7)

Four new tables, nothing existing is changed: notifications (one suggestion per row, unique per
user and dedupe key so a second agent run adds nothing), notification_preferences (opt-in per
type, sensitivity, daily cap, quiet hours), push_devices (web push now, Expo in Phase 10) and
agent_runs (one row per run, with the skip reason or what was found but not sent).

Revision ID: 3404ca79b944
Revises: fdddb7608c7c
Create Date: 2026-10-25 15:50:13.341789

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3404ca79b944'
down_revision: Union[str, Sequence[str], None] = 'fdddb7608c7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('agent_runs',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('trigger', sa.String(), nullable=False),
    sa.Column('scope_user_id', sa.UUID(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.String(), nullable=False),
    sa.Column('skip_reason', sa.String(), nullable=True),
    sa.Column('model_version', sa.String(), nullable=True),
    sa.Column('forecasts_generated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('data_as_of', sa.Date(), nullable=True),
    sa.Column('portfolios_checked', sa.Integer(), nullable=False),
    sa.Column('notifications_created', sa.Integer(), nullable=False),
    sa.Column('suppressed', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('detail', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.CheckConstraint("status IN ('running', 'completed', 'skipped', 'failed')", name='ck_agent_runs_status'),
    sa.CheckConstraint("trigger IN ('schedule', 'after_predictions', 'cli')", name='ck_agent_runs_trigger'),
    sa.ForeignKeyConstraint(['scope_user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('notification_preferences',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('buy_enabled', sa.Boolean(), nullable=False),
    sa.Column('sell_enabled', sa.Boolean(), nullable=False),
    sa.Column('roll_enabled', sa.Boolean(), nullable=False),
    sa.Column('push_enabled', sa.Boolean(), nullable=False),
    sa.Column('sensitivity', sa.String(), nullable=False),
    sa.Column('daily_cap', sa.Integer(), nullable=False),
    sa.Column('quiet_hours_enabled', sa.Boolean(), nullable=False),
    sa.Column('quiet_start', sa.Time(), nullable=False),
    sa.Column('quiet_end', sa.Time(), nullable=False),
    sa.Column('language', sa.String(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("language IN ('en', 'ur')", name='ck_notification_preferences_language'),
    sa.CheckConstraint("sensitivity IN ('all', 'strong_only')", name='ck_notification_preferences_sensitivity'),
    sa.CheckConstraint('daily_cap BETWEEN 1 AND 10', name='ck_notification_preferences_cap'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id')
    )
    op.create_table('push_devices',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('platform', sa.String(), nullable=False),
    sa.Column('token', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("platform IN ('web', 'expo')", name='ck_push_devices_platform'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token', name='uq_push_devices_token')
    )
    op.create_index(op.f('ix_push_devices_user_id'), 'push_devices', ['user_id'], unique=False)
    op.create_table('notifications',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('portfolio_id', sa.UUID(), nullable=True),
    sa.Column('agent_run_id', sa.UUID(), nullable=True),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('rule', sa.String(), nullable=False),
    sa.Column('strength', sa.String(), nullable=True),
    sa.Column('ticker', sa.String(), nullable=True),
    sa.Column('reasoning', sa.Text(), nullable=False),
    sa.Column('params', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('link', sa.String(), nullable=False),
    sa.Column('data_as_of', sa.Date(), nullable=True),
    sa.Column('model_version', sa.String(), nullable=True),
    sa.Column('dedupe_key', sa.String(), nullable=False),
    sa.Column('detected_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('delivery_latency_ms', sa.Integer(), nullable=True),
    sa.Column('read', sa.Boolean(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('push_status', sa.String(), nullable=False),
    sa.Column('push_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('push_sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('push_latency_ms', sa.Integer(), nullable=True),
    sa.Column('push_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.CheckConstraint("push_status IN ('off', 'waiting_quiet_hours', 'pending', 'sent', 'no_device', 'failed')", name='ck_notifications_push_status'),
    sa.CheckConstraint("rule IN ('roll_suggested', 'sell_forecast', 'idle_cash')", name='ck_notifications_rule'),
    sa.CheckConstraint("strength IS NULL OR strength IN ('strong', 'watch')", name='ck_notifications_strength'),
    sa.CheckConstraint("type IN ('buy', 'sell', 'roll')", name='ck_notifications_type'),
    sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['portfolio_id'], ['portfolios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'dedupe_key', name='uq_notifications_user_dedupe')
    )
    op.create_index('ix_notifications_push_due', 'notifications', ['push_status', 'push_after'], unique=False)
    op.create_index('ix_notifications_user_sent', 'notifications', ['user_id', 'sent_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_notifications_user_sent', table_name='notifications')
    op.drop_index('ix_notifications_push_due', table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_push_devices_user_id'), table_name='push_devices')
    op.drop_table('push_devices')
    op.drop_table('notification_preferences')
    op.drop_table('agent_runs')
