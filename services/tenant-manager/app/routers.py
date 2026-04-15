"""
Routers del Tenant Manager.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.schemas import (
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyResponse,
    TenantCreateRequest,
    TenantCreateResponse,
    TenantResponse,
    TenantUpdateRequest,
    WidgetTokenRequest,
    WidgetTokenResponse,
)
from app.settings import TenantManagerSettings, get_settings
from shared.db.connection import get_db_session
from shared.security.tenant import AdminCtx, require_same_tenant
from shared.security.jwt import create_widget_token
from shared.db.redis_client import RedisKeys, get_redis
from shared.models.domain import (
    ActionType,
    ConversationFSMState,
    FlowTransition,
    IntentDefinition,
    SkillConfig,
    TenantConfigDTO,
    TeamsConfig,
    EmailConfig,
    AIConfig,
    FSMConfig,
    PaymentConfig,
    TelegramConfig,
)
from shared.utils.logging import get_logger
from shared.utils.responses import APIResponse, PaginatedResponse, PaginationMeta

logger = get_logger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


# ─────────────────────────────────────────────────────────────────
# Tenant CRUD
# ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=APIResponse[TenantCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new tenant (super_admin only)",
)
async def create_tenant(
    data: TenantCreateRequest,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
    settings: TenantManagerSettings = Depends(get_settings),
):
    admin.require_super_admin()
    try:
        tenant, raw_key = await crud.create_tenant(data, db, settings)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except Exception as exc:
        logger.error("create_tenant_error", error=str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Provisioning failed")

    response = TenantCreateResponse(
        **TenantResponse.model_validate(tenant).model_dump(),
        api_key=raw_key,
    )
    return APIResponse(data=response)


@router.get(
    "",
    response_model=PaginatedResponse[TenantResponse],
    summary="List tenants (super_admin only)",
)
async def list_tenants(
    admin: AdminCtx,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
):
    admin.require_super_admin()
    offset = (page - 1) * page_size
    tenants, total = await crud.list_tenants(db, offset=offset, limit=page_size)
    items = [TenantResponse.model_validate(t) for t in tenants]
    return PaginatedResponse(
        data=items,
        pagination=PaginationMeta(
            total_returned=len(items),
            has_more=(offset + len(items)) < total,
            limit=page_size,
        ),
    )


@router.get(
    "/{tenant_id}",
    response_model=APIResponse[TenantResponse],
    summary="Get tenant by ID",
)
async def get_tenant(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    tenant = await crud.get_tenant(tenant_id, db)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found")

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.patch(
    "/{tenant_id}",
    response_model=APIResponse[TenantResponse],
    summary="Update tenant configuration",
)
async def update_tenant(
    tenant_id: str,
    data: TenantUpdateRequest,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    try:
        tenant = await crud.update_tenant(tenant_id, data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.post(
    "/{tenant_id}/suspend",
    response_model=APIResponse[TenantResponse],
    summary="Suspend tenant (super_admin only)",
)
async def suspend_tenant(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    admin.require_super_admin()
    try:
        tenant = await crud.suspend_tenant(tenant_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return APIResponse(data=TenantResponse.model_validate(tenant))


# ─────────────────────────────────────────────────────────────────
# API Keys
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{tenant_id}/api-keys",
    response_model=APIResponse[ApiKeyCreateResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create API key for tenant",
)
async def create_api_key(
    tenant_id: str,
    data: ApiKeyCreateRequest,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    try:
        api_key_obj, raw_key = await crud.create_api_key(tenant_id, data.name, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    response = ApiKeyCreateResponse(
        **ApiKeyResponse.model_validate(api_key_obj).model_dump(),
        raw_key=raw_key,
    )
    return APIResponse(data=response)


@router.get(
    "/{tenant_id}/api-keys",
    response_model=APIResponse[list[ApiKeyResponse]],
    summary="List API keys for tenant",
)
async def list_api_keys(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    keys = await crud.list_api_keys(tenant_id, db)
    return APIResponse(data=[ApiKeyResponse.model_validate(k) for k in keys])


# ─────────────────────────────────────────────────────────────────
# Widget config (público — sin autenticación, para el widget JS)
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/widget-config",
    summary="Get public widget branding and lead configuration",
)
async def get_widget_config(
    tenant_id: str,
    db: AsyncSession = Depends(get_db_session),
    settings: TenantManagerSettings = Depends(get_settings),
):
    """
    Devuelve la configuración pública del widget: colores, textos, lead_config.
    No requiere autenticación — es llamado por el widget JS al montar.
    """
    tenant = await crud.get_tenant(tenant_id, db)
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")

    # Refrescar caché Redis del tenant (contiene jwt_secret que necesita
    # el orchestrator para verificar los widget-tokens JWT).
    from app.provisioning import _cache_tenant_config
    await _cache_tenant_config(tenant)

    ui = tenant.ui_config or {}
    lead = tenant.lead_config or {}

    return {
        "primary_color":        ui.get("primary_color", "#2563EB"),
        "logo_url":             ui.get("logo_url"),
        "chat_title":           ui.get("chat_title", "Asistente Virtual"),
        "welcome_message":      ui.get("welcome_message", ""),
        "show_welcome_message": ui.get("show_welcome_message", False),
        "input_placeholder":    ui.get("input_placeholder", "Escribe un mensaje…"),
        "suggested_questions":  ui.get("suggested_questions", []),
        "widget_token":         "",   # el widget obtiene el JWT real vía /widget-token
        "transcript_url":       settings.transcript_service_url,
        "lead_config":          lead if lead.get("enabled") else None,
    }


# ─────────────────────────────────────────────────────────────────
# Widget token (público — autenticado con API key del tenant)
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/{tenant_id}/widget-token",
    response_model=APIResponse[WidgetTokenResponse],
    summary="Issue widget JWT for a new session",
)
async def issue_widget_token(
    tenant_id: str,
    data: WidgetTokenRequest,
    db: AsyncSession = Depends(get_db_session),
    settings: TenantManagerSettings = Depends(get_settings),
):
    """
    Emite un JWT para iniciar una sesión de widget.
    Llamado por el widget JS con el API key del tenant en el header.
    """
    tenant = await crud.get_tenant(tenant_id, db)
    if not tenant or tenant.status != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found or inactive")

    session_id = str(uuid.uuid4())
    token = create_widget_token(
        session_id=session_id,
        tenant_id=tenant_id,
        secret=tenant.jwt_secret,
        page_url=data.page_url,
        user_agent=data.user_agent,
        ttl_minutes=data.ttl_minutes,
    )

    return APIResponse(
        data=WidgetTokenResponse(
            token=token,
            session_id=session_id,
            tenant_id=tenant_id,
            expires_in_seconds=data.ttl_minutes * 60,
        )
    )


# ─────────────────────────────────────────────────────────────────
# Tenant config (para consumo interno de otros servicios)
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/config",
    response_model=APIResponse[TenantConfigDTO],
    summary="Get cached tenant configuration (internal use)",
)
async def get_tenant_config(
    tenant_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Endpoint interno — otros servicios lo consultan para obtener config."""
    import json

    redis = await get_redis()
    raw = await redis.get(RedisKeys.tenant_config(tenant_id))

    if raw:
        config_dict = json.loads(raw)
        config_dict.pop("jwt_secret", None)  # No exponer secreto
        return APIResponse(data=TenantConfigDTO(**config_dict))

    # Fallback: leer de DB
    tenant = await crud.get_tenant(tenant_id, db)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    from app.provisioning import _cache_tenant_config
    await _cache_tenant_config(tenant)

    from shared.models.domain import LeadConfig, LimitsConfig, RAGConfig, UIConfig, TeamsConfig, EmailConfig, AIConfig, FSMConfig, PaymentConfig, TelegramConfig
    config = TenantConfigDTO(
        tenant_id=tenant.id,
        version=tenant.config_version,
        ui_config=UIConfig(**tenant.ui_config) if tenant.ui_config else UIConfig(),
        lead_config=LeadConfig(**tenant.lead_config) if tenant.lead_config else LeadConfig(),
        limits_config=LimitsConfig(**tenant.limits_config) if tenant.limits_config else LimitsConfig(),
        rag_config=RAGConfig(**tenant.rag_config) if tenant.rag_config else RAGConfig(),
        teams_config=TeamsConfig(**tenant.teams_config) if tenant.teams_config else TeamsConfig(),
        email_config=EmailConfig(**tenant.email_config) if tenant.email_config else EmailConfig(),
        ai_config=AIConfig(**tenant.ai_config) if tenant.ai_config else AIConfig(),
        fsm_config=FSMConfig(**tenant.fsm_config) if tenant.fsm_config else FSMConfig(),
        payment_config=PaymentConfig(**tenant.payment_config) if tenant.payment_config else PaymentConfig(),
        telegram_config=TelegramConfig(**tenant.telegram_config) if tenant.telegram_config else TelegramConfig(),
    )
    return APIResponse(data=config)


