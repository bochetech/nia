"""
SQLAlchemy ORM models para tenant-manager.
Tabla global en schema public.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.connection import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plan: Mapped[str] = mapped_column(String(20), default="starter")
    status: Mapped[str] = mapped_column(String(20), default="provisioning")
    schema_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    db_schema: Mapped[str | None] = mapped_column(String(60), nullable=True)
    qdrant_collection: Mapped[str] = mapped_column(String(100), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(200), nullable=False)
    api_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    jwt_secret: Mapped[str] = mapped_column(String(64), nullable=False)
    ui_config: Mapped[dict] = mapped_column(JSON, default=dict)
    lead_config: Mapped[dict] = mapped_column(JSON, default=dict)
    limits_config: Mapped[dict] = mapped_column(JSON, default=dict)
    rag_config: Mapped[dict] = mapped_column(JSON, default=dict)
    teams_config: Mapped[dict] = mapped_column(JSON, default=dict)
    email_config: Mapped[dict] = mapped_column(JSON, default=dict)
    ai_config: Mapped[dict] = mapped_column(JSON, default=dict)
    fsm_config: Mapped[dict] = mapped_column(JSON, default=dict)
    payment_config: Mapped[dict] = mapped_column(JSON, default=dict)
    telegram_config: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    config_version: Mapped[int] = mapped_column(Integer, default=1)

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} slug={self.slug} status={self.status}>"


class TenantApiKey(Base):
    """Tabla de API keys adicionales por tenant (varios por tenant permitidos)."""
    __tablename__ = "tenant_api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
