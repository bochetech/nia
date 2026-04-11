"""
Model Adapter — FastAPI application entry point.
Puerto: 8005
"""
from __future__ import annotations

import sys
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.providers.factory import create_provider, _provider_instance
from app.routers import chat, embed
from app.settings import get_settings
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse

settings = get_settings()
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_logs=settings.json_logs,
)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA Model Adapter",
    description="Abstraction layer for LLM providers (LM Studio, Vertex AI, OpenAI)",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    latency = (time.perf_counter() - t0) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round(latency))
    return response


# ── Routers ──────────────────────────────────────────────────────
app.include_router(chat.router, prefix="/v1")
app.include_router(embed.router, prefix="/v1")


# ── Lifecycle ────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    logger.info(
        "model_adapter_starting",
        provider=settings.model_provider,
        env=settings.env,
    )
    # Inicializar provider al arrancar
    create_provider(settings)
    logger.info("model_adapter_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    global _provider_instance
    if _provider_instance and hasattr(_provider_instance, "close"):
        await _provider_instance.close()
    logger.info("model_adapter_shutdown")


# ── Health ───────────────────────────────────────────────────────

@app.get("/health", tags=["ops"])
async def health():
    provider = create_provider(settings)
    provider_ok = await provider.health_check()
    status_str = "healthy" if provider_ok else "degraded"
    return JSONResponse(
        status_code=200 if provider_ok else 503,
        content={
            "status": status_str,
            "service": settings.service_name,
            "provider": settings.model_provider,
            "provider_reachable": provider_ok,
        },
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "nia-model-adapter", "version": "1.0.0"}