# ─────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────

def require_same_tenant_admin(admin, tenant_id: str) -> None:
    if admin.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied",
        )


async def _get_fsm_config(tenant_id: str, db: AsyncSession) -> tuple:
    """Helper: load tenant + fsm_config dict from DB. Returns (tenant, fsm_dict)."""
    tenant = await crud.get_tenant(tenant_id, db)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Tenant '{tenant_id}' not found")
    fsm = dict(tenant.fsm_config or {})
    return tenant, fsm


async def _save_fsm_config(tenant_id: str, fsm: dict, db: AsyncSession):
    """Helper: persist updated fsm_config dict directly via SQL to avoid JSONB mutation issues."""
    from sqlalchemy import text

    fsm_config = FSMConfig(**fsm)
    fsm_json = fsm_config.model_dump()

    await db.execute(
        text(
            "UPDATE tenants SET fsm_config = CAST(:fsm AS jsonb), "
            "config_version = config_version + 1, "
            "updated_at = NOW() "
            "WHERE id = :tid"
        ),
        {"fsm": __import__("json").dumps(fsm_json), "tid": tenant_id},
    )
    await db.commit()

    # Refresh Redis cache
    from app.provisioning import _cache_tenant_config
    from app import crud as _crud
    tenant = await _crud.get_tenant(tenant_id, db)
    if tenant:
        await _cache_tenant_config(tenant)

    logger.info("fsm_config_saved", tenant_id=tenant_id)


