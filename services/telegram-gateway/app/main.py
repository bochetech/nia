"""
Telegram Gateway — NIA channel adapter para Telegram Bot API.
Puerto: 8010

Flujo por mensaje entrante:
  1. Telegram → POST /webhook/{tenant_id}  (validado con webhook_secret)
  2. Gateway obtiene config del tenant (bot_token, jwt_secret) desde tenant-manager
  3. Genera JWT de sesión a partir del chat_id
  4. Llama al orchestrator POST /v1/chat con el mensaje
  5. Formatea la respuesta y la envía de vuelta via Telegram Bot API

Comandos especiales:
  /start             — bienvenida y descripción del asistente
  /tenant            — lista todos los tenants disponibles con botones inline
  /tenant <id>       — cambia directamente al tenant especificado
  /reset             — reinicia la conversación (nueva sesión)

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
    description=(
        "**[Channel]** Telegram Bot API adapter for NIA. "
        "Receives Telegram webhook events, translates them to the orchestrator's internal format, "
        "and sends formatted replies back to users. "
        "Supports multi-tenant switching (`/tenant`), session reset (`/reset`) and "
        "persistent tenant preferences in Redis."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "webhook",
            "description": "Telegram update ingestion and message processing.",
        },
        {
            "name": "setup",
            "description": "Register and manage Telegram webhooks for tenants.",
        },
        {
            "name": "ops",
            "description": "Health and readiness probes.",
        },
    ],
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


def _tenant_display_name(data: dict) -> str:
    """
    Extrae el nombre para mostrar de un dict de configuración de tenant.
    La estructura en Redis usa 'tenant_id' (no 'id') y guarda el nombre
    en ui_config.chat_title (no en un campo 'name' top-level).
    Fallback chain: chat_title → header_title → tenant_id
    """
    ui = data.get("ui_config", {}) or {}
    return (
        ui.get("chat_title")
        or ui.get("header_title")
        or data.get("name")
        or data.get("tenant_id")
        or data.get("id", "")
    )


async def _get_available_tenants() -> list[dict]:
    """
    Obtiene la lista de tenants activos con Telegram habilitado desde Redis.
    Busca todas las claves tenant:*:config y filtra los que tienen telegram_config.enabled=True.
    """
    redis = await get_redis()
    keys = await redis.keys("tenant:*:config")
    tenants = []
    for key in keys:
        try:
            raw = await redis.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            telegram_cfg = data.get("telegram_config", {})
            if telegram_cfg.get("enabled"):
                tid = data.get("tenant_id") or data.get("id", "")
                tenants.append({
                    "id": tid,
                    "name": _tenant_display_name(data),
                    "title": _tenant_display_name(data),
                    "welcome": data.get("ui_config", {}).get("welcome_message", ""),
                })
        except Exception:
            continue
    return tenants


async def _handle_tenant_command(
    tenant_id: str,
    chat_id: int,
    text: str,
    cfg: dict,
) -> None:
    """
    Maneja el comando /tenant:
    - /tenant          → muestra lista de tenants con botones inline
    - /tenant <id>     → cambia al tenant especificado directamente
    """
    bot_token = cfg["bot_token"]
    parse_mode = cfg["parse_mode"]

    parts = text.strip().split(maxsplit=1)
    target_id = parts[1].strip() if len(parts) > 1 else ""

    if target_id:
        # Cambio directo: /tenant moda_imagen
        await _switch_tenant(chat_id, tenant_id, target_id, bot_token, parse_mode)
        return

    # Sin argumento → mostrar menú
    tenants = await _get_available_tenants()

    if not tenants:
        await _send_telegram_message(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": "⚠️ No hay asistentes disponibles en este momento.",
            "parse_mode": parse_mode,
        })
        return

    # Construir botones inline
    buttons = []
    for t in tenants:
        mark = "✅ " if t["id"] == tenant_id else ""
        buttons.append([{
            "text": f"{mark}{t['title']}",
            "callback_data": f"switch_tenant:{t['id']}",
        }])

    tenant_list = "\n".join(
        f"{'▶️' if t['id'] == tenant_id else '·'} *{t['title']}* `{t['id']}`"
        for t in tenants
    )
    msg = (
        f"🤖 *Asistentes disponibles*\n\n"
        f"{tenant_list}\n\n"
        f"Selecciona uno para cambiar de asistente:"
    )

    await _send_telegram_message(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": msg,
        "parse_mode": parse_mode,
        "reply_markup": {"inline_keyboard": buttons},
    })
    logger.info("tenant_menu_shown", chat_id=chat_id, current=tenant_id, options=len(tenants))


async def _switch_tenant(
    chat_id: int,
    current_tenant_id: str,
    target_tenant_id: str,
    bot_token: str,
    parse_mode: str,
) -> None:
    """
    Cambia el tenant activo para un chat_id:
    1. Guarda la preferencia en Redis (clave: tg_tenant:{chat_id})
    2. Limpia la sesión anterior para empezar fresco
    3. Envía mensaje de confirmación con el welcome del nuevo tenant
    """
    if target_tenant_id == current_tenant_id:
        await _send_telegram_message(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"✅ Ya estás usando *{target_tenant_id}*.",
            "parse_mode": parse_mode,
        })
        return

    # Verificar que el target tenant existe y tiene Telegram habilitado
    redis = await get_redis()
    raw = await redis.get(f"tenant:{target_tenant_id}:config")
    if not raw:
        await _send_telegram_message(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"❌ El asistente `{target_tenant_id}` no existe o no está disponible.",
            "parse_mode": parse_mode,
        })
        return

    target_config = json.loads(raw)
    telegram_cfg = target_config.get("telegram_config", {})
    if not telegram_cfg.get("enabled"):
        await _send_telegram_message(bot_token, "sendMessage", {
            "chat_id": chat_id,
            "text": f"❌ El asistente `{target_tenant_id}` no tiene Telegram habilitado.",
            "parse_mode": parse_mode,
        })
        return

    # Guardar preferencia de tenant en Redis (TTL: 30 días)
    pref_key = f"tg_tenant_pref:{chat_id}"
    await redis.setex(pref_key, 30 * 24 * 3600, target_tenant_id)

    # Limpiar sesión anterior del tenant anterior
    old_session_id = chat_id_to_session_id(chat_id, current_tenant_id)
    old_session_key = RedisKeys.session(current_tenant_id, old_session_id)
    await redis.delete(old_session_key)

    # También limpiar lead lock si existe
    old_lead_key = f"lead_lock:{current_tenant_id}:{old_session_id}"
    await redis.delete(old_lead_key)

    target_name = _tenant_display_name(target_config)
    welcome = target_config.get("ui_config", {}).get("welcome_message", f"¡Hola! Soy el asistente de {target_name}.")

    confirm_msg = (
        f"🔄 *Cambiando a {target_name}*\n\n"
        f"{welcome}\n\n"
        f"_Conversación anterior cerrada. Empezamos de nuevo._"
    )
    await _send_telegram_message(bot_token, "sendMessage", {
        "chat_id": chat_id,
        "text": confirm_msg,
        "parse_mode": parse_mode,
    })
    logger.info("tenant_switched", chat_id=chat_id, from_tenant=current_tenant_id, to_tenant=target_tenant_id)


async def _get_preferred_tenant(chat_id: int, default_tenant_id: str) -> str:
    """Devuelve el tenant activo preferido para este chat_id, o el default."""
    redis = await get_redis()
    pref = await redis.get(f"tg_tenant_pref:{chat_id}")
    return pref.decode() if pref else default_tenant_id


async def _register_bot_commands(bot_token: str, tenant_name: str = "") -> bool:
    """
    Registra los comandos del bot en Telegram mediante setMyCommands.
    Esto hace que aparezcan en el menú '/' del cliente Telegram de forma nativa.
    Devuelve True si el registro fue exitoso.
    """
    name_hint = f" de {tenant_name}" if tenant_name else ""
    commands = [
        {
            "command": "start",
            "description": f"👋 Iniciar conversación con el asistente{name_hint}",
        },
        {
            "command": "tenant",
            "description": "🤖 Ver y cambiar de asistente disponible",
        },
        {
            "command": "reset",
            "description": "🔄 Reiniciar la conversación desde cero",
        },
    ]
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"https://api.telegram.org/bot{bot_token}/setMyCommands",
            json={"commands": commands},
        )
        result = resp.json()
    if result.get("ok"):
        logger.info("bot_commands_registered", tenant=tenant_name, count=len(commands))
    else:
        logger.warning(
            "bot_commands_register_failed",
            tenant=tenant_name,
            error=result.get("description"),
        )
    return bool(result.get("ok"))


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
    tags=["webhook"],
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

        # Manejar selección de tenant desde el menú /tenant
        if data.startswith("switch_tenant:"):
            target = data.split(":", 1)[1]
            await _switch_tenant(chat_id, tenant_id, target, cfg["bot_token"], cfg["parse_mode"])
            return JSONResponse({"ok": True})

        text = f"Seleccionaste: {data.split(':')[-1]}" if ":" in data else data
        active_tenant = await _get_preferred_tenant(chat_id, tenant_id)
        active_cfg = cfg if active_tenant == tenant_id else await _get_tenant_telegram_config(active_tenant)
        await _process_message(active_tenant, chat_id, text, active_cfg)
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

    # ── Determinar tenant activo (puede haber cambiado con /tenant) ──
    active_tenant = await _get_preferred_tenant(chat_id, tenant_id)
    if active_tenant != tenant_id:
        try:
            cfg = await _get_tenant_telegram_config(active_tenant)
        except HTTPException:
            # Si el tenant preferido ya no está disponible, limpiar preferencia
            redis = await get_redis()
            await redis.delete(f"tg_tenant_pref:{chat_id}")
            active_tenant = tenant_id
            logger.warning("preferred_tenant_unavailable", chat_id=chat_id, preferred=active_tenant)

    # ── Comando /start ──
    if text.strip() == "/start":
        await _send_telegram_message(cfg["bot_token"], "sendMessage", {
            "chat_id": chat_id,
            "text": cfg["welcome_message"],
            "parse_mode": cfg["parse_mode"],
        })
        return JSONResponse({"ok": True})

    # ── Comando /tenant ──
    if text.strip().startswith("/tenant"):
        await _handle_tenant_command(active_tenant, chat_id, text.strip(), cfg)
        return JSONResponse({"ok": True})

    # ── Comando /reset ──
    if text.strip() == "/reset":
        session_id = chat_id_to_session_id(chat_id, active_tenant)
        redis = await get_redis()
        await redis.delete(RedisKeys.session(active_tenant, session_id))
        await _send_telegram_message(cfg["bot_token"], "sendMessage", {
            "chat_id": chat_id,
            "text": "🔄 Conversación reiniciada. " + cfg["welcome_message"],
            "parse_mode": cfg["parse_mode"],
        })
        return JSONResponse({"ok": True})

    # ── Mensaje normal → orchestrator ──
    if text:
        await _process_message(active_tenant, chat_id, text, cfg)

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

    # Mostrar indicador "escribiendo…" mientras el orchestrator procesa.
    # Telegram lo mantiene visible ~5 s; si la respuesta tarda más se repetiría
    # automáticamente, pero en la práctica el LLM responde en < 5 s.
    await _send_telegram_message(cfg["bot_token"], "sendChatAction", {
        "chat_id": chat_id,
        "action": "typing",
    })

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
    tags=["setup"],
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

    # Registrar los comandos del bot (/start, /tenant, /reset) en el menú nativo de Telegram
    tenant_name = ""
    try:
        redis = await get_redis()
        raw = await redis.get(f"tenant:{tenant_id}:config")
        if raw:
            tenant_data = json.loads(raw)
            tenant_name = _tenant_display_name(tenant_data)
    except Exception:
        pass
    await _register_bot_commands(bot_token, tenant_name)

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

    # Registrar comandos automáticamente en todos los bots ya configurados en Redis.
    # Esto garantiza que el menú '/' aparezca incluso sin volver a llamar a /setup.
    try:
        redis = await get_redis()
        keys = await redis.keys("tenant:*:config")
        for key in keys:
            raw = await redis.get(key)
            if not raw:
                continue
            data = json.loads(raw)
            telegram_cfg = data.get("telegram_config", {})
            bot_token = telegram_cfg.get("bot_token", "")
            if telegram_cfg.get("enabled") and bot_token:
                tenant_name = _tenant_display_name(data)
                await _register_bot_commands(bot_token, tenant_name)
    except Exception as exc:
        logger.warning("startup_commands_register_failed", error=str(exc))


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()
    logger.info("telegram_gateway_shutdown")
