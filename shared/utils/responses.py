"""
Respuestas API estándar HATEOAS — Nivel Richardson 3.
Todas las respuestas siguen este formato unificado.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


class HATEOASLink(BaseModel):
    href: str
    method: str = "GET"
    rel: str | None = None


class ResponseMeta(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: str = "1"


class APIResponse(BaseModel, Generic[T]):
    """Respuesta estándar de la API con soporte HATEOAS."""
    data: T
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
    links: dict[str, HATEOASLink] = Field(default={}, alias="_links")

    model_config = {"populate_by_name": True}

    @classmethod
    def ok(
        cls,
        data: Any,
        links: dict[str, HATEOASLink] | None = None,
        request_id: str | None = None,
    ) -> "APIResponse":
        meta = ResponseMeta(request_id=request_id or str(uuid.uuid4()))
        return cls(data=data, meta=meta, links=links or {})


class PaginatedResponse(BaseModel, Generic[T]):
    """Respuesta paginada con cursor-based pagination."""
    data: list[T]
    meta: ResponseMeta = Field(default_factory=ResponseMeta)
    pagination: PaginationMeta
    links: dict[str, HATEOASLink] = Field(default={}, alias="_links")

    model_config = {"populate_by_name": True}


class PaginationMeta(BaseModel):
    total_returned: int
    has_more: bool
    next_cursor: str | None = None
    limit: int


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details para errores."""
    type: str = "https://nia.io/errors/generic-error"
    title: str
    status: int
    detail: str
    instance: str | None = None
    errors: list[dict[str, str]] | None = None


def problem_response(
    status: int,
    title: str,
    detail: str,
    error_type: str = "https://nia.io/errors/generic-error",
    errors: list[dict[str, str]] | None = None,
    instance: str | None = None,
) -> JSONResponse:
    problem = ProblemDetail(
        type=error_type,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
        errors=errors,
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(exclude_none=True),
        media_type="application/problem+json",
    )