# ─────────────────────────────────────────────────────────────────
# Intents CRUD  (per-tenant configurable intents)
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/intents",
    response_model=APIResponse[list[IntentDefinition]],
    summary="List configured intents for a tenant",
)
async def list_intents(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the intents configured for this tenant.
    If the tenant has no custom intents, returns the 8 NIA default intents.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_intents = fsm.get("intents", [])
    if raw_intents:
        intents = [IntentDefinition(**i) if isinstance(i, dict) else i for i in raw_intents]
    else:
        # Return defaults so the caller can see what's active
        from shared.models.flow_defaults import DEFAULT_INTENTS
        intents = DEFAULT_INTENTS

    return APIResponse(data=intents)


@router.post(
    "/{tenant_id}/intents",
    response_model=APIResponse[IntentDefinition],
    status_code=status.HTTP_201_CREATED,
    summary="Add a new intent to the tenant",
)
async def create_intent(
    tenant_id: str,
    intent: IntentDefinition,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Add a custom intent to the tenant's FSM configuration.
    If the tenant has no custom intents yet, the 8 defaults are copied first,
    then the new intent is appended.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_intents: list[dict] = fsm.get("intents", [])

    # If empty, bootstrap with defaults so we don't lose the base intents
    if not raw_intents:
        from shared.models.flow_defaults import DEFAULT_INTENTS
        raw_intents = [i.model_dump() for i in DEFAULT_INTENTS]

    # Check for duplicate key
    existing_keys = {i["key"] for i in raw_intents}
    if intent.key in existing_keys:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Intent '{intent.key}' already exists. Use PATCH to update it.",
        )

    raw_intents.append(intent.model_dump())
    fsm["intents"] = raw_intents
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data=intent)


@router.patch(
    "/{tenant_id}/intents/{intent_key}",
    response_model=APIResponse[IntentDefinition],
    summary="Update an existing intent",
)
async def update_intent(
    tenant_id: str,
    intent_key: str,
    updates: dict,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Partially update an intent's fields (name, description, examples, enabled, priority).
    The `key` field cannot be changed — delete and recreate if you need a new key.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_intents: list[dict] = fsm.get("intents", [])

    # If no custom intents, bootstrap with defaults
    if not raw_intents:
        from shared.models.flow_defaults import DEFAULT_INTENTS
        raw_intents = [i.model_dump() for i in DEFAULT_INTENTS]

    # Find the intent
    found = False
    for i, entry in enumerate(raw_intents):
        if entry["key"] == intent_key:
            # Don't allow changing the key
            updates.pop("key", None)
            raw_intents[i] = {**entry, **updates}
            # Validate
            IntentDefinition(**raw_intents[i])
            found = True
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Intent '{intent_key}' not found")

    fsm["intents"] = raw_intents
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data=IntentDefinition(**raw_intents[i]))


