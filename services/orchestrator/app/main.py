"""
Orchestrator — FastAPI entry point.
Puerto: 8001 — Servicio central del sistema.
"""
import asyncio
import time
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

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

app = FastAPI(
    title="NIA Orchestrator",
    description="Central conversation orchestrator: intent detection, FSM routing, RAG, recommendations and handoff.",
    version="1.0.0",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID", "X-Session-ID"],
)

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

    model_config = {"json_schema_extra": {"example": {"message": "¿Cuál es el horario de la viña?"}}}


class LeadSubmitRequest(BaseModel):
    lead_data: dict
    gdpr_consent: bool = False

    model_config = {"json_schema_extra": {"example": {
        "lead_data": {"full_name": "María García", "email": "maria@example.com"},
        "gdpr_consent": True,
    }}}


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


class SessionStateResponse(BaseModel):
    session_id: str
    tenant_id: str
    fsm_state: str
    messages_count: int
    lead_captured: bool
    last_intent: str | None = None
    tokens_used: int = 0


# ─────────────────────────────────────────────────────────────────
# Helper: obtener tenant config
# ─────────────────────────────────────────────────────────────────

async def _get_tenant_config(tenant_id: str, settings: OrchestratorSettings) -> dict:
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
    tags=["chat"],
)
@limiter.limit("60/minute")
async def chat(
    request: Request,
    body: ChatRequest,
    ctx: TenantCtx,
) -> APIResponse[ChatResponse]:
    """
    Main chat endpoint. Authenticated with a widget JWT (`Authorization: Bearer <token>`).

    The JWT is issued by the tenant-manager via `POST /api/tenants/{tenant_id}/widget-token`
    and encodes the `session_id` and `tenant_id` — no need to pass them in the body.
    """
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

    return APIResponse(data=ChatResponse(
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
    ))


@app.post(
    "/v1/sessions/{session_id}/lead",
    response_model=APIResponse[dict],
    summary="Submit lead capture form",
    tags=["chat"],
)
async def submit_lead(
    session_id: str,
    body: LeadSubmitRequest,
    ctx: TenantCtx,
) -> APIResponse[dict]:
    """
    Submit the lead capture form for the current session.
    Called by the widget after the user fills in their contact data.
    The JWT session_id is used as the canonical session identity.
    """
    canonical_sid = ctx.session_id
    session = await get_or_create_session(ctx.tenant_id, canonical_sid)
    session.lead_captured = True
    session.metadata = session.metadata or {}
    session.metadata["lead_data"] = body.lead_data
    session.metadata["gdpr_consent"] = body.gdpr_consent
    await transition_state(session, ConversationFSMState.GREETING)

    async def _persist_lead():
        lead_data = body.lead_data
        payload = {
            "tenant_id": ctx.tenant_id,
            "session_id": canonical_sid,
            "name": lead_data.get("full_name", "") or lead_data.get("name", ""),
            "email": lead_data.get("email", ""),
            "phone": lead_data.get("phone"),
            "intent_data": {k: v for k, v in lead_data.items()
                            if k not in ("name", "full_name", "email", "phone")},
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

    asyncio.create_task(_persist_lead())

    return APIResponse(data={"status": "lead_captured", "session_id": canonical_sid})


@app.get(
    "/v1/sessions/{session_id}",
    response_model=APIResponse[SessionStateResponse],
    summary="Get current session state",
    tags=["chat"],
)
async def get_session(session_id: str, ctx: TenantCtx) -> APIResponse[SessionStateResponse]:
    """Returns the FSM state and metadata for the current session."""
    session = await load_session(ctx.tenant_id, ctx.session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return APIResponse(data=SessionStateResponse(
        session_id=session.session_id,
        tenant_id=session.tenant_id,
        fsm_state=session.fsm_state.value if hasattr(session.fsm_state, "value") else str(session.fsm_state),
        messages_count=session.messages_count,
        lead_captured=session.lead_captured,
        last_intent=session.last_intent,
        tokens_used=session.tokens_used,
    ))


@app.on_event("startup")
async def on_startup():
    logger.info("orchestrator_starting")
    init_redis(settings.redis_url)
    logger.info("orchestrator_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()
    logger.info("orchestrator_shutdown")
