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
    """
    Legacy enum — kept for backwards compatibility.
    New tenants should use IntentDefinition objects in fsm_config.intents.
    The orchestrator checks fsm_config.intents first; if empty, falls back
    to this enum + INTENT_SYSTEM_PROMPT.
    """
    BOOKING_INTENT = "booking_intent"
    FAQ_QUERY = "faq_query"
    COMPLAINT = "complaint"
    OUT_OF_SCOPE = "out_of_scope"
    UNCLEAR = "unclear"
    PRODUCT_INQUIRY = "product_inquiry"
    HUMAN_REQUEST = "human_request"   # "quiero hablar con un humano"
    NPS_RESPONSE = "nps_response"     # respuesta a encuesta post-chat


class ActionType(str, Enum):
    """
    Predefined bot skills (actions).  Each value maps to a handler function
    in the orchestrator's FSM — they are NOT configurable because they
    represent compiled code, not data.

    To add a new action you must write the handler in fsm.py first.
    """
    FAQ = "faq"                          # consulta al RAG service
    RECOMMEND = "recommend"              # consulta al Recommender service
    HANDOFF = "handoff"                  # escala a asesor humano
    NPS = "nps"                          # captura puntuación NPS
    COMPLAINT = "complaint"              # registra queja y evalúa escalación
    STATIC_REPLY = "static_reply"        # responde con un mensaje fijo
    DISCOVERY = "discovery"              # pide más detalles al usuario
    CONVERSATIONAL = "conversational"    # LLM puro con preparation_prompt personalizado


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
    """Apariencia y textos del widget de chat embebido."""

    primary_color: str = Field(
        default="#1A5276",
        description="Color principal del widget en formato hex. Se aplica al header, botón launcher y burbujas del bot.",
    )
    secondary_color: str = Field(
        default="#F39C12",
        description="Color de acento (botones secundarios, highlights). Formato hex.",
    )
    logo_url: Union[str, None] = Field(
        default=None,
        description="URL de la imagen del logo que aparece en el header del widget. Si es null se muestra un emoji por defecto.",
    )
    font_family: str = Field(
        default="Inter",
        description="Fuente CSS a usar en el widget. Debe estar disponible en la página anfitriona.",
    )
    chat_title: str = Field(
        default="Asistente",
        description="Texto del header del widget. Identifica al asistente (ej: 'Soporte Viña Asturias'). Es distinto al saludo inicial.",
    )
    avatar_url: Union[str, None] = Field(
        default=None,
        description="URL del avatar del bot que aparece junto a sus mensajes. Si es null no se muestra avatar.",
    )
    position: str = Field(
        default="bottom-right",
        description="Posición del launcher flotante en la pantalla. Valores: 'bottom-right' | 'bottom-left'.",
    )
    welcome_message: str = Field(
        default="Hola 👋 ¿En qué puedo ayudarte hoy?",
        description=(
            "Primer mensaje burbuja que aparece al abrir el chat, antes de que el usuario escriba. "
            "Solo se muestra si show_welcome_message=true. "
            "No se envía al backend ni consume tokens."
        ),
    )
    show_welcome_message: bool = Field(
        default=True,
        description=(
            "Controla si el widget muestra el welcome_message como burbuja inicial al abrir el chat. "
            "true = el bot saluda proactivamente. false = el chat arranca vacío y el usuario escribe primero."
        ),
    )
    input_placeholder: str = Field(
        default="Escribe un mensaje…",
        description=(
            "Texto de ayuda (hint) dentro del textarea de escritura. "
            "Úsalo para orientar al usuario sobre qué puede preguntar, ej: 'Ej: quiero una cata para 4 personas…'"
        ),
    )


class LeadField(BaseModel):
    """Define un campo del formulario de captura de lead."""

    name: str = Field(..., description="Identificador interno del campo (ej: 'full_name', 'phone'). Debe ser único dentro del formulario.")
    label: str = Field(..., description="Etiqueta visible para el usuario (ej: 'Nombre completo').")
    type: str = Field(
        default="text",
        description="Tipo de input HTML. Valores: 'text' | 'email' | 'tel' | 'number' | 'select'.",
    )
    required: bool = Field(default=True, description="Si true, el usuario no puede enviar el formulario sin completar este campo.")
    validation: Union[str, None] = Field(
        default=None,
        description="Expresión regular para validar el valor, ej: '^[0-9]{9}$' para teléfono español.",
    )
    options: list[str] | None = Field(
        default=None,
        description="Solo para type='select'. Lista de opciones desplegables, ej: ['Mañana', 'Tarde', 'Noche'].",
    )


