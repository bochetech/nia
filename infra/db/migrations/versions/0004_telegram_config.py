"""004 — Telegram channel configuration.

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-13 00:00:00.000000

Notes
-----
* Adds telegram_config column to public.tenants
* Stores bot token, webhook secret, allowed_chat_ids, etc.
* Defaults to empty JSON object for backward compatibility
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add telegram_config column to tenants table."""
    op.add_column(
        'tenants',
        sa.Column('telegram_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )


def downgrade() -> None:
    """Remove telegram_config column from tenants table."""
    op.drop_column('tenants', 'telegram_config', schema='public')
