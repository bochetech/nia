"""
Bokun Adapter — stub para la integración con el sistema de reservas Bokun.

Estado: STUB — pendiente de materiales y credenciales de Bokun.
        Todos los métodos levantan NotImplementedError o devuelven datos mock.

Endpoints Bokun REST (v2) a implementar:
  POST /booking.json             → create booking
  GET  /booking/{id}.json        → get booking status
  POST /booking/{id}/confirm     → confirm booking
  POST /booking/{id}/cancel      → cancel booking
  GET  /product/{id}/availability → check availability
  GET  /product/{id}/price       → get price

Doc: https://bokun.io/developers/api
"""
from __future__ import annotations

import httpx
from pydantic import BaseModel
from shared.utils.logging import get_logger

logger = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────

class BokunConfig(BaseModel):
    access_key: str = ""          # BOKUN_ACCESS_KEY env var
    secret_key: str = ""          # BOKUN_SECRET_KEY env var
    vendor_id: str = ""           # BOKUN_VENDOR_ID env var
    base_url: str = "https://api.bokun.io"
    timeout: int = 30


# ─────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────

class BokunAvailabilityRequest(BaseModel):
    product_id: str
    date: str                     # YYYY-MM-DD
    pax_count: int = 1


class BokunAvailabilitySlot(BaseModel):
    time: str                     # HH:MM
    available_seats: int
    price_per_person: float
    currency: str = "CLP"


class BokunBookingRequest(BaseModel):
    product_id: str
    date: str                     # YYYY-MM-DD
    time: str                     # HH:MM
    pax_count: int
    contact_name: str
    contact_email: str
    contact_phone: str | None = None
    booking_intent_id: str        # Internal ID for reconciliation


class BokunBookingResult(BaseModel):
    bokun_booking_id: str
    confirmation_code: str
    status: str                   # CONFIRMED | PENDING | REJECTED
    total_amount: float
    currency: str


# ─────────────────────────────────────────────────────────────────
# Adapter
# ─────────────────────────────────────────────────────────────────

class BokunAdapter:
    """
    Wrapper asíncrono sobre la API REST de Bokun.

    STUB: todos los métodos son mock hasta que se proporcionen las credenciales.
    Para activar la integración real, setear las variables de entorno:
      BOKUN_ACCESS_KEY, BOKUN_SECRET_KEY, BOKUN_VENDOR_ID
    """

    def __init__(self, config: BokunConfig):
        self.config = config
        self._client: httpx.AsyncClient | None = None

    @property
    def is_configured(self) -> bool:
        return bool(self.config.access_key and self.config.secret_key and self.config.vendor_id)

    async def _client_headers(self) -> dict:
        """
        Bokun usa HMAC-SHA512 signing para autenticación.
        TODO: implementar firma según doc:
              https://bokun.io/developers/api#authentication
        """
        import hashlib, hmac, base64
        from datetime import datetime, UTC
        date_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
        message = f"{date_str}{self.config.access_key}"
        signature = hmac.new(
            self.config.secret_key.encode(),
            message.encode(),
            hashlib.sha512,
        ).digest()
        return {
            "X-Bokun-Date": date_str,
            "X-Bokun-AccessKey": self.config.access_key,
            "X-Bokun-Signature": base64.b64encode(signature).decode(),
            "Content-Type": "application/json;charset=UTF-8",
        }

    # ── Public API ────────────────────────────────────────────────

    async def get_availability(
        self, req: BokunAvailabilityRequest
    ) -> list[BokunAvailabilitySlot]:
        """
        Consulta disponibilidad para un producto en una fecha.
        STUB: devuelve datos mock hasta configurar credenciales.
        """
        if not self.is_configured:
            logger.warning("bokun_not_configured_using_mock", product_id=req.product_id)
            return _mock_availability(req)

        # TODO: implementar llamada real
        # GET /product/{product_id}/availability?date={date}&lang=es&currency=CLP
        raise NotImplementedError("Bokun real availability — pendiente de implementación")

    async def create_booking(self, req: BokunBookingRequest) -> BokunBookingResult:
        """
        Crea una reserva en Bokun.
        STUB: devuelve un resultado mock hasta configurar credenciales.
        """
        if not self.is_configured:
            logger.warning("bokun_not_configured_mock_booking", product_id=req.product_id)
            return _mock_booking(req)

        # TODO: implementar llamada real
        # POST /booking.json
        raise NotImplementedError("Bokun real booking — pendiente de implementación")

    async def get_booking_status(self, bokun_booking_id: str) -> dict:
        """
        Obtiene el estado actual de una reserva en Bokun.
        """
        if not self.is_configured:
            return {"status": "CONFIRMED", "id": bokun_booking_id}

        raise NotImplementedError("Bokun get_booking_status — pendiente de implementación")

    async def cancel_booking(self, bokun_booking_id: str, reason: str = "") -> dict:
        """
        Cancela una reserva en Bokun.
        """
        if not self.is_configured:
            return {"status": "CANCELLED", "id": bokun_booking_id}

        raise NotImplementedError("Bokun cancel_booking — pendiente de implementación")

    async def close(self):
        if self._client:
            await self._client.aclose()


# ─────────────────────────────────────────────────────────────────
# Mock helpers (desarrollo / tests)
# ─────────────────────────────────────────────────────────────────

def _mock_availability(req: BokunAvailabilityRequest) -> list[BokunAvailabilitySlot]:
    """Slots de disponibilidad ficticios para desarrollo."""
    return [
        BokunAvailabilitySlot(time="09:00", available_seats=12, price_per_person=85000.0),
        BokunAvailabilitySlot(time="14:00", available_seats=8, price_per_person=85000.0),
        BokunAvailabilitySlot(time="17:00", available_seats=4, price_per_person=75000.0),
    ]


def _mock_booking(req: BokunBookingRequest) -> BokunBookingResult:
    """Reserva ficticia para desarrollo."""
    import uuid
    return BokunBookingResult(
        bokun_booking_id=f"MOCK-{uuid.uuid4().hex[:8].upper()}",
        confirmation_code=f"CYT-{uuid.uuid4().hex[:6].upper()}",
        status="CONFIRMED",
        total_amount=req.pax_count * 85000.0,
        currency="CLP",
    )


# ─────────────────────────────────────────────────────────────────
# Singleton factory
# ─────────────────────────────────────────────────────────────────

_adapter: BokunAdapter | None = None


def get_bokun_adapter() -> BokunAdapter:
    """Devuelve el adapter singleton, inicializando config desde env vars."""
    global _adapter
    if _adapter is None:
        import os
        config = BokunConfig(
            access_key=os.getenv("BOKUN_ACCESS_KEY", ""),
            secret_key=os.getenv("BOKUN_SECRET_KEY", ""),
            vendor_id=os.getenv("BOKUN_VENDOR_ID", ""),
            base_url=os.getenv("BOKUN_BASE_URL", "https://api.bokun.io"),
        )
        _adapter = BokunAdapter(config)
        if not _adapter.is_configured:
            logger.info("bokun_adapter_mock_mode")
        else:
            logger.info("bokun_adapter_real_mode", vendor_id=config.vendor_id)
    return _adapter