class LeadConfig(BaseModel):
    """Configuración del formulario de captura de datos antes de iniciar el chat."""

    enabled: bool = Field(
        default=True,
        description=(
            "Si true, el widget muestra un formulario al usuario antes de la primera conversación. "
            "Sirve para capturar nombre y email (lead). Si false, el chat empieza directamente."
        ),
    )
    fields: list[LeadField] = Field(
        default_factory=lambda: [
            LeadField(name="full_name", label="Nombre completo", type="text", required=True),
            LeadField(name="email", label="Correo electrónico", type="email", required=True),
        ],
        description="Lista de campos del formulario. Por defecto pide nombre completo y email.",
    )
    gdpr_consent_text: Union[str, None] = Field(
        default=None,
        description=(
            "Texto del checkbox de consentimiento GDPR. Si se especifica, el usuario debe aceptarlo "
            "para poder enviar el formulario. Si es null no se muestra el checkbox."
        ),
    )
    submit_label: str = Field(
        default="Comenzar chat",
        description="Texto del botón de envío del formulario de lead.",
    )


class LimitsConfig(BaseModel):
    """Límites operacionales y controles de uso del tenant."""

    max_tokens_per_conversation: int = Field(
        default=10_000,
        description="Máximo de tokens LLM acumulados por sesión. Al superarlo la conversación se cierra automáticamente.",
    )
    max_conversations_per_month: int = Field(
        default=1_000,
        description="Máximo de conversaciones únicas por mes. Al alcanzarlo el widget muestra un mensaje de capacidad agotada.",
    )
    max_llm_cost_usd_per_month: float = Field(
        default=50.0,
        description="Techo de gasto en LLM (USD/mes). El sistema deja de procesar peticiones al superarlo.",
    )
    max_rag_docs: int = Field(
        default=100,
        description="Máximo de documentos indexados en Qdrant para este tenant.",
    )
    handoff_enabled: bool = Field(
        default=True,
        description=(
            "Habilita o deshabilita el handoff a asesor humano para este tenant. "
            "Si false, los intents de tipo 'human_request' y los umbrales de queja/sin-respuesta "
            "no escalan — el bot responde que el servicio humano no está disponible."
        ),
    )
    response_timeout_minutes: int = Field(
        default=15,
        description="Minutos sin respuesta del asesor humano en handoff antes de devolver el control al bot.",
    )


