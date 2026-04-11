"""
Tenant Manager — FastAPI entry point.
Puerto: 8003
"""

import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.routers import router
from app.settings import get_settings
from shared.db.connection import close_db, init_db
from shared.db.redis_client import close_redis, init_redis
from shared.utils.logging import get_logger, setup_logging

settings = get_settings()
setup_logging(
    service_name=settings.service_name,
    log_level=settings.log_level,
    json_logs=settings.json_logs,
)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA Tenant Manager",
    description="Multi-tenant provisioning, configuration and authentication service",
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


app.include_router(router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    logger.info("tenant_manager_starting", env=settings.env)
    init_db(str(settings.postgres_dsn))
    init_redis(settings.redis_url)
    logger.info("tenant_manager_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()
    await close_redis()
    logger.info("tenant_manager_shutdown")


@app.get("/health", tags=["ops"])
async def health():
    return JSONResponse(
        content={"status": "healthy", "service": settings.service_name}
    )


@app.get("/", include_in_schema=False)
async def root():
    return {"service": "nia-tenant-manager", "version": "1.0.0"}
