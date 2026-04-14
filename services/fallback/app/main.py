"""
Fallback Service — respuestas de emergencia cuando los servicios están caídos.
Puerto: 8009
"""

import random
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shared.config.base import BaseServiceSettings
from shared.db.redis_client import close_redis, init_redis
from shared.utils.logging import get_logger, setup_logging

FALLBACK_RESPONSES = [
    "Lo siento, estoy teniendo problemas técnicos en este momento. Por favor intenta de nuevo en unos minutos.",
    "Disculpa la interrupción. Nuestros sistemas están experimentando dificultades. ¿Puedo ayudarte con algo más sencillo?",
    "En este momento no puedo procesar tu solicitud. Por favor contáctanos directamente o intenta más tarde.",
]


class FallbackSettings(BaseServiceSettings):
    service_name: str = "fallback"
    port: int = 8009


_settings = None


def get_settings():
    global _settings
    if _settings is None:
        _settings = FallbackSettings()  # type: ignore[call-arg]
    return _settings


settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA Fallback Service",
    description=(
        "**[Skill]** Emergency fallback responses for when upstream services are unavailable. "
        "Returns a randomly-selected graceful error message so the user always gets a reply. "
        "Invoked by the orchestrator on timeout or critical skill failure."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "fallback",
            "description": "Retrieve a fallback message when the system cannot process a request normally.",
        },
        {
            "name": "ops",
            "description": "Health and readiness probes.",
        },
    ],
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get(
    "/v1/fallback/message",
    summary="Get a fallback error message",
    tags=["fallback"],
)
async def get_fallback_message(tenant_id: str | None = None) -> dict:
    message = random.choice(FALLBACK_RESPONSES)
    logger.warning("fallback_response_served", tenant_id=tenant_id)
    return {"message": message, "is_fallback": True}


@app.on_event("startup")
async def on_startup():
    init_redis(settings.redis_url)


@app.on_event("shutdown")
async def on_shutdown():
    await close_redis()


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "healthy", "service": settings.service_name}