class RAGConfig(BaseModel):
    """Configuración del sistema de Retrieval-Augmented Generation (base de conocimiento)."""

    confidence_threshold: float = Field(
        default=0.65,
        description=(
            "Umbral mínimo de similitud coseno (0.0–1.0) para considerar un chunk relevante. "
            "Valores más altos = respuestas más precisas pero más fallbacks. Recomendado: 0.6–0.75."
        ),
    )
    max_tokens_response: int = Field(
        default=500,
        description="Máximo de tokens en la respuesta generada por el RAG. Controla la longitud de las respuestas.",
    )
    fallback_message: str = Field(
        default="No tengo información precisa sobre eso. ¿Te gustaría hablar con un asesor?",
        description=(
            "Mensaje que el bot responde cuando el RAG no encuentra respuesta con suficiente confianza. "
            "Cada vez que se dispara suma al contador de 'unresolved', que puede escalar a handoff."
        ),
    )
    top_k_retrieval: int = Field(
        default=8,
        description="Número de chunks recuperados de Qdrant en la fase de retrieval. Más chunks = más contexto pero más latencia.",
    )
    top_k_rerank: int = Field(
        default=3,
        description="Número de chunks que pasan al modelo de generación tras el reranking. Subconjunto de top_k_retrieval.",
    )


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
    # fsm_state puede ser un enum conocido o un string para estados personalizados del tenant
    fsm_state: Union[ConversationFSMState, str] = ConversationFSMState.IDLE
    lead_id: Union[str, None] = None
    lead_captured: bool = False
    user_profile_id: Union[str, None] = None
    messages_count: int = 0
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0
    last_intent: Union[IntentType, str, None] = None
    last_entities: dict[str, Any] = Field(default_factory=dict)
    last_recommendations: list[str] = Field(default_factory=list)
    recommendation_context_id: Union[str, None] = None
    booking_intent_id: Union[str, None] = None
    checkout_session_id: Union[str, None] = None
    handoff_case_id: Union[str, None] = None
    previous_fsm_state: Union[ConversationFSMState, str, None] = None
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
    """Integración con Microsoft Teams para notificaciones y handoff de conversaciones."""

    enabled: bool = Field(
        default=False,
        description="Activa la integración con Teams. Requiere webhook_url configurado.",
    )
    webhook_url: str = Field(
        default="",
        description="URL del Incoming Webhook de Teams donde se envían las notificaciones de handoff.",
    )
    channel_id: str = Field(
        default="general",
        description="ID o nombre del canal de Teams donde se publican los mensajes.",
    )
    auto_handoff_keywords: list[str] = Field(
        default_factory=lambda: ["queja", "problema", "reclamo"],
        description=(
            "Palabras clave que disparan un handoff automático al detectarse en el mensaje del usuario. "
            "Se evalúan antes del análisis de intención."
        ),
    )
    escalation_timeout_minutes: int = Field(
        default=10,
        description="Minutos que el sistema espera una respuesta del agente en Teams antes de reintentar o cerrar el handoff.",
    )
    adaptive_card_template: str = Field(
        default="default",
        description="Nombre de la plantilla de Adaptive Card usada en las notificaciones de Teams.",
    )
    mention_users: list[str] = Field(
        default_factory=list,
        description="Lista de IDs o emails de usuarios de Teams a mencionar (@mention) en cada notificación de handoff.",
    )


class EmailConfig(BaseModel):
    """Configuración SMTP para envío de emails transaccionales (confirmaciones, resúmenes, handoff)."""

    enabled: bool = Field(
        default=False,
        description="Activa el envío de emails. Requiere smtp_host y credenciales configurados.",
    )
    smtp_host: str = Field(default="", description="Servidor SMTP, ej: 'smtp.gmail.com' o 'smtp.sendgrid.net'.")
    smtp_port: int = Field(default=587, description="Puerto SMTP. 587 = TLS (recomendado), 465 = SSL, 25 = sin cifrado.")
    smtp_user: str = Field(default="", description="Usuario de autenticación SMTP.")
    smtp_password: str = Field(
        default="",
        description="Contraseña SMTP. En producción usar Secret Manager — no hardcodear aquí.",
    )
    smtp_from: str = Field(
        default="noreply@nia-platform.com",
        description="Dirección de email del remitente que verán los destinatarios.",
    )
    smtp_from_name: str = Field(
        default="Asistente NIA",
        description="Nombre del remitente visible en el cliente de email.",
    )
    use_tls: bool = Field(default=True, description="Usar STARTTLS al conectar. Recomendado true para puerto 587.")
    timeout_seconds: int = Field(default=30, description="Timeout en segundos para la conexión SMTP.")
    template_path: str = Field(
        default="default",
        description="Nombre de la plantilla HTML de email a usar. 'default' usa la plantilla NIA estándar.",
    )


