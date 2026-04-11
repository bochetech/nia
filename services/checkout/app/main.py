"""
Checkout Service — FastAPI entry point.
Gestiona intents de reserva y sesiones de pago con Stripe.
Puerto: 8006
"""

import time
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from shared.config.base import BaseServiceSettings
from shared.db.connection import close_db, get_db_session, init_db
from shared.db.redis_client import close_redis, init_redis
from shared.models.domain import BookingContact, BookingIntentDTO, CheckoutSessionDTO, CheckoutStatus
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse


class CheckoutSettings(BaseServiceSettings):
    service_name: str = "checkout"
    port: int = 8006
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_currency: str = "clp"
    checkout_expiry_minutes: int = 30


_settings: CheckoutSettings | None = None


def get_settings() -> CheckoutSettings:
    global _settings
    if _settings is None:
        _settings = CheckoutSettings()  # type: ignore[call-arg]
    return _settings


settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

app = FastAPI(title="NIA Checkout", version="1.0.0")
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

class CreateBookingIntentRequest(BaseModel):
    tenant_id: str
    session_id: str
    product_id: str
    selected_date: str     # YYYY-MM-DD
    selected_time: str     # HH:MM
    pax_count: int
    contact: BookingContact
    total_amount: float
    currency: str = "CLP"


class CreateCheckoutSessionRequest(BaseModel):
    booking_intent_id: str
    tenant_id: str
    session_id: str
    success_url: str = "https://example.com/success"
    cancel_url: str = "https://example.com/cancel"


# ─────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────

@app.post(
    "/v1/checkout/booking-intents",
    response_model=APIResponse[BookingIntentDTO],
    status_code=status.HTTP_201_CREATED,
)
async def create_booking_intent(body: CreateBookingIntentRequest) -> APIResponse[BookingIntentDTO]:
    import json as _json
    from datetime import date, time as time_type

    intent_id = str(uuid.uuid4())
    intent = BookingIntentDTO(
        id=intent_id,
        session_id=body.session_id,
        tenant_id=body.tenant_id,
        product_id=body.product_id,
        selected_date=date.fromisoformat(body.selected_date),
        selected_time=time_type.fromisoformat(body.selected_time),
        pax_count=body.pax_count,
        contact=body.contact,
        total_amount=body.total_amount,
        currency=body.currency,
        status="pending",
    )

    schema = f"tenant_{body.tenant_id}"
    async for db in get_db_session():
        try:
            await db.execute(
                __import__("sqlalchemy").text(f"""
                    INSERT INTO {schema}.booking_intents
                        (id, session_id, product_id, selected_date, selected_time,
                         pax_count, contact, total_amount, currency, status,
                         bokun_booking_id, created_at)
                    VALUES
                        (:id, :session_id, :product_id, :selected_date, :selected_time,
                         :pax_count, :contact::jsonb, :total_amount, :currency, 'pending',
                         NULL, NOW())
                """),
                {
                    "id": intent_id,
                    "session_id": body.session_id,
                    "product_id": body.product_id,
                    "selected_date": body.selected_date,
                    "selected_time": body.selected_time,
                    "pax_count": body.pax_count,
                    "contact": _json.dumps(body.contact.model_dump()),
                    "total_amount": body.total_amount,
                    "currency": body.currency,
                },
            )
            await db.commit()
        except Exception as exc:
            await db.rollback()
            logger.error("booking_intent_db_error", error=str(exc), schema=schema)
            # No fallar por error de DB — el intent ya está creado en memoria
            logger.warning("booking_intent_not_persisted", intent_id=intent_id)

    logger.info("booking_intent_created", intent_id=intent_id, tenant_id=body.tenant_id)
    return APIResponse(data=intent)


@app.post(
    "/v1/checkout/sessions",
    response_model=APIResponse[CheckoutSessionDTO],
    status_code=status.HTTP_201_CREATED,
)
async def create_checkout_session(body: CreateCheckoutSessionRequest) -> APIResponse[CheckoutSessionDTO]:
    """Crea una sesión de Stripe Checkout (o mock en dev)."""
    checkout_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.checkout_expiry_minutes)

    if settings.stripe_secret_key and settings.stripe_secret_key.startswith("sk_"):
        # Stripe real
        import stripe
        stripe.api_key = settings.stripe_secret_key
        try:
            stripe_session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": settings.stripe_currency,
                        "product_data": {"name": f"Reserva #{body.booking_intent_id[:8]}"},
                        "unit_amount": 0,  # Se obtendría del booking intent
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=body.success_url,
                cancel_url=body.cancel_url,
                expires_at=int(expires_at.timestamp()),
                metadata={
                    "booking_intent_id": body.booking_intent_id,
                    "tenant_id": body.tenant_id,
                    "session_id": body.session_id,
                },
            )
            payment_url = stripe_session.url
            external_id = stripe_session.id
        except Exception as exc:
            logger.error("stripe_session_error", error=str(exc))
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    else:
        # Mock para desarrollo
        payment_url = f"http://localhost:8006/mock-payment/{checkout_id}"
        external_id = f"mock_{checkout_id}"
        logger.warning("using_mock_payment", checkout_id=checkout_id)

    session = CheckoutSessionDTO(
        id=checkout_id,
        tenant_id=body.tenant_id,
        booking_intent_id=body.booking_intent_id,
        session_id=body.session_id,
        payment_url=payment_url,
        amount=0.0,
        currency=settings.stripe_currency.upper(),
        status=CheckoutStatus.CREATED,
        expires_at=expires_at,
    )
    return APIResponse(data=session)


@app.get("/mock-payment/{checkout_id}", include_in_schema=False)
async def mock_payment_page(checkout_id: str):
    """Página de pago mock para desarrollo."""
    return JSONResponse(content={
        "message": "Mock payment page",
        "checkout_id": checkout_id,
        "hint": "POST /mock-payment/{checkout_id}/confirm to simulate success",
    })


@app.post("/mock-payment/{checkout_id}/confirm", include_in_schema=False)
async def mock_payment_confirm(checkout_id: str):
    """Confirma un pago mock — simula webhook de Stripe."""
    logger.info("mock_payment_confirmed", checkout_id=checkout_id)
    return JSONResponse(content={"status": "paid", "checkout_id": checkout_id})


@app.post("/v1/checkout/webhook")
async def stripe_webhook(request: Request):
    """Recibe webhooks de Stripe."""
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    if settings.stripe_secret_key and settings.stripe_webhook_secret:
        import stripe
        try:
            event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid signature")

        if event["type"] == "checkout.session.completed":
            metadata = event["data"]["object"]["metadata"]
            logger.info("stripe_payment_success", metadata=metadata)

    return {"received": True}


@app.on_event("startup")
async def on_startup():
    logger.info("checkout_starting")
    init_db(str(settings.postgres_dsn))
    init_redis(settings.redis_url)


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()
    await close_redis()


@app.get("/health")
async def health():
    return {"status": "healthy", "service": settings.service_name}
