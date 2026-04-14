"""
shared/utils/health.py — Health check helpers reutilizables.

Cada servicio importa `build_health_router` y lo monta en su app.
Permite configurar qué dependencias verificar: Redis, Postgres, Qdrant.

Uso:
    from shared.utils.health import build_health_router
    app.include_router(build_health_router(check_redis=True, check_postgres=True))
"""
from __future__ import annotations

import time
from typing import Callable, Coroutine

from fastapi import APIRouter
from fastapi.responses import JSONResponse


def build_health_router(
    service_name: str = "service",
    *,
    check_redis: bool = False,
    check_postgres: bool = False,
    check_qdrant: bool = False,
    extra_checks: dict[str, Callable[[], Coroutine]] | None = None,
) -> APIRouter:
    """
    Devuelve un APIRouter con dos endpoints:
      GET /health/live  — liveness:  el proceso está vivo (siempre 200)
      GET /health/ready — readiness: todas las dependencias responden
    """
    router = APIRouter(tags=["ops"])

    @router.get("/health", include_in_schema=False)
    @router.get("/health/live", include_in_schema=False)
    async def liveness():
        return {"status": "alive", "service": service_name}

    @router.get("/health/ready")
    async def readiness():
        checks: dict[str, dict] = {}
        healthy = True

        if check_redis:
            result = await _check_redis()
            checks["redis"] = result
            if not result["ok"]:
                healthy = False

        if check_postgres:
            result = await _check_postgres()
            checks["postgres"] = result
            if not result["ok"]:
                healthy = False

        if check_qdrant:
            result = await _check_qdrant()
            checks["qdrant"] = result
            if not result["ok"]:
                healthy = False

        if extra_checks:
            for name, fn in extra_checks.items():
                result = await _run_check(name, fn)
                checks[name] = result
                if not result["ok"]:
                    healthy = False

        return JSONResponse(
            status_code=200 if healthy else 503,
            content={
                "status": "ready" if healthy else "degraded",
                "service": service_name,
                "checks": checks,
            },
        )

    return router


# ─────────────────────────────────────────────────────────────────
# Check implementations
# ─────────────────────────────────────────────────────────────────

async def _check_redis() -> dict:
    t0 = time.perf_counter()
    try:
        from shared.db.redis_client import get_redis
        redis = await get_redis()
        await redis.ping()
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - t0) * 1000)}


async def _check_postgres() -> dict:
    t0 = time.perf_counter()
    try:
        from shared.db.connection import get_db_session
        from sqlalchemy import text
        async for db in get_db_session():
            await db.execute(text("SELECT 1"))
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - t0) * 1000)}


async def _check_qdrant() -> dict:
    t0 = time.perf_counter()
    try:
        # Importar dentro del check para no requerir qdrant-client en servicios que no lo usan
        from qdrant_client import AsyncQdrantClient
        import os
        url = os.getenv("QDRANT_URL", "http://localhost:6333")
        client = AsyncQdrantClient(url=url)
        await client.get_collections()
        await client.close()
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - t0) * 1000)}


async def _run_check(name: str, fn: Callable) -> dict:
    t0 = time.perf_counter()
    try:
        await fn()
        return {"ok": True, "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - t0) * 1000)}
