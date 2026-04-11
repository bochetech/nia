"""
Orchestrator — FastAPI entry point.
Puerto: 8001 — Servicio central del sistema.
"""
from __future__ import annotations

import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from app.fsm import process_message
from app.session import get_or_create_session, load_session, transition_state
from app.settings import OrchestratorSettings, get_settings
from shared.db.redis_client import close_redis, init_redis
from shared.models.domain import ConversationFSMState
from shared.security.tenant import TenantCtx
from shared.utils.health import build_health_router
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse

settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

# ─── Rate limiter ────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="NIA Orchestrator", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID", "X-Session-ID"],
)

# Health checks (Redis)
app.include_router(build_health_router(
    service_name=settings.service_name,
    check_redis=True,
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
# Schemas
# ─────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    stream: bool = False


class LeadSubmitRequest(BaseModel):
    data: dict
    gdpr_consent: bool = False


class ChatResponse(BaseModel):
    session_id: str
    tenant_id: str
    response: str
    fsm_state: str
    show_lead_form: bool = False
    recommendations: list | None = None
    handoff_triggered: bool = False
    checkout_url: str | None = None
    tokens_used: int = 0


# ─────────────────────────────────────────────────────────────────
# Helper: obtener tenant config
# ─────────────────────────────────────────────────────────────────

async def _get_tenant_config(tenant_id: str, settings: OrchestratorSettings) -> dict:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.tenant_manager_url}/api/tenants/{tenant_id}/config")
            resp.raise_for_status()
            return resp.json()["data"]
    except Exception as exc:
        logger.error("tenant_config_fetch_failed", tenant_id=tenant_id, error=str(exc))
        return {}


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/v1/chat",
    response_model=APIResponse[ChatResponse],
    summary="Send a message in a conversation session",
)
@limiter.limit("60/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    ctx: TenantCtx,
) -> APIResponse[ChatResponse]:
    tenant_id = ctx.tenant_id
    session_id = ctx.session_id

    if not body.message.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message cannot be empty",
        )

    tenant_config = await _get_tenant_config(tenant_id, settings)

    result = await process_message(
        message=body.message,
        tenant_id=tenant_id,
        session_id=session_id,
        tenant_config=tenant_config,
        settings=settings,
    )

    response_data = ChatResponse(
        session_id=session_id,
        tenant_id=tenant_id,
        response=result.response_text,
        fsm_state=result.new_state.value,
        show_lead_form=result.show_lead_form,
        recommendations=(
            [r.model_dump() for r in result.recommendations.recommendations]
            if result.recommendations
            else None
        ),
        handoff_triggered=result.handoff_triggered,
        checkout_url=result.checkout_url,
        tokens_used=result.session.tokens_used,
    )

    return APIResponse(data=response_data)


@app.post(
    "/v1/chat/stream",
    summary="Send a message with SSE streaming response",
)
@limiter.limit("60/minute")
async def chat_stream(
    request: Request,
    body: ChatRequest,
    ctx: TenantCtx,
):
    """Streaming via Server-Sent Events."""
    tenant_id = ctx.tenant_id
    session_id = ctx.session_id
    tenant_config = await _get_tenant_config(tenant_id, settings)

    async def event_generator():
        try:
            result = await process_message(
                message=body.message,
                tenant_id=tenant_id,
                session_id=session_id,
                tenant_config=tenant_config,
                settings=settings,
            )
            # Simular streaming char-by-char de la respuesta
            import asyncio
            for char in result.response_text:
                yield {"data": char}
                await asyncio.sleep(0.01)
            yield {"event": "done", "data": result.new_state.value}
        except Exception as exc:
            logger.error("stream_error", error=str(exc))
            yield {"event": "error", "data": str(exc)}

    return EventSourceResponse(event_generator())


@app.post(
    "/v1/sessions/{session_id}/lead",
    response_model=APIResponse[dict],
    summary="Submit lead capture form",
)
async def submit_lead(
    session_id: str,
    body: LeadSubmitRequest,
    ctx: TenantCtx,
) -> APIResponse[dict]:
    import httpx

    session = await get_or_create_session(ctx.tenant_id, session_id)
    session.lead_captured = True
    session.metadata = session.metadata or {}
    session.metadata["lead_data"] = body.data
    session.metadata["gdpr_consent"] = body.gdpr_consent
    await transition_state(session, ConversationFSMState.GREETING)

    # Persistir lead en DB via transcript service (fire-and-forget)
    lead_data = body.data
    async def _persist_lead():
        payload = {
            "tenant_id": ctx.tenant_id,
            "session_id": session_id,
            "name": lead_data.get("name", ""),
            "email": lead_data.get("email", ""),
            "phone": lead_data.get("phone"),
            "intent_data": {k: v for k, v in lead_data.items()
                            if k not in ("name", "email", "phone")},
            "gdpr_consent": body.gdpr_consent,
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{settings.transcript_url}/v1/leads",
                    json=payload,
                )
                if resp.status_code not in (200, 201):
                    logger.error("lead_persist_failed", status=resp.status_code,
                                 tenant_id=ctx.tenant_id)
                else:
                    logger.info("lead_persisted", tenant_id=ctx.tenant_id,
                                email=lead_data.get("email"))
        except Exception as exc:
            logger.error("lead_persist_exception", error=str(exc))

    import asyncio
    asyncio.create_task(_persist_lead())

    return APIResponse(data={"status": "lead_captured", "session_id": session_id})


@app.get(
    "/v1/sessions/{session_id}",
    response_model=APIResponse[dict],
    summary="Get current session state",
)
async def get_session(session_id: str, ctx: TenantCtx) -> APIResponse[dict]:
    session = await load_session(ctx.tenant_id, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return APIResponse(data=session.model_dump())


@app.on_event("startup")
async def on_startup():
    logger.info("orchestrator_starting")
    await init_redis(settings.redis_url)
    logger.info("orchestrator_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()
    logger.info("orchestrator_shutdown")


@app.get("/health", tags=["ops"])
async def health():
    return JSONResponse(content={"status": "healthy", "service": settings.service_name})