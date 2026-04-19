"""
CRUD y lógica de negocio para tenants.
"""
from __future__ import annotations

import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant, TenantApiKey
from app.provisioning import provision_tenant, _cache_tenant_config
from app.schemas import TenantCreateRequest, TenantUpdateRequest
from app.settings import TenantManagerSettings
from shared.security.jwt import generate_api_key
from shared.utils.logging import get_logger

logger = get_logger(__name__)


async def create_tenant(
    data: TenantCreateRequest,
    session: AsyncSession,
    settings: TenantManagerSettings,
) -> tuple[Tenant, str]:
    """
    Crea un tenant + provisioning completo.
    Retorna (tenant, raw_api_key).
    """
    # Verificar que no exista ya
    existing = await session.get(Tenant, data.id)
    if existing:
        raise ValueError(f"Tenant '{data.id}' already exists")

    # Generar secretos
    raw_key, key_hash = generate_api_key()
    jwt_secret = secrets.token_hex(32)
    schema = f"tenant_{data.id}"
    qdrant_collection = f"nia_tenant_{data.id}_knowledge"

    tenant = Tenant(
        id=data.id,
        name=data.name,
        slug=data.id,
        plan=data.plan.value,
        status="provisioning",
        schema_name=schema,
        db_schema=schema,
        qdrant_collection=qdrant_collection,
        contact_email=str(data.contact_email),
        api_key_hash=key_hash,
        jwt_secret=jwt_secret,
        ui_config=data.ui_config.model_dump(),
        lead_config=data.lead_config.model_dump(),
        limits_config=data.limits_config.model_dump(),
        rag_config=data.rag_config.model_dump(),
        teams_config=data.teams_config.model_dump(),
        email_config=data.email_config.model_dump(),
        ai_config=data.ai_config.model_dump(),
        fsm_config=data.fsm_config.model_dump(),
        payment_config=data.payment_config.model_dump(),
        telegram_config=data.telegram_config.model_dump(),
        chatwoot_config=data.chatwoot_config.model_dump(),
        config_version=1,
    )

    session.add(tenant)
    await session.flush()  # Obtener el ID antes del provisioning

    try:
        await provision_tenant(tenant, session, settings)
        tenant.status = "active"
        await session.commit()
        await session.refresh(tenant)
    except Exception as exc:
        await session.rollback()
        logger.error("tenant_provision_failed", tenant_id=data.id, error=str(exc))
        raise

    logger.info("tenant_created", tenant_id=tenant.id, plan=tenant.plan)
    return tenant, raw_key


async def get_tenant(tenant_id: str, session: AsyncSession) -> Tenant | None:
    return await session.get(Tenant, tenant_id)


async def list_tenants(
    session: AsyncSession,
    offset: int = 0,
    limit: int = 20,
) -> tuple[list[Tenant], int]:
    from sqlalchemy import func

    count_q = await session.execute(select(func.count()).select_from(Tenant))
    total = count_q.scalar_one()

    result = await session.execute(
        select(Tenant).order_by(Tenant.created_at.desc()).offset(offset).limit(limit)
    )
    return list(result.scalars().all()), total


async def update_tenant(
    tenant_id: str,
    data: TenantUpdateRequest,
    session: AsyncSession,
) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError(f"Tenant '{tenant_id}' not found")

    if data.name is not None:
        tenant.name = data.name
    if data.contact_email is not None:
        tenant.contact_email = str(data.contact_email)
    if data.plan is not None:
        tenant.plan = data.plan.value
    if data.ui_config is not None:
        tenant.ui_config = data.ui_config.model_dump()
        flag_modified(tenant, "ui_config")
    if data.lead_config is not None:
        tenant.lead_config = data.lead_config.model_dump()
        flag_modified(tenant, "lead_config")
    if data.limits_config is not None:
        tenant.limits_config = data.limits_config.model_dump()
        flag_modified(tenant, "limits_config")
    if data.rag_config is not None:
        tenant.rag_config = data.rag_config.model_dump()
        flag_modified(tenant, "rag_config")
    if data.teams_config is not None:
        tenant.teams_config = data.teams_config.model_dump()
        flag_modified(tenant, "teams_config")
    if data.email_config is not None:
        tenant.email_config = data.email_config.model_dump()
        flag_modified(tenant, "email_config")
    if data.ai_config is not None:
        tenant.ai_config = data.ai_config.model_dump()
        flag_modified(tenant, "ai_config")
    if data.fsm_config is not None:
        tenant.fsm_config = data.fsm_config.model_dump()
        flag_modified(tenant, "fsm_config")
    if data.payment_config is not None:
        tenant.payment_config = data.payment_config.model_dump()
        flag_modified(tenant, "payment_config")
    if data.telegram_config is not None:
        tenant.telegram_config = data.telegram_config.model_dump()
        flag_modified(tenant, "telegram_config")
    if data.chatwoot_config is not None:
        tenant.chatwoot_config = data.chatwoot_config.model_dump()
        flag_modified(tenant, "chatwoot_config")

    tenant.config_version += 1

    await session.commit()
    await session.refresh(tenant)

    # Refrescar cache
    await _cache_tenant_config(tenant)

    logger.info("tenant_updated", tenant_id=tenant_id, version=tenant.config_version)
    return tenant


async def suspend_tenant(tenant_id: str, session: AsyncSession) -> Tenant:
    tenant = await session.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError(f"Tenant '{tenant_id}' not found")
    tenant.status = "suspended"
    await session.commit()
    await session.refresh(tenant)
    logger.info("tenant_suspended", tenant_id=tenant_id)
    return tenant


async def create_api_key(
    tenant_id: str,
    name: str,
    session: AsyncSession,
) -> tuple[TenantApiKey, str]:
    tenant = await session.get(Tenant, tenant_id)
    if not tenant:
        raise ValueError(f"Tenant '{tenant_id}' not found")

    raw_key, key_hash = generate_api_key()
    api_key = TenantApiKey(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        key_hash=key_hash,
        name=name,
        is_active=True,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)
    return api_key, raw_key


async def list_api_keys(tenant_id: str, session: AsyncSession) -> list[TenantApiKey]:
    result = await session.execute(
        select(TenantApiKey)
        .where(TenantApiKey.tenant_id == tenant_id)
        .order_by(TenantApiKey.created_at.desc())
    )
    return list(result.scalars().all())
