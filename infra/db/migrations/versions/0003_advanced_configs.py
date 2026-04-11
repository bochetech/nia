"""003 — Advanced tenant configurations.

Revision ID: 0003
Revises: 0002
Create Date: 2024-01-03 00:00:00.000000

Notes
-----
* Adds teams_config, email_config, ai_config, fsm_config, payment_config columns to public.tenants
* Allows complete API configurability for all tenant settings
* Maintains backward compatibility with default empty JSON objects
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add advanced configuration columns to tenants table."""
    # Add the new configuration columns to public.tenants
    op.add_column(
        'tenants',
        sa.Column('teams_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )
    op.add_column(
        'tenants',
        sa.Column('email_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )
    op.add_column(
        'tenants',
        sa.Column('ai_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )
    op.add_column(
        'tenants',
        sa.Column('fsm_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )
    op.add_column(
        'tenants',
        sa.Column('payment_config', postgresql.JSONB, nullable=False, server_default='{}'),
        schema='public'
    )


def downgrade() -> None:
    """Remove advanced configuration columns from tenants table."""
    op.drop_column('tenants', 'payment_config', schema='public')
    op.drop_column('tenants', 'fsm_config', schema='public')
    op.drop_column('tenants', 'ai_config', schema='public')
    op.drop_column('tenants', 'email_config', schema='public')
    op.drop_column('tenants', 'teams_config', schema='public')