"""
Schemas Pydantic para la API del Tenant Manager.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from shared.models.domain import (
    AIConfig,
    EmailConfig,
    FSMConfig,
    LeadConfig,
    LimitsConfig,
    PaymentConfig,
    RAGConfig,
    TeamsConfig,
    TenantPlan,
    TenantStatus,
    UIConfig,
)


class TenantCreateRequest(BaseModel):
    id: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9_]+$",
        description="Unique tenant ID (lowercase alphanumeric + underscores)",
    )
    name: str = Field(..., min_length=2, max_length=200)
    contact_email: EmailStr
    plan: TenantPlan = TenantPlan.STARTER
    ui_config: UIConfig = Field(default_factory=UIConfig)
    lead_config: LeadConfig = Field(default_factory=LeadConfig)
    limits_config: LimitsConfig = Field(default_factory=LimitsConfig)
    rag_config: RAGConfig = Field(default_factory=RAGConfig)
    teams_config: TeamsConfig = Field(default_factory=TeamsConfig)
    email_config: EmailConfig = Field(default_factory=EmailConfig)
    ai_config: AIConfig = Field(default_factory=AIConfig)
    fsm_config: FSMConfig = Field(default_factory=FSMConfig)
    payment_config: PaymentConfig = Field(default_factory=PaymentConfig)


class TenantUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=200)
    contact_email: EmailStr | None = None
    plan: TenantPlan | None = None
    ui_config: UIConfig | None = None
    lead_config: LeadConfig | None = None
    limits_config: LimitsConfig | None = None
    rag_config: RAGConfig | None = None
    teams_config: TeamsConfig | None = None
    email_config: EmailConfig | None = None
    ai_config: AIConfig | None = None
    fsm_config: FSMConfig | None = None
    payment_config: PaymentConfig | None = None


class TenantResponse(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    contact_email: str
    db_schema: str
    qdrant_collection: str
    config_version: int
    ui_config: dict
    lead_config: dict
    limits_config: dict
    rag_config: dict
    teams_config: dict
    email_config: dict
    ai_config: dict
    fsm_config: dict
    payment_config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantCreateResponse(TenantResponse):
    """Extendida con el API key — solo se muestra una vez."""
    api_key: str


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)


class ApiKeyResponse(BaseModel):
    id: str
    tenant_id: str
    name: str
    is_active: bool
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class ApiKeyCreateResponse(ApiKeyResponse):
    """Incluye el raw key — solo al crear."""
    raw_key: str


class WidgetTokenRequest(BaseModel):
    page_url: str | None = None
    user_agent: str | None = None
    ttl_minutes: int = Field(default=480, ge=1, le=1440)


class WidgetTokenResponse(BaseModel):
    token: str
    session_id: str
    tenant_id: str
    expires_in_seconds: int