class AIConfig(BaseModel):
    """Configuración del modelo de lenguaje (LLM) y comportamiento de generación de respuestas."""

    # ── Conexión primaria ────────────────────────────────────────────────────
    primary_provider: str = Field(
        default="lmstudio",
        description="Tipo de proveedor principal: 'lmstudio' | 'openai' | 'openai_compat' | 'anthropic' | 'vertex_ai'.",
    )
    primary_model: str = Field(
        default="",
        description=(
            "Nombre exacto del modelo tal como lo reporta la API, "
            "ej: 'google/gemma-4-e4b', 'gpt-4o', 'claude-3-5-sonnet-20241022'. "
            "Vacío = usa el modelo por defecto del proveedor configurado en el servidor."
        ),
    )
    primary_endpoint_url: str = Field(
        default="",
        description=(
            "URL base del endpoint del proveedor primario. "
            "Para LM Studio local: 'http://localhost:1234'. "
            "Para servicios compatibles con OpenAI: URL del servidor. "
            "Vacío = usa la URL configurada en el servidor."
        ),
    )
    primary_api_key: str = Field(
        default="",
        description=(
            "API key del proveedor primario. "
            "Para LM Studio local no se requiere (dejar vacío). "
            "Se almacena cifrado en la base de datos."
        ),
    )

    # ── Conexión fallback ────────────────────────────────────────────────────
    fallback_provider: str = Field(
        default="openai",
        description="Proveedor al que el model-adapter escala si el principal falla o está saturado.",
    )
    fallback_model: str = Field(
        default="",
        description="Modelo del proveedor de fallback. Vacío = usa el modelo por defecto del fallback.",
    )
    fallback_endpoint_url: str = Field(
        default="",
        description="URL base del endpoint fallback. Vacío = usa la URL configurada en el servidor.",
    )
    fallback_api_key: str = Field(
        default="",
        description="API key del proveedor fallback.",
    )
    temperature: float = Field(
        default=0.3,
        description=(
            "Controla la aleatoriedad de las respuestas (0.0–1.0). "
            "0.0 = respuestas deterministas y precisas. 1.0 = más creativas y variadas. "
            "Para asistentes de atención al cliente se recomienda 0.2–0.4."
        ),
    )
    max_tokens: int = Field(
        default=1000,
        description="Máximo de tokens en cada respuesta del LLM. Controla longitud y costo por llamada.",
    )
    top_p: float = Field(
        default=0.9,
        description="Nucleus sampling: solo considera los tokens cuya probabilidad acumulada alcanza este valor.",
    )
    system_prompt_override: str = Field(
        default="",
        description=(
            "Prompt de sistema personalizado que reemplaza al prompt NIA por defecto. "
            "Úsalo para dar personalidad, restricciones o contexto específico del negocio al bot. "
            "Vacío = usa el prompt estándar de NIA."
        ),
    )
    enable_caching: bool = Field(
        default=True,
        description="Activa caché semántico en Redis. Respuestas a preguntas similares se sirven desde caché, reduciendo latencia y costo.",
    )
    cache_ttl_seconds: int = Field(
        default=300,
        description="Tiempo de vida del caché semántico en segundos. Tras este tiempo la entrada expira y se regenera.",
    )
    cost_optimization: bool = Field(
        default=True,
        description="Si true, el model-adapter puede seleccionar automáticamente un modelo más económico para intents de baja complejidad.",
    )
    input_cost_per_million: float = Field(
        default=0.15,
        description=(
            "Costo en USD por cada 1 millón de tokens de entrada (prompt). "
            "Referencia: Gemini 1.5 Flash ≈ $0.075, GPT-4o-mini ≈ $0.15, "
            "GPT-4o ≈ $2.50, Claude 3 Haiku ≈ $0.25."
        ),
    )
    output_cost_per_million: float = Field(
        default=0.60,
        description=(
            "Costo en USD por cada 1 millón de tokens de salida (completion). "
            "Referencia: Gemini 1.5 Flash ≈ $0.30, GPT-4o-mini ≈ $0.60, "
            "GPT-4o ≈ $10.00, Claude 3 Haiku ≈ $1.25."
        ),
    )


class PaymentConfig(BaseModel):
    """Configuración del checkout y pasarela de pagos (Stripe) para reservas."""

    enabled: bool = Field(
        default=False,
        description="Activa el flujo de checkout. Si false, el estado CHECKOUT_INIT no se alcanza y el bot no ofrece pago.",
    )
    stripe_public_key: str = Field(
        default="",
        description="Clave pública de Stripe (pk_live_... o pk_test_...). Se expone al frontend.",
    )
    stripe_secret_key: str = Field(
        default="",
        description="Clave secreta de Stripe. En producción debe cargarse desde Secret Manager, no almacenarse aquí.",
    )
    currency_default: str = Field(
        default="CLP",
        description="Moneda ISO 4217 por defecto para los pagos, ej: 'CLP', 'EUR', 'USD'.",
    )
    payment_methods: list[str] = Field(
        default_factory=lambda: ["card"],
        description="Métodos de pago habilitados en Stripe. Valores posibles: 'card', 'bank_transfer', 'paypal'.",
    )
    checkout_session_expires_minutes: int = Field(
        default=30,
        description="Minutos antes de que una sesión de checkout de Stripe expire sin completarse.",
    )
    success_url_template: str = Field(
        default="https://{domain}/payment/success",
        description="URL de redirección tras un pago exitoso. Usa {domain} como placeholder.",
    )
    cancel_url_template: str = Field(
        default="https://{domain}/payment/cancel",
        description="URL de redirección si el usuario cancela el pago. Usa {domain} como placeholder.",
    )
    webhook_secret: str = Field(
        default="",
        description="Secreto del webhook de Stripe para verificar la autenticidad de los eventos recibidos.",
    )


