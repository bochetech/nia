"""
Tenant provisioning pipeline.
Al crear un tenant: schema PG → tablas → Qdrant collection → cache Redis.
"""
from __future__ import annotations

import secrets

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Tenant
from app.settings import TenantManagerSettings
from shared.db.redis_client import RedisKeys, get_redis
from shared.models.domain import (
    AIConfig,
    ChatwootConfig,
    EmailConfig,
    FSMConfig,
    LeadConfig,
    LimitsConfig,
    PaymentConfig,
    RAGConfig,
    TeamsConfig,
    TelegramConfig,
    TenantConfigDTO,
    UIConfig,
)
from shared.security.jwt import generate_api_key
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# SQL para crear el schema de tenant con las tablas base
TENANT_SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS {schema};

CREATE TABLE IF NOT EXISTS {schema}.products (
    id VARCHAR(36) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100),
    description TEXT,
    short_description VARCHAR(500),
    base_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'CLP',
    duration_minutes INTEGER,
    max_pax INTEGER,
    min_pax INTEGER DEFAULT 1,
    languages JSONB DEFAULT '[]',
    images JSONB DEFAULT '[]',
    tags JSONB DEFAULT '[]',
    attributes JSONB DEFAULT '{{}}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.availability (
    id VARCHAR(36) PRIMARY KEY,
    product_id VARCHAR(36) NOT NULL REFERENCES {schema}.products(id),
    available_date DATE NOT NULL,
    start_time TIME NOT NULL,
    spots_total INTEGER NOT NULL DEFAULT 0,
    spots_reserved INTEGER NOT NULL DEFAULT 0,
    guide_name VARCHAR(100),
    guide_language VARCHAR(20),
    UNIQUE(product_id, available_date, start_time)
);

CREATE TABLE IF NOT EXISTS {schema}.leads (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) UNIQUE NOT NULL,
    full_name VARCHAR(200),
    email VARCHAR(200),
    phone VARCHAR(50),
    data JSONB DEFAULT '{{}}',
    gdpr_consent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.conversations (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) UNIQUE NOT NULL,
    lead_id VARCHAR(36) REFERENCES {schema}.leads(id),
    fsm_state VARCHAR(50) DEFAULT 'idle',
    messages_count INTEGER DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    estimated_cost_usd NUMERIC(10, 6) DEFAULT 0,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    last_active_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{{}}'
);

CREATE TABLE IF NOT EXISTS {schema}.messages (
    id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES {schema}.conversations(id),
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    tokens INTEGER DEFAULT 0,
    intent VARCHAR(50),
    confidence NUMERIC(5,4),
    rag_sources JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.booking_intents (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    product_id VARCHAR(36) NOT NULL,
    selected_date DATE NOT NULL,
    selected_time TIME NOT NULL,
    pax_count INTEGER NOT NULL DEFAULT 1,
    contact JSONB NOT NULL DEFAULT '{{}}',
    total_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    currency CHAR(3) NOT NULL DEFAULT 'CLP',
    status VARCHAR(30) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.checkout_sessions (
    id VARCHAR(36) PRIMARY KEY,
    booking_intent_id VARCHAR(36) REFERENCES {schema}.booking_intents(id),
    session_id VARCHAR(36) NOT NULL,
    payment_provider VARCHAR(50) DEFAULT 'stripe',
    external_id VARCHAR(200),
    payment_url TEXT,
    amount NUMERIC(12, 2) NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'CLP',
    status VARCHAR(30) DEFAULT 'created',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {schema}.handoff_cases (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_reason TEXT,
    status VARCHAR(30) DEFAULT 'pending',
    context_summary TEXT,
    teams_message_id VARCHAR(200),
    agent_email VARCHAR(200),
    bot_paused_at TIMESTAMPTZ DEFAULT NOW(),
    agent_joined_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_{schema_plain}_products_category ON {schema}.products(category);
CREATE INDEX IF NOT EXISTS idx_{schema_plain}_conversations_session ON {schema}.conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_{schema_plain}_messages_conv ON {schema}.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_{schema_plain}_availability_date ON {schema}.availability(product_id, available_date);
"""


async def provision_tenant(
    tenant: Tenant,
    session: AsyncSession,
    settings: TenantManagerSettings,
) -> None:
    """
    Pipeline completo de provisioning:
    1. Crear schema PostgreSQL + tablas
    2. Crear colección Qdrant
    3. Poblar cache Redis con TenantConfig
    """
    schema = tenant.db_schema
    schema_plain = schema.replace(".", "_")

    logger.info("provisioning_start", tenant_id=tenant.id, schema=schema)

    # 1. Schema + tablas PostgreSQL
    sql = TENANT_SCHEMA_SQL.format(schema=schema, schema_plain=schema_plain)
    for statement in sql.strip().split(";"):
        stmt = statement.strip()
        if stmt:
            await session.execute(text(stmt))
    await session.commit()
    logger.info("provisioning_schema_done", tenant_id=tenant.id)

    # 2. Qdrant collection
    collection_name = tenant.qdrant_collection
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.put(
                f"{settings.qdrant_url}/collections/{collection_name}",
                json={
                    "vectors": {
                        "size": 768,  # nomic-embed-text-v1.5 / text-multilingual-embedding-002
                        "distance": "Cosine",
                    },
                    "optimizers_config": {"default_segment_number": 2},
                    "replication_factor": 1,
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "qdrant_collection_warning",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
    except Exception as exc:
        logger.error("qdrant_provision_failed", error=str(exc))
        # No bloquear el provisioning si Qdrant falla en dev
        if "development" not in settings.env:
            raise

    logger.info("provisioning_qdrant_done", tenant_id=tenant.id, collection=collection_name)

    # 3. Cache Redis (TenantConfigDTO)
    await _cache_tenant_config(tenant)
    logger.info("provisioning_done", tenant_id=tenant.id)


async def _cache_tenant_config(tenant: Tenant) -> None:
    import json

    redis = await get_redis()
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
        chatwoot_config=ChatwootConfig(**tenant.chatwoot_config) if tenant.chatwoot_config else ChatwootConfig(),
    )
    # Incluir jwt_secret para que el middleware pueda verificar tokens
    raw = config.model_dump()
    raw["jwt_secret"] = tenant.jwt_secret

    await redis.setex(
        RedisKeys.tenant_config(tenant.id),
        3600,  # 1 hora TTL, se refresca en cada update
        json.dumps(raw, default=str),
    )
    logger.debug("tenant_config_cached", tenant_id=tenant.id)
