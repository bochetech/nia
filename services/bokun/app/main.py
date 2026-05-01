"""
Bokun Skill Service — FastAPI entry point.
Puerto: 8011

Expone:
  GET  /v1/bokun/activities                           — lista de experiencias activas
  GET  /v1/bokun/activities/{activity_id}             — detalle de una experiencia
  POST /v1/bokun/activities/{activity_id}/availabilities — disponibilidad por rango de fechas
  GET  /health                                        — health probe
"""

import time
import uuid

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.client import BokunClient
from app.settings import get_settings
from shared.utils.health import build_health_router
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
    title="NIA Bokun Skill",
    description=(
        "**[Skill]** Bokun booking platform integration. "
        "Queries active experiences and real-time availability via the Bokun REST v1 API. "
        "Invoked by the orchestrator when the FSM needs to show tours, activities or "
        "check slots for a specific date range."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "bokun", "description": "Bokun activity catalogue and availability."},
        {"name": "ops", "description": "Health and readiness probes."},
    ],
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(build_health_router(check_redis=False, check_postgres=False), tags=["ops"])


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    t0 = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Latency-Ms"] = str(round((time.perf_counter() - t0) * 1000))
    return response


def _get_client() -> BokunClient:
    return BokunClient(
        access_key=settings.bokun_access_key,
        secret_key=settings.bokun_secret_key,
        base_url=settings.bokun_api_base_url,
    )


# ─────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────

class AvailabilityRequest(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$")
    end_date: str = Field(..., description="End date in YYYY-MM-DD format", pattern=r"^\d{4}-\d{2}-\d{2}$")
    currency: str = Field("CLP", description="ISO 4217 currency code (default: CLP)")
    lang: str = Field("ES", description="ISO 639-1 language code (ES, EN, ...)")
    include_sold_out: bool = Field(False, description="Include fully-booked slots in the response")


class ActivityListResponse(BaseModel):
    activities: list[dict]
    count: int


class AvailabilityResponse(BaseModel):
    activity_id: int
    slots: list[dict]
    count: int


# ─────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────

@app.get(
    "/v1/bokun/activities",
    response_model=APIResponse[ActivityListResponse],
    summary="List all active Bokun activities with details",
    tags=["bokun"],
)
async def list_activities(
    lang: str = "EN",
    currency: str = "USD",
    limit: int = 50,
):
    """
    Fetches all active activity IDs from Bokun (`/activity.json/active-ids`)
    and then retrieves the detail for each one concurrently.
    Returns up to `limit` activities.
    """
    client = _get_client()
    try:
        activities = await client.list_activities_with_details(
            lang=lang,
            currency=currency,
            limit=limit,
        )
    except Exception as exc:
        logger.error("bokun_list_activities_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bokun API error: {exc}",
        )

    logger.info("bokun_activities_listed", count=len(activities))
    return APIResponse(
        data=ActivityListResponse(activities=activities, count=len(activities))
    )


@app.get(
    "/v1/bokun/activities/{activity_id}",
    response_model=APIResponse[dict],
    summary="Get detail for a single Bokun activity",
    tags=["bokun"],
)
async def get_activity(
    activity_id: int,
    lang: str = "EN",
    currency: str = "USD",
):
    """
    Returns the full detail payload for a single activity.
    """
    client = _get_client()
    try:
        activity = await client.get_activity(activity_id, lang=lang, currency=currency)
    except Exception as exc:
        logger.error("bokun_get_activity_failed", activity_id=activity_id, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bokun API error: {exc}",
        )

    return APIResponse(data=activity)


@app.post(
    "/v1/bokun/activities/{activity_id}/availabilities",
    response_model=APIResponse[AvailabilityResponse],
    summary="Check availability for a Bokun activity",
    tags=["bokun"],
)
async def get_availabilities(activity_id: int, body: AvailabilityRequest):
    """
    Calls `POST /activity.json/{id}/availabilities` on Bokun.
    Returns the availability calendar for the requested date range.
    """
    client = _get_client()
    try:
        slots = await client.get_availabilities(
            activity_id,
            start_date=body.start_date,
            end_date=body.end_date,
            currency=body.currency,
            lang=body.lang,
            include_sold_out=body.include_sold_out,
        )
    except Exception as exc:
        logger.error(
            "bokun_availabilities_failed",
            activity_id=activity_id,
            start=body.start_date,
            end=body.end_date,
            error=str(exc),
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Bokun API error: {exc}",
        )

    logger.info(
        "bokun_availabilities_fetched",
        activity_id=activity_id,
        start=body.start_date,
        end=body.end_date,
        slots=len(slots),
    )
    return APIResponse(data=AvailabilityResponse(activity_id=activity_id, slots=slots, count=len(slots)))
