"""
Telegram Gateway — NIA channel adapter para Telegram Bot API.
Puerto: 8010

Flujo por mensaje entrante:
  1. Telegram → POST /webhook/{tenant_id}  (validado con webhook_secret)
  2. Gateway obtiene config del tenant (bot_token, jwt_secret) desde tenant-manager
  3. Genera JWT de sesión a partir del chat_id
  4. Llama al orchestrator POST /v1/chat con el mensaje
  5. Formatea la respuesta y la envía de vuelta via Telegram Bot API

Endpoints:
  POST /webhook/{tenant_id}              — webhook de Telegram
  POST /setup/{tenant_id}               — registra el webhook en Telegram
  GET  /health                           — health check
"""

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.formatter import build_reply_payload
from app.session import chat_id_to_session_id, create_channel_token
from app.settings import get_settings
from shared.db.redis_client import RedisKeys, get_redis, init_redis, close_redis
from shared.utils.health import build_health_router
from shared.utils.logging import get_logger, setup_logging

settings = get_settings()
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_logs=settings.json_logs,
)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA Telegram Gateway",
    description="Canal Telegram para NIA — convierte mensajes de Telegram al formato interno del orchestrator.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(build_health_router(
    service_name=settings.service_name,
    check_redis=False,
    check_postgres=False,
))


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - t0) * 1000))
    return response


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

async def _get_tenant_telegram_config(tenant_id: str) -> dict:
    """
    Obtiene la configuración del tenant desde Redis (caché) o tenant-manager.
    Devuelve el dict de telegram_config + jwt_secret del tenant.
    """
    # Intentar leer desde Redis directamente (incluye jwt_secret)
    redis = await get_redis()
    raw = await redis.get(RedisKeys.tenant_config(tenant_id))
    if raw:
        data = json.loads(raw)
    else:
        # Fallback: pedir al tenant-manager que recargue la caché
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                f"{settings.tenant_manager_url}/api/tenants/{tenant_id}/config"
            )
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
            resp.raise_for_status()
        # Leer de Redis ahora que la caché está poblada
        raw = await redis.get(RedisKeys.tenant_config(tenant_id))
        data = json.loads(raw) if raw else {}

    telegram_cfg = data.get("telegram_config", {})
    if not telegram_cfg.get("enabled"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Telegram channel not enabled for this tenant",
        )
    return {
        "bot_token":        telegram_cfg.get("bot_token", ""),
        "webhook_secret":   telegram_cfg.get("webhook_secret", ""),
        "allowed_chat_ids": telegram_cfg.get("allowed_chat_ids", []),
        "welcome_message":  telegram_cfg.get("welcome_message", "¡Hola! 👋 ¿En qué puedo ayudarte hoy?"),
        "parse_mode":       telegram_cfg.get("parse_mode", "Markdown"),
        "jwt_secret":       data.get("jwt_secret", settings.jwt_secret.get_secret_value()),
    }


def _verify_telegram_signature(body: bytes, secret_token: str, header_token: str) -> bool:
    """
    Verifica X-Telegram-Bot-Api-Secret-Token enviado por Telegram.
    Si no hay secret configurado, acepta el request (modo desarrollo).
    """
    if not secret_token:
        return True
    return hmac.compare_digest(header_token or "", secret_token)


async def _send_telegram_message(bot_token: str, method: str, payload: dict) -> None:
    """Llama a la Bot API de Telegram."""
    url = f"https://api.telegram.org/bot{bot_token}/{method}"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(url, json=payload)
        if not resp.is_success:
            logger.warning(
                "telegram_send_failed",
                method=method,
                status=resp.status_code,
                body=resp.text[:200],
            )


