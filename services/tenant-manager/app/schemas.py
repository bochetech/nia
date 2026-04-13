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
    TelegramConfig,
    TenantPlan,
    TenantStatus,
    UIConfig,
)


class TenantCreateRequest(BaseModel):
    """
    Cuerpo para crear un nuevo tenant en la plataforma NIA.

    Solo `id`, `name` y `contact_email` son obligatorios.
    El resto de los bloques de configuración son opcionales — si se omiten
    se usan los valores por defecto definidos en cada modelo de config.
    """

    id: str = Field(
        ...,
        min_length=3,
        max_length=50,
        pattern=r"^[a-z0-9_]+$",
        description=(
            "Identificador único del tenant. Solo minúsculas, números y guiones bajos. "
            "No se puede cambiar después de crear. Ej: 'vina_asturias', 'hotel_costa_del_sol'."
        ),
    )
    name: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="Nombre legible del tenant, ej: 'Viña Asturias Tours'. Se usa en la UI de administración.",
    )
    contact_email: EmailStr = Field(
        ...,
        description="Email de contacto del administrador del tenant. Se usa para notificaciones del sistema.",
    )
    plan: TenantPlan = Field(
        default=TenantPlan.STARTER,
        description="Plan de suscripción. Valores: 'starter' | 'professional' | 'enterprise'. Determina límites y funcionalidades.",
    )
    ui_config: UIConfig = Field(
        default_factory=UIConfig,
        description="Apariencia del widget: colores, título del header, mensaje de bienvenida, placeholder del input.",
    )
    lead_config: LeadConfig = Field(
        default_factory=LeadConfig,
        description="Formulario de captura de lead antes del chat: campos, consentimiento GDPR, botón de envío.",
    )
    limits_config: LimitsConfig = Field(
        default_factory=LimitsConfig,
        description="Límites operacionales: máximo de conversaciones/mes, tokens/sesión, handoff habilitado.",
    )
    rag_config: RAGConfig = Field(
        default_factory=RAGConfig,
        description="Configuración de la base de conocimiento: umbral de confianza, chunks recuperados, mensaje de fallback.",
    )
    teams_config: TeamsConfig = Field(
        default_factory=TeamsConfig,
        description="Integración con Microsoft Teams para notificaciones de handoff. Desactivado por defecto.",
    )
    email_config: EmailConfig = Field(
        default_factory=EmailConfig,
        description="Configuración SMTP para emails transaccionales. Desactivado por defecto.",
    )
    ai_config: AIConfig = Field(
        default_factory=AIConfig,
        description="Modelo LLM a usar, temperatura, system prompt personalizado, configuración de caché.",
    )
    fsm_config: FSMConfig = Field(
        default_factory=FSMConfig,
        description=(
            "Máquina de estados de la conversación: timeouts, NPS, y tabla de transiciones personalizada. "
            "Si transitions está vacío, se usa el flujo NIA por defecto."
        ),
    )
    payment_config: PaymentConfig = Field(
        default_factory=PaymentConfig,
        description="Checkout con Stripe para reservas de pago. Desactivado por defecto.",
    )
    telegram_config: TelegramConfig = Field(
        default_factory=TelegramConfig,
        description="Canal de Telegram: bot token, webhook secret, lista de chats permitidos. Desactivado por defecto.",
    )


class TenantUpdateRequest(BaseModel):
    """
    Cuerpo para actualizar la configuración de un tenant existente.
    Todos los campos son opcionales — solo se actualizan los que se envíen (PATCH semántico).
    Los bloques de config se reemplazan completos: si envías ui_config, reemplaza todo el ui_config actual.
    """

    name: str | None = Field(None, min_length=2, max_length=200, description="Nuevo nombre legible del tenant.")
    contact_email: EmailStr | None = Field(None, description="Nuevo email de contacto del administrador.")
    plan: TenantPlan | None = Field(None, description="Cambiar el plan de suscripción.")
    ui_config: UIConfig | None = Field(None, description="Reemplaza toda la configuración visual del widget.")
    lead_config: LeadConfig | None = Field(None, description="Reemplaza toda la configuración del formulario de lead.")
    limits_config: LimitsConfig | None = Field(None, description="Reemplaza todos los límites operacionales.")
    rag_config: RAGConfig | None = Field(None, description="Reemplaza toda la configuración del RAG.")
    teams_config: TeamsConfig | None = Field(None, description="Reemplaza toda la configuración de Teams.")
    email_config: EmailConfig | None = Field(None, description="Reemplaza toda la configuración de email SMTP.")
    ai_config: AIConfig | None = Field(None, description="Reemplaza toda la configuración del modelo LLM.")
    fsm_config: FSMConfig | None = Field(None, description="Reemplaza toda la configuración del FSM, incluidas las transiciones.")
    payment_config: PaymentConfig | None = Field(None, description="Reemplaza toda la configuración de pagos.")
    telegram_config: TelegramConfig | None = Field(None, description="Reemplaza toda la configuración del canal de Telegram.")


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
    telegram_config: dict
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
