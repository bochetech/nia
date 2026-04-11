"""
Modelos de dominio compartidos — DTOs y esquemas Pydantic.
Usados como contratos entre servicios.
"""
from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time
from enum import Enum
from typing import Any, Union

from pydantic import BaseModel, EmailStr, Field


# ─────────────────────────────────────────────────────────────────
# Enums compartidos
# ─────────────────────────────────────────────────────────────────

class TenantStatus(str, Enum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TenantPlan(str, Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class ConversationFSMState(str, Enum):
    IDLE = "idle"
    PRE_CHAT = "pre_chat"
    GREETING = "greeting"
    DISCOVERY = "discovery"
    FAQ_ANSWER = "faq_answer"
    RECOMMENDING = "recommending"
    PRODUCT_SELECTED = "product_selected"
    CHECKOUT_INIT = "checkout_init"
    AWAITING_PAYMENT = "awaiting_payment"
    PAYMENT_FAILED = "payment_failed"
    CONFIRMED = "confirmed"
    POST_CHAT = "post_chat"
    HANDOFF_ACTIVE = "handoff_active"
    CLOSED = "closed"


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class IntentType(str, Enum):
    BOOKING_INTENT = "booking_intent"
    FAQ_QUERY = "faq_query"
    COMPLAINT = "complaint"
    OUT_OF_SCOPE = "out_of_scope"
    UNCLEAR = "unclear"
    PRODUCT_INQUIRY = "product_inquiry"
    HUMAN_REQUEST = "human_request"   # "quiero hablar con un humano"
    NPS_RESPONSE = "nps_response"     # respuesta a encuesta post-chat


class HandoffTrigger(str, Enum):
    COMPLAINT = "complaint"
    UNRESOLVED = "unresolved"
    EXPLICIT_REQUEST = "explicit_request"
    PAYMENT_FAILED = "payment_failed"
    TIMEOUT = "timeout"


class CheckoutStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    EXPIRED = "expired"
    REFUNDED = "refunded"


# ─────────────────────────────────────────────────────────────────
# DTOs de Tenant
# ─────────────────────────────────────────────────────────────────

class UIConfig(BaseModel):
    primary_color: str = "#1A5276"
    secondary_color: str = "#F39C12"
    logo_url: Union[str, None] = None
    font_family: str = "Inter"
    welcome_message: str = "Hola 👋 ¿En qué puedo ayudarte hoy?"
    chat_title: str = "Asistente"
    avatar_url: Union[str, None] = None
    position: str = "bottom-right"  # bottom-right | bottom-left


class LeadField(BaseModel):
    name: str
    label: str
    type: str = "text"  # text | email | tel | number | select
    required: bool = True
    validation: Union[str, None] = None
    options: list[str] | None = None  # para type=select


class LeadConfig(BaseModel):
    enabled: bool = True
    fields: list[LeadField] = Field(default_factory=lambda: [
        LeadField(name="full_name", label="Nombre completo", type="text", required=True),
        LeadField(name="email", label="Correo electrónico", type="email", required=True),
    ])
    gdpr_consent_text: Union[str, None] = None
    submit_label: str = "Comenzar chat"


class LimitsConfig(BaseModel):
    max_tokens_per_conversation: int = 10_000
    max_conversations_per_month: int = 1_000
    max_llm_cost_usd_per_month: float = 50.0
    max_rag_docs: int = 100
    handoff_enabled: bool = True
    response_timeout_minutes: int = 15


class RAGConfig(BaseModel):
    confidence_threshold: float = 0.65
    max_tokens_response: int = 500
    fallback_message: str = "No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?"
    top_k_retrieval: int = 8
    top_k_rerank: int = 3


# ─────────────────────────────────────────────────────────────────
# DTOs de Conversación
# ─────────────────────────────────────────────────────────────────

class ConversationMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    tenant_id: str
    role: MessageRole
    content: str
    tokens: int = 0
    intent: Union[IntentType, None] = None
    confidence: Union[float, None] = None
    rag_sources: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    """Un turno de conversación (par user/assistant) para mantener en Redis."""
    role: str  # "user" | "assistant"
    content: str
    intent: Union[str, None] = None


class SessionState(BaseModel):
    """Estado completo de una sesión en Redis."""
    session_id: str
    tenant_id: str
    fsm_state: ConversationFSMState = ConversationFSMState.IDLE
    lead_id: Union[str, None] = None
    lead_captured: bool = False
    user_profile_id: Union[str, None] = None
    messages_count: int = 0
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    last_intent: Union[IntentType, None] = None
    last_entities: dict[str, Any] = Field(default_factory=dict)
    last_recommendations: list[str] = Field(default_factory=list)
    recommendation_context_id: Union[str, None] = None
    booking_intent_id: Union[str, None] = None
    checkout_session_id: Union[str, None] = None
    handoff_case_id: Union[str, None] = None
    previous_fsm_state: Union[ConversationFSMState, None] = None
    page_url: Union[str, None] = None
    user_agent: Union[str, None] = None
    # Historial de conversación (últimos MAX_HISTORY_TURNS turnos en Redis)
    conversation_history: list[ConversationTurn] = Field(default_factory=list)
    nps_score: Union[int, None] = None  # 1-5, capturado en estado POST_CHAT
    metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_active_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ─────────────────────────────────────────────────────────────────
# DTOs de Recomendación
# ─────────────────────────────────────────────────────────────────

class IntentEntities(BaseModel):
    activity_type: Union[str, None] = None
    date: Union[date, None] = None
    pax_count: Union[int, None] = None
    language_preference: Union[str, None] = None
    budget_max: Union[float, None] = None
    physical_level: Union[str, None] = None
    duration_preference_hours: Union[int, None] = None
    time_of_day: Union[str, None] = None  # morning | afternoon | evening


class AvailabilitySlot(BaseModel):
    time: str  # "09:00"
    spots_left: int
    guide_language: str
    guide_name: Union[str, None] = None


class ProductAvailability(BaseModel):
    product_id: str
    date: date
    has_slots: bool
    slots: list[AvailabilitySlot] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source: str = "mock"  # mock | api | cache
    error: bool = False
    error_type: Union[str, None] = None


class RecommendationItem(BaseModel):
    product_id: str
    tenant_id: str
    name: str
    category: str
    base_price: float
    currency: str = "CLP"
    duration_minutes: Union[int, None] = None
    languages: list[str] = Field(default_factory=list)
    score: float
    rank: int
    availability_status: str = "available"  # available | unverified | unavailable
    available_slots: list[AvailabilitySlot] = Field(default_factory=list)
    rank_reason: str = ""
    image_url: Union[str, None] = None


class RecommendationResult(BaseModel):
    recommendations: list[RecommendationItem]
    availability_checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total_candidates_evaluated: int = 0
    reason: Union[str, None] = None  # si no hay recomendaciones, por qué


# ─────────────────────────────────────────────────────────────────
# DTOs de RAG
# ─────────────────────────────────────────────────────────────────

class RAGChunkSource(BaseModel):
    doc_id: str
    doc_name: str
    chunk_index: int
    section: Union[str, None] = None
    retrieval_score: float
    rerank_score: Union[float, None] = None
    text_excerpt: str


class RAGQueryResult(BaseModel):
    query: str
    answer: str
    confidence_score: float
    chunks_used: list[RAGChunkSource]
    groundedness_check: str = "passed"  # passed | failed | skipped
    retrieval_model: str
    generation_model: str
    latency_retrieval_ms: float
    latency_generation_ms: float
    is_fallback: bool = False  # True si no se encontró respuesta


# ─────────────────────────────────────────────────────────────────
# DTOs de Checkout
# ─────────────────────────────────────────────────────────────────

class BookingContact(BaseModel):
    name: str
    email: EmailStr
    phone: Union[str, None] = None
    special_requests: Union[str, None] = None


class BookingIntentDTO(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    tenant_id: str
    product_id: str
    selected_date: date
    selected_time: time
    pax_count: int
    contact: BookingContact
    total_amount: float
    currency: str = "CLP"
    status: str = "pending"


class CheckoutSessionDTO(BaseModel):
    id: str
    tenant_id: str
    booking_intent_id: str
    session_id: str
    payment_url: str
    amount: float
    currency: str
    status: CheckoutStatus
    expires_at: datetime


# ─────────────────────────────────────────────────────────────────
# DTOs de Handoff
# ─────────────────────────────────────────────────────────────────

class HandoffCaseDTO(BaseModel):
    id: str
    tenant_id: str
    session_id: str
    trigger_type: HandoffTrigger
    trigger_reason: Union[str, None] = None
    status: str = "pending"
    context_summary: Union[str, None] = None
    bot_paused_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    expires_at: Union[datetime, None] = None


# ─────────────────────────────────────────────────────────────────
# Configuraciones avanzadas de tenant
# ─────────────────────────────────────────────────────────────────

class TeamsConfig(BaseModel):
    """Configuración de integración con Microsoft Teams."""
    enabled: bool = False
    webhook_url: str = ""
    channel_id: str = "general"
    auto_handoff_keywords: list[str] = Field(default_factory=lambda: ["queja", "problema", "reclamo"])
    escalation_timeout_minutes: int = 10
    adaptive_card_template: str = "default"
    mention_users: list[str] = Field(default_factory=list)


class EmailConfig(BaseModel):
    """Configuración SMTP para envío de emails."""
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # En producción: usar Secret Manager
    smtp_from: str = "noreply@nia-platform.com"
    smtp_from_name: str = "Asistente NIA"
    use_tls: bool = True
    timeout_seconds: int = 30
    template_path: str = "default"


class AIConfig(BaseModel):
    """Configuración de modelos de IA y prompts."""
    primary_provider: str = "vertex_ai"  # vertex_ai | openai | anthropic
    primary_model: str = "gemini-1.5-flash"
    fallback_provider: str = "openai"
    fallback_model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 1000
    top_p: float = 0.9
    system_prompt_override: str = ""
    enable_caching: bool = True
    cache_ttl_seconds: int = 300
    cost_optimization: bool = True


class FSMConfig(BaseModel):
    """Configuración avanzada de la máquina de estados."""
    states_enabled: list[str] = Field(default_factory=lambda: [
        "idle", "greeting", "discovery", "recommending", "checkout_init"
    ])
    max_conversation_turns: int = 50
    session_timeout_minutes: int = 480  # 8 horas
    nps_enabled: bool = True
    post_chat_delay_seconds: int = 300  # 5 minutos
    handoff_triggers: list[str] = Field(default_factory=lambda: [
        "complaint", "unresolved", "explicit_request"
    ])
    auto_close_after_minutes: int = 60


class PaymentConfig(BaseModel):
    """Configuración de checkout y pagos."""
    enabled: bool = False
    stripe_public_key: str = ""
    stripe_secret_key: str = ""  # En producción: Secret Manager
    currency_default: str = "CLP"
    payment_methods: list[str] = Field(default_factory=lambda: ["card"])
    checkout_session_expires_minutes: int = 30
    success_url_template: str = "https://{domain}/payment/success"
    cancel_url_template: str = "https://{domain}/payment/cancel"
    webhook_secret: str = ""


class TenantConfigDTO(BaseModel):
    tenant_id: str
    version: int
    ui_config: UIConfig = Field(default_factory=UIConfig)
    lead_config: LeadConfig = Field(default_factory=LeadConfig)
    limits_config: LimitsConfig = Field(default_factory=LimitsConfig)
    rag_config: RAGConfig = Field(default_factory=RAGConfig)
    teams_config: TeamsConfig = Field(default_factory=TeamsConfig)
    email_config: EmailConfig = Field(default_factory=EmailConfig)
    ai_config: AIConfig = Field(default_factory=AIConfig)
    fsm_config: FSMConfig = Field(default_factory=FSMConfig)
    payment_config: PaymentConfig = Field(default_factory=PaymentConfig)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