@router.delete(
    "/{tenant_id}/intents/{intent_key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an intent",
)
async def delete_intent(
    tenant_id: str,
    intent_key: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Remove an intent from the tenant's configuration.
    Also removes any transitions that reference this intent.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_intents: list[dict] = fsm.get("intents", [])

    if not raw_intents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Intent '{intent_key}' not found")

    original_len = len(raw_intents)
    raw_intents = [i for i in raw_intents if i["key"] != intent_key]
    if len(raw_intents) == original_len:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Intent '{intent_key}' not found")

    # Also clean up transitions referencing this intent
    raw_transitions: list[dict] = fsm.get("transitions", [])
    raw_transitions = [t for t in raw_transitions if t.get("intent") != intent_key]

    fsm["intents"] = raw_intents
    fsm["transitions"] = raw_transitions
    await _save_fsm_config(tenant_id, fsm, db)


# ─────────────────────────────────────────────────────────────────
# Actions (read-only — predefined skills)
# ─────────────────────────────────────────────────────────────────

ACTIONS_CATALOG = [
    {"key": a.value, "name": a.name.replace("_", " ").title(), "description": desc}
    for a, desc in [
        (ActionType.FAQ, "Consulta la base de conocimiento (RAG service) y responde con información del tenant."),
        (ActionType.RECOMMEND, "Consulta el Recommender service y presenta productos/actividades al usuario."),
        (ActionType.HANDOFF, "Escala la conversación a un asesor humano (Teams, email, etc.)."),
        (ActionType.NPS, "Captura la puntuación de satisfacción del usuario (1-5)."),
        (ActionType.COMPLAINT, "Registra la queja del usuario y evalúa si necesita escalación a humano."),
        (ActionType.STATIC_REPLY, "Responde con un mensaje fijo predefinido, sin llamar a ningún servicio externo."),
        (ActionType.DISCOVERY, "Pide más detalles al usuario para entender mejor su necesidad."),
        (ActionType.CONVERSATIONAL, "Responde libremente usando el LLM con un system prompt personalizable (sin servicios externos)."),
    ]
]


@router.get(
    "/{tenant_id}/actions",
    summary="List available bot actions (skills)",
)
async def list_actions(
    tenant_id: str,
    admin: AdminCtx,
):
    """
    Returns the catalog of predefined actions (skills) available to connect
    with intents via transitions.  Actions are NOT configurable — they are
    compiled handler functions in the orchestrator.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    return APIResponse(data=ACTIONS_CATALOG)


@router.get(
    "/{tenant_id}/states",
    summary="List valid FSM states",
)
async def list_fsm_states(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the merged list of FSM states for a tenant:
    - Default states from ConversationFSMState enum
    - Custom states the tenant has added (stored in fsm_config.custom_states)

    Each item: { key, label, is_default }
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    # Default states from enum — exclude any the tenant has hidden
    _, fsm = await _get_fsm_config(tenant_id, db)
    hidden_states: set = set(fsm.get("hidden_states", []))

    states = [
        {"key": s.value, "label": s.value.replace("_", " ").title(), "is_default": True}
        for s in ConversationFSMState
        if s.value not in hidden_states
    ]
    default_keys = {s.value for s in ConversationFSMState}

    # Custom states from tenant config
    custom_states = fsm.get("custom_states", [])
    for cs in custom_states:
        if cs.get("key") and cs["key"] not in default_keys:
            states.append({
                "key": cs["key"],
                "label": cs.get("label", cs["key"].replace("_", " ").title()),
                "is_default": False,
            })

    return APIResponse(data=states)


@router.post(
    "/{tenant_id}/states",
    summary="Add a custom FSM state",
    status_code=status.HTTP_201_CREATED,
)
async def create_fsm_state(
    tenant_id: str,
    body: dict,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Add a custom FSM state for this tenant.
    Body: { "key": "my_state", "label": "My State" }
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    key = body.get("key", "").strip().lower().replace(" ", "_")
    label = body.get("label", "").strip() or key.replace("_", " ").title()

    if not key or not key.replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="State key must be alphanumeric with underscores")

    # Check conflict with defaults
    default_keys = {s.value for s in ConversationFSMState}
    if key in default_keys:
        raise HTTPException(status_code=409, detail=f"State '{key}' is a built-in state and cannot be re-created")

    _, fsm = await _get_fsm_config(tenant_id, db)
    custom_states = fsm.get("custom_states", [])

    # Check conflict with existing custom states
    if any(cs.get("key") == key for cs in custom_states):
        raise HTTPException(status_code=409, detail=f"State '{key}' already exists")

    custom_states.append({"key": key, "label": label})
    fsm["custom_states"] = custom_states
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data={"key": key, "label": label, "is_default": False})


@router.delete(
    "/{tenant_id}/states/{state_key}",
    summary="Delete a custom FSM state",
)
async def delete_fsm_state(
    tenant_id: str,
    state_key: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Delete an FSM state from the tenant's available states.
    'idle' is the only immutable state and cannot be removed.
    Built-in (enum) states are removed by recording them in a
    'hidden_states' list in fsm_config rather than actually deleting
    the enum value. Custom states are removed from custom_states.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    if state_key == "idle":
        raise HTTPException(status_code=400, detail="Cannot delete the 'idle' state — it is the initial state")

    _, fsm = await _get_fsm_config(tenant_id, db)

    default_keys = {s.value for s in ConversationFSMState}

    if state_key in default_keys:
        # Hide built-in state by adding to hidden list
        hidden = set(fsm.get("hidden_states", []))
        hidden.add(state_key)
        fsm["hidden_states"] = list(hidden)
        await _save_fsm_config(tenant_id, fsm, db)
        return APIResponse(data={"deleted": state_key, "type": "hidden"})

    # Delete custom state
    custom_states = fsm.get("custom_states", [])
    original_len = len(custom_states)
    custom_states = [cs for cs in custom_states if cs.get("key") != state_key]

    if len(custom_states) == original_len:
        raise HTTPException(status_code=404, detail=f"State '{state_key}' not found")

    fsm["custom_states"] = custom_states
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data={"deleted": True, "key": state_key})


# ─────────────────────────────────────────────────────────────────
# Transitions CRUD
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/transitions",
    response_model=APIResponse[list[FlowTransition]],
    summary="List FSM transitions for a tenant",
)
async def list_transitions(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the FSM transitions configured for this tenant.
    If the tenant has no custom transitions, returns the NIA defaults.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_transitions = fsm.get("transitions", [])
    if raw_transitions:
        transitions = [FlowTransition(**t) if isinstance(t, dict) else t for t in raw_transitions]
    else:
        from shared.models.flow_defaults import DEFAULT_TRANSITIONS
        transitions = DEFAULT_TRANSITIONS

    return APIResponse(data=transitions)


@router.put(
    "/{tenant_id}/transitions",
    response_model=APIResponse[list[FlowTransition]],
    summary="Replace all FSM transitions",
)
async def replace_transitions(
    tenant_id: str,
    transitions: list[FlowTransition],
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Replace the entire transitions table for a tenant.
    Validates that every transition.intent references a configured intent key.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    _, fsm = await _get_fsm_config(tenant_id, db)

    # Validate intents exist
    raw_intents = fsm.get("intents", [])
    if raw_intents:
        valid_keys = {i["key"] for i in raw_intents}
    else:
        # Use default intent keys
        from shared.models.flow_defaults import DEFAULT_INTENTS
        valid_keys = {i.key for i in DEFAULT_INTENTS}

    # Validate all actions are known (including conversational sub-skills)
    valid_actions = {a.value for a in ActionType}

    errors = []
    for t in transitions:
        # Empty intent = wildcard (matches any intent) — skip validation
        if t.intent and t.intent not in valid_keys:
            errors.append(f"Intent '{t.intent}' not found in configured intents. Valid: {sorted(valid_keys)}")
        is_conversational_sub = t.action.startswith("conversational__") and len(t.action) > len("conversational__")
        if t.action not in valid_actions and not is_conversational_sub:
            errors.append(f"Action '{t.action}' is not a valid skill. Valid: {sorted(valid_actions)} or 'conversational__<slug>'")

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": errors},
        )

    fsm["transitions"] = [t.model_dump() for t in transitions]
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data=transitions)


# ─────────────────────────────────────────────────────────────────
# Skills / Action Configuration CRUD
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/skills",
    response_model=APIResponse[list[SkillConfig]],
    summary="List skill configs for a tenant",
)
async def list_skills(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the skill configurations for this tenant.

    Each skill config defines how the AI prepares to execute a particular action:
    entity extraction schema, preparation prompt, and response templates.

    If the tenant has no custom skill configs, returns the NIA defaults.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_skills = fsm.get("skills", [])
    if raw_skills:
        skills = [SkillConfig(**s) if isinstance(s, dict) else s for s in raw_skills]
    else:
        from shared.models.flow_defaults import DEFAULT_SKILLS
        skills = DEFAULT_SKILLS

    return APIResponse(data=skills)


@router.get(
    "/{tenant_id}/skills/{action_key}",
    response_model=APIResponse[SkillConfig],
    summary="Get skill config for a specific action",
)
async def get_skill(
    tenant_id: str,
    action_key: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Returns the skill configuration for a specific action.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_skills = fsm.get("skills", [])
    if raw_skills:
        skills = [SkillConfig(**s) if isinstance(s, dict) else s for s in raw_skills]
    else:
        from shared.models.flow_defaults import DEFAULT_SKILLS
        skills = DEFAULT_SKILLS

    for skill in skills:
        if skill.action == action_key:
            return APIResponse(data=skill)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"No skill config found for action '{action_key}'",
    )


@router.put(
    "/{tenant_id}/skills/{action_key}",
    response_model=APIResponse[SkillConfig],
    summary="Create or replace skill config for an action",
)
async def upsert_skill(
    tenant_id: str,
    action_key: str,
    skill: SkillConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Create or replace the skill configuration for a specific action.

    This endpoint lets you configure:
    - **entity_schema**: What entities the AI should extract from user messages
      for this action (e.g., date, number of guests, activity type).
    - **preparation_prompt**: Instructions for the AI on how to extract entities.
    - **response_templates**: Customizable response text patterns (success, error, empty, followup).

    Example: For a hotel tenant's `recommend` skill, you might configure
    entity_schema to extract check_in_date, check_out_date, room_type, and guests
    instead of the default tourism entities (activity_type, date, pax_count).
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    # Validate action_key matches body
    if skill.action != action_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"URL action_key '{action_key}' does not match body action '{skill.action}'",
        )

    # Validate action_key: must be a known ActionType OR a conversational sub-skill
    # (conversational skills use keys like "conversational__slug" to allow multiple
    #  independent LLM personas per tenant, each with their own system prompt)
    valid_actions = {a.value for a in ActionType}
    is_conversational_sub = action_key.startswith("conversational__") and len(action_key) > len("conversational__")
    if action_key not in valid_actions and not is_conversational_sub:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Action '{action_key}' is not a valid skill. Valid: {sorted(valid_actions)} or 'conversational__<slug>'",
        )

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_skills = fsm.get("skills", [])

    # If empty, bootstrap from defaults
    if not raw_skills:
        from shared.models.flow_defaults import DEFAULT_SKILLS
        raw_skills = [s.model_dump() for s in DEFAULT_SKILLS]

    # Upsert: replace if exists, append if new
    found = False
    for i, s in enumerate(raw_skills):
        s_action = s.get("action") if isinstance(s, dict) else s.action
        if s_action == action_key:
            raw_skills[i] = skill.model_dump()
            found = True
            break
    if not found:
        raw_skills.append(skill.model_dump())

    fsm["skills"] = raw_skills
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data=skill)


@router.patch(
    "/{tenant_id}/skills/{action_key}",
    response_model=APIResponse[SkillConfig],
    summary="Partially update skill config for an action",
)
async def patch_skill(
    tenant_id: str,
    action_key: str,
    updates: dict,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Partially update the skill configuration for a specific action.
    Only the provided fields will be updated.

    Useful for updating just the entity_schema or response_templates
    without replacing the entire skill config.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    # Cannot change the action key
    if "action" in updates and updates["action"] != action_key:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot change the action key via PATCH. Use PUT to replace the entire skill.",
        )

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_skills = fsm.get("skills", [])

    # If empty, bootstrap from defaults
    if not raw_skills:
        from shared.models.flow_defaults import DEFAULT_SKILLS
        raw_skills = [s.model_dump() for s in DEFAULT_SKILLS]

    # Find and update
    found = False
    for i, s in enumerate(raw_skills):
        s_dict = s if isinstance(s, dict) else s.model_dump()
        if s_dict.get("action") == action_key:
            s_dict.update(updates)
            # Validate the merged result
            try:
                validated = SkillConfig(**s_dict)
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Invalid skill config after merge: {exc}",
                )
            raw_skills[i] = validated.model_dump()
            found = True
            break

    if not found:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No skill config found for action '{action_key}'",
        )

    fsm["skills"] = raw_skills
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data=SkillConfig(**raw_skills[i]))


@router.delete(
    "/{tenant_id}/skills/{action_key}",
    summary="Reset skill config for an action to defaults",
)
async def delete_skill(
    tenant_id: str,
    action_key: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Remove the custom skill configuration for a specific action,
    reverting it to NIA defaults.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    _, fsm = await _get_fsm_config(tenant_id, db)
    raw_skills = fsm.get("skills", [])

    if not raw_skills:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No custom skill configs configured. Already using defaults.",
        )

    original_len = len(raw_skills)
    raw_skills = [
        s for s in raw_skills
        if (s.get("action") if isinstance(s, dict) else s.action) != action_key
    ]

    if len(raw_skills) == original_len:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No skill config found for action '{action_key}'",
        )

    fsm["skills"] = raw_skills
    await _save_fsm_config(tenant_id, fsm, db)

    return APIResponse(data={"message": f"Skill config for '{action_key}' removed. Will use NIA defaults."})


# ─────────────────────────────────────────────────────────────────
# Configuraciones avanzadas - endpoints específicos
# ─────────────────────────────────────────────────────────────────

@router.patch(
    "/{tenant_id}/teams-config",
    response_model=APIResponse[TeamsConfig],
    summary="Update Teams integration configuration",
)
async def update_teams_config(
    tenant_id: str,
    config: TeamsConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración específica de Microsoft Teams."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(teams_config=config)
    
    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=TeamsConfig(**(tenant.teams_config or {})))


@router.patch(
    "/{tenant_id}/email-config",
    response_model=APIResponse[EmailConfig],
    summary="Update email/SMTP configuration",
)
async def update_email_config(
    tenant_id: str,
    config: EmailConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración SMTP para envío de emails."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(email_config=config)
    
    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=EmailConfig(**(tenant.email_config or {})))


@router.patch(
    "/{tenant_id}/ai-config",
    response_model=APIResponse[AIConfig],
    summary="Update AI model configuration",
)
async def update_ai_config(
    tenant_id: str,
    config: AIConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración de modelos de IA y prompts."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(ai_config=config)
    
    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=AIConfig(**(tenant.ai_config or {})))


@router.patch(
    "/{tenant_id}/fsm-config",
    response_model=APIResponse[FSMConfig],
    summary="Update conversation state machine configuration",
)
async def update_fsm_config(
    tenant_id: str,
    config: FSMConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración avanzada de la máquina de estados."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(fsm_config=config)
    
    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=FSMConfig(**(tenant.fsm_config or {})))


@router.patch(
    "/{tenant_id}/payment-config",
    response_model=APIResponse[PaymentConfig],
    summary="Update payment/checkout configuration",
)
async def update_payment_config(
    tenant_id: str,
    config: PaymentConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración de checkout y pagos."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(payment_config=config)
    
    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=PaymentConfig(**(tenant.payment_config or {})))


@router.patch(
    "/{tenant_id}/telegram-config",
    response_model=APIResponse[TelegramConfig],
    summary="Update Telegram channel configuration",
)
async def update_telegram_config(
    tenant_id: str,
    config: TelegramConfig,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
):
    """Actualizar configuración del canal de Telegram (bot token, webhook secret, etc.)."""
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)
        admin.require_admin()

    update_data = TenantUpdateRequest(telegram_config=config)

    try:
        tenant = await crud.update_tenant(tenant_id, update_data, db)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return APIResponse(data=TelegramConfig(**(tenant.telegram_config or {})))


# ─────────────────────────────────────────────────────────────────
# Analytics — aggregated stats per tenant
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/analytics",
    summary="Get aggregated analytics stats for a tenant",
    tags=["tenants"],
)
async def get_analytics(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
):
    """
    Returns aggregated metrics for the Admin Console dashboards:
    - Total conversations and messages in the time window
    - Average NPS score
    - Top 5 intents by frequency
    - Daily message volume (for sparkline charts)
    - Token usage and estimated cost
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    schema = f"tenant_{tenant_id}"
    since = datetime.now(UTC) - timedelta(days=days)

    try:
        # Total conversations
        r_convs = await db.execute(
            text(f"""
                SELECT COUNT(*) AS total_conversations,
                       COALESCE(SUM(messages_count), 0) AS total_messages
                FROM {schema}.conversations
                WHERE created_at >= :since
            """),
            {"since": since},
        )
        conv_row = r_convs.mappings().first() or {}

        # NPS average (stored in conversation metadata column if available)
        r_nps = await db.execute(
            text(f"""
                SELECT ROUND(AVG(nps_score)::numeric, 2) AS avg_nps,
                       COUNT(*) FILTER (WHERE nps_score IS NOT NULL) AS nps_responses
                FROM {schema}.conversations
                WHERE created_at >= :since
            """),
            {"since": since},
        )
        nps_row = r_nps.mappings().first() or {}

        # Top intents
        r_intents = await db.execute(
            text(f"""
                SELECT intent, COUNT(*) AS freq
                FROM {schema}.messages
                WHERE intent IS NOT NULL
                  AND created_at >= :since
                GROUP BY intent
                ORDER BY freq DESC
                LIMIT 10
            """),
            {"since": since},
        )
        top_intents = [{"intent": row["intent"], "count": row["freq"]} for row in r_intents.mappings().all()]

        # Daily message volume (last `days` days)
        r_daily = await db.execute(
            text(f"""
                SELECT DATE(created_at) AS day, COUNT(*) AS messages
                FROM {schema}.messages
                WHERE created_at >= :since
                GROUP BY day
                ORDER BY day ASC
            """),
            {"since": since},
        )
        daily_volume = [{"date": str(row["day"]), "messages": row["messages"]} for row in r_daily.mappings().all()]

        # Token & cost estimates
        r_tokens = await db.execute(
            text(f"""
                SELECT COALESCE(SUM(tokens), 0) AS total_tokens
                FROM {schema}.messages
                WHERE created_at >= :since
            """),
            {"since": since},
        )
        token_row = r_tokens.mappings().first() or {}
        total_tokens = int(token_row.get("total_tokens", 0))
        # Rough estimate: $0.0001 per 1000 tokens (gemini-flash tier)
        estimated_cost_usd = round(total_tokens * 0.0000001, 4)

    except Exception:
        # Schema may not exist yet for new tenants — return empty stats
        return APIResponse(data={
            "tenant_id": tenant_id,
            "days": days,
            "total_conversations": 0,
            "total_messages": 0,
            "avg_nps": None,
            "nps_responses": 0,
            "top_intents": [],
            "daily_volume": [],
            "total_tokens": 0,
            "estimated_cost_usd": 0.0,
        })

    return APIResponse(data={
        "tenant_id": tenant_id,
        "days": days,
        "total_conversations": int(conv_row.get("total_conversations", 0)),
        "total_messages": int(conv_row.get("total_messages", 0)),
        "avg_nps": float(nps_row["avg_nps"]) if nps_row.get("avg_nps") else None,
        "nps_responses": int(nps_row.get("nps_responses", 0)),
        "top_intents": top_intents,
        "daily_volume": daily_volume,
        "total_tokens": total_tokens,
        "estimated_cost_usd": estimated_cost_usd,
    })


# ─────────────────────────────────────────────────────────────────
# Sessions list — paginated conversation list for Admin Console
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/sessions",
    summary="List conversations/sessions for a tenant (Admin Console)",
    tags=["tenants"],
)
async def list_sessions(
    tenant_id: str,
    admin: AdminCtx,
    db: AsyncSession = Depends(get_db_session),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    days: int = Query(default=30, ge=1, le=365),
):
    """
    Returns a paginated list of conversations for the Admin Console conversation viewer.
    Each item includes session_id, message count, NPS score, lead info, and timestamps.
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    schema = f"tenant_{tenant_id}"
    since = datetime.now(UTC) - timedelta(days=days)
    offset = (page - 1) * page_size

    try:
        r_total = await db.execute(
            text(f"SELECT COUNT(*) FROM {schema}.conversations WHERE created_at >= :since"),
            {"since": since},
        )
        total = r_total.scalar() or 0

        r_convs = await db.execute(
            text(f"""
                SELECT c.id, c.session_id, c.messages_count, c.nps_score,
                       c.created_at, c.last_active_at,
                       l.full_name AS lead_name, l.email AS lead_email
                FROM {schema}.conversations c
                LEFT JOIN {schema}.leads l ON l.session_id = c.session_id
                WHERE c.created_at >= :since
                ORDER BY c.last_active_at DESC NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            {"since": since, "limit": page_size, "offset": offset},
        )
        rows = r_convs.mappings().all()

        sessions = []
        for row in rows:
            sessions.append({
                "id": str(row["id"]),
                "session_id": row["session_id"],
                "messages_count": row["messages_count"] or 0,
                "nps_score": row["nps_score"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "last_active_at": row["last_active_at"].isoformat() if row["last_active_at"] else None,
                "lead_name": row["lead_name"],
                "lead_email": row["lead_email"],
            })

    except Exception:
        return APIResponse(data={"items": [], "total": 0, "page": page, "page_size": page_size})

    return APIResponse(data={
        "items": sessions,
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "has_more": (offset + len(sessions)) < int(total),
    })


# ─────────────────────────────────────────────────────────────────
# RAG collection stats
# ─────────────────────────────────────────────────────────────────

@router.get(
    "/{tenant_id}/rag/stats",
    summary="Get Qdrant collection stats for a tenant",
    tags=["tenants"],
)
async def get_rag_stats(
    tenant_id: str,
    admin: AdminCtx,
    settings: TenantManagerSettings = Depends(get_settings),
):
    """
    Returns the Qdrant vector collection stats for a tenant's knowledge base:
    - vectors_count: total indexed chunks
    - status: collection health
    - collection_name: the canonical collection name used by RAG service
    """
    if not admin.is_super_admin:
        require_same_tenant_admin(admin, tenant_id)

    import httpx
    collection_name = f"{tenant_id}_docs"

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.rag_url}/v1/qdrant/collections/{collection_name}")
            if resp.status_code == 200:
                data = resp.json()
                return APIResponse(data={
                    "collection_name": collection_name,
                    "vectors_count": data.get("vectors_count", 0),
                    "status": data.get("status", "unknown"),
                    "points_count": data.get("points_count", 0),
                })
    except Exception:
        pass

    # Fallback: query Qdrant directly if RAG URL accessible
    try:
        qdrant_url = getattr(settings, "qdrant_url", "http://localhost:6333")
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{qdrant_url}/collections/{collection_name}")
            if resp.status_code == 200:
                body = resp.json()
                info = body.get("result", {})
                return APIResponse(data={
                    "collection_name": collection_name,
                    "vectors_count": info.get("vectors_count", 0),
                    "status": info.get("status", "unknown"),
                    "points_count": info.get("points_count", 0),
                })
    except Exception:
        pass

    return APIResponse(data={
        "collection_name": collection_name,
        "vectors_count": 0,
        "status": "unreachable",
        "points_count": 0,
    })