async def _ensure_lead_captured(tenant_id: str, session_id: str, chat_id: int) -> None:
    """
    En el canal Telegram no hay formulario de lead — el propio chat_id actúa
    como identificador del usuario.  Garantiza que la sesión en Redis tenga
    lead_captured=True antes de que el orchestrator la procese, para que el
    FSM no bloquee en pre_chat.

    - Sesión nueva   → la crea en Redis con lead_captured=True desde el inicio.
    - Sesión existente con lead_captured=False → la corrige + resetea a IDLE.
    - Sesión ya capturada → no-op.
    """
    redis = await get_redis()
    key = RedisKeys.session(tenant_id, session_id)
    raw = await redis.get(key)

    now_iso = datetime.now(UTC).isoformat()
    telegram_meta = {
        "channel": "telegram",
        "telegram_chat_id": str(chat_id),
        "lead_auto_captured_at": now_iso,
    }

    if not raw:
        # Sesión nueva — pre-crearla con lead ya capturado
        session = {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "fsm_state": "idle",
            "lead_id": f"tg_{chat_id}",
            "lead_captured": True,
            "user_profile_id": None,
            "messages_count": 0,
            "tokens_used": 0,
            "estimated_cost_usd": 0.0,
            "last_intent": None,
            "last_entities": {},
            "last_recommendations": [],
            "recommendation_context_id": None,
            "booking_intent_id": None,
            "checkout_session_id": None,
            "handoff_case_id": None,
            "previous_fsm_state": None,
            "page_url": None,
            "user_agent": None,
            "conversation_history": [],
            "nps_score": None,
            "metadata": telegram_meta,
            "started_at": now_iso,
            "last_active_at": now_iso,
        }
        await redis.setex(key, 28800, json.dumps(session))  # 8 h TTL
        logger.info(
            "telegram_session_precreated",
            tenant_id=tenant_id,
            session_id=session_id,
            chat_id=chat_id,
        )
        return

    session = json.loads(raw)
    if session.get("lead_captured"):
        return  # ya capturado, nada que hacer

    # Sesión existente sin lead capturado → corregir
    session["lead_captured"] = True
    session["lead_id"] = f"tg_{chat_id}"
    session["fsm_state"] = "idle"                  # resetear para que el FSM
    session["previous_fsm_state"] = "pre_chat"     # evalúe desde cero
    session["metadata"] = session.get("metadata", {}) | telegram_meta
    session["last_active_at"] = now_iso

    # Limpiar el historial contaminado con respuestas del estado pre_chat
    _discovery_fallback = (
        "Entiendo. ¿Puedes darme más detalles? Por ejemplo, ¿qué tipo de actividad buscas, "
        "para cuántas personas y en qué fecha?"
    )
    session["conversation_history"] = [
        turn for turn in session.get("conversation_history", [])
        if turn.get("content") != _discovery_fallback
    ]

    ttl = await redis.ttl(key)
    ttl = ttl if ttl and ttl > 0 else 28800
    await redis.setex(key, ttl, json.dumps(session))

    logger.info(
        "telegram_lead_auto_captured",
        tenant_id=tenant_id,
        session_id=session_id,
        chat_id=chat_id,
    )


