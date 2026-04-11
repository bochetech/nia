"""
Routers del Tenant Manager.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    TenantConfigDTO,
    TeamsConfig,
    EmailConfig,
    AIConfig,
    FSMConfig,
    PaymentConfig,
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
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
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

    from shared.models.domain import LeadConfig, LimitsConfig, RAGConfig, UIConfig, TeamsConfig, EmailConfig, AIConfig, FSMConfig, PaymentConfig
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


# ─────────────────────────────────────────────────────────────────
# Configuraciones avanzadas - endpoints específicos
# ─────────────────────────────────────────────────────────────────

@router.patch(
    "/{tenant_id}/teams-config",
    response_model=APIResponse[TenantResponse],
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

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.patch(
    "/{tenant_id}/email-config",
    response_model=APIResponse[TenantResponse],
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

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.patch(
    "/{tenant_id}/ai-config",
    response_model=APIResponse[TenantResponse],
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

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.patch(
    "/{tenant_id}/fsm-config",
    response_model=APIResponse[TenantResponse],
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

    return APIResponse(data=TenantResponse.model_validate(tenant))


@router.patch(
    "/{tenant_id}/payment-config",
    response_model=APIResponse[TenantResponse],
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

    return APIResponse(data=TenantResponse.model_validate(tenant))
