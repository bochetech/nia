"""
Handoff Service — gestiona transferencia bot → agente humano vía Teams y Chatwoot.
Puerto: 8007
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import FastAPI, Header, HTTPException, Request, status
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

app = FastAPI(
    title="NIA Handoff Service",
    description=(
        "**[Essential Infrastructure]** Manages bot-to-human handoff — creates cases, "
        "notifies agents via Microsoft Teams Adaptive Cards, pauses the bot, and "
        "resumes conversation once the agent resolves the case."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "handoff",
            "description": "Handoff case lifecycle: create, status and resolve.",
        },
        {
            "name": "ops",
            "description": "Health and readiness probes.",
        },
    ],
)
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
    summary="Create a new handoff case",
    tags=["handoff"],
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


@app.get(
    "/v1/handoff/cases/{case_id}",
    response_model=APIResponse[HandoffStatusResponse],
    summary="Get handoff case status",
    tags=["handoff"],
)
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


@app.post(
    "/v1/handoff/cases/{case_id}/resolve",
    summary="Resolve a handoff case and resume the bot",
    tags=["handoff"],
)
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


# ─────────────────────────────────────────────────────────────────
# Chatwoot Webhook — incoming messages from Chatwoot inboxes
# ─────────────────────────────────────────────────────────────────

CHATWOOT_TENANT_MANAGER_URL = "http://tenant-manager:8003"
ORCHESTRATOR_URL = "http://orchestrator:8001"


class ChatwootWebhookPayload(BaseModel):
    """
    Subset of the Chatwoot webhook payload that NIA needs.
    Chatwoot sends a rich JSON — we only parse what we care about.
    Full spec: https://www.chatwoot.com/docs/product/channels/api/send-messages
    """
    model_config = {"extra": "ignore"}

    event: str
    id: int | None = None
    content: str | None = None
    message_type: str | int | None = None  # 0/"incoming" = user, 1/"outgoing" = bot/agent, 2="activity"
    conversation: dict | None = None
    contact: dict | None = None
    account: dict | None = None

    def is_incoming(self) -> bool:
        """Returns True if the message is from the user (not bot/agent/activity)."""
        return self.message_type in (0, "incoming")


def _verify_chatwoot_hmac(body: bytes, secret: str, signature: str | None) -> bool:
    """Verifica HMAC-SHA256 del webhook de Chatwoot (header X-Chatwoot-Signature)."""
    if not secret:
        return True  # Si no hay secret configurado, se acepta (dev mode)
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _get_chatwoot_config(tenant_id: str) -> dict | None:
    """Obtiene la configuración Chatwoot del tenant desde tenant-manager."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"{CHATWOOT_TENANT_MANAGER_URL}/api/tenants/{tenant_id}/config",
                headers={"X-Internal-Service": "handoff"},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            return data.get("data", {}).get("chatwoot_config")
    except Exception:
        return None


