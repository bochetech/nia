"""001 — Initial schema: tenants registry + per-tenant conversations.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

Notes
-----
* The `public` schema (created by 01_init.sql) holds the tenants registry.
* Each tenant gets a dedicated schema created during provisioning (tenant-manager).
  This migration only handles the public schema tables that are needed globally.
* pgvector extension is assumed to already exist (installed by 01_init.sql).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── tenants ──────────────────────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(64), primary_key=True, comment="Slug: alphanumeric + hyphens"),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("plan", sa.String(32), nullable=False, server_default="starter",
                  comment="starter | pro | enterprise"),
        sa.Column("schema_name", sa.String(64), nullable=False, unique=True,
                  comment="PostgreSQL schema: tenant_<id>"),
        sa.Column("api_key_hash", sa.String(128), nullable=False, unique=True),
        sa.Column(
            "branding",
            postgresql.JSONB,
            nullable=False,
            server_default='{"primary_color":"#2563eb","logo_url":null,"welcome_message":"¡Hola! Soy NIA.","placeholder":"Escribe un mensaje…"}',
            comment="UI branding config served to widget",
        ),
        sa.Column("qdrant_collection", sa.String(128), nullable=True,
                  comment="Qdrant collection name for this tenant"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
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
        schema="public",
    )
    op.create_index("ix_tenants_api_key_hash", "tenants", ["api_key_hash"], schema="public")
    op.create_index("ix_tenants_is_active", "tenants", ["is_active"], schema="public")

    # ── tenant_audit_log ────────────────────────────────────────────────────
    op.create_table(
        "tenant_audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.String(64), sa.ForeignKey("public.tenants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("actor", sa.String(255), nullable=False, comment="user email or 'system'"),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("detail", postgresql.JSONB, nullable=True),
        sa.Column(
            "occurred_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="public",
    )
    op.create_index("ix_audit_tenant_id", "tenant_audit_log", ["tenant_id"], schema="public")
    op.create_index("ix_audit_occurred_at", "tenant_audit_log", ["occurred_at"], schema="public")

    # ── conversations (shared, schema-qualified by tenant_id column) ─────────
    # For high-volume deployments each tenant would get their own schema.
    # For starter/pro we use a shared table with tenant_id + RLS.
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False, server_default="widget",
                  comment="widget | teams | api"),
        sa.Column("language", sa.String(8), nullable=False, server_default="es"),
        sa.Column("fsm_state", sa.String(64), nullable=False, server_default="idle"),
        sa.Column("handoff_triggered", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_", postgresql.JSONB, nullable=True, key="metadata"),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.TIMESTAMP(timezone=True), nullable=True),
        schema="public",
    )
    op.create_index("ix_conv_tenant_session", "conversations",
                    ["tenant_id", "session_id"], schema="public")
    op.create_index("ix_conv_started_at", "conversations", ["started_at"], schema="public")

    # ── messages ─────────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64),
                  sa.ForeignKey("public.conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False, comment="user | assistant | system"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fsm_state", sa.String(64), nullable=True),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("recommendations", postgresql.JSONB, nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="public",
    )
    op.create_index("ix_msg_conversation_id", "messages", ["conversation_id"], schema="public")
    op.create_index("ix_msg_tenant_id", "messages", ["tenant_id"], schema="public")
    op.create_index("ix_msg_created_at", "messages", ["created_at"], schema="public")

    # ── leads ────────────────────────────────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("conversation_id", sa.String(64),
                  sa.ForeignKey("public.conversations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("intent_data", postgresql.JSONB, nullable=True),
        sa.Column("source", sa.String(64), nullable=False, server_default="widget"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        schema="public",
    )
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"], schema="public")
    op.create_index("ix_leads_email", "leads", ["email"], schema="public")

    # ── Enable Row Level Security ─────────────────────────────────────────────
    for table in ("conversations", "messages", "leads"):
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY tenant_isolation ON public.{table} "
            f"USING (tenant_id = current_setting('app.tenant_id', true));"
        )

    # ── updated_at trigger for tenants ────────────────────────────────────────
    op.execute("""
        CREATE OR REPLACE FUNCTION public.set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER tenants_updated_at
        BEFORE UPDATE ON public.tenants
        FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tenants_updated_at ON public.tenants;")
    op.execute("DROP FUNCTION IF EXISTS public.set_updated_at();")

    for table in ("leads", "messages", "conversations"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON public.{table};")
        op.drop_table(table, schema="public")

    op.drop_table("tenant_audit_log", schema="public")
    op.drop_table("tenants", schema="public")
