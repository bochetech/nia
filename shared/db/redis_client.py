"""
Cliente Redis compartido para todos los servicios.
"""
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from redis.asyncio import Redis

from shared.utils.logging import get_logger

logger = get_logger(__name__)

_redis_client: Redis | None = None


def init_redis(url: str) -> None:
    """Inicializa el cliente Redis. Llamar en startup del servicio."""
    global _redis_client
    _redis_client = aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        retry_on_timeout=True,
    )
    logger.info("Redis client initialized", url=url)


def get_redis() -> Redis:
    if _redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        logger.info("Redis connection closed")


class RedisKeys:
    """Centraliza todos los patrones de clave Redis para evitar inconsistencias."""

    @staticmethod
    def session(tenant_id: str, session_id: str) -> str:
        return f"tenant:{tenant_id}:session:{session_id}"

    @staticmethod
    def session_fsm(tenant_id: str, session_id: str) -> str:
        return f"tenant:{tenant_id}:session:{session_id}:fsm"

    @staticmethod
    def tenant_config(tenant_id: str) -> str:
        return f"tenant:{tenant_id}:config"

    @staticmethod
    def rate_limit(tenant_id: str, action: str, window: str) -> str:
        return f"tenant:{tenant_id}:ratelimit:{action}:{window}"

    @staticmethod
    def availability_cache(product_id: str, date: str, pax: int) -> str:
        return f"availability:{product_id}:{date}:{pax}"

    @staticmethod
    def semantic_cache(tenant_id: str, query_hash: str) -> str:
        return f"tenant:{tenant_id}:scache:{query_hash}"

    @staticmethod
    def handoff_lock(session_id: str) -> str:
        return f"handoff:lock:{session_id}"

    @staticmethod
    def handoff_active(session_id: str) -> str:
        return f"handoff:active:{session_id}"

    @staticmethod
    def widget_token(token_hash: str) -> str:
        return f"widget:token:{token_hash}"
