"""
JWT utilities — generación y validación de tokens para NIA.
Dos tipos de tokens:
  - widget_token: emitido por tenant-manager, firmado con tenant secret
  - admin_token: emitido por tenant-manager, firmado con master JWT secret
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from pydantic import BaseModel

from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────
# Claims schemas
# ─────────────────────────────────────────────────────────────────

class WidgetTokenClaims(BaseModel):
    sub: str            # session_id
    tid: str            # tenant_id
    iss: str = "nia-tenant-manager"
    aud: str = "nia-widget"
    page_url: str | None = None
    user_agent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class AdminTokenClaims(BaseModel):
    sub: str            # user email o ID
    tid: str            # tenant_id (o "system" para super-admin)
    role: str           # admin | super_admin | viewer
    iss: str = "nia-tenant-manager"
    aud: str = "nia-api"

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


# ─────────────────────────────────────────────────────────────────
# Configuración de algoritmos
# ─────────────────────────────────────────────────────────────────

ALGORITHM = "HS256"
WIDGET_TOKEN_TTL_MINUTES = 60 * 8     # 8 horas
ADMIN_TOKEN_TTL_MINUTES = 60           # 1 hora


# ─────────────────────────────────────────────────────────────────
# Generación de tokens
# ─────────────────────────────────────────────────────────────────

def create_widget_token(
    *,
    session_id: str,
    tenant_id: str,
    secret: str,
    page_url: str | None = None,
    user_agent: str | None = None,
    ttl_minutes: int = WIDGET_TOKEN_TTL_MINUTES,
) -> str:
    """Genera un JWT firmado para una sesión de widget."""
    now = datetime.now(UTC)
    claims = {
        "sub": session_id,
        "tid": tenant_id,
        "iss": "nia-tenant-manager",
        "aud": "nia-widget",
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    if page_url:
        claims["page_url"] = page_url
    if user_agent:
        claims["user_agent"] = user_agent

    token = jwt.encode(claims, secret, algorithm=ALGORITHM)
    logger.debug("widget_token_created", session_id=session_id, tenant_id=tenant_id)
    return token


def create_admin_token(
    *,
    subject: str,
    tenant_id: str,
    role: str,
    secret: str,
    ttl_minutes: int = ADMIN_TOKEN_TTL_MINUTES,
) -> str:
    """Genera un JWT firmado para administración de tenant."""
    now = datetime.now(UTC)
    claims = {
        "sub": subject,
        "tid": tenant_id,
        "role": role,
        "iss": "nia-tenant-manager",
        "aud": "nia-api",
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(claims, secret, algorithm=ALGORITHM)
    logger.debug("admin_token_created", subject=subject, tenant_id=tenant_id, role=role)
    return token


# ─────────────────────────────────────────────────────────────────
# Validación de tokens
# ─────────────────────────────────────────────────────────────────

def verify_widget_token(
    token: str,
    secret: str,
) -> WidgetTokenClaims:
    """
    Valida un widget token. Lanza JWTError si no es válido.
    Retorna WidgetTokenClaims con los campos deserializados.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            audience="nia-widget",
            issuer="nia-tenant-manager",
        )
    except JWTError as exc:
        logger.warning("widget_token_invalid", error=str(exc))
        raise

    return WidgetTokenClaims(
        sub=payload["sub"],
        tid=payload["tid"],
        iss=payload.get("iss", "nia-tenant-manager"),
        aud=payload.get("aud", "nia-widget"),
        page_url=payload.get("page_url"),
        user_agent=payload.get("user_agent"),
    )


def verify_admin_token(
    token: str,
    secret: str,
) -> AdminTokenClaims:
    """
    Valida un admin token. Lanza JWTError si no es válido.
    """
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[ALGORITHM],
            audience="nia-api",
            issuer="nia-tenant-manager",
        )
    except JWTError as exc:
        logger.warning("admin_token_invalid", error=str(exc))
        raise

    return AdminTokenClaims(
        sub=payload["sub"],
        tid=payload["tid"],
        role=payload.get("role", "viewer"),
        iss=payload.get("iss", "nia-tenant-manager"),
        aud=payload.get("aud", "nia-api"),
    )


# ─────────────────────────────────────────────────────────────────
# Utilidades
# ─────────────────────────────────────────────────────────────────

def generate_api_key() -> tuple[str, str]:
    """
    Genera un API key opaco para tenants.
    Retorna (raw_key, hashed_key).
    El raw_key se muestra UNA SOLA VEZ al crear el tenant.
    El hashed_key se almacena en base de datos.
    """
    raw = f"nia_{secrets.token_urlsafe(32)}"
    hashed = _hash_api_key(raw)
    return raw, hashed


def _hash_api_key(raw_key: str) -> str:
    """SHA-256 del API key. No se usa bcrypt aquí para mantener latencia O(1)."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def verify_api_key(raw_key: str, stored_hash: str) -> bool:
    """Compara en tiempo constante el hash del api key presentado."""
    return secrets.compare_digest(_hash_api_key(raw_key), stored_hash)


def hash_token_for_redis(token: str) -> str:
    """Hash corto para usar como clave en Redis (no almacenar JWT raw)."""
    return hashlib.sha256(token.encode()).hexdigest()[:32]
