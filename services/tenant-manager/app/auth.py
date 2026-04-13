"""
Auth router — emite admin JWTs mediante usuario/contraseña.

POST /auth/token   → login con email + password, devuelve JWT de admin
POST /auth/refresh → renueva un token válido (mismas claims, nueva expiración)
"""
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr

from app.settings import get_settings
from shared.security.jwt import create_admin_token, verify_admin_token
from jose import JWTError

router = APIRouter(prefix="/auth", tags=["auth"])


# ─────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────

class TokenRequest(BaseModel):
    email: str
    password: str
    ttl_minutes: int = 1440  # 24 h por defecto


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    role: str
    subject: str


class RefreshRequest(BaseModel):
    token: str
    ttl_minutes: int = 1440


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Login — obtén un JWT de admin",
    description="""
Autentica con email y contraseña del super-admin.

**Credenciales por defecto (dev):**
- email: `admin@nia.local`
- password: `changeme`

El token resultante debe enviarse en el header:
`Authorization: Bearer <token>`
""",
)
async def login(body: TokenRequest) -> TokenResponse:
    settings = get_settings()

    # Validar credenciales del super-admin
    if (
        body.email != settings.super_admin_email
        or body.password != settings.super_admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )

    secret = settings.jwt_secret.get_secret_value()
    token = create_admin_token(
        subject=body.email,
        tenant_id="*",
        role="super_admin",
        secret=secret,
        ttl_minutes=body.ttl_minutes,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=body.ttl_minutes * 60,
        role="super_admin",
        subject=body.email,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renueva un token admin existente",
)
async def refresh(body: RefreshRequest) -> TokenResponse:
    settings = get_settings()
    secret = settings.jwt_secret.get_secret_value()

    try:
        claims = verify_admin_token(body.token, secret)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {exc}",
        ) from exc

    new_token = create_admin_token(
        subject=claims.sub,
        tenant_id=claims.tid,
        role=claims.role,
        secret=secret,
        ttl_minutes=body.ttl_minutes,
    )

    return TokenResponse(
        access_token=new_token,
        expires_in_seconds=body.ttl_minutes * 60,
        role=claims.role,
        subject=claims.sub,
    )
