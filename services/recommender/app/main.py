"""
Recommender Service — FastAPI entry point.
Puerto: 8004
"""

import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.engine import get_recommendations
from app.settings import get_settings
from shared.config.base import BaseServiceSettings
from shared.db.connection import close_db, get_db_session, init_db
from shared.db.redis_client import close_redis, init_redis
from shared.models.domain import IntentEntities, RecommendationResult
from shared.utils.logging import get_logger, setup_logging
from shared.utils.responses import APIResponse

settings = get_settings()
setup_logging(service_name=settings.service_name, log_level=settings.log_level, json_logs=settings.json_logs)
logger = get_logger(__name__)

app = FastAPI(
    title="NIA Recommender",
    description=(
        "**[Skill]** Product recommendation engine. "
        "Queries the tenant's PostgreSQL product catalogue using intent entities "
        "(category, date, time, pax, price range) and returns ranked suggestions. "
        "Invoked by the orchestrator when the FSM routes to the `recommend` action."
    ),
    version="1.0.0",
    openapi_tags=[
        {
            "name": "recommendations",
            "description": "Intent-driven product recommendation queries.",
        },
        {
            "name": "ops",
            "description": "Health and readiness probes.",
        },
    ],
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - t0) * 1000))
    return response


class RecommendRequest(BaseModel):
    tenant_id: str
    tenant_schema: str
    entities: IntentEntities
    top_k: int = 5


@app.post(
    "/v1/recommendations",
    response_model=APIResponse[RecommendationResult],
    summary="Get product recommendations based on user intent entities",
    tags=["recommendations"],
)
async def recommend(body: RecommendRequest) -> APIResponse[RecommendationResult]:
    async for db in get_db_session():
        result = await get_recommendations(
            tenant_id=body.tenant_id,
            tenant_schema=body.tenant_schema,
            entities=body.entities,
            session=db,
            top_k=body.top_k,
        )
    return APIResponse(data=result)


@app.on_event("startup")
async def on_startup():
    logger.info("recommender_starting")
    init_db(str(settings.postgres_dsn))
    init_redis(settings.redis_url)
    logger.info("recommender_ready", port=settings.port)


@app.on_event("shutdown")
async def on_shutdown():
    await close_db()
    await close_redis()


@app.get("/health", tags=["ops"])
async def health():
    return JSONResponse(content={"status": "healthy", "service": settings.service_name})
