"""002 — Booking intents per-tenant schema tables.

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 00:00:00.000000

Notes
-----
* Adds `booking_intents` to each per-tenant schema.
* Adds `gdpr_consent` and `source` columns to public.leads.
* The per-tenant tables are created by the tenant-manager on provisioning;
  this migration applies the changes to existing tenant schemas.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ── Helper ────────────────────────────────────────────────────────────────────

def _get_tenant_schemas(connection) -> list[str]:
    """Descubre todos los schemas de tenant (patron: tenant_*)."""
    result = connection.execute(
        sa.text(
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name LIKE 'tenant_%'"
        )
    )
    return [row[0] for row in result]


# ── DDL for booking_intents ───────────────────────────────────────────────────

def _booking_intents_table(schema: str):
    return sa.Table(
        "booking_intents",
        sa.MetaData(),
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("session_id", sa.String(128), nullable=False, index=True),
        sa.Column("product_id", sa.String(128), nullable=False),
        sa.Column("selected_date", sa.Date(), nullable=False),
        sa.Column("selected_time", sa.Time(), nullable=False),
        sa.Column("pax_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("contact", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(8), nullable=False, server_default="CLP"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending",
                  comment="pending | confirmed | cancelled | refunded"),
        # Bokun integration — populated once Bokun confirms
        sa.Column("bokun_booking_id", sa.String(128), nullable=True),
        sa.Column("bokun_confirmation_code", sa.String(64), nullable=True),
        sa.Column("checkout_session_id", sa.String(128), nullable=True,
                  comment="Stripe checkout session ID"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema=schema,
    )


def upgrade() -> None:
    conn = op.get_bind()
    schemas = _get_tenant_schemas(conn)

    # ── Add booking_intents to all existing tenant schemas ──────────────────
    for schema in schemas:
        op.create_table(
            "booking_intents",
            sa.Column("id", sa.String(64), primary_key=True),
            sa.Column("session_id", sa.String(128), nullable=False),
            sa.Column("product_id", sa.String(128), nullable=False),
            sa.Column("selected_date", sa.Date(), nullable=False),
            sa.Column("selected_time", sa.Time(), nullable=False),
            sa.Column("pax_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("contact", postgresql.JSONB, nullable=False, server_default="{}"),
            sa.Column("total_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
            sa.Column("currency", sa.String(8), nullable=False, server_default="CLP"),
            sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("bokun_booking_id", sa.String(128), nullable=True),
            sa.Column("bokun_confirmation_code", sa.String(64), nullable=True),
            sa.Column("checkout_session_id", sa.String(128), nullable=True),
            sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.TIMESTAMP(timezone=True),
                      nullable=False, server_default=sa.text("now()")),
            schema=schema,
        )
        op.create_index(f"ix_{schema}_bi_session", "booking_intents", ["session_id"], schema=schema)
        op.create_index(f"ix_{schema}_bi_status", "booking_intents", ["status"], schema=schema)
        op.execute(f"""
            CREATE OR REPLACE TRIGGER booking_intents_updated_at
            BEFORE UPDATE ON {schema}.booking_intents
            FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
        """)

    # ── Patch public.leads — add gdpr_consent + source columns if missing ───
    op.execute("""
        ALTER TABLE public.leads
        ADD COLUMN IF NOT EXISTS gdpr_consent BOOLEAN NOT NULL DEFAULT FALSE;
    """)
    op.execute("""
        ALTER TABLE public.leads
        ADD COLUMN IF NOT EXISTS source VARCHAR(64) NOT NULL DEFAULT 'widget';
    """)


def downgrade() -> None:
    conn = op.get_bind()
    schemas = _get_tenant_schemas(conn)

    for schema in schemas:
        op.execute(f"DROP TRIGGER IF EXISTS booking_intents_updated_at ON {schema}.booking_intents;")
        op.drop_table("booking_intents", schema=schema)

    op.execute("ALTER TABLE public.leads DROP COLUMN IF EXISTS gdpr_consent;")
    op.execute("ALTER TABLE public.leads DROP COLUMN IF EXISTS source;")
