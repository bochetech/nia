"""
Transcript Service — persiste mensajes y conversaciones en PostgreSQL.
Puerto: 8008

Endpoints:
  POST /v1/transcripts/messages               — guarda un mensaje
  GET  /v1/transcripts/{tenant}/{session}      — historial completo
  POST /v1/transcripts/{tenant}/{session}/email — envía transcripción por email
  POST /v1/leads                               — persiste un lead en DB
"""

import time
import uuid
from datetime import UTC, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy import text

from shared.config.base import BaseServiceSettings
from shared.db.connection import close_db, get_db_session, init_db
from shared.db.redis_client import close_redis, init_redis
from shared.utils.health import build_health_router
from shared.utils.logging import get_logger, setup_logging


class TranscriptSettings(BaseServiceSettings):
    service_name: str = "transcript"
    port: int = 8008
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@nia-platform.com"
    smtp_use_tls: bool = True


_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = TranscriptSettings()  # type: ignore[call-arg]
    return _settings


settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

app = FastAPI(title="NIA Transcript Service", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(build_health_router(
    service_name=settings.service_name,
    check_redis=True,
    check_postgres=True,
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

class SaveMessageRequest(BaseModel):
    tenant_id: str
    session_id: str
    role: str
    content: str
    tokens: int = 0
    intent: str | None = None
    confidence: float | None = None
    rag_sources: list = []
    metadata: dict = {}


class EmailExportRequest(BaseModel):
    to_email: EmailStr
    subject: str = "Tu conversación con NIA"
    tenant_name: str = "NIA"


class LeadCreateRequest(BaseModel):
    tenant_id: str
    session_id: str
    name: str
    email: EmailStr
    phone: str | None = None
    intent_data: dict = {}
    gdpr_consent: bool = False


# ─────────────────────────────────────────────────────────────────
# Routes — Messages
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/transcripts/messages", status_code=status.HTTP_201_CREATED)
async def save_message(body: SaveMessageRequest) -> dict:
    """Persiste un mensaje en la tabla de mensajes del tenant."""
    schema = f"tenant_{body.tenant_id}"
    msg_id = str(uuid.uuid4())
    conv_id = _session_to_conv_id(body.session_id)

    async for db in get_db_session():
        try:
            await db.execute(
                text(f"""
                    INSERT INTO {schema}.conversations (id, session_id, messages_count)
                    VALUES (:id, :session_id, 0)
                    ON CONFLICT (session_id) DO UPDATE
                    SET messages_count = {schema}.conversations.messages_count + 1,
                        last_active_at = NOW()
                """),
                {"id": conv_id, "session_id": body.session_id},
            )
            await db.execute(
                text(f"""
                    INSERT INTO {schema}.messages
                        (id, conversation_id, role, content, tokens, intent, confidence,
                         rag_sources, metadata, created_at)
                    VALUES
                        (:id, :conv_id, :role, :content, :tokens, :intent, :confidence,
                         :rag_sources::jsonb, :metadata::jsonb, NOW())
                """),
                {
                    "id": msg_id,
                    "conv_id": conv_id,
                    "role": body.role,
                    "content": body.content,
                    "tokens": body.tokens,
                    "intent": body.intent,
                    "confidence": body.confidence,
                    "rag_sources": "[]",
                    "metadata": "{}",
                },
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("save_message_error", error=str(exc), schema=schema)
            raise HTTPException(status_code=500, detail=str(exc))

    return {"id": msg_id, "session_id": body.session_id}


@app.get("/v1/transcripts/{tenant_id}/{session_id}")
async def get_transcript(tenant_id: str, session_id: str) -> dict:
    """Obtiene el historial completo de una sesión."""
    schema = f"tenant_{tenant_id}"
    conv_id = _session_to_conv_id(session_id)

    async for db in get_db_session():
        result = await db.execute(
            text(f"""
                SELECT id, role, content, tokens, intent, confidence, created_at
                FROM {schema}.messages
                WHERE conversation_id = :conv_id
                ORDER BY created_at ASC
            """),
            {"conv_id": conv_id},
        )
        rows = result.mappings().all()
        messages = [dict(r) for r in rows]

    return {"session_id": session_id, "messages": messages, "count": len(messages)}


# ─────────────────────────────────────────────────────────────────
# Routes — Email export
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/transcripts/{tenant_id}/{session_id}/email")
async def export_transcript_email(
    tenant_id: str,
    session_id: str,
    body: EmailExportRequest,
) -> dict:
    """
    Genera HTML con la transcripción y lo envía por email.
    Sin SMTP configurado, devuelve el HTML en la respuesta (dev mode).
    """
    schema = f"tenant_{tenant_id}"
    conv_id = _session_to_conv_id(session_id)

    async for db in get_db_session():
        result = await db.execute(
            text(f"""
                SELECT role, content, intent, created_at
                FROM {schema}.messages
                WHERE conversation_id = :conv_id
                ORDER BY created_at ASC
            """),
            {"conv_id": conv_id},
        )
        rows = result.mappings().all()
        messages = [dict(r) for r in rows]

    if not messages:
        raise HTTPException(status_code=404, detail="No messages found for this session")

    html = _build_transcript_html(messages, session_id=session_id, tenant_name=body.tenant_name)

    if settings.smtp_host:
        await _send_email(to_email=body.to_email, subject=body.subject, html_body=html)
        return {"status": "sent", "to": body.to_email, "message_count": len(messages)}
    else:
        logger.warning("smtp_not_configured_returning_html", tenant_id=tenant_id)
        return {
            "status": "no_smtp",
            "message": "SMTP not configured. HTML returned in 'html' field.",
            "html": html,
            "message_count": len(messages),
        }


# ─────────────────────────────────────────────────────────────────
# Routes — Leads
# ─────────────────────────────────────────────────────────────────

@app.post("/v1/leads", status_code=status.HTTP_201_CREATED)
async def create_lead(body: LeadCreateRequest) -> dict:
    """Persiste un lead capturado en el formulario pre-chat."""
    import json as _json

    schema = f"tenant_{body.tenant_id}"
    conv_id = _session_to_conv_id(body.session_id)

    async for db in get_db_session():
        try:
            result = await db.execute(
                text(f"""
                    INSERT INTO {schema}.leads
                        (tenant_id, conversation_id, name, email, phone,
                         intent_data, gdpr_consent, source, created_at)
                    VALUES
                        (:tenant_id, :conv_id, :name, :email, :phone,
                         :intent_data::jsonb, :gdpr_consent, 'widget', NOW())
                    RETURNING id
                """),
                {
                    "tenant_id": body.tenant_id,
                    "conv_id": conv_id,
                    "name": body.name,
                    "email": body.email,
                    "phone": body.phone,
                    "intent_data": _json.dumps(body.intent_data),
                    "gdpr_consent": body.gdpr_consent,
                },
            )
            row = result.fetchone()
            await db.commit()
            lead_id = row[0] if row else None
        except Exception as exc:
            await db.rollback()
            logger.error("create_lead_error", error=str(exc))
            raise HTTPException(status_code=500, detail=str(exc))

    logger.info("lead_created", tenant_id=body.tenant_id, email=body.email)
    return {"id": lead_id, "session_id": body.session_id, "email": body.email}


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _session_to_conv_id(session_id: str) -> str:
    """Genera un conversation_id determinista desde session_id."""
    import hashlib
    h = hashlib.md5(session_id.encode()).hexdigest()
    return f"{h[:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def _build_transcript_html(messages: list[dict], *, session_id: str, tenant_name: str) -> str:
    """Genera HTML limpio y legible con la transcripción."""
    rows = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "").replace("\n", "<br>")
        ts = msg.get("created_at", "")
        if isinstance(ts, datetime):
            ts = ts.strftime("%H:%M")
        elif ts:
            ts = str(ts)[11:16]

        if role == "user":
            align, bg, label = "right", "#f0f4f8", "Tú"
        elif role == "assistant":
            align, bg, label = "left", "#fff3e0", tenant_name
        else:
            continue

        rows.append(f"""
        <tr>
          <td style="text-align:{align}; padding:8px 16px;">
            <div style="display:inline-block; background:{bg}; border-radius:8px;
                        padding:10px 14px; max-width:70%; font-size:14px; color:#1a202c;">
              <div style="font-size:11px; color:#718096; margin-bottom:4px;">{label} · {ts}</div>
              {content}
            </div>
          </td>
        </tr>""")

    body_rows = "\n".join(rows)
    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"/><title>Transcripción NIA</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
             background:#f7f8fa;margin:0;padding:32px;">
  <div style="max-width:680px;margin:0 auto;background:#fff;
              border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.08);">
    <div style="background:#5c1a1a;color:#fff;padding:24px 32px;">
      <h2 style="margin:0;font-size:20px;">{tenant_name} — Transcripción de conversación</h2>
      <p style="margin:4px 0 0;font-size:13px;opacity:0.7;">Sesión: {session_id[:16]}…</p>
    </div>
    <table style="width:100%;border-collapse:collapse;padding:16px;">
      {body_rows}
    </table>
    <div style="padding:20px 32px;border-top:1px solid #edf2f7;
                font-size:12px;color:#a0aec0;text-align:center;">
      Generado por NIA Platform · {datetime.now(UTC).strftime('%d/%m/%Y %H:%M')} UTC
    </div>
  </div>
</body>
</html>"""


async def _send_email(*, to_email: str, subject: str, html_body: str) -> None:
    """Envía email via aiosmtplib."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html"))
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_use_tls,
        )
        logger.info("email_sent", to=to_email)
    except Exception as exc:
        logger.error("email_send_failed", error=str(exc), to=to_email)
        raise HTTPException(status_code=502, detail=f"Email send failed: {exc}")


# ─────────────────────────────────────────────────────────────────
# Lifecycle
# ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    logger.info("transcript_starting")
    init_db(str(settings.postgres_dsn))
    init_redis(settings.redis_url)


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()
    await close_redis()


@app.get("/health", tags=["ops"])
async def health():
    return JSONResponse(content={"status": "healthy", "service": settings.service_name})