async def _send_chatwoot_message(
    instance_url: str,
    api_token: str,
    account_id: int,
    conversation_id: int,
    message: str,
    message_type: str = "outgoing",
) -> None:
    """Envía un mensaje de respuesta a Chatwoot vía su API REST."""
    # Rewrite localhost → host.docker.internal so the request works from inside Docker
    internal_url = instance_url.replace("localhost", "host.docker.internal")
    url = f"{internal_url}/api/v1/accounts/{account_id}/conversations/{conversation_id}/messages"
    payload = {
        "content": message,
        "message_type": message_type,
        "private": False,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={
                "api_access_token": api_token,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()


async def _get_widget_token(tenant_id: str, session_id: str) -> str | None:
    """Obtiene un JWT de widget desde tenant-manager para autenticar llamadas al orquestador."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                f"{CHATWOOT_TENANT_MANAGER_URL}/api/tenants/{tenant_id}/widget-token",
                json={"session_id": session_id},
                headers={"X-Internal-Service": "handoff"},
            )
            if resp.status_code == 200:
                return resp.json().get("data", {}).get("token")
    except Exception:
        pass
    return None


async def _call_orchestrator(tenant_id: str, session_id: str, message: str) -> str:
    """Envía el mensaje al orquestador NIA y devuelve la respuesta del bot."""
    try:
        token = await _get_widget_token(tenant_id, session_id)
        headers: dict = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{ORCHESTRATOR_URL}/v1/chat",
                json={
                    "tenant_id": tenant_id,
                    "session_id": session_id,
                    "message": message,
                },
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {}).get("response", "")
    except Exception as exc:
        logger.warning("orchestrator_call_failed", error=str(exc))
        return "Lo siento, hubo un problema procesando tu mensaje. Por favor intenta de nuevo."


@app.post(
    "/webhooks/chatwoot/{tenant_id}",
    summary="Receive incoming Chatwoot webhook events",
    tags=["chatwoot"],
)
async def chatwoot_webhook(
    tenant_id: str,
    request: Request,
    x_chatwoot_signature: str | None = Header(default=None, alias="X-Chatwoot-Signature"),
) -> dict:
    """
    Endpoint que Chatwoot llama para cada evento del inbox del bot.
    """
    logger.info("chatwoot_webhook_received", tenant_id=tenant_id, method=request.method)
    body = await request.body()

    # ── Obtener config del tenant ──────────────────────────────
    cw_cfg = await _get_chatwoot_config(tenant_id)
    if not cw_cfg or not cw_cfg.get("enabled"):
        logger.warning("chatwoot_webhook_tenant_not_found_or_disabled", tenant_id=tenant_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chatwoot not enabled for this tenant")

    # ── Verificar firma HMAC ───────────────────────────────────
    if not _verify_chatwoot_hmac(body, cw_cfg.get("webhook_hmac_token", ""), x_chatwoot_signature):
        logger.warning("chatwoot_webhook_invalid_signature", tenant_id=tenant_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook signature")

    # ── Parsear payload ────────────────────────────────────────
    try:
        raw_body = json.loads(body)
        logger.info("chatwoot_webhook_raw", tenant_id=tenant_id, cw_event=raw_body.get("event"), msg_type=raw_body.get("message_type"), content=str(raw_body.get("content",""))[:100])
        payload = ChatwootWebhookPayload(**raw_body)
    except Exception as exc:
        logger.warning("chatwoot_webhook_parse_error", error=str(exc), body=body[:200].decode(errors="replace"))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payload")

    # Solo procesar mensajes entrantes del usuario (message_type == 0)
    if payload.event != "message_created" or not payload.is_incoming():
        return {"status": "ignored", "reason": "not_user_message"}

    content = (payload.content or "").strip()
    if not content:
        return {"status": "ignored", "reason": "empty_message"}

    # ── Extraer IDs relevantes ─────────────────────────────────
    conversation_id: int = (payload.conversation or {}).get("id", 0)
    contact_id: int | str = str((payload.contact or {}).get("id", ""))
    if not conversation_id:
        return {"status": "ignored", "reason": "no_conversation_id"}

    # Usamos el conversation_id de Chatwoot como session_id en NIA
    # para mantener contexto por conversación
    session_id = f"cw_{tenant_id}_{conversation_id}"

    # ── Comprobar si hay handoff activo (bot en pausa) ─────────
    redis = await get_redis()
    handoff_lock = await redis.get(RedisKeys.handoff_lock(session_id))
    if handoff_lock:
        logger.info(
            "chatwoot_webhook_handoff_active_skipped",
            tenant_id=tenant_id,
            session_id=session_id,
        )
        return {"status": "ignored", "reason": "handoff_active"}

    # ── Llamar al orquestador ──────────────────────────────────
    logger.info(
        "chatwoot_webhook_processing",
        tenant_id=tenant_id,
        session_id=session_id,
        conversation_id=conversation_id,
    )

    bot_response = await _call_orchestrator(tenant_id, session_id, content)

    # ── Responder en Chatwoot ──────────────────────────────────
    try:
        await _send_chatwoot_message(
            instance_url=cw_cfg["instance_url"],
            api_token=cw_cfg["api_access_token"],
            account_id=cw_cfg["account_id"],
            conversation_id=conversation_id,
            message=bot_response,
        )
    except Exception as exc:
        logger.error(
            "chatwoot_send_message_failed",
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            error=str(exc),
        )
        # No fallar el webhook — Chatwoot haría retry y causaría duplicados

    return {"status": "ok", "session_id": session_id}


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": settings.service_name}