class IntentDefinition(BaseModel):
    """
    Defines a configurable intent for a tenant.

    Each tenant can have its own set of intents tailored to its business domain.
    The LLM prompt is built dynamically from these definitions at runtime.

    Example:
        IntentDefinition(
            key="room_inquiry",
            name="Consulta de habitación",
            description="El usuario pregunta sobre tipos de habitación, tarifas o disponibilidad.",
            examples=["¿Tienen habitación doble?", "¿Cuánto cuesta la suite?"],
        )
    """
    key: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
        description=(
            "Identificador único del intent (snake_case). Se usa como referencia "
            "en las transiciones del FSM. Ej: 'booking_intent', 'room_inquiry'."
        ),
    )
    name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nombre legible del intent. Se muestra en dashboards y logs.",
    )
    description: str = Field(
        default="",
        min_length=0,
        max_length=500,
        description=(
            "Instrucción de clasificación para el LLM. Explica cuándo debe asignarse "
            "este intent. Esta descripción se inyecta directamente en el system prompt."
        ),
    )
    examples: list[str] = Field(
        default_factory=list,
        description=(
            "Frases de ejemplo del usuario que corresponden a este intent. "
            "Se incluyen en el prompt del LLM como few-shot examples."
        ),
    )
    enabled: bool = Field(
        default=True,
        description="Si false, el intent no se incluye en el prompt del LLM y no puede ser detectado.",
    )
    priority: int = Field(
        default=0,
        description=(
            "Prioridad de evaluación (mayor = se evalúa primero). "
            "Útil cuando un mensaje podría encajar en varios intents."
        ),
    )


# ──────────────────────────────────────────────────────────────────
# Skill / Action Configuration (per-tenant)
# ──────────────────────────────────────────────────────────────────

