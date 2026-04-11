"""
Handoff Service — gestiona transferencia bot → agente humano vía Teams.
Puerto: 8007
"""

import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.config.base import BaseServiceSettings
from shared.db.redis_client import RedisKeys, close_redis, get_redis, init_redis
from shared.models.domain import HandoffCaseDTO, HandoffTrigger
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse


class HandoffSettings(BaseServiceSettings):
    service_name: str = "handoff"
    port: int = 8007
    teams_webhook_url: str = "http://teams-stub:3001/webhook"
    teams_timeout_minutes: int = 15
    teams_max_wait_minutes: int = 5
    teams_bot_app_id: str = ""
    teams_bot_app_password: str = ""


_settings: HandoffSettings | None = None


def get_settings() -> HandoffSettings:
    global _settings
    if _settings is None:
        _settings = HandoffSettings()  # type: ignore[call-arg]
    return _settings


settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

app = FastAPI(title="NIA Handoff Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - t0) * 1000))
    return response


# ─────────────────────────────────────────────────────────────────
# Schemas
# ─────────────────────────────────────────────────────────────────

class CreateHandoffRequest(BaseModel):
    tenant_id: str
    session_id: str
    trigger_type: str
    trigger_reason: str | None = None
    context_summary: str | None = None


class HandoffStatusResponse(BaseModel):
    case_id: str
    status: str
    bot_paused: bool
    agent_joined: bool
    expires_at: str | None


# ─────────────────────────────────────────────────────────────────
# Adaptive Card para Teams
# ─────────────────────────────────────────────────────────────────

def _build_teams_adaptive_card(case: HandoffCaseDTO, context: str | None) -> dict:
    return {
        "type": "message",
        "attachments": [{
            "contentType": "application/vnd.microsoft.card.adaptive",
            "content": {
                "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                "type": "AdaptiveCard",
                "version": "1.4",
                "body": [
                    {
                        "type": "TextBlock",
                        "text": "🤖 NIA — Nueva solicitud de atención",
                        "weight": "Bolder",
                        "size": "Large",
                        "color": "Accent",
                    },
                    {
                        "type": "FactSet",
                        "facts": [
                            {"title": "Case ID", "value": case.id[:8]},
                            {"title": "Tenant", "value": case.tenant_id},
                            {"title": "Sesión", "value": case.session_id[:8]},
                            {"title": "Motivo", "value": case.trigger_type},
                            {"title": "Razón", "value": case.trigger_reason or "—"},
                            {"title": "Hora", "value": case.bot_paused_at.strftime("%H:%M:%S")},
                        ],
                    },
                    {
                        "type": "TextBlock",
                        "text": f"**Contexto:** {context or 'Sin contexto adicional'}",
                        "wrap": True,
                    },
                ],
                "actions": [
                    {
                        "type": "Action.Submit",
                        "title": "✅ Tomar caso",
                        "data": {"action": "claim", "case_id": case.id},
                    },
                    {
                        "type": "Action.Submit",
                        "title": "❌ Cerrar sin atender",
                        "data": {"action": "close", "case_id": case.id},
                    },
                ],
            },
        }],
    }


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/v1/handoff/cases",
    response_model=APIResponse[HandoffCaseDTO],
    status_code=status.HTTP_201_CREATED,
)
async def create_handoff_case(body: CreateHandoffRequest) -> APIResponse[HandoffCaseDTO]:
    case_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.teams_timeout_minutes)

    try:
        trigger = HandoffTrigger(body.trigger_type)
    except ValueError:
        trigger = HandoffTrigger.UNRESOLVED

    case = HandoffCaseDTO(
        id=case_id,
        tenant_id=body.tenant_id,
        session_id=body.session_id,
        trigger_type=trigger,
        trigger_reason=body.trigger_reason,
        status="pending",
        context_summary=body.context_summary,
        bot_paused_at=datetime.now(UTC),
        expires_at=expires_at,
    )

    # Guardar en Redis
    redis = await get_redis()
    await redis.setex(
        RedisKeys.handoff_active(body.session_id),
        settings.teams_timeout_minutes * 60,
        json.dumps(case.model_dump(mode="json")),
    )
    await redis.setex(
        RedisKeys.handoff_lock(body.session_id),
        settings.teams_timeout_minutes * 60,
        "1",
    )

    # Enviar a Teams
    adaptive_card = _build_teams_adaptive_card(case, body.context_summary)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(settings.teams_webhook_url, json=adaptive_card)
            resp.raise_for_status()
            logger.info("teams_card_sent", case_id=case_id)
    except Exception as exc:
        logger.warning("teams_webhook_failed", error=str(exc))
        # No bloquear — el handoff sigue activo aunque Teams falle

    logger.info(
        "handoff_case_created",
        case_id=case_id,
        tenant_id=body.tenant_id,
        trigger=body.trigger_type,
    )
    return APIResponse(data=case)


@app.get("/v1/handoff/cases/{case_id}", response_model=APIResponse[HandoffStatusResponse])
async def get_handoff_status(case_id: str) -> APIResponse[HandoffStatusResponse]:
    # En producción: buscar en DB. Por ahora: leer de Redis.
    redis = await get_redis()
    # Búsqueda simplificada — en prod habría una tabla
    return APIResponse(data=HandoffStatusResponse(
        case_id=case_id,
        status="pending",
        bot_paused=True,
        agent_joined=False,
        expires_at=None,
    ))


@app.post("/v1/handoff/cases/{case_id}/resolve")
async def resolve_case(case_id: str, session_id: str) -> dict:
    """El agente resuelve el caso → reactivar bot."""
    redis = await get_redis()
    await redis.delete(RedisKeys.handoff_active(session_id))
    await redis.delete(RedisKeys.handoff_lock(session_id))
    logger.info("handoff_resolved", case_id=case_id, session_id=session_id)
    return {"status": "resolved", "case_id": case_id}


@app.on_event("startup")
async def on_startup():
    logger.info("handoff_starting")
    init_redis(settings.redis_url)


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name}
