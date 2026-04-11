"""
Tenant context middleware y dependencias FastAPI.
Garantiza el aislamiento cross-tenant en todos los servicios.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from shared.db.redis_client import RedisKeys, get_redis
from shared.security.jwt import (
    AdminTokenClaims,
    WidgetTokenClaims,
    verify_admin_token,
    verify_widget_token,
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────
# Esquemas de seguridad
# ─────────────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


class TenantContext:
    """Contexto de tenant resuelto desde el JWT de widget."""

    def __init__(
        self,
        tenant_id: str,
        session_id: str,
        page_url: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.page_url = page_url
        self.user_agent = user_agent

    def __repr__(self) -> str:
        return f"TenantContext(tenant={self.tenant_id}, session={self.session_id})"


class AdminContext:
    """Contexto de administración resuelto desde el JWT de admin."""

    def __init__(self, tenant_id: str, subject: str, role: str) -> None:
        self.tenant_id = tenant_id
        self.subject = subject
        self.role = role

    @property
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    def require_admin(self) -> None:
        if self.role not in ("admin", "super_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role: admin required",
            )

    def require_super_admin(self) -> None:
        if self.role != "super_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role: super_admin required",
            )


# ─────────────────────────────────────────────────────────────────
# Helper interno: obtener tenant config desde Redis o header
# ─────────────────────────────────────────────────────────────────

async def _get_tenant_jwt_secret(tenant_id: str, request: Request) -> str:
    """
    Obtiene el jwt_secret del tenant.
    1. Intenta Redis (TenantConfig cacheada)
    2. Si no hay, lee del header X-Tenant-Secret (solo para testing / bootstrap)
    En producción siempre viene de Redis.
    """
    redis = await get_redis()
    key = RedisKeys.tenant_config(tenant_id)
    raw = await redis.get(key)

    if raw:
        import json
        config = json.loads(raw)
        secret = config.get("jwt_secret") or config.get("widget_secret")
        if secret:
            return secret

    # Fallback para desarrollo / bootstrap
    secret_header = request.headers.get("X-Tenant-Secret")
    if secret_header:
        logger.warning("using_x_tenant_secret_header", tenant_id=tenant_id)
        return secret_header

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Tenant secret not configured",
    )


# ─────────────────────────────────────────────────────────────────
# Dependencias FastAPI
# ─────────────────────────────────────────────────────────────────

async def get_tenant_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> TenantContext:
    """
    FastAPI dependency para endpoints del widget / orchestrator.
    Extrae y valida el widget JWT del header Authorization: Bearer <token>.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    # Primero decodimos sin verificar sólo para extraer el tenant_id (tid)
    import jose.jwt as _jwt
    try:
        unverified = _jwt.get_unverified_claims(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
        )

    tenant_id = unverified.get("tid")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing tenant identifier in token",
        )

    secret = await _get_tenant_jwt_secret(tenant_id, request)

    try:
        claims: WidgetTokenClaims = verify_widget_token(token, secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc

    logger.debug("tenant_context_resolved", tenant_id=tenant_id, session_id=claims.sub)
    return TenantContext(
        tenant_id=claims.tid,
        session_id=claims.sub,
        page_url=claims.page_url,
        user_agent=claims.user_agent,
    )


async def get_admin_context(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> AdminContext:
    """
    FastAPI dependency para endpoints del panel admin.
    Valida admin JWT usando el master JWT_SECRET del sistema.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Leer el master secret desde settings
    from shared.config.base import BaseServiceSettings
    settings = BaseServiceSettings()  # type: ignore[call-arg]
    secret = settings.jwt_secret.get_secret_value()

    try:
        claims: AdminTokenClaims = verify_admin_token(credentials.credentials, secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid admin token: {exc}",
        ) from exc

    logger.debug(
        "admin_context_resolved",
        subject=claims.sub,
        tenant_id=claims.tid,
        role=claims.role,
    )
    return AdminContext(
        tenant_id=claims.tid,
        subject=claims.sub,
        role=claims.role,
    )


def require_same_tenant(context: TenantContext, tenant_id: str) -> None:
    """
    Valida que el tenant_id del request coincida con el del contexto.
    Previene ataques cross-tenant: tenant A accediendo a recursos de tenant B.
    """
    if context.tenant_id != tenant_id:
        logger.warning(
            "cross_tenant_attempt",
            context_tenant=context.tenant_id,
            requested_tenant=tenant_id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant access denied",
        )


# Aliases convenientes
TenantCtx = Annotated[TenantContext, Depends(get_tenant_context)]
AdminCtx = Annotated[AdminContext, Depends(get_admin_context)]