async def _call_orchestrator(
    token: str,
    message: str,
    session_id: str,
) -> dict:
    """Envía el mensaje al orchestrator y devuelve la respuesta."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{settings.orchestrator_url}/v1/chat",
            json={"message": message},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json().get("data", {})


# ─────────────────────────────────────────────────────────────────
# Webhook — punto de entrada de mensajes de Telegram
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/webhook/{tenant_id}",
    status_code=status.HTTP_200_OK,
    summary="Recibe actualizaciones de Telegram para un tenant",
)
async def telegram_webhook(tenant_id: str, request: Request):
    """
    Endpoint llamado por los servidores de Telegram cuando llega un mensaje.
    Telegram espera siempre HTTP 200 — los errores se loguean pero no se propagan.
    """
    body = await request.body()
    update = await request.json()

    # ── Obtener config del tenant ──
    try:
        cfg = await _get_tenant_telegram_config(tenant_id)
    except HTTPException as exc:
        logger.warning("webhook_tenant_error", tenant_id=tenant_id, detail=exc.detail)
        return JSONResponse({"ok": True})  # Siempre 200 a Telegram

    # ── Verificar firma ──
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not _verify_telegram_signature(body, cfg["webhook_secret"], header_secret):
        logger.warning("webhook_invalid_signature", tenant_id=tenant_id)
        return JSONResponse({"ok": True})

    # ── Procesar mensaje de texto ──
    message = update.get("message") or update.get("edited_message")
    callback = update.get("callback_query")

    if callback:
        # Responder a botón inline pulsado
        chat_id = callback["message"]["chat"]["id"]
        data = callback.get("data", "")
        text = f"Seleccionaste: {data.split(':')[-1]}" if ":" in data else data
        await _process_message(tenant_id, chat_id, text, cfg)
        return JSONResponse({"ok": True})

    if not message:
        return JSONResponse({"ok": True})  # Ignorar actualizaciones sin mensaje

    chat_id: int = message["chat"]["id"]
    text: str = message.get("text", "")

    # ── Lista blanca ──
    allowed = cfg["allowed_chat_ids"]
    if allowed and chat_id not in allowed:
        logger.info("chat_id_not_allowed", chat_id=chat_id, tenant_id=tenant_id)
        return JSONResponse({"ok": True})

    # ── Comando /start ──
    if text.strip() == "/start":
        await _send_telegram_message(cfg["bot_token"], "sendMessage", {
            "chat_id": chat_id,
            "text": cfg["welcome_message"],
            "parse_mode": cfg["parse_mode"],
        })
        return JSONResponse({"ok": True})

    # ── Mensaje normal → orchestrator ──
    if text:
        await _process_message(tenant_id, chat_id, text, cfg)

    return JSONResponse({"ok": True})


async def _process_message(tenant_id: str, chat_id: int, text: str, cfg: dict) -> None:
    """
    Pipeline completo: texto → orchestrator → respuesta formateada → Telegram.
    """
    jwt_secret = cfg["jwt_secret"]
    token, session_id = create_channel_token(
        chat_id=chat_id,
        tenant_id=tenant_id,
        jwt_secret=jwt_secret,
    )

    logger.info(
        "telegram_message_received",
        tenant_id=tenant_id,
        chat_id=chat_id,
        session_id=session_id,
        text_len=len(text),
    )

    # Marcar lead como capturado antes de llamar al orchestrator.
    # En Telegram no hay formulario de lead — el chat_id es suficiente
    # como identificador del usuario.  Esto desbloquea el FSM del estado
    # pre_chat y permite que el orchestrator use el flujo RAG completo.
    await _ensure_lead_captured(tenant_id, session_id, chat_id)

    try:
        nia_response = await _call_orchestrator(token, text, session_id)
    except Exception as exc:
        logger.error("orchestrator_error", error=str(exc), tenant_id=tenant_id)
        await _send_telegram_message(cfg["bot_token"], "sendMessage", {
            "chat_id": chat_id,
            "text": "Lo siento, ocurrió un error. Por favor intenta de nuevo en unos segundos.",
        })
        return

    payloads = build_reply_payload(chat_id, nia_response, cfg["parse_mode"])
    for msg in payloads:
        await _send_telegram_message(cfg["bot_token"], msg["method"], msg["payload"])

    logger.info(
        "telegram_response_sent",
        tenant_id=tenant_id,
        chat_id=chat_id,
        fsm_state=nia_response.get("fsm_state"),
    )


# ─────────────────────────────────────────────────────────────────
# Setup — registra el webhook en Telegram
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/setup/{tenant_id}",
    summary="Registra el webhook de este tenant en la API de Telegram",
)
async def setup_webhook(tenant_id: str, request: Request):
    """
    Llama a setWebhook en la Bot API de Telegram apuntando a esta instancia.

    Body (opcional):
    ```json
    { "public_url": "https://mi-servidor.com" }
    ```
    Si no se pasa, usa la variable de entorno PUBLIC_URL del gateway.
    """
    body = await request.json() if request.headers.get("content-type") == "application/json" else {}

    cfg = await _get_tenant_telegram_config(tenant_id)
    bot_token = cfg["bot_token"]

    if not bot_token:
        raise HTTPException(status_code=400, detail="bot_token not configured for this tenant")

    import os
    public_url = body.get("public_url") or os.getenv("PUBLIC_URL", "")
    if not public_url:
        raise HTTPException(
            status_code=400,
            detail="public_url required — pasa {\"public_url\": \"https://...\"} en el body o configura PUBLIC_URL env var",
        )

    webhook_url = f"{public_url.rstrip('/')}/webhook/{tenant_id}"
    payload: dict = {"url": webhook_url}
    if cfg["webhook_secret"]:
        payload["secret_token"] = cfg["webhook_secret"]

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json=payload,
        )
        result = resp.json()

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram API error: {result.get('description')}")

    logger.info("webhook_registered", tenant_id=tenant_id, url=webhook_url)
    return {
        "ok": True,
        "webhook_url": webhook_url,
        "telegram_response": result,
    }


# ─────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    init_redis(settings.redis_url)
    logger.info("telegram_gateway_starting", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()
    logger.info("telegram_gateway_shutdown")