class EntityField(BaseModel):
    """
    Defines a single entity that the LLM should extract from the user message
    when preparing to execute a skill/action.

    The field name becomes the JSON key in the extraction output.
    The LLM uses `description` and `examples` to understand what to extract.

    Example:
        EntityField(
            name="check_in_date",
            type="date",
            description="Fecha de ingreso al hotel en formato YYYY-MM-DD",
            required=True,
            examples=["2025-03-15", "mañana", "el próximo viernes"],
        )
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        pattern=r"^[a-z][a-z0-9_]*$",
        description="Nombre del campo (snake_case). Se usa como clave JSON en el resultado de extracción.",
    )
    type: str = Field(
        default="string",
        description=(
            "Tipo de dato esperado: string, integer, float, date, boolean, enum. "
            "El LLM lo usa como hint para el formato de la respuesta."
        ),
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=300,
        description="Descripción del campo para el LLM. Explica qué dato extraer y en qué formato.",
    )
    required: bool = Field(
        default=False,
        description="Si true, el LLM intentará siempre extraer este campo. Si no puede, devuelve null.",
    )
    default: Any = Field(
        default=None,
        description="Valor por defecto si el LLM no puede extraer el campo del mensaje.",
    )
    enum_values: list[str] = Field(
        default_factory=list,
        description="Valores permitidos cuando type='enum'. Ej: ['morning', 'afternoon', 'evening'].",
    )
    examples: list[str] = Field(
        default_factory=list,
        description="Ejemplos de valores válidos para este campo. Ayudan al LLM con few-shot extraction.",
    )


class SkillConfig(BaseModel):
    """
    Configuración de un skill/action para un tenant.

    Cada tenant puede personalizar cómo la IA prepara y ejecuta cada skill.
    Esto incluye:
      - Qué entidades extraer del mensaje del usuario (entity_schema)
      - Instrucciones específicas para la IA (preparation_prompt)
      - Plantillas de respuesta personalizables (response_templates)

    Example:
        SkillConfig(
            action="recommend",
            name="Recomendador de experiencias",
            entity_schema=[
                EntityField(name="activity_type", type="string", description="Tipo de actividad turística"),
                EntityField(name="date", type="date", description="Fecha deseada en formato YYYY-MM-DD"),
                EntityField(name="pax_count", type="integer", description="Número de personas"),
            ],
            preparation_prompt="Extrae las preferencias del usuario para buscar actividades turísticas.",
            response_templates={
                "success": "Te recomiendo estas opciones:",
                "empty": "No encontré actividades que coincidan. ¿Quieres ampliar la búsqueda?",
                "error": "Estoy teniendo dificultades. ¿Puedes intentarlo de nuevo?",
            },
        )
    """
    action: str = Field(
        ...,
        description=(
            "Clave del ActionType al que aplica esta configuración. "
            "Debe coincidir con uno de los valores del enum ActionType "
            "(faq, recommend, handoff, nps, complaint, static_reply, discovery)."
        ),
    )
    name: str = Field(
        default="",
        max_length=100,
        description="Nombre legible del skill. Se muestra en dashboards.",
    )
    description: str = Field(
        default="",
        max_length=500,
        description="Descripción de lo que hace este skill para el tenant.",
    )
    entity_schema: list[EntityField] = Field(
        default_factory=list,
        description=(
            "Schema de entidades que la IA debe extraer del mensaje del usuario "
            "antes de ejecutar este skill. Se inyecta en el prompt de detección de intents. "
            "Si está vacío, se usan los campos por defecto (IntentEntities)."
        ),
    )
    preparation_prompt: str = Field(
        default="",
        max_length=1000,
        description=(
            "Instrucciones adicionales para la IA al preparar la ejecución de este skill. "
            "Se agrega al system prompt del clasificador de intents cuando la acción "
            "detectada requiere extracción de entidades. Ej: 'Extrae preferencias de habitación: "
            "tipo, fecha check-in/check-out y número de huéspedes'."
        ),
    )
    response_templates: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Plantillas de texto para las respuestas del skill. Claves estándar: "
            "'success' (resultado exitoso), 'empty' (sin resultados), 'error' (fallo), "
            "'followup' (pregunta de seguimiento). El handler puede usar str.format() "
            "con variables de contexto."
        ),
    )
    enabled: bool = Field(
        default=True,
        description="Si false, el skill está desactivado para este tenant.",
    )


class FlowTransition(BaseModel):
    """
    Define una transición de estado en el FSM.

    Cuando el orquestador detecta `intent` en `from_states` (o en cualquier estado
    si from_states está vacío), ejecuta `action` y transiciona a `to_state`.

    Acciones disponibles:
      - "faq"            → consulta al RAG service
      - "recommend"      → consulta al Recommender service
      - "handoff"        → escala a asesor humano
      - "nps"            → captura puntuación NPS
      - "complaint"      → registra queja y evalúa escalación
      - "static_reply"   → responde con `static_message` sin llamar a ningún servicio
      - "discovery"      → pide más detalles al usuario
    """
    intent: str = Field(..., description="Valor del IntentType (ej: 'faq_query')")
    from_states: list[str] = Field(
        default_factory=list,
        description="Estados desde los que aplica esta transición. Vacío = cualquier estado.",
    )
    to_state: str = Field(..., description="Estado FSM resultante tras ejecutar la acción")
    action: str = Field(..., description="Acción a ejecutar (faq, recommend, handoff, nps, complaint, static_reply, discovery)")
    static_message: str | None = Field(
        default=None,
        description="Mensaje fijo a devolver cuando action='static_reply'",
    )
    bot_prompt: str | None = Field(
        default=None,
        description=(
            "Mensaje proactivo que el bot envía ANTES de ejecutar la acción cuando "
            "esta transición se dispara. Útil para guiar al usuario al siguiente estado "
            "del funnel (ej: 'Bienvenido a Concha y Toro, déjame mostrarte nuestras experiencias')."
        ),
    )
    suggested_replies: list[str] = Field(
        default_factory=list,
        description=(
            "Opciones de respuesta sugeridas que se muestran al usuario como chips "
            "clickeables después del mensaje del bot. Permiten guiar la conversación "
            "hacia el siguiente intent deseado sin que el usuario tenga que escribir."
        ),
    )
    enabled: bool = True


class FSMConfig(BaseModel):
    """Configuración de la máquina de estados de la conversación (FSM)."""

    intents: list[IntentDefinition] = Field(
        default_factory=list,
        description=(
            "Lista de intents configurados para este tenant. Cada intent define una "
            "intención del usuario que el LLM puede detectar. Si está vacía, el "
            "orquestador usa los 8 intents NIA por defecto (booking_intent, faq_query, "
            "complaint, out_of_scope, unclear, product_inquiry, human_request, nps_response)."
        ),
    )
    transitions: list[FlowTransition] = Field(
        default_factory=list,
        description=(
            "Tabla de transiciones personalizada del flujo de conversación. "
            "Cada entrada define qué hace el bot cuando detecta un intent desde un estado dado. "
            "Si está vacía, el orquestador usa el flujo NIA por defecto (DEFAULT_TRANSITIONS)."
        ),
    )
    states_enabled: list[str] = Field(
        default_factory=lambda: ["idle", "greeting", "discovery", "recommending", "checkout_init"],
        description="Estados FSM activos para este tenant. Desactivar un estado lo excluye del flujo posible.",
    )
    max_conversation_turns: int = Field(
        default=50,
        description="Máximo de turnos (pares usuario/bot) antes de cerrar la conversación automáticamente.",
    )
    session_timeout_minutes: int = Field(
        default=480,
        description="Minutos de inactividad antes de expirar la sesión en Redis. Por defecto 8 horas.",
    )
    nps_enabled: bool = Field(
        default=True,
        description="Si true, al cerrar la conversación el bot pregunta al usuario una puntuación NPS del 1 al 5.",
    )
    post_chat_delay_seconds: int = Field(
        default=300,
        description="Segundos de espera tras el último mensaje antes de pasar al estado POST_CHAT y lanzar la encuesta NPS.",
    )
    handoff_triggers: list[str] = Field(
        default_factory=lambda: ["complaint", "unresolved", "explicit_request"],
        description=(
            "Eventos que pueden disparar un handoff a asesor humano. "
            "Valores: 'complaint' (queja), 'unresolved' (RAG sin respuesta repetido), 'explicit_request' (el usuario lo pide)."
        ),
    )
    auto_close_after_minutes: int = Field(
        default=60,
        description="Minutos tras los que una sesión en estado HANDOFF_ACTIVE sin actividad se cierra automáticamente.",
    )
    skills: list[SkillConfig] = Field(
        default_factory=list,
        description=(
            "Configuración de skills/acciones para este tenant. Cada entrada define "
            "qué entidades extraer, qué instrucciones darle a la IA y qué plantillas "
            "de respuesta usar para cada acción. Si está vacía, el orquestador usa "
            "los skills NIA por defecto (DEFAULT_SKILLS)."
        ),
    )
    # ── Admin-console only fields ─────────────────────────────
    # These are stored in the DB JSONB column and managed via the admin API.
    # They must be declared here so FSMConfig(**raw).model_dump() round-trips
    # without silently dropping them.
    hidden_states: list[str] = Field(
        default_factory=list,
        description=(
            "Default enum states that have been hidden for this tenant. "
            "Populated by DELETE /api/tenants/{id}/states/{key} when the key "
            "is a built-in ConversationFSMState value."
        ),
    )
    custom_states: list[dict] = Field(
        default_factory=list,
        description=(
            "Custom FSM states added for this tenant via the admin console. "
            "Each entry is {key, label}."
        ),
    )


class TelegramConfig(BaseModel):
    """Configuración del canal de Telegram para un tenant."""

    enabled: bool = Field(
        default=False,
        description="Activa o desactiva el canal de Telegram para este tenant.",
    )
    bot_token: str = Field(
        default="",
        description="Token del bot de Telegram obtenido desde @BotFather. Ej: 123456:ABC-DEF...",
    )
    bot_username: str = Field(
        default="",
        description="Username del bot sin @. Se usa para mostrar el enlace de inicio.",
    )
    webhook_secret: str = Field(
        default="",
        description="Token secreto para validar que los webhooks provienen de Telegram (X-Telegram-Bot-Api-Secret-Token).",
    )
    allowed_chat_ids: list[int] = Field(
        default_factory=list,
        description="Lista blanca de chat_ids permitidos. Si está vacía, acepta cualquier usuario.",
    )
    welcome_message: str = Field(
        default="¡Hola! 👋 Soy tu asistente virtual. ¿En qué puedo ayudarte hoy?",
        description="Mensaje enviado automáticamente al recibir /start.",
    )
    parse_mode: str = Field(
        default="Markdown",
        description="Modo de formato de mensajes: Markdown o HTML.",
    )


# ─── Chatwoot ─────────────────────────────────────────────────────────────────

class ChatwootHandoffAgent(BaseModel):
    """Define un grupo de agentes en Chatwoot al que el bot puede transferir casos."""
    label: str = Field(
        description="Nombre visible del grupo. Ej: 'Soporte Técnico', 'Ventas'.",
    )
    inbox_id: int = Field(
        description="ID del inbox de Chatwoot al que se asignará la conversación en el handoff.",
    )
    team_id: int | None = Field(
        default=None,
        description="ID del equipo de Chatwoot (opcional). Si se proporciona, se asignará al equipo dentro del inbox.",
    )
    assignee_id: int | None = Field(
        default=None,
        description="ID del agente individual a asignar (opcional). Si se omite, el inbox/team decide la asignación.",
    )
    fsm_trigger_state: str = Field(
        default="",
        description=(
            "Estado FSM que activa este handoff. Ej: 'handoff_sales'. "
            "Si está vacío, se usa como destino por defecto."
        ),
    )


class ChatwootConfig(BaseModel):
    """
    Integración con Chatwoot como canal de mensajería y plataforma de handoff.

    Flujo:
      Usuario en Chatwoot → webhook → NIA procesa → responde vía Chatwoot API.
      Si se activa handoff → NIA asigna la conversación a un inbox/equipo en Chatwoot.
    """

    enabled: bool = Field(
        default=False,
        description="Activa o desactiva el canal de Chatwoot para este tenant.",
    )
    instance_url: str = Field(
        default="",
        description=(
            "URL base de la instancia de Chatwoot. "
            "Ej: 'https://app.chatwoot.com' (cloud) o 'https://chat.miempresa.com' (self-hosted)."
        ),
    )
    account_id: int = Field(
        default=0,
        description="ID numérico de la cuenta en Chatwoot. Se encuentra en Ajustes → Cuenta.",
    )
    bot_inbox_id: int = Field(
        default=0,
        description=(
            "ID del inbox de Chatwoot donde el bot recibe mensajes. "
            "El webhook de Chatwoot debe apuntar al endpoint /webhooks/chatwoot/{tenant_id} de NIA."
        ),
    )
    api_access_token: str = Field(
        default="",
        description=(
            "Token de acceso de la API de Chatwoot. "
            "Se obtiene en Perfil → Tokens de Acceso. Debe tener permisos de agente."
        ),
    )
    webhook_hmac_token: str = Field(
        default="",
        description=(
            "Token HMAC para verificar la autenticidad de los webhooks entrantes de Chatwoot. "
            "Se configura en Ajustes → Integraciones → Webhooks de Chatwoot."
        ),
    )
    # Handoff
    handoff_enabled: bool = Field(
        default=False,
        description="Permite que el bot transfiera conversaciones a agentes humanos en Chatwoot.",
    )
    handoff_agents: list[ChatwootHandoffAgent] = Field(
        default_factory=list,
        description=(
            "Lista de grupos de agentes disponibles para handoff. "
            "El bot elegirá el grupo cuyo fsm_trigger_state coincida con el estado activo, "
            "o usará el primero como destino por defecto."
        ),
    )
    handoff_bot_agent_id: int | None = Field(
        default=None,
        description=(
            "ID del agente-bot en Chatwoot. Cuando NIA toma el control, "
            "la conversación se asigna a este agente. Al hacer handoff, se reasigna al grupo humano."
        ),
    )


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
    telegram_config: TelegramConfig = Field(default_factory=TelegramConfig)
    chatwoot_config: ChatwootConfig = Field(default_factory=ChatwootConfig)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
